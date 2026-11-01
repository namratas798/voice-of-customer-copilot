"""Voice of Customer Copilot: a PM-facing view of a frozen snapshot of Groww Play Store reviews.

Run from the project root:  .venv/bin/streamlit run app/streamlit_app.py
"""
import datetime
import os
import pathlib
import sys

import pandas as pd
import streamlit as st

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from voc import appdata  # noqa: E402
from voc.env import load_dotenv  # noqa: E402
from voc.schema import SEV_WEIGHT  # noqa: E402

load_dotenv(str(ROOT / ".env"))
try:  # on a host the key lives in its secrets, never in the code
    if not os.environ.get("GROQ_API_KEY") and "GROQ_API_KEY" in st.secrets:
        os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
except Exception:
    pass
st.set_page_config(page_title="Voice of Customer Copilot", page_icon="📣", layout="wide")


REAL, DEMO = ROOT / "app" / "snapshot.json", ROOT / "app" / "demo_snapshot.json"
SNAP_PATH = DEMO if (os.environ.get("VOC_DEMO") == "1" or not REAL.exists()) else REAL


@st.cache_data
def get_snapshot(path, mtime):
    return appdata.load(path)


snap = get_snapshot(str(SNAP_PATH), os.path.getmtime(SNAP_PATH))
meta = snap["meta"]
SEV_ICON = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "⚪", "none": "⚪"}


DAILY_LIVE_LIMIT = 40  # live model calls per day across all visitors, to protect the free allowance


@st.cache_resource
def live_budget():
    return {"day": None, "used": 0}


def take_live_call():
    b, today = live_budget(), datetime.date.today().isoformat()
    if b["day"] != today:
        b["day"], b["used"] = today, 0
    if b["used"] >= DAILY_LIVE_LIMIT:
        return False
    b["used"] += 1
    return True


def show_reviews(items):
    """Real review text, one block per review."""
    for it in items:
        st.markdown("%s **%s** · %d star · %s · v%s" % (SEV_ICON[it["severity"]], it["severity"], it["stars"], it["date"], it["version"]))
        st.write(it["text"])
        for a in it["aspects"]:
            st.caption("Problem: %s" % a["phrase"])
        st.divider()


# ---------------------------------------------------------------- sidebar
st.sidebar.header("Filters")
d0, d1 = datetime.date.fromisoformat(meta["date_from"]), datetime.date.fromisoformat(meta["date_to"])
picked = st.sidebar.date_input("Review dates", value=(d0, d1), min_value=d0, max_value=d1)
start, end = (picked[0], picked[1]) if isinstance(picked, (tuple, list)) and len(picked) == 2 else (d0, d1)
start_s, end_s = start.isoformat(), end.isoformat()
WEIGHT_MODES = {"A mix of both": dict(SEV_WEIGHT),
                "The most serious problems": {"critical": 25, "high": 8, "medium": 2, "low": 1, "none": 0},
                "The most complaints": {"critical": 1, "high": 1, "medium": 1, "low": 1, "none": 0}}
mode = st.sidebar.radio("What should come first?", list(WEIGHT_MODES),
                        help="Changes how the list is ordered. 'The most serious problems' puts critical issues on top even if few "
                             "people mention them. 'The most complaints' just counts reviews.")
weights = WEIGHT_MODES[mode]
min_size = st.sidebar.slider("Show a theme only if it has at least this many reviews", 3, 15, meta["min_theme_size"])
all_cats = sorted({t["category"] for t in snap["themes"]})
cats = st.sidebar.multiselect("Categories", all_cats, default=all_cats)

# ---------------------------------------------------------------- header
st.title("📣 Voice of Customer Copilot")
st.caption("%s · %d reviews · %s to %s" % (meta["app"], meta["n_reviews"], meta["date_from"], meta["date_to"]))

if meta.get("demo"):
    st.info("Demo data: what you see is invented, for a fictional app. The accuracy figures on 'How reliable is this?' "
            "are real, but they come from real data I keep private.")

tabs = st.tabs(["Weekly brief", "What to fix", "Theme detail", "Releases", "How reliable is this?", "Try it on a review"])
rows, trend_ok = appdata.ranking(snap, start_s, end_s, weights, min_size, cats)
head = appdata.headline(snap, start_s, end_s)

# ---------------------------------------------------------------- weekly brief
with tabs[0]:
    period = st.radio("Period", ["Last 7 days", "Last 14 days", "Whole sample"], index=1, horizontal=True)
    days = {"Last 7 days": 7, "Last 14 days": 14}.get(period)
    b_end = d1
    b_start = max(d0, d1 - datetime.timedelta(days=days - 1)) if days else d0
    brief = appdata.build_brief(snap, b_start.isoformat(), b_end.isoformat(), weights, min_size)
    problems = appdata.check_brief(snap, brief)
    if problems:
        st.error("This brief failed its own checks and should not be sent: " + "; ".join(problems))
    brief_md = appdata.render_markdown(brief)
    st.markdown(brief_md)
    st.download_button("Download this brief", brief_md, file_name="weekly_brief_%s.md" % b_end.isoformat(), mime="text/markdown")

# ---------------------------------------------------------------- tab 1
with tabs[1]:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Reviews", head["reviews"])
    c2.metric("Average rating", "%.2f" % head["avg_rating"])
    c3.metric("1 to 2 star share", "%.0f%%" % (100 * head["negative_share"]))
    c4.metric("Reviews with a problem", head["problem_reviews"])
    ranked = [r for r in rows if r["status"] == "ranked"]
    emerging = [r for r in rows if r["status"] == "emerging"]
    st.subheader("What to fix first")
    if ranked:
        def serious(r):
            mix = appdata.theme_detail(snap, r["theme_id"], start_s, end_s)["severity_mix"]
            return mix.get("critical", 0) + mix.get("high", 0)

        df = pd.DataFrame([{"#": i, "Theme": r["name"], "Category": r["category"], "Reviews": r["reviews"],
                            "Critical or high": serious(r), "Share of reviews": r["share"] * 100,
                            "Rating lift if fixed": r["rating_drag"], "Trend": ("%.1fx" % r["trend"]) if trend_ok else "n/a",
                            "Priority score": round(r["priority"], 1)} for i, r in enumerate(ranked, 1)])
        st.dataframe(df, hide_index=True, use_container_width=True, column_config={
            "Share of reviews": st.column_config.NumberColumn(format="%.1f%%"),
            "Critical or high": st.column_config.NumberColumn(help="Reviews in this theme that I rate critical or high."),
            "Rating lift if fixed": st.column_config.NumberColumn(format="+%.3f stars",
                help="How much the average rating would go up if these reviews were as happy as everyone else's."),
            "Priority score": st.column_config.NumberColumn(help="How many people complain times how serious it is. Higher means fix sooner.")})
        st.caption("Priority score = how many people complain × how serious it is. Higher means fix sooner.")
        st.bar_chart(df.rename(columns={"Priority score": "Priority"}), x="Theme", y="Priority", horizontal=True, sort="-Priority")
        if any(r["category"] == "fraud_money_loss_claim" for r in ranked):
            st.warning("Fraud and money-loss themes are what reviewers claim, not verified facts.")
    else:
        st.write("No theme has %d or more reviews in this range." % min_size)
    if emerging:
        st.divider()
        if st.toggle("Show emerging themes (%d, fewer than %d reviews each)" % (len(emerging), min_size)):
            for r in emerging:
                with st.expander("%s (%s): %d review%s" % (r["name"], r["category"], r["reviews"], "" if r["reviews"] == 1 else "s")):
                    show_reviews(appdata.theme_detail(snap, r["theme_id"], start_s, end_s)["reviews"])

# ---------------------------------------------------------------- tab 2
with tabs[2]:
    options = {"%s: %s (%d reviews)" % (r["category"], r["name"], r["reviews"]): r for r in rows}
    if not options:
        st.write("Nothing to show for these filters.")
    else:
        choice = st.selectbox("Theme", list(options))
        r = options[choice]
        det = appdata.theme_detail(snap, r["theme_id"], start_s, end_s)
        st.markdown("**%s** · %s · %d reviews" % (r["name"], r["category"], r["reviews"]))
        left, right = st.columns(2)
        with left:
            st.caption("Severity")
            mix = det["severity_mix"]
            order = ["critical", "high", "medium", "low", "none"]
            st.bar_chart(pd.DataFrame({"Severity": order, "Reviews": [mix.get(k, 0) for k in order]}),
                         x="Severity", y="Reviews", sort=False)
        with right:
            st.caption("Reviews per week")
            if det["by_week"]:
                st.bar_chart(pd.DataFrame({"Week": list(det["by_week"]), "Reviews": list(det["by_week"].values())}),
                             x="Week", y="Reviews", sort=False)
        st.caption("App versions: " + ", ".join("%s (%d)" % kv for kv in list(det["by_version"].items())[:8]))
        st.subheader("What reviewers wrote")
        show_all = st.checkbox("Show all reviews (otherwise the 8 most severe)")
        show_reviews(det["reviews"] if show_all else det["reviews"][:8])

# ---------------------------------------------------------------- tab 3
with tabs[3]:
    rt = appdata.release_table(snap)
    st.subheader("Did a new version make things worse?")
    st.caption("Compared only when both versions have %d or more reviews." % rt["min_n"])
    vdf = pd.DataFrame([{"Version": v["version"], "Reviews": v["reviews"], "Average rating": round(v["avg_rating"], 2),
                         "1 to 2 star share": v["negative_share"] * 100} for v in rt["versions"] if v["reviews"] >= 5])
    st.dataframe(vdf, hide_index=True, use_container_width=True,
                 column_config={"1 to 2 star share": st.column_config.NumberColumn(format="%.0f%%")})
    comps = [c for c in rt["comparisons"] if c["subject"] == "negative_share"]
    if comps:
        st.dataframe(pd.DataFrame([{"From": c["baseline"], "To": c["version"], "Reviews (before / after)": "%d / %d" % (c["n_base"], c["n_new"]),
                                    "1 to 2 star share before": c["share_base"] * 100, "after": c["share_new"] * 100,
                                    "Result": c["why"]} for c in comps]), hide_index=True, use_container_width=True,
                     column_config={"1 to 2 star share before": st.column_config.NumberColumn(format="%.0f%%"),
                                    "after": st.column_config.NumberColumn(format="%.0f%%")})
    flagged = [c for c in rt["comparisons"] if c["flag"]]
    if flagged:
        for c in flagged:
            st.error("%s went from %.0f%% to %.0f%% between %s and %s" %
                     (c["subject"], 100 * c["share_base"], 100 * c["share_new"], c["baseline"], c["version"]))
    else:
        st.success("No version stands out as worse.")
    u = rt["unknown"]
    st.warning("%d reviews have no app version (%s are 1 to 2 stars), so I left them out of the comparison." %
               (u["n"], "n/a" if u["negative_share"] is None else "%.0f%%" % (100 * u["negative_share"])))

# ---------------------------------------------------------------- tab 4
with tabs[4]:
    ev = snap["evidence"]
    st.subheader("How reliable is this?")
    s = ev["severity_fresh_validation"]
    st.markdown("**Severity**")
    st.caption("Checked on 30 reviews I rated myself.")
    a, b, c, d = st.columns(4)
    a.metric("Critical issues caught (recall)", s["critical_recall"], help="Of the reviews I rated critical, how many the model also called critical.")
    b.metric("Critical calls that were right (precision)", s["critical_precision"], help="Of the reviews the model called critical, how many I also rated critical.")
    c.metric("Exact severity match (accuracy)", s["exact_agreement"], help="How often the model and I picked the same level.")
    d.metric("Off by at most one level (±1 accuracy)", s["within_one_level"], help="Severity has 5 levels: none, low, medium, high, critical. This is how often the model and I differ by one level at most.")
    x = ev["extraction_vs_ai_labels"]
    st.markdown("**Reading the reviews**")
    st.caption("Checked on 200 reviews against reference labels.")
    p1, p2, p3 = st.columns(3)
    p1.metric("Problem-finding (precision)", x["aspect_precision"], help="Of the problems the model found, how many are in the reference labels. Low means it invents problems.")
    p2.metric("Problem-finding (recall)", x["aspect_recall"], help="Of the problems in the reference labels, how many the model found. Low means it misses problems.")
    p3.metric("Problem-finding score (F1)", x["aspect_f1"], help="One number balancing precision and recall: 2 × precision × recall ÷ (precision + recall). 1.0 is perfect.")
    q1, q2, q3 = st.columns(3)
    q1.metric("Category score (macro F1)", x["category_macro_f1"], help="F1 worked out for each category, then averaged equally, so small categories count as much as big ones.")
    q2.metric("Sentiment agreement (Cohen's kappa)", x["sentiment_kappa"], help="Agreement on positive versus negative, corrected for chance. 1.0 is perfect, 0 is no better than chance.")
    q3.metric("Keyword-rules baseline (F1)", x["keyword_baseline_aspect_f1"], help="The same F1 for a simple keyword approach, to compare against.")
    g = ev["labeler_agreement"]
    st.markdown("**Two labelers, same reviews**")
    st.caption("99 reviews labeled twice, independently.")
    r1, r2, r3 = st.columns(3)
    r1.metric("Problem-finding (precision)", g["problem_precision"], help="Taking one labeler as the reference: of the problems the other found, how many match.")
    r2.metric("Problem-finding (recall)", g["problem_recall"], help="Taking one labeler as the reference: of its problems, how many the other also found.")
    r3.metric("Problem-finding agreement (F1)", g["problem_aspect_f1"], help="One number balancing precision and recall. Praise is left out.")
    t1, t2, t3 = st.columns(3)
    t1.metric("Sentiment agreement (Cohen's kappa)", g["sentiment_kappa"], help="Agreement on positive versus negative, corrected for chance. 1.0 is perfect.")
    t2.metric("Severity agreement (weighted kappa)", g["severity_kappa"], help="Agreement on severity, where missing by one level counts less than missing by three. 1.0 is perfect.")
    t3.metric("Agreement on usable reviews (% agreement)", g["usable_agreement"], help="How often both agreed whether a review has something worth analysing.")

# ---------------------------------------------------------------- tab 5
with tabs[5]:
    st.subheader("Try it on a review")
    have_key = bool(os.environ.get("GROQ_API_KEY"))
    if not have_key:
        st.warning("The live demo is off right now.")
    used = st.session_state.get("tries", 0)
    with st.form("try_it"):  # a form, so the button works as soon as the text is typed
        text = st.text_area("Review", max_chars=1000, height=120, placeholder="e.g. my withdrawal has been stuck for three days and support is not replying")
        st.caption("Please don't paste personal details.")
        st.caption("Stars (optional)")
        fb = st.feedback("stars")
        submitted = st.form_submit_button("Label this review", disabled=(not have_key or used >= 5))
    stars = (fb + 1) if fb is not None else 3
    if submitted and not text.strip():
        st.warning("Write or paste a review first.")
    elif submitted:
        detail = ""
        st.session_state["tries"] = used + 1
        if not take_live_call():
            label, errors = None, ["The live demo has reached its limit for today. Try again tomorrow."]
        else:
            with st.spinner("Reading the review..."):
                try:
                    label, errors = appdata.label_one(text, stars, str(ROOT))
                except Exception as e:  # daily limit, network, bad key: say so plainly
                    daily = type(e).__name__ == "DailyLimit"
                    label, errors = None, ["The free model has reached its limit for today. Try again tomorrow." if daily
                                           else "The demo is busy right now. Try again later."]
                    # our own error messages never contain a key, so a short detail is safe to show
                    detail = type(e).__name__ + (": " + str(e)[:140] if type(e).__name__ == "ProviderError" else "")
        if label is None:
            st.error("; ".join(errors))
            if detail:
                st.caption("Technical detail: %s" % detail)
        else:
            st.write("**Usable:** %s · **Overall:** %s" % (label["usable"], label["overall_sentiment"]))
            for a in label["aspects"]:
                st.markdown("%s **%s** (`%s`) · %s · severity **%s**" % (SEV_ICON[a["severity"]], a["aspect"], a["category"], a["sentiment"], a["severity"]))
                st.caption("\"%s\"  ·  What stood out: %s" % (a["quote"], ", ".join(appdata.plain_facts(a["impact"])) or "nothing specific"))
            if not label["aspects"]:
                st.write("No problem or praise found in this review.")
    if used >= 5:
        st.caption("That's 5 tries for this session.")
