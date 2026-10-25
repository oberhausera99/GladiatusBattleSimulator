"""Chances computed from raw stats must equal the values on a real battle report."""
import pytest


def _pairs(att, dfn):
    for i, a in enumerate(att):
        for j, d in enumerate(dfn):
            yield i, j, a, d


def test_hit_chance_matches_sheet(report):
    s = report["sheet"]
    for i, j, a, d in _pairs(report["att"], report["dfn"]):
        assert a.hit_chance_vs(d) == s["hit_attackers"][i][j], (a.name, d.name)
    for i, j, d, a in _pairs(report["dfn"], report["att"]):
        assert d.hit_chance_vs(a) == s["hit_defenders"][i][j], (d.name, a.name)


def test_double_hit_chance_matches_sheet(report):
    s = report["sheet"]
    for i, j, a, d in _pairs(report["att"], report["dfn"]):
        assert a.double_hit_chance_vs(d) == s["double_attackers"][i][j], (a.name, d.name)
    for i, j, d, a in _pairs(report["dfn"], report["att"]):
        assert d.double_hit_chance_vs(a) == s["double_defenders"][i][j], (d.name, a.name)


def test_block_chance_matches_sheet(report):
    s = report["sheet"]
    for i, j, a, d in _pairs(report["att"], report["dfn"]):
        # block chance of attacker i when hit by defender j
        assert a.block_chance_vs(d) == s["block_attackers_vs_defenders"][i][j]
    for i, j, d, a in _pairs(report["dfn"], report["att"]):
        assert d.block_chance_vs(a) == s["block_defenders_vs_attackers"][i][j], (d.name, a.name)


def test_armor_absorb_matches_sheet(report):
    s = report["sheet"]
    for f, exp in zip(report["att"], s["absorb_attackers"]):
        assert list(f.armor_absorb()) == exp
    for f, exp in zip(report["dfn"], s["absorb_defenders"]):
        assert list(f.armor_absorb()) == exp


def test_points_to_percent_conversion():
    from gladiatus_sim import Fighter
    f = Fighter("x", 100, 1000, 100, 100, 100, 100, 0, (1, 2),
                critical_points=40, block_points=500, avoid_critical_points=3000)
    assert f.crit_chance() == round(40 * 52 / 92 / 5)
    assert f.base_block() == round(500 * 52 / 92 / 6)
    assert f.avoid_chance() == 25            # capped
