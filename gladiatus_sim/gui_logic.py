"""Tk-független logika a grafikus felülethez (tesztelhető)."""
from __future__ import annotations

from typing import List, Optional, Tuple

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from .arena import simulate_arena
from .fetch import (Client, FetchError, fetch_arena_fighter, fetch_arena_fighter_by_id,
                    fetch_guild_info, fetch_guild_members, fetch_turma_team, parse_player_spec, search_guild)
from .bestplayer import (collect_candidates, discover_servers, load_fighters, load_teams, parse_server_range,
                         tournament)
from .guild import simulate_guild
from .fighter import Fighter
from .turma import TurmaRules, normalize_team, simulate_turma

ROLE_LABELS = {"tank": "tank (védő)", "dps": "támadó", "healer": "gyógyító", "out": "tétlen"}
ROLE_FROM_LABEL = {v: k for k, v in ROLE_LABELS.items()}


def cache_dir() -> str:
    """Pages are cached on disk for 10 minutes (HP changes in battles, so not longer)."""
    import os
    import tempfile
    return os.path.join(tempfile.gettempdir(), "gladiatus_sim_cache")


def split_player(name: str, server: str) -> Tuple[str, str, str]:
    """('Name', 's51-en') -> (name, country, server)."""
    return parse_player_spec(f"{name.strip()}@{server.strip()}")


def _fmt(x: float) -> str:
    return f"{x:,.0f}".replace(",", " ")


def _life(f: Fighter) -> str:
    cur = f.current_life if f.current_life is not None else f.life
    return _fmt(f.life) if round(cur) == round(f.life) else f"{_fmt(cur)} / {_fmt(f.life)}"


def stat_rows(a: Fighter, d: Fighter) -> List[Tuple[str, str, str]]:
    """Rows (label, attacker value, defender value) of the head-to-head table.
    Chances are the ones of each fighter *against the other one*."""
    def dmg(f):
        return f"{_fmt(f.damage[0])} - {_fmt(f.damage[1])}"

    def absorb(f):
        lo, hi = f.armor_absorb()
        return f"{lo} - {hi}"

    rows = [
        ("Név", a.name, d.name),
        ("Szint", str(a.level), str(d.level)),
        ("Életerő (aktuális / max)", _life(a), _life(d)),
        ("Ügyesség", _fmt(a.skill), _fmt(d.skill)),
        ("Fürgeség", _fmt(a.agility), _fmt(d.agility)),
        ("Karizma", _fmt(a.charisma), _fmt(d.charisma)),
        ("Intelligencia", _fmt(a.intelligence), _fmt(d.intelligence)),
        ("Páncél", _fmt(a.armor), _fmt(d.armor)),
        ("Elnyelés / ütés", absorb(a), absorb(d)),
        ("Sebzés", dmg(a), dmg(d)),
        ("Találati esély", f"{a.hit_chance_vs(d)} %", f"{d.hit_chance_vs(a)} %"),
        ("Dupla találat", f"{a.double_hit_chance_vs(d)} %", f"{d.double_hit_chance_vs(a)} %"),
        ("Kritikus esély", f"{a.crit_chance(50):.0f} %", f"{d.crit_chance(50):.0f} %"),
        ("Kritikus elkerülés", f"{a.avoid_chance(25):.0f} %", f"{d.avoid_chance(25):.0f} %"),
        ("Blokk", f"{a.block_chance_vs(d):.0f} %", f"{d.block_chance_vs(a):.0f} %"),
    ]
    if a.healing or d.healing:
        rows.append(("Gyógyítás", _fmt(a.healing), _fmt(d.healing)))
        rows.append(("Dupla gyógyítás", f"{a.critical_healing_chance:.0f} %", f"{d.critical_healing_chance:.0f} %"))
    if a.threat or d.threat:
        rows.append(("Veszély", _fmt(a.threat), _fmt(d.threat)))
    return rows


@dataclass
class GuildSide:
    name: str
    gid: str
    fighters: List[Fighter]
    failed: List[str] = field(default_factory=list)      # "name: reason" of unreadable members
    listed: int = 0                                      # members found on the member list
    expected: int = 0                                    # member count shown on the guild page
    full_name: str = ""
    suspicious: List[str] = field(default_factory=list)  # loaded, but with implausible values


def fetch_guild_side(name: str, server: str, client: Optional[Client] = None, progress=None,
                     workers: int = 8) -> GuildSide:
    """Download a guild's member list and every member's arena character."""
    client = client or Client()
    n, country, srv = split_player(name, server)       # same 'name@server' splitting
    gid, gname = search_guild(client, country, srv, n)
    members = fetch_guild_members(client, country, srv, gid)
    full_name, expected = fetch_guild_info(client, country, srv, gid)
    client.delay = min(client.delay, 0.12)          # adaptive: it slows down by itself on 503
    done = [0]
    reasons = {}

    def load(m):
        last = None
        for attempt in range(3):
            try:
                f = fetch_arena_fighter_by_id(client, m.pid, country, srv, name=m.name)
                if not f.level and m.level:
                    f.level = m.level
                f.pid = m.pid
                return f
            except Exception as e:                  # noqa: BLE001 - reported per member
                last = e
                time.sleep(0.4 * (attempt + 1))
        reasons[m.pid] = f"{type(last).__name__}: {last}"[:120]
        return None

    def load_progress(m):
        f = load(m)
        done[0] += 1
        if progress:
            progress(f"{gname}: tagok letöltése {done[0]}/{len(members)}")
        return f

    with ThreadPoolExecutor(max_workers=workers) as ex:
        loaded = list(ex.map(load_progress, members))      # keeps the member order
    fighters = [f for f in loaded if f is not None]
    failed = [f"{m.name}: {reasons.get(m.pid, '?')}" for m, f in zip(members, loaded) if f is None]
    suspicious = [f"{f.name} (L{f.level}, élet {f.life:.0f}, sebzés {f.damage[0]:.0f}-{f.damage[1]:.0f})"
                  for f in fighters
                  if f.life <= 0 or f.damage[1] <= 0 or f.skill <= 0 or f.level <= 0
                  or f.damage[1] < 1.03 * f.damage[0]]
    if not fighters:
        raise FetchError(f"{gname}: egyik tag adatlapját sem sikerült beolvasni "
                         f"({failed[0] if failed else 'nincs tag'})")
    side = GuildSide(gname, gid, fighters, failed, len(members), expected, full_name or "", suspicious)
    return side



def fetch_players(mode: str, att: Tuple[str, str], dfd: Tuple[str, str],
                  client: Optional[Client] = None, progress=None, debug_dir: Optional[str] = None):
    """Download both players. `att`/`dfd` are (name, server). Returns (a, d):
    single Fighters in arena mode, lists (idle mercs included) in turma mode."""
    client = client or Client(debug_dir=debug_dir, cache_dir=cache_dir())
    if mode == "guild":
        # both guilds at once; they share the client's global request spacing
        with ThreadPoolExecutor(max_workers=2) as ex:
            fa = ex.submit(fetch_guild_side, att[0], att[1], client, progress)
            fd = ex.submit(fetch_guild_side, dfd[0], dfd[1], client, progress)
            return fa.result(), fd.result()
    out = []
    for name, server in (att, dfd):
        n, country, srv = split_player(name, server)
        if mode == "arena":
            out.append(fetch_arena_fighter(client, n, country, srv))
        else:
            out.append(fetch_turma_team(client, n, country, srv, keep_idle=True))
    return out[0], out[1]


def run_simulation(mode: str, a, d, runs: int, rules: Optional[TurmaRules] = None,
                   seed: Optional[int] = None, life_mode: str = "current") -> str:
    """Run the simulation and return the human readable result text."""
    if mode == "guild":
        return _guild_text(a, d, runs, seed, life_mode)
    if mode == "arena":
        r = simulate_arena(a, d, runs=runs, seed=seed)
        return (f"Aréna csata, {r.runs} szimuláció\n"
                f"  {a.name} nyer: {r.win_chance:.1f} %\n"
                f"  döntetlen:     {r.draw_chance:.1f} %\n"
                f"  {d.name} nyer: {r.lose_chance:.1f} %\n"
                f"  átlagos pontszám: {r.avg_score_attacker:.0f} - {r.avg_score_defender:.0f}\n"
                f"  átlagos körszám: {r.avg_rounds:.1f}")
    ta, td = normalize_team(a), normalize_team(d)
    if not ta or not td:
        return "Mindkét csapatban legalább egy aktív harcosnak lennie kell."
    r = simulate_turma(ta, td, runs=runs, seed=seed, rules=rules)
    lines = [f"Circus Turma csata, {r.runs} szimuláció",
             f"  támadó nyer: {r.win_chance:.1f} %   döntetlen: {r.draw_chance:.1f} %   védő nyer: {r.lose_chance:.1f} %",
             f"  átlagos pontszám: {r.avg_points[0]:,.0f} - {r.avg_points[1]:,.0f}".replace(",", " "),
             f"  halálok csatánként: támadó {r.avg_deaths[0]:.2f}, védő {r.avg_deaths[1]:.2f}",
             "", "  Harcosonként (átlag):"]
    for label, team, stats in (("Támadó", ta, r.avg_stats[0]), ("Védő", td, r.avg_stats[1])):
        for f, s in zip(team, stats):
            lines.append(f"   {label:7s} {f.name[:22]:22s} {ROLE_LABELS[f.role]:12s} "
                         f"sebzés {s.damage_done:>9,.0f}  gyógyítás {s.heal_done:>8,.0f}".replace(",", " "))
    return "\n".join(lines)


def _guild_text(a: "GuildSide", d: "GuildSide", runs: int, seed: Optional[int], life_mode: str = "current") -> str:
    r = simulate_guild(a.fighters, d.fighters, runs=runs, seed=seed, life_mode=life_mode)
    f = r.first
    verdict = {"attacker": f"{a.name} nyer", "defender": f"{d.name} nyer", "draw": "döntetlen"}[f.winner]
    lines = [f"Egyesületi csata: {a.name} (támadó, {len(a.fighters)} tag) vs {d.name} (védő, {len(d.fighters)} tag)",
             f"Összeredmény: {a.name} {f.points_attacker} - {f.points_defender} {d.name}  =>  {verdict}", ""]
    if r.runs > 1:
        lines[2:2] = [f"  {r.runs} szimuláció: {a.name} nyer {r.win_chance:.1f} %, döntetlen {r.draw_chance:.1f} %, "
                      f"{d.name} nyer {r.lose_chance:.1f} %, átlagpont {r.avg_points[0]:.1f} - {r.avg_points[1]:.1f}",
                      "  (az alábbi párosítás az első szimulált csata)"]
    lines.append("Párharcok:")
    for p in f.pairs:
        if p.walkover:
            who = p.attacker or p.defender
            side = a.name if p.attacker else d.name
            lines.append(f"  {who} ({side}) ellenfél nélkül maradt: automatikus győzelem, +{p.points} pont")
        else:
            win = p.attacker if p.winner == "attacker" else p.defender
            note = " (döntetlen, a védő nyer)" if p.drawn else ""
            lines.append(f"  {p.attacker} vs {p.defender}: nyertes {win}{note}, +{p.points} pont "
                         f"(pontszám {p.score_attacker:.0f} - {p.score_defender:.0f}, {p.rounds} kör)")
    lines += ["", "Adatbeolvasás:"]
    for g in (a, d):
        exp = f" / oldal szerint {g.expected}" if g.expected else ""
        full = f" [{g.full_name}]" if g.full_name else ""
        lines.append(f"  {g.name}{full}: életerő: {'teljes' if life_mode == 'full' else 'aktuális'}; lista {g.listed} tag{exp}, beolvasva {len(g.fighters)}, hibás {len(g.failed)}")
        for x in g.failed[:15]:
            lines.append(f"    ! nem olvasható: {x}")
        for x in g.suspicious[:15]:
            lines.append(f"    ? gyanús adat: {x}")
    return "\n".join(lines)


def guild_summary(a: "GuildSide", d: "GuildSide") -> str:
    """One status line about how complete the download was."""
    parts = []
    for g in (a, d):
        t = f"{g.name}: {len(g.fighters)}/{g.listed} tag"
        if g.expected and g.listed < g.expected:
            t += f" (az oldal szerint {g.expected} tag, a lista csak {g.listed}-et tartalmaz!)"
        if g.failed:
            t += f", {len(g.failed)} nem olvasható"
        parts.append(t)
    return "Statok letöltve. " + " | ".join(parts)


@dataclass
class BestSet:
    fighters: List[Fighter]
    server_errors: dict = field(default_factory=dict)
    failed: List[str] = field(default_factory=list)
    level_min: int = 0
    level_max: int = 0
    servers: int = 0
    mode: str = "arena"


def fetch_best_set(level_min: int, level_max: int, servers_text: str = "",
                   country: str = "en", client: Optional[Client] = None, progress=None,
                   mode: str = "arena") -> BestSet:
    """All players of the level interval from the highscore of every server. With an empty
    ``servers_text`` the servers of the country are discovered dynamically."""
    client = client or Client(cache_dir=cache_dir())
    client.delay = min(client.delay, 0.12)
    servers = parse_server_range(servers_text) if servers_text.strip() else \
        discover_servers(client, country, progress=progress)
    if not servers:
        raise FetchError("nem találtam szervert (add meg kézzel, pl. 1-60)")
    cands, errors = collect_candidates(client, servers, country, level_min, level_max, progress=progress)
    if len(cands) < 2:
        raise FetchError(f"a {level_min}-{level_max} szinttartományban kevesebb mint 2 játékost találtam "
                         f"({len(servers)} szerver, {len(errors)} hibás)")
    if mode == "turma":
        fighters, failed = load_teams(client, cands, progress)
    else:
        fighters, failed = load_fighters(client, cands, progress)
    if len(fighters) < 2:
        raise FetchError("kevesebb mint 2 játékos adatlapját sikerült beolvasni")
    return BestSet(fighters, errors, failed, level_min, level_max, len(servers), mode)


def best_text(b: BestSet, samples: int = 2, seed: Optional[int] = None, progress=None) -> str:
    top = tournament(b.fighters, samples=samples, seed=seed, progress=progress, mode=b.mode)
    turma = b.mode == "turma"
    lines = [f"Legjobb játékosok: {b.level_min}-{b.level_max} szint, {b.servers} szerver, {len(b.fighters)} játékos "
             f"({'turma szabályok szerint, a profilban beállított zsoldosokkal' if turma else 'teljes életerővel, aréna szabályok szerint'})", "",
             "  #  játékos                       szint  döntő győzelem%  selejtező győzelem%"]
    for i, r in enumerate(top, 1):
        lines.append(f"  {i}  {r.fighter.name[:28]:28s} {r.fighter.level:5d}  {r.final:14.1f}  {r.stage1:18.1f}")
    lines += ["", "Módszer: minden játékos mindenkivel megmérkőzik (selejtező; ha túl sok a játékos, véletlen",
              "ellenfelekkel), a legjobb 16 körmérkőzést játszik (döntő). A győzelem% a mezőnytől függ."]
    if b.server_errors:
        lines.append(f"Nem elérhető szerverek ({len(b.server_errors)}): " +
                     ", ".join(f"s{k}" for k in sorted(b.server_errors, key=int)[:20]))
    if b.failed:
        lines.append(f"Nem olvasható adatlap: {len(b.failed)} játékos")
    return "\n".join(lines)
