"""Interface texts in Hungarian and English. ``t(key, **kw)`` returns the text in the current
language (default Hungarian); the choice is remembered in a small file in the home directory."""
from __future__ import annotations

import os
from typing import Dict

LANGS = {"hu": "Magyar", "en": "English"}
_current = "hu"
_PREF = os.path.join(os.path.expanduser("~"), ".gladiatus_sim_lang")

# key: (hungarian, english)
TEXTS: Dict[str, tuple] = {
    # window / menu
    "title": ("Gladiatus szimulátor", "Gladiatus simulator"),
    "menu_lang": ("Nyelv", "Language"),
    "settings": ("Beállítások", "Settings"),
    "mode_turma": ("Circus Turma (5v5)", "Circus Turma (5v5)"),
    "mode_arena": ("Aréna (1v1)", "Arena (1v1)"),
    "mode_guild": ("Egyesületi csata", "Guild battle"),
    "mode_best": ("Legjobb játékos", "Best player"),
    "attacker": ("Támadó", "Attacker"),
    "defender": ("Védő", "Defender"),
    "name_of": ("{who} neve:", "{who} name:"),
    "guild_name_of": ("{who} egyesület teljes neve (vagy azonosítója):",
                      "{who} guild name, tag or id:"),
    "server": ("szerver:", "server:"),
    "runs": ("Szimulációk száma:", "Number of simulations:"),
    "get_stats": ("Get stats", "Get stats"),
    "simulate": ("Simulate battle", "Simulate battle"),
    "full_life": ("Egyesületi csata: teljes életerővel számol (alapból az aktuális)",
                  "Guild battle: use full life (default: current life)"),
    "debug": ("Letöltött lapok mentése (debug_pages mappába)", "Save downloaded pages (to debug_pages folder)"),
    "lvl_from": ("Szint tól:", "Level from:"),
    "lvl_to": ("ig:", "to:"),
    "servers_lbl": ("Szerverek (üres = az összes EN):", "Servers (empty = all EN):"),
    "samples_lbl": ("Csata / páros:", "Battles / pair:"),
    "measure": ("Mérés:", "Measure:"),
    "m_arena": ("Aréna", "Arena"),
    "m_turma": ("Turma", "Turma"),
    "team_a": ("Támadó csapat", "Attacker team"),
    "team_d": ("Védő csapat", "Defender team"),
    "role_lbl": ("Szerep:", "Role:"),
    "result": ("Eredmény", "Result"),
    # roles
    "role_tank": ("tank (védő)", "tank (defender)"),
    "role_dps": ("támadó", "attacker"),
    "role_healer": ("gyógyító", "healer"),
    "role_out": ("tétlen", "idle"),
    # stat table
    "s_name": ("Név", "Name"), "s_level": ("Szint", "Level"),
    "s_life": ("Életerő (aktuális / max)", "Life (current / max)"),
    "s_skill": ("Ügyesség", "Skill"), "s_agility": ("Fürgeség", "Agility"),
    "s_charisma": ("Karizma", "Charisma"), "s_intelligence": ("Intelligencia", "Intelligence"),
    "s_armor": ("Páncél", "Armor"), "s_absorb": ("Elnyelés / ütés", "Absorbed / hit"),
    "s_damage": ("Sebzés", "Damage"), "s_hit": ("Találati esély", "Hit chance"),
    "s_double": ("Dupla találat", "Double hit"), "s_crit": ("Kritikus esély", "Critical chance"),
    "s_avoid": ("Kritikus elkerülés", "Critical avoidance"), "s_block": ("Blokk", "Block"),
    "s_heal": ("Gyógyítás", "Healing"), "s_dheal": ("Dupla gyógyítás", "Double healing"),
    "s_threat": ("Veszély", "Threat"), "s_role": ("Szerep", "Role"),
    # status line
    "st_two": ("Add meg a két játékost, majd kattints a Get stats gombra.",
               "Enter the two players, then click Get stats."),
    "st_best": ("Add meg a szintintervallumot és a szervereket, majd kattints a Get stats gombra.",
                "Enter the level interval (and the servers), then click Get stats."),
    "st_names": ("Mindkét játékos nevét add meg.", "Enter the names of both players."),
    "st_downloading": ("Statok letöltése...", "Downloading stats..."),
    "st_int": ("Egész számot adj meg ({key})", "Enter a whole number ({key})"),
    "st_searching": ("Játékosok keresése a toplistákon...", "Searching the highscore lists..."),
    "st_error": ("Hiba: {e}", "Error: {e}"),
    "st_unexpected": ("Váratlan hiba: {e}", "Unexpected error: {e}"),
    "st_best_done": ("{n} játékos letöltve ({srv} szerver, {err} hibás). Kattints a Simulate battle gombra.",
                     "{n} players downloaded ({srv} servers, {err} failed). Click Simulate battle."),
    "st_ok_turma": ("Statok letöltve. Állítsd be a szerepeket, majd kattints a Simulate battle gombra.",
                    "Stats downloaded. Set the roles, then click Simulate battle."),
    "st_ok": ("Statok letöltve. Kattints a Simulate battle gombra.",
              "Stats downloaded. Click Simulate battle."),
    "st_tournament": ("Verseny fut...", "Tournament running..."),
    "st_runs_int": ("A szimulációk száma egész szám legyen.", "The number of simulations must be a whole number."),
    "st_running": ("Szimuláció fut ({runs} csata)...", "Simulation running ({runs} battles)..."),
    "st_sim_err": ("Hiba a szimuláció közben: {e}", "Error during the simulation: {e}"),
    "st_done": ("Kész.", "Done."),
    # progress / errors from the logic layer
    "p_members": ("{g}: tagok letöltése {i}/{n}", "{g}: downloading members {i}/{n}"),
    "p_servers_find": ("Szerverek keresése: {i}/{n}", "Looking for servers: {i}/{n}"),
    "p_servers_crawl": ("Szerverek bejárása: {i}/{n}", "Crawling servers: {i}/{n}"),
    "p_players": ("Játékosok letöltése: {i}/{n}", "Downloading players: {i}/{n}"),
    "p_teams": ("Csapatok letöltése: {i}/{n}", "Downloading teams: {i}/{n}"),
    "p_stage1": ("Selejtező", "Qualifying"),
    "p_final": ("Döntő", "Final"),
    "p_pairs": ("{label}: {i}/{n} páros", "{label}: {i}/{n} pairs"),
    "e_no_member_read": ("{g}: egyik tag adatlapját sem sikerült beolvasni ({why})",
                         "{g}: could not read any member's page ({why})"),
    "e_no_members": ("nincs tag", "no members"),
    "e_no_servers": ("nem találtam szervert (add meg kézzel, pl. 1-60)",
                     "no server found (enter them manually, e.g. 1-60)"),
    "e_few_players": ("a {lo}-{hi} szinttartományban kevesebb mint 2 játékost találtam ({srv} szerver, {err} hibás)",
                      "found fewer than 2 players in the level range {lo}-{hi} ({srv} servers, {err} failed)"),
    "e_few_pages": ("kevesebb mint 2 játékos adatlapját sikerült beolvasni",
                    "could read the page of fewer than 2 players"),
    "suspicious": ("{name} (L{level}, élet {life:.0f}, sebzés {d0:.0f}-{d1:.0f})",
                   "{name} (L{level}, life {life:.0f}, damage {d0:.0f}-{d1:.0f})"),
    # result texts
    "arena_head": ("Aréna csata, {runs} szimuláció", "Arena battle, {runs} simulations"),
    "arena_win": ("{n} nyer: {p:.1f} %", "{n} wins: {p:.1f} %"),
    "arena_draw": ("döntetlen:     {p:.1f} %", "draw:           {p:.1f} %"),
    "arena_pts": ("átlagos pontszám: {a:.0f} - {d:.0f}", "average score: {a:.0f} - {d:.0f}"),
    "arena_rounds": ("átlagos körszám: {r:.1f}", "average rounds: {r:.1f}"),
    "turma_empty": ("Mindkét csapatban legalább egy aktív harcosnak lennie kell.",
                    "Both teams need at least one active fighter."),
    "turma_head": ("Circus Turma csata, {runs} szimuláció", "Circus Turma battle, {runs} simulations"),
    "turma_chances": ("támadó nyer: {w:.1f} %   döntetlen: {d:.1f} %   védő nyer: {l:.1f} %",
                      "attacker wins: {w:.1f} %   draw: {d:.1f} %   defender wins: {l:.1f} %"),
    "turma_pts": ("átlagos pontszám: {a} - {d}", "average score: {a} - {d}"),
    "turma_deaths": ("halálok csatánként: támadó {a:.2f}, védő {d:.2f}",
                     "deaths per battle: attacker {a:.2f}, defender {d:.2f}"),
    "turma_per": ("Harcosonként (átlag):", "Per fighter (average):"),
    "turma_row": ("sebzés {dmg}  gyógyítás {heal}", "damage {dmg}  healing {heal}"),
    "g_wins": ("{n} nyer", "{n} wins"), "g_draw": ("döntetlen", "draw"),
    "g_head": ("Egyesületi csata: {a} (támadó, {na} tag) vs {d} (védő, {nd} tag)",
               "Guild battle: {a} (attacker, {na} members) vs {d} (defender, {nd} members)"),
    "g_total": ("Összeredmény: {a} {pa} - {pd} {d}  =>  {v}", "Total: {a} {pa} - {pd} {d}  =>  {v}"),
    "g_runs": ("  {runs} szimuláció: {a} nyer {w:.1f} %, döntetlen {dr:.1f} %, {d} nyer {l:.1f} %, átlagpont {pa:.1f} - {pd:.1f}",
               "  {runs} simulations: {a} wins {w:.1f} %, draw {dr:.1f} %, {d} wins {l:.1f} %, average points {pa:.1f} - {pd:.1f}"),
    "g_first": ("  (az alábbi párosítás az első szimulált csata)", "  (the pairing below is the first simulated battle)"),
    "g_pairs": ("Párharcok:", "Pairings:"),
    "g_walkover": ("  {who} ({side}) ellenfél nélkül maradt: automatikus győzelem, +{pts} pont",
                   "  {who} ({side}) has no opponent: automatic win, +{pts} points"),
    "g_drawn": (" (döntetlen, a védő nyer)", " (draw, the defender wins)"),
    "g_pair": ("  {a} vs {d}: nyertes {w}{note}, +{pts} pont (pontszám {sa:.0f} - {sd:.0f}, {rounds} kör)",
               "  {a} vs {d}: winner {w}{note}, +{pts} points (score {sa:.0f} - {sd:.0f}, {rounds} rounds)"),
    "g_data": ("Adatbeolvasás:", "Data loading:"),
    "g_life_full": ("teljes", "full"), "g_life_cur": ("aktuális", "current"),
    "g_exp": (" / oldal szerint {n}", " / per page {n}"),
    "g_line": ("  {g}{full}: életerő: {life}; lista {listed} tag{exp}, beolvasva {ok}, hibás {bad}",
               "  {g}{full}: life: {life}; list {listed} members{exp}, loaded {ok}, failed {bad}"),
    "g_unreadable": ("    ! nem olvasható: {x}", "    ! unreadable: {x}"),
    "g_suspicious": ("    ? gyanús adat: {x}", "    ? suspicious data: {x}"),
    "g_summary_head": ("Statok letöltve. ", "Stats downloaded. "),
    "g_members": ("{g}: {ok}/{listed} tag", "{g}: {ok}/{listed} members"),
    "g_short": (" (az oldal szerint {exp} tag, a lista csak {listed}-et tartalmaz!)",
                " (the page says {exp} members, the list has only {listed}!)"),
    "g_failed": (", {n} nem olvasható", ", {n} unreadable"),
    # best player result
    "b_head": ("Legjobb játékosok: {lo}-{hi} szint, {srv} szerver, {n} játékos ({how})",
               "Best players: level {lo}-{hi}, {srv} servers, {n} players ({how})"),
    "b_how_turma": ("turma szabályok szerint, a profilban beállított zsoldosokkal",
                    "by turma rules, with the mercenaries set in the profile"),
    "b_how_arena": ("teljes életerővel, aréna szabályok szerint", "with full life, by arena rules"),
    "b_cols": ("  #  játékos                       szint  döntő győzelem%  selejtező győzelem%",
               "  #  player                        level  final win%       qualifying win%"),
    "b_method1": ("Módszer: minden játékos mindenkivel megmérkőzik (selejtező; ha túl sok a játékos, véletlen",
                  "Method: every player fights every other player (qualifying; with too many players,"),
    "b_method2": ("ellenfelekkel), a legjobb 16 körmérkőzést játszik (döntő). A győzelem% a mezőnytől függ.",
                  "against random opponents), the best 16 play a round robin (final). Win% depends on the field."),
    "b_servers_down": ("Nem elérhető szerverek ({n}): ", "Unavailable servers ({n}): "),
    "b_failed": ("Nem olvasható adatlap: {n} játékos", "Unreadable pages: {n} players"),
}


def get_language() -> str:
    return _current


def set_language(code: str, save: bool = True) -> None:
    global _current
    if code not in LANGS:
        raise ValueError(code)
    _current = code
    if save:
        try:
            with open(_PREF, "w", encoding="utf-8") as fh:
                fh.write(code)
        except OSError:
            pass


def load_saved_language() -> str:
    try:
        with open(_PREF, encoding="utf-8") as fh:
            code = fh.read().strip()
        if code in LANGS:
            set_language(code, save=False)
    except OSError:
        pass
    return _current


def t(key: str, **kw) -> str:
    hu, en = TEXTS[key]
    s = en if _current == "en" else hu
    return s.format(**kw) if kw else s
