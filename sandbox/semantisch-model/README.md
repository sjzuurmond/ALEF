# Core semantic model for rule models in legislation

A generic, engine-agnostic semantic model for executable legislation, designed to be
**interpreted directly** (the next step). It is object/instance-centric — entities,
relations, universally-quantified rules, object-graph actions — because that matches
how law is formulated. It was derived from ALEF's Regelspraak language family
(extracted from the MPS `structure.mps` models in this repository), then recast in
generic English terminology with a single clean expression IR. It is a theoretical
trial: related to, but deliberately not identical to,
[RegelRecht RFC-001](https://regelrecht.rijks.app/rfcs/rfc-001), whose clean parts
(operation enum, `type_spec`, value-as-output) it borrows.

## Files

| File | What it is |
|---|---|
| [`core-model.schema.json`](./core-model.schema.json) | The model — JSON Schema (Draft 2020-12) |
| [`evaluation-trace.schema.json`](./evaluation-trace.schema.json) | Runtime values of one test run; what an interpreter produces |
| [`core-model.example.json`](./core-model.example.json) | BMI example (from `solutions/Beslistabellen_Test`) |
| [`core-model.example.trace.json`](./core-model.example.trace.json) | Trace of one BMI test case, paired with the example |
| [`core-model.temporal-example.json`](./core-model.temporal-example.json) | Temporal example: income timeline + mid-year parameter change |

## Design principles

1. **Object-centric.** A `DataModel` declares `EntityType`s (attributes +
   boolean characteristics), `RelationType`s with roles, `Domain`s, `Dimension`s,
   `UnitSystem`s and `Parameter`s. Rules navigate this model; they do not read flat
   fields.
2. **A rule = versioned ∀-quantified condition → action.** `Rule` → `RuleVersion`
   (each valid for a `Period`) → optional `Condition` + exactly one `Action`. The rule
   implicitly ranges over *every* instance of its subject (`universal` anchor;
   repeated use is a `reference` to its id). No statement lists, no loops, no call
   stack; sequencing exists only at `RuleGroup` level (`recursive` = iterate to a
   fixpoint).
3. **Eight action kinds**, all reducible to reads/writes of the object graph:
   `assignment` (with `initial` = only-if-empty), `setCharacteristic`, `createObject`,
   `createFact`, `consistencyCheck` (attaches a verdict, writes nothing),
   `distribution` (divide an amount over recipients), `dayTypeDefinition`,
   `timelineStart`.
4. **One expression IR.** Scalar arithmetic, bounding, rounding, abs/sqrt/power are a
   single `operation` node with an `op` enum. Surface constructs *desugar* into it
   (see below). Parentheses do not exist: the operand tree encodes grouping.
5. **A value is a function of context; time is a dimension.** A `Dimension` is either
   `labels` (per bracket, per region) or `time` (granularity + start). A
   timeline-valued attribute is simply a `dimensioned` type over a time dimension —
   there is no separate timeline type. Per-instance/relationship variation is *not* a
   dimension (it lives in the object graph via navigation); state-dependent variation
   is a condition. Constants vary over time at two levels: `ParameterSet.validity`
   (which set applies) and the `timeVarying` literal (variation within a set).
6. **Containment vs reference.** Nesting is the tree you serialize; string reference
   fields (`to`, name lookups) are cross-references. Any node that *evaluates to a
   value* (selections, expressions, conditions, variables) may carry an optional
   stable `id` — the hook for references, annotations and runtime values. Literals
   (value = themselves) and actions (effects, not values) get no id.
7. **Everything non-semantic is an overlay.** Comments, source-law references,
   metatags and the natural-language rendering live in `annotations`, a side table
   keyed by node id — never inside the executable tree.

## Evaluation semantics (what an interpreter does)

1. **Facts in** — a test case or service call creates instances and fills input slots.
2. **Time selects the law** — the calculation date picks the valid `RuleVersion` of
   every rule and the valid `ParameterSet`; reading a timeline-valued slot samples a
   piecewise-constant function at a date (or over a period, for `temporal` operators
   like `total` and `timeProportional`).
3. **Rules fire per instance** — for every instance of the subject type: bind
   `variables`, evaluate the `condition`, and if it holds execute the `action`.
4. **Actions derive new facts**, which may enable other rules; a `recursive`
   rule group repeats until nothing fires anymore (fixpoint).
5. **Results are read out** through the same navigation paths; `consistencyCheck`
   verdicts and fired-rule bookkeeping go to the trace.

## Interpretation pairing: rendering + trace

The `annotations[id].rendering` is a **segment tree**: literal text segments and node
segments with an `origin` (the node whose value belongs there) and optional `target`
(the definition it refers to). An interpreter writes an
[`evaluation-trace`](./evaluation-trace.schema.json) — `values[instance][nodeId]` —
and a UI walks the segments, injecting each origin's value:

> The bmi **[20.0]** of a Person equals the weight of the Person **[80 kg]** divided
> by (the height of the Person **[2.00 m]** times the height of the Person
> **[2.00 m]**), rounded to 1 decimal.

Trace value kinds mirror what slots can hold, including `timeline`
(`periods: [{from, to, value}]`) for time-dimensioned attributes.

## Normalization (what does *not* get its own construct)

| Surface construct | Normalizes to |
|---|---|
| Decision table | ordinary rules (one per row) |
| Parentheses | the operand tree |
| "x reduced by y, not below zero" | `max(subtract(x, y), 0)` |
| "p% of x" | `multiply(divide(p, 100), x)` |
| Conditional expression | `conditional` (case/when-then-else) |

## Origin: ALEF ↔ core terminology

`ObjectType/Attribuut/Kenmerk` → `EntityType/Attribute/Characteristic` ·
`FeitType/Rol` → `RelationType/Role` · `Regelgroep/Regel/RegelVersie` →
`RuleGroup/Rule/RuleVersion` · `Gelijkstelling/Initialisatie` → `assignment` ·
`KenmerkToekenning/ObjectCreatie/FeitCreatie/ConsistentieRegel/Verdeling` →
`setCharacteristic/createObject/createFact/consistencyCheck/distribution` ·
`Selectie/OnderwerpRef/UnivOnderwerp` → `selection/reference/universal` ·
`EnkeleVoorwaarde/SamengesteldeVoorwaarde` → `simple/compound` condition ·
`Plus…Machtsverheffen/Afronden/Begrensd` → one `operation` ·
`Tijdsdimensie/Tijdlijn` → `Dimension(kind: time)` · `TijdsafhankelijkeLiteral` →
`timeVarying` literal · `Geldigheidsperiode` → `Period`.

## Known gaps (for real cross-system interchange)

Deliberately not modeled — neither ALEF nor this core has them; RegelRecht does, and
they are the extension direction if the core must span systems: cross-law delegation
(`open_terms`/`implements`), a global reference URI scheme
(`regelrecht://law/output#field`), legal-effect classification
(`legal_character`, `competent_authority`), lex-specialis overrides across laws,
the official law text as a co-equal artifact, and outputs as public endpoints.

## Validate

```bash
pip install jsonschema
python3 - <<'PY'
import json
from jsonschema import Draft202012Validator as V
D = 'sandbox/semantisch-model/'
schema = json.load(open(D + 'core-model.schema.json'))
trace_schema = json.load(open(D + 'evaluation-trace.schema.json'))
for s in (schema, trace_schema): V.check_schema(s)
for sch, ex in [(schema, 'core-model.example.json'),
                (schema, 'core-model.temporal-example.json'),
                (trace_schema, 'core-model.example.trace.json')]:
    errs = list(V(sch).iter_errors(json.load(open(D + ex))))
    print(ex, 'VALID' if not errs else f'{len(errs)} error(s)')
PY
```

Semantic invariants JSON Schema cannot express (check with a linter): every
`reference.to`, rendering `origin`/`target`, annotation key and trace node id must
resolve to an `id` (or `universal` anchor) in the model; trace `entityType`s must
exist in the data model.

## Next step

An **interpreter** over this core: load a model + test case, run the evaluation
cycle above, emit an `evaluation-trace`, and render the rule text with injected
values. After that, an AST → core transformer from the MPS models would replace the
hand-written examples.
