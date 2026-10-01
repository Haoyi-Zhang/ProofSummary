"""Clean reproduction from retained exact inputs; standard-library Python only.

Creates a new result directory outside the retained measurements, runs the unit
suite and every fixed phase, then compares semantic/count evidence. No network
access, installation, random input generation or manuscript dependency.
"""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys
import time
import resource
import re

ROOT = Path(__file__).resolve().parent
PHASES = ('interval-pilot', 'main', 'family', 'boundary')
FRONTIER_PHASES = ('frontier-regression', 'frontier-stress')


def child_limits() -> None:
    # Linux/Unix child only. Leave the invoking interpreter and paper build alone.
    resource.setrlimit(resource.RLIMIT_CPU, (180, 180))
    resource.setrlimit(resource.RLIMIT_AS, (int(2.5 * 1024**3), int(2.5 * 1024**3)))


def invoke(arguments: list[str], log: Path) -> None:
    with log.open('w') as stream:
        proc = subprocess.run([sys.executable, *arguments], cwd=ROOT,
                              stdout=stream, stderr=subprocess.STDOUT,
                              timeout=180, preexec_fn=child_limits, check=False)
    if proc.returncode:
        raise RuntimeError(f'Command failed ({proc.returncode}); see {log.name}')


def compare(source: Path, replay: Path) -> int:
    def read(path: Path) -> dict:
        with (path / 'raw.csv').open(newline='') as stream:
            return {r['id']: r for r in csv.DictReader(stream)}
    old, new = read(source), read(replay)
    if set(old) != set(new):
        raise ValueError('Reproduction changed the input selection.')
    for name in old:
        for key, value in old[name].items():
            if key.endswith('_cpu_s') or key == 'peak_rss_kib':
                continue
            if new[name][key] != value:
                raise ValueError(f'{name}: changed semantic/count field {key}')
        for folder in ('inputs', 'certificates', 'dense-certificates', 'details'):
            source_file = source / folder / (name + '.json')
            replay_file = replay / folder / (name + '.json')
            if source_file.exists() != replay_file.exists():
                raise ValueError(f'{name}: changed presence of {folder} evidence')
            if source_file.exists():
                a = json.loads(source_file.read_text())
                b = json.loads(replay_file.read_text())
                if a != b:
                    raise ValueError(f'{name}: changed {folder} evidence')
    return len(old)


def compare_tree(source: Path, replay: Path) -> int:
    old = {p.relative_to(source): p.read_bytes() for p in source.rglob('*') if p.is_file()}
    new = {p.relative_to(replay): p.read_bytes() for p in replay.rglob('*') if p.is_file()}
    if old != new:
        missing = sorted(str(k) for k in old.keys() - new.keys())
        extra = sorted(str(k) for k in new.keys() - old.keys())
        changed = sorted(str(k) for k in old.keys() & new.keys() if old[k] != new[k])
        raise ValueError(f'Changed byte-boundary evidence: missing={missing}, extra={extra}, changed={changed}')
    return len(old)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True, help='New, non-existing directory.')
    args = ap.parse_args(); out = args.out.resolve()
    if out.exists():
        raise SystemExit('Refusing to overwrite an existing output directory.')
    out.mkdir(parents=True)
    start_self = time.process_time()
    start_children = resource.getrusage(resource.RUSAGE_CHILDREN)
    try:
        invoke(['-m', 'unittest', 'discover', '-s', 'tests', '-v'], out / 'unit-tests.txt')
        unit_text = (out / 'unit-tests.txt').read_text()
        match = re.search(r'Ran (\d+) tests?', unit_text)
        if not match:
            raise ValueError('Could not recover unit-test count.')
        unit_tests = int(match.group(1))
        compared = 0
        for phase in PHASES:
            invoke(['src/replay_study.py', '--source', str(ROOT / 'results' / phase),
                    '--out', str(out / phase)], out / (phase + '.txt'))
            compared += compare(ROOT / 'results' / phase, out / phase)
        frontier_compared = 0
        for phase in FRONTIER_PHASES:
            invoke(['src/frontier_replay.py', '--source', str(ROOT / 'results' / phase),
                    '--out', str(out / phase)], out / (phase + '.txt'))
            frontier_compared += compare(ROOT / 'results' / phase, out / phase)
        invoke(['src/public_replay.py', '--source', str(ROOT / 'results' / 'public-summary-cases'),
                '--out', str(out / 'public-summary-cases')], out / 'public-summary-cases.txt')
        public_compared = compare(ROOT / 'results' / 'public-summary-cases', out / 'public-summary-cases')
        invoke(['src/mutation_study.py', '--out', str(out / 'frontier-mutations')], out / 'frontier-mutations.txt')
        retained_mutations = json.loads((ROOT / 'results' / 'frontier-mutations' / 'summary.json').read_text())
        replay_mutations = json.loads((out / 'frontier-mutations' / 'summary.json').read_text())
        if retained_mutations != replay_mutations:
            raise ValueError('Mutation-study evidence changed.')
        invoke(['src/consumer_boundary_study.py', '--out', str(out / 'consumer-boundary')], out / 'consumer-boundary.txt')
        consumer_files = compare_tree(ROOT / 'results' / 'consumer-boundary', out / 'consumer-boundary')
        consumer_summary = json.loads((out / 'consumer-boundary' / 'summary.json').read_text())
        invoke(['src/tiny_exhaustive.py', '--out', str(out / 'tiny-exhaustive')], out / 'tiny-exhaustive.txt')
        retained_tiny = json.loads((ROOT / 'results' / 'tiny-exhaustive' / 'summary.json').read_text())
        replay_tiny = json.loads((out / 'tiny-exhaustive' / 'summary.json').read_text())
        for transient in ('cpu_seconds', 'peak_rss_kib'):
            retained_tiny.pop(transient, None); replay_tiny.pop(transient, None)
        if retained_tiny != replay_tiny:
            raise ValueError('Exhaustive micro-validation evidence changed.')
        for name in ('specification.json', 'strata.csv'):
            if (ROOT / 'results' / 'tiny-exhaustive' / name).read_bytes() != (out / 'tiny-exhaustive' / name).read_bytes():
                raise ValueError('Exhaustive micro-validation detail changed: ' + name)
        tiny_cases = replay_tiny['cases']
        invoke(['src/analyze.py', '--results', str(out), '--out', str(out / 'aggregate')], out / 'analysis.txt')
        invoke(['src/frontier_analyze.py', '--results', str(out), '--out', str(out / 'frontier-aggregate')], out / 'frontier-analysis.txt')
        end_children = resource.getrusage(resource.RUSAGE_CHILDREN)
        report = {'status': 'semantic_reproduction_passed', 'cases': compared, 'frontier_cases': frontier_compared, 'public_cases': public_compared,
                  'mutation_cases': replay_mutations['mutations'], 'consumer_boundary_positive_cases': consumer_summary['positive_cases'],
                  'consumer_boundary_negative_cases': consumer_summary['negative_cases'], 'consumer_boundary_files': consumer_files,
                  'exhaustive_micro_cases': tiny_cases, 'unit_test_methods': unit_tests,
                  'unit_test_suite_passed': True, 'exact_json_evidence_equal': True,
                  'deterministic_count_fields_equal': True,
                  'timing_and_rss_equality_required': False, 'workers': 1,
                  'controller_cpu_seconds': time.process_time() - start_self,
                  'children_cpu_seconds': (end_children.ru_utime + end_children.ru_stime
                                          - start_children.ru_utime - start_children.ru_stime),
                  'children_peak_rss_kib': end_children.ru_maxrss}
        (out / 'reproduction.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
        print(json.dumps(report)); return 0
    except (OSError, RuntimeError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
        report = {'status': 'reproduction_failed', 'reason': str(exc)}
        (out / 'reproduction.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report)); return 1

if __name__ == '__main__':
    raise SystemExit(main())
