"""
Measures average redirect latency. Run once with USE_CACHE=0 and once with USE_CACHE=1.

Usage:
python benchmark.py         # 500 requests against http://localhost:5000
python benchmark.py 2000    # custom request count
"""
import statistics
import sys
import time

import requests

BASE = "http://localhost:5000"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 500

code = requests.post(f"{BASE}/api/shorten", json={"url": "https://example.com"}).json()["short_code"]

latencies = []
with requests.Session() as s:
    for _ in range(N):
        start = time.perf_counter()
        s.get(f"{BASE}/{code}", allow_redirects=False)
        latencies.append((time.perf_counter() - start) * 1000)

latencies.sort()
print(f"requests : {N}")
print(f"avg      : {statistics.mean(latencies):.2f} ms")
print(f"median   : {statistics.median(latencies):.2f} ms")
print(f"p95      : {latencies[int(N * 0.95) - 1]:.2f} ms")
