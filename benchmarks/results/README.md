# Benchmark Results

This directory contains benchmark result JSON files.

## File Naming Convention

- `benchmark_YYYYMMDD_HHMMSS.json` - Timestamped benchmark runs
- `baseline.json` - Established baseline metrics (committed)

## Comparing Results

To compare against baseline:

```python
import json

with open('baseline.json') as f:
    baseline = json.load(f)

with open('benchmark_latest.json') as f:
    current = json.load(f)

# Compare results
for result in current['results']:
    baseline_result = next(
        (r for r in baseline['results'] if r['name'] == result['name']),
        None
    )
    if baseline_result:
        change = (result['mean_time_ms'] - baseline_result['mean_time_ms']) / baseline_result['mean_time_ms'] * 100
        print(f"{result['name']}: {change:+.1f}%")
```
