"""HTML guild battle report that imitates the look of the game's own report."""
from __future__ import annotations

import colorsys
import hashlib
from html import escape
from typing import Sequence

from .guild import GuildBattleResult
from .i18n import t

CSS = """
body{margin:0;background:#3b2a1a;font-family:Verdana,Arial,sans-serif;font-size:13px;color:#2b1a0a}
.page{max-width:620px;margin:0 auto;padding:14px 10px;background:#d9bf8c;border:6px double #7a5a2a}
.banners{display:flex;justify-content:space-between;margin-bottom:8px}
.banner{width:120px;height:62px;border:2px solid #4a331a;border-radius:2px 2px 30px 30px;color:#fff;
 text-align:center;font-weight:bold;font-size:11px;display:flex;align-items:center;justify-content:center;
 text-shadow:1px 1px 2px #000;padding:2px 6px;box-sizing:border-box;overflow:hidden;word-break:break-all;line-height:1.1}
.verdict{background:#c9a96a;border:1px solid #8a6a3a;padding:6px 8px;font-weight:bold;margin-bottom:8px}
table{width:100%;border-collapse:collapse;background:#ecd9b0;border:2px solid #8a6a3a}
th{padding:4px;border-bottom:1px solid #8a6a3a;background:#e0c993}
td{padding:2px 4px;white-space:nowrap}
tr:nth-child(even) td{background:#e6d2a3}
.l{text-align:right}.r{text-align:left}.n{text-align:center;width:14%}
.thumb{width:22px;text-align:center}
.name{text-decoration:underline;color:#1d4b8f;font-weight:bold}
.tot td{font-weight:bold;border-top:2px solid #8a6a3a;background:#e0c993}
.note{margin-top:8px;font-size:11px;color:#5a4020}
"""


def _banner(name: str) -> str:
    h = int(hashlib.md5(name.encode()).hexdigest()[:4], 16) / 65535
    r, g, b = (int(255 * x) for x in colorsys.hls_to_rgb(h, 0.32, 0.6))
    r2, g2, b2 = (int(255 * x) for x in colorsys.hls_to_rgb((h + 0.5) % 1, 0.45, 0.7))
    return (f'<div class="banner" style="background:linear-gradient(90deg,rgb({r},{g},{b}) 50%,'
            f'rgb({r2},{g2},{b2}) 50%)">{escape(name)}</div>')


def guild_report_html(att_name: str, def_name: str, res: GuildBattleResult, extra: str = "") -> str:
    win = {"attacker": att_name, "defender": def_name}.get(res.winner)
    verdict = t("r_won", n=escape(win)) if win else t("r_draw")
    rows = []
    thumb = "&#128077;"
    for p in res.pairs:
        att_won = p.winner == "attacker"
        la = f'<span class="name">{escape(p.attacker)}</span>' if p.attacker else ""
        ld = f'<span class="name">{escape(p.defender)}</span>' if p.defender else ""
        rows.append(
            f'<tr><td class="thumb">{thumb if att_won and p.attacker else ""}</td>'
            f'<td class="l">{la}</td><td class="n">{p.score_attacker:.0f}</td>'
            f'<td class="n">{p.score_defender:.0f}</td><td class="r">{ld}</td>'
            f'<td class="thumb">{thumb if not att_won and p.defender else ""}</td></tr>')
    total = (f'<tr class="tot"><td></td><td class="l">{res.points_attacker}&nbsp;&nbsp;{escape(att_name)}</td>'
             f'<td></td><td></td><td class="r">{escape(def_name)}&nbsp;&nbsp;{res.points_defender}</td><td></td></tr>')
    note = f'<div class="note">{escape(extra)}</div>' if extra else ""
    return (f'<!doctype html><html><head><meta charset="utf-8"><title>{escape(att_name)} vs {escape(def_name)}</title>'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><style>{CSS}</style></head><body>'
            f'<div class="page"><div class="banners">{_banner(att_name)}{_banner(def_name)}</div>'
            f'<div class="verdict">{verdict}</div>'
            f'<table><tr><th></th><th>{t("r_name")}</th><th>{t("r_damage")}</th><th>{t("r_damage")}</th>'
            f'<th>{t("r_name")}</th><th></th></tr>{"".join(rows)}{total}</table>{note}</div></body></html>')
