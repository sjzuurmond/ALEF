// Exact rational arithmetic on BigInt — matching ALEF's runtime (BigRational in
// alefRuntime), which the extracted test expectations demand: fractions like
// "2/32", mixed numbers like "2_2/3", and 40+-digit exact quotients.
// Values are strings: decimals ("18,5" / "18.5"), fractions ("1/3", "-2/32"),
// or mixed numbers ("2_2/3"). toString emits a decimal when it terminates,
// otherwise a (mixed) fraction. Only sqrt and non-integer pow may approximate.

const gcd = (a, b) => { a = a < 0n ? -a : a; b = b < 0n ? -b : b;
  while (b) [a, b] = [b, a % b]; return a; };
const norm = (n, d) => {
  if (d === 0n) throw new Error('division by zero');
  if (d < 0n) { n = -n; d = -d; }
  const g = gcd(n, d) || 1n;
  return { n: n / g, d: d / g };
};

const parse = (s) => {
  const t = String(s).replace(',', '.').trim();
  let m;
  if ((m = /^(-?)(\d+)_(\d+)\/(\d+)$/.exec(t))) { // mixed: w_n/d
    const sign = m[1] === '-' ? -1n : 1n;
    return norm(sign * (BigInt(m[2]) * BigInt(m[4]) + BigInt(m[3])), BigInt(m[4]));
  }
  if ((m = /^(-?)(\d+)\/(\d+)$/.exec(t)))
    return norm(BigInt(m[1] + m[2]), BigInt(m[3]));
  if ((m = /^(-?)(\d+)(?:\.(\d+))?$/.exec(t))) {
    const frac = m[3] ?? '';
    return norm(BigInt(m[1] + m[2] + frac), 10n ** BigInt(frac.length));
  }
  throw new Error(`not a number: ${s}`);
};

const toString = (r) => {
  if (r.d === 1n) return r.n.toString();
  // terminating decimal iff denominator = 2^a * 5^b
  let d = r.d, e2 = 0, e5 = 0;
  while (d % 2n === 0n) { d /= 2n; e2++; }
  while (d % 5n === 0n) { d /= 5n; e5++; }
  if (d === 1n) {
    const scale = Math.max(e2, e5);
    const digits = ((r.n < 0n ? -r.n : r.n) * 10n ** BigInt(scale)) / r.d;
    let s = digits.toString().padStart(scale + 1, '0');
    s = s.slice(0, -scale) + '.' + s.slice(-scale);
    s = s.replace(/0+$/, '').replace(/\.$/, '');
    return (r.n < 0n ? '-' : '') + s;
  }
  // non-terminating: (mixed) fraction, like ALEF renders rationals
  const neg = r.n < 0n, n = neg ? -r.n : r.n;
  const whole = n / r.d, rest = n % r.d;
  const frac = `${rest}/${r.d}`;
  return (neg ? '-' : '') + (whole > 0n ? `${whole}_${frac}` : frac);
};

// floor of the integer k-th root (Newton); exact BigInt, any size
const iroot = (v, k) => {
  if (v < 0n) throw new Error('iroot of negative');
  if (v < 2n) return v;
  const bits = BigInt(v.toString(2).length);
  let x = 1n << (bits / k + 1n);
  for (;;) {
    const y = ((k - 1n) * x + v / x ** (k - 1n)) / k;
    if (y >= x) break;
    x = y;
  }
  while (x ** k > v) x -= 1n;
  return x;
};
const GUARD = 30; // working decimals for irrational roots; callers round far below this

export const dec = {
  add: (a, b) => { const x = parse(a), y = parse(b); return toString(norm(x.n * y.d + y.n * x.d, x.d * y.d)); },
  sub: (a, b) => { const x = parse(a), y = parse(b); return toString(norm(x.n * y.d - y.n * x.d, x.d * y.d)); },
  mul: (a, b) => { const x = parse(a), y = parse(b); return toString(norm(x.n * y.n, x.d * y.d)); },
  div: (a, b) => { const x = parse(a), y = parse(b); return toString(norm(x.n * y.d, x.d * y.n)); },
  cmp: (a, b) => { const x = parse(a), y = parse(b); const l = x.n * y.d, r = y.n * x.d;
    return l < r ? -1 : l > r ? 1 : 0; },
  neg: (a) => { const x = parse(a); return toString({ n: -x.n, d: x.d }); },
  abs: (a) => { const x = parse(a); return toString({ n: x.n < 0n ? -x.n : x.n, d: x.d }); },
  isZero: (a) => parse(a).n === 0n,
  // modes (ALEF Roundings): 'round' = rekenkundig (half away from zero),
  // 'halfTrunc' = half richting nul, 'ceil' = naar boven, 'floor' = naar beneden,
  // 'away' = weg van nul, 'trunc' = richting nul.
  // Returns a decimal string with exactly `precision` decimals.
  round: (a, precision, mode = 'round') => {
    const x = parse(a);
    const scale = 10n ** BigInt(precision);
    const num = x.n * scale;                    // value * 10^p = num / x.d
    let q = num / x.d; const r = num % x.d;     // trunc toward zero
    if (r !== 0n) {
      const twice = 2n * (r < 0n ? -r : r);
      if (mode === 'ceil' && x.n > 0n) q += 1n;
      else if (mode === 'floor' && x.n < 0n) q -= 1n;
      else if (mode === 'away') q += x.n > 0n ? 1n : -1n;
      else if (mode === 'round' && twice >= x.d) q += x.n > 0n ? 1n : -1n;
      else if (mode === 'halfTrunc' && twice > x.d) q += x.n > 0n ? 1n : -1n;
      // 'trunc': keep q
    }
    const neg = q < 0n; const digits = (neg ? -q : q).toString().padStart(precision + 1, '0');
    return (neg ? '-' : '') + (precision
      ? digits.slice(0, -precision) + '.' + digits.slice(-precision) : digits);
  },
  sqrt: (a) => dec.pow(a, '1/2'),
  // x^(n/d): exact integer powers; d-th roots exact when they exist, otherwise a
  // floor approximation with GUARD (30) correct decimals. Odd roots of negatives
  // are supported ((-125)^(1/3) = -5); even roots of negatives throw.
  pow: (a, b) => {
    const x = parse(a), e = parse(b);
    const negExp = e.n < 0n, n = negExp ? -e.n : e.n, k = e.d;
    let t = norm(x.n ** n, x.d ** n); // exact |n|-th power
    if (k !== 1n) t = kthRoot(t, k);
    return toString(negExp ? norm(t.d, t.n) : t);
  },
};

function kthRoot(r, k) {
  if (r.n < 0n) {
    if (k % 2n === 0n) throw new Error('even root of a negative number');
    const p = kthRoot({ n: -r.n, d: r.d }, k);
    return { n: -p.n, d: p.d };
  }
  const rn = iroot(r.n, k), rd = iroot(r.d, k);
  if (rn ** k === r.n && rd ** k === r.d) return norm(rn, rd); // exact
  if (k > 2000n) throw new Error(`root degree ${k} too large for exact evaluation`);
  const scale = 10n ** (BigInt(GUARD) * k);
  return norm(iroot((r.n * scale) / r.d, k), 10n ** BigInt(GUARD));
}
