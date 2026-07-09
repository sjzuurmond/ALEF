# Object-centric rule interchange core (theoretical trial)

## Waarom

Dit is een verkenning van een **generieke "core"** voor uitvoerbare wetgeving die
tussen verschillende regelsystemen uitgewisseld kan worden — niet alleen ALEF.
Uitgangspunt: neem **ALEF's object/instantie-georiënteerde vorm** als basis (die past
bij hoe wetgeving is geformuleerd: objecttypen, rollen, regels die over *elke*
instantie gelden, en acties die de objectgraaf muteren), maar giet die in **generieke,
Engelse terminologie** en een **schone, engine-agnostische expressie-IR**. Waar ALEF
oppervlakte-specifieke constructies heeft (aparte `PlusExpressie`/`MinusExpressie`,
`Haakjes`, Nederlandse namen), gebruikt de core één generieke `operation`-node en laat
haakjes weg (de operandenboom groepeert al).

Dit is een theoretische proef; het hoeft **niet** één-op-één te matchen met
RegelRecht RFC-001. Wel leent het de schone stukken daaruit (operation-enum,
`type_spec` met unit/precision/min/max, temporele spec, output-als-waarde).

- Schema: **[`core-model.schema.json`](./core-model.schema.json)** (Draft 2020-12).
- Voorbeeld: **[`core-model.example.json`](./core-model.example.json)** — het
  BMI-domein in de core; valideert.

```bash
python3 -c "import json;from jsonschema import Draft202012Validator as V; \
s=json.load(open('docs/architectuur/core-model.schema.json')); \
e=json.load(open('docs/architectuur/core-model.example.json')); \
V.check_schema(s); print('VALID' if not list(V(s).iter_errors(e)) else 'INVALID')"
```

## Wat blijft (ALEF's kracht) en wat verandert (schoner/generiek)

**Behouden — object/instantie-centrisch (hier is ALEF rijker dan een veldmodel):**

- Een echt **datamodel**: `EntityType` met `Attribute`/`Characteristic`, `RelationType`
  met `Role`s, `Domain`, `Dimension`, `Unit`/`UnitSystem`, `Parameter`.
- **Regels over elke instantie**: `Rule` → `RuleVersion` (geldig per periode), met een
  impliciet universeel onderwerp (`universal` anker) — de ∀-kwantificatie.
- De acht **objectgraaf-acties**: `assignment`, `setCharacteristic`, `createObject`,
  `createFact`, `consistencyCheck`, `distribution`, `dayTypeDefinition`,
  `timelineStart`.
- **Navigatie** door het model: `selection` ("the X of the Y"), `subselection`,
  aggregatie *over instanties*.
- **Tijdlijnen** en dimensies.

**Veranderd — generiek en schoon:**

- **Expressie-IR**: alle scalaire rekenkunde, begrenzing, afronding, abs/sqrt, macht en
  percentage-van vouwen samen in één `operation`-node met een `op`-enum
  (`add, subtract, multiply, divide, power, min, max, abs, sqrt, round, ceil, floor,
  percentageOf`). Geen aparte `Plus/Minus/...`-concepten.
- **Haakjes weg**: de operandenboom codeert groepering; `Haakjes` was AST-residu.
- **Desugaring**: `VerminderdMet` → `max(subtract(a,b), 0)`; een beslistabel →
  gewone regels; een conditie-expressie → `conditional` (case/when-then-else, à la
  RegelRecht `IF`).
- **`type_spec`** op getallen (`unit`, `precision`, `min`, `max`) en een schone
  **`temporal`** spec op attributen (`period`/`pointInTime`, `periodType`,
  `reference`) — geleend van RegelRecht.
- **Engelse terminologie** overal; discriminator is `kind` (niet `soort`).

De annotatie-overlay (commentaar, bron, metatags, **rendering met origin/target**) en
het idee van een losse evaluatie-trace blijven: waarde-injectie ("the bmi **[20.0]**")
werkt identiek, nu met Engelse rendering-segmenten.

## ALEF → core terminologie

| ALEF (`soort`) | Core (`kind`) |
|---|---|
| `Objecttype` / `Attribuut` / `Kenmerk` | `EntityType` / `Attribute` / `Characteristic` |
| `FeitType` / `Rol` | `RelationType` / `Role` |
| `Domein` / `Dimensie` / `Eenheid` | `Domain` / `Dimension` / `Unit` |
| `Regelgroep` / `Regel` / `RegelVersie` | `RuleGroup` / `Rule` / `RuleVersion` |
| `Gelijkstelling` / `Initialisatie` | `assignment` (`initial: true`) |
| `KenmerkToekenning` / `ObjectCreatie` / `FeitCreatie` | `setCharacteristic` / `createObject` / `createFact` |
| `ConsistentieRegel` / `Verdeling` | `consistencyCheck` / `distribution` |
| `Selectie` / `OnderwerpRef` / `UnivOnderwerp` | `selection` / `reference` / `universal` |
| `EnkeleVoorwaarde` / `SamengesteldeVoorwaarde` | `simple` / `compound` condition |
| `Vergelijking` / `IsGevuld` / `Elfproef` | `comparison` / `isFilled` / `checksumEleven` |
| `PlusExpressie` … `Machtsverheffen`, `Afronden`, `Begrensd` | één `operation` met `op` |
| `Aggregatie` / `TekstExpressie` | `aggregation` / `textConcat` |
| `ConditioneleExpressie` | `conditional` |
| `Geldigheidsperiode` | `Period` (validity) |

## Wat ALEF (en dus deze core) mist — t.o.v. interchange/RegelRecht

Bewust genoteerd, want dit is waar het ALEF-model *niet* in voorziet en een echte
cross-systeem-interchange wél nodig heeft:

1. **Cross-wet / cross-systeem delegatie.** RegelRecht heeft `open_terms` (een hogere
   wet laat een term open) en `implements` (een lagere regeling vult die in) — een
   IoC-patroon tussen wetten. ALEF modelleert één samenhangend regelmodel; er is geen
   eerstteklas mechanisme voor "deze term wordt elders/door een andere autoriteit
   ingevuld".
2. **Globaal referentieschema.** RegelRecht's `regelrecht://{law}/{output}#{field}`
   adresseert outputs van *andere* systemen/wetten. ALEF-verwijzingen (en onze
   node-ids) zijn model-lokaal; er is geen URI-schema om naar een externe bron te
   wijzen.
3. **Rechtsgevolg-classificatie.** RegelRecht's `produces` (`legal_character`:
   BESCHIKKING/TOETS/…, `decision_type`), `competent_authority` en `procedure_id`
   (AWB). ALEF kent bron-traceerbaarheid en metatags, maar classificeert niet welk
   *rechtsgevolg* een regel oplevert of welke autoriteit bevoegd is.
4. **Lex specialis / overrides tussen wetten.** RegelRecht's `overrides` vervangt op
   artikelniveau outputs van andere wetten. ALEF heeft regelversies (temporeel) en
   regelgroepen, maar geen cross-wet voorrang/override-mechanisme.
5. **Wettekst naast de regels.** RegelRecht bewaart de officiële artikeltekst en de
   machine-regels in één bestand (`bwb_id`, `eli`, `celex`, artikelnummering). ALEF
   verwijst naar de bron, maar neemt de canonieke wettekst niet als gelijkwaardig
   artefact op.
6. **Publieke output-endpoints als contract.** RegelRecht behandelt outputs als
   benoemde publieke endpoints. ALEF heeft hiervoor `servicespraak`, maar dat is een
   losse laag; het kern-regelmodel kent het niet.

Omgekeerd is ALEF juist **rijker** in de kernlogica: objectcreatie/feitcreatie,
verdeling, ∀-kwantificatie over instanties, dimensies en volledige tijdlijnen — dingen
die RegelRecht's vlakke veldmodel niet heeft. De core hierboven houdt die rijkdom vast;
de zes punten hierboven zijn de logische *uitbreidingsrichting* als je de core echt
cross-systeem wilt maken.

## Verhouding tot de andere documenten

Dit is de **generieke core-laag** van de twee-lagen-opzet. De ALEF-specifieke
[`semantisch-model.schema.json`](./semantisch-model.schema.json) is dan de
**sugar-laag** (Nederlandse Regelspraak-oppervlakte) die *naar* deze core afbeeldt via
de mapping hierboven. De evaluatie-trace en rendering werken op beide lagen, gekoppeld
op node-id.
