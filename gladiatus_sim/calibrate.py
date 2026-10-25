"""Valós turma jelentések (report_parser) és a szimulátor összevetése.

`report_to_teams` a jelentés karakterlapjából épít Fightert + pontos páronkénti
esélyeket (találat / dupla találat / elhárítás), így a szimuláció a játék saját
számait használja, nem a mi becslésünket.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

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


def report_to_teams(rep: Report, roles: Optional[dict] = None) -> Tuple[List[Fighter], List[Fighter], dict]:
    """(attackers, defenders, pair_overrides). `roles`: {fid: 'tank'|'dps'|'healer'}."""
    roles = roles or {}
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
