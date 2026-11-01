"""Import labels returned by an outside model, check them with our own rules, and derive severity in code.

Usage:
  python3 -I scripts/import_external_labels.py --chunks <dir with chunk_NN.jsonl> --returned <dir with the
      pasted replies, any text files> --out <labels.jsonl> --labeler "ChatGPT (model name)"

The replies may contain code fences or commentary: every JSON object that has a reviewId is picked up.
Each label goes through the same checks as the pipeline's own labels (valid categories, quote copied
exactly, at most 3 aspects, impact flags present). Failures are listed so those reviews can be redone.
"""
import argparse
import glob
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))
from voc import extract  # noqa: E402


def find_labels(text: str) -> list:
    """Return every JSON object with a reviewId found anywhere in the text (also inside arrays)."""
    dec, out, i = json.JSONDecoder(), [], 0
    while i < len(text):
        j = min([k for k in (text.find("{", i), text.find("[", i)) if k != -1] or [-1])
        if j == -1:
            break
        try:
            obj, end = dec.raw_decode(text, j)
        except json.JSONDecodeError:
            i = j + 1
            continue
        items = obj if isinstance(obj, list) else [obj]
        found = [x for x in items if isinstance(x, dict) and "reviewId" in x]
        if found:
            out.extend(found)
            i = end
        else:
            i = j + 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", required=True)
    ap.add_argument("--returned", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--labeler", required=True, help='who produced the labels, e.g. "ChatGPT (model name)"')
    ap.add_argument("--max-aspect-words", type=int, default=8,
                    help="allow longer aspect names than the pipeline default of 8 (a documented deviation)")
    a = ap.parse_args()

    reviews, chunk_of = {}, {}
    for path in sorted(glob.glob(os.path.join(a.chunks, "chunk_*.jsonl"))):
        n = int(os.path.basename(path)[6:8])
        for line in open(path):
            r = json.loads(line)
            reviews[r["reviewId"]] = r
            chunk_of[r["reviewId"]] = n
    raw = []
    for path in sorted(glob.glob(os.path.join(a.returned, "*"))):
        if os.path.isfile(path) and not os.path.basename(path).startswith("."):
            raw += find_labels(open(path, encoding="utf-8", errors="replace").read())

    good, errors, unknown, seen = {}, {}, 0, set()
    for lab in raw:
        rid = lab["reviewId"]
        if rid not in reviews:
            unknown += 1
            continue
        if rid in seen:
            continue  # first copy wins
        seen.add(rid)
        label, errs = extract._check(lab, reviews[rid], "flags", a.max_aspect_words)
        if label is None:
            errors[rid] = errs
        else:
            label["source"] = a.labeler
            good[rid] = label
    with open(a.out, "w") as f:
        for rid in reviews:
            if rid in good:
                f.write(json.dumps(good[rid], ensure_ascii=False) + "\n")

    per_chunk = {}
    for rid, n in chunk_of.items():
        s = per_chunk.setdefault(n, [0, 0, 0, 0])  # total, ok, failed, not returned
        s[0] += 1
        s[1] += rid in good
        s[2] += rid in errors
        s[3] += rid not in good and rid not in errors
    print("labeler: %s" % a.labeler)
    print("reviews in kit %d | valid labels %d | failed checks %d | not returned %d | unknown ids %d" %
          (len(reviews), len(good), len(errors), len(reviews) - len(good) - len(errors), unknown))
    print("chunk status (ok/total):", ", ".join("%02d:%d/%d%s" % (n, s[1], s[0], "!" if s[2] else "")
                                                  for n, s in sorted(per_chunk.items()) if s[1] + s[2] > 0))
    if errors:
        print("\nREDO THESE (chunk, review id, problem):")
        for rid, errs in list(errors.items())[:40]:
            print("  chunk %02d  %s  %s" % (chunk_of[rid], rid[:8], "; ".join(errs)[:150]))
    print("\nwrote %d labels to %s" % (len(good), a.out))


if __name__ == "__main__":
    main()
