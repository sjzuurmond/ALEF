#!/usr/bin/env python3
"""Extract test fixtures from ALEF test solutions.

Parses .mps solution models (gegevensspraak ObjectModel + regelspraak Regelgroep +
testspraak TestSet), transforms the subset the reference interpreter supports into
core-model JSON, and emits one fixture per TestSet:

    fixtures/<model>.<testset>.json
    { "model": <core model>, "cases": [ { "name", "calculationDate", "instances",
      "expectations": [ {"instance", "attribute", "expected", "decimals"} ] } ] }

TestSets (or whole models) using constructs outside the supported subset are
skipped with a reason. Run from the repo root:

    python3 sandbox/semantisch-model/interpreter/extract-tests.py
"""
import xml.etree.ElementTree as ET
import glob, json, os, sys

REPO = os.path.normpath(os.path.join(os.path.dirname(__file__), '../../..'))
OUT = os.path.join(os.path.dirname(__file__), 'fixtures')

class Skip(Exception): pass

# ---------- generic .mps parser: registry-decoded node trees ----------
def parse(path):
    root = ET.parse(path).getroot()
    cname, cprops, cchildren, crefs = {}, {}, {}, {}
    for lang in root.iter('language'):
        for c in lang.iter('concept'):
            cname[c.get('index')] = c.get('name')
            for p in c.findall('property'): cprops[p.get('index')] = p.get('name')
            for ch in c.findall('child'): cchildren[ch.get('index')] = ch.get('name')
            for r in c.findall('reference'): crefs[r.get('index')] = r.get('name')
    def node(n):
        d = {'concept': (cname.get(n.get('concept'), '?')).rsplit('.', 1)[-1],
             'nid': n.get('id'), 'props': {}, 'refs': {}, 'children': {}}
        for p in n.findall('property'):
            d['props'][cprops.get(p.get('role'), p.get('role'))] = p.get('value')
        for r in n.findall('ref'):
            d['refs'][crefs.get(r.get('role'), r.get('role'))] = \
                {'resolve': r.get('resolve'), 'node': r.get('node'), 'to': r.get('to')}
        for ch in n.findall('node'):
            d['children'].setdefault(cchildren.get(ch.get('role'), ch.get('role')), []).append(node(ch))
        return d
    return [node(n) for n in root.findall('node')]

def child(n, role, i=0): return n['children'].get(role, [None] * (i + 1))[i]
def kids(n, role): return n['children'].get(role, [])
def ref(n, role):
    r = n['refs'].get(role)
    return (r.get('resolve') or r.get('node')) if r else None
def refnode(n, role):
    r = n['refs'].get(role)
    return r.get('node') if r else None

# ---------- literals & dates ----------
def date_of(lit):  # DatumTijdLiteral {jaar, maand?, dag?}
    if not lit['props'].get('jaar'): raise Skip('date without year')
    y = int(lit['props']['jaar'])
    m = int(lit['props'].get('maand', 1) or 1)
    d = int(lit['props'].get('dag', 1) or 1)
    return f"{y:04d}-{m:02d}-{d:02d}"

def literal(n):
    if n is None: return {'kind': 'empty'}  # e.g. EigenschapToekenning without value
    c = n['concept']
    if c in ('NumeriekeLiteral', 'PercentageLiteral'):
        return {'kind': 'number', 'value': n['props']['waarde'].replace(',', '.')}
    if c == 'TekstLiteral': return {'kind': 'text', 'value': n['props'].get('waarde', '')}
    if c == 'BooleanLiteral': return {'kind': 'boolean', 'value': n['props'].get('waarde') in ('true', 'waar')}
    if c == 'DatumTijdLiteral': return {'kind': 'date', 'value': date_of(n)}
    if c == 'Leeg': return {'kind': 'empty'}
    if c == 'EnumWaardeRef': return {'kind': 'enumValue', 'value': ref(n, 'waarde')}
    raise Skip(f"literal '{c}'")

# ---------- gegevensspraak -> dataModel ----------
def datatype(n):
    c = n['concept']
    if c == 'NumeriekType':
        t = {'kind': 'number'}
        d = int(n['props'].get('decimalen', -1))
        if d >= 0: t['spec'] = {'precision': d}
        return t
    if c == 'PercentageType': return {'kind': 'percentage'}
    if c == 'TekstType': return {'kind': 'text'}
    if c == 'BooleanType': return {'kind': 'boolean'}
    if c == 'DatumTijdType': return {'kind': 'datetime'}
    if c == 'DomeinType': return {'kind': 'domain', 'domain': ref(n, 'domein')}
    raise Skip(f"datatype '{c}'")

def data_model(om):
    # Lenient: declarations the core cannot express yet are DROPPED, not fatal —
    # the interpreter resolves slots dynamically, so extraction only fails later
    # if a rule actually uses a dropped construct.
    dm = {'entityTypes': [], 'domains': []}
    for elem in kids(om, 'elem'):
        if elem['concept'] == 'ObjectType':
            et = {'name': elem['props']['name'], 'attributes': [], 'characteristics': []}
            for a in kids(elem, 'elem'):
                if a['concept'] == 'Attribuut':
                    try:
                        et['attributes'].append({'name': a['props']['name'], 'type': datatype(child(a, 'type'))})
                    except Skip:
                        pass  # attribute with unsupported type: dropped
                elif a['concept'] == 'Kenmerk':
                    et['characteristics'].append({'name': a['props']['name']})
            dm['entityTypes'].append(et)
        elif elem['concept'] == 'Parameter':
            try:
                dm.setdefault('parameters', []).append(
                    {'name': elem['props']['name'], 'type': datatype(child(elem, 'type'))})
            except Skip:
                pass
        elif elem['concept'] == 'FeitType':
            roles = [{'name': r['props'].get('name') or r['props'].get('frase', '?'),
                      'entityType': ref(r, 'objectType'),
                      **({'plural': True} if r['props'].get('single') != 'true' else {})}
                     for r in kids(elem, 'rollen')]
            dm.setdefault('relationTypes', []).append(
                {**({'name': elem['props']['name']} if elem['props'].get('name') else {}), 'roles': roles})
        elif elem['concept'] == 'Domein':
            try:
                base = child(elem, 'base')
                if base['concept'] == 'EnumeratieType':
                    dm['domains'].append({'name': elem['props']['name'], 'base': {
                        'kind': 'enumeration', 'values': [w['props']['name'] for w in kids(base, 'waarde')]}})
                else:
                    dm['domains'].append({'name': elem['props']['name'], 'base': datatype(base)})
            except Skip:
                pass
        # anything else (Dimensie, EenheidSysteem, Dagsoort, ObjectExtensie, ...): dropped
    return dm

# ---------- regelspraak -> ruleGroups ----------
BINOPS = {'PlusExpressie': 'add', 'MinusExpressie': 'subtract',
          'VermenigvuldigExpressie': 'multiply', 'DelenExpressie': 'divide',
          'Machtsverheffen': 'power'}
# ALEF Roundings member -> (op, rounding); default member is rekenkundig_afgerond
ROUND = {'rekenkundig_afgerond': ('round', None),
         'afgerond_naar_beneden': ('floor', None),
         'afgerond_naar_boven': ('ceil', None),
         'afgerond_richting_nul': ('round', 'towardZero'),
         'afgerond_weg_van_nul': ('round', 'awayFromZero'),
         'afgerond_half_richting_nul': ('round', 'halfTowardZero'),
         # oracle (Afronden verschillende manieren: +3.5->3, -3.5->-3): this legacy
         # member name also means ties toward zero
         'afgerond_half_naar_beneden': ('round', 'halfTowardZero')}

class Ctx:  # per rule version: the universal anchor + variable names
    def __init__(self): self.univ_nid, self.anchor, self.entity = None, None, None

def subject(n, ctx):
    c = n['concept']
    if c == 'UnivOnderwerp':
        entity = ref(n, 'base')
        if ctx.univ_nid is None:
            ctx.univ_nid, ctx.anchor, ctx.entity = n['nid'], f"u.{n['nid']}", entity
            return {'kind': 'universal', 'id': ctx.anchor, 'entityType': entity}
        return {'kind': 'reference', 'to': ctx.anchor}
    if c == 'OnderwerpRef':
        if refnode(n, 'ref') == ctx.univ_nid or ref(n, 'ref') == ctx.entity:
            return {'kind': 'reference', 'to': ctx.anchor}
        raise Skip(f"OnderwerpRef to '{ref(n, 'ref')}'")
    raise Skip(f"subject '{c}'")

def expression(n, ctx):
    c = n['concept']
    if c in BINOPS:
        return {'kind': 'operation', 'op': BINOPS[c],
                'operands': [expression(child(n, 'links'), ctx), expression(child(n, 'rechts'), ctx)]}
    if c == 'Haakjes':  # parentheses: unwrap — the tree groups
        return expression(child(n, 'waarde'), ctx)
    if c == 'Worteltrekken':
        return {'kind': 'operation', 'op': 'sqrt', 'operands': [expression(next(iter(n['children'].values()))[0], ctx)]}
    if c == 'AbsoluteWaarde':
        return {'kind': 'operation', 'op': 'abs', 'operands': [expression(next(iter(n['children'].values()))[0], ctx)]}
    if c == 'Afronden':
        member = (n['props'].get('hoeAfTeRonden') or '/rekenkundig_afgerond').rsplit('/', 1)[-1].replace(' ', '_')
        if member not in ROUND: raise Skip(f"afronding '{member}'")
        op, rounding = ROUND[member]
        return {'kind': 'operation', 'op': op, 'precision': int(n['props'].get('aantalDecimalen', 0)),
                **({'rounding': rounding} if rounding else {}),
                'operands': [expression(child(n, 'afTeRonden'), ctx)]}
    if c == 'Selectie':
        sel = child(n, 'selector')
        if sel['concept'] != 'AttribuutSelector': raise Skip(f"selector '{sel['concept']}'")
        return {'kind': 'selection', 'object': subject(child(n, 'object'), ctx),
                'selector': {'kind': 'attribute', 'name': ref(sel, 'base')}}
    if c == 'BegrensdeExpressie':  # fold bounds: minimum -> max(arg, w), maximum -> min(arg, w)
        out = expression(child(n, 'argument'), ctx)
        for g in kids(n, 'grenzen'):
            kind = (g['props'].get('begrenzing') or '').rsplit('/', 1)[-1]
            op = {'minimum': 'max', 'maximum': 'min'}.get(kind) or Skip(f"begrenzing '{kind}'")
            if isinstance(op, Skip): raise op
            out = {'kind': 'operation', 'op': op, 'operands': [out, expression(child(g, 'waarde'), ctx)]}
        return out
    if c == 'Aggregatie':  # over a Concatenatie chain -> n-ary operation
        fn = (n['props'].get('functie') or '').rsplit('/', 1)[-1]
        op = {'som': 'add', 'max': 'max', 'min': 'min', 'maximum': 'max', 'minimum': 'min'}.get(fn)
        if not op: raise Skip(f"aggregatie functie '{fn}'")
        items = concat_items(child(n, 'lijst'), ctx)
        return {'kind': 'operation', 'op': op, 'operands': items}
    if c in ('UnivOnderwerp', 'OnderwerpRef'): return subject(n, ctx)
    if c == 'VariabeleRef': return {'kind': 'variable', 'variable': ref(n, 'var')}
    if c == 'ParameterRef': return {'kind': 'parameter', 'parameter': ref(n, 'param')}
    return literal(n)  # raises Skip for unknown concepts

def concat_items(n, ctx):  # flatten a binary Concatenatie chain into a list of expressions
    if n['concept'] == 'Concatenatie':
        return concat_items(child(n, 'links'), ctx) + concat_items(child(n, 'rechts'), ctx)
    return [expression(n, ctx)]

OPERATORS = {'GT': 'gt', 'GE': 'ge', 'LT': 'lt', 'LE': 'le', 'EQ': 'eq', 'NE': 'ne',
             'gelijk_aan': 'eq', 'ongelijk_aan': 'ne', 'groter_dan': 'gt', 'kleiner_dan': 'lt',
             'groter_of_gelijk_aan': 'ge', 'kleiner_of_gelijk_aan': 'le'}

def predicate(n, ctx):
    c = n['concept']
    if c == 'Vergelijking':
        member = (n['props'].get('operator') or '').rsplit('/', 1)[-1]
        op = OPERATORS.get(member)
        if not op: raise Skip(f"vergelijkingsoperator '{member}'")
        return {'kind': 'comparison', 'operator': op, 'value': expression(child(n, 'rechts'), ctx)}
    if c == 'IsGevuld': return {'kind': 'isFilled'}
    if c == 'IsLeeg': return {'kind': 'isFilled', 'negated': True}
    raise Skip(f"predicaat '{c}'")

def condition(n, ctx):
    c = n['concept']
    if c == 'EnkeleVoorwaarde':
        if kids(n, 'quant'): raise Skip('voorwaarde met quantificatie')
        return {'kind': 'simple', 'subject': expression(child(n, 'expr'), ctx),
                'predicate': predicate(child(n, 'predicaat'), ctx)}
    if c == 'SamengesteldeVoorwaarde':
        sp = child(n, 'predicaat')
        if kids(sp, 'quant'): raise Skip('samengesteld met quantificatie')
        logic = 'and'  # ALEF default reading; refined per 'verkortWeergeven'/operator when present
        subs = [condition(child(s, 'conditie'), ctx) for s in kids(sp, 'subconditie')]
        return {'kind': 'compound', 'logic': logic, 'conditions': subs}
    raise Skip(f"conditie '{c}'")

def rule_of(regel):
    versions = []
    for v in kids(regel, 'versie'):
        ctx = Ctx()
        stmt = child(v, 'statement')
        if stmt is None or stmt['concept'] != 'ActieIndienVoorwaarde': raise Skip(f"statement '{stmt and stmt['concept']}'")
        if kids(stmt, 'univVar'): raise Skip('rule with univVar')
        actie = child(stmt, 'actie')
        if actie['concept'] not in ('Gelijkstelling', 'Initialisatie'): raise Skip(f"action '{actie['concept']}'")
        target = expression(child(actie, 'links'), ctx)
        value = expression(child(actie, 'rechts'), ctx) if child(actie, 'rechts') else None
        variables = []
        for var in kids(stmt, 'var'):
            variables.append({'name': var['props']['name'], 'value': expression(child(var, 'waarde'), ctx)})
        cond = condition(child(stmt, 'conditie'), ctx) if kids(stmt, 'conditie') else None
        version = {'validity': validity(child(v, 'geldig')),
                   **({'variables': variables} if variables else {}),
                   **({'condition': cond} if cond else {}),
                   'action': {'kind': 'assignment', 'target': target,
                              **({'initial': True} if actie['concept'] == 'Initialisatie' else {}),
                              **({'value': value} if value else {})}}
        versions.append(version)
    return {'name': regel['props']['name'], 'versions': versions}

def validity(g):
    if g is None: return {}
    p = {}
    van, tm = child(g, 'van'), child(g, 'tm')
    if van is not None: p['from'] = date_of(van)
    if tm is not None:  # inclusive year/date end
        y = int(tm['props'].get('jaar')); m = tm['props'].get('maand'); d = tm['props'].get('dag')
        p['to'] = date_of(tm) if (m and d) else f"{y:04d}-12-31"
    return p

def rule_group(rg):
    rules = [rule_of(r) for r in kids(rg, 'inhoud') if r['concept'] == 'Regel']
    others = {r['concept'] for r in kids(rg, 'inhoud')} - {'Regel', 'Witruimte', 'Commentaar', 'Koptekst'}
    if others: raise Skip(f"rule group content {sorted(others)}")
    return {'name': rg['props']['name'], 'rules': rules}

# ---------- testspraak -> cases ----------
def test_cases(ts, inst_index):
    rekendatums = kids(ts, 'rekendatums')
    if not rekendatums: raise Skip('test set without rekendatum')
    calc_date = date_of(rekendatums[0])
    cases = []
    for tg in kids(ts, 'testGevallen'):
        instances, expectations, nid2id = [], [], {}
        for inst in kids(tg, 'situatie'):
            if inst['concept'] != 'Instantie': raise Skip(f"situatie '{inst['concept']}'")
            iid = f"{inst['props'].get('name') or inst['nid']}"
            nid2id[inst['nid']] = iid
            slots = {}
            for et in kids(inst, 'eigenschappen'):
                if et['concept'] != 'EigenschapToekenning': raise Skip(f"toekenning '{et['concept']}'")
                slots[ref(et, 'eigenschap')] = literal(child(et, 'waarde'))
            instances.append({'id': iid, 'entityType': ref(inst, 'type'), 'slots': slots})
        params = {}
        for pt in kids(tg, 'parameter'):  # per-case parameter values
            if pt['concept'] != 'Parametertoekenning': raise Skip(f"case parameter '{pt['concept']}'")
            params[ref(pt, 'param')] = literal(child(pt, 'waarde'))
        for res in kids(tg, 'resultaat'):
            iid = nid2id.get(refnode(res, 'instantie'))
            if iid is None and len(instances) == 1:
                iid = instances[0]['id']  # implicit: the case's single instance
            if iid is None: raise Skip('resultaat for unknown instantie')
            for uv in kids(res, 'uitvoer'):
                if uv['concept'] != 'UitvoerVoorspelling': raise Skip(f"uitvoer '{uv['concept']}'")
                expectations.append({'instance': iid, 'attribute': ref(uv, 'eigenschap'),
                                     'expected': literal(child(uv, 'waarde')),
                                     'decimals': int(uv['props'].get('decimalen', -1))})
        cases.append({'name': tg['props'].get('name', '?'), 'calculationDate': calc_date,
                      'instances': instances, 'expectations': expectations,
                      **({'parameters': params} if params else {})})
    tested = []
    for tt in kids(ts, 'teTesten'):
        if tt['concept'] == 'TeTestenRegelset':
            tested += [ref(sr, 'set') for sr in kids(tt, 'sets')]
        elif tt['concept'] == 'TeTestenRegelgroep':
            tested.append(ref(tt, 'ref'))
        else:
            raise Skip(f"teTesten '{tt['concept']}'")
    return cases, tested

# ---------- per-model extraction ----------
def parameter_sets(roots):
    sets = []
    for r in roots:
        if r['concept'] != 'Parameterset': continue
        assignments = []
        for t in kids(r, 'toekenning'):
            if t['concept'] != 'Parametertoekenning': continue
            assignments.append({'parameter': ref(t, 'param'), 'value': literal(child(t, 'waarde'))})
        sets.append({'validity': validity(child(r, 'geldig')), 'assignments': assignments})
    return sets

def extract_solution(paths, sol_name):
    """Extract fixtures from ALL models of one solution together: gegevens, regels
    and tests often live in separate .mps models of the same solution."""
    roots = []
    for p in paths:
        try:
            for r in parse(p):
                r['src'] = p
                roots.append(r)
        except ET.ParseError: pass
    oms = [r for r in roots if r['concept'] == 'ObjectModel']
    rgs = {}  # group name -> [groups]; names collide across models ('Regels'), so
    for r in roots:  # resolution prefers a group from the TestSet's own model file
        if r['concept'] == 'Regelgroep': rgs.setdefault(r['props']['name'], []).append(r)
    tss = [r for r in roots if r['concept'] == 'TestSet']
    if not (oms and rgs and tss): raise Skip('missing ObjectModel/Regelgroep/TestSet')
    psets = parameter_sets(roots)
    fixtures, skips = [], []
    for ts in tss:
        try:
            dm = {'entityTypes': [], 'domains': [], 'parameters': [], 'relationTypes': []}
            for om in oms:  # merge all object models of the solution
                d = data_model(om)
                for k in dm: dm[k] += d.get(k, [])
            cases, tested = test_cases(ts, None)
            groups = []
            for name in tested:
                cands = rgs.get(name, [])
                same = [g for g in cands if g['src'] == ts['src']]
                if same or cands: groups.append(rule_group((same or cands)[0]))
            if not groups: raise Skip(f"tests unknown rule sets {tested}")
            model = {'name': ts['props']['name'], 'dataModel': {k: v for k, v in dm.items() if v},
                     'ruleGroups': groups, **({'parameterSets': psets} if psets else {})}
            fixtures.append((ts['props']['name'], {'model': model, 'cases': cases}))
        except Skip as s:
            skips.append((f"{sol_name}::{ts['props'].get('name')}", str(s)))
    return fixtures, skips

def main():
    os.makedirs(OUT, exist_ok=True)
    import re
    from collections import Counter
    pattern = sys.argv[1] if len(sys.argv) > 1 else 'solutions/*_Test/models/*.mps'
    # Servicespraak_Test exercises the service/message boundary (mappings, DST
    # datetimes), which the core deliberately does not model — see README 'scope'.
    EXCLUDE = {'Servicespraak_Test'}
    by_solution = {}
    for path in sorted(glob.glob(os.path.join(REPO, pattern))):
        sol = path.split('solutions/')[-1].split('/')[0]
        if sol in EXCLUDE: continue
        by_solution.setdefault(sol, []).append(path)
    written, skipped = 0, []
    for sol, paths in sorted(by_solution.items()):
        try:
            fixtures, skips = extract_solution(paths, sol)
            skipped += skips
            for ts_name, fixture in fixtures:
                fname = re.sub(r'[^A-Za-z0-9._-]', '_', f"{sol}.{ts_name}") + '.json'
                with open(os.path.join(OUT, fname), 'w') as f:
                    json.dump(fixture, f, indent=1, ensure_ascii=False)
                n = sum(len(c['expectations']) for c in fixture['cases'])
                print(f"OK   {fname}  ({len(fixture['cases'])} cases, {n} expectations)")
                written += 1
        except Skip as s:
            skipped.append((sol, str(s)))
        except Exception as e:
            skipped.append((sol, f"ERROR {e}"))
    print(f"\n{written} fixtures written, {len(skipped)} test sets/solutions skipped")
    for why, cnt in Counter(w for _, w in skipped).most_common(20):
        print(f"{cnt:4d}  {why}")

if __name__ == '__main__':
    main()
