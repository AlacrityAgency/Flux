"""Snapshot-only extraction, typed source bindings, sparse lexical index and graph."""
import ast
from collections import defaultdict
from dataclasses import asdict
import json
import re
from time import perf_counter
import numpy as np
from sklearn.feature_extraction.text import CountVectorizer
from contracts import Source, Unit, Relation, dumps, digest, normalize, terms, tokens

PARSER_VERSION = 'v5.1-ast-json-records'
TRUSTED_ROLES = {'contract', 'config', 'canonical', 'runtime_receipt'}

def typed(value, kind):
    if kind == 'integer':
        return type(value) is int
    if kind == 'number':
        return type(value) in (int, float) and np.isfinite(value)
    if kind in ('string', 'entity_ref'):
        return type(value) is str
    if kind == 'boolean':
        return type(value) is bool
    if kind == 'literal_set':
        return type(value) is list and all(type(x) in (str, int, float, bool) for x in value)
    if kind == 'quantity':
        return (type(value) is dict and set(value) == {'amount', 'unit'}
                and type(value['amount']) in (int, float) and np.isfinite(value['amount'])
                and type(value['unit']) is str)
    return False

def infer_type(value):
    return {bool: 'boolean', int: 'integer', float: 'number', str: 'string'}.get(type(value), '')

def canonical_sources(records, project, epoch):
    by_id = defaultdict(list)
    for s in records:
        if s.project == project and s.epoch == epoch:
            by_id[s.source_id].append(s)
    result = []
    for key in sorted(by_id):
        rows = by_id[key]
        revision = max(s.revision for s in rows)
        current = [s for s in rows if s.revision == revision]
        if len({digest(asdict(s)) for s in current}) > 1:
            raise ValueError('Conflicting source revisions: ' + key)
        s = current[0]
        # A latest tombstone/proposal never resurrects an older verified value.
        if s.status == 'verified':
            result.append(s)
    return result

def extract(source):
    lines = source.text.splitlines()
    source_hash = digest(source.text)
    units = []
    serial = 0

    def add(start, end, entity='', field='', value=None, value_type='', proof='text_excerpt'):
        nonlocal serial
        if not lines or end < start:
            return
        serial += 1
        units.append(Unit(source.source_id + ':' + str(serial), source.source_id, source_hash,
                          start, end, '\n'.join(lines[start-1:end]), entity, field, value,
                          value_type, proof, source.role, source.namespace))

    if source.format == 'python':
        try:
            tree = ast.parse(source.text)
        except SyntaxError:
            tree = None
        if tree is not None:
            def walk(body, scope=''):
                for node in body:
                    if not hasattr(node, 'lineno'):
                        continue
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        entity = '.'.join(x for x in (scope, node.name) if x)
                        start = min([node.lineno] + [d.lineno for d in node.decorator_list])
                        # Header includes decorators, annotations and multiline signatures.
                        header_end = node.body[0].lineno - 1 if node.body else node.end_lineno
                        header_end = max(start, header_end)
                        header = '\n'.join(lines[start-1:header_end])
                        add(start, header_end, entity, value=header, value_type='string', proof='definition')
                        walk(node.body, entity)
                    elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                        annotation = node.annotation
                        if isinstance(annotation, ast.Subscript) and (isinstance(annotation.value, ast.Name)
                                and annotation.value.id == 'Literal' or isinstance(annotation.value, ast.Attribute)
                                and annotation.value.attr == 'Literal'):
                            try:
                                raw = ast.literal_eval(annotation.slice)
                                value = list(raw if isinstance(raw, tuple) else (raw,))
                                add(node.lineno, node.end_lineno, scope or 'module', node.target.id,
                                    value, 'literal_set', 'contract_literal')
                                continue
                            except (ValueError, TypeError):
                                pass
                        try:
                            value_node = node.value
                            if isinstance(value_node, ast.Call) and isinstance(value_node.func, ast.Name) and value_node.func.id == 'Field':
                                value_node = next((k.value for k in value_node.keywords if k.arg == 'default'), None)
                            value = ast.literal_eval(value_node)
                            kind = infer_type(value)
                        except (ValueError, TypeError):
                            kind = ''
                        add(node.lineno, node.end_lineno, scope or 'module', node.target.id,
                            value if kind else None, kind, 'typed_fact' if kind else 'definition')
                    elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                        try:
                            value = ast.literal_eval(node.value)
                            kind = infer_type(value)
                        except (ValueError, TypeError):
                            value, kind = None, ''
                        add(node.lineno, node.end_lineno, scope or 'module', node.targets[0].id,
                            value if kind else None, kind, 'typed_fact' if kind else 'definition')
                    else:
                        add(node.lineno, node.end_lineno, scope, proof='text_excerpt')
            walk(tree.body)
            return units
    if source.format == 'json':
        try:
            data = json.loads(source.text)
        except ValueError:
            data = None
        if isinstance(data, dict):
            for entity, fields in data.items():
                if isinstance(fields, dict):
                    for key, value in fields.items():
                        kind = source.schema.get(key, '')
                        if typed(value, kind):
                            add(1, len(lines), entity, key, value, kind, 'typed_fact')
            if units:
                return units
    grammar = re.compile(r'^\s*([^\s:]+)\s+([^\s:]+)\s*:\s*(.*?)\s*$')
    for line_no, line in enumerate(lines, 1):
        match = grammar.match(line)
        if match and match[2] in source.schema:
            kind = source.schema[match[2]]
            try:
                value = json.loads(match[3])
            except ValueError:
                value = match[3] if kind in ('string', 'entity_ref') else None
            if typed(value, kind):
                add(line_no, line_no, match[1], match[2], value, kind, 'typed_fact')
                continue
        if line.strip():
            add(line_no, line_no)
    return units

class Snapshot:
    def __init__(self, records, project='experiment', epoch='1', aliases=None):
        start = perf_counter()
        self.project, self.epoch = project, epoch
        self.sources = tuple(canonical_sources(records, project, epoch))
        self.aliases = {normalize(k): v for k, v in (aliases or {}).items()}
        self.units = tuple(u for s in self.sources for u in extract(s))
        self.by_id = {u.unit_id: u for u in self.units}
        self.source_map = {s.source_id: s for s in self.sources}
        self.cost = {u.unit_id: tokens(dumps(asdict(u))) + 1 for u in self.units}
        self.entities = defaultdict(set)
        self.fields = defaultdict(list)
        self.facts = defaultdict(list)
        self.definitions = defaultdict(list)
        for u in self.units:
            if u.entity:
                self.entities[normalize(u.entity)].add(u.namespace)
            if u.field:
                self.fields[normalize(u.field)].append(u.unit_id)
                self.facts[(normalize(u.entity), normalize(u.field))].append(u.unit_id)
            if u.proof_kind == 'definition' and not u.field and u.value_type == 'string':
                self.definitions[normalize(u.entity)].append(u.unit_id)
        self.relations = []
        by_source = defaultdict(list)
        for u in self.units:
            by_source[u.source_id].append(u)
        for rows in by_source.values():
            for a, b in zip(rows, rows[1:]):
                self.relations.append(Relation(a.unit_id, b.unit_id, 'adjacent'))
            headers = {u.entity: u for u in rows if u.proof_kind == 'definition' and not u.field and u.value_type == 'string'}
            for u in rows:
                parent = headers.get(u.entity)
                if parent is not None and parent.unit_id != u.unit_id:
                    self.relations.append(Relation(parent.unit_id, u.unit_id, 'containment'))
        entity_units = defaultdict(list)
        for u in self.units:
            if u.entity:
                entity_units[(u.namespace, normalize(u.entity))].append(u)
        for u in self.units:
            if u.value_type == 'entity_ref':
                target = normalize(u.value)
                matches = entity_units.get((u.namespace, target), ())
                for v in matches:
                    self.relations.append(Relation(u.unit_id, v.unit_id, 'explicit_reference'))
        # Bare-name function calls are resolved only against unique module definitions
        # in the same source. Attribute calls and unresolved mentions remain unclaimed.
        for source in self.sources:
            if source.format != 'python':
                continue
            try: tree = ast.parse(source.text)
            except SyntaxError: continue
            local = {u.entity: u for u in by_source[source.source_id]
                     if u.entity and '.' not in u.entity and u.proof_kind == 'definition' and u.value_type == 'string'}
            rows = by_source[source.source_id]
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in local:
                    owners = [u for u in rows if u.line_start <= node.lineno <= u.line_end]
                    if len(owners) == 1:
                        self.relations.append(Relation(owners[0].unit_id, local[node.func.id].unit_id, 'resolved_reference'))
        self.edges = defaultdict(list)
        for r in self.relations:
            self.edges[r.left].append(r)
        self.vectorizer = None
        self.bm25 = None
        if self.units:
            vectorizer = CountVectorizer(analyzer=terms, dtype=np.float32)
            try:
                matrix = vectorizer.fit_transform([u.text for u in self.units]).tocsr()
                lengths = np.asarray(matrix.sum(axis=1)).ravel()
                df = np.bincount(matrix.indices, minlength=matrix.shape[1])
                idf = np.log(1 + (len(self.units) - df + .5) / (df + .5))
                rows = np.repeat(np.arange(len(self.units)), np.diff(matrix.indptr))
                matrix.data = matrix.data * 2.2 / (matrix.data + 1.2 * (.25 + .75 * lengths[rows] / max(1, lengths.mean()))) * idf[matrix.indices]
                self.vectorizer, self.bm25 = vectorizer, matrix
            except ValueError as error:
                if 'empty vocabulary' not in str(error):
                    raise
        self.hash = digest({'parser': PARSER_VERSION, 'project': project, 'epoch': epoch,
                            'sources': [asdict(s) for s in self.sources], 'aliases': self.aliases})
        self.build_ms = (perf_counter() - start) * 1000

    def lexical(self, queries, k=4):
        if self.vectorizer is None:
            return [[] for _ in queries]
        # Sparse matrix for all public criteria; materialize only nonzero candidates.
        q = self.vectorizer.transform(queries)
        q.data[:] = 1
        scores = (q @ self.bm25.T).tocsr()
        results = []
        for row in range(len(queries)):
            a, b = scores.indptr[row:row+2]
            values = scores.data[a:b]
            order = np.argsort(-values, kind='stable')[:k]
            results.append([(self.units[int(scores.indices[a+i])].unit_id, float(values[i])) for i in order])
        return results

    def resolve(self, need, role_required=True):
        if need.proof_kind == 'definition' and not need.field:
            ids = self.definitions.get(normalize(need.entity), ())
        else:
            ids = self.facts.get((normalize(need.entity), normalize(need.field)), ()) if need.entity else self.fields.get(normalize(need.field), ())
        allowed_roles = TRUSTED_ROLES | {'code'} if need.proof_kind == 'definition' else TRUSTED_ROLES
        candidates = [self.by_id[i] for i in ids if (not need.namespace or self.by_id[i].namespace == need.namespace)
                      and (not need.value_type or self.by_id[i].value_type == need.value_type)
                      and self.by_id[i].proof_kind == need.proof_kind
                      and (not role_required or self.by_id[i].role in allowed_roles)]
        identities = {(u.namespace, u.entity) for u in candidates}
        if len(identities) > 1:
            return [], 'ambiguous'
        if len({dumps(u.value) for u in candidates}) > 1:
            return [], 'conflict'
        return candidates, 'resolved' if candidates else 'missing'

    def is_current_unit(self, public):
        unit = self.by_id.get(public.get('unit_id'))
        return unit is not None and asdict(unit) == public
