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

## Eredmények 50 valódi jelentésből (`gladiatus_sim/report_parser.py`)

A `tools/export_reports.js` által letöltött jelentéseket a `report_parser` alakítja
adattá (harcosok + lapon látott esélymátrixok + eseménysorok + összesítő tábla). Mind
az 50 jelentésen az események összege pontosan megegyezik az összesítő táblával.

**Találat-feloldás (megerősítve ~20 000 ütésen):**

* A **blokk független a kritikustól**: a találatok ~50%-a blokkolt (a lapon 50% a plafon),
  a kritikusak közül is. A blokkolt normál találat `dmg/2 - páncél` (sokszor 0, "blokkolt"),
  a blokkolt kritikus `dmg - páncél` (a jelentésben szürke, félkövér `**`).
* A kritikus elkerülés **külön dobás**: ha sikerül, a kritikus sima találattá válik.
  Így a kritikus események aránya `crit% * (1 - elkerülés%)`.
* Ez volt a korábbi 30-60%-os sebzéstöbblet oka: a régi sorrend (kritikus, majd blokk) nem
  blokkolta a kritikusokat és az elkerült kritikusokat.
* Az új szabállyal a szimuláció pontszáma a 33 Aveloca-Durham harcra átlag **~2%-on belül**
  egyezik (118k/115k valós, 120k/116k szimulált), és az egyes harcosok sebzése, gyógyítása is.

**Célpontválasztás (még nem teljesen megfejtett):**

* A főkarakterek (a játékos saját karaktere) a támadások ~80%-át kapják. Az illesztett
  súlyozás: "Veszély" érték, a főkarakterre ~6,5-szeres szorzóval (`main_multiplier`).
* A dupla találat mindig **ugyanarra a célpontra** megy.
* A célzás **időben változik**: a főkarakter saját első ütései az első ~9 körben közel
  egyenletesen oszlanak el (az ellenfél főkarakterét ~30%-ban célozzák), majd kb. a 10-25.
  körig 90%-ra nő. A zsoldosok kezdettől 70-85%-ban a főkarakterre mennek.
  A jelenlegi statikus súlyozás ezt nem adja vissza, de a végeredményre (pontszám) elég jó.
* Sokkal gyengébb támadók (-140 szint) a főkarakter ellen csak ~60%-ban célozzák.

**Zsoldos-tank (védőre állított zsoldos):** Aveloca csapatában a tank a 373-as szintű utolsó
Samnit (5. hely). Ugyanolyan statokkal 24,5k sebzést okoz átlagosan, a két másik hasonló
zsoldos 17,8k-t (+37%). A nyers fegyversebzésre **~7%-os bónusz** (`tank_damage_multiplier`)
illeszkedik, mert a páncél levonása után ez ~20-35% többlet. Durham csapatában a legtöbbet
sebző zsoldos (14-es hely) a tank; az aréna-körmérkőzéses tipp (`pick_tank`) ott mást (13-as)
választott, tehát a "legerősebb zsoldos" nem mindig a tank.

**Megerősítés 75 jelentésen, 14 ellenfél-csapattal:** Aveloca tankja a szimulációhoz képest
1,16-szor annyit sebez, a többi zsoldosa 0,85-ször; a relatív többlet **+37%**, 14 ellenfélből 11-nél
látszik. Az ellenfelek csapataiban is mindenhol kiugrik egy zsoldos (átlag 1,7x a többihez képest).
Az aréna-körmérkőzéses tank-tipp a csapatok 8/14-ében találta el ezt a zsoldost (az "első helyen
álló zsoldos" 10/14-ben), ezért a tankot lehetőleg meg kell adni (`roles=`).

**Még nyitott:** az időfüggő célzás pontos szabálya, a zsoldos-tank szerepe (a jelentés nem
tartalmazza a szerepeket), halálesetek hatása (az elemzett jelentésekben nem halt meg senki).

## Szerkezet

```
gladiatus_sim/fighter.py   harcos + közös esélyszámítás
gladiatus_sim/arena.py     aréna motor
gladiatus_sim/turma.py     turma motor, TurmaRules
gladiatus_sim/report_parser.py   mentett turma jelentések (HTML) feldolgozása
gladiatus_sim/calibrate.py     jelentés -> szimulációs csapatok (pontos lapesélyekkel)
tools/export_reports.js        jelentések letöltése a böngészőből
gladiatus_sim/cli.py       parancssor
examples/                  aréna példa, valódi turma jelentés (statok + megfigyelt eredmények)
tests/                     képlet- és motorellenőrzések
```
