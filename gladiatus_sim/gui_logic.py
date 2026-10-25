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
from .report_html import guild_report_html
from .i18n import t
from .fighter import Fighter
from .turma import TurmaRules, normalize_team, simulate_turma

ROLES = ("tank", "dps", "healer", "out")


class _RoleLabels:
    """Role -> label in the current language."""
    def __getitem__(self, role: str) -> str:
        return t("role_" + role)


class _RoleFromLabel:
    """Label (current language) -> role."""
    def __getitem__(self, label: str) -> str:
        for r in ROLES:
            if t("role_" + r) == label:
                return r
        raise KeyError(label)


ROLE_LABELS = _RoleLabels()
ROLE_FROM_LABEL = _RoleFromLabel()


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
        (t("s_name"), a.name, d.name),
        (t("s_level"), str(a.level), str(d.level)),
        (t("s_life"), _life(a), _life(d)),
        (t("s_skill"), _fmt(a.skill), _fmt(d.skill)),
        (t("s_agility"), _fmt(a.agility), _fmt(d.agility)),
        (t("s_charisma"), _fmt(a.charisma), _fmt(d.charisma)),
        (t("s_intelligence"), _fmt(a.intelligence), _fmt(d.intelligence)),
        (t("s_armor"), _fmt(a.armor), _fmt(d.armor)),
        (t("s_absorb"), absorb(a), absorb(d)),
        (t("s_damage"), dmg(a), dmg(d)),
        (t("s_hit"), f"{a.hit_chance_vs(d)} %", f"{d.hit_chance_vs(a)} %"),
        (t("s_double"), f"{a.double_hit_chance_vs(d)} %", f"{d.double_hit_chance_vs(a)} %"),
        (t("s_crit"), f"{a.crit_chance(50):.0f} %", f"{d.crit_chance(50):.0f} %"),
        (t("s_avoid"), f"{a.avoid_chance(25):.0f} %", f"{d.avoid_chance(25):.0f} %"),
        (t("s_block"), f"{a.block_chance_vs(d):.0f} %", f"{d.block_chance_vs(a):.0f} %"),
    ]
    if a.healing or d.healing:
        rows.append((t("s_heal"), _fmt(a.healing), _fmt(d.healing)))
        rows.append((t("s_dheal"), f"{a.critical_healing_chance:.0f} %", f"{d.critical_healing_chance:.0f} %"))
    if a.threat or d.threat:
        rows.append((t("s_threat"), _fmt(a.threat), _fmt(d.threat)))
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
            progress(t("p_members", g=gname, i=done[0], n=len(members)))
        return f

    with ThreadPoolExecutor(max_workers=workers) as ex:
        loaded = list(ex.map(load_progress, members))      # keeps the member order
    fighters = [f for f in loaded if f is not None]
    failed = [f"{m.name}: {reasons.get(m.pid, '?')}" for m, f in zip(members, loaded) if f is None]
    suspicious = [t("suspicious", name=f.name, level=f.level, life=f.life, d0=f.damage[0], d1=f.damage[1])
                  for f in fighters
                  if f.life <= 0 or f.damage[1] <= 0 or f.skill <= 0 or f.level <= 0
                  or f.damage[1] < 1.03 * f.damage[0]]
    if not fighters:
        raise FetchError(t("e_no_member_read", g=gname,
                           why=failed[0] if failed else t("e_no_members")))
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
        return run_guild(a, d, runs, seed, life_mode)[0]
    if mode == "arena":
        r = simulate_arena(a, d, runs=runs, seed=seed)
        return "\n".join([t("arena_head", runs=r.runs),
                          "  " + t("arena_win", n=a.name, p=r.win_chance),
                          "  " + t("arena_draw", p=r.draw_chance),
                          "  " + t("arena_win", n=d.name, p=r.lose_chance),
                          "  " + t("arena_pts", a=r.avg_score_attacker, d=r.avg_score_defender),
                          "  " + t("arena_rounds", r=r.avg_rounds)])
    ta, td = normalize_team(a), normalize_team(d)
    if not ta or not td:
        return t("turma_empty")
    r = simulate_turma(ta, td, runs=runs, seed=seed, rules=rules)
    lines = [t("turma_head", runs=r.runs),
             "  " + t("turma_chances", w=r.win_chance, d=r.draw_chance, l=r.lose_chance),
             "  " + t("turma_pts", a=_fmt(r.avg_points[0]), d=_fmt(r.avg_points[1])),
             "  " + t("turma_deaths", a=r.avg_deaths[0], d=r.avg_deaths[1]),
             "", "  " + t("turma_per")]
    for label, team, stats in ((t("attacker"), ta, r.avg_stats[0]), (t("defender"), td, r.avg_stats[1])):
        for f, s in zip(team, stats):
            lines.append(f"   {label:9s} {f.name[:22]:22s} {ROLE_LABELS[f.role]:14s} "
                         + t("turma_row", dmg=f"{_fmt(s.damage_done):>9s}", heal=f"{_fmt(s.heal_done):>8s}"))
    return "\n".join(lines)


def run_guild(a: "GuildSide", d: "GuildSide", runs: int, seed: Optional[int] = None,
              life_mode: str = "current") -> Tuple[str, str]:
    """(result text, HTML report) of the same simulated guild battle."""
    r = simulate_guild(a.fighters, d.fighters, runs=runs, seed=seed, life_mode=life_mode)
    extra = ""
    if r.runs > 1:
        extra = t("g_runs", runs=r.runs, a=a.name, w=r.win_chance, dr=r.draw_chance, d=d.name,
                  l=r.lose_chance, pa=r.avg_points[0], pd=r.avg_points[1]).strip()
    return _guild_text(a, d, r, life_mode), guild_report_html(a.name, d.name, r.first, extra)


def _guild_text(a: "GuildSide", d: "GuildSide", r, life_mode: str = "current") -> str:
    f = r.first
    verdict = {"attacker": t("g_wins", n=a.name), "defender": t("g_wins", n=d.name), "draw": t("g_draw")}[f.winner]
    lines = [t("g_head", a=a.name, na=len(a.fighters), d=d.name, nd=len(d.fighters)),
             t("g_total", a=a.name, pa=f.points_attacker, pd=f.points_defender, d=d.name, v=verdict), ""]
    if r.runs > 1:
        lines[2:2] = [t("g_runs", runs=r.runs, a=a.name, w=r.win_chance, dr=r.draw_chance, d=d.name,
                        l=r.lose_chance, pa=r.avg_points[0], pd=r.avg_points[1]),
                      t("g_first")]
    lines.append(t("g_pairs"))
    for p in f.pairs:
        if p.walkover:
            who = p.attacker or p.defender
            side = a.name if p.attacker else d.name
            lines.append(t("g_walkover", who=who, side=side, pts=p.points))
        else:
            win = p.attacker if p.winner == "attacker" else p.defender
            note = t("g_drawn") if p.drawn else ""
            lines.append(t("g_pair", a=p.attacker, d=p.defender, w=win, note=note, pts=p.points,
                           sa=p.score_attacker, sd=p.score_defender, rounds=p.rounds))
    lines += ["", t("g_data")]
    for g in (a, d):
        exp = t("g_exp", n=g.expected) if g.expected else ""
        full = f" [{g.full_name}]" if g.full_name else ""
        life = t("g_life_full") if life_mode == "full" else t("g_life_cur")
        lines.append(t("g_line", g=g.name, full=full, life=life, listed=g.listed, exp=exp,
                       ok=len(g.fighters), bad=len(g.failed)))
        for x in g.failed[:15]:
            lines.append(t("g_unreadable", x=x))
        for x in g.suspicious[:15]:
            lines.append(t("g_suspicious", x=x))
    return "\n".join(lines)


def guild_summary(a: "GuildSide", d: "GuildSide") -> str:
    """One status line about how complete the download was."""
    parts = []
    for g in (a, d):
        x = t("g_members", g=g.name, ok=len(g.fighters), listed=g.listed)
        if g.expected and g.listed < g.expected:
            x += t("g_short", exp=g.expected, listed=g.listed)
        if g.failed:
            x += t("g_failed", n=len(g.failed))
        parts.append(x)
    return t("g_summary_head") + " | ".join(parts)


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
        raise FetchError(t("e_no_servers"))
    cands, errors = collect_candidates(client, servers, country, level_min, level_max, progress=progress)
    if len(cands) < 2:
        raise FetchError(t("e_few_players", lo=level_min, hi=level_max, srv=len(servers), err=len(errors)))
    if mode == "turma":
        fighters, failed = load_teams(client, cands, progress)
    else:
        fighters, failed = load_fighters(client, cands, progress)
    if len(fighters) < 2:
        raise FetchError(t("e_few_pages"))
    return BestSet(fighters, errors, failed, level_min, level_max, len(servers), mode)


def best_text(b: BestSet, samples: int = 2, seed: Optional[int] = None, progress=None) -> str:
    top = tournament(b.fighters, samples=samples, seed=seed, progress=progress, mode=b.mode)
    turma = b.mode == "turma"
    how = t("b_how_turma") if turma else t("b_how_arena")
    lines = [t("b_head", lo=b.level_min, hi=b.level_max, srv=b.servers, n=len(b.fighters), how=how), "",
             t("b_cols")]
    for i, r in enumerate(top, 1):
        lines.append(f"  {i}  {r.fighter.name[:28]:28s} {r.fighter.level:5d}  {r.final:14.1f}  {r.stage1:18.1f}")
        if r.fighter.profile_url:
            lines.append(f"     {r.fighter.profile_url}")
    lines += ["", t("b_method1"), t("b_method2")]
    if b.server_errors:
        lines.append(t("b_servers_down", n=len(b.server_errors)) +
                     ", ".join(f"s{k}" for k in sorted(b.server_errors, key=int)[:20]))
    if b.failed:
        lines.append(t("b_failed", n=len(b.failed)))
    return "\n".join(lines)
