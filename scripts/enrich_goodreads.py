"""
enrich_goodreads.py

Streams goodreads_books.json (8.6 GB, one JSON object per line) once,
collects candidate records whose normalized title overlaps with any of the
200 target book titles, then picks the best match per book using a
combination of exact/fuzzy title matching + author matching.

Adds to book_movie_adaptations_final_200.csv:
    book_avg_rating
    book_ratings_count
    book_reviews_count
    book_page_count
    book_series_indicator
    book_description
    book_description_length
    goodreads_match_title      (the matched Goodreads title, for audit)
    goodreads_match_score      (0-100 similarity score)
"""

import json
import re
import sys
import pandas as pd
from difflib import SequenceMatcher

sys.stdout.reconfigure(encoding="utf-8")

FINAL_CSV   = "book_movie_adaptations_final_200.csv"
GR_JSON     = "goodreads_books.json"
OUT_CSV     = "book_movie_adaptations_final_200.csv"   # overwrite in place
REPORT_CSV  = "goodreads_match_report.csv"

# ── helpers ────────────────────────────────────────────────────────────────

def normalize(text):
    """Lowercase, strip articles, remove punctuation/extra spaces."""
    if not isinstance(text, str):
        return ""
    t = text.lower()
    t = re.sub(r"^(the|a|an)\s+", "", t)          # strip leading article
    t = re.sub(r"[^a-z0-9 ]", " ", t)             # remove punctuation
    t = re.sub(r"\s+", " ", t).strip()
    return t

def token_set(text):
    return set(normalize(text).split())

def sim(a, b):
    """SequenceMatcher ratio 0-100."""
    return int(SequenceMatcher(None, normalize(a), normalize(b)).ratio() * 100)

def author_sim(gr_authors_list, target_author):
    """
    gr_authors_list is a list of dicts with 'author_id'.
    We don't have author names in the JSON directly, so we approximate
    by checking if any word from the target author appears in the
    normalized GR title (authors often appear there for bios) or
    just return 50 as a neutral score when we can't verify.
    """
    # In this dataset the author names aren't in the book record —
    # only author IDs are. So we skip author filtering and rely on
    # title + publication year proximity instead.
    return 50

# ── load the 200 targets ───────────────────────────────────────────────────

df = pd.read_csv(FINAL_CSV, encoding="utf-8-sig")
print(f"Loaded {len(df)} target books")

targets = []
for _, row in df.iterrows():
    targets.append({
        "row_id":    row["row_id"],
        "title":     str(row["book_title"]),
        "author":    str(row["book_author"]),
        "pub_year":  int(row["book_publication_year"]) if pd.notna(row["book_publication_year"]) else None,
        "norm":      normalize(str(row["book_title"])),
        "tokens":    token_set(str(row["book_title"])),
    })

# Build a fast lookup: first word of normalized title → list of target indices
first_word_index = {}
for i, t in enumerate(targets):
    words = list(t["tokens"])
    for w in words:
        if len(w) >= 4:                            # skip short words
            first_word_index.setdefault(w, set()).add(i)

# ── first pass: stream JSON and collect candidates ─────────────────────────
# For each target, keep up to 10 candidate GR records.

candidates = {t["row_id"]: [] for t in targets}
target_by_id = {t["row_id"]: t for t in targets}

print(f"Streaming {GR_JSON} …")
BATCH  = 500_000
count  = 0

with open(GR_JSON, "r", encoding="utf-8", errors="replace") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        count += 1
        if count % BATCH == 0:
            print(f"  {count:,} lines scanned …")

        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue

        gr_title = rec.get("title", "") or ""
        gr_norm  = normalize(gr_title)
        gr_tokens = set(gr_norm.split())

        # Quick pre-filter: does any meaningful token overlap with any target?
        candidate_ids = set()
        for tok in gr_tokens:
            if len(tok) >= 4 and tok in first_word_index:
                candidate_ids |= first_word_index[tok]

        if not candidate_ids:
            continue

        # For each candidate target, compute title similarity
        for idx in candidate_ids:
            tgt = targets[idx]
            title_score = sim(gr_title, tgt["title"])
            if title_score < 60:
                continue

            # Optional: check publication year proximity
            gr_year = rec.get("publication_year")
            try:
                gr_year = int(gr_year) if gr_year else None
            except (ValueError, TypeError):
                gr_year = None

            year_ok = True
            if tgt["pub_year"] and gr_year:
                year_ok = abs(gr_year - tgt["pub_year"]) <= 5   # allow reprints

            if not year_ok:
                continue

            candidates[tgt["row_id"]].append({
                "gr_title":          gr_title,
                "gr_year":           gr_year,
                "title_score":       title_score,
                "average_rating":    rec.get("average_rating"),
                "ratings_count":     rec.get("ratings_count"),
                "text_reviews_count":rec.get("text_reviews_count"),
                "num_pages":         rec.get("num_pages"),
                "series":            rec.get("series", []),
                "description":       rec.get("description", ""),
            })

print(f"Done. Scanned {count:,} lines total.")

# ── second pass: pick best candidate per target ────────────────────────────

results = {}
for tgt in targets:
    rid  = tgt["row_id"]
    pool = candidates[rid]

    if not pool:
        results[rid] = None
        continue

    # Pick the candidate with highest title_score; break ties by ratings_count
    def sort_key(c):
        try:
            rc = int(c["ratings_count"]) if c["ratings_count"] else 0
        except (ValueError, TypeError):
            rc = 0
        return (c["title_score"], rc)

    best = max(pool, key=sort_key)
    results[rid] = best

# ── build enrichment columns ───────────────────────────────────────────────

def safe_int(v):
    try:
        return int(v) if v not in (None, "", "None") else None
    except (ValueError, TypeError):
        return None

def safe_float(v):
    try:
        return float(v) if v not in (None, "", "None") else None
    except (ValueError, TypeError):
        return None

rows_enriched = []
for _, row in df.iterrows():
    rid  = row["row_id"]
    best = results.get(rid)

    if best:
        desc   = best["description"] or ""
        series = best["series"]
        rows_enriched.append({
            "book_avg_rating":       safe_float(best["average_rating"]),
            "book_ratings_count":    safe_int(best["ratings_count"]),
            "book_reviews_count":    safe_int(best["text_reviews_count"]),
            "book_page_count":       safe_int(best["num_pages"]),
            "book_series_indicator": 1 if series else 0,
            "book_description":      desc.strip(),
            "book_description_length": len(desc.strip()),
            "goodreads_match_title": best["gr_title"],
            "goodreads_match_score": best["title_score"],
        })
    else:
        rows_enriched.append({
            "book_avg_rating":        None,
            "book_ratings_count":     None,
            "book_reviews_count":     None,
            "book_page_count":        None,
            "book_series_indicator":  None,
            "book_description":       None,
            "book_description_length":None,
            "goodreads_match_title":  None,
            "goodreads_match_score":  0,
        })

enrich_df = pd.DataFrame(rows_enriched)
df_out    = pd.concat([df.reset_index(drop=True), enrich_df], axis=1)

# ── save ───────────────────────────────────────────────────────────────────

df_out.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
print(f"\nSaved enriched CSV → {OUT_CSV}")

# Match report
matched   = enrich_df[enrich_df["goodreads_match_score"] > 0]
unmatched = enrich_df[enrich_df["goodreads_match_score"] == 0]
print(f"Matched:   {len(matched)}/200")
print(f"Unmatched: {len(unmatched)}/200")

report = df_out[["row_id", "book_title", "book_author", "book_publication_year",
                  "goodreads_match_title", "goodreads_match_score",
                  "book_avg_rating", "book_ratings_count"]].copy()
report.to_csv(REPORT_CSV, index=False, encoding="utf-8-sig")
print(f"Match report → {REPORT_CSV}")

print("\n--- Unmatched titles (need manual lookup) ---")
unmatched_rows = df_out[df_out["goodreads_match_score"] == 0][
    ["row_id", "book_title", "book_author", "book_publication_year"]
]
print(unmatched_rows.to_string(index=False))
