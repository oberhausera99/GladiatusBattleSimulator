"""Tk-független logika a grafikus felülethez (tesztelhető)."""
from __future__ import annotations

from typing import List, Optional, Tuple

from .arena import simulate_arena
from .fetch import Client, fetch_arena_fighter, fetch_turma_team, parse_player_spec
from .fighter import Fighter
from .turma import TurmaRules, normalize_team, simulate_turma

ROLE_LABELS = {"tank": "tank (védő)", "dps": "támadó", "healer": "gyógyító", "out": "tétlen"}
ROLE_FROM_LABEL = {v: k for k, v in ROLE_LABELS.items()}


def split_player(name: str, server: str) -> Tuple[str, str, str]:
    """('Name', 's51-en') -> (name, country, server)."""
    return parse_player_spec(f"{name.strip()}@{server.strip()}")


def _fmt(x: float) -> str:
    return f"{x:,.0f}".replace(",", " ")


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
        ("Életerő", _fmt(a.life), _fmt(d.life)),
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


def fetch_players(mode: str, att: Tuple[str, str], dfd: Tuple[str, str], client: Optional[Client] = None):
    """Download both players. `att`/`dfd` are (name, server). Returns (a, d):
    single Fighters in arena mode, lists (idle mercs included) in turma mode."""
    client = client or Client()
    out = []
    for name, server in (att, dfd):
        n, country, srv = split_player(name, server)
        if mode == "arena":
            out.append(fetch_arena_fighter(client, n, country, srv))
        else:
            out.append(fetch_turma_team(client, n, country, srv, keep_idle=True))
    return out[0], out[1]


def run_simulation(mode: str, a, d, runs: int, rules: Optional[TurmaRules] = None,
                   seed: Optional[int] = None) -> str:
    """Run the simulation and return the human readable result text."""
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
