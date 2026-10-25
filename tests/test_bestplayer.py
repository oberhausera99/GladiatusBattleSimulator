import random

from gladiatus_sim import gui_logic as gl
from gladiatus_sim.bestplayer import (Candidate, crawl_server, parse_highscore, parse_server_range,
                                      tournament)
from gladiatus_sim.fetch import Client
from gladiatus_sim.fighter import Fighter
from tests import fake_game as fg


def test_server_range():
    assert parse_server_range("1-3, 7, s9") == ["1", "2", "3", "7", "9"]


def test_parse_highscore_header_level_and_links():
    html = ('<table><tr><th>Hely</th><th>Név</th><th>Szint</th><th>Fame</th></tr>'
            '<tr><td>1</td><td><a href="index.php?mod=player&p=5&sh=a">Alpha</a></td><td>140</td><td>9.999</td></tr>'
            '</table><a href="index.php?mod=highscore&amp;p=2&amp;sh=a">2</a>'
            '<a href="index.php?mod=highscore&amp;t=1&amp;sh=a">guilds</a>')
    rows, links = parse_highscore(html)
    assert rows == [("5", "Alpha", 140)]
    assert links == ["index.php?mod=highscore&p=2&sh=a"]          # the guild list is not followed


def test_parse_highscore_without_header_guesses_level():
    html = ('<tr><td>12</td><td><a href="index.php?mod=player&p=7">Bob</a></td><td>88</td><td>5.000</td></tr>')
    assert parse_highscore(html)[0] == [("7", "Bob", 88)]


def mk(name, dmg):
    return Fighter(name=name, level=140, life=30000, skill=1200, agility=1000, charisma=900,
                   intelligence=900, armor=20000, damage=(dmg, dmg + 40))


def test_tournament_puts_the_strongest_first():
    fs = [mk(f"p{i}", 600 + 40 * i) for i in range(12)]
    top = tournament(fs, opponents=6, samples=4, finalists=6, final_samples=20, seed=1, top=3)
    assert top[0].fighter.name == "p11" and len(top) == 3
    assert top[0].final >= top[1].final >= top[2].final


def test_crawl_and_full_flow_on_fake_server():
    pages = [[("1", "A", 100), ("2", "B", 135), ("3", "C", 142)],
             [("4", "D", 150), ("5", "E", 130), ("6", "F", 160)]]
    players = {str(i): {1: fg.make_character(n, level=l, dmg=(100 + 30 * i, 140 + 30 * i))}
               for i, n, l in [(2, "B", 135), (3, "C", 142), (4, "D", 150), (5, "E", 130)]}
    srv, base = fg.start(players, {}, highscore=pages)
    try:
        c = Client(base=base, delay=0)
        cands = crawl_server(c, "en", "1", 130, 150)
        assert [x.name for x in cands] == ["B", "C", "D", "E"]       # follows page links, filters the level
        b = gl.fetch_best_set(130, 150, "1", 10, client=Client(base=base, delay=0))
        text = gl.best_text(b, opponents=3, samples=2, seed=1)
        assert "Legjobb játékosok" in text and "1  " in text
    finally:
        srv.shutdown()
