"""Download a player's arena character and Circus Turma team from the game.

The public profile pages (``mod=player&p=<id>``, ``doll=1`` is the arena
character, ``doll=2`` the turma main character, ``doll=3..6`` the mercenaries)
can be read without logging in. The parsing follows the approach of
GladiatusPlayerStatsAPI (DinoDevs, LGPL-3.0,
https://github.com/DinoDevs/GladiatusPlayerStatsAPI), re-implemented in Python.

The page markup is parsed with regular expressions, so a change in the game's
HTML can break it. Use ``Client(debug_dir=...)`` to save the raw pages.
"""
from __future__ import annotations

import gzip
import hashlib
import html as htmllib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import threading
import urllib.request
import zlib
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .fighter import Fighter, php_round
from .roles_i18n import ROLE_TEXTS

DEFAULT_BASE = "https://s{server}-{country}.gladiatus.gameforge.com"
USER_AGENT = "Mozilla/5.0 (compatible; gladiatus-sim)"


class FetchError(Exception):
    pass


# --------------------------------------------------------------------- input
_SERVER_RE = re.compile(r"^\s*s?(\d+)[-_ ]?([a-zA-Z]{2})\s*$")


def parse_server(text: str) -> Tuple[str, str]:
    """'s51-en' / '51-en' / 's51 en' -> ('en', '51')."""
    m = _SERVER_RE.match(text)
    if not m:
        raise FetchError(f"cannot read server {text!r}, expected e.g. s51-en")
    return m.group(2).lower(), m.group(1)


def parse_player_spec(spec: str) -> Tuple[str, str, str]:
    """'Name@s51-en' -> (name, country, server). The last '@' separates."""
    if "@" not in spec:
        raise FetchError(f"{spec!r}: expected NAME@SERVER, e.g. Aveloca@s59-en")
    name, srv = spec.rsplit("@", 1)
    country, server = parse_server(srv)
    return name.strip(), country, server


# -------------------------------------------------------------------- client
class _Pace:
    def __init__(self, delay: float) -> None:
        self.delay = delay
        self.next = 0.0
        self.streak = 0


class Client:
    def __init__(self, base: str = DEFAULT_BASE, delay: float = 0.3,
                 timeout: float = 20, debug_dir: Optional[str] = None,
                 cache_dir: Optional[str] = None, cache_ttl: float = 600.0,
                 min_delay: float = 0.08) -> None:
        self.base = base
        self._lock = threading.Lock()
        self._default = _Pace(delay)
        self._paces = {}
        self.min_delay = min_delay          # the adaptive rate never goes below this
        self.cache_dir = cache_dir          # on-disk page cache (gzip), for GET requests only
        self.cache_ttl = cache_ttl
        self.timeout = timeout
        self.debug_dir = debug_dir
        self._cache = {}

    def url(self, country: str, server: str, query: str) -> str:
        root = self.base.format(country=country, server=server)
        return f"{root}/game/index.php?{query}"

    def _disk_path(self, url: str) -> str:
        return os.path.join(self.cache_dir, hashlib.md5(url.encode()).hexdigest() + ".html.gz")

    @staticmethod
    def _decode(raw: bytes, encoding: str) -> str:
        enc = encoding.lower()
        if "gzip" in enc:
            raw = gzip.decompress(raw)
        elif "deflate" in enc:
            try:
                raw = zlib.decompress(raw)
            except zlib.error:
                raw = zlib.decompress(raw, -zlib.MAX_WBITS)
        return raw.decode("utf-8", errors="replace")

    # Pacing is kept per game server (host): every server throttles on its own, so requests to
    # different servers never wait for each other.
    def _pace(self, host: Optional[str] = None) -> "_Pace":
        with self._lock:
            if host is None:
                return self._default
            p = self._paces.get(host)
            if p is None:
                p = self._paces[host] = _Pace(self._default.delay)
            return p

    @property
    def delay(self) -> float:
        return self._default.delay

    @delay.setter
    def delay(self, value: float) -> None:
        self._default.delay = value
        for p in self._paces.values():
            p.delay = min(p.delay, value)

    def _good(self, host: Optional[str] = None) -> None:
        """AIMD: every 15 requests in a row without a 503 the pause shrinks a bit."""
        p = self._pace(host)
        with self._lock:
            p.streak += 1
            if p.streak >= 15:
                p.streak = 0
                p.delay = max(self.min_delay, p.delay * 0.85)

    def _back_off(self, attempt: int, retry_after, slow_down: bool = True,
                  host: Optional[str] = None) -> None:
        """The game answers 503/429 when it is asked too fast: pause the threads talking to that
        server and permanently slow the request rate towards it down a little."""
        try:
            pause = float(retry_after)
        except (TypeError, ValueError):
            pause = 1.5 * 2 ** attempt
        pause = min(pause, 30.0)
        p = self._pace(host)
        with self._lock:
            p.streak = 0
            p.next = max(p.next, time.time() + pause)
            if slow_down:
                p.delay = min(max(p.delay, 0.1) * 1.5, 2.0)

    def _wait(self, host: Optional[str] = None) -> None:
        """Request spacing per server, safe to call from several threads."""
        p = self._pace(host)
        with self._lock:
            now = time.time()
            start = max(now, p.next)
            p.next = start + p.delay
        if start > now:
            time.sleep(start - now)

    def request(self, url: str, data: Optional[dict] = None) -> str:
        key = (url, json.dumps(data, sort_keys=True))
        if key in self._cache:
            return self._cache[key]
        disk = self._disk_path(url) if (self.cache_dir and data is None) else None
        if disk and os.path.exists(disk) and time.time() - os.path.getmtime(disk) < self.cache_ttl:
            try:
                with gzip.open(disk, "rt", encoding="utf-8") as fh:
                    text = fh.read()
                self._cache[key] = text
                return text
            except (OSError, EOFError):
                pass
        body = urllib.parse.urlencode(data).encode() if data is not None else None
        text = None
        last: Optional[Exception] = None
        host = urllib.parse.urlsplit(url).netloc
        for attempt in range(6):
            self._wait(host)
            req = urllib.request.Request(url, data=body, headers={
                "User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"})
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    raw = r.read()
                    enc = (getattr(r, "headers", None) or {}).get("Content-Encoding", "") or ""
                text = self._decode(raw, enc)
                self._good(host)
                break
            except urllib.error.HTTPError as e:
                last = e
                if e.code not in (429, 500, 502, 503, 504):
                    break
                self._back_off(attempt, e.headers.get("Retry-After") if e.headers else None, host=host)
            except (urllib.error.URLError, OSError) as e:
                last = e
                self._back_off(attempt, None, slow_down=False, host=host)
        if text is None:
            raise FetchError(f"request failed for {url}: {last}") from last
        if disk:
            try:
                os.makedirs(self.cache_dir, exist_ok=True)
                with gzip.open(disk, "wt", encoding="utf-8") as fh:
                    fh.write(text)
            except OSError:
                pass
        if self.debug_dir:
            os.makedirs(self.debug_dir, exist_ok=True)
            name = re.sub(r"[^A-Za-z0-9]+", "_", url.split("?", 1)[-1])[:80]
            with open(os.path.join(self.debug_dir, name + ".html"), "w",
                      encoding="utf-8") as fh:
                fh.write(text)
        self._cache[key] = text
        return text


# ------------------------------------------------------------------- parsing
def _backup_mode(html: str) -> bool:
    return '<h2 id="logoGladiatus_infobox"></h2>' in html


def _slice(html: str, head: int) -> str:
    """Drop page head/foot like the original library does (keeps tooltip indices stable)."""
    start = html.find('<div id="content">')
    if start < 0:
        start = head if len(html) > head + 2000 else 0
    return html[start:-2000] if len(html) > start + 2000 else html[start:]


def search_player(client: Client, country: str, server: str, name: str):
    """Find a player id by name through the highscore search. Returns (id, name)."""
    url = client.url(country, server, "mod=highscore&submod=suche")
    html = client.request(url, data={"s": "s", "xs": name})
    if len(html) > 42000:
        html = html[40000:-2000]
    if _backup_mode(html):
        raise FetchError(f"s{server}-{country}: the server is in backup mode")
    found = re.findall(
        r'<a\s+href="index\.php\?mod=player&p=(\d+)[^>]+>\s*([^<]+)</a>', html)
    for pid, pname in found:
        if pname.strip() == name:
            return pid, pname.strip()
    for pid, pname in found:
        if pname.strip().lower() == name.lower():
            return pid, pname.strip()
    raise FetchError(f"player {name!r} not found on s{server}-{country}")


def _num_list(html: str, allow_negative: bool) -> List[int]:
    pat = r"&quot;,(-?\d+)\],\s*\[&quot;#BA9700&quot;,&quot;#BA9700&quot;\]\]"
    if not allow_negative:
        pat = pat.replace("-?", "")
    return [int(x) for x in re.findall(pat, html)]


def _percent_list(html: str) -> List[int]:
    return [int(x) for x in re.findall(
        r"&quot;,&quot;(\d+) %&quot;\],\[&quot;#DDDDDD&quot;,&quot;#DDDDDD&quot;\]\]", html)]


def _grab(html: str, pattern: str, what: str):
    m = re.search(pattern, html)
    if not m:
        raise FetchError(f"could not find {what} on the page (the page layout may have changed)")
    return m


@dataclass
class RawCharacter:
    name: str
    level: int
    life_now: int
    life_max: int
    strength: int
    skill: int
    agility: int
    constitution: int
    charisma: int
    intelligence: int
    armor: int
    damage: Tuple[int, int]
    healing: int
    threat: int
    avoid_points: int
    block_points: int
    crit_points: int
    crit_heal_points: int
    percents: List[int]


_LANG_LABEL = re.compile(r"(?:nyelv|language|sprache|langue|idioma|lingua|j[eę]zyk|dil|язык|taal|jazyk|limba|γλώσσα)\s*:?", re.I)
_FLAG_CODE = [re.compile(p, re.I) for p in (
    r"flags?[/_\-.]+(?:\w+[/_\-.]+)?([a-z]{2})(?![a-z])",       # .../flags/hu.gif, flag_hu, flag-hu
    r"(?:^|[^a-z])([a-z]{2})\.(?:gif|png|jpg|svg)",               # .../hu.gif
    r"lang(?:uage)?[_\-]([a-z]{2})(?![a-z])")]


def parse_flag(html: str, page_url: str = "") -> Tuple[str, str]:
    """Nationality flag of a player's profile page, next to the 'Nyelv:' label.
    Returns (comma separated codes or '', absolute image URL or ''). The game marks the flags with
    ``<span class="language-flag ae">`` (a CSS sprite, there is no image URL), usually two of them."""
    box = re.search(r'class="flag-box"[^>]*>(.*?)</div>', html, re.I | re.S)
    codes = re.findall(r'language-flag\s+([A-Za-z_]+)', box.group(1) if box else html)
    if codes:
        return ",".join(c.lower() for c in codes), ""
    for m in _LANG_LABEL.finditer(html):
        seg = html[m.end(): m.end() + 600]
        end = re.search(r"</tr>|<tr[\s>]", seg, re.I)       # stay within the same table row
        if end:
            seg = seg[:end.start()]
        img = re.search(r"<img\b[^>]*>", seg, re.I)
        tag = img.group(0) if img else seg
        src = re.search(r'src\s*=\s*["\']([^"\']+)', tag, re.I)
        code = ""
        for pat in _FLAG_CODE:
            c = pat.search(tag)
            if c:
                code = c.group(1).lower()
                break
        if not code:
            c = re.search(r'(?:alt|title)\s*=\s*["\']([A-Za-z]{2})["\']', tag)
            code = c.group(1).lower() if c else ""
        url = urllib.parse.urljoin(page_url, htmllib.unescape(src.group(1))) if src else ""
        if code or url:
            return code, url
    return "", ""


def parse_character_page(html: str, head: int = 40000) -> RawCharacter:
    if _backup_mode(html):
        raise FetchError("the game server is in backup mode")
    h = _slice(html, head)
    name = _grab(h, r'<div class="playername(?:_achievement)* ellipsis">([^<]+)</div>',
                 "player name").group(1).strip()
    level = int(_grab(h, r'<span id="char_level" class="charstats_value22">(\d+)</span>', "level").group(1))
    life = _grab(h, r'<div\s+class="charstats_bg"\s+id="char_leben_tt"\s+data-tooltip="\[\[\[\[[^,]+,'
                    r'&quot;(\d+)\s*\\/\s*(\d+)&quot;', "life")
    stat = lambda i: int(_grab(h, rf'<span id="char_f{i}" class="charstats_value">(\d+)</span>', f"stat {i}").group(1))
    armor = int(_grab(h, r'<span id="char_panzer" class="charstats_value22">(\d+)</span>', "armor").group(1))
    dmg = _grab(h, r'<span id="char_schaden" class="charstats_value22">(\d+)\s*-\s*(\d+)</span>', "damage")
    healing = int(_grab(h, r'<span id="char_healing" class="charstats_value22">(\d+)</span>', "healing").group(1))
    t = re.search(r'<span id="char_threat" class="charstats_value22">(\d+)</span>', h)
    nums = _num_list(h, allow_negative=True)
    if len(nums) <= 10:
        raise FetchError("could not find the critical / block rating tooltips")
    return RawCharacter(
        name=name, level=level, life_now=int(life.group(1)), life_max=int(life.group(2)),
        strength=stat(0), skill=stat(1), agility=stat(2), constitution=stat(3),
        charisma=stat(4), intelligence=stat(5), armor=armor,
        damage=(int(dmg.group(1)), int(dmg.group(2))), healing=healing,
        threat=int(t.group(1)) if t else 0,
        avoid_points=nums[7], block_points=nums[8], crit_points=nums[9],
        crit_heal_points=nums[11] if len(nums) > 11 else 0,
        percents=_percent_list(h),
    )


def parse_roles(html: str, country: str) -> List[Optional[str]]:
    """Roles of the 5 turma slots (main + 4 mercenaries) from the doll=2 page.

    Returns a list of 5 entries: 'tank' | 'dps' | 'healer' | 'out' | None (no
    such slot). Unknown texts are treated as 'dps'.
    """
    h = html[html.find('<div id="content">'):] if '<div id="content">' in html else html
    own = ROLE_TEXTS.get(country, {})
    roles: List[Optional[str]] = []
    for doll in range(2, 7):
        m = re.search(rf'<div class="charmercpic doll{doll}"\s*data-tooltip="([^"]+)"', h)
        if not m:
            if doll == 2:
                raise FetchError("could not find the turma main character slot")
            roles.append(None)
            continue
        roles.append(_resolve_role(m.group(1), own))
    return roles


def _resolve_role(tooltip: str, own: dict) -> str:
    try:
        data = json.loads(htmllib.unescape(tooltip))
        inner = data[0][0][0]
    except (ValueError, IndexError, TypeError):
        return "dps"
    m = re.search(r"<font style=font-size:smaller;color:#DDDDDD>([^<]+)</font>", inner)
    if not m:
        return "dps"
    text = m.group(1).strip()
    for role in ("tank", "dps", "healer", "out"):
        if own.get(role) == text:
            return role
    # server language not in our table: try every language
    for texts in ROLE_TEXTS.values():
        for role in ("tank", "dps", "healer", "out"):
            if texts.get(role) == text:
                return role
    return "dps"


# ------------------------------------------------------------ build fighters
def to_fighter(raw: RawCharacter, role: str = "dps", is_main: bool = False,
               name: Optional[str] = None, use_current_life: bool = False) -> Fighter:
    pct = raw.percents
    crit_pct = pct[2] if len(pct) >= 4 else None
    heal_crit = pct[3] if len(pct) >= 4 else 0.0
    f = Fighter(
        name=name or raw.name, level=raw.level, life=raw.life_max,
        current_life=raw.life_now if use_current_life else raw.life_max,
        skill=raw.skill, agility=raw.agility, charisma=raw.charisma,
        intelligence=raw.intelligence, armor=raw.armor, damage=raw.damage,
        critical_points=raw.crit_points, block_points=raw.block_points,
        avoid_critical_points=raw.avoid_points,
        healing=raw.healing, critical_healing_chance=heal_crit,
        threat=raw.threat, role=role, is_main=is_main,
    )
    # Honour of the veteran etc.: the page percentage includes buffs that the
    # rating points do not, so prefer the displayed value when it differs.
    if crit_pct is not None and crit_pct != f.crit_chance(cap=10 ** 6):
        f.critical_chance = crit_pct
    return f


def fetch_arena_fighter(client: Client, name: str, country: str, server: str) -> Fighter:
    pid, real_name = search_player(client, country, server, name)
    url = client.url(country, server, f"mod=player&p={pid}")
    html = client.request(url)
    raw = parse_character_page(html)
    f = to_fighter(raw, use_current_life=True)
    f.name = f"{real_name}@s{server}-{country}"
    f.flag, f.flag_url = parse_flag(html, url)
    veteran = raw.percents[2] - php_round(raw.crit_points * 52 / max(2, raw.level - 8) / 5) == 10 \
        if len(raw.percents) >= 4 else False
    if veteran:
        f.buffs = frozenset({"honour_veteran"})
        f.critical_chance = None      # the arena engine adds the +10 itself
    return f


def fetch_turma_team(client: Client, name: str, country: str, server: str,
                     keep_idle: bool = False) -> List[Fighter]:
    pid, real_name = search_player(client, country, server, name)
    return fetch_turma_team_by_id(client, pid, country, server, f"{real_name}@s{server}-{country}", keep_idle)


def fetch_turma_team_by_id(client: Client, pid: str, country: str, server: str, label: str,
                           keep_idle: bool = False) -> List[Fighter]:
    team: List[Fighter] = []
    roles = None
    for slot, doll in enumerate(range(2, 7)):
        if roles is not None and roles[slot] is None:
            continue
        html = client.request(client.url(country, server, f"mod=player&doll={doll}&p={pid}"))
        if slot == 0:
            roles = parse_roles(html, country)
        if roles[slot] == "out" and not keep_idle:
            continue
        raw = parse_character_page(html)
        name = label if slot == 0 else f"{raw.name} #{slot}"
        team.append(to_fighter(raw, role=roles[slot], is_main=(slot == 0), name=name))
    if not team:
        raise FetchError("the turma team is empty")
    return team


def fighter_to_dict(f: Fighter) -> dict:
    d = {k: getattr(f, k) for k in (
        "name", "level", "life", "skill", "agility", "charisma", "intelligence",
        "armor", "critical_points", "block_points", "avoid_critical_points",
        "critical_chance", "block_chance", "avoid_critical_chance", "healing",
        "critical_healing_chance", "threat", "role", "is_main")}
    d["damage"] = list(f.damage)
    d["current_life"] = f.current_life
    if f.buffs:
        d["buffs"] = sorted(f.buffs)
    return {k: v for k, v in d.items() if v is not None}


# ------------------------------------------------------------------- guilds
EMPTY_SH = "d41d8cd98f00b204e9800998ecf8427e"      # md5("") - the public, not logged in token


@dataclass
class GuildMember:
    pid: str
    name: str
    rank: str = ""
    level: int = 0


def parse_guild_ref(text: str) -> Optional[str]:
    """A guild id given directly: '2562' or a URL containing '...&i=2562'. Else None."""
    t = text.strip()
    if re.fullmatch(r"\d+", t):
        return t
    m = re.search(r"[?&]i=(\d+)", t)
    return m.group(1) if m else None


def search_guild(client: Client, country: str, server: str, name: str):
    """Find a guild id by its full name through the highscore search. Returns (id, name).

    The game's guild search markup could not be checked from the build environment, so
    several request shapes are tried; if none works the caller should enter the guild id
    (the ``i=`` value of the guild page URL) instead of the name.
    """
    gid = parse_guild_ref(name)
    if gid:
        return gid, name.strip()
    attempts = [
        ("mod=highscore&submod=suche&t=1", {"s": "s", "xs": name, "t": "1"}),
        ("mod=highscore&submod=suche", {"s": "s", "xs": name, "t": "1"}),
        ("mod=highscore&t=1", {"s": "s", "xs": name}),
        ("mod=highscore&submod=suche", {"s": "s", "xs": name}),
    ]
    found: List[Tuple[str, str]] = []
    for query, data in attempts:
        html = client.request(client.url(country, server, query), data=data)
        if _backup_mode(html):
            raise FetchError(f"s{server}-{country}: the server is in backup mode")
        found = re.findall(
            r'<a\s+[^>]*href="index\.php\?mod=guild&(?:amp;)?(?:submod=\w+&(?:amp;)?)?'
            r'i=(\d+)[^"]*"[^>]*>\s*([^<]+?)\s*</a>', html)
        if found:
            break
    def norm(t: str) -> str:          # full name or [TAG]: brackets and case do not matter
        return re.sub(r"[\[\]\s]", "", htmllib.unescape(t)).lower()

    for gid, gname in found:
        if gname.strip() == name.strip():
            return gid, gname.strip()
    for gid, gname in found:
        if norm(gname) == norm(name):
            return gid, gname.strip()
    seen = ", ".join(sorted({g.strip() for _, g in found})[:6])
    raise FetchError(
        f"guild {name!r} not found on s{server}-{country}"
        + (f" (the search returned: {seen})" if seen else "")
        + ("; the game's guild list shows only the guild tags, so enter the tag (e.g. [TiGeR]) "
           "or the guild id" if seen else "")
        + "; the guild id is the number after 'i=' in the guild page URL")


def parse_member_list(html: str) -> List[GuildMember]:
    """All members of a member-list page. Rows with rank/level are read precisely, any
    other player link on the page is still picked up (with unknown rank/level)."""
    members: List[GuildMember] = []
    seen = set()
    for pid, name, rank, level in re.findall(
            r'<tr>\s*<td>\s*<a\s+href="index\.php\?mod=player&(?:amp;)?p=(\d+)[^"]*">\s*([^<]+?)\s*</a>'
            r'\s*</td>\s*<td>\s*([^<]*?)\s*</td>\s*<td>\s*(\d+)\s*</td>', html):
        if pid not in seen:
            seen.add(pid)
            members.append(GuildMember(pid, htmllib.unescape(name), htmllib.unescape(rank), int(level)))
    for pid, name in re.findall(
            r'<a\s+href="index\.php\?mod=player&(?:amp;)?p=(\d+)[^"]*">\s*([^<]+?)\s*</a>', html):
        if pid not in seen:
            seen.add(pid)
            members.append(GuildMember(pid, htmllib.unescape(name)))
    return members


def parse_member_total(html: str) -> int:
    """'128 / 129 Members' on the guild page: the number of members (first number)."""
    m = re.search(r"(\d+)\s*/\s*(\d+)\s*(?:Tagok|Members|Mitglieder|Miembros|Membres|Membri)", html)
    return int(m.group(1)) if m else 0


def fetch_guild_info(client: Client, country: str, server: str, gid: str):
    """(full name, member count) from the guild's public page; (None, 0) when unreadable."""
    try:
        html = client.request(client.url(
            country, server, f"mod=guild&submod=forumGladiatorius&i={gid}&sh={EMPTY_SH}"))
    except FetchError:
        return None, 0
    m = re.search(r"<t[dh][^>]*>\s*(?:N[eé]v|Name)\s*:?\s*</t[dh]>(?:\s*<[^>]+>)*?\s*([^<\s][^<]*?)\s*<", html)
    return (htmllib.unescape(m.group(1)) if m else None), parse_member_total(html)


def fetch_guild_members(client: Client, country: str, server: str, gid: str) -> List[GuildMember]:
    html = client.request(client.url(
        country, server, f"mod=guild&submod=memberList&i={gid}&sh={EMPTY_SH}"))
    if _backup_mode(html):
        raise FetchError(f"s{server}-{country}: the server is in backup mode")
    members = parse_member_list(html)
    if not members:
        raise FetchError(f"no members found on the member list of guild {gid} "
                         "(the guild does not exist or its member list is not public)")
    return members


def fetch_arena_fighter_by_id(client: Client, pid: str, country: str, server: str,
                              name: str = "") -> Fighter:
    url = client.url(country, server, f"mod=player&p={pid}")
    html = client.request(url)
    raw = parse_character_page(html)
    f = to_fighter(raw, use_current_life=True)
    f.name = name or raw.name
    f.flag, f.flag_url = parse_flag(html, url)
    if len(raw.percents) >= 4 and \
            raw.percents[2] - php_round(raw.crit_points * 52 / max(2, raw.level - 8) / 5) == 10:
        f.buffs = frozenset({"honour_veteran"})
        f.critical_chance = None
    return f
