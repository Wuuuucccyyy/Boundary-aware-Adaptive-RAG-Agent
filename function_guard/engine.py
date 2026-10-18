"""Explicit, auditable adapter for the pilot profile vocabulary.

Unknown requirements stay unknown. This module does not infer statistical facts
from data, execute documentation text, or certify statistical validity.
"""
from importlib.resources import files
import hashlib
import json
from pathlib import Path
import time

MISSING = object()
NUMERIC = {'numeric', 'integer', 'double'}
KNOWN_TYPES = NUMERIC | {'complex', 'categorical', 'binary', 'logical', 'text'}


def unknown(value):
    return value is MISSING or value is None or isinstance(value, str) and value in ('unknown', 'any')


def number(value):
    return type(value) in (int, float) and value == value and abs(value) != float('inf')


class ProfileStore:
    def __init__(self, path=None):
        text = Path(path).read_text(encoding='utf-8') if path else files('function_profiles').joinpath('pilot_v1/profiles.json').read_text(encoding='utf-8')
        records = json.loads(text)
        self.records = {r['record_id']: r for r in records}
        if len(self.records) != len(records):
            raise ValueError('Duplicate profile IDs')
        self.snapshot = hashlib.sha256(json.dumps(records, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        for record in records:
            if record['profile_target'] != 'function_input_requirements':
                raise ValueError('Unsupported profile target')


class Context:
    def __init__(self, request):
        self.parameters = request.get('parameters', {})
        self.facts = request.get('facts', {})
        self.provenance = request.get('fact_provenance', {})
        if not all(isinstance(v, dict) for v in (self.parameters, self.facts, self.provenance)):
            raise ValueError('parameters/facts/fact_provenance must be objects')
        self.parameters = dict(self.parameters)
        self.bindings = []
        self.binding_issues = []
        for key in ('center','scale','scale.'):
            value = self.parameters.get(key,MISSING)
            if number(value):
                self.parameters[key] = [value]
                self.bindings.append(dict(parameter=key,original=value,bound=[value],rule='numeric_scalar_is_length_one_vector'))
            elif isinstance(value,list) and not all(number(v) for v in value):
                self.binding_issues.append(dict(parameter=key,reason='vector_numeric_conversion_not_verified'))
        self.reads = []

    def fact(self, key):
        value = self.facts.get(key, MISSING)
        self.reads.append(dict(kind='fact', key=key, value=None if value is MISSING else value,
                               source=self.provenance.get(key, 'caller_supplied' if value is not MISSING else 'not_provided')))
        return value

    def param(self, key):
        value = self.parameters.get(key, MISSING)
        self.reads.append(dict(kind='parameter', key=key, value=None if value is MISSING else value,
                               source='explicit_binding' if value is not MISSING else 'not_bound'))
        return value


def both(states):
    return 'false' if 'false' in states else 'unknown' if 'unknown' in states else 'true'


def condition(ctx, item):
    target = item['target']
    if target == 'center_or_scale_parameter':
        values = [ctx.param(k) for k in ('center', 'scale') if k in ctx.parameters]
        if not values:
            return 'unknown'
        return 'true' if any(isinstance(v, list) for v in values) else 'unknown' if any(unknown(v) for v in values) else 'false'
    value = ctx.param(target)
    if unknown(value):
        return 'unknown'
    if target == 'centers':
        value = 'explicit_centers' if isinstance(value, list) else 'cluster_count' if number(value) else value
    if item['operator'] != 'equals':
        return 'unknown'
    # R logical parameters are not silently equated with Python integer 0/1.
    return 'true' if type(value) is type(item['value']) and value == item['value'] else 'false'


def type_result(value, allowed):
    if unknown(value) or not isinstance(value, str) or value not in KNOWN_TYPES:
        return 'unknown'
    return 'satisfied' if value in allowed else 'conflict'


def relation(values, predicate):
    if any(unknown(v) for v in values):
        return 'unknown'
    try:
        return 'satisfied' if predicate(*values) else 'conflict'
    except (ValueError, TypeError):
        return 'unknown'


def mapped_check(function, field, c, ctx):
    """Return status and an adapter explanation. Every rule keeps its claim ID."""
    attr, value = c['attribute'], c['value']
    f = ctx.fact
    if field == 'feature_type':
        if value == 'factor_two_levels':
            return relation([f('grouping_type'), f('grouping_levels')], lambda t,n: t == 'factor' and type(n) is int and n == 2), 'factor_and_two_levels'
        allowed = NUMERIC | ({'complex'} if value == 'numeric_or_complex' else set())
        if value in ('numeric', 'numeric_or_complex', 'numeric_matrix_like', 'numeric_or_coercible_to_numeric_matrix'):
            status = type_result(f('x_type'), allowed)
            if value == 'numeric_or_coercible_to_numeric_matrix' and status != 'satisfied':
                convertible = f('numeric_matrix_coercible')
                status = 'satisfied' if convertible is True else 'conflict' if convertible is False else 'unknown'
            if function == 'stats::t.test':
                present = f('y_present')
                if present is True:
                    y = type_result(f('y_type'), NUMERIC)
                    status = 'conflict' if 'conflict' in (status,y) else 'unknown' if 'unknown' in (status,y) else 'satisfied'
                elif unknown(present):
                    status = 'unknown' if status != 'conflict' else status
            return status, 'documented_type_set_membership'
    if attr == 'input_structure':
        accepted = {'x_vector_optional_y_vector': {'vector'}, 'matrix_or_data_frame': {'matrix','data_frame'},
                    'matrix_or_coercible': {'matrix','data_frame','vector'}, 'matrix_like': {'matrix','matrix_like'}}
        if value in accepted:
            actual = f('x_structure')
            if unknown(actual):return 'unknown', 'input_structure_not_provided'
            if not isinstance(actual, str):return 'unknown', 'invalid_structure_fact'
            return ('satisfied' if actual in accepted[value] else 'conflict'), 'documented_input_structure'
    if attr == 'x_and_supplied_y' and value == 'nonempty':
        x, present = f('x_length'), f('y_present')
        status = relation([x], lambda n: type(n) is int and n > 0)
        if present is True:
            y = relation([f('y_length')], lambda n: type(n) is int and n > 0)
            status = 'conflict' if 'conflict' in (status,y) else 'unknown' if 'unknown' in (status,y) else 'satisfied'
        elif unknown(present) and status != 'conflict':status = 'unknown'
        return status, 'nonempty_vectors'
    if attr == 'paired_inputs' and value == 'both_present_equal_length':
        present = f('y_present')
        if present is False:return 'conflict', 'paired_y_missing'
        return relation([present, f('x_length'), f('y_length')], lambda p,x,y: p is True and type(x) is int and type(y) is int and x == y), 'paired_presence_and_length'
    if attr == 'formula_response' and value == 'absent':
        return relation([f('formula_response_present')], lambda present: present is False), 'response_free_formula'
    if attr == 'center_or_scale_vector_length' and value == 'ncol(x)':
        names = ('center','scale.') if function == 'stats::prcomp' else ('center','scale')
        vectors = [ctx.param(k) for k in names if isinstance(ctx.parameters.get(k), list)]
        if not vectors:return 'inactive', 'no_vector_parameter'
        return relation([f('ncol')], lambda n: type(n) is int and all(len(v) == n for v in vectors)), 'parameter_vector_length_equals_ncol'
    if attr == 'initial_centers' and value == 'distinct':
        return relation([f('initial_centers_distinct')], lambda distinct: distinct is True), 'distinct_initial_centers'
    if attr == 'distinct_rows_for_initialization' and value == 'at_least_k':
        return relation([f('distinct_rows'),ctx.param('centers')], lambda n,k: type(n) is int and type(k) is int and n >= k), 'inferred_distinct_row_count'
    if attr == 'effectively_constant' and value == 'error':
        return relation([f('effectively_constant')], lambda constant: constant is False), 'documented_error_condition'
    if attr == 'infinite_input':
        actual = f('has_infinite')
        return ('warning' if actual is True else 'unknown' if unknown(actual) else 'informational'), 'documented_unhelpful_result_warning'
    if attr == 'unassigned_initial_center' and value == 'error':
        actual = f('centers_no_assigned_points')
        return ('conflict' if actual is True else 'unknown' if unknown(actual) else 'satisfied'), 'documented_empty_center_error'
    if attr == 'very_close_rows':
        actual = f('rows_extremely_close')
        return ('warning' if actual is True else 'unknown' if unknown(actual) else 'informational'), 'possible_nonconvergence_not_hard_rejection'
    return 'informational' if c['strength'] in ('behavior','supported','recommendation','warning') else 'unknown', 'descriptive_claim_no_additional_execution_rule'


def evaluate(request, store=None, max_checks=80):
    started = time.perf_counter()
    store = store or ProfileStore()
    function = request['function_id']
    if function not in store.records:raise ValueError('Unknown function ID')
    if type(max_checks) is not int or max_checks < 1:raise ValueError('Invalid check budget')
    record = store.records[function]
    ctx = Context(request)
    methods = {'stats::t.test':{'default','formula'},'stats::prcomp':{'default','formula'},'stats::kmeans':{'default'},'base::scale':{'default'}}
    if record['selection']['keep'] and (not isinstance(ctx.parameters.get('method'),str) or ctx.parameters['method'] not in methods.get(function,set())):
        ctx.binding_issues.append(dict(parameter='method',reason='interface_not_bound_or_not_supported_by_adapter'))
    evidence = {e['id']:e for e in record['evidence']}
    sources = {s['id']:s for s in record['document_sources']}
    results = []
    consumed = 0
    exhausted = False
    focus = set(request.get('focus_claim_ids', []))
    known_ids = {c['id'] for g in record['data_profile'].values() for c in g}
    if focus - known_ids:raise ValueError('Unknown focus claim ID')
    if record['selection']['keep']:
        for field, claims in record['data_profile'].items():
            for c in claims:
                if consumed >= max_checks:
                    exhausted = True
                    break
                consumed += 1
                at = len(ctx.reads)
                conditions = c['applies_when']
                # The source's virtual name refers to two different real R names.
                if c['attribute'] == 'center_or_scale_vector_length':
                    names = ('center','scale.') if function == 'stats::prcomp' else ('center','scale')
                    active = 'true' if any(isinstance(ctx.parameters.get(k),list) for k in names) else 'unknown' if any(unknown(ctx.parameters.get(k,MISSING)) for k in names) else 'false'
                else:
                    active = both([condition(ctx, w) for w in conditions])
                critical = c['strength'] == 'required' or c['id'] in focus
                if c['attribute'] == 'effectively_constant':critical = True
                if active == 'false':
                    status, why = 'inactive', 'parameter_branch_not_active'
                    critical = False
                elif active == 'unknown':
                    status, why = 'unknown', 'parameter_branch_unknown'
                elif c['basis'] in ('unknown','not_assessed'):
                    status, why = 'unknown', c['reason']
                    if field == 'missing_data_handling':
                        missing = ctx.fact('has_missing')
                        if c['attribute'] == 'all_missing_or_degenerate_column':
                            critical = critical or missing is True and ctx.fact('all_missing_column') is not False or ctx.facts.get('constant_columns') is True
                        else:
                            critical = critical or missing is True or unknown(missing)
                    # Other unknowns do not automatically gate unrelated operations.
                elif c['basis'] == 'conflict':
                    status, why = 'documentation_conflict', c['reason']
                    if c['attribute'] == 'degenerate_column_scaling_rule':
                        enabled = ctx.param('scale.')
                        zero, constant = ctx.fact('zero_columns'), ctx.fact('constant_columns')
                        critical = critical or enabled is True and (zero is not False or constant is not False)
                else:
                    status, why = mapped_check(function, field, c, ctx)
                if c['basis'] == 'inferred' and status == 'conflict':
                    status, why = 'unknown', 'inferred_constraint_requires_confirmation'
                    critical = True
                # Documented error conditions can block the affected configuration.
                if c['attribute'] == 'unassigned_initial_center' and active != 'false':critical = True
                if status == 'conflict' and c['basis'] != 'documented':status = 'unknown'
                value = c['value']
                refs = []
                for eid in c['evidence_ids']:
                    e = evidence[eid]
                    refs.append(dict(claim_id=c['id'],evidence_id=eid,section=e['section'],quote=e['quote'],
                                     source_id=e['source_id'],url=sources[e['source_id']]['url'],sha256=sources[e['source_id']]['sha256']))
                results.append(dict(claim_id=c['id'],field=field,attribute=c['attribute'],value=value,
                                    basis=c['basis'],strength=c['strength'],active=active,status=status,
                                    critical=critical,reason=why,observations=ctx.reads[at:],evidence=refs))
            if exhausted:break
    if not record['selection']['keep']:
        state, action = 'excluded', 'do_not_route'
    elif any(r['status'] == 'conflict' for r in results):
        state, action = 'conflict', 'block_configuration'
    elif exhausted:
        state, action = 'unknown', 'budget_exhausted'
    elif ctx.binding_issues:
        state, action = 'unknown', 'clarify_binding'
    elif any(r['critical'] and r['status'] in ('unknown','documentation_conflict') for r in results):
        state, action = 'unknown', 'clarify_or_review'
    else:
        state = 'applicable'
        action = 'proceed_with_warnings' if any(r['status']=='warning' for r in results) else 'proceed_with_documented_scope'
    return dict(function_id=function,state=state,action=action,profile_snapshot=store.snapshot,
                profile_review_status=record['review_status'],parameters=ctx.parameters,
                parameter_bindings=ctx.bindings,binding_issues=ctx.binding_issues,
                selection=record['selection'],checks=results,profile_conflicts=record['conflicts'],
                budget=dict(max_checks=max_checks,checks_used=consumed,exhausted=exhausted),
                metrics=dict(fact_reads=len(ctx.reads),elapsed_ms=(time.perf_counter()-started)*1000),
                scope='documented_input_constraints_only_not_statistical_validity_or_R_execution')
