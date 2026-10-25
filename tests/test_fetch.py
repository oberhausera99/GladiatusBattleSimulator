import pytest

from gladiatus_sim.fetch import (Client, FetchError, fetch_arena_fighter,
                                 fetch_turma_team, parse_player_spec,
                                 parse_server)
from tests import fake_game as fg


@pytest.fixture()
def site():
    arena = fg.make_character("Hero", level=100)
    turma_roles = {2: "Quest: Direct attention to oneself", 3: "Quest: Heal group members",
                   4: "Quest: Dish out damage", 5: "Quest: Do not take with"}
    players = {"77": {
        1: arena,
        2: fg.make_character("Hero", role_map=turma_roles, threat=3000),
        3: fg.make_character("Samnit", heal=900, threat=100),
        4: fg.make_character("Samnit", threat=200),
        5: fg.make_character("Samnit", threat=300),
    }}
    srv, base = fg.start(players, {"Hero": "77", "-Odd-": "78"})
    yield Client(base=base, delay=0)
    srv.shutdown()


def test_parse_server_and_spec():
    assert parse_server("s51-en") == ("en", "51")
    assert parse_server("51 HU") == ("hu", "51")
    assert parse_player_spec("-Durham-@s51-en") == ("-Durham-", "en", "51")
    with pytest.raises(FetchError):
        parse_player_spec("nobody")


def test_arena_fighter_is_parsed(site):
    f = fetch_arena_fighter(site, "Hero", "en", "1")
    assert (f.level, f.life, f.current_life) == (100, 1000, 900)
    assert (f.skill, f.agility, f.charisma, f.intelligence) == (400, 300, 250, 260)
    assert f.armor == 5000 and f.damage == (100.0, 140.0)
    assert (f.avoid_critical_points, f.block_points, f.critical_points) == (40, 90, 70)


def test_turma_team_roles_and_slots(site):
    team = fetch_turma_team(site, "Hero", "en", "1")
    # slot 6 does not exist, the 'out' merc (doll 5) is dropped
    assert [f.role for f in team] == ["tank", "healer", "dps"]
    assert team[0].is_main and team[0].threat == 3000
    assert team[1].healing == 900 and team[1].critical_healing_chance == 8


def test_unknown_player_is_a_clean_error(site):
    with pytest.raises(FetchError):
        fetch_arena_fighter(site, "Nobody", "en", "1")


def test_case_insensitive_name_fallback(site):
    f = fetch_arena_fighter(site, "hero", "en", "1")
    assert f.name.startswith("Hero")


def test_parse_flag_variants():
    from gladiatus_sim.fetch import parse_flag
    base = "https://s1-hu.gladiatus.gameforge.com/game/index.php?mod=player&p=5"
    a = '<tr><td>Nyelv:</td><td><img src="//lang.gameforge.com/flags/hu.gif" alt=""></td></tr>'
    assert parse_flag(a, base) == ("hu", "https://lang.gameforge.com/flags/hu.gif")
    b = '<tr><th>Language:</th><td><span class="flag flag_de" title="Deutsch"></span></td></tr><tr><td><img src="x/fr.png">'
    assert parse_flag(b, base) == ("de", "")
    c = '<td>Nyelv:</td><td><img src="/img/country/es.png" title="ES"></td>'
    assert parse_flag(c, base)[0] == "es"
    assert parse_flag("<td>Szint:</td><td>5</td>", base) == ("", "")
