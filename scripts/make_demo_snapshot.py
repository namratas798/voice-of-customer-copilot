"""Build the public demo snapshot: INVENTED reviews for a fictional app. No real review text is used.

Usage: python3 -I scripts/make_demo_snapshot.py [out.json]   (default app/demo_snapshot.json)

Every review is assembled from sentences written for this demo. Labels follow the same format and the same
severity rules as the real pipeline (src/voc/severity.py). The story in the data (performance complaints rising
after the newest version) is invented too, to show what the app does.
"""
import datetime
import json
import os
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from voc.evidence import EVIDENCE  # noqa: E402
from voc.schema import IMPACT_FLAGS  # noqa: E402
from voc.severity import derive_severity  # noqa: E402
from voc.validate import check_label  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "app" / "demo_snapshot.json")
APP = "Demo Invest (a fictional app)"
D0, D1 = datetime.date(2026, 9, 25), datetime.date(2026, 10, 30)
E = "event_described"

# category, theme name, how many reviews, rising (more reviews late in the period), phrases, (sentence, true facts)
THEMES = [
    ("performance", "App performance slow and lagging", 40, True,
     ["slow during market hours", "charts take long to load", "lag while placing orders", "app freezes at market open", "delayed price updates"],
     [("The chart takes forever to load at market open. By the time it shows up the price has already moved.", [E]),
      ("The app is very slow in the morning. Orders take ages to go through.", [E]),
      ("Laggy after the latest update. Prices do not refresh unless I restart the app.", [E, "workaround_mentioned"]),
      ("It freezes every time I open the options screen.", [E, "core_action_blocked"]),
      ("I missed my entry because the app hung for a full minute. That cost me real money.", [E, "money_lost"]),
      ("Slow, slow, slow. Please fix the speed.", [])]),
    ("charges_pricing", "High overall charges and taxes", 36, False,
     ["high brokerage charges", "hidden fees on every order", "charges and taxes too high", "platform fee keeps going up", "too many separate charges"],
     [("Every sale I make, the fees eat a big part of my profit. Too many small charges nobody explains.", [E]),
      ("Brokerage here is much higher than the other apps I tried. Not worth it for small trades.", []),
      ("Why are there so many different charges on one order? Please make it simpler.", []),
      ("The platform fee went up again this month and nobody told us.", [E]),
      ("Found extra charges on delivery trades only when I read the statement.", [E]),
      ("Taxes, brokerage and platform fee together are just too much.", [])]),
    ("payments_funds", "Withdrawal delays and stuck money", 22, False,
     ["withdrawal pending for days", "refund not received", "payment deducted but failed", "money not credited"],
     [("My withdrawal has been pending for three days and support keeps saying it is processing.", [E, "money_blocked", "core_action_blocked"]),
      ("Money left my account for the IPO application but the refund has not come back.", [E, "money_blocked"]),
      ("The UPI payment failed but the amount was deducted from my bank.", [E, "money_lost"]),
      ("Withdrawal shows success but nothing has arrived in my bank account.", [E, "money_blocked"]),
      ("Withdrawals used to be instant. Now it takes a full day.", [E])]),
    ("customer_support", "Support does not respond", 20, False,
     ["no reply to tickets", "template answers only", "nobody calls back", "support not helpful"],
     [("I raised a ticket five days ago and nobody has replied.", [E]),
      ("Customer care only sends copy paste answers and closes the ticket.", [E]),
      ("Worst support. Nobody calls back even after multiple requests.", []),
      ("Support is not helpful at all.", [])]),
    ("login_kyc_account", "Login and KYC problems", 16, False,
     ["OTP not received", "kyc stuck in verification", "repeated verification prompts", "cannot log in"],
     [("The OTP never arrives so I cannot log in to my account.", [E, "core_action_blocked"]),
      ("My KYC has been stuck at verification for two weeks.", [E, "core_action_blocked"]),
      ("It asks me to verify again every single time I open the app.", [E]),
      ("I cannot log in on the phone and it only works on the website for me.", [E, "core_action_blocked", "workaround_mentioned"])]),
    ("feature_request", "Chart and indicator requests", 16, False,
     ["more chart indicators", "trailing stop loss", "price alerts", "dark mode", "tablet landscape mode"],
     [("Please add more technical indicators to the charts.", []), ("We need a trailing stop loss option for intraday trades.", []),
      ("Would love price alerts for my watchlist.", []), ("Please add a dark mode.", []),
      ("The app does not support landscape mode on tablets.", [])]),
    ("order_execution", "Orders not executed or wrong price", 14, True,
     ["stop loss did not trigger", "order executed at wrong price", "order cancelled by itself", "target hit but sell not executed"],
     [("I placed a stop loss and it never triggered. The price kept falling and I lost a lot.", [E, "order_wrong", "money_lost"]),
      ("My order was cancelled by itself and later executed at a worse price.", [E, "order_wrong"]),
      ("The target price was hit but the sell order did not execute.", [E, "order_wrong"]),
      ("Square off happened automatically even though I had enough margin.", [E, "order_wrong"])]),
    ("fraud_money_loss_claim", "Claims of fraud or money loss", 12, False,
     ["fraud allegation", "claims money was taken", "generic scam accusation"],
     [("This app is a scam, stay away from it.", []), ("Total fraud. They only want your brokerage.", []),
      ("They took money out of my account and gave no explanation.", [E, "money_lost"]),
      ("Funds disappeared from my wallet balance and nobody could explain why.", [E, "money_lost"])]),
    ("crash_bug", "App crashes or will not open", 10, True,
     ["crashes on startup", "closes when opening orders", "app will not open"],
     [("The app crashes on startup since the last update.", [E, "core_action_blocked"]),
      ("It keeps closing when I open the orders tab.", [E, "core_action_blocked"]),
      ("The app will not open at all on my phone, even after reinstalling twice.", [E, "core_action_blocked", "workaround_mentioned"])]),
    ("feature_request", "International investing requests", 9, False,
     ["add US stocks", "international investing", "more asset types"],
     [("Please let us invest in US stocks from the app.", []), ("Add fixed deposits and bonds as options.", []),
      ("I would like to invest in international markets too.", [])]),
    ("ux_friction", "Confusing screens after the update", 9, False,
     ["sell button hard to find", "cluttered portfolio screen", "navigation changed"],
     [("After the update I cannot find the sell button anywhere.", [E]),
      ("The portfolio screen is cluttered now. Please bring back the old layout.", [E]),
      ("Too many tabs, I keep tapping the wrong thing.", [])]),
]
# themes too small to rank (fewer than 5 reviews)
EMERGING = [
    ("payments_funds", "Statement download fails", 2, ["statement download fails"], [("The monthly statement download fails every time.", [E])]),
    ("login_kyc_account", "Nominee update pending", 2, ["nominee update pending"], [("My nominee update has been pending for ten days.", [E])]),
    ("ux_friction", "Too many notifications", 3, ["too many notifications"], [("Too many promotional notifications, please let me turn them off.", [])]),
    ("payments_funds", "SIP deducted on wrong date", 2, ["SIP date wrong"], [("My SIP was deducted on the wrong date.", [E])]),
    ("crash_bug", "Duplicate order confirmations", 2, ["duplicate confirmations"], [("I got the same order confirmation three times.", [E])]),
    ("feature_request", "Regional language support", 3, ["regional language support"], [("Please add regional language support.", [])]),
    ("login_kyc_account", "Fingerprint login fails", 3, ["biometric login fails"], [("Fingerprint login stopped working after the update.", [E])]),
    ("customer_support", "Promised callback never came", 2, ["callback never happened"], [("They promised a callback and it never came.", [E])]),
]
PRAISE = [("Simple and easy to use.", "easy to use"), ("Great app for beginners.", "good for beginners"),
          ("Clean design and a smooth experience.", "clean design"), ("Quick to open and place orders.", "fast to place orders"),
          ("Very helpful for tracking my investments.", "easy tracking"), ("I love the interface.", "nice interface"),
          ("Good for long term investing.", "good for long term investing"), ("Easy to start investing.", "easy to start"),
          ("The best investing app I have used so far.", "overall satisfaction"), ("Reliable and simple.", "reliable and simple")]
OPEN_P = ["", "", "", "Honestly, ", "Been using it for a month. ", "Not happy. ", "Could you check this? "]
CLOSE_P = ["", "", "", " Please fix.", " Hope this gets better.", " Disappointed."]
OPEN_G = ["", "", "As a beginner, ", "Been using it for weeks. "]
VERSIONS = [(datetime.date(2026, 9, 25), "18.18.1"), (datetime.date(2026, 10, 5), "18.19.2"),
            (datetime.date(2026, 10, 13), "18.20.2"), (datetime.date(2026, 10, 21), "18.21.1")]
N_TOTAL = 420
rng = random.Random(11)


def pick_date(rising):
    last10 = D1 - datetime.timedelta(days=9)
    if rising and rng.random() < 0.7:
        return last10 + datetime.timedelta(days=rng.randrange(10))
    return D0 + datetime.timedelta(days=rng.randrange((D1 - D0).days + 1))


def version_for(d):
    r = rng.random()
    if r < 0.10:
        return "unknown"
    if r < 0.14:
        return rng.choice(["18.19.1", "18.20.1", "18.17.3", "18.22.1"])
    v = VERSIONS[0][1]
    for start, name in VERSIONS:
        if d >= start:
            v = name
    return v


def stars(kind):
    if kind == "problem":
        return rng.choices([1, 2, 3, 4, 5], [55, 20, 15, 7, 3])[0]
    return rng.choices([3, 4, 5], [10, 30, 60])[0]


def aspect(cat, phrase, sentence, facts, theme_key):
    imp = {k: (k in facts) for k in IMPACT_FLAGS}
    a = {"category": cat, "aspect": phrase, "sentiment": "negative", "quote": sentence, "impact": imp}
    a["severity"] = derive_severity(a)
    a["_theme"] = theme_key
    return a


def praise_aspect(sentence, phrase):
    return {"category": "praise", "aspect": phrase, "sentiment": "positive", "severity": "none", "quote": sentence,
            "impact": {k: False for k in IMPACT_FLAGS}, "_theme": None}


rows = []  # (date, score, version, text, aspects)


def lc_first(s):
    """Lower-case the first letter, except for the word I."""
    return s if s.startswith(("I ", "I'")) else s[0].lower() + s[1:]


def compose(opener, sentence, closer=""):
    """Join opener, sentence and closer. Returns (text, quote) where quote is the sentence exactly as it appears in text."""
    quote = lc_first(sentence) if opener.endswith(", ") else sentence
    return opener + quote + closer, quote


specs = [(c, n, k, r, ph, tp, "t%d" % i) for i, (c, n, k, r, ph, tp) in enumerate(THEMES)] + \
        [(c, n, k, False, ph, tp, "e%d" % i) for i, (c, n, k, ph, tp) in enumerate(EMERGING)]
for cat, name, count, rising, phrases, templates, key in specs:
    for _ in range(count):
        sentence, facts = rng.choice(templates)
        d = pick_date(rising)
        a = aspect(cat, rng.choice(phrases), sentence, facts, key)
        if rng.random() < 0.15:  # a review that praises something and also complains
            ps, pp = rng.choice(PRAISE)
            q = lc_first(sentence)
            text = ps + " But " + q + rng.choice(CLOSE_P)
            a["quote"] = q
            rows.append((d, rng.choice([3, 3, 4]), version_for(d), text.strip(), [praise_aspect(ps, pp), a]))
        else:
            text, q = compose(rng.choice(OPEN_P), sentence, rng.choice(CLOSE_P))
            a["quote"] = q
            rows.append((d, stars("problem"), version_for(d), text.strip(), [a]))
while len(rows) < N_TOTAL:
    ps, pp = rng.choice(PRAISE)
    d = D0 + datetime.timedelta(days=rng.randrange((D1 - D0).days + 1))
    text, q = compose(rng.choice(OPEN_G), ps)
    pa = praise_aspect(q, pp)
    rows.append((d, stars("praise"), version_for(d), text, [pa]))
rng.shuffle(rows)
rows.sort(key=lambda r: r[0])

reviews, aspects_out = [], []
for i, (d, score, ver, text, asp) in enumerate(rows, 1):
    rid = "demo-%04d" % i
    reviews.append({"review_id": rid, "date": d.isoformat(), "score": score, "version": ver, "text": text})
    for a in asp:
        a = dict(a)
        a["review_id"] = rid
        a["theme_id"] = None
        a["_review_text"] = text
        aspects_out.append(a)

# theme ids: rank within each category by number of distinct reviews
spec_by_key = {s[6]: s for s in specs}
reviews_in = {}
for a in aspects_out:
    if a["_theme"]:
        reviews_in.setdefault(a["_theme"], set()).add(a["review_id"])
themes, by_cat = [], {}
for key, rids in sorted(reviews_in.items(), key=lambda kv: -len(kv[1])):
    cat, name, phrases = spec_by_key[key][0], spec_by_key[key][1], spec_by_key[key][4]
    by_cat[cat] = by_cat.get(cat, 0) + 1
    tid = "%s:%d" % (cat, by_cat[cat])
    themes.append({"theme_id": tid, "category": cat, "name": name, "size": sum(1 for a in aspects_out if a["_theme"] == key),
                   "review_count": len(rids), "merged_from": 1, "status": "ranked" if len(rids) >= 5 else "emerging",
                   "samples": phrases[:4]})
    for a in aspects_out:
        if a["_theme"] == key:
            a["theme_id"] = tid

# validate: every label must pass the same checks as real labels
bad = []
for r in reviews:
    mine = [a for a in aspects_out if a["review_id"] == r["review_id"]]
    label = {"reviewId": r["review_id"], "usable": True, "overall_sentiment": "mixed" if len(mine) > 1 else mine[0]["sentiment"],
             "aspects": [{k: a[k] for k in ("category", "aspect", "sentiment", "severity", "quote")} for a in mine]}
    bad += check_label(label, r["text"])
if bad:
    sys.exit("invalid demo labels: %s" % bad[:5])
for a in aspects_out:
    a.pop("_theme"), a.pop("_review_text")

dates = sorted(r["date"] for r in reviews)
snap = {"meta": {"snapshot_date": datetime.date.today().isoformat(), "n_reviews": len(reviews), "date_from": dates[0], "date_to": dates[-1],
                 "labeler": "invented demo data", "theme_merge_model": "not used", "app": APP, "min_theme_size": 5, "demo": True,
                 "sampling": "Invented reviews for demonstration. Not real."},
        "reviews": reviews, "aspects": aspects_out, "themes": themes, "evidence": EVIDENCE}
os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
with open(OUT, "w") as f:
    json.dump(snap, f, ensure_ascii=False)
print("demo snapshot: %d invented reviews, %d aspects, %d themes (%d ranked) -> %s (%.0f KB)" %
      (len(reviews), len(aspects_out), len(themes), sum(1 for t in themes if t["status"] == "ranked"), OUT, os.path.getsize(OUT) / 1024))
