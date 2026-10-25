"""Mentett Circus Turma csatajelentések (HTML) feldolgozása strukturált adattá.

A bemenet a `tools/export_reports.js` által letöltött JSON ([{reportId, html}, ...])
vagy egy önálló jelentés HTML-je. A jelentés nyelve (magyar) a szövegminták miatt fix.
"""
from __future__ import annotations

import html as _html
import json
import re
from dataclasses import dataclass, field, asdict
from typing import Optional

ATT_IDS = [1, 2, 3, 4, 5]
DEF_IDS = [11, 12, 13, 14, 15]
DEFENDER_BG = "#CFC7A3"


def _num(s: str) -> int:
    return int(re.sub(r"[^\d-]", "", s) or 0)


def _text(s: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


@dataclass
class ReportFighter:
    fid: int
    side: str                      # 'A' támadó | 'D' védő
    name: str = ""
    level: int = 0
    life: int = 0
    strength: int = 0
    skill: int = 0
    agility: int = 0
    constitution: int = 0
    charisma: int = 0
    intelligence: int = 0
    armor: int = 0
    armor_lo: int = 0
    armor_hi: int = 0
    dmg_min: int = 0
    dmg_max: int = 0
    crit: int = 0
    avoid_crit: int = 0
    threat: int = 0
    heal: int = 0
    heal_crit: int = 0
    is_player: bool = False
    # cél fighter-id -> %
    hit: dict = field(default_factory=dict)
    double: dict = field(default_factory=dict)
    block: dict = field(default_factory=dict)
    # statisztika-táblából
    dmg_dealt: int = 0
    dmg_taken: int = 0
    heal_dealt: int = 0
    heal_taken: int = 0
    threat_total: int = 0


@dataclass
class Event:
    round: int
    side: str                      # a cselekvő oldala: 'A' | 'D'
    kind: str                      # hit | crit | avoided_crit | block | miss | heal | other
    actor: str
    target: str
    value: int = 0
    color: str = ""
    bold: bool = False


@dataclass
class Report:
    report_id: str
    winner: str = ""
    points_att: int = 0
    points_def: int = 0
    fighters: list = field(default_factory=list)
    events: list = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


def _block(h: str, start_id: str, next_ids: list[str]) -> str:
    i = h.find(f'id="{start_id}"')
    if i < 0:
        return ""
    ends = [h.find(f'id="{n}"', i + 10) for n in next_ids]
    ends = [e for e in ends if e > 0]
    return h[i:min(ends)] if ends else h[i:i + 12000]


def _parse_fighter(h: str, fid: int, side: str) -> ReportFighter:
    pre = "attacker" if side == "A" else "defender"
    f = ReportFighter(fid=fid, side=side)
    av = _block(h, f"{pre}Avatar{fid}", [f"{pre}Avatar{fid + 1}", f"{pre}CharStats{ATT_IDS[0] if side == 'A' else DEF_IDS[0]}"])
    m = re.search(r'class="playername(_achievement)?[^"]*">\s*(.*?)\s*</div>', av, re.S)
    if m:
        f.name = _text(m.group(2))
    f.is_player = fid in (ATT_IDS[0], DEF_IDS[0])   # az első helyen mindig a játékos karaktere áll
    cs_ids = [f"{pre}CharStats{i}" for i in (ATT_IDS if side == "A" else DEF_IDS)]
    idx = cs_ids.index(f"{pre}CharStats{fid}")
    nxt = cs_ids[idx + 1:idx + 2] + (["defenderAvatar11"] if side == "A" and idx == 4 else []) \
        + (['class="section-header"'] if False else [])
    cs = _block(h, f"{pre}CharStats{fid}", nxt)
    if side == "D" and idx == 4:
        cs = cs[: cs.find("section-header")] if "section-header" in cs else cs
    g = lambda pat: re.search(pat, cs, re.S)
    m = g(r'Szint</span>')  # szint a címke előtt áll
    m = re.search(r'value22(?:_mirrored)?">\s*(\d+)\s*</span>\s*<span[^>]*>Szint', cs)
    f.level = int(m.group(1)) if m else 0
    m = re.search(r'Életerő.*?value3(?:_mirrored)?">\s*([\d.]+)\s*/\s*([\d.]+)', cs, re.S)
    f.life = _num(m.group(2)) if m else 0
    for key, n in (("strength", 0), ("skill", 1), ("agility", 2), ("constitution", 3), ("charisma", 4), ("intelligence", 5)):
        m = re.search(rf'id="char_f{n}"[^>]*>\s*(\d+)', cs)
        setattr(f, key, int(m.group(1)) if m else 0)
    m = re.search(r'Páncél</span>\s*<span[^>]*>\s*(\d+)\s*\((\d+)\s*-\s*(\d+)\)', cs)
    if m:
        f.armor, f.armor_lo, f.armor_hi = int(m.group(1)), int(m.group(2)), int(m.group(3))
    m = re.search(r'Sebzés</span>\s*<span[^>]*>\s*(\d+)\s*-\s*(\d+)', cs)
    if m:
        f.dmg_min, f.dmg_max = int(m.group(1)), int(m.group(2))

    def single(label):
        m = re.search(label + r'</span>\s*<span[^>]*>\s*(\d+)\s*%?\s*</span>', cs)
        return int(m.group(1)) if m else 0

    f.crit = single("Esély a kritikus találatra")
    f.avoid_crit = single("Kritikus találat elkerülésének esélye")
    f.threat = single("Veszély")
    f.heal = single("Gyógyítás")
    f.heal_crit = single("dupla gyógyítási érték")
    for kind, attr in (("hitchance", "hit"), ("doublehitchance", "double"), ("blockchance", "block")):
        for m in re.finditer(rf'id="{kind}Fighter{fid}_(\d+)"[^>]*>\s*(\d+)\s*%', cs):
            getattr(f, attr)[int(m.group(1))] = int(m.group(2))
    return f


def _parse_stats_table(h: str, fighters: list[ReportFighter]) -> None:
    i = h.find("Sérülés és gyógyítás")
    j = h.find("</table>", i)
    rows = re.findall(r"<tr>\s*<th[^>]*>(.*?)</th>(.*?)</tr>", h[i:j], re.S)
    rows = [(n, c) for n, c in rows if "<td" in c]
    for f, (_, cells) in zip(fighters, rows):
        vals = [_num(_text(c)) for c in re.findall(r"<td[^>]*>(.*?)</td>", cells, re.S)]
        if len(vals) >= 5:
            f.dmg_dealt, f.dmg_taken, f.heal_dealt, f.heal_taken, f.threat_total = vals[:5]


_HIT = re.compile(r"^(.*?) megütötte (.*?) -t\.$")
_HEAL = re.compile(r"^(.*?) gyógyítja (.*?) -t\.$")


def _parse_events(h: str) -> list[Event]:
    i = h.find("Csata jelentés - (")
    body = h[i:] if i >= 0 else h
    out: list[Event] = []
    rnd = 0
    for m in re.finditer(r"<tr([^>]*)>(.*?)</tr>", body, re.S):
        attrs, inner = m.groups()
        hm = re.search(r"Kör\s+(\d+)", inner)
        if hm and "colspan" in inner:
            rnd = int(hm.group(1))
            continue
        cells = re.findall(r"<td[^>]*>(.*?)</td>", inner, re.S)
        if len(cells) < 2:
            continue
        line = _text(cells[0])
        side = "D" if DEFENDER_BG.lower() in attrs.lower() else "A"
        res_html = cells[1]
        res = _text(res_html)
        cm = re.search(r'<font color="([^"]+)"', res_html)
        color = cm.group(1) if cm else ""
        bold = "<b>" in res_html
        n = re.search(r"(\d[\d.]*)\s*(?:sebzést|gyógyítást)", res)
        val = _num(n.group(1)) if n else 0
        hm = _HIT.match(line)
        if hm:
            actor, target = hm.groups()
            if "nem talált" in res:
                kind, val = "miss", 0
            elif "blokkolt" in res:
                kind, val = "block", 0
            elif "**" in res:
                kind = "crit" if color == "red" else "avoided_crit"
            elif color == "dimgray":
                kind = "block"          # elhárított (félbe csökkentett) találat
            else:
                kind = "hit"
            out.append(Event(rnd, side, kind, actor, target, val, color, bold))
            continue
        hm = _HEAL.match(line)
        if hm:
            out.append(Event(rnd, side, "heal", hm.group(1), hm.group(2), val, color, bold))
            continue
        out.append(Event(rnd, side, "other", line, res, 0, color, bold))
    return out


def parse_report(html: str, report_id: str = "") -> Report:
    r = Report(report_id=str(report_id))
    m = re.search(r"Győztes:\s*([^<]+)", html)
    r.winner = m.group(1).strip() if m else ""
    m = re.search(r"Támadó Pontjai:\s*(\d+)", html)
    r.points_att = int(m.group(1)) if m else 0
    m = re.search(r"Védő pontjai:\s*(\d+)", html)
    r.points_def = int(m.group(1)) if m else 0
    r.fighters = [_parse_fighter(html, i, "A") for i in ATT_IDS] + [_parse_fighter(html, i, "D") for i in DEF_IDS]
    _parse_stats_table(html, r.fighters)
    r.events = _parse_events(html)
    return r


def load_reports(path: str) -> list[Report]:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict):
        data = [data]
    return [parse_report(d["html"], d.get("reportId", "")) for d in data]
