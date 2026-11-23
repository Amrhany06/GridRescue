"""Independently hand-check exported real examples with the standard library."""
import json
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    results = []
    for scope in ['sample', 'county']:
        path = ROOT / 'reports/memory' / scope / 'label_traces.json'
        traces = json.loads(path.read_text(encoding='utf-8'))
        for entry in traces:
            anchor = entry['anchor']
            start = datetime.fromisoformat(anchor['timestamp'])
            expected = {start+timedelta(minutes=15*i) for i in range(1, 13)}
            observed = {datetime.fromisoformat(r['timestamp']): r['customers_out'] for r in entry['trace']}
            assert len(observed) == len(entry['trace']), 'Duplicate key in trace'
            assert observed[start] == anchor['customers_out_t']
            future = {t: count for t, count in observed.items() if t in expected}
            assert len(future) == anchor['future_slots']
            threshold = observed[start] + max(200, 0.5*observed[start])
            assert threshold == anchor['escalation_threshold']
            assert (max(future.values()) if future else None) == anchor['future_max']
            expected_y = int(max(future.values()) >= threshold) if len(future) == 12 and observed[start] > 0 else None
            assert expected_y == anchor['candidate_y']
            results.append(dict(scope=scope, category=anchor['example_type'], fips=anchor['fips_code'], timestamp=anchor['timestamp'],
                                current=observed[start], threshold=threshold, future_slots=len(future), future_max=anchor['future_max'], y=expected_y))
    (ROOT / 'reports/real_trace_checks.json').write_text(json.dumps(results, indent=2)+'\n', encoding='utf-8')
    print(f'Independently verified {len(results)} real positive/negative/incomplete anchor traces; no missing slot treated as zero.')
    for scope in ['sample','county']:
        print(json.dumps(next(r for r in results if r['scope']==scope and r['category']=='positive')))


if __name__ == '__main__':
    main()
