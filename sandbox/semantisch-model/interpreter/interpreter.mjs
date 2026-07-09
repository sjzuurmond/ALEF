// Minimal reference interpreter for core-model.schema.json.
// Shape borrowed from ALEF's Merlin runtime (MUniverse: object/fact extents,
// parameter sets, working date, recursion cap) and RegelRecht's engine
// (deterministic evaluation returning a result WITH an explanation trail):
// the emitted evaluation-trace (evaluation-trace.schema.json) IS the trail.
//
// Values are the trace's Value union: {kind:'number',value,unit?} | text |
// boolean | date | enumValue | empty | list | object | timeline.
// Runs unmodified in browsers and Node (plain ESM, no dependencies).

import { dec } from './decimal.mjs';

const EMPTY = { kind: 'empty' };
const bool = (v) => ({ kind: 'boolean', value: v });
const isEmpty = (v) => !v || v.kind === 'empty';
const unsupported = (what) => { throw new Error(`unsupported by this interpreter: ${what}`); };

// ---------- time helpers (ISO date strings) ----------
const inPeriod = (date, p = {}) => // validity Period: throughInclusive defaults true
  (!p.from || date >= p.from) && (!p.to || (p.throughInclusive === false ? date < p.to : date <= p.to));
const inCase = (date, c) => (!c.from || date >= c.from) && (!c.to || date < c.to); // half-open
const stepsBetween = (from, to, unit) => {
  const a = new Date(from + 'T00:00Z'), b = new Date(to + 'T00:00Z');
  if (unit === 'day') return Math.round((b - a) / 86400000);
  if (unit === 'week') return Math.round((b - a) / (7 * 86400000));
  if (unit === 'month') return (b.getUTCFullYear() - a.getUTCFullYear()) * 12 + (b.getUTCMonth() - a.getUTCMonth());
  if (unit === 'year') return b.getUTCFullYear() - a.getUTCFullYear();
  unsupported(`granularity '${unit}' in timeline arithmetic`);
};

// ---------- the universe: instances, relations, verdicts (cf. Merlin MUniverse) ----------
class Universe {
  constructor() {
    this.instances = new Map(); // id -> {id, entityType, name?, slots:Map, characteristics:Set}
    this.relations = [];        // {type, roles: {roleName: instanceId}}
    this.fired = [];            // {ruleVersion, instance}
    this.consistency = [];      // {rule, instance, consistent}
    this.mutations = 0;
    this.created = 0;
  }
  add(id, entityType, name) {
    const inst = { id, entityType, name, slots: new Map(), characteristics: new Set() };
    this.instances.set(id, inst);
    return inst;
  }
  ofType(t) { return [...this.instances.values()].filter((i) => i.entityType === t); }
  write(inst, attr, value) {
    const before = JSON.stringify(inst.slots.get(attr) ?? null);
    if (before !== JSON.stringify(value)) { inst.slots.set(attr, value); this.mutations++; }
  }
}

// ---------- the interpreter ----------
function runModel(model, testCase) {
  const date = testCase.calculationDate;
  const uni = new Universe();
  const trace = { model: model.name, testCase: testCase.name, calculationDate: date,
                  instances: [], values: {}, fired: uni.fired, consistency: uni.consistency };

  // facts in
  for (const i of testCase.instances ?? []) {
    const inst = uni.add(i.id, i.entityType, i.name);
    for (const [attr, v] of Object.entries(i.slots ?? {})) inst.slots.set(attr, v);
    for (const c of i.characteristics ?? []) inst.characteristics.add(c);
  }
  for (const r of testCase.relations ?? []) uni.relations.push(r);

  const record = (env, node, value) => {
    if (!node.id) return value;
    const key = env.instance ?? '(global)';
    (trace.values[key] ??= {})[node.id] = value;
    return value;
  };

  // parameter lookup: valid set at date, then timeVarying case at date
  const parameter = (name) => {
    for (const set of model.parameterSets ?? []) {
      if (!inPeriod(date, set.validity)) continue;
      const a = set.assignments.find((x) => x.parameter === name);
      if (!a) continue;
      let v = a.value;
      if (v.kind === 'timeVarying') {
        const c = v.cases.find((c) => inCase(date, c));
        if (!c) throw new Error(`parameter '${name}': no time case covers ${date}`);
        v = c.value;
      }
      return v;
    }
    throw new Error(`no valid parameter value for '${name}' at ${date}`);
  };

  // ----- navigation: Subject -> instance | list of instances -----
  const instancesOf = (env, node) => {
    switch (node.kind) {
      case 'universal': { // the rule's bound subject (id only matters for later references)
        if (env.subject && env.subject.entityType === node.entityType) return [env.subject];
        throw new Error(`universal '${node.entityType}' outside a rule bound to that type`);
      }
      case 'reference': {
        const bound = env.anchors.get(node.to);
        if (bound) return [bound];
        if (env.variables.has(node.to)) {
          const v = env.variables.get(node.to);
          if (v.kind === 'object') return [uni.instances.get(v.instance)];
          unsupported(`reference '${node.to}' does not name an instance`);
        }
        throw new Error(`unbound anchor '${node.to}'`);
      }
      case 'all': return uni.ofType(node.entityType);
      case 'subselection':
        return instancesOf(env, node.object).filter((inst) =>
          truthy(predicate(env, node.predicate, { kind: 'object', instance: inst.id })));
      case 'selection': { // navigate a role: instances reached through relations
        const sel = node.selector;
        if (sel.kind !== 'role') unsupported(`selection as subject with selector '${sel.kind}'`);
        const out = [];
        for (const src of instancesOf(env, node.object))
          for (const rel of uni.relations)
            if (Object.values(rel.roles).includes(src.id) && rel.roles[sel.name] && rel.roles[sel.name] !== src.id)
              out.push(uni.instances.get(rel.roles[sel.name]));
        return out;
      }
      default: unsupported(`subject kind '${node.kind}'`);
    }
  };

  const readSelector = (inst, sel) => {
    if (sel.kind === 'attribute') return inst.slots.get(sel.name) ?? EMPTY;
    if (sel.kind === 'characteristic') return bool(inst.characteristics.has(sel.name));
    if (sel.kind === 'combination') return { kind: 'list', elements: sel.selectors.map((s) => readSelector(inst, s)) };
    unsupported(`selector kind '${sel.kind}'`);
  };

  // ----- expressions -----
  const num = (v) => {
    if (v.kind === 'timeline') return v; // temporal ops handle timelines
    if (v.kind !== 'number' && v.kind !== 'percentage') throw new Error(`expected number, got ${v.kind}`);
    return v;
  };
  const asList = (v) => (v.kind === 'list' ? v.elements : [v]);

  const evalExpr = (env, e) => record(env, e, evalExprInner(env, e));
  function evalExprInner(env, e) {
    switch (e.kind) {
      // literals
      case 'number': case 'percentage': case 'text': case 'boolean': case 'date': case 'enumValue': return e;
      case 'empty': return EMPTY;
      case 'calculationDate': return { kind: 'date', value: date };
      case 'calculationYear': return { kind: 'number', value: String(new Date(date + 'T00:00Z').getUTCFullYear()) };
      case 'timeVarying': {
        const c = e.cases.find((c) => inCase(date, c));
        return c ? evalExpr(env, c.value) : EMPTY;
      }
      case 'parameter': return parameter(e.parameter);
      case 'variable': {
        if (!env.variables.has(e.variable)) throw new Error(`unbound variable '${e.variable}'`);
        return env.variables.get(e.variable);
      }
      // navigation as value
      case 'universal': case 'reference': case 'all': case 'subselection': {
        const list = instancesOf(env, e).map((i) => ({ kind: 'object', instance: i.id }));
        return e.kind === 'all' || e.kind === 'subselection' ? { kind: 'list', elements: list } : list[0] ?? EMPTY;
      }
      case 'selection': {
        if (e.selector.kind === 'role') {
          const list = instancesOf(env, e).map((i) => ({ kind: 'object', instance: i.id }));
          return list.length === 1 ? list[0] : { kind: 'list', elements: list };
        }
        const insts = instancesOf(env, e.object);
        const vals = insts.map((i) => readSelector(i, e.selector));
        return insts.length === 1 ? vals[0] : { kind: 'list', elements: vals };
      }
      // computation
      case 'operation': return operation(env, e);
      case 'aggregation': {
        const items = asList(evalExpr(env, e.over)).filter((v) => !isEmpty(v));
        if (e.function === 'count') return { kind: 'number', value: String(items.length) };
        if (items.length === 0) return EMPTY;
        const nums = items.map((v) => num(v).value);
        let acc = nums[0];
        for (const n of nums.slice(1)) {
          if (e.function === 'sum' || e.function === 'average') acc = dec.add(acc, n);
          if (e.function === 'min') acc = dec.cmp(n, acc) < 0 ? n : acc;
          if (e.function === 'max') acc = dec.cmp(n, acc) > 0 ? n : acc;
        }
        if (e.function === 'average') acc = dec.div(acc, String(nums.length));
        return { kind: 'number', value: acc, unit: items[0].unit };
      }
      case 'conditional': {
        for (const c of e.cases) if (truthy(condition(env, c.when))) return evalExpr(env, c.then);
        return e.else ? evalExpr(env, e.else) : EMPTY;
      }
      case 'textConcat':
        return { kind: 'text', value: e.parts.map((p) => { const v = evalExpr(env, p); return isEmpty(v) ? '' : String(v.value); }).join('') };
      case 'dateFunction': return dateFunction(env, e);
      case 'unitConversion': return unitConversion(env, e);
      case 'temporal': return temporal(env, e);
      default: unsupported(`expression kind '${e.kind}'`);
    }
  }

  function operation(env, e) {
    // Oracle semantics (RekenkundigeFuncties_Test): empty numeric operands act as 0
    // ("1 getal is leeg" expects leeg+2+4 = 6, leeg*2*3 = 0); division by zero -> empty.
    const ZERO = { kind: 'number', value: '0' };
    const ops = e.operands.map((o) => { const v = evalExpr(env, o); return isEmpty(v) ? ZERO : v; });
    const [a, b] = ops.map((v) => num(v).value ?? v);
    if (e.op === 'divide' && dec.isZero(b)) return EMPTY;
    // unit soundness: additive ops keep the shared unit; multiplicative ops always
    // drop units (compound-unit algebra is out of scope; use unitConversion to
    // reintroduce a unit deliberately)
    const additive = ['add', 'subtract', 'min', 'max', 'abs', 'round', 'ceil', 'floor'].includes(e.op);
    const unit = additive ? ops.find((o) => o.unit)?.unit : undefined;
    const n = (value, u = unit) => ({ kind: 'number', value, ...(u && { unit: u }) });
    switch (e.op) {
      case 'add': return n(ops.map((o) => num(o).value).reduce(dec.add));
      case 'subtract': return n(dec.sub(a, b));
      case 'multiply': return n(ops.map((o) => num(o).value).reduce(dec.mul));
      case 'divide': return n(dec.div(a, b));
      case 'power': return n(dec.pow(a, b));
      case 'min': case 'max': {
        let acc = num(ops[0]).value;
        for (const o of ops.slice(1)) { const v = num(o).value;
          acc = (e.op === 'min' ? dec.cmp(v, acc) < 0 : dec.cmp(v, acc) > 0) ? v : acc; }
        return n(acc);
      }
      case 'abs': return n(dec.abs(a));
      case 'sqrt': return n(dec.sqrt(a));
      case 'round': case 'ceil': case 'floor': {
        const mode = e.op !== 'round' ? e.op
          : { halfAwayFromZero: 'round', halfTowardZero: 'halfTrunc',
              awayFromZero: 'away', towardZero: 'trunc' }[e.rounding ?? 'halfAwayFromZero'];
        return n(dec.round(a, e.precision ?? 0, mode), ops[0].unit);
      }
      default: unsupported(`operation '${e.op}'`);
    }
  }

  function dateFunction(env, e) {
    const args = (e.arguments ?? []).map((a) => evalExpr(env, a));
    const d = (v) => new Date(v.value + 'T00:00Z');
    switch (e.function) {
      case 'age': case 'dateDiff': {
        const unit = e.function === 'age' ? 'year' : (args[2]?.value ?? 'day');
        const [from, to] = e.function === 'age' ? [args[0], args[1] ?? { value: date }] : [args[0], args[1]];
        if (unit === 'year' || unit === 'month') { // whole units, birthday-style
          const a = d(from), b = d(to);
          let months = (b.getUTCFullYear() - a.getUTCFullYear()) * 12 + b.getUTCMonth() - a.getUTCMonth();
          if (b.getUTCDate() < a.getUTCDate()) months--;
          return { kind: 'number', value: String(unit === 'year' ? Math.floor(months / 12) : months) };
        }
        return { kind: 'number', value: String(Math.floor((d(to) - d(from)) / 86400000)) };
      }
      case 'dateElement': {
        const parts = { year: 'getUTCFullYear', month: 'getUTCMonth', day: 'getUTCDate' };
        const part = args[1].value;
        const raw = d(args[0])[parts[part] ?? unsupported(`date element '${part}'`)]();
        return { kind: 'number', value: String(part === 'month' ? raw + 1 : raw) };
      }
      case 'dateFromParts': {
        const [y, m, dd] = args.map((v) => Number(v.value));
        return { kind: 'date', value: `${String(y).padStart(4, '0')}-${String(m).padStart(2, '0')}-${String(dd).padStart(2, '0')}` };
      }
      case 'easterSunday': { // anonymous Gregorian algorithm
        const y = Number(args[0].value);
        const a = y % 19, b = Math.floor(y / 100), c = y % 100, dd = Math.floor(b / 4), ee = b % 4,
          f = Math.floor((b + 8) / 25), g = Math.floor((b - f + 1) / 3), h = (19 * a + b - dd - g + 15) % 30,
          i = Math.floor(c / 4), k = c % 4, l = (32 + 2 * ee + 2 * i - h - k) % 7,
          m = Math.floor((a + 11 * h + 22 * l) / 451), month = Math.floor((h + l - 7 * m + 114) / 31),
          day = ((h + l - 7 * m + 114) % 31) + 1;
        return { kind: 'date', value: `${y}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}` };
      }
      default: unsupported(`dateFunction '${e.function}'`);
    }
  }

  function unitConversion(env, e) {
    const v = num(evalExpr(env, e.argument));
    const to = typeof e.toUnit === 'string' ? e.toUnit : unsupported('structured unit in conversion');
    for (const sys of model.dataModel.unitSystems ?? []) {
      const f = Object.fromEntries((sys.conversions ?? []).map((c) => [c.base, c.factor]));
      for (const base of sys.baseUnits) f[base] ??= '1';
      if (v.unit in f && to in f)
        return { kind: 'number', value: dec.div(dec.mul(v.value, f[v.unit]), f[to]), unit: to };
    }
    throw new Error(`no conversion from '${v.unit}' to '${to}'`);
  }

  function temporal(env, e) {
    switch (e.op) {
      case 'currentDay': return { kind: 'date', value: date };
      case 'total': { // sum a timeline over its bounded periods, weighted by granularity steps
        const tl = evalExpr(env, e.expression);
        if (tl.kind !== 'timeline') return tl; // constant: nothing to total
        const unit = timeUnitOf(e.expression) ?? 'month';
        let acc = '0', u;
        for (const p of tl.periods) {
          if (!p.from || !p.to) throw new Error('total over unbounded timeline period');
          acc = dec.add(acc, dec.mul(num(p.value).value, String(stepsBetween(p.from, p.to, unit))));
          u = p.value.unit ?? u;
        }
        return { kind: 'number', value: acc, unit: u };
      }
      default: unsupported(`temporal operator '${e.op}'`); // timeProportional, durationWhere
    }
  }
  // granularity of the time dimension behind a selection's attribute type, if any
  function timeUnitOf(expr) {
    if (expr.kind !== 'selection' || expr.selector.kind !== 'attribute') return null;
    for (const et of model.dataModel.entityTypes ?? [])
      for (const at of et.attributes ?? [])
        if (at.name === expr.selector.name && at.type.kind === 'dimensioned')
          for (const dName of at.type.dimensions) {
            const dim = (model.dataModel.dimensions ?? []).find((d) => d.name === dName);
            if (dim?.kind === 'time') return dim.granularity.unit;
          }
    return null;
  }

  // ----- predicates & conditions (booleans; recorded like values) -----
  const truthy = (v) => v.kind === 'boolean' && v.value === true;

  const predicate = (env, p, subject) => record(env, p, predicateInner(env, p, subject));
  function predicateInner(env, p, subject) {
    const negate = (v) => (p.negated ? bool(!v.value) : v);
    switch (p.kind) {
      case 'comparison': {
        const rhs = evalExpr(env, p.value);
        if (isEmpty(subject) || isEmpty(rhs)) return bool(false);
        const c = compare(subject, rhs);
        return bool({ eq: c === 0, ne: c !== 0, lt: c < 0, le: c <= 0, gt: c > 0, ge: c >= 0 }[p.operator]);
      }
      case 'isFilled': return negate(bool(!isEmpty(subject)));
      case 'hasRoleOrCharacteristic': {
        if (subject.kind !== 'object') return bool(false);
        const inst = uni.instances.get(subject.instance);
        const has = inst.characteristics.has(p.target) ||
          uni.relations.some((r) => r.roles[p.target] === inst.id);
        return negate(bool(has));
      }
      case 'isNumericWithLength':
        return negate(bool(subject.kind === 'text' && new RegExp(`^\\d{${p.length}}$`).test(subject.value)));
      case 'checksum': {
        if (p.algorithm !== 'elevenProof') unsupported(`checksum algorithm '${p.algorithm}'`);
        const s = String(subject.value ?? '');
        if (!/^\d{9}$/.test(s)) return negate(bool(false));
        const sum = [...s].reduce((acc, ch, i) => acc + Number(ch) * (i === 8 ? -1 : 9 - i), 0);
        return negate(bool(sum % 11 === 0));
      }
      case 'isDayType': unsupported('isDayType (requires dayTypeDefinition semantics)');
      default: unsupported(`predicate kind '${p.kind}'`);
    }
  }
  function compare(a, b) {
    if (a.kind === 'number' || a.kind === 'percentage') return dec.cmp(a.value, num(b).value);
    if (a.kind === 'date') return a.value < b.value ? -1 : a.value > b.value ? 1 : 0;
    return String(a.value) === String(b.value) ? 0 : String(a.value) < String(b.value) ? -1 : 1;
  }

  const condition = (env, c) => record(env, c, conditionInner(env, c));
  function conditionInner(env, c) {
    switch (c.kind) {
      case 'simple': {
        const subj = evalExpr(env, c.subject);
        const items = subj.kind === 'list' ? subj.elements : [subj];
        const hits = items.filter((v) => truthy(predicate(env, c.predicate, v))).length;
        return bool(quantified(c.quantifier, hits, items.length));
      }
      case 'compound': {
        const results = c.conditions.map((sub) => truthy(condition(env, sub)));
        const hits = results.filter(Boolean).length, total = results.length;
        if (c.logic === 'and') return bool(hits === total);
        if (c.logic === 'or') return bool(hits > 0);
        if (c.logic === 'none') return bool(hits === 0);
        if (c.logic === 'notAll') return bool(hits < total);
        break;
      }
      case 'uniqueness': {
        const seen = new Set();
        for (const inst of uni.ofType(subjectTypeOf(env))) // uniqueness ranges over the subject's extent
          for (const sel of c.selections) {
            const v = JSON.stringify(readSelector(inst, sel.selector));
            if (seen.has(v)) return bool(false);
            seen.add(v);
          }
        return bool(true);
      }
      case 'period':
        return bool((!c.from || date >= evalExpr(env, c.from).value) &&
                    (!c.throughInclusive || date <= evalExpr(env, c.throughInclusive).value));
      case 'ruleStatus': {
        const hit = c.status === 'fired'
          ? uni.fired.some((f) => f.ruleVersion === c.rule || f.rule === c.rule)
          : uni.consistency.some((x) => x.rule === c.rule && !x.consistent);
        return bool(c.negated ? !hit : hit);
      }
      default: unsupported(`condition kind '${c.kind}'`);
    }
  }
  const quantified = (q, hits, total) => {
    if (!q || q.kind === 'all') return total > 0 && hits === total;
    if (q.kind === 'none') return hits === 0;
    return { atLeast: hits >= q.count, atMost: hits <= q.count, exactly: hits === q.count }[q.mode];
  };
  const subjectTypeOf = (env) => env.subjectType ?? unsupported('uniqueness outside a subject-bound rule');

  // ----- actions -----
  function execute(env, action) {
    switch (action.kind) {
      case 'assignment': {
        const targets = instancesOf(env, action.target.object);
        const sel = action.target.selector;
        if (sel.kind !== 'attribute') unsupported(`assignment to selector '${sel.kind}'`);
        for (const inst of targets) {
          if (action.initial && !isEmpty(inst.slots.get(sel.name) ?? EMPTY)) continue;
          const v = action.value ? evalExpr(env, action.value) : EMPTY;
          uni.write(inst, sel.name, v);
          record(env, action.target, v);
        }
        return;
      }
      case 'setCharacteristic':
        for (const inst of instancesOf(env, action.object))
          if (!inst.characteristics.has(action.characteristic)) { inst.characteristics.add(action.characteristic); uni.mutations++; }
        return;
      case 'createObject': case 'createFact': {
        const rel = relationOfRole(action.role);
        const me = env.subject ?? unsupported(`${action.kind} without a bound subject`);
        if (action.kind === 'createObject') {
          const otherRole = rel.roles.find((r) => r.name !== action.role) ?? rel.roles[0];
          const roleDef = rel.roles.find((r) => r.name === action.role);
          const inst = uni.add(`${roleDef.entityType}#${++uni.created}`, roleDef.entityType);
          trace.instances.push({ id: inst.id, entityType: inst.entityType });
          for (const init of action.initializations ?? []) uni.write(inst, init.attribute, evalExpr(env, init.value));
          uni.relations.push({ type: rel.name, roles: { [action.role]: inst.id, [otherRole.name]: me.id } });
        } else {
          const other = instancesOf(env, action.other)[0] ?? unsupported('createFact: no other instance');
          const myRole = rel.roles.find((r) => r.name !== action.role) ?? rel.roles[0];
          uni.relations.push({ type: rel.name, roles: { [action.role]: other.id, [myRole.name]: me.id } });
        }
        uni.mutations++;
        return;
      }
      case 'consistencyCheck': {
        const ok = truthy(condition(env, action.criterion));
        uni.consistency.push({ rule: env.versionId, instance: env.instance, consistent: ok });
        return;
      }
      case 'distribution': return distribute(env, action);
      case 'dayTypeDefinition': case 'timelineStart':
        unsupported(`action '${action.kind}' (recorded in the model, no runtime semantics here)`);
      default: unsupported(`action kind '${action.kind}'`);
    }
  }
  const relationOfRole = (role) =>
    (model.dataModel.relationTypes ?? []).find((r) => r.roles.some((x) => x.name === role))
      ?? unsupported(`role '${role}' not found in any relation type`);

  function distribute(env, action) {
    const amount = num(evalExpr(env, action.amount)).value;
    const r = action.recipient;
    const shareSel = r.share; // 'the share of each <recipient>' — its object path yields the recipients
    const recipients = instancesOf(env, shareSel.object);
    if (recipients.length === 0) return;
    const precision = r.precision ?? 2;
    const weights = r.proRata
      ? recipients.map((i) => num(readSelector(i, r.proRata.selector)).value)
      : recipients.map(() => '1');
    const totalW = weights.reduce(dec.add);
    let distributed = '0';
    recipients.forEach((inst, i) => {
      let share = dec.round(dec.div(dec.mul(amount, weights[i]), totalW), precision, 'floor');
      if (r.maxClaim) { const max = num(readSelector(inst, r.maxClaim.selector)).value;
        if (dec.cmp(share, max) > 0) share = max; }
      uni.write(inst, shareSel.selector.name, { kind: 'number', value: share });
      distributed = dec.add(distributed, share);
    });
    if (action.remainder) {
      const rest = dec.sub(amount, distributed);
      for (const inst of instancesOf(env, action.remainder.object))
        uni.write(inst, action.remainder.selector.name, { kind: 'number', value: rest });
    }
  }

  // ----- the evaluation cycle -----
  const findUniversal = (node) => { // first 'universal' anchor decides the rule's subject
    if (node && typeof node === 'object') {
      if (node.kind === 'universal') return node;
      for (const v of Object.values(node)) { const f = findUniversal(v); if (f) return f; }
    }
    return null;
  };

  const MAX_PASSES = 250; // recursion cap, cf. Merlin's maxRecursion
  for (const group of model.ruleGroups ?? []) {
    for (let pass = 0; ; pass++) {
      const before = uni.mutations;
      for (const rule of group.rules) {
        const version = rule.versions.find((v) => inPeriod(date, v.validity));
        if (!version) continue;
        const uniAnchor = findUniversal(version);
        const bindings = uniAnchor ? uni.ofType(uniAnchor.entityType) : [null];
        for (const inst of bindings) {
          const env = { anchors: new Map(), variables: new Map(),
                        subject: inst, instance: inst?.id, subjectType: uniAnchor?.entityType,
                        versionId: version.id ?? rule.id ?? rule.name };
          if (inst && uniAnchor?.id) env.anchors.set(uniAnchor.id, inst);
          for (const v of version.variables ?? []) env.variables.set(v.name, record(env, v, evalExpr(env, v.value)));
          if (version.condition && !truthy(condition(env, version.condition))) continue;
          execute(env, version.action);
          uni.fired.push({ ruleVersion: env.versionId, ...(inst && { instance: inst.id }) });
        }
      }
      // Always iterate to a fixpoint: ALEF evaluates dependency-driven (Merlin's lazy
      // properties — rule order within a group is irrelevant), which re-running until
      // nothing changes approximates. Oracle: 'Numeriek: Expressie vgl regel' has rule 1
      // reading an attribute that rule 2 (listed later) computes. 'recursive' groups
      // additionally allow rules to feed themselves; both converge or hit the cap.
      if (uni.mutations === before) break;
      if (pass >= MAX_PASSES) throw new Error(`no fixpoint after ${MAX_PASSES} passes in group '${group.name}'`);
    }
  }

  // read out: final slot values of declared instances also land in the trace
  for (const i of testCase.instances ?? []) {
    trace.instances.push({ id: i.id, entityType: i.entityType, ...(i.name && { name: i.name }) });
  }
  const state = {};
  for (const inst of uni.instances.values())
    state[inst.id] = { slots: Object.fromEntries(inst.slots), characteristics: [...inst.characteristics] };
  return { trace, state };
}

// Public API: interpret() returns the schema-conformant trace; run() additionally
// exposes the final instance state (used by the test runner to check expectations).
export function interpret(model, testCase) { return runModel(model, testCase).trace; }
export function run(model, testCase) { return runModel(model, testCase); }
