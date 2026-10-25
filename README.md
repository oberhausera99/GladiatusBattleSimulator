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

## Grafikus felület

```
python -m gladiatus_sim gui      # vagy: gladiatus-sim gui
```

Add meg a támadó és a védő nevét + szerverét (pl. `s51-en`), a szimulációk számát, majd
**Get stats**. Turmánál a két csapat tagjai között lehet váltani (★ = a játékos saját
karaktere), a középső táblázat mindig a kiválasztott két harcos statjait mutatja egymással
szemben (az esélyek egymás ellen értendők). A kiválasztott harcos **szerepe** (tank, támadó,
gyógyító, tétlen) átállítható. Két vagy több tankra állított zsoldos a játék szabálya szerint
tétlen lesz. **Egyesületi csata** (harmadik mód): add meg a két egyesület **teljes nevét** (vagy az azonosítóját: az
egyesületi oldal URL-jében az `i=` szám, pl. 2562) és a szervert. A Get stats letölti a tagok listáját
(`mod=guild&submod=memberList&i=ID`) és minden tag aréna-karakterét; a listában a névre kattintva a tag
statjai látszanak. Szabályok: a tagokat véletlenszerűen párosítja, a párok aréna csatát vívnak; ha az
egyik egyesületben több tag van, a felesleg ellenfél nélkül automatikusan nyer (+1 pont); csatagyőzelem
+2 pont; döntetlen esetén a védő egyesület tagja nyer (+2). Több pontot szerző egyesület a győztes. Az
eredmény: összpontszám + minden párharc (ki kivel, ki nyert). A minta alapértelmezése 1 csata. Az
egyesületi keresés a játék kereső oldalán nem volt ellenőrizhető, ha nem találja a nevet, add meg az
azonosítót. A letöltés gyorsítása: gzip tömörítés, 8 párhuzamos szál oldalanként, a két egyesület egyszerre töltődik, a kérések közti szünet önmagát hangolja (503 esetén lassít, utána fokozatosan gyorsul), és a letöltött lapok 10 percig a lemezen (`%TEMP%/gladiatus_sim_cache`) gyorsítótárban vannak, így az ismételt Get stats azonnali. A csatákhoz a tagok **aktuális** életerejével számol (a letöltés pillanatában), ahogy az aréna is; a GUI-ban egy jelölőnégyzettel a teljes életerőre lehet váltani (`life_mode="full"`).

**Legjobb játékos** (negyedik mód): csak a szintintervallumot kell megadni (pl. 130-150). Az EN szervereket
a program magától derítené fel (lobby JSON, ennek hiányában `s1..s300-en` DNS/HTTP próba); a szerverek mező
üresen hagyva = az összes EN szerver (kézzel is megadható, pl. `1-60`). A Get stats minden szerver
játékos-toplistáját bejárja (a lapok lapozó linkjeit követi), **korlát nélkül** összegyűjti az intervallumba
eső összes játékost, és letölti az aréna karakterüket. A **Mérés** választóval (Aréna / Turma) dől el, hogy az aréna-karakterek 1v1-ben, vagy a profilban beállított 5 fős turma-csapatok (szerepekkel, 5 letöltés/játékos, kisebb csataszám-kerettel: ~150 ezer csata) mérkőznek. A Simulate battle mindenkit mindenkivel megütköztet
(csak ha ez a ~4 millió csatás keretet meghaladná, akkor véletlen ellenfelek), a legjobbak körmérkőzést
játszanak (döntő), és kiírja az 5 legerősebbet. A szerverfelderítést és a toplista markupját a játékon nem
tudtam ellenőrizni; ha nem talál semmit, a `debug_pages` jelölőnégyzettel mentsd a lapokat.

**Egyesületi jelentés:** a guild szimuláció után a program a játékbeli jelentéshez hasonló HTML oldalt készít (két zászló/felirat fent, győztes sor, páronként a sebzés/pontszám, győztes oldalon 👍, alul az összpontszám), és megnyitja a böngészőben; a *Jelentés megnyitása* gombbal újra előhozható.

**Nyelv:** a menüsor *Nyelv / Language* menüjében magyar és angol között lehet váltani, azonnal, az adatok elvesztése nélkül (a már kiírt eredményszöveg a régi nyelven marad, a következő szimulációtól az újon jelenik meg). A választás a felhasználó könyvtárában a `.gladiatus_sim_lang` fájlban megmarad. A szövegek a `gladiatus_sim/i18n.py` katalógusban vannak.

A **Simulate battle** gomb lefuttatja a szimulációt és kiírja az eredményt.
Linuxon a `python3-tk` csomag kell hozzá.

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
Samnit (5. hely): ugyanolyan statokkal átlagosan 24,5k sebzést okoz, a két másik hasonló zsoldos
17,8k-t (+37%). A **mechanizmus nem a megemelt ütésenkénti sebzés**: Durham ellen 1026 normál
zsoldos-találat közül egy sem lépi túl a bónusz nélküli maximumot (926 <= 934), +7% bónusznál ~100-at
várnánk. Az ütések száma sem több (166 megfigyelt vs 168 szimulált). A relatív különbséget az
magyarázza (14 ellenfélnél 0,87 vs 0,85), ha a **tank zsoldos nem a főkarakterre fókuszál**, hanem
a veszély értékek szerint (főkarakter-szorzó nélkül) választ célpontot: így többet üt a
gyengébb páncélú ellenséges zsoldosokra, és ugyanaz az ütés ott ~2x annyi sebzést okoz.
(`tank_targeting="weak"`, ez az alapértelmezés; a `tank_damage_multiplier` 1.0.) Ez nem bizonyított, a
jelentésekből nem látszik, melyik zsoldos ütött. Ehhez az illesztéshez `main_multiplier=10` tartozik.

**Megerősítés 75 jelentésen, 14 ellenfél-csapattal:** Aveloca tankja a szimulációhoz képest
1,16-szor annyit sebez, a többi zsoldosa 0,85-ször; a relatív többlet **+37%**, 14 ellenfélből 11-nél
látszik. Az ellenfelek csapataiban is mindenhol kiugrik egy zsoldos (átlag 1,7x a többihez képest).
Az aréna-körmérkőzéses tank-tipp a csapatok 8/14-ében találta el ezt a zsoldost (az "első helyen
álló zsoldos" 10/14-ben), ezért a tankot lehetőleg meg kell adni (`roles=`).

**Ismert tankok (játékostól kapott adat, a jelentésekkel egyezik):** a védő zsoldos Klaus, Goofy, AKKILES,
Maccabi_TelAviv és Aveloca esetében az első (Aveloca: az utolsó, 4.), Durhamnál a harmadik zsoldos. A
jelentésekben pontosan ezek a zsoldosok sebeznek kiugróan. A szerepet a játék **nem számolja**: a játékos
állítja be, és a profiloldal tippjéből (`charmercpic dollN`) olvasható ki, ahogy az eredeti szimulátor és a
`fetch.py` is csinálja. Az "erősebb zsoldos = tank" tipp csak 3/9 esetben egyezett, ezért a `pick_tank`
csak jelentés-elemzésnél kell, ahol nincs profil. A 6 ismert tankú csapaton a `tank_targeting="weak"`,
`main_multiplier=10` illeszkedik legjobban (tank 0,93, többi zsoldos 0,89, pontszám 1,02x).

**Célzás szerepek szerint (24 jelentés egyedi nevű zsoldosokkal, Aveloca csapata):** az első ütés célpontja az
ellenfél főkarakterére: támadó zsoldosok 93-96%, gyógyító 97%, **tank zsoldos 54%** (45% -> 60% a harc
során), **a főkarakter** 27% (1-10. kör) -> 78% -> 89% -> 94%. A tank a maradék célpontokat a veszély
értékek szerint választja. Ezt építi a `TurmaRules.role_targeting` (alapértelmezett): `dps_main_prob=0.96`,
`tank_main_mult=2.2`, `main_focus`. A 125 jelentésre a szimulált/valós sebzés a tankra 0,99, a többi
zsoldosra 0,96 (a régi statikus súlyozással 0,91 és 0,89), a pontszám 1,01x.

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
