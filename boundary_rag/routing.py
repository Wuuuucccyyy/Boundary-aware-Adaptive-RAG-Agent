"""Four source selectors. Dynamic boundaries are per unmet task, never a blacklist."""
import re
from .text import similarity

METHODS = ('all', 'positive', 'fixed', 'dynamic')


def route(query, missing, corpus, method, config, visits):
    if method not in METHODS:
        raise ValueError(f'Unknown method: {method}')
    if method == 'all':
        return ([p['id'] for p in corpus.profiles],
                [dict(source=p['id'], profile_version=p['version'], selected=True,
                      reason='全知识库基线：每轮检索所有库。') for p in corpus.profiles])
    rows = []
    for p in corpus.profiles:
        positive = similarity(query, p['positive'] + ' ' + ' '.join(p['examples']))
        applicable = [t for t in missing if t in p['supports']] if method == 'dynamic' else []
        conflicts = [t for t in missing if t in p['unsupported']] if method == 'dynamic' else []
        uncertain = [t for t in missing if t not in p['supports'] and t not in p['unsupported']] if method == 'dynamic' else []
        static_hits = [s for s in p['fixed_negative_patterns'] if re.search(s, query, re.I)] if method == 'fixed' else []
        risk = (len(conflicts) + 0.25 * len(uncertain)) / max(1, len(missing))
        score = positive
        if method == 'fixed':
            score -= config.boundary_penalty * bool(static_hits)
        elif method == 'dynamic':
            score = (0.35 * positive + len(applicable) / max(1, len(missing))
                     - config.boundary_penalty * risk - 0.04 * visits.get(p['id'], 0))
        rows.append(dict(source=p['id'], profile_version=p['version'], positive=round(positive, 6),
                         score=round(score, 6), applicable=applicable if method == 'dynamic' else [],
                         conflicts=conflicts if method == 'dynamic' else [],
                         uncertain=uncertain if method == 'dynamic' else [],
                         static_hits=static_hits if method == 'fixed' else [],
                         evidence_refs={t: p['supports'][t] for t in applicable} if method == 'dynamic' else {},
                         selected=False, reason=''))
    ranked = sorted(rows, key=lambda r: (-r['score'], r['source']))
    if method == 'all':
        selected = [r['source'] for r in rows]
    elif method in ('positive', 'fixed'):
        # After a failed round, widen to unvisited sources, using the same baseline score.
        unvisited = [r for r in ranked if visits.get(r['source'], 0) == 0]
        selected = [r['source'] for r in (unvisited or ranked)[:config.positive_top_k]]
    else:
        remaining = set(missing)
        selected = []
        pool = ranked[:]
        while pool:
            best = max(pool, key=lambda r: (len(remaining & set(r['applicable'])), r['score'], r['source']))
            gain = remaining & set(best['applicable'])
            if not gain:
                break
            selected.append(best['source'])
            remaining -= gain
            pool.remove(best)
        if not selected:
            # Unknown is not an exclusion: perform budgeted exploration, no permanent updates.
            unvisited = [r for r in ranked if visits.get(r['source'], 0) == 0]
            selected = [r['source'] for r in (unvisited or ranked)[:1]]
    for row in rows:
        row['selected'] = row['source'] in selected
        if method == 'dynamic':
            row['reason'] = (f"当前缺口可支持={row['applicable']}；版本内不支持={row['conflicts']}；"
                             f"未核实={row['uncertain']}；得分={row['score']}；"
                             + ('选中以补足证据或探索未知。' if row['selected'] else '本轮新增覆盖不足，保留候选。'))
        elif method == 'all':
            row['reason'] = '全知识库基线：每轮检索所有库。'
        else:
            row['reason'] = f"正向得分={row['positive']}；固定冲突={row['static_hits']}；最终得分={row['score']}；按排名及未访问回退选库。"
    return selected, rows
