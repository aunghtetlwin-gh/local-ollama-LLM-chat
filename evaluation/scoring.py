"""Offline scoring. Generated source is parsed as data, never compiled or executed."""
import ast
import json
import re
from decimal import Decimal, InvalidOperation

from .common import MAX_TEXT

NUMERIC = r'[+-]?(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]+)?\Z'


def normalize(text):
    # Preserve spaces/blank lines; allow CRLF and exactly one terminal newline.
    text = text.replace('\r\n', '\n')
    return text[:-1] if text.endswith('\n') else text


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    def reject(value):
        raise ValueError('Nonfinite JSON value')
    return json.loads(text, object_pairs_hook=pairs, parse_constant=reject)


def typed_equal(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(actual, dict):
        return actual.keys() == expected.keys() and all(typed_equal(actual[k], expected[k]) for k in actual)
    if isinstance(actual, list):
        return len(actual) == len(expected) and all(typed_equal(a, b) for a, b in zip(actual, expected))
    return actual == expected


def numeric_answer(text):
    lines = normalize(text).split('\n')
    if text.count('FINAL_ANSWER:') != 1 or not lines[-1].startswith('FINAL_ANSWER: '):
        raise ValueError('Missing, duplicate, or non-final answer marker')
    value = lines[-1][len('FINAL_ANSWER: '):]
    if len(value) > 1000 or not re.fullmatch(NUMERIC, value):
        raise ValueError('Invalid numeric representation')
    return Decimal(value.replace(',', ''))


def structural_code(text, reference):
    """Structural compliance only. Neither safety nor functional correctness proof."""
    tree = ast.parse(text)
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        return False
    fn = tree.body[0]
    args = fn.args
    return all([
        fn.name == reference['function'],
        [a.arg for a in args.posonlyargs + args.args] == reference['args'],
        not args.posonlyargs, not args.kwonlyargs, not args.defaults,
        args.vararg is None, args.kwarg is None, not fn.decorator_list,
        fn.returns is None, all(a.annotation is None for a in args.args),
        not any(isinstance(n, (ast.Import, ast.ImportFrom)) for n in ast.walk(tree)),
        '```' not in text,
    ])


def format_check(text, spec):
    text = normalize(text)
    if spec['type'] == 'bullets':
        lines = text.split('\n')
        return len(lines) == spec['count'] and all(x.startswith('- ') and x[2:].strip() for x in lines)
    if spec['type'] == 'sentences':
        # Controlled English passages; this is a documented heuristic, not semantic parsing.
        return bool(text) and text[-1:] in '.!?' and len(re.split(r'(?<=[.!?])\s+', text)) == spec['count']
    raise ValueError('Unknown format rule')


def score(text, reference, status='completed'):
    kind = reference['kind']
    objective = kind in {'exact', 'json', 'json_alternatives', 'numeric'}
    result = {'answer_correct': False if objective else None, 'format_compliant': False,
              'static_checks_pass': None, 'manual_review_required': not objective,
              'runtime_correctness': 'not evaluated' if kind == 'code' else 'not applicable',
              'status': status, 'details': ''}
    if status != 'completed':
        result['details'] = 'Non-completed attempt; no success credit'
        return result
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT:
        result.update(status='invalid_output', details='Empty, nontext, or oversized response')
        return result
    try:
        if kind == 'exact':
            result['answer_correct'] = result['format_compliant'] = normalize(text) == reference['expected']
        elif kind in {'json', 'json_alternatives'}:
            actual = strict_json(text)
            alternatives = reference['expected'] if kind == 'json_alternatives' else [reference['expected']]
            result['format_compliant'] = True
            result['answer_correct'] = any(typed_equal(actual, expected) for expected in alternatives)
            # Required keys, scalar types, and shape are part of the format contract.
            def shape(a, e):
                if type(a) is not type(e): return False
                if isinstance(e, dict): return a.keys() == e.keys() and all(shape(a[k], e[k]) for k in e)
                if isinstance(e, list): return len(a) == len(e) and all(shape(x,y) for x,y in zip(a,e))
                return True
            result['format_compliant'] = any(shape(actual,e) for e in alternatives)
        elif kind == 'numeric':
            actual = numeric_answer(text)
            result['format_compliant'] = True
            result['answer_correct'] = actual == Decimal(reference['expected'].replace(',', ''))
        elif kind == 'code':
            result['static_checks_pass'] = structural_code(text, reference)
            result['format_compliant'] = result['static_checks_pass']
            result['details'] = 'AST only; behavior and code safety not established; execution disabled'
        elif kind == 'manual':
            result['format_compliant'] = bool(format_check(text, reference['format']))
            result['details'] = 'Correctness/fidelity requires manual review; sentence checks are heuristic'
        else:
            raise ValueError('Unknown scoring kind')
    except (ValueError, SyntaxError, TypeError, RecursionError, InvalidOperation, OverflowError):
        if kind == 'code': result['static_checks_pass'] = False
        result['details'] = 'Malformed output or unsupported representation; no repair performed'
    return result
