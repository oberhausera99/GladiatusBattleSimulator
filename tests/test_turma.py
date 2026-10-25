import random

import pytest

from gladiatus_sim import Fighter, TurmaRules, simulate_turma, turma_battle


def mk(name, role="dps", life=20000, dmg=(900, 1100), heal=0.0, main=False, threat=1000):
    return Fighter(name, 100, life, 1000, 1000, 500, 500, 3000, dmg,
                   critical_chance=10, block_chance=10, avoid_critical_chance=5,
                   healing=heal, critical_healing_chance=0, threat=threat,
                   role=role, is_main=main)


def team(prefix, n=3, **kw):
    return [mk(f"{prefix}{i}", main=(i == 0), **kw) for i in range(n)]


def test_points_are_damage_plus_half_heal():
    att = team("a") + [mk("ah", role="healer", heal=3000)]
    dfn = team("d") + [mk("dh", role="healer", heal=3000)]
    b = turma_battle(att, dfn, random.Random(5))
    for s in (0, 1):
        dmg = sum(x.damage_done for x in b.stats[s])
        heal = sum(x.heal_done for x in b.stats[s])
        assert b.points[s] == pytest.approx(dmg + heal / 2)


def test_heal_never_exceeds_damage_taken():
    att = team("a") + [mk("ah", role="healer", heal=50000)]
    dfn = team("d")
    b = turma_battle(att, dfn, random.Random(2))
    taken = sum(x.damage_taken for x in b.stats[0])
    healed = sum(x.heal_taken for x in b.stats[0])
    assert healed <= taken + 1e-6


def test_damage_capped_by_life_and_dead_stay_dead():
    att = [mk("big", dmg=(20000, 21000), main=True)]
    dfn = [mk("weak", life=500, main=True)]
    b = turma_battle(att, dfn, random.Random(1), TurmaRules(rounds=50))
    assert b.winner == 0
    assert b.stats[1][0].died_round is not None
    assert b.stats[1][0].damage_taken <= 500 + 1e-6
    assert b.stats[0][0].swings < 20          # battle stopped early


def test_wiped_team_loses_even_with_more_points():
    # defender out-damages but is wiped out first
    att = [mk("a", life=1_000_000, dmg=(50, 60), main=True)]
    dfn = [mk("d", life=50, dmg=(900, 1100), main=True)]
    b = turma_battle(att, dfn, random.Random(0))
    assert b.winner == 0


def test_main_char_gets_most_swings_with_default_rules():
    att = team("a", 5, life=10**7)
    dfn = team("d", 5, life=10**7)
    r = simulate_turma(att, dfn, runs=200, seed=4)
    assert r.main_hit_share[0] > 0.6 and r.main_hit_share[1] > 0.6
    r2 = simulate_turma(att, dfn, runs=200, seed=4, rules=TurmaRules(targeting="uniform"))
    assert 0.1 < r2.main_hit_share[0] < 0.3


def test_seed_reproducible():
    att, dfn = team("a", 5), team("d", 5)
    assert simulate_turma(att, dfn, runs=50, seed=9).avg_points == \
        simulate_turma(att, dfn, runs=50, seed=9).avg_points


def test_real_report_runs(report):
    r = simulate_turma(report["att"], report["dfn"], runs=20, seed=1)
    assert r.runs == 20 and r.avg_deaths == [0.0, 0.0]


def test_role_targeting_dps_mercs_go_for_the_main_character():
    att = team("a", 5, life=10**7)
    dfn = team("d", 5, life=10**7)
    for f in att[1:]:
        f.role = "dps"
    r = simulate_turma(att, dfn, runs=100, seed=2)
    assert r.main_hit_share[0] > 0.8
