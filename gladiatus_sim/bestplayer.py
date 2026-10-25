"""Best player search: collect the players of a level interval from the highscore lists of
several servers, let them fight each other in simulated arena battles and rank them.

The highscore markup could not be checked from the build environment. The crawler therefore
follows the pages' own links and finds the level column by its header; see ``parse_highscore``.
"""
from __future__ import annotations

import html as htmllib
import json
import random
import re
import socket
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from .arena import arena_battle
from .fetch import (Client, FetchError, _backup_mode, fetch_arena_fighter_by_id,
                    fetch_turma_team_by_id)
from .fighter import Fighter
from .turma import turma_battle

LEVEL_WORDS = re.compile(r"szint|level|stufe|nivel|niveau|livello|poziom|n[ií]vel|seviye|уров|lvl", re.I)


@dataclass
class Candidate:
    pid: str
    name: str
    level: int
    server: str
    country: str = "en"

    @property
    def label(self) -> str:
        return f"{self.name}@s{self.server}-{self.country}"


LOBBY_APIS = (
    "https://lobby.gladiatus.gameforge.com/api/servers",
    "https://lobby.gameforge.com/api/servers",
)


def _servers_from_json(text: str, country: str) -> List[str]:
    """Server numbers of a country from a lobby-style JSON list (several shapes tolerated)."""
    try:
        data = json.loads(text)
    except ValueError:
        return []
    out: List[str] = []
    for item in data if isinstance(data, list) else []:
        if not isinstance(item, dict):
            continue
        lang = str(item.get("language") or item.get("lang") or item.get("country") or "").lower()
        game = str(item.get("gameEnvironmentId") or item.get("game") or "gladiatus").lower()
        num = item.get("number") or item.get("server") or item.get("id")
        if lang in (country, "") and "gladiatus" in game or lang == country:
            if str(num).isdigit():
                out.append(str(num))
    return sorted(set(out), key=int)


def discover_servers(client: Client, country: str = "en", max_number: int = 300,
                     progress: Optional[Callable] = None) -> List[str]:
    """Every existing server of a country, found dynamically.

    1. The public lobby server list is tried (JSON).
    2. Otherwise the host names ``s<N>-<country>.gladiatus.gameforge.com`` are probed: names that
       resolve in DNS are then checked with one request to the game.
    """
    for url in LOBBY_APIS:
        try:
            found = _servers_from_json(client.request(url), country)
        except FetchError:
            continue
        if found:
            return found
    root = client.base

    def resolves(n: int) -> bool:
        host = re.sub(r"^https?://", "", root.format(country=country, server=n)).split("/")[0]
        try:
            socket.getaddrinfo(host, 443)
            return True
        except OSError:
            return False

    with ThreadPoolExecutor(max_workers=32) as ex:
        cands = [n for n, ok in zip(range(1, max_number + 1), ex.map(resolves, range(1, max_number + 1))) if ok]
    alive: List[str] = []
    done = [0]

    def alive_check(n: int) -> bool:
        try:
            html = client.request(client.url(country, str(n), "mod=highscore"))
            return "mod=player" in html or "highscore" in html
        except FetchError:
            return False
        finally:
            done[0] += 1
            if progress:
                progress(f"Szerverek keresése: {done[0]}/{len(cands)}")

    with ThreadPoolExecutor(max_workers=8) as ex:
        for n, ok in zip(cands, ex.map(alive_check, cands)):
            if ok:
                alive.append(str(n))
    return alive


def parse_server_range(text: str) -> List[str]:
    """'1-5, 12, 20-22' -> ['1','2','3','4','5','12','20','21','22']."""
    out: List[str] = []
    for part in re.split(r"[,\s;]+", text.strip()):
        if not part:
            continue
        m = re.fullmatch(r"s?(\d+)\s*-\s*s?(\d+)", part)
        if m:
            lo, hi = int(m.group(1)), int(m.group(2))
            if hi < lo or hi - lo > 500:
                raise ValueError(f"bad server range {part!r}")
            out += [str(i) for i in range(lo, hi + 1)]
        elif re.fullmatch(r"s?\d+", part):
            out.append(part.lstrip("s"))
        else:
            raise ValueError(f"bad server {part!r}")
    seen = set()
    return [s for s in out if not (s in seen or seen.add(s))]


def _cells(row_html: str) -> List[str]:
    return [re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", c))).strip()
            for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row_html, re.S)]


def _num(text: str) -> Optional[int]:
    t = re.sub(r"[.\s,]", "", text)
    return int(t) if t.isdigit() else None


def parse_highscore(html: str) -> Tuple[List[Tuple[str, str, Optional[int]]], List[str]]:
    """(rows, next page links). Rows are (player id, name, level or None).

    The level column is found by its header text; without a header the first plausible
    number (<= 500) after the name is used.
    """
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S)
    level_idx: Optional[int] = None
    for r in rows:
        if "<th" in r:
            cells = _cells(r)
            for i, c in enumerate(cells):
                if LEVEL_WORDS.search(c):
                    level_idx = i
                    break
        if level_idx is not None:
            break
    out: List[Tuple[str, str, Optional[int]]] = []
    for r in rows:
        m = re.search(r'<a\s+[^>]*href="[^"]*mod=player&(?:amp;)?p=(\d+)[^"]*"[^>]*>\s*([^<]+?)\s*</a>', r)
        if not m:
            continue
        cells = _cells(r)
        level = None
        if level_idx is not None and level_idx < len(cells):
            level = _num(cells[level_idx])
        if level is None:
            name_pos = next((i for i, c in enumerate(cells) if htmllib.unescape(m.group(2)) in c), 0)
            for c in cells[name_pos + 1:]:
                v = _num(c)
                if v is not None and 1 <= v <= 500:
                    level = v
                    break
        out.append((m.group(1), htmllib.unescape(m.group(2)), level))
    links = []
    for href in re.findall(r'href="(index\.php\?mod=highscore[^"]*)"', html):
        h = htmllib.unescape(href)
        if re.search(r"[?&]t=1\b|submod=suche", h):          # guild list / search form
            continue
        if h not in links:
            links.append(h)
    return out, links


def _page_key(href: str) -> str:
    return re.sub(r"[?&]sh=[0-9a-f]+", "", href)


def crawl_server(client: Client, country: str, server: str, level_min: int, level_max: int,
                 max_players: int = 10 ** 9, max_pages: int = 2000) -> List[Candidate]:
    """Walk the highscore pages of a server and collect players of the level interval."""
    queue = ["index.php?mod=highscore"]
    visited = set()
    found: List[Candidate] = []
    ids = set()
    while queue and len(visited) < max_pages and len(found) < max_players:
        href = queue.pop(0)
        key = _page_key(href)
        if key in visited:
            continue
        visited.add(key)
        root = client.base.format(country=country, server=server)
        html = client.request(f"{root}/game/{href}")
        if _backup_mode(html):
            raise FetchError(f"s{server}-{country}: the server is in backup mode")
        rows, links = parse_highscore(html)
        for pid, name, level in rows:
            if level is not None and level_min <= level <= level_max and pid not in ids:
                ids.add(pid)
                found.append(Candidate(pid, name, level, server, country))
        for h in links:
            if _page_key(h) not in visited and h not in queue:
                queue.append(h)
    return found[:max_players]


def collect_candidates(client: Client, servers: Sequence[str], country: str, level_min: int,
                       level_max: int, per_server: int = 10 ** 9, progress: Optional[Callable] = None,
                       workers: int = 4) -> Tuple[List[Candidate], Dict[str, str]]:
    """Candidates from all servers (errors per server are returned, not raised)."""
    errors: Dict[str, str] = {}
    result: List[Candidate] = []
    done = [0]

    def one(srv):
        try:
            return crawl_server(client, country, srv, level_min, level_max, per_server)
        except Exception as e:                       # noqa: BLE001 - reported per server
            errors[srv] = f"{type(e).__name__}: {e}"[:120]
            return []
        finally:
            done[0] += 1
            if progress:
                progress(f"Szerverek bejárása: {done[0]}/{len(servers)}")

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for lst in ex.map(one, servers):
            result += lst
    return result, errors


def load_fighters(client: Client, cands: Sequence[Candidate], progress: Optional[Callable] = None,
                  workers: int = 8) -> Tuple[List[Fighter], List[str]]:
    done = [0]
    failed: List[str] = []

    def one(c):
        try:
            f = fetch_arena_fighter_by_id(client, c.pid, c.country, c.server, name=c.label)
            f.level = f.level or c.level
            return f
        except Exception as e:                       # noqa: BLE001
            failed.append(f"{c.label}: {type(e).__name__}")
            return None
        finally:
            done[0] += 1
            if progress:
                progress(f"Játékosok letöltése: {done[0]}/{len(cands)}")

    with ThreadPoolExecutor(max_workers=workers) as ex:
        loaded = list(ex.map(one, cands))
    return [f for f in loaded if f is not None], failed


def load_teams(client: Client, cands: Sequence[Candidate], progress: Optional[Callable] = None,
               workers: int = 8) -> Tuple[List[List[Fighter]], List[str]]:
    """Turma teams (main character + mercenaries with their roles) of the candidates."""
    done = [0]
    failed: List[str] = []

    def one(c):
        try:
            team = fetch_turma_team_by_id(client, c.pid, c.country, c.server, c.label)
            team[0].level = team[0].level or c.level
            return team
        except Exception as e:                       # noqa: BLE001
            failed.append(f"{c.label}: {type(e).__name__}")
            return None
        finally:
            done[0] += 1
            if progress:
                progress(f"Csapatok letöltése: {done[0]}/{len(cands)}")

    with ThreadPoolExecutor(max_workers=workers) as ex:
        loaded = list(ex.map(one, cands))
    return [t for t in loaded if t], failed


# ------------------------------------------------------------------ tournament
@dataclass
class Ranking:
    fighter: Fighter          # the main character (in turma mode the team's first member)
    stage1: float            # win rate against random opponents (%)
    final: float             # win rate in the final round robin (%), -1 if not a finalist
    battles: int
    team: Optional[List[Fighter]] = None


def _duel(a, b, rng: random.Random, n: int, life_mode: str, mode: str = "arena") -> float:
    """Wins of a against b over n battles (half as attacker, half as defender); draw = 0.5.
    In ``turma`` mode a and b are teams (lists of fighters)."""
    if mode == "turma":
        fight = lambda x, y: {0: 1, 1: -1, -1: 0}[turma_battle(x, y, rng).winner]
    else:
        fight = lambda x, y: arena_battle(x, y, rng, life_mode).result
    w = 0.0
    for k in range(n):
        if k % 2 == 0:
            r = fight(a, b)
            w += 1 if r == 1 else 0.5 if r == 0 else 0
        else:
            r = fight(b, a)
            w += 1 if r == -1 else 0.5 if r == 0 else 0
    return w


def tournament(fighters: Sequence, samples: int = 2, finalists: int = 16,
               final_samples: int = 100, seed: Optional[int] = None, life_mode: str = "full",
               top: int = 5, battle_budget: Optional[int] = None, mode: str = "arena",
               progress: Optional[Callable] = None) -> List[Ranking]:
    """Stage 1: everybody fights everybody (``samples`` battles per pair) as long as that fits into
    ``battle_budget`` battles; with more players each fights a random subset of the others.
    Stage 2: the best ``finalists`` fight a round robin (``final_samples`` per pair).
    Returns the best ``top`` players."""
    rng = random.Random(seed)
    if battle_budget is None:
        battle_budget = 150_000 if mode == "turma" else 4_000_000
    fs = list(fighters)
    n = len(fs)
    if n < 2:
        raise ValueError("at least two players are needed")
    samples = max(1, samples)
    pairs_total = n * (n - 1) // 2
    per_pair = samples
    if pairs_total * per_pair > battle_budget:
        per_pair = 1
    wins = [0.0] * n
    games = [0] * n
    if pairs_total * per_pair <= battle_budget:
        plan = ((i, j) for i in range(n) for j in range(i + 1, n))           # everybody vs everybody
    else:
        k = max(1, battle_budget // (n * per_pair) // 1)

        def sampled():
            for i in range(n):
                for j in rng.sample([x for x in range(n) if x != i], min(k, n - 1)):
                    yield i, j
        plan = sampled()
    last = -1
    for i, j in plan:
        w = _duel(fs[i], fs[j], rng, per_pair, life_mode, mode)
        wins[i] += w
        wins[j] += per_pair - w
        games[i] += per_pair
        games[j] += per_pair
        if progress and i != last and i % 25 == 0:
            progress(f"Selejtező: {i + 1}/{n}")
            last = i
    rate1 = [100 * wins[i] / games[i] if games[i] else 0.0 for i in range(n)]
    order = sorted(range(n), key=lambda i: -rate1[i])[:max(2, min(finalists, n))]
    fw = {i: 0.0 for i in order}
    fg = {i: 0 for i in order}
    for x in range(len(order)):
        for y in range(x + 1, len(order)):
            i, j = order[x], order[y]
            w = _duel(fs[i], fs[j], rng, final_samples, life_mode, mode)
            fw[i] += w
            fw[j] += final_samples - w
            fg[i] += final_samples
            fg[j] += final_samples
        if progress:
            progress(f"Döntő: {x + 1}/{len(order)}")
    ranked = sorted(order, key=lambda i: -fw[i] / fg[i])
    def mk(i):
        team = fs[i] if mode == "turma" else None
        return Ranking(team[0] if team else fs[i], rate1[i], 100 * fw[i] / fg[i], games[i] + fg[i], team)
    return [mk(i) for i in ranked[:top]]
