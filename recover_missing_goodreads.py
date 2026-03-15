"""
recover_missing_goodreads.py

Strategy:
  Pass 1  — Stream goodreads_books.json ONCE, save a small candidate subset CSV
            containing only rows likely to match our missing/incomplete books.
  Pass 2  — Match exclusively against the tiny subset.
            • For already-matched rows missing page_count/description:
              exact lookup by goodreads_match_title → pick best edition.
            • For 19 fully unmatched rows:
              fuzzy title + author matching with configurable thresholds.
  Output  — enriched CSV, manual-review CSV, recovery summary.
"""

import json, re, sys
import pandas as pd
from difflib import SequenceMatcher

sys.stdout.reconfigure(encoding="utf-8")

# ── config ──────────────────────────────────────────────────────────────────
FINAL_CSV   = "book_movie_adaptations_final_200.csv"
GR_JSON     = "goodreads_books.json"
SUBSET_CSV  = "goodreads_candidate_subset.csv"
OUT_CSV     = "book_movie_adaptations_final_200.csv"
REVIEW_CSV  = "goodreads_manual_review.csv"

AUTO_SCORE   = 85   # >= this  → auto-fill
MANUAL_SCORE = 55   # >= this  → manual review (< AUTO_SCORE)

GR_FIELDS = [
    "book_avg_rating", "book_ratings_count", "book_reviews_count",
    "book_page_count", "book_series_indicator",
    "book_description", "book_description_length",
]

# ── helpers ──────────────────────────────────────────────────────────────────

def normalize(text):
    if not isinstance(text, str):
        return ""
    t = text.lower()
    t = t.replace("&", "and").replace("'s", "s")
    t = re.sub(r"^(the|a|an)\s+", "", t)   # strip leading article
    t = re.sub(r"\s*:.*$", "", t)           # strip subtitle after colon
    t = re.sub(r"\s*\(.*?\)", "", t)        # strip parenthetical
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def tokens(text, min_len=3):
    return set(w for w in normalize(text).split() if len(w) >= min_len)

def sim(a, b):
    return int(SequenceMatcher(None, normalize(a), normalize(b)).ratio() * 100)

def safe_int(v):
    try:
        return int(float(v)) if v not in (None, "", "None") else None
    except (ValueError, TypeError):
        return None

def safe_float(v):
    try:
        return float(v) if v not in (None, "", "None") else None
    except (ValueError, TypeError):
        return None

def author_tokens(author_str):
    """Split author string into lowercase last-name-sized tokens."""
    if not isinstance(author_str, str):
        return set()
    parts = re.split(r"[\s,\.]+", author_str.lower())
    return {p for p in parts if len(p) >= 3}

# ── load adaptation CSV ──────────────────────────────────────────────────────
df = pd.read_csv(FINAL_CSV, encoding="utf-8-sig")
print(f"Loaded {len(df)} rows from {FINAL_CSV}")

unmatched_mask     = df["goodreads_match_score"] == 0
missing_pages_mask = (~unmatched_mask) & df["book_page_count"].isnull()
missing_desc_mask  = (~unmatched_mask) & df["book_description"].isnull()

print(f"  Fully unmatched              : {unmatched_mask.sum()}")
print(f"  Matched, missing page_count  : {missing_pages_mask.sum()}")
print(f"  Matched, missing description : {missing_desc_mask.sum()}")

# ── build streaming targets ───────────────────────────────────────────────────

# Group A: 19 unmatched — need fuzzy matching
unmatched_targets = []
for _, row in df[unmatched_mask].iterrows():
    title  = str(row["book_title"])
    author = str(row.get("book_author", ""))
    norm   = normalize(title)
    toks   = tokens(title, min_len=3)
    short  = (len(toks) == 0)   # e.g. "It", "69"
    unmatched_targets.append({
        "row_id"   : row["row_id"],
        "title"    : title,
        "author"   : author,
        "pub_year" : safe_int(row.get("book_publication_year")),
        "norm"     : norm,
        "toks"     : toks,
        "short"    : short,
        "auth_toks": author_tokens(author),
    })

# Group B: matched but missing page_count or description — need exact title lookup
match_title_norms = set()
for _, row in df[missing_pages_mask | missing_desc_mask].iterrows():
    mtt = row.get("goodreads_match_title")
    if pd.notna(mtt):
        match_title_norms.add(normalize(str(mtt)))

# Token index for Group A
tok_index = {}
for i, t in enumerate(unmatched_targets):
    for w in t["toks"]:
        tok_index.setdefault(w, set()).add(i)

# Exact norm index for short-title unmatched
short_norms = {t["norm"]: i for i, t in enumerate(unmatched_targets) if t["short"]}

print(f"\nStreaming {GR_JSON}…")
print(f"  Watching for {len(match_title_norms)} exact match titles")
print(f"  + fuzzy candidates for {len(unmatched_targets)} unmatched books")

# ── Pass 1: stream JSON, collect candidates ───────────────────────────────────
candidate_rows = []
count = 0
BATCH = 500_000

with open(GR_JSON, "r", encoding="utf-8", errors="replace") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        count += 1
        if count % BATCH == 0:
            print(f"  {count:,} lines scanned | {len(candidate_rows)} candidates")

        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue

        gr_title = rec.get("title", "") or ""
        if not gr_title:
            continue
        gr_norm   = normalize(gr_title)
        gr_tokens = set(gr_norm.split())

        keep = False

        # --- Group B: exact match for already-matched titles ---
        if gr_norm in match_title_norms:
            keep = True

        # --- Group A: token overlap with unmatched targets ---
        if not keep:
            for tok in gr_tokens:
                if len(tok) >= 3 and tok in tok_index:
                    keep = True
                    break

        # --- Group A: short-title exact norm match ---
        if not keep and gr_norm in short_norms:
            keep = True

        if keep:
            try:
                series_raw = rec.get("series", [])
                series_str = json.dumps(series_raw) if series_raw else "[]"
            except Exception:
                series_str = "[]"

            candidate_rows.append({
                "gr_title"           : gr_title,
                "gr_norm"            : gr_norm,
                "gr_year"            : rec.get("publication_year"),
                "average_rating"     : rec.get("average_rating"),
                "ratings_count"      : rec.get("ratings_count"),
                "text_reviews_count" : rec.get("text_reviews_count"),
                "num_pages"          : rec.get("num_pages"),
                "series"             : series_str,
                "description"        : (rec.get("description") or "").strip(),
            })

print(f"\nDone. Scanned {count:,} lines → {len(candidate_rows)} candidates")

subset_df = pd.DataFrame(candidate_rows)
subset_df.to_csv(SUBSET_CSV, index=False, encoding="utf-8-sig")
print(f"Saved candidate subset → {SUBSET_CSV}  ({len(subset_df)} rows)")

# ── Pass 2a: fill missing page_count / description for already-matched rows ──
print("\n--- Phase 2a: fill missing fields for matched rows ---")

# Build multi-record lookup: norm → list of rows
subset_by_norm = {}
for _, row in subset_df.iterrows():
    subset_by_norm.setdefault(row["gr_norm"], []).append(row)

pages_recovered = 0
desc_recovered  = 0

for idx, row in df.iterrows():
    if unmatched_mask[idx]:
        continue
    mtt = row.get("goodreads_match_title")
    if pd.isna(mtt):
        continue
    mtt_norm = normalize(str(mtt))
    candidates = subset_by_norm.get(mtt_norm, [])

    # Fill page_count: pick the candidate with the best (largest plausible) page count
    if pd.isna(df.at[idx, "book_page_count"]):
        page_vals = []
        for c in candidates:
            p = safe_int(c["num_pages"])
            if p and 10 < p < 5000:
                page_vals.append(p)
        if page_vals:
            # use median-ish: sort and pick middle
            page_vals.sort()
            chosen = page_vals[len(page_vals) // 2]
            df.at[idx, "book_page_count"] = chosen
            pages_recovered += 1

    # Fill description: pick the longest non-empty one
    if pd.isna(df.at[idx, "book_description"]) or str(df.at[idx, "book_description"]).strip() == "":
        descs = [str(c["description"]).strip() for c in candidates
                 if pd.notna(c["description"]) and str(c["description"]).strip()]
        if descs:
            best_desc = max(descs, key=len)
            df.at[idx, "book_description"]        = best_desc
            df.at[idx, "book_description_length"] = len(best_desc)
            desc_recovered += 1

print(f"  page_count recovered : {pages_recovered}")
print(f"  description recovered: {desc_recovered}")

# ── Pass 2b: fuzzy-match the 19 unmatched titles ─────────────────────────────
print("\n--- Phase 2b: fuzzy matching 19 unmatched titles against subset ---")

auto_filled    = []
manual_review  = []

for tgt in unmatched_targets:
    rid       = tgt["row_id"]
    tgt_toks  = tgt["toks"]
    auth_toks = tgt["auth_toks"]

    # gather candidates from subset
    pool = []
    for _, srow in subset_df.iterrows():
        gr_norm  = srow["gr_norm"]
        gr_toks  = set(gr_norm.split())

        overlap = tgt_toks & gr_toks

        # Short-title: require exact norm match
        if tgt["short"]:
            if gr_norm != tgt["norm"]:
                continue
            overlap = {tgt["norm"]}

        if not overlap:
            continue

        title_score = sim(tgt["title"], srow["gr_title"])
        if title_score < 45:
            continue

        # Year proximity bonus (loose: within 10 years)
        gr_year  = safe_int(srow["gr_year"])
        year_ok  = True
        year_diff = 999
        if gr_year and tgt["pub_year"]:
            year_diff = abs(gr_year - tgt["pub_year"])
            year_ok   = year_diff <= 10

        if not year_ok:
            continue

        # Composite score: title sim + small year bonus
        year_bonus  = max(0, 5 - year_diff)
        combo_score = title_score + year_bonus

        pool.append({
            "srow"        : srow,
            "title_score" : title_score,
            "combo_score" : combo_score,
            "year_diff"   : year_diff,
            "gr_year"     : gr_year,
        })

    if not pool:
        manual_review.append({
            "row_id"           : rid,
            "book_title"       : tgt["title"],
            "book_author"      : tgt["author"],
            "gr_candidate_title" : None,
            "gr_candidate_year"  : None,
            "title_score"      : 0,
            "combo_score"      : 0,
            "reason"           : "No candidates in subset",
        })
        continue

    pool.sort(key=lambda x: (-x["combo_score"], x["year_diff"]))
    best       = pool[0]
    srow       = best["srow"]
    score      = best["title_score"]
    combo      = best["combo_score"]

    review_entry = {
        "row_id"             : rid,
        "book_title"         : tgt["title"],
        "book_author"        : tgt["author"],
        "gr_candidate_title" : srow["gr_title"],
        "gr_candidate_year"  : srow["gr_year"],
        "gr_avg_rating"      : srow["average_rating"],
        "gr_ratings_count"   : srow["ratings_count"],
        "title_score"        : score,
        "combo_score"        : combo,
        "reason"             : f"title_sim={score}, year_diff={best['year_diff']}",
    }

    if combo >= AUTO_SCORE:
        # Auto-fill
        df_idx = df[df["row_id"] == rid].index[0]
        desc = str(srow["description"]).strip() if pd.notna(srow["description"]) else ""
        try:
            series_val = json.loads(srow["series"])
        except Exception:
            series_val = []

        df.at[df_idx, "book_avg_rating"]         = safe_float(srow["average_rating"])
        df.at[df_idx, "book_ratings_count"]       = safe_int(srow["ratings_count"])
        df.at[df_idx, "book_reviews_count"]       = safe_int(srow["text_reviews_count"])
        df.at[df_idx, "book_page_count"]          = safe_int(srow["num_pages"]) or None
        df.at[df_idx, "book_series_indicator"]    = 1 if series_val else 0
        df.at[df_idx, "book_description"]         = desc if desc else None
        df.at[df_idx, "book_description_length"]  = len(desc) if desc else None
        df.at[df_idx, "goodreads_match_title"]    = srow["gr_title"]
        df.at[df_idx, "goodreads_match_score"]    = score

        review_entry["action"] = "AUTO-FILLED"
        auto_filled.append(review_entry)

    elif combo >= MANUAL_SCORE:
        review_entry["action"] = "MANUAL REVIEW"
        manual_review.append(review_entry)
    else:
        review_entry["action"] = "REJECTED (low score)"
        manual_review.append(review_entry)

print(f"  Auto-filled    : {len(auto_filled)}")
print(f"  Manual review  : {len(manual_review)}")

# ── Save outputs ─────────────────────────────────────────────────────────────
df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
print(f"\nSaved enriched CSV → {OUT_CSV}")

review_df = pd.DataFrame(auto_filled + manual_review)
review_df.sort_values("row_id").to_csv(REVIEW_CSV, index=False, encoding="utf-8-sig")
print(f"Saved manual review CSV → {REVIEW_CSV}")

# ── Summary ───────────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("RECOVERY SUMMARY")
print("="*60)
final_missing = df.isnull().sum()
for col in GR_FIELDS:
    if col in df.columns:
        n = final_missing[col]
        print(f"  {col:<30}: {n} still missing")

print(f"\nGroup A (19 unmatched):")
print(f"  Auto-filled   : {len(auto_filled)}")
for e in auto_filled:
    print(f"    [{e['row_id']:>3}] {e['book_title'][:40]:<40} → {e['gr_candidate_title'][:40]} (score={e['title_score']})")

print(f"\n  Manual review : {len(manual_review)}")
for e in manual_review:
    cand = e.get("gr_candidate_title") or "(no match)"
    print(f"    [{e['row_id']:>3}] {e['book_title'][:40]:<40} → {cand[:40]} (action={e['action']})")

print(f"\nGroup B (matched, missing fields):")
print(f"  page_count recovered   : {pages_recovered}")
print(f"  description recovered  : {desc_recovered}")
print("="*60)
