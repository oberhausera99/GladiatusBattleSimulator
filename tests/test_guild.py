import random

import pytest

from gladiatus_sim import gui_logic as gl
from gladiatus_sim.fetch import (Client, FetchError, parse_guild_ref, parse_member_list,
                                 search_guild)
from gladiatus_sim.fighter import Fighter
from gladiatus_sim.guild import guild_battle, simulate_guild
from tests import fake_game as fg


def fighter(name, dmg=100, life=5000, skill=500):
    return Fighter(name=name, level=50, life=life, skill=skill, agility=300, charisma=200,
                   intelligence=200, armor=100, damage=(dmg, dmg + 20))


def test_unequal_guilds_give_walkover_points():
    a = [fighter(f"a{i}") for i in range(5)]
    d = [fighter(f"d{i}") for i in range(3)]
    r = guild_battle(a, d, random.Random(1))
    walk = [p for p in r.pairs if p.walkover]
    assert len(r.pairs) == 5 and len(walk) == 2
    assert all(p.points == 1 and p.winner == "attacker" for p in walk)
    assert r.points_attacker + r.points_defender == 3 * 2 + 2 * 1


def test_draw_is_won_by_the_defender(monkeypatch):
    from gladiatus_sim import guild as g
    from gladiatus_sim.arena import ArenaBattle
    monkeypatch.setattr(g, "arena_battle", lambda *a, **k: ArenaBattle(0, 10, 10, 1, 1, 15))
    r = g.guild_battle([fighter("a")], [fighter("d")], random.Random(1))
    assert (r.points_attacker, r.points_defender) == (0, 2)
    assert r.pairs[0].winner == "defender" and r.pairs[0].drawn


def test_strong_guild_wins_and_statistics():
    strong = [fighter(f"s{i}", dmg=900) for i in range(4)]
    weak = [fighter(f"w{i}", dmg=20) for i in range(4)]
    s = simulate_guild(strong, weak, runs=50, seed=3)
    assert s.win_chance == 100 and s.avg_points == [8.0, 0.0]


def test_guild_ref_and_member_list_parsing():
    assert parse_guild_ref("2562") == "2562"
    assert parse_guild_ref("https://x/game/index.php?mod=guild&submod=memberList&i=2562&sh=abc") == "2562"
    assert parse_guild_ref("Some Guild") is None
    html = ('<tr><td><a href="index.php?mod=player&p=11&sh=aa">Alpha</a></td><td>Leader</td><td>120</td>'
            '<td align="right"></td></tr><tr><td><a href="index.php?mod=player&p=12&sh=aa">Beta</a></td>'
            '<td>Member</td><td>99</td></tr>')
    m = parse_member_list(html)
    assert [(x.pid, x.name, x.rank, x.level) for x in m] == [("11", "Alpha", "Leader", 120), ("12", "Beta", "Member", 99)]


@pytest.fixture()
def site():
    chars = lambda n, dmg: {1: fg.make_character(n, level=100, dmg=(dmg, dmg + 40))}
    players = {"1": chars("A1", 100), "2": chars("A2", 100), "3": chars("B1", 100)}
    srv, base = fg.start(players, {"A1": "1", "A2": "2", "B1": "3"},
                         guilds={"Red Legion": "10", "Blue Hawks": "20"},
                         members={"10": [("1", "A1", "Leader", 100), ("2", "A2", "Member", 100)],
                                  "20": [("3", "B1", "Leader", 100)]})
    yield Client(base=base, delay=0)
    srv.shutdown()


def test_search_by_name_and_by_id(site):
    assert search_guild(site, "en", "1", "Red Legion") == ("10", "Red Legion")
    assert search_guild(site, "en", "1", "20")[0] == "20"
    with pytest.raises(FetchError):
        search_guild(site, "en", "1", "No Such Guild")


def test_guild_flow_end_to_end(site):
    a, d = gl.fetch_players("guild", ("Red Legion", "s1-en"), ("Blue Hawks", "s1-en"), client=site)
    assert [f.name for f in a.fighters] == ["A1", "A2"] and len(d.fighters) == 1
    text = gl.run_simulation("guild", a, d, 1, seed=1)
    assert "Egyesületi csata" in text and "Párharcok" in text and "ellenfél nélkül" in text
    assert "Összeredmény" in text


def test_tag_matching_and_parallel_fetch(site):
    # the search tolerates brackets and case
    assert search_guild(site, "en", "1", "red legion")[0] == "10"
    a, d = gl.fetch_players("guild", ("10", "s1-en"), ("20", "s1-en"), client=site)
    assert [f.name for f in a.fighters] == ["A1", "A2"]      # member order is kept


def test_client_wait_is_thread_safe():
    import time
    from concurrent.futures import ThreadPoolExecutor
    c = Client(base="http://x", delay=0.05)
    t = time.time()
    with ThreadPoolExecutor(8) as ex:
        list(ex.map(lambda _: c._wait(), range(8)))
    assert time.time() - t >= 0.05 * 7 - 0.01      # requests are spaced even across threads


def test_503_is_retried_and_slows_the_client_down(monkeypatch):
    import io
    import urllib.error
    import urllib.request
    calls = []

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    def fake_urlopen(req, timeout=None):
        calls.append(1)
        if len(calls) < 3:
            raise urllib.error.HTTPError(req.full_url, 503, "busy", {"Retry-After": "0"}, None)
        return Resp(b"<html>ok</html>")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    c = Client(base="http://x", delay=0.01)
    assert c.request("http://x/a") == "<html>ok</html>"
    assert len(calls) == 3 and c.delay > 0.01
