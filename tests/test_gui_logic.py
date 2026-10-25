import pytest

from gladiatus_sim import gui_logic as gl
from gladiatus_sim.fetch import Client
from gladiatus_sim.fighter import Fighter
from gladiatus_sim.turma import normalize_team
from tests import fake_game as fg


@pytest.fixture()
def site():
    roles = {2: "Quest: Direct attention to oneself", 3: "Quest: Heal group members",
             4: "Quest: Dish out damage", 5: "Quest: Do not take with"}
    mk = lambda name, thr: {1: fg.make_character(name, level=100), 2: fg.make_character(name, role_map=roles, threat=thr),
                            3: fg.make_character("Samnit", heal=900, threat=100),
                            4: fg.make_character("Samnit", threat=200), 5: fg.make_character("Samnit", threat=300)}
    srv, base = fg.start({"77": mk("Hero", 3000), "78": mk("Odd", 2500)}, {"Hero": "77", "Odd": "78"})
    yield Client(base=base, delay=0)
    srv.shutdown()


def test_fetch_keeps_idle_for_the_gui_and_simulation_runs(site):
    a, d = gl.fetch_players("turma", ("Hero", "s1-en"), ("Odd", "s1-en"), client=site)
    assert len(a) == 4 and a[-1].role == "out"      # idle merc is kept so its role can be changed
    a[-1].role = "dps"
    text = gl.run_simulation("turma", a, d, 20, seed=1)
    assert "Circus Turma csata" in text and "támadó nyer" in text


def test_arena_flow(site):
    a, d = gl.fetch_players("arena", ("Hero", "s1-en"), ("Odd", "s1-en"), client=site)
    rows = gl.stat_rows(a, d)
    assert rows[0][0] == "Név" and ("Találati esély" in [r[0] for r in rows])
    assert "Aréna csata" in gl.run_simulation("arena", a, d, 50, seed=1)


def test_two_tank_mercs_become_idle():
    mk = lambda role, main=False: Fighter(name=role, level=50, life=1000, skill=100, agility=100, charisma=50,
                                          intelligence=50, armor=100, damage=(10, 20), role=role, is_main=main)
    team = normalize_team([mk("tank", True), mk("tank"), mk("tank"), mk("dps"), mk("out")])
    assert [f.role for f in team] == ["tank", "dps"] and team[0].is_main
