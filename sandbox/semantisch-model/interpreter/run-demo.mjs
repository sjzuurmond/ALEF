// Node demo: interpret both example models and print traces + rendered rules.
//   node sandbox/semantisch-model/interpreter/run-demo.mjs
import { readFileSync } from 'node:fs';
import { interpret } from './interpreter.mjs';
import { renderWithValues } from './render.mjs';

const here = new URL('.', import.meta.url).pathname;
const load = (p) => JSON.parse(readFileSync(new URL(p, import.meta.url)));

// --- BMI ---
const bmiModel = load('../core-model.example.json');
const bmiTrace = interpret(bmiModel, load('./bmi.testcase.json'));
console.log('== BMI ==');
console.log(renderWithValues(bmiModel, bmiTrace, 'person#Jan', 'rule.bmi.v1'));
console.log('category:', JSON.stringify(bmiTrace.values['person#Jan']['sel.category']));
console.log('fired:', bmiTrace.fired.map((f) => f.ruleVersion).join(', '));

// --- income over time ---
const incModel = load('../core-model.temporal-example.json');
const incTrace = interpret(incModel, load('./income.testcase.json'));
console.log('\n== Income over time ==');
console.log(renderWithValues(incModel, incTrace, 'employee#1', 'rule.annualIncome.v1'));
console.log('annualIncome:', JSON.stringify(incTrace.values['employee#1']['sel.annualIncome']));

// full traces on demand
if (process.argv.includes('--trace')) {
  console.log('\n' + JSON.stringify(bmiTrace, null, 2));
  console.log('\n' + JSON.stringify(incTrace, null, 2));
}
