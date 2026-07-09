// Run the fixtures extracted from ALEF's test solutions (extract-tests.py)
// against the reference interpreter, comparing final instance state with the
// UitvoerVoorspelling expectations. ALEF's own tests are the correctness oracle.
//
//   node sandbox/semantisch-model/interpreter/run-alef-tests.mjs [-v]
import { readFileSync, readdirSync } from 'node:fs';
import { run } from './interpreter.mjs';
import { dec } from './decimal.mjs';

const dir = new URL('./fixtures/', import.meta.url);
const verbose = process.argv.includes('-v');

const same = (expected, actual, decimals) => {
  if (expected.kind === 'empty') return !actual || actual.kind === 'empty';
  if (!actual || actual.kind === 'empty') return false;
  if (expected.kind === 'number') {
    let a = actual.value;
    if (decimals >= 0) a = dec.round(a, decimals);
    return dec.cmp(expected.value, a) === 0;
  }
  return String(expected.value) === String(actual.value);
};
const show = (v) => v ? (v.kind === 'number' ? v.value : `${v.kind}:${v.value ?? ''}`) : '(missing)';

let pass = 0, fail = 0, error = 0;
for (const file of readdirSync(dir).filter((f) => f.endsWith('.json')).sort()) {
  const { model, cases } = JSON.parse(readFileSync(new URL(file, dir)));
  for (const c of cases) {
    // per-case parameter values become a prepended (always-valid) parameter set
    const m = c.parameters
      ? { ...model, parameterSets: [
          { validity: {}, assignments: Object.entries(c.parameters).map(([parameter, value]) => ({ parameter, value })) },
          ...(model.parameterSets ?? [])] }
      : model;
    let state;
    try {
      ({ state } = run(m, { name: c.name, calculationDate: c.calculationDate, instances: c.instances }));
    } catch (e) {
      console.log(`ERROR ${file} :: ${c.name} :: ${e.message}`);
      error += c.expectations.length;
      continue;
    }
    for (const x of c.expectations) {
      const actual = state[x.instance]?.slots[x.attribute];
      let ok;
      try { ok = same(x.expected, actual, x.decimals); }
      catch (e) { ok = false; }
      if (ok) {
        pass++;
        if (verbose) console.log(`pass  ${file} :: ${c.name} :: ${x.attribute}`);
      } else {
        fail++;
        console.log(`FAIL  ${file} :: ${c.name} :: ${x.attribute}: expected ${show(x.expected)}, got ${show(actual)}`);
      }
    }
  }
}
console.log(`\n${pass} passed, ${fail} failed, ${error} errored (of ${pass + fail + error} expectations)`);
process.exit(fail + error ? 1 : 0);
