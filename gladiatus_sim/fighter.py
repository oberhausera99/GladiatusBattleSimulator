"""Fighter model and the per-pair combat chances shared by arena and turma.

All formulas below were checked against real battle data (see README):
hit chance, double hit chance, block chance and armor absorption reproduce the
values shown on the in-game battle report sheet for every fighter pair of a
real Circus Turma report.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, fields
from typing import Optional, Tuple


def php_round(x: float) -> int:
    """Round half away from zero (the game server is PHP)."""
    return int(math.floor(x + 0.5)) if x >= 0 else -int(math.floor(-x + 0.5))


ROLES = ("tank", "dps", "healer", "out")   # "out": idle, does not take part


@dataclass
class Fighter:
    name: str
    level: int
    life: float                       # maximum life
    skill: float                      # Ügyesség / Skill (drives hit chance)
    agility: float                    # Fürgeség / Agility (avoids hits)
    charisma: float
    intelligence: float
    armor: float
    damage: Tuple[float, float]       # (min, max) weapon damage

    current_life: Optional[float] = None   # defaults to full life

    # Rating points (from the character sheet) ...
    critical_points: float = 0.0
    block_points: float = 0.0
    avoid_critical_points: float = 0.0
    # ... or direct percentages (override the points when given).
    # block_chance is the value against an opponent of the same level.
    critical_chance: Optional[float] = None
    block_chance: Optional[float] = None
    avoid_critical_chance: Optional[float] = None

    # Turma specific
    healing: float = 0.0
    critical_healing_chance: float = 0.0
    threat: float = 0.0               # "Veszély" value of the character sheet
    role: str = "dps"                 # "tank" | "dps" | "healer"
    is_main: bool = False
    profile_url: str = ""
    flag: str = ""                    # nationality flag from the profile: 2-letter code and/or image URL
    flag_url: str = ""

    # Arena specific god / pact buffs: minerva, mars, apollo,
    # honour_veteran, honour_destroyer
    buffs: frozenset = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        self.damage = (float(self.damage[0]), float(self.damage[1]))
        self.buffs = frozenset(self.buffs)
        if self.current_life is None:
            self.current_life = self.life
        if self.role not in ROLES:
            raise ValueError(f"unknown role {self.role!r}")

    @classmethod
    def from_dict(cls, data: dict) -> "Fighter":
        known = {f.name for f in fields(cls)}
        unknown = set(data) - known
        if unknown:
            raise ValueError(f"unknown fighter keys: {sorted(unknown)}")
        return cls(**data)

    # ---- own chances -----------------------------------------------------
    @property
    def level_factor(self) -> int:
        return max(2, int(self.level) - 8)

    def avoid_chance(self, cap: float = 25) -> float:
        if self.avoid_critical_chance is not None:
            return min(cap, self.avoid_critical_chance)
        pts = max(0.0, self.avoid_critical_points)
        return min(cap, php_round(pts * 52 / self.level_factor / 4))

    def crit_chance(self, cap: float = 50) -> float:
        if self.critical_chance is not None:
            return min(cap, self.critical_chance)
        pts = max(0.0, self.critical_points)
        return min(cap, php_round(pts * 52 / self.level_factor / 5))

    def base_block(self) -> float:
        if self.block_chance is not None:
            return self.block_chance
        pts = max(0.0, self.block_points)
        return php_round(pts * 52 / self.level_factor / 6)

    def armor_absorb(self, armor: Optional[float] = None) -> Tuple[int, int]:
        a = self.armor if armor is None else armor
        lo = math.floor(a / 66) - math.floor((a - 66) / 660 + 1)
        hi = math.floor(a / 66) + math.floor(a / 660)
        return int(lo), int(hi)

    # ---- chances against a specific opponent ------------------------------
    def hit_chance_vs(self, other: "Fighter") -> int:
        return int(math.floor(self.skill / (self.skill + other.agility) * 100))

    def double_hit_chance_vs(self, other: "Fighter") -> int:
        # Same formula in arena and turma (verified on turma report sheets).
        return php_round(
            self.charisma * self.skill / (other.agility * other.intelligence) * 10
        )

    def block_chance_vs(self, attacker: "Fighter") -> float:
        """Chance that *self* blocks a normal hit of *attacker*."""
        b = self.base_block() + max(0, self.level - attacker.level) * 2
        return min(50, b)
