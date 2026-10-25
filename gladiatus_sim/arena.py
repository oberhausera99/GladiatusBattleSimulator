"""Arena (1v1) battle simulator.

Faithful port of the original, well-validated PHP arena engine: attacker and
defender alternate single hits, each with a chance of a second (double) hit.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .fighter import Fighter


class Hit(Enum):
    NORMAL = "normal"
    CRITICAL = "critical"
    AVOIDED_CRITICAL = "avoided_critical"
    BLOCKED = "blocked"
    MISSED = "missed"


class _Side:
    """Pre-computed arena stats of one fighter against one opponent."""

    def __init__(self, me: Fighter, opp: Fighter) -> None:
        self.hit = me.hit_chance_vs(opp)
        self.double = me.double_hit_chance_vs(opp)
        self.crit = me.crit_chance(cap=50)
        self.avoid = me.avoid_chance(cap=25)
        block = me.base_block() + max(0, me.level - opp.level) * 2
        block = min(50, block)
        armor = me.armor
        if "honour_destroyer" in opp.buffs:
            armor = max(0, armor - opp.level * 15)
        self.absorb = me.armor_absorb(armor)
        self.damage = me.damage
        # god / pact buffs
        if "minerva" in me.buffs or "minerva" in opp.buffs:
            self.double = 0
        if "mars" in me.buffs or "mars" in opp.buffs:
            self.crit = 0
        if "apollo" in me.buffs:
            block += 15          # applied after the 50 cap, as in the original
        if "honour_veteran" in me.buffs:
            self.crit += 10
        self.block = block


def _roll(rng: random.Random, pct: float) -> bool:
    return rng.random() * 100 < pct


def _dmg(rng: random.Random, att: _Side, dfn: _Side, mult: float = 1.0) -> float:
    base = rng.randint(int(att.damage[0]), int(att.damage[1]))
    return mult * base - rng.randint(*dfn.absorb)


def hit_simulation(rng: random.Random, att: _Side, dfn: _Side):
    """Return (Hit, damage) for one swing of *att* against *dfn*."""
    if not _roll(rng, att.hit):
        return Hit.MISSED, 0.0
    if _roll(rng, att.crit):
        if _roll(rng, dfn.avoid):
            kind, dmg = Hit.AVOIDED_CRITICAL, _dmg(rng, att, dfn)
        else:
            kind, dmg = Hit.CRITICAL, _dmg(rng, att, dfn, 2)
    elif _roll(rng, dfn.block):
        kind, dmg = Hit.BLOCKED, _dmg(rng, att, dfn, 0.5)
    else:
        kind, dmg = Hit.NORMAL, _dmg(rng, att, dfn)
    return kind, max(0.0, dmg)


@dataclass
class ArenaBattle:
    result: int            # 1 attacker wins, 0 draw, -1 attacker loses
    score_attacker: float
    score_defender: float
    life_attacker: float
    life_defender: float
    rounds: int


def arena_battle(attacker: Fighter, defender: Fighter, rng: random.Random,
                 life_mode: str = "current", rounds: int = 15) -> ArenaBattle:
    if life_mode == "full":
        la, ld = attacker.life, defender.life
    elif life_mode in ("unlimited", "ignore"):
        la = ld = float("inf")
    else:
        la, ld = attacker.current_life, defender.current_life
    a, d = _Side(attacker, defender), _Side(defender, attacker)
    sa = sd = 0.0
    done = 0
    dead = False
    while done < rounds and la > 0 and ld > 0 and not dead:
        for first in (True, False):
            att, dfn = (a, d) if first else (d, a)
            for swing in range(2):
                if swing == 1 and not _roll(rng, att.double):
                    break
                _, dmg = hit_simulation(rng, att, dfn)
                if first:
                    sa += dmg
                    ld -= dmg
                    left = ld
                else:
                    sd += dmg
                    la -= dmg
                    left = la
                if left <= 0:
                    # damage beyond the remaining life does not count
                    if first:
                        sa += ld
                    else:
                        sd += la
                    dead = True
                    break
            if dead:
                break
        if not dead:
            done += 1
    la, ld = max(la, 0.0), max(ld, 0.0)
    score = sa - sd
    if ld <= 0 or score > 0:
        res = 1
    elif score == 0:
        res = 0
    else:
        res = -1
    return ArenaBattle(res, sa, sd, la, ld, done)


@dataclass
class ArenaResult:
    runs: int
    win_chance: float
    draw_chance: float
    lose_chance: float
    avg_score_attacker: float
    avg_score_defender: float
    avg_rounds: float

    def __str__(self) -> str:
        return (f"{self.runs} battles: win {self.win_chance:.2f}%  "
                f"draw {self.draw_chance:.2f}%  lose {self.lose_chance:.2f}%  "
                f"(avg score {self.avg_score_attacker:.0f} vs "
                f"{self.avg_score_defender:.0f}, {self.avg_rounds:.1f} rounds)")


def simulate_arena(attacker: Fighter, defender: Fighter, runs: int = 10000,
                   seed: Optional[int] = None, life_mode: str = "current",
                   rounds: int = 15) -> ArenaResult:
    rng = random.Random(seed)
    w = dr = lo = 0
    sa = sd = rd = 0.0
    for _ in range(runs):
        b = arena_battle(attacker, defender, rng, life_mode, rounds)
        w += b.result == 1
        dr += b.result == 0
        lo += b.result == -1
        sa += b.score_attacker
        sd += b.score_defender
        rd += b.rounds
    return ArenaResult(runs, 100 * w / runs, 100 * dr / runs, 100 * lo / runs,
                       sa / runs, sd / runs, rd / runs)
