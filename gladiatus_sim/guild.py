"""Guild battle (egyesületi csata) simulator.

Rules (as described by the game's players): the members of the two guilds are paired
randomly and every pair fights an arena battle. If one guild has more members, the
unpaired members win without a fight. A won fight is worth 2 points for the member's
guild, a walkover only 1 point. A drawn fight is won by the member of the defending
guild (2 points). The guild with more points wins.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from .arena import arena_battle
from .fighter import Fighter

WIN_POINTS = 2
WALKOVER_POINTS = 1


@dataclass
class PairResult:
    attacker: Optional[str]          # None: the defender had no opponent
    defender: Optional[str]
    winner: str                      # "attacker" | "defender"
    walkover: bool
    points: int
    detail: str = ""                 # "attacker won by score ..." etc.
    score_attacker: float = 0.0
    score_defender: float = 0.0
    rounds: int = 0
    drawn: bool = False


@dataclass
class GuildBattleResult:
    pairs: List[PairResult]
    points_attacker: int
    points_defender: int

    @property
    def winner(self) -> str:
        if self.points_attacker > self.points_defender:
            return "attacker"
        if self.points_defender > self.points_attacker:
            return "defender"
        return "draw"


def guild_battle(attackers: Sequence[Fighter], defenders: Sequence[Fighter],
                 rng: random.Random, life_mode: str = "full") -> GuildBattleResult:
    a = list(attackers)
    d = list(defenders)
    rng.shuffle(a)
    rng.shuffle(d)
    pairs: List[PairResult] = []
    pa = pd = 0
    for x, y in zip(a, d):
        b = arena_battle(x, y, rng, life_mode)
        if b.result == 1:
            winner, pts, drawn = "attacker", WIN_POINTS, False
        elif b.result == -1:
            winner, pts, drawn = "defender", WIN_POINTS, False
        else:
            winner, pts, drawn = "defender", WIN_POINTS, True     # draw: the defender wins
        if winner == "attacker":
            pa += pts
        else:
            pd += pts
        pairs.append(PairResult(x.name, y.name, winner, False, pts,
                                "draw (defender wins)" if drawn else "",
                                b.score_attacker, b.score_defender, b.rounds, drawn))
    for x in a[len(d):]:                       # attacker guild has more members
        pa += WALKOVER_POINTS
        pairs.append(PairResult(x.name, None, "attacker", True, WALKOVER_POINTS))
    for y in d[len(a):]:
        pd += WALKOVER_POINTS
        pairs.append(PairResult(None, y.name, "defender", True, WALKOVER_POINTS))
    return GuildBattleResult(pairs, pa, pd)


@dataclass
class GuildSimulation:
    runs: int
    win_chance: float                 # attacker guild wins (%)
    draw_chance: float
    lose_chance: float
    avg_points: List[float]
    first: GuildBattleResult          # the first simulated battle (the detailed one)


def simulate_guild(attackers: Sequence[Fighter], defenders: Sequence[Fighter],
                   runs: int = 1, seed: Optional[int] = None,
                   life_mode: str = "full") -> GuildSimulation:
    rng = random.Random(seed)
    w = dr = 0
    pts = [0.0, 0.0]
    first = None
    for _ in range(max(1, runs)):
        r = guild_battle(attackers, defenders, rng, life_mode)
        first = first or r
        w += r.winner == "attacker"
        dr += r.winner == "draw"
        pts[0] += r.points_attacker
        pts[1] += r.points_defender
    n = max(1, runs)
    return GuildSimulation(n, 100 * w / n, 100 * dr / n, 100 * (n - w - dr) / n,
                           [pts[0] / n, pts[1] / n], first)
