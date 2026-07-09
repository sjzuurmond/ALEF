// Render a rule's natural-language segments with evaluated values injected,
// e.g. "The bmi [20.0] of a Person equals the weight of the Person [80 kg] ...".
// Pairs annotations[nodeId].rendering.segments (origin/target) with a trace.

const fmt = (v) => {
  if (!v || v.kind === 'empty') return '—';
  if (v.kind === 'number' || v.kind === 'percentage') return v.value + (v.unit ? ` ${v.unit}` : '');
  if (v.kind === 'timeline') return v.periods.map((p) => `${p.from ?? '..'}–${p.to ?? '..'}: ${fmt(p.value)}`).join('; ');
  if (v.kind === 'list') return v.elements.map(fmt).join(', ');
  return String(v.value);
};

export function renderWithValues(model, trace, instanceId, annotatedNodeId) {
  const rendering = model.annotations?.[annotatedNodeId]?.rendering;
  if (!rendering) return null;
  const values = trace.values[instanceId] ?? {};
  const walk = (segments) => segments.map((s) => {
    if (s.origin === undefined) return s.text ?? '';
    const display = s.text ?? (s.segments ? walk(s.segments) : '');
    const v = values[s.origin];
    return display + (v !== undefined ? ` [${fmt(v)}]` : '');
  }).join('');
  return walk(rendering.segments);
}
