"""Valós turma jelentések (report_parser) és a szimulátor összevetése.

`report_to_teams` a jelentés karakterlapjából épít Fightert + pontos páronkénti
esélyeket (találat / dupla találat / elhárítás), így a szimuláció a játék saját
számait használja, nem a mi becslésünket.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from .arena import simulate_arena
from .fighter import Fighter
from .report_parser import Report, ReportFighter


def _to_fighter(f: ReportFighter, role: str) -> Fighter:
    return Fighter(
        name=f.name, level=f.level, life=f.life, skill=f.skill, agility=f.agility,
        charisma=f.charisma, intelligence=f.intelligence, armor=f.armor,
        damage=(f.dmg_min, f.dmg_max),
        critical_chance=f.crit, block_chance=50.0, avoid_critical_chance=f.avoid_crit,
        healing=f.heal, critical_healing_chance=f.heal_crit, threat=f.threat,
        role=role, is_main=f.is_player,
    )


def guess_role(f: ReportFighter) -> str:
    """A jelentés nem tartalmazza a szerepet: a gyógyítás statisztikából következtetünk."""
    return "healer" if f.heal_dealt > 0 else "dps"


def pick_tank(mercs: List[Fighter], runs: int = 300, seed: int = 1) -> int:
    """Index of the merc with the best arena record against the other mercs
    (round robin, both as attacker and defender). Healers are not passed in."""
    best, best_score = 0, -1.0
    for i, f in enumerate(mercs):
        score = 0.0
        for j, g in enumerate(mercs):
            if i == j:
                continue
            a = simulate_arena(f, g, runs=runs, seed=seed)
            d = simulate_arena(g, f, runs=runs, seed=seed)
            score += a.win_chance + 0.5 * a.draw_chance + d.lose_chance + 0.5 * d.draw_chance
        if score > best_score:
            best, best_score = i, score
    return best


def team_roles(rep: Report, side: str, tank_mercs: int = 1) -> dict:
    """{fid: role}: healer from the heal statistics, the strongest non-healer
    merc (by arena round robin) becomes the tank merc."""
    team = [f for f in rep.fighters if f.side == side]
    roles = {f.fid: guess_role(f) for f in team}
    mercs = [f for f in team if not f.is_player and roles[f.fid] != "healer"]
    if tank_mercs and len(mercs) > 1:
        fighters = [_to_fighter(f, "dps") for f in mercs]
        roles[mercs[pick_tank(fighters)].fid] = "tank"
    return roles


def report_to_teams(rep: Report, roles: Optional[dict] = None, auto_tank: bool = True) -> Tuple[List[Fighter], List[Fighter], dict]:
    """(attackers, defenders, pair_overrides). `roles`: {fid: 'tank'|'dps'|'healer'}."""
    if roles is None:
        roles = {}
        if auto_tank:
            roles.update(team_roles(rep, "A"))
            roles.update(team_roles(rep, "D"))
    A = [f for f in rep.fighters if f.side == "A"]
    D = [f for f in rep.fighters if f.side == "D"]
    att = [_to_fighter(f, roles.get(f.fid, guess_role(f))) for f in A]
    dfd = [_to_fighter(f, roles.get(f.fid, guess_role(f))) for f in D]
    teams = (A, D)
    ov = {}
    for s in (0, 1):
        for i, f in enumerate(teams[s]):
            for j, e in enumerate(teams[1 - s]):
                ov[(s, i, j)] = dict(
                    hit=float(f.hit[e.fid]), double=float(f.double[e.fid]),
                    block=float(e.block[f.fid]),
                )
    return att, dfd, ov
