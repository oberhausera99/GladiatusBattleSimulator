"""A tiny fake Gladiatus server that serves pages in the layout the parser expects.

This only tests our plumbing (URL building, parsing, role mapping); the real
game markup is mirrored from the GladiatusPlayerStatsAPI patterns.
"""
import html
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

PAD = "<!-- pad -->" * 4000          # real pages are long; parsers skip the head


def tooltip(role_text):
    inner = f"<table><tr><td><font style=font-size:smaller;color:#DDDDDD>{role_text}</font></td></tr></table>"
    return html.escape(json.dumps([[[inner, "white"]]]), quote=True)


def page(ch):
    nums = [10, 20, 30, 40, 50, 60, 70, ch["avoid"], ch["block"], ch["crit"], 5, ch["cheal"], 7]
    num_tt = "".join(f'&quot;,{n}], [&quot;#BA9700&quot;,&quot;#BA9700&quot;]]' for n in nums)
    pct_tt = "".join(f'&quot;,&quot;{p} %&quot;],[&quot;#DDDDDD&quot;,&quot;#DDDDDD&quot;]]'
                     for p in ch["pcts"])
    stats = "".join(f'<span id="char_f{i}" class="charstats_value">{v}</span>'
                    for i, v in enumerate(ch["stats"]))
    mercs = ""
    for doll, role in ch.get("roles", {}).items():
        mercs += f'<div class="charmercpic doll{doll}" data-tooltip="{tooltip(role)}"></div>'
    return (
        "<html><head>" + PAD + "</head><body><div id=\"content\">"
        f'<div class="playername ellipsis">{ch["name"]}</div>'
        f'<span id="char_level" class="charstats_value22">{ch["level"]}</span>'
        '<div class="charstats_bg" id="char_leben_tt" data-tooltip="[[[[&quot;Life&quot;,'
        f'&quot;{ch["life"][0]} \\/ {ch["life"][1]}&quot;]]]]"></div>'
        + stats +
        f'<span id="char_panzer" class="charstats_value22">{ch["armor"]}</span>'
        f'<span id="char_schaden" class="charstats_value22">{ch["dmg"][0]} - {ch["dmg"][1]}</span>'
        f'<span id="char_healing" class="charstats_value22">{ch["heal"]}</span>'
        f'<span id="char_threat" class="charstats_value22">{ch["threat"]}</span>'
        f'<div data-x="{num_tt}"></div><div data-y="{pct_tt}"></div>' + mercs +
        "</div>" + PAD[:3000] + "</body></html>")


def make_character(name, role_map=None, **kw):
    ch = dict(name=name, level=100, life=(900, 1000), stats=[100, 400, 300, 200, 250, 260],
              armor=5000, dmg=(100, 140), heal=50, threat=1234, avoid=40, block=90,
              crit=70, cheal=30, pcts=[12, 34, 15, 8], roles=role_map or {})
    ch.update(kw)
    return ch


class Handler(BaseHTTPRequestHandler):
    players = {}      # id -> {doll -> character}
    names = {}        # name -> id
    guilds = {}       # guild name -> id
    members = {}      # guild id -> [(player id, name, rank, level)]
    highscore = []    # pages of [(player id, name, level)]

    def log_message(self, *a):
        pass

    def _send(self, body):
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        form = parse_qs(self.rfile.read(n).decode())
        q = form.get("xs", [""])[0]
        rows = "".join(f'<a href="index.php?mod=player&p={pid}" target="_self">{nm}</a>'
                       for nm, pid in self.names.items() if q.lower() in nm.lower())
        rows += "".join(f'<a href="index.php?mod=guild&submod=forumGladiatorius&i={gid}">{nm}</a>'
                        for nm, gid in self.guilds.items() if q.lower() in nm.lower())
        self._send("<html>" + PAD + rows + PAD + "</html>")

    def do_GET(self):
        q = parse_qs(urlparse(self.path).query)
        if q.get("mod", [""])[0] == "highscore" and self.highscore:
            pg = int(q.get("page", ["0"])[0])
            rows = "".join(
                f'<tr><td>{pg * 10 + k + 1}</td><td class="ellipsis"><a href="index.php?mod=player&p={pid}&sh=x">{nm}</a></td>'
                f'<td>{lv}</td><td>1.234</td></tr>' for k, (pid, nm, lv) in enumerate(self.highscore[pg]))
            nav = "".join(f'<a href="index.php?mod=highscore&amp;page={i}&amp;sh=x">{i + 1}</a>'
                          for i in range(len(self.highscore)))
            guild = '<a href="index.php?mod=highscore&amp;t=1&amp;sh=x">Guilds</a>'
            self._send("<html>" + PAD + "<table><tr><th>Rank</th><th>Name</th><th>Level</th><th>Fame</th></tr>"
                       + rows + "</table>" + nav + guild + PAD + "</html>")
            return
        if q.get("submod", [""])[0] == "memberList":
            rows = "".join(
                f'<tr><td><a href="index.php?mod=player&p={pid}&sh=x">{nm}</a></td><td>{rk}</td><td>{lv}</td>'
                '<td align="right"></td></tr>'
                for pid, nm, rk, lv in self.members.get(q.get("i", [""])[0], []))
            self._send("<html>" + PAD + "<table>" + rows + "</table>" + PAD + "</html>")
            return
        pid = q.get("p", [""])[0]
        doll = int(q.get("doll", ["1"])[0])
        ch = self.players.get(pid, {}).get(doll)
        self._send(page(ch) if ch else "<html>" + PAD + "nothing</html>")


def start(players, names, guilds=None, members=None, highscore=None):
    Handler.highscore = highscore or []
    Handler.players, Handler.names = players, names
    Handler.guilds, Handler.members = guilds or {}, members or {}
    srv = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}"
