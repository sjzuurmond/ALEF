# Code review — reference interpreter

Self-review of `interpreter.mjs` / `decimal.mjs` / `render.mjs` (state: first
committed version). Every confirmed finding below was **reproduced with a concrete
test case**, not just read from the code. Severity: 🔴 wrong results, 🟠 silent
misbehaviour or unusable construct, 🟡 quality/robustness.

## Confirmed defects (reproduced)

| # | Sev | Finding |
|---|-----|---------|
| 1 | 🔴 | **`uniqueness` semantics are wrong.** All selections' values are pooled into one `seen`-set, so (a) values of *different* attributes collide (`p1.a = 5`, `p2.b = 5` → false) and (b) the intended semantics — the *tuple* of selections per instance must be unique across instances — is not what's computed. Reproduced: two instances with unique `(a,b)` tuples judged non-unique. Fix: build one tuple per instance, compare tuples. |
| 2 | 🔴 | **Multi-period conditions silently pass.** `PeriodCondition.periods` (MultiPeriode) is ignored; a condition covering only 2030 evaluates `true` in 2026 because neither `from` nor `throughInclusive` is present at the top level. Silent wrong verdict — the worst failure mode. Fix: evaluate as OR over `periods`, or `unsupported()` until implemented. |
| 3 | 🟠 | **`quantifier` on compound conditions is silently ignored.** The schema allows it; the engine drops it. Reproduced: `quantifier: none` on an `and` had no effect. Fix: apply `quantified()` to sub-condition hits, or reject models that use it. |
| 4 | 🟠 | **Wrong arity is silently truncated.** `subtract(10, 3, 99)` returns `7` — the third operand vanishes. Same for `divide`, `power`; extra operands to `abs`/`sqrt` are ignored. Fix: validate arity per op (binary: exactly 2, unary: exactly 1) and throw. |
| 5 | 🟠 | **Non-date inputs to date functions produce silent `NaN`.** `dateDiff("hello", …)` yields `{kind:"number", value:"NaN"}` — which even *validates* against the trace schema (the trace's number value has no pattern). Fix: assert `kind === 'date'` on date arguments; also consider adding the decimal pattern to the trace schema's number value. |
| 6 | 🟠 | **`createObject` diverges in recursive groups.** No idempotence guard → a new instance per pass → guaranteed "no fixpoint after 250 passes". Merlin solves exactly this with its `constructionDone` bookkeeping in `MUniverse`. Fix: track per (ruleVersion, subject-instance) that creation already happened. |
| 7 | 🟡 | **`fired` accumulates duplicates across fixpoint passes.** 2 instances × 2 passes = 4 entries. Bloats the trace and misleads readers. Fix: dedupe on (ruleVersion, instance). |

## Defects found by reading (not separately reproduced)

| # | Sev | Finding |
|---|-----|---------|
| 8 | 🟠 | **`ruleStatus` referencing a `Rule.id` never matches** — `fired` stores version ids only; the `f.rule === c.rule` clause tests a field that is never written (dead code). A rule-level reference silently evaluates false. |
| 9 | 🟡 | **`num()` passes timelines through**, so a timeline reaching a scalar op fails deep inside `decimal.mjs` with `not a decimal: [object Object]` (via the `num(v).value ?? v` fallback in `operation`). Should fail fast: "timeline in scalar operation — use temporal.total". |
| 10 | 🟡 | **Role navigation ignores the relation type.** Matching is by role *name* across all relation types; a name collision navigates the wrong relation. Also `createObject`/`createFact` store `type: rel.name`, but `RelationType.name` is optional → `type: undefined`. |
| 11 | 🟡 | **Overlap is resolved by order, silently.** `versions.find(...)` picks the first valid version when validity periods overlap; parameter sets ditto. Overlap is a model error and should be reported. |
| 12 | 🟡 | **Unbound (subject-less) rules record trace values under `'(global)'`** — a key that is not a declared instance id, violating the documented invariant that trace keys resolve to instances. |
| 13 | 🟡 | **Empty-extent `all` quantifier returns false** (`total > 0 && hits === total`). Vacuous truth is a real semantic decision in law ("all children are minors" with zero children); this choice is undocumented and unverified against ALEF's Alle semantics. |
| 14 | 🟡 | **`distribution`: `sortCriteria` silently ignored; `maxClaim` excess is not redistributed** — in ALEF's Verdeling redistribution is the whole point of sort criteria + remainder. README says "basic", but silent-ignore contradicts the "deliberately unsupported = clear error" policy. |
| 15 | 🟡 | **Change detection is `JSON.stringify`-based** and therefore key-order sensitive; semantically equal writes can count as mutations, which can in principle prevent fixpoint detection. |
| 16 | 🟡 | **`findUniversal` takes the first `universal` in JSON property order** — assumes exactly one universal entity type per rule version; two types would make the subject arbitrary. Should validate the assumption. |
| 17 | 🟡 | **`decimal.sqrt` and non-integer `pow` fall back to floats**, weakening the "no floats for money" guarantee (documented in code, but worth flagging at the README level). |
| 18 | 🟡 | Minor: `percentage` values act as bare numbers in arithmetic (no /100 — consistent with the desugaring, but undocumented); aggregation takes the first item's unit without checking homogeneity; `esc()` in `index.html` doesn't escape `>`; unused `here` variable in `run-demo.mjs`; `stepsBetween` rounds weeks but truncates nothing else consistently. |

## Process finding (the biggest one)

**No committed test suite.** All verification so far lived in throw-away shell
commands. Every defect above was findable by systematic tests; the demo happened to
exercise only the happy paths of two examples. The probes used for this review
should be committed as a regression suite (`tests.mjs`, plain node, no framework:
run, assert, exit non-zero on failure) and extended per fix.

## What held up well

- One value representation shared by engine, trace and renderer — no conversions.
- Empty-value propagation through operations matches ALEF's lege-waarde behaviour.
- The exact-decimal core (BigInt fixed point) survived adversarial probing; the
  two earlier bugs (division scale, unit propagation) were caught before commit.
- Emitted traces validate against `evaluation-trace.schema.json`; browser/Node parity
  is real (verified in Chromium).

## Suggested order of work

1. Fix 🔴 1–2 (wrong verdicts) + add regression tests.
2. Fix 🟠 3–6 and 8 (silent misbehaviour → either correct or loud).
3. Decide + document the semantic choices: vacuous `all` (13), percentage (18),
   overlap policy (11).
4. The 🟡 robustness batch (7, 9, 10, 12, 14–17) as one cleanup pass.
