"""Reconcile retained raw measurements and create paper-facing derived data.

No external packages. Semantic comparisons exclude elapsed time and peak RSS.
The paper export is optional; the repository is usable without the manuscript.
"""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
from collections import Counter

PHASES = ('interval-pilot', 'main', 'family', 'boundary')
EXPECTED = {'interval-pilot': 33, 'main': 276, 'family': 320, 'boundary': 32}


def derive(root: Path) -> tuple[dict, list[dict]]:
    all_rows = []
    phases = []
    ids = set()
    for phase in PHASES:
        source = root / phase
        with (source / 'raw.csv').open(newline='') as stream:
            rows = list(csv.DictReader(stream))
        if len(rows) != EXPECTED[phase]:
            raise ValueError(f'{phase}: unexpected selection size')
        summary = json.loads((source / 'summary.json').read_text())
        if summary['cases'] != len(rows) or summary['agreement'] != len(rows) or summary['incomplete']:
            raise ValueError(f'{phase}: incomplete evidence')
        for r in rows:
            name = r['id']
            if name in ids or Path(name).name != name:
                raise ValueError('Duplicate or non-local case identifier')
            ids.add(name)
            p = json.loads((source / 'inputs' / (name + '.json')).read_text())
            cpath = source / 'certificates' / (name + '.json')
            c = json.loads(cpath.read_text())
            d = json.loads((source / 'details' / (name + '.json')).read_text())
            cells = len(p['locations']) * (1 << p['bits']) * (p['gas'] + 1) * (p['steps'] + 1)
            if p['id'] != name or c['query'] != p or cells != int(r['cells']):
                raise ValueError(name + ': query/cell mismatch')
            if cpath.stat().st_size != int(r['certificate_bytes']):
                raise ValueError(name + ': certificate size mismatch')
            k, ik, o = d['checker'], d['interval_checker'], d['oracle']
            if (k['status'], k['lower'], k['upper']) != (ik['status'], ik['lower'], ik['upper']):
                raise ValueError(name + ': checkers disagree')
            if (k['status'], k['upper']) != (o['status'], o['cost']):
                raise ValueError(name + ': oracle disagreement')
            if k['status'] not in {'optimal_bounded', 'safe_bounded'} or r['agreement'] != 'yes':
                raise ValueError(name + ': uncertified result')
            if r['status'] != k['status'] or r['cost'] != ('' if k['upper'] is None else str(k['upper'])):
                raise ValueError(name + ': raw-result mismatch')
            for field, value in [('checker_work', k['transition_obligations']),
                                 ('interval_work', ik['interval_obligations']),
                                 ('oracle_prefixes', o['prefixes']),
                                 ('error_traces', o['error_traces']),
                                 ('segments', k['segments'])]:
                if int(r[field]) != value:
                    raise ValueError(name + ': inconsistent ' + field)
            if 'intentionally_unsound_ablation' in d:
                if d['intentionally_unsound_ablation']['returned_cost'] != 9 or o['cost'] != 1:
                    raise ValueError(name + ': negative control changed')
        statuses = Counter(r['status'] for r in rows)
        entry = {'phase': phase, 'cases': len(rows), 'optimal': statuses['optimal_bounded'],
                 'safe': statuses['safe_bounded'], 'cpu_seconds': summary['cpu_seconds'],
                 'peak_rss_kib': summary['peak_rss_kib']}
        for field in ('cells', 'checker_work', 'interval_work', 'oracle_prefixes', 'segments'):
            entry[field] = sum(int(r[field]) for r in rows)
        phases.append(entry)
        all_rows.extend(rows)
    totals = {'cases': len(all_rows), 'optimal': sum(p['optimal'] for p in phases),
              'safe': sum(p['safe'] for p in phases), 'phases': phases,
              'phase_cpu_seconds': sum(p['cpu_seconds'] for p in phases),
              'peak_rss_kib': max(p['peak_rss_kib'] for p in phases)}
    for field in ('cells', 'checker_work', 'interval_work', 'oracle_prefixes', 'segments'):
        totals[field] = sum(int(r[field]) for r in all_rows)
    for field in ('cells', 'certificate_bytes', 'oracle_prefixes', 'checker_work', 'interval_work'):
        totals['max_' + field] = max(int(r[field]) for r in all_rows)
    totals['guided_fewer_expansions'] = sum(int(r['guided_expanded']) < int(r['ucs_expanded']) for r in all_rows)
    totals['guided_equal_expansions'] = sum(int(r['guided_expanded']) == int(r['ucs_expanded']) for r in all_rows)
    totals['guided_more_expansions'] = sum(int(r['guided_expanded']) > int(r['ucs_expanded']) for r in all_rows)
    totals['largest_boundary'] = next(r for r in all_rows if r['id'] == 'boundary-g128-h64')
    return totals, all_rows


def export(root: Path, out: Path, paper: Path | None = None) -> dict:
    totals, rows = derive(root)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'metrics.json').write_text(json.dumps(totals, indent=2, sort_keys=True) + '\n')
    fields = ['phase', 'cases', 'optimal', 'safe', 'cells', 'checker_work', 'interval_work',
              'oracle_prefixes', 'segments', 'cpu_seconds', 'peak_rss_kib']
    with (out / 'phase-summary.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader(); writer.writerows(totals['phases'])
    boundary = sorted((r for r in rows if r['group'] == 'resource-boundary' and r['steps'] == '64'),
                      key=lambda r: int(r['gas']))
    with (out / 'boundary-counts.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['gas', 'dense', 'interval', 'cells', 'segments'])
        writer.writerows([r['gas'], r['checker_work'], r['interval_work'], r['cells'], r['segments']] for r in boundary)
    if paper is not None:
        paper.mkdir(parents=True, exist_ok=True)
        (paper / 'boundary-counts.csv').write_bytes((out / 'boundary-counts.csv').read_bytes())
        tex = ['% Generated from retained raw measurements by artifact/src/analyze.py.']
        labels = {'interval-pilot': 'Pilot', 'main': 'Seeded extension', 'family': 'Parameter family', 'boundary': 'Resource boundary'}
        for p in totals['phases']:
            tex.append(f"{labels[p['phase']]} & {p['cases']:,} & {p['optimal']:,} & {p['safe']:,} & {p['oracle_prefixes']:,} & {p['checker_work']:,} & {p['interval_work']:,} \\\\")
        tex.append('\\midrule')
        tex.append(f"Total & {totals['cases']:,} & {totals['optimal']:,} & {totals['safe']:,} & {totals['oracle_prefixes']:,} & {totals['checker_work']:,} & {totals['interval_work']:,} \\\\")
        (paper / 'phase-rows.tex').write_text('\n'.join(tex) + '\n')
        header = [r'\begin{tabular}{lrrrrrr}', r'\toprule',
                  r'Group & Cases & Optimal & Safe & Prefixes & Dense & Interval\\', r'\midrule']
        (paper / 'phase-table.tex').write_text('\n'.join(header + tex + [r'\bottomrule', r'\end{tabular}']) + '\n')
    return totals


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--results', type=Path, default=Path('results'))
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--paper-out', type=Path)
    args = ap.parse_args()
    try:
        metrics = export(args.results, args.out, args.paper_out)
    except (OSError, ValueError, KeyError, TypeError, StopIteration) as exc:
        print(json.dumps({'status': 'inconsistent', 'reason': str(exc)})); return 1
    print(json.dumps({'status': 'reconciled', 'cases': metrics['cases'], 'optimal': metrics['optimal'], 'safe': metrics['safe']}))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
