"""Latency and tokens per real model call, from the call log. No model calls.

Usage: python3 -I scripts/latency_report.py [data/llm_cache.db.calls.jsonl]
The log is written by src/voc/llm.py for every real (not cached) call, starting from 2026-11-01.
"""
import json
import statistics
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "data/llm_cache.db.calls.jsonl"
try:
    calls = [json.loads(l) for l in open(path) if l.strip()]
except OSError:
    sys.exit("No call log yet at %s. It is created by the next model call." % path)
by = {}
for c in calls:
    by.setdefault(c["model"], []).append(c)
print("%d real calls logged\n" % len(calls))
print("%-26s %6s %9s %9s %12s %12s" % ("model", "calls", "p50 (s)", "p95 (s)", "in tok/call", "out tok/call"))
for m, cs in sorted(by.items()):
    lat = sorted(c["latency_s"] for c in cs)
    p95 = lat[min(len(lat) - 1, int(0.95 * len(lat)))]
    print("%-26s %6d %9.1f %9.1f %12.0f %12.0f" % (m, len(cs), statistics.median(lat), p95,
          statistics.mean(c["input_tokens"] for c in cs), statistics.mean(c["output_tokens"] for c in cs)))
