"""Circus Turma (5v5) battle simulator.

Confirmed against a real battle report (see README):
  * 50 rounds; every living fighter acts once per round in random order, a
    successful double hit adds an extra swing; dead fighters stay idle.
  * Team points = damage dealt + healing done / 2 (healing counted only as far
    as it really restored life). A team that is wiped out loses, otherwise the
    higher point total wins.
  * Per-pair hit / double hit / block chances and armor absorption use the
    same formulas as the arena (the old PHP turma code used a wrong double
    hit formula).
  * Healers heal the most wounded living teammate, or attack if nobody is hurt.

NOT yet settled (configurable via :class:`TurmaRules`): how a target is chosen.
The default is a threat-weighted draw where the player's own character gets an
extra multiplier -- it reproduces the target distribution of the one analysed
report (main character takes ~80% of the hits) but is a fitted hypothesis.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from .arena import Hit
from .fighter import Fighter


@dataclass
class TurmaRules:
    rounds: int = 50
    heal_score_factor: float = 0.5
    # --- target selection ---
    targeting: str = "weighted"        # "weighted" | "uniform"
    main_multiplier: float = 6.5       # threat multiplier of the player's character (50 jelentésre illesztve: 6-7)
    tank_multiplier: float = 1.0       # extra multiplier of tank mercenaries
    tank_damage_multiplier: float = 1.07  # tank merc bonus on raw weapon damage (fit; ~+20-35% after armor)
    healers_targetable: bool = True
    # --- hit resolution ---
    # "independent": a blokk a kritikus dobástól függetlenül dönt (a 50 jelentés
    # alapján: a találatok ~50%-a blokkolt, kritikussal is, és a blokkolt
    # kritikus sebzése dmg-absorb). "crit_first" | "block_first": régi PHP-s sorrendek.
    crit_block_order: str = "independent"
    avoid_critical_cap: float = 25
    crit_cap: float = 50


@dataclass
class FighterStats:
    name: str
    damage_done: float = 0.0
    damage_taken: float = 0.0
    heal_done: float = 0.0
    heal_taken: float = 0.0
    swings: int = 0                 # attack swings made
    damaging_hits: int = 0
    swings_received: int = 0
    swings_failed_received: int = 0  # missed or blocked
    crits: int = 0
    avoided_crits: int = 0
    died_round: Optional[int] = None


@dataclass
class TurmaBattle:
    stats: List[List[FighterStats]]    # [side][fighter]
    points: List[float]
    winner: int                        # 0 attackers, 1 defenders, -1 draw
    rounds: int


class _Engine:
    def __init__(self, teams: Sequence[Sequence[Fighter]], rules: TurmaRules,
                 pair_overrides: Optional[dict] = None):
        self.t = [list(teams[0]), list(teams[1])]
        self.r = rules
        self.pair = {}      # (side, i, j) -> dict of chances of fighter i vs enemy j
        for s in (0, 1):
            for i, f in enumerate(self.t[s]):
                for j, e in enumerate(self.t[1 - s]):
                    self.pair[(s, i, j)] = dict(
                        hit=f.hit_chance_vs(e),
                        double=f.double_hit_chance_vs(e),
                        crit=f.crit_chance(rules.crit_cap),
                        # block / avoid are those of the *defender*
                        block=e.block_chance_vs(f),
                        avoid=e.avoid_chance(rules.avoid_critical_cap),
                        absorb=e.armor_absorb(),
                    )
        # (side, i, j) -> {hit|double|block|crit|avoid|absorb: value}: e.g. the exact
        # values read from a battle report's character sheet
        for key, vals in (pair_overrides or {}).items():
            self.pair[key].update(vals)
        self.weights = [[self._weight(f) for f in team] for team in self.t]

    def _weight(self, f: Fighter) -> float:
        if self.r.targeting == "uniform":
            return 1.0
        if f.role == "healer" and not self.r.healers_targetable:
            return 0.0
        w = max(f.threat, 0.0)
        if f.is_main:
            w *= self.r.main_multiplier
        elif f.role == "tank":
            w *= self.r.tank_multiplier
        return w

    # one swing
    def swing(self, rng, s, i, j):
        f = self.t[s][i]
        c = self.pair[(s, i, j)]
        if rng.random() * 100 >= c["hit"]:
            return Hit.MISSED, 0.0
        base = rng.randint(int(f.damage[0]), int(f.damage[1]))
        if f.role == "tank" and not f.is_main:
            base *= self.r.tank_damage_multiplier
        absorb = rng.randint(*c["absorb"])
        if self.r.crit_block_order == "independent":
            crit = rng.random() * 100 < c["crit"] and not rng.random() * 100 < c["avoid"]
            blocked = rng.random() * 100 < c["block"]
            dmg = max(0.0, (2 * base if crit else base) / (2 if blocked else 1) - absorb)
            if blocked:
                return (Hit.AVOIDED_CRITICAL if crit else Hit.BLOCKED), dmg
            return (Hit.CRITICAL if crit else Hit.NORMAL), dmg
        if self.r.crit_block_order == "block_first" and rng.random() * 100 < c["block"]:
            return Hit.BLOCKED, 0.0
        if rng.random() * 100 < c["crit"]:
            if rng.random() * 100 < c["avoid"]:
                return Hit.AVOIDED_CRITICAL, max(0.0, base - absorb)
            return Hit.CRITICAL, max(0.0, 2 * base - absorb)
        if self.r.crit_block_order == "crit_first" and rng.random() * 100 < c["block"]:
            return Hit.BLOCKED, max(0.0, base / 2 - absorb)
        return Hit.NORMAL, max(0.0, base - absorb)

    def pick_target(self, rng, s):
        opp = self.t[1 - s]
        alive = [j for j, e in enumerate(opp) if self.life[1 - s][j] > 0]
        w = [self.weights[1 - s][j] for j in alive]
        total = sum(w)
        if total <= 0:
            return rng.choice(alive)
        x = rng.random() * total
        for j, wj in zip(alive, w):
            x -= wj
            if x < 0:
                return j
        return alive[-1]

    def run(self, rng: random.Random) -> TurmaBattle:
        self.life = [[f.current_life for f in team] for team in self.t]
        st = [[FighterStats(f.name) for f in team] for team in self.t]
        rounds_done = 0
        for rnd in range(1, self.r.rounds + 1):
            if not all(any(l > 0 for l in lv) for lv in self.life):
                break
            order = [(s, i) for s in (0, 1) for i in range(len(self.t[s]))
                     if self.life[s][i] > 0]
            rng.shuffle(order)
            for s, i in order:
                if self.life[s][i] <= 0:
                    continue
                if not any(l > 0 for l in self.life[1 - s]):
                    break
                f = self.t[s][i]
                if f.role == "healer" and self._heal(rng, s, i, st):
                    continue
                for n in range(2):
                    j = self.pick_target(rng, s) if n == 0 else j
                    if n == 1:
                        if rng.random() * 100 >= self.pair[(s, i, j)]["double"]:
                            break
                        if self.life[1 - s][j] <= 0:
                            break
                    kind, dmg = self.swing(rng, s, i, j)
                    dmg = min(dmg, self.life[1 - s][j])
                    self.life[1 - s][j] -= dmg
                    a, d = st[s][i], st[1 - s][j]
                    a.swings += 1
                    a.damage_done += dmg
                    d.swings_received += 1
                    d.damage_taken += dmg
                    if kind in (Hit.MISSED, Hit.BLOCKED) and dmg == 0:
                        d.swings_failed_received += 1
                    if dmg > 0:
                        a.damaging_hits += 1
                    if kind is Hit.CRITICAL:
                        a.crits += 1
                    elif kind is Hit.AVOIDED_CRITICAL:
                        a.avoided_crits += 1
                    if self.life[1 - s][j] <= 0:
                        d.died_round = rnd
                        break
            rounds_done = rnd
        points = []
        for s in (0, 1):
            dmg = sum(x.damage_done for x in st[s])
            heal = sum(x.heal_done for x in st[s])
            points.append(dmg + heal * self.r.heal_score_factor)
        alive = [any(l > 0 for l in lv) for lv in self.life]
        if alive[0] and not alive[1]:
            winner = 0
        elif alive[1] and not alive[0]:
            winner = 1
        elif points[0] > points[1]:
            winner = 0
        elif points[1] > points[0]:
            winner = 1
        else:
            winner = -1
        return TurmaBattle(st, points, winner, rounds_done)

    def _heal(self, rng, s, i, st) -> bool:
        team = self.t[s]
        missing = [(team[j].life - self.life[s][j], j) for j in range(len(team))
                   if self.life[s][j] > 0 and team[j].life - self.life[s][j] > 0]
        if not missing:
            return False
        gap, j = max(missing)
        f = team[i]
        amount = f.healing * (2 if rng.random() * 100 < f.critical_healing_chance else 1)
        amount = min(amount, gap)
        self.life[s][j] += amount
        st[s][i].heal_done += amount
        st[s][j].heal_taken += amount
        return True


def turma_battle(attackers: Sequence[Fighter], defenders: Sequence[Fighter],
                 rng: random.Random, rules: Optional[TurmaRules] = None,
                 pair_overrides: Optional[dict] = None) -> TurmaBattle:
    return _Engine((attackers, defenders), rules or TurmaRules(), pair_overrides).run(rng)


@dataclass
class TurmaResult:
    runs: int
    win_chance: float
    draw_chance: float
    lose_chance: float
    avg_points: List[float]
    avg_stats: List[List[FighterStats]]
    avg_deaths: List[float]
    main_hit_share: List[float]   # share of swings of side s aimed at the enemy main char

    def __str__(self) -> str:
        return (f"{self.runs} battles: win {self.win_chance:.2f}%  "
                f"draw {self.draw_chance:.2f}%  lose {self.lose_chance:.2f}%  "
                f"(avg points {self.avg_points[0]:.0f} vs {self.avg_points[1]:.0f})")


def simulate_turma(attackers: Sequence[Fighter], defenders: Sequence[Fighter],
                   runs: int = 1000, seed: Optional[int] = None,
                   rules: Optional[TurmaRules] = None,
                   pair_overrides: Optional[dict] = None) -> TurmaResult:
    rng = random.Random(seed)
    rules = rules or TurmaRules()
    eng = _Engine((attackers, defenders), rules, pair_overrides)
    wins = draws = 0
    pts = [0.0, 0.0]
    deaths = [0.0, 0.0]
    sums = [[FighterStats(f.name) for f in team] for team in (attackers, defenders)]
    main_idx = [next((j for j, f in enumerate(team) if f.is_main), 0)
                for team in (attackers, defenders)]
    main_sw = [0, 0]
    all_sw = [0, 0]
    numeric = [n for n, v in FighterStats("x").__dict__.items()
               if isinstance(v, (int, float)) and n != "died_round"]
    for _ in range(runs):
        b = eng.run(rng)
        wins += b.winner == 0
        draws += b.winner == -1
        for s in (0, 1):
            pts[s] += b.points[s]
            for k, x in enumerate(b.stats[s]):
                deaths[s] += x.died_round is not None
                for n in numeric:
                    setattr(sums[s][k], n, getattr(sums[s][k], n) + getattr(x, n))
            # swings aimed at the enemy main character: swings received there
            main_sw[s] += b.stats[1 - s][main_idx[1 - s]].swings_received
            all_sw[s] += sum(x.swings_received for x in b.stats[1 - s])
    for team in sums:
        for x in team:
            for n in numeric:
                setattr(x, n, getattr(x, n) / runs)
    return TurmaResult(
        runs, 100 * wins / runs, 100 * draws / runs,
        100 * (runs - wins - draws) / runs,
        [p / runs for p in pts], sums, [d / runs for d in deaths],
        [m / a if a else 0.0 for m, a in zip(main_sw, all_sw)],
    )
