"""Draw the stratified golden-set sample (dev / test / blind-human subset).

Usage: python3 -I scripts/draw_golden_sample.py <raw_json> <out_dir>

Strips identity fields and the developer reply. Deterministic (seed 42).
"""
import csv, json, random, re, sys, collections

SEED = 42
raw_path, out_dir = sys.argv[1], sys.argv[2]
d = json.load(open(raw_path))
seen, rows = set(), []
for r in d:
    if r["reviewId"] in seen or not r["content"].strip():
        continue
    seen.add(r["reviewId"])
    rows.append({
        "reviewId": r["reviewId"],
        "content": r["content"].strip(),
        "score": r["score"],
        "appVersion": r["appVersion"] or "unknown",
        "date": r["at"][:10],
    })

HIN = set("hai nahi nhi bahut bhi kya mera mere ho hota karo kar raha rha hain h ka ki ke se mein me aur ye toh to paisa nahin accha acha bekar bakwas".split())
MONEY = re.compile(r"fraud|scam|cheat|loot|fake|hack|stole|chor|lutera|farji|loss|lost|deduct|stuck|refund|withdraw|money|paisa|paise|debit", re.I)


def words(t):
    return len(t.split())


def is_hinglish(t):
    if re.search(r"[ऀ-ॿ]", t):
        return True
    w = re.findall(r"[a-z]+", t.lower())
    return len(w) > 0 and sum(x in HIN for x in w) / len(w) >= 0.15


def stratum(r):
    t, n = r["content"], words(r["content"])
    if n >= 4 and is_hinglish(t):
        return "hinglish"
    if n >= 8 and MONEY.search(t):
        return "money_claim"
    if n >= 8 and r["score"] <= 3:
        return "substantive_neg"
    if n >= 8:
        return "substantive_pos"
    if r["score"] <= 3:
        return "short_neg"
    return "short_any"


for r in rows:
    r["stratum"] = stratum(r)

pools = collections.defaultdict(list)
for r in rows:
    pools[r["stratum"]].append(r)

# quota per split of 200
QUOTA = {"substantive_neg": 70, "substantive_pos": 30, "short_neg": 30,
         "short_any": 10, "hinglish": 30, "money_claim": 30}
rng = random.Random(SEED)
dev, test = [], []
print("stratum, pool size, drawn")
for s, q in QUOTA.items():
    pool = sorted(pools[s], key=lambda r: r["reviewId"])
    if len(pool) < 2 * q:
        sys.exit(f"pool too small for {s}: {len(pool)} < {2*q}")
    pick = rng.sample(pool, 2 * q)
    dev += pick[:q]
    test += pick[q:]
    print(f"{s}, {len(pool)}, {2*q}")

# blind human subset: 30% of each test stratum
blind = []
for s, q in QUOTA.items():
    st = [r for r in test if r["stratum"] == s]
    blind += rng.sample(st, round(0.3 * len(st)))
blind_ids = {r["reviewId"] for r in blind}
assert len(blind) == 60, len(blind)

rng.shuffle(dev)
rng.shuffle(test)
rng.shuffle(blind)

LABELER_FIELDS = ["reviewId", "content", "score", "appVersion", "date"]


def slim(r):
    return {k: r[k] for k in LABELER_FIELDS}


with open(f"{out_dir}/dev_for_ai.jsonl", "w") as f:
    for r in dev:
        f.write(json.dumps(slim(r), ensure_ascii=False) + "\n")
with open(f"{out_dir}/test_for_ai.jsonl", "w") as f:
    for r in test:
        f.write(json.dumps(slim(r), ensure_ascii=False) + "\n")
with open(f"{out_dir}/test_blind_for_human.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(LABELER_FIELDS)
    for r in blind:
        w.writerow([r[k] for k in LABELER_FIELDS])
# manifest holds strata and the blind flag. Do NOT give it to the labelers.
with open(f"{out_dir}/manifest.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["reviewId", "split", "stratum", "blind_human"])
    for r in dev:
        w.writerow([r["reviewId"], "dev", r["stratum"], 0])
    for r in test:
        w.writerow([r["reviewId"], "test", r["stratum"], int(r["reviewId"] in blind_ids)])
print("dev", len(dev), "test", len(test), "blind", len(blind))
