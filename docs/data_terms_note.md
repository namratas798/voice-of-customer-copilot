# Data terms note (read before publishing anything)

Checked on 2026-11-01 by reading Google's own pages. This is a reading of the text, not legal advice.

## What I read
- Google Play Terms of Service: https://play.google.com/about/play-terms/
- Google Terms of Service: https://policies.google.com/terms
- Google Play robots.txt: https://play.google.com/robots.txt
- The scraping library used to collect the reviews (`google-play-scraper`): its source file `constants/request.py`.

## What they say, in short
1. **Reviews belong to the people who wrote them.** The Google Terms of Service say users keep the intellectual property rights in their content, and name "reviews you write" as an example. Nothing I read gives third parties a licence to republish reviews.
2. **Automated access must follow robots.txt.** The Google Terms of Service list, among things not to do, using automated means to access content in violation of the machine-readable instructions on its pages, with robots.txt as the example.
3. **robots.txt disallows the path our collection used.** Its rules include `Disallow: /_`, `Disallow: /xhr`, `Disallow: /store/xhr` and `Disallow: /store/getreviews`. The scraping library requests reviews from `/_/PlayStoreUi/data/batchexecute`, a path that starts with `/_`.
4. **The Play Terms limit store content to personal, non-commercial use and restrict redistribution.** That wording is about content people install or buy, so it may not apply to reviews directly. I note it because it points the same way.

## What it means for this project
- The way the reviews were collected appears to conflict with robots.txt and therefore with the Google Terms of Service. The usual practical consequence is being blocked, but I can't say what else could follow.
- Publishing full review text means republishing other people's writing without a licence I can point to.
- Quoting a short excerpt with attribution is treated differently in different countries. I can't tell you it is safe.

## Decisions to make before going public
1. Do not publish review text, the raw files, or the saved review samples. (Done in `.gitignore`: raw files, saved review samples and the app snapshot are kept out.)
2. Real quotes also appear in a few worked examples inside `docs/labeling_guide.md`. Replace them with invented examples before the repository is public.
3. Choose what the public app shows: invented example reviews clearly labeled as such, or no live data at all (video and screenshots without review text).
4. Consider whether to keep presenting results from this data in the case study, or to repeat the evaluation on data whose terms are clear (your own data, a dataset with an explicit licence, or reviews you have permission to use).
5. If it matters to you, ask someone qualified. I am not a lawyer.

## Decision (2026-11-01)
The public app uses **invented demo data** about a fictional app (`app/demo_snapshot.json`, built by `scripts/make_demo_snapshot.py`). Real reviews, the raw files, the saved samples, the real snapshot and the real labeling guide stay on the author's machine and are excluded by `.gitignore`. `scripts/public_check.py` compares everything that would be public against all the real reviews, looking for any run of six consecutive words, and must pass before publishing. The figures on "How reliable is this?" were measured on the real reviews, and the demo page says so.
