import concurrent.futures
import requests
import time

BASE_URL = "http://13.211.112.66:8080"

def hit(i):
    try:
        start = time.time()
        r = requests.get(f"{BASE_URL}/health")
        delay = time.time() - start
        return f"Req {i}: {r.status_code} in {round(delay,3)}s"
    except:
        return f"Req {i}: FAILED"

print("Running 20 concurrent requests...\n")

with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
    results = list(ex.map(hit, range(20)))

ok = 0
for r in results:
    print(r)
    if "200" in r:
        ok += 1

print("\n------------------")
print(f"Success: {ok}/20")

if ok == 20:
    print("✅ PASS")
else:
    print("❌ FAIL")