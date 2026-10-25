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

import html as htmllib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
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
class Client:
    def __init__(self, base: str = DEFAULT_BASE, delay: float = 0.3,
                 timeout: float = 20, debug_dir: Optional[str] = None) -> None:
        self.base = base
        self.delay = delay
        self.timeout = timeout
        self.debug_dir = debug_dir
        self._cache = {}
        self._last = 0.0

    def url(self, country: str, server: str, query: str) -> str:
        root = self.base.format(country=country, server=server)
        return f"{root}/game/index.php?{query}"

    def _wait(self) -> None:
        wait = self.delay - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.time()

    def request(self, url: str, data: Optional[dict] = None) -> str:
        key = (url, json.dumps(data, sort_keys=True))
        if key in self._cache:
            return self._cache[key]
        self._wait()
        body = urllib.parse.urlencode(data).encode() if data is not None else None
        req = urllib.request.Request(url, data=body, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                text = r.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, OSError) as e:
            raise FetchError(f"request failed for {url}: {e}") from e
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
    html = client.request(client.url(country, server, f"mod=player&p={pid}"))
    raw = parse_character_page(html)
    f = to_fighter(raw, use_current_life=True)
    f.name = f"{real_name}@s{server}-{country}"
    veteran = raw.percents[2] - php_round(raw.crit_points * 52 / max(2, raw.level - 8) / 5) == 10 \
        if len(raw.percents) >= 4 else False
    if veteran:
        f.buffs = frozenset({"honour_veteran"})
        f.critical_chance = None      # the arena engine adds the +10 itself
    return f


def fetch_turma_team(client: Client, name: str, country: str, server: str,
                     keep_idle: bool = False) -> List[Fighter]:
    pid, real_name = search_player(client, country, server, name)
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
        label = f"{real_name}@s{server}-{country}" if slot == 0 else f"{raw.name} #{slot}"
        team.append(to_fighter(raw, role=roles[slot], is_main=(slot == 0), name=label))
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
