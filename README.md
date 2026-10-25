# GladiatusBattleSimulator (Python)

Gladiatus **aréna** (1v1) és **Circus Turma** (5v5) csataszimulátor Pythonban, függőségek nélkül.

Az aréna motor a [DinoDevs/GladiatusBattleSimulator](https://github.com/DinoDevs/GladiatusBattleSimulator)
(PHP) jól működő arénakódjának portja. A turma motor új: a régi PHP-s turma kód
több ponton hibás volt, ezeket egy valódi csatajelentés számaival ellenőriztem és javítottam.

## Játékosok lekérdezése név és szerver alapján

A játék nyilvános profiloldalát bejelentkezés nélkül le lehet kérni, ugyanígy dolgozik az
eredeti [GladiatusPlayerStatsAPI](https://github.com/DinoDevs/GladiatusPlayerStatsAPI)
is (az innen portolt részeknek a licence LGPL-3.0). A szerver formátuma `s51-en`
(szerverszám + országkód), a két játékos lehet különböző szerveren.

```bash
# aréna: a karakter arénás felszerelése (doll=1)
python -m gladiatus_sim fight arena --attacker "Aveloca@s59-en" --defender=-Durham-@s51-en

# turma: a főkarakter + zsoldosok szerepekkel (doll=2..6)
python -m gladiatus_sim fight turma --attacker "Aveloca@s59-en" --defender=-Durham-@s51-en --runs 2000

# csak letöltés, JSON-ba (szerkeszthető, majd a `turma` / `arena` parancs bemenete)
python -m gladiatus_sim show turma "Aveloca@s59-en" > aveloca_turma.json
```

Ha a név kötőjellel kezdődik, az `=` jeles alakot használd (`--defender=-Durham-@s51-en`).
A szerepeket (tank, dps, gyógyító, "kimarad") a játék tooltipjéből olvassa ki, a
szövegek országonként vannak (31 ország).

**Fontos:** a letöltés az oldal HTML-jét reguláris kifejezésekkel olvassa. A
fejlesztési környezetemből a játék szervere nem érhető el, ezért a lekérdezést
csak egy mesterséges, a játék oldalainak szerkezetét utánzó teszt-szerverrel
próbáltam ki (`tests/fake_game.py`), éles játékoldallal nem. Ha egy lekérdezés
"could not find ... on the page" hibát ad, futtasd `--save-html mappa` kapcsolóval,
és a mentett oldalak alapján javítható a szerkezet.

## Használat

```bash
pip install -e .[dev]
python -m gladiatus_sim arena  examples/arena_example.json --runs 10000
python -m gladiatus_sim turma  csapatok.json --runs 1000
python -m gladiatus_sim compare examples/turma_report_114889279.json --runs 500
pytest
```

```python
from gladiatus_sim import Fighter, simulate_arena, simulate_turma, TurmaRules

a = Fighter("Aveloca", level=369, life=85358, skill=4049, agility=3120,
            charisma=3121, intelligence=3121, armor=107031, damage=(2312, 2538),
            critical_chance=30, avoid_critical_chance=25, block_chance=50)
print(simulate_arena(a, other, runs=10000))
print(simulate_turma(attackers, defenders, runs=1000, rules=TurmaRules(main_multiplier=8)))
```

Egy harcos adatai pontértékekből (`critical_points`, `block_points`,
`avoid_critical_points`) vagy közvetlenül százalékból (`critical_chance`,
`block_chance`, `avoid_critical_chance`) adhatók meg. A `block_chance` az
azonos szintű ellenfél elleni érték. Turmában szerep (`role`: `tank` / `dps` /
`healer`), `threat` (a karakterlap "Veszély" értéke), `healing`,
`critical_healing_chance` és `is_main` (a játékos saját karaktere) is kell.
Egy teljes példa: `examples/turma_report_114889279.json`.

## Mi van ellenőrizve (tesztekkel, valódi jelentés alapján)

A `tests/test_formulas.py` a jelentés lapján szereplő **mind a 100 harcospárra**
összeveti a nyers statokból számolt értékeket a lapon látottakkal:

| | képlet | eredmény |
|---|---|---|
| találati esély | `floor(ügyesség / (ügyesség + ellenfél fürgesége) * 100)` | egyezik |
| dupla találat | `round(karizma * ügyesség / (ellenfél fürgesége * ellenfél intelligenciája) * 10)` | egyezik (aréna és turma ugyanaz) |
| blokk | `round(pont*52/(szint-8)/6) + 2*max(0, szintkülönbség)`, max 50 | egyezik |
| páncélelnyelés | a régi kód képlete | egyezik |
| turma pontszám | okozott sebzés + hatékony gyógyítás / 2 | egyezik, a jelentés pontszáma a tizedesig kijön |

A régi PHP turma kód **hibái**: a dupla találatot a karizmák különbségéből számolta,
és a százalékos plafon rosszul volt megírva (egy tömböt hasonlított egy számhoz), ezért
magas szinten szinte mindenki mindig duplázott. A tank 10x-es veszélyszorzója
ki volt kommentelve, a gyógyítók `threat=0`-val soha nem lehettek célpontok.

## Ami még NEM biztos (kalibrálandó)

A `compare` parancs egy valódi jelentéshez hasonlítja a szimulációt. Az egyetlen
elemzett jelentésnél:

* **Célpontválasztás**: a főkarakter a találatok 76%-át és 84%-át kapta. A
  szimulátor alapértelmezése a "Veszély" érték szerinti súlyozott húzás, a
  főkarakter 8-szoros szorzójával (`TurmaRules.main_multiplier`). Ez az eloszlást
  jól visszaadja (76%, illetve 86%), de egyetlen harcból illesztett hipotézis. A
  zsoldos-tank szorzója alapból 1, mert ha a főkarakterrel megegyező szorzót kap,
  a főkarakter aránya 51-69%-ra esik.
* **Sebzés nagysága**: a szimuláció jelenleg 30-60%-kal több sebzést okoz, mint a
  valóságos jelentés, ezért a csapatpontok is magasabbak. A találatszámok,
  a kudarcarányok (elhibázott/blokkolt) egyeznek. Valószínű ok: a kritikus
  találat és a blokk sorrendje vagy a kritikus elkerülés tényleges valószínűsége.
  A `crit_block_order` és az `avoid_critical_cap` kapcsolók erre vannak.
* **Zsoldos védő szerep**: a megfigyelés szerint az egyetlen védőre állított zsoldos
  többet sebez, mint támadóként. Ezt még nem modellezi a szimulátor.
* **Halálesetek** hatása a célzásra: az elemzett jelentésben senki sem halt meg.

Hogyan lehet tovább pontosítani: több valódi jelentést kell a
`examples/turma_report_*.json` formátumban rögzíteni (statlap + a jelentés
összesítő táblája + a szerepkiosztás), majd `compare --rule kulcs=érték`-kel
ráilleszteni a szabályokat.

## Szerkezet

```
gladiatus_sim/fighter.py   harcos + közös esélyszámítás
gladiatus_sim/arena.py     aréna motor
gladiatus_sim/turma.py     turma motor, TurmaRules
gladiatus_sim/cli.py       parancssor
examples/                  aréna példa, valódi turma jelentés (statok + megfigyelt eredmények)
tests/                     képlet- és motorellenőrzések
```
