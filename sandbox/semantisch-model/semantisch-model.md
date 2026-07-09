# Semantisch model van de spraken

## Doel

Dit document legt vast wat de ALEF-spraken (regelspraak, gegevensspraak, testspraak,
beslistabelspraak, servicespraak en de `.tijd`-varianten) betekenen, losgekoppeld van
alles wat specifiek is aan JetBrains MPS of de projectionele editor. Het is bedoeld
als opstap naar een **interpreteerbaar semantisch (regel)model**: een representatie
van een regelmodel/regelservice — een geheel aan regels en gegevens waarmee wetgeving
wordt uitgevoerd, dat gezamenlijk één of meerdere beslissingen/berekeningen maakt —
die je kunt evalueren zonder de MPS-AST, de generator-templates of gegenereerde Java
nodig te hebben.

De inhoud is geëxtraheerd uit de `structure.mps`-modellen van de talen in deze repo
(MPS 2025.1).

## Drie bevindingen

1. **Er is geen "Merlin-AST".** De `merlin*`-talen (`merlinRegels`, `merlinGegevens`,
   `merlinService`, …) hebben vrijwel lege structuurmodellen. Het zijn
   generator-only talen: MPS-templates die de spraak-ASTs direct omzetten naar Java
   (BaseLanguage), draaiend tegen de `AlefJava`-runtime (`alefRuntime`, `merlin`).
   De operationele semantiek zit vandaag dus in generator-templates + Java, niet in
   een tussenliggend model — een schoon interpreteerbaar model bestaat nog niet.
2. **Er bestaat al een interpretatielaag.** De taal `interpreter.debug` definieert de
   `L*`-interfaces — `LClass`, `LSlot`, `LReference`, `LValue`, `LAction`,
   `LConstruction`, `LArgument` — die door concepten in alle spraken worden
   geïmplementeerd. Dit is in feite een eerste opzet van een objecten-met-slots /
   acties-die-slots-lezen-en-schrijven-model, en een goede sanity-check voor een
   nieuw semantisch model.
3. **Niet-semantiek is al gemarkeerd.** Concepten zonder uitvoeringsbetekenis
   implementeren `Semantiekloos` ("semantiek-loos"), `IForGenerationOnly`,
   `ICannotBeAddedByUser`, `LDummy*` (editor-placeholders) of `ITaalkundig`
   (Nederlandse grammatica-weergave). Dit is een kant-en-klaar filter.

## Taalkaart

| Taal | Concepten | Rol | Locatie |
|---|---:|---|---|
| `regelspraak` | 156 | Regels-CNL — het hart | `languages/regelspraak` |
| `gegevensspraak` | 118 | Datamodel (objecten, types, eenheden, dimensies, parameters) | `languages/objecten` ⚠️ map ≠ taalnaam |
| `testspraak` | 72 | Tests & verwachtingen | `languages/validatie` ⚠️ map ≠ taalnaam |
| `servicespraak` | 69 | Servicegrens: berichtmappings, restricties (marshalling, geen regelsemantiek) | `languages/servicespraak` |
| `beslistabelspraak` | 31 | Beslistabellen — alternatieve surface-syntax voor regels | `languages/beslistabelspraak` |
| `besturingspraak` | 18 | Flows/orkestratie (Flow is deprecated volgens de docs) | `languages/besturingspraak` |
| `bronspraak` | 18 | Traceerbaarheid naar wettekst (JuriConnect), metatags — herkomst | `languages/bronspraak` |
| `vrijspraak` | 15 | Vrije gecontroleerde zinnen, geen uitvoeringssemantiek | `languages/vrijspraak` |
| `*.tijd` | ~60 | Tijdlaag: tijdlijnen, periodes, tijdsafhankelijke expressies — kernsemantiek | `languages/*.tijd` |
| `interpreter.debug` | 38 | De `L*`-interpretatie-interfaces + `Debug*`-runtime-spiegels | `languages/interpreter.debug` |
| `merlin*` | ≈0 | Generator-only talen (templates naar Java) | `languages/merlin*` |

## Het kernmodel

Het regelmodel valt uiteen in vier vocabulaires en twee relaties.

### 1. Objectschema (gegevensspraak)

- **`ObjectModel`** (root) ▸ `ObjectType` / `ObjectExtensie` — de "dingen".
  - `ObjectType` ▸ `Attribuut` (getypeerd) en `Kenmerk` (boolean).
  - `FeitType` ▸ `Rol` [1..n] → `ObjectType` — relaties tussen objecttypes.
- **Typesysteem**: `DataType` = `NumeriekType` | `PercentageType` | `DatumTijdType` |
  `BooleanType` | `TekstType` | `EnumeratieType` | `DomeinType` (→ `Domein`) |
  `GedimensioneerdType`.
- **Dimensies**: `Dimensie` ▸ `Label` [0..n] — attributen kunnen arrays zijn over
  benoemde dimensies (bv. per jaar, per schijf), gefilterd met `DimensieFilter`.
- **Eenheden**: volledige eenhedenalgebra — `Eenheid` ▸ `EenheidMacht`
  (basis-eenheid tot een macht), `EenheidSysteem`, `Omrekenfactor`.
- **Parameters**: `Parameter` ▸ type; waarden apart in `Parameterset` (root) ▸
  `geldig: Geldigheidsperiode` ▸ `Parametertoekenning` → wetsconstanten,
  geldig per periode.
- De expressiebasis (`Expressie`, `Waarde`, `Literal`) staat hier, niet in
  regelspraak — gedeelde basis voor alle spraken.

### 2. Regels (regelspraak)

- **`Regelgroep`** (root) ▸ `Regel` ▸ `RegelVersie` [1..n] ▸ `geldig:
  Geldigheidsperiode` ▸ `statement: ActieIndienVoorwaarde`.
- Elke regelversie = **onderwerp (impliciet universeel gekwantificeerd) + optionele
  conditie + één actie**. `IUnivQuantifier` markeert dit iteratiegedrag.
- **Condities**: `EnkeleVoorwaarde` (quant? · expr · predicaat) en
  `SamengesteldeVoorwaarde` (en/of/n-van-m nesting via `SamengesteldPredicaat`).
  Predicaten: `Vergelijking`, `IsGevuld`/`IsLeeg`, `RolOfKenmerkCheck`,
  `IsDagsoort`, `ElfproefCheck` (BSN-elfproef), …
- **Navigatie**: `Selectie` (structuur op interface `ISelectie`) = `object:
  OnderwerpExpressie` + `selector: Selector` → `Attribuut`/`Kenmerk`/`Rol`. Dit is
  het enige mechanisme waarmee regels het schema aanraken (zowel lezen als, via
  `Gelijkstelling.links`, schrijven).
- **Expressies**: ~20 knooptypes — rekenkundig (`ArithmetischeExpressie` met
  `links`/`rechts`), `Afronden`, `BegrensdeExpressie` (grenzen), `Aggregatie`/
  `DimensieAggregatie`, tekst, datumfuncties, `ParameterRef`, `VariabeleRef`.

### 3. Beslistabellen normaliseren naar regels (beslistabelspraak)

`Beslistabel` **is** een `AbstracteRegel`. `BeslistabelVersie` bevat naast condities/
conclusies/rijen ook `regels: Regel [0..n]` — de tabel materialiseert in gewone
`Regel`s. Voor het interpreteerbare model is **geen apart tabelconstruct nodig**;
tabellen zijn surface-syntax.

### 4. Tijd (`.tijd`-laag)

Slots kunnen tijdlijn-waardig zijn: stuksgewijs-constante functies van tijd.

- `TijdlijnDefinitie` ▸ `Tijdlijn` ▸ `granulariteit` (aantal × eenheid) ▸
  `startpunt`.
- `TijdsafhankelijkeLiteral` ▸ `LiteralMetPeriode` [1..n] (waarde + van/tot).
- Tijdsoperatoren: `Tijdsevenredig`, `TijdsduurDat`, `Periode`/`MultiPeriode`,
  `ConditioneleExpressie`.
- Gespiegeld in de runtime door `interpreter.timed.debug`
  (`DebugTimed`, `DebugPeriod`, `TAction`).

### 5. Tests (testspraak)

Zelfde vocabulaire, datazijde: `TestSet` (root) ▸ `TestGeval` ▸ `Instantie` (→type)
▸ `EigenschapToekenning` (input) en `UitvoerVoorspelling`/`ConsistentieVoorspelling`
(verwachte output) — instanties en toekenningen in, voorspellingen uit.

## De acht actiesoorten

Alle effecten in de taal herleiden tot acht `Actie`-varianten:

1. **`Gelijkstelling`** — toekenning/vergelijking (`Initialisatie` is een subtype)
2. **`KenmerkToekenning`** — kenmerk toekennen aan een object
3. **`ObjectCreatie`** — nieuw object aanmaken
4. **`FeitCreatie`** — nieuwe relatie (feit) aanmaken
5. **`ConsistentieRegel`** — consistentie beoordelen (schrijft geen waarde, hangt een oordeel op)
6. **`Verdeling`** — bedrag verdelen over ontvangers (met sorteercriterium, rato, afronding)
7. **`DagsoortDefinitie`** — dagsoort definiëren
8. **`StartpuntBepaling`** *(regelspraak.tijd)* — startpunt van een tijdlijn bepalen

## Het versioning-patroon, één keer

Eén structureel idioom draagt alle wetswijziging-in-de-tijd. Model het één keer, hergebruik het overal:

| Patroon | Gebruikt door |
|---|---|
| `X ▸ versie: XVersie [1..n] ▸ geldig: Geldigheidsperiode` | `Regel` → `RegelVersie` · `Beslistabel` → `BeslistabelVersie` · `RegelgroepConditie` → `RegelgroepConditieVersie` · `Flow` → `FlowVersie` |
| `X ▸ geldig: Geldigheidsperiode` (direct) | `Parameterset` · `TestSet` |

## Evaluatiecyclus

De uitvoeringssemantiek die de merlin-generatoren vandaag in Java coderen, samengevat:

1. **Feiten in** — een servicebericht of testcase construeert instanties van het
   objectschema en vult hun invoerslots.
2. **Tijdselectie** — de *rekendatum* bepaalt de geldige `RegelVersie` van elke
   regel en de geldige `Parameterset`, via hetzelfde `geldig`-patroon overal. Een
   tijdlijn-waardig slot lezen betekent samplen van een stuksgewijs-constante
   functie op een datum (of over een periode, voor operatoren als `TijdsduurDat`
   en `Tijdsevenredig`).
3. **Regels vuren per instantie** — elke regelversie wordt geëvalueerd voor iedere
   instantie van haar onderwerptype; lokale `Variabele`s worden gebonden, de
   conditieboom wordt geëvalueerd, en indien waar voert de ene actie uit.
4. **Acties leiden nieuwe feiten af**, die andere regels toepasbaar kunnen maken —
   een `Regelgroep` gemarkeerd als `recursief` herhaalt tot een fixpoint.
   Consistentieregels schrijven geen waarde; ze hangen een oordeel op.
5. **Uitvoer** wordt gelezen via dezelfde navigatiepaden: uitvoerberichtmappings
   voor de Beslisservice, `UitvoerVoorspelling`-vergelijkingen voor tests.

## Keep/drop-filter voor cross-cutting interfaces

| Behouden — semantisch | Weglaten — MPS/tooling |
|---|---|
| `Typed`, `Expressie`, `Waarde`, `Slot`, `Onderwerp`, `Eigenschap` | `ScopeProvider`, `ITypeExpector`, `ISmartReferent` — editor/typesysteem-machinerie |
| `IVersie`, `IPeriodeProvider`, `IMetTijdlijn`, `ITijdsafhankelijk` — versionering & tijd | `ITaalkundig`, `Naamwoord`/`INoun`, `IVerb` — Nederlandse grammatica-weergave |
| `IUnivQuantifier`, `IQuantifier` — impliciete iteratie over instanties | `Semantiekloos`, `IForGenerationOnly`, `ICannotBeAddedByUser`, `LDummy*` |
| `IDimensie*`, `EenheidProvider`, `IEenheidTransformer` — dimensies & eenheden | `ICoverageArc`, `LeafCoverageArc` — testdekking-boekhouding |
| `LClass`/`LSlot`/`LReference`/`LValue`/`LAction`/`LConstruction`/`LArgument` — de interpretatie-abstractie zelf | `ICanHaveBron`, `IHaveMetatags`, `ICanHaveComment` — herkomst: bewaren als optionele metadata, geen kern |

**Containment vs. referentie**: nesting (▸) in de structuurmodellen is de boom die
je serialiseert; cross-referenties (→, bv. `AttribuutSelector → Attribuut`,
`Parametertoekenning → Parameter`) zijn precies de plekken waar een geserialiseerd
semantisch model stabiele identifiers nodig heeft.

## Het schema

Het kernmodel is uitgewerkt tot een concrete, valideerbare schemadefinitie:

- **[`semantisch-model.schema.json`](./semantisch-model.schema.json)** — JSON Schema
  (Draft 2020-12) van het interpreteerbare regelmodel. Getagde unions (`soort`)
  voor datatypes, acties, condities, predicaten, navigatiepaden en expressies;
  containment als nesting, cross-references als string-verwijzingen
  (`Objecttype.naam`, `Domein.naam`, `Parameter.naam`, `Universeel.id`).
- **[`voorbeeld-bmi.json`](./voorbeeld-bmi.json)** — een volledig uitgewerkte
  instantie: het BMI-domein uit
  `solutions/Beslistabellen_Test/models/Beslistabellen_Test.BMI_tabel.*`
  (objectmodel `Persoon`, de regel `bmi = afronden(gewicht / (lengte × lengte), 1)`,
  een `Initialisatie`, en de beslistabel genormaliseerd naar regels).

Het voorbeeld valideert tegen het schema; de evaluatie-trace (zie *Waarden tonen*
hieronder) valideert tegen zijn schema en verwijst kruislings naar het model. Snel te
controleren:

```bash
pip install jsonschema
python3 - <<'PY'
import json
from jsonschema import Draft202012Validator as V
D = 'sandbox/semantisch-model/'
m  = json.load(open(D+'semantisch-model.schema.json'))
mi = json.load(open(D+'voorbeeld-bmi.json'))
t  = json.load(open(D+'evaluatie-trace.schema.json'))
ti = json.load(open(D+'voorbeeld-bmi.trace.json'))
for s in (m, t): V.check_schema(s)
for sch, inst, naam in [(m, mi, 'model'), (t, ti, 'trace')]:
    errs = list(V(sch).iter_errors(inst))
    print(naam, "VALID" if not errs else f"{len(errs)} fout(en)")

# waarde-injectie: render de zin met waarden uit de trace
vals = ti['waarden']['persoon#Jan']
def fmt(w): return w['waarde'] + (f" {w['eenheid']}" if w.get('eenheid') else '') if w['soort'] in ('getal','percentage') else str(w.get('waarde'))
out = []
for s in mi['annotaties']['regel.bmi.v1']['rendering']['segments']:
    if 'origin' in s:
        out.append(s.get('text',''))
        if s['origin'] in vals: out.append(f" [{fmt(vals[s['origin']])}]")
    else: out.append(s['text'])
print(''.join(out))
PY
```

### Ontwerpkeuzes

- **Beslistabellen** krijgen geen eigen construct: ze normaliseren naar gewone
  `Regel`s (zie de gegenereerde `regels: Regel [0..n]` in `BeslistabelVersie`).
- **Universele kwantificatie** is expliciet gemaakt via het `universeel`-anker met
  een optioneel `id`; herhaald gebruik van hetzelfde onderwerp binnen één regel is
  een `referentie` naar dat `id` (een echte cross-reference, precies zoals in de AST
  `OnderwerpRef` terugverwijst).
- **Getallen** zijn strings (bv. `"18,5"`) om decimale precisie en de Nederlandse
  komma-notatie te behouden.
- **`id` op alles wat een waarde oplevert.** Elke node die tot een waarde evalueert
  mag een optioneel `id` dragen, zodat de geëvalueerde waarde per testrun te tonen is
  (rendering `origin` + evaluatie-trace). Dat is de hele `Expressie`-familie
  (`Selectie`, `Rekenkundig`, `Afronden`, `Aggregatie`, `ParameterRef`, … en de
  navigatie-ankers), plus de boolean-opleverende `Conditie`/`Predicaat` (ALEF kleurt
  die groen/rood) en gebonden `Variabele`n. Deze verzameling valt samen met de
  `L*`/`LValue`-laag die `interpreter.debug` volgt. Bewust géén `id`: `Literal`s (hun
  waarde is zichzelf) en `Actie`s (effecten, geen waarde; het resultaat van een
  `Gelijkstelling` is de waarde van zijn `doel`-`Selectie`, en consistentie-oordelen
  hangen aan het regel-id). Id's zijn optioneel: ken ze alleen toe waar je een
  verwijzing of waarde-uitlezing nodig hebt.
- **Tijd is een dimensie.** Een waarde is een functie van context; tijd is één
  context-as. In plaats van een apart tijdlijn-type is tijd gemodelleerd als
  `Dimensie` met `soort: "tijd"` (granulariteit + startpunt) — precies zoals ALEF's
  eigen `Tijdsdimensie : IDimensie`. Een **tijdlijn-waardig slot** is daarmee gewoon
  een `gedimensioneerd` attribuut over een tijddimensie; de tijd-operatoren
  (`Totaal`, `Tijdsevenredig`, `Tijdsoperator`) hebben nu een typeerbare basis.
  Variatie *per instantie/relatie* is géén dimensie maar loopt via de objectgraaf
  (navigatie); variatie *per toestand* via condities. Een constante die per periode
  verschilt is een `tijdsafhankelijk`-literal — dus tijdvariatie kan op **twee**
  niveaus: de `Geldigheidsperiode` van een hele `Parameterset` én een
  `tijdsafhankelijk`-literal binnen één set. De evaluatie-trace draagt de uitkomst als
  `tijdlijn`-waarde (`perioden: [{van,tot,waarde}]`).
- Weggelaten: editor-scaffolding, Nederlandse grammatica (`ITaalkundig`),
  testdekking (`ICoverageArc`) en generatie-only helpers — conform het
  keep/drop-filter hierboven.

### Annotaties: een overlay-zijtabel

Commentaar, bronverwijzingen en metatags zijn in MPS geen kinderen in de
containment-boom maar **node-attributen** (`CommentAttribute`,
`BronVerwijzingAttribute`, `MetatagsAsAttribute`, alle `extends NodeAttribute`,
gebonden aan de marker-interfaces `ICanHaveComment` / `ICanHaveBron` /
`IHaveMetatags`). Een node-attribuut hangt *op identiteit* aan een node, los van de
child-structuur.

JSON kent geen attribuut-begrip (alleen key/value-properties). We modelleren dit
daarom als **overlay-zijtabel** in plaats van inline: een top-level `annotaties`,
gesleuteld op `NodeId`. Nodes krijgen alleen een `id` waar dat nodig is (als doel van
een cross-reference of als annotatiedoel). Dit houdt de uitvoerbare boom schoon en
komt exact overeen met hoe MPS attributen aanhangt.

Dezelfde overlay draagt de **linguïstische rendering-trace**. De `linguistics`-runtime
rendert de AST naar een `NodeRendering`-*boom* ("NodeRenderings vormen een
boomstructuur") waarin knopen een **origin** hebben (de node waar de tekst bij hoort,
`getOrigin()`) en soms een **target** (voor referentie-spans, de node waar de
verwijzing naartoe wijst, `getTarget()`). We modelleren dit als segmentenboom:
`rendering.segments` bevat letterlijke tekst-segmenten en node-segmenten met een
`origin` (waardedoel) en optioneel `target` (navigatiedoel). Zo levert de grammatica
per node de natuurlijke-taal-weergave terug (uitlegbaarheid richting juristen) zonder
de kern te vervuilen.

```jsonc
"annotaties": {
  "regel.bmi":    { "commentaar": "...", "bron": [ { "soort": "vrij", "wet": "...", "verwijzing": "art. 3, tweede lid" } ], "metatags": [ { "naam": "status", "waarde": "concept" } ] },
  "regel.bmi.v1": { "rendering": { "segments": [
    { "text": "De " },
    { "origin": "sel.bmi", "target": "at.persoon.bmi", "text": "bmi" },
    { "text": " van een Persoon is gelijk aan " },
    { "origin": "sel.gewicht", "text": "het gewicht van de Persoon" },
    { "text": " gedeeld door (...)." }
  ] } }
}
```

De overlay-sleutels en segment-`origin`/`target` moeten overeenkomen met een `id` in
het model. Dat is een semantische invariant die JSON Schema niet afdwingt; een kleine
linter controleert dat elke `referentie.naar`, `origin`, `target` en overlay-sleutel
oplost naar een bestaand id.

### Waarden tonen (evaluatie-trace)

De rendering-segmenten leveren het skelet voor een interpreter-UI zoals ALEF die zelf
heeft: tekst met de gebruikte waarden ertussen, bv. *de bmi **[20,0]** = het gewicht
**[80]** / (de lengte **[2,00]** × de lengte **[2,00]**)*. De waarden zelf horen niet
in het model of in de statische rendering — het zijn resultaten van het **evalueren**
van het model tegen één `TestGeval` (instantiedata + rekendatum), en dus gesleuteld op
`(instantie, node-id, rekendatum)`. Dat is een apart zijartefact:

- **[`evaluatie-trace.schema.json`](./evaluatie-trace.schema.json)** — JSON Schema van
  één testrun. `waarden[instantie][node-id]` = de geëvalueerde `Waarde` (getagde union:
  getal met optionele eenheid, tekst, boolean, enum, leeg, lijst, object-ref, en
  `tijdlijn` voor tijdlijn-waardige slots). Dit is de tegenhanger van de `Debug*`-laag
  (`interpreter.debug` / `interpreter.timed.debug`) die ALEF's eigen interpreter
  produceert; het paart met de rendering via node-id (de `origin`).
- **[`voorbeeld-bmi.trace.json`](./voorbeeld-bmi.trace.json)** — een uitgewerkte run
  (`Jan`, gewicht 80, lengte 2,00 → bmi 20,0 → Gezond gewicht).

Een UI loopt de segmenten af en injecteert per `origin` de waarde uit de gekozen run.
Uitgerekend levert dat exact:

> De bmi **[20,0]** van een Persoon is gelijk aan het gewicht van de Persoon **[80]**
> gedeeld door (de lengte van de Persoon **[2,00]** maal de lengte van de Persoon
> **[2,00]**), afgerond op 1 decimaal.

Waarde-injectie is dus ondersteund: het model draagt de identiteit (`id`) en de
rendering (`origin`/`target`), de trace draagt de waarden per instantie, en beide
paren op node-id. Zie het validatie-snippet hieronder, dat naast schema-validatie ook
de kruisverwijzingen tussen model, rendering en trace controleert en de zin met
waarden rendert.

### Dekking (gemeten tegen de solutions)

Om te sturen op wat er écht toe doet, telt
**[`dekking-scan.py`](./dekking-scan.py)** het gebruik van elk concept in alle 569
`solutions/**/*.mps`-modellen en verdeelt ze over drie emmers. Draaien:

```bash
python3 sandbox/semantisch-model/dekking-scan.py
```

Huidige uitkomst (569 modellen, 225 concepten, ~108k node-gebruiken):

| Emmer | Concepten | Gebruiken | Aandeel |
|---|---:|---:|---:|
| **Gedekt** door het schema | 160 | 95.188 | **87,8 %** |
| **Buiten scope / genormaliseerd** | 62 | 13.175 | 12,2 % |
| **Nog te doen** | 3 | 3 | 0,0 % |

*Buiten scope* is bewust: beslistabellen (`Bt*`) normaliseren naar gewone `Regel`s;
de servicegrens/berichten (`servicespraak`, service-tests) is marshalling, geen
regelsemantiek; en linguïstiek/opmaak (`Werkwoord`, `Koptekst`) hoort in de
annotatie-overlay, niet in de kern. *Nog te doen* is een verwaarloosbare staart van
3 concepten die elk één keer voorkomen (`ListType`, `MultiExpressie`,
`PredicaatMetTijdsbepaling`).

Op basis van deze scan is het schema uitgebreid met de veelgebruikte constructies die
eerst ontbraken: `Leeg`/`Rekendatum`/`Rekenjaar` (literals), `Concatenatie`, unaire
functies (`AbsoluteWaarde`, `Worteltrekken`), `PercentageVan`, `VerminderdMet`,
`EenheidConversie`, `DeDag`, `Totaal`, de tijd-`Periode`voorwaarde, `Regelstatus`
(is-afgevuurd/inconsistent), `IsNumeriekMetLengte` en `SorteerCriterium`.

### Volgende stap

Met 87,8 % concept-dekking is het schema klaar voor de echte test: een
**AST → semantisch-model transformer** die een `.mps`-model automatisch omzet naar
JSON conform dit schema, gevalideerd tegen meerdere solutions (niet alleen het
handmatige BMI-voorbeeld). De `Bt*`-normalisatie en de `.tijd`-details
(tijdlijn-waardige slots) zijn dan de eerste dingen om end-to-end te bewijzen.
Gebruik de `L*`-interfaces in `interpreter.debug` als sanity-check: zij markeren welke
concepten de huidige interpreter al als uitvoerbaar beschouwt.
