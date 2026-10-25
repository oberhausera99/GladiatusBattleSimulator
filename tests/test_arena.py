from gladiatus_sim import Fighter, simulate_arena


def make(name, dmg=(100, 140), life=3000, skill=100):
    return Fighter(name, 30, life, skill, 100, 100, 100, 600, dmg,
                   critical_chance=10, block_chance=10, avoid_critical_chance=5)


def test_mirror_is_fair():
    r = simulate_arena(make("a"), make("b"), runs=6000, seed=3)
    assert 44 < r.win_chance < 56
    assert r.win_chance + r.draw_chance + r.lose_chance == pytest.approx(100)


def test_stronger_fighter_wins():
    r = simulate_arena(make("a", dmg=(300, 400), life=9000), make("b"), runs=500, seed=1)
    assert r.win_chance > 99


def test_seed_reproducible():
    a = simulate_arena(make("a"), make("b"), runs=500, seed=7)
    b = simulate_arena(make("a"), make("b"), runs=500, seed=7)
    assert a == b


def test_gods_and_buffs():
    a, b = make("a"), make("b")
    a.buffs = frozenset({"minerva"})
    from gladiatus_sim.arena import _Side
    assert _Side(a, b).double == 0 and _Side(b, a).double == 0


import pytest  # noqa: E402
