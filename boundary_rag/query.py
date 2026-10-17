"""Rule-based task parser, independent of evaluation labels and source IDs."""
import re


def decompose(query: str, task_definitions: list[dict]) -> list[str]:
    if not query.strip():
        raise ValueError('Query must not be empty')
    # Keep unknown clauses: a known subquestion must not hide a separate unknown one.
    clauses = [c.strip(' 。？！?！') for c in re.split(r'[，,；;]|以及|并且|同时|另外', query)]
    result = []
    for clause in filter(None, clauses):
        found = []
        for task in task_definitions:
            for pattern in task['patterns']:
                if all(re.search(group, clause, re.I) for group in pattern):
                    found.append(task['id'])
                    break
        # Topic inheritance is only used for short follow-up clauses with an intent.
        if not found and clause != query:
            for task in task_definitions:
                for pattern in task.get('inherit_patterns', []):
                    if re.search(pattern[0], query, re.I) and re.search(pattern[1], clause, re.I):
                        found.append(task['id'])
                        break
        result.extend(found or ['unknown:' + clause])
    return list(dict.fromkeys(result))
