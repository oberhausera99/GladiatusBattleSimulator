import os

from gladiatus_sim.report_parser import parse_report
from gladiatus_sim.calibrate import report_to_teams
from gladiatus_sim.turma import simulate_turma

HERE = os.path.dirname(__file__)


def _report():
    with open(os.path.join(HERE, "data", "report_114891789.html"), encoding="utf-8") as fh:
        return parse_report(fh.read(), "114891789")


def test_header_and_fighters():
    r = _report()
    assert r.winner == "Aveloca"
    assert (r.points_att, r.points_def) == (118498, 111637)
    assert len(r.fighters) == 10
    assert [f.is_player for f in r.fighters] == [True] + [False] * 4 + [True] + [False] * 4
    assert r.fighters[0].name == "Aveloca" and r.fighters[0].level == 369
    assert set(r.fighters[0].hit) == {11, 12, 13, 14, 15}


def test_events_reproduce_stat_table_and_points():
    r = _report()
    dmg = {"A": 0, "D": 0}
    heal = {"A": 0, "D": 0}
    for e in r.events:
        if e.kind in ("hit", "crit", "avoided_crit", "block"):
            dmg[e.side] += e.value
        elif e.kind == "heal":
            heal[e.side] += e.value
    assert dmg["A"] == sum(f.dmg_dealt for f in r.fighters if f.side == "A")
    assert heal["D"] == sum(f.heal_dealt for f in r.fighters if f.side == "D")
    assert abs(dmg["A"] + heal["A"] // 2 - r.points_att) <= len(r.events)


def test_blocked_crit_deals_normal_damage_range():
    r = _report()
    normal = [e.value for e in r.events if e.kind == "hit" and e.actor == "Aveloca" and e.target == "-Durham-"]
    blocked_crit = [e.value for e in r.events if e.kind == "avoided_crit" and e.actor == "Aveloca" and e.target == "-Durham-"]
    assert normal and blocked_crit
    assert max(blocked_crit) <= max(normal) * 1.05


def test_report_to_simulation_runs():
    att, dfd, ov = report_to_teams(_report())
    res = simulate_turma(att, dfd, runs=30, seed=1, pair_overrides=ov)
    assert 0 <= res.win_chance <= 100
    assert 40_000 < res.avg_points[0] < 300_000
