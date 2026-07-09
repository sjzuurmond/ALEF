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

Het voorbeeld valideert tegen het schema. Snel te controleren:

```bash
pip install jsonschema
python3 - <<'PY'
import json
from jsonschema import Draft202012Validator
schema = json.load(open('docs/architectuur/semantisch-model.schema.json'))
inst   = json.load(open('docs/architectuur/voorbeeld-bmi.json'))
Draft202012Validator.check_schema(schema)
errs = list(Draft202012Validator(schema).iter_errors(inst))
print("VALID" if not errs else f"{len(errs)} fout(en)")
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
- Weggelaten: editor-scaffolding, Nederlandse grammatica (`ITaalkundig`),
  testdekking (`ICoverageArc`) en generatie-only helpers — conform het
  keep/drop-filter hierboven.

### Volgende stap

Het schema dekt nu de kern-constructies (acht actiesoorten, condities/predicaten,
navigatie, ~een dozijn expressiesoorten, tijd-operatoren). Logische uitbreidingen:
de resterende expressie- en predicaatsoorten uit `regelspraak.structure` aanvullen,
de `.tijd`-laag (tijdlijn-waardige slots, periodes) verder uitmodelleren, en meer
solutions door de validator halen. Gebruik daarbij de `L*`-interfaces in
`interpreter.debug` als sanity-check: zij markeren welke concepten de huidige
interpreter al als uitvoerbaar beschouwt.
