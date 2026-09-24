"""Rerun one phase from exact retained mathematical inputs, not a random seed.

The original CSV controls only input order and descriptive group names. Costs,
certificates, oracle results and all measurements are recomputed by run_one.
"""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
import re
import resource
import time
from model import load
from run_study import FIELDS, run_one


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    if args.out.exists():
        raise SystemExit('Output directory must not already exist.')
    with (args.source / 'raw.csv').open(newline='') as stream:
        selection = list(csv.DictReader(stream))
    ids = [r['id'] for r in selection]
    if len(set(ids)) != len(ids) or not all(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}', name) for name in ids):
        raise SystemExit('Non-local or duplicate case identifier in retained selection.')
    for folder in ('inputs', 'certificates', 'details'):
        (args.out / folder).mkdir(parents=True, exist_ok=False)
    started = time.process_time(); rows = []
    with (args.out / 'raw.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS); writer.writeheader()
        for selected in selection:
            p = load(str(args.source / 'inputs' / (selected['id'] + '.json')))
            if p['id'] != selected['id']:
                raise SystemExit('Input identifier differs from retained selection.')
            result = run_one(p, selected['group'], args.out)
            rows.append(result); writer.writerow(result); stream.flush()
            if result['agreement'] == 'NO':
                raise SystemExit('Scientific disagreement on ' + p['id'])
    old_summary = json.loads((args.source / 'summary.json').read_text())
    summary = {'phase': old_summary['phase'], 'cases': len(rows),
               'agreement': sum(r['agreement'] == 'yes' for r in rows),
               'incomplete': sum(r['agreement'] == 'incomplete' for r in rows),
               'cpu_seconds': time.process_time() - started,
               'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, 'workers': 1}
    (args.out / 'summary.json').write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n')
    print(json.dumps(summary))
    return 0 if summary['agreement'] == summary['cases'] else 2

if __name__ == '__main__':
    raise SystemExit(main())
