// Minimal fixed-point decimal on BigInt. Values are strings ("18,5" or "18.5");
// law needs exact decimal arithmetic, so no floats. Scale = number of decimals.

const parse = (s) => {
  const t = String(s).replace(',', '.').trim();
  const m = /^(-?)(\d+)(?:\.(\d+))?$/.exec(t);
  if (!m) throw new Error(`not a decimal: ${s}`);
  const [, sign, int, frac = ''] = m;
  return { u: BigInt(sign + int + frac), scale: frac.length };
};

const rescale = (d, scale) => {
  if (d.scale === scale) return d;
  if (scale > d.scale) return { u: d.u * 10n ** BigInt(scale - d.scale), scale };
  throw new Error('rescale down needs rounding');
};

const align = (a, b) => {
  const s = Math.max(a.scale, b.scale);
  return [rescale(a, s), rescale(b, s), s];
};

const toString = (d) => {
  const neg = d.u < 0n;
  let digits = (neg ? -d.u : d.u).toString().padStart(d.scale + 1, '0');
  const int = digits.slice(0, digits.length - d.scale);
  const frac = d.scale ? '.' + digits.slice(digits.length - d.scale) : '';
  return (neg ? '-' : '') + int + frac;
};

const trim = (d) => {
  while (d.scale > 0 && d.u % 10n === 0n) d = { u: d.u / 10n, scale: d.scale - 1 };
  return d;
};

export const dec = {
  add: (a, b) => { const [x, y, s] = align(parse(a), parse(b)); return toString({ u: x.u + y.u, scale: s }); },
  sub: (a, b) => { const [x, y, s] = align(parse(a), parse(b)); return toString({ u: x.u - y.u, scale: s }); },
  mul: (a, b) => { const x = parse(a), y = parse(b); return toString(trim({ u: x.u * y.u, scale: x.scale + y.scale })); },
  div: (a, b) => {
    const x = parse(a), y = parse(b);
    if (y.u === 0n) throw new Error('division by zero');
    const S = 12; // working precision; callers round explicitly
    const exp = S + y.scale - x.scale; // so that q has scale S
    const num = exp >= 0 ? x.u * 10n ** BigInt(exp) : x.u / 10n ** BigInt(-exp);
    return toString(trim({ u: num / y.u, scale: S }));
  },
  cmp: (a, b) => { const [x, y] = align(parse(a), parse(b)); return x.u < y.u ? -1 : x.u > y.u ? 1 : 0; },
  neg: (a) => { const x = parse(a); return toString({ u: -x.u, scale: x.scale }); },
  abs: (a) => { const x = parse(a); return toString({ u: x.u < 0n ? -x.u : x.u, scale: x.scale }); },
  // mode: 'round' (half-up, "rekenkundig"), 'ceil', 'floor'; precision = decimals to keep
  round: (a, precision, mode = 'round') => {
    const x = parse(a);
    if (x.scale <= precision) return toString(rescale(x, precision));
    const drop = 10n ** BigInt(x.scale - precision);
    let q = x.u / drop; const r = x.u % drop;
    if (r !== 0n) {
      if (mode === 'ceil' && x.u > 0n) q += 1n;
      else if (mode === 'floor' && x.u < 0n) q -= 1n;
      else if (mode === 'round') {
        const half = drop / 2n;
        if (x.u > 0n && r >= half) q += 1n;
        if (x.u < 0n && -r >= half) q -= 1n;
      }
    }
    return toString({ u: q, scale: precision });
  },
  sqrt: (a) => { // via Number: adequate for a reference interpreter; round afterwards
    const v = Number(String(a).replace(',', '.'));
    if (v < 0) throw new Error('sqrt of negative');
    return String(Math.sqrt(v));
  },
  pow: (a, b) => {
    const e = parse(b);
    if (e.scale === 0 && e.u >= 0n) { // exact integer power
      let r = '1'; for (let i = 0n; i < e.u; i++) r = dec.mul(r, a);
      return r;
    }
    return String(Math.pow(Number(String(a).replace(',', '.')), Number(String(b).replace(',', '.'))));
  },
};
