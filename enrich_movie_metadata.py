"""
enrich_movie_metadata.py

Adds movie-side metadata to book_movie_adaptations_final_200.csv:
    movie_release_month   <- TMDb release_date
    runtime_minutes       <- IMDb title.basics
    mpaa_rating           <- TMDb US certification
    distributor           <- Wikidata SPARQL (P750)
    movie_genre_raw       <- IMDb title.basics genres
    imdb_vote_count       <- IMDb title.ratings numVotes
    imdb_rating           <- IMDb title.ratings averageRating

Sources:
    1. IMDb bulk TSVs  (title.basics.tsv, title.ratings.tsv)  — offline, fast
    2. TMDb REST API   — rate-limited, requires bearer token
    3. Wikidata SPARQL — public, no key needed

Outputs:
    book_movie_adaptations_final_200.csv   (overwrite in place)
    movie_match_review.csv                 (rows that need manual inspection)
"""

import os
import re
import sys
import time
import numpy as np
import pandas as pd
import requests
from difflib import SequenceMatcher

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

# ── CONFIG ────────────────────────────────────────────────────────────────────

INPUT_CSV       = "book_movie_adaptations_final_200.csv"
IMDB_BASICS     = "title.basics.tsv"
IMDB_RATINGS    = "title.ratings.tsv"
OUTPUT_CSV      = "book_movie_adaptations_final_200.csv"
REVIEW_CSV      = "movie_match_review.csv"

TMDB_BEARER_TOKEN = os.environ.get("TMDB_BEARER_TOKEN", "")
if not TMDB_BEARER_TOKEN:
    raise EnvironmentError(
        "TMDB_BEARER_TOKEN not set. "
        "Run: set TMDB_BEARER_TOKEN=your_token_here  (Windows)\n"
        "  or export TMDB_BEARER_TOKEN=your_token_here  (Mac/Linux)"
    )

IMDB_SIM_THRESHOLD  = 0.85   # minimum title similarity to accept IMDb match
TMDB_SIM_THRESHOLD  = 0.80   # minimum title similarity to accept TMDb match
YEAR_TOLERANCE      = 1      # ± years allowed in IMDb match
TMDB_DELAY          = 0.26   # seconds between TMDb calls (~4 req/sec, well under 50/s limit)
WIKIDATA_DELAY      = 1.0    # seconds between Wikidata calls

# ── HELPERS ───────────────────────────────────────────────────────────────────

def norm(text):
    if pd.isna(text) or not isinstance(text, str):
        return ""
    t = text.lower().strip()
    t = t.replace("&", "and").replace("'s", "s")
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def sim(a, b):
    return SequenceMatcher(None, norm(a), norm(b)).ratio()

def month_from_date(date_str):
    if not date_str or pd.isna(date_str):
        return np.nan
    try:
        return int(str(date_str).split("-")[1])
    except Exception:
        return np.nan

def safe_int(v):
    try:
        return int(float(v)) if pd.notna(v) else np.nan
    except (ValueError, TypeError):
        return np.nan

# ── LOAD DATA ─────────────────────────────────────────────────────────────────

print("Loading adaptation CSV…")
df = pd.read_csv(INPUT_CSV, encoding="utf-8-sig")
df["movie_release_year"] = pd.to_numeric(df["movie_release_year"], errors="coerce")
print(f"  {len(df)} rows loaded")

# ── LOAD IMDb BULK FILES (chunked to avoid loading full 1 GB at once) ─────────

print("\nLoading IMDb title.basics (chunked, movies only)…")
chunks = []
CHUNK = 200_000
for chunk in pd.read_csv(
    IMDB_BASICS, sep="\t", na_values="\\N", low_memory=True,
    usecols=["tconst", "titleType", "primaryTitle", "startYear",
             "runtimeMinutes", "genres"],
    chunksize=CHUNK,
    dtype=str,          # read as str first — avoids mixed-type warnings
):
    movies = chunk[chunk["titleType"] == "movie"]
    if not movies.empty:
        chunks.append(movies)

basics = pd.concat(chunks, ignore_index=True)
basics["startYear"]      = pd.to_numeric(basics["startYear"],      errors="coerce")
basics["runtimeMinutes"] = pd.to_numeric(basics["runtimeMinutes"], errors="coerce")
# Pre-normalise only the ~600k movie titles (not all 10M rows)
basics["primaryTitle_norm"] = basics["primaryTitle"].map(norm)
print(f"  {len(basics):,} movies loaded")

print("Loading IMDb title.ratings…")
ratings = pd.read_csv(
    IMDB_RATINGS, sep="\t", na_values="\\N",
    usecols=["tconst", "averageRating", "numVotes"],
    dtype={"tconst": str, "averageRating": str, "numVotes": str},
)
ratings["numVotes"]      = pd.to_numeric(ratings["numVotes"],      errors="coerce")
ratings["averageRating"] = pd.to_numeric(ratings["averageRating"], errors="coerce")

imdb = basics.merge(ratings, on="tconst", how="left")
print(f"  {len(imdb):,} movies with ratings merged")

# ── IMDb MATCH FUNCTION ───────────────────────────────────────────────────────

def find_imdb_match(film_title, release_year):
    """Return best IMDb row or None if no confident match found."""
    if pd.isna(release_year):
        return None, 0.0

    year = int(release_year)
    title_norm = norm(film_title)

    # 1. Year window filter
    pool = imdb[imdb["startYear"].between(year - YEAR_TOLERANCE,
                                           year + YEAR_TOLERANCE,
                                           inclusive="both")]
    if pool.empty:
        return None, 0.0

    # 2. Fast prefix pre-filter: first word of target must appear in candidate
    first_word = title_norm.split()[0] if title_norm.split() else ""
    if first_word and len(first_word) >= 3:
        mask = pool["primaryTitle_norm"].str.contains(re.escape(first_word), na=False)
        pre = pool[mask]
        if pre.empty:
            pre = pool   # fall back to full pool if prefix found nothing
    else:
        pre = pool

    # 3. Compute similarity only on the pre-filtered subset
    pre = pre.copy()
    pre["_sim"] = pre["primaryTitle_norm"].map(lambda x: sim(title_norm, x))
    pre = pre.sort_values(["_sim", "numVotes"], ascending=[False, False])
    best = pre.iloc[0]
    score = float(best["_sim"])

    if score < IMDB_SIM_THRESHOLD:
        return None, score
    return best, score

# ── TMDb FUNCTIONS ────────────────────────────────────────────────────────────

TMDB_HEADERS = {
    "Authorization": f"Bearer {TMDB_BEARER_TOKEN}",
    "accept": "application/json",
}

def tmdb_search(title, year):
    url = "https://api.themoviedb.org/3/search/movie"
    params = {"query": title, "language": "en-US", "page": 1}
    if pd.notna(year):
        params["year"] = int(year)
    try:
        r = requests.get(url, headers=TMDB_HEADERS, params=params, timeout=30)
        r.raise_for_status()
        return r.json().get("results", [])
    except Exception as e:
        print(f"    TMDb search error ({title}): {e}")
        return []

def tmdb_release_dates(movie_id):
    url = f"https://api.themoviedb.org/3/movie/{movie_id}/release_dates"
    try:
        r = requests.get(url, headers=TMDB_HEADERS, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"    TMDb release_dates error ({movie_id}): {e}")
        return {}

def us_certification(release_dates_json):
    for block in release_dates_json.get("results", []):
        if block.get("iso_3166_1") == "US":
            for item in block.get("release_dates", []):
                cert = item.get("certification", "").strip()
                if cert:
                    return cert
    return np.nan

def pick_tmdb(results, film_title, year):
    if not results:
        return None, 0.0
    scored = []
    title_norm = norm(film_title)
    for res in results:
        cand_norm  = norm(res.get("title", ""))
        cand_year  = None
        if res.get("release_date"):
            try:
                cand_year = int(res["release_date"][:4])
            except Exception:
                pass
        score = sim(title_norm, cand_norm)
        if cand_year and pd.notna(year) and abs(cand_year - int(year)) > 1:
            score -= 0.10
        scored.append((score, res))
    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best = scored[0]
    if best_score < TMDB_SIM_THRESHOLD:
        return None, best_score
    return best, best_score

# ── WIKIDATA DISTRIBUTOR FUNCTION ─────────────────────────────────────────────

WD_ENDPOINT = "https://query.wikidata.org/sparql"
WD_HEADERS  = {
    "Accept"    : "application/sparql-results+json",
    "User-Agent": "Mozilla/5.0 STAT482-Capstone academic project",
}

def wikidata_distributor(film_title, year):
    """Query Wikidata for distributor (P750) using film label + year."""
    escaped = film_title.replace('"', '\\"')
    year_filter = f"FILTER(!BOUND(?year) || ABS(?year - {int(year)}) <= 2)" if pd.notna(year) else ""

    query = f"""
SELECT ?distributorLabel WHERE {{
  ?film wdt:P31 wd:Q11424 ;
        rdfs:label "{escaped}"@en .
  OPTIONAL {{ ?film wdt:P577 ?pubdate . BIND(YEAR(?pubdate) AS ?year) }}
  OPTIONAL {{ ?film wdt:P750 ?distributor . }}
  {year_filter}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
}}
LIMIT 10
"""
    try:
        r = requests.get(
            WD_ENDPOINT,
            params={"query": query, "format": "json"},
            headers=WD_HEADERS,
            timeout=60,
        )
        r.raise_for_status()
        bindings = r.json()["results"]["bindings"]
        names = [b["distributorLabel"]["value"]
                 for b in bindings if "distributorLabel" in b]
        if not names:
            return np.nan
        return " | ".join(dict.fromkeys(names))
    except Exception as e:
        print(f"    Wikidata error ({film_title}): {e}")
        return np.nan

# ── MAIN ENRICHMENT LOOP ──────────────────────────────────────────────────────

new_cols = {
    "movie_release_month" : [],
    "runtime_minutes"     : [],
    "mpaa_rating"         : [],
    "distributor"         : [],
    "movie_genre_raw"     : [],
    "imdb_vote_count"     : [],
    "imdb_rating"         : [],
}
review_rows = []

print(f"\nEnriching {len(df)} movies…\n")

for i, row in df.iterrows():
    film_title = str(row["film_title"])
    year       = row["movie_release_year"]

    print(f"[{int(row['row_id']):>3}] {film_title} ({int(year) if pd.notna(year) else '?'})")

    runtime_minutes    = np.nan
    movie_genre_raw    = np.nan
    imdb_vote_count    = np.nan
    imdb_rating_val    = np.nan
    movie_release_month= np.nan
    mpaa_rating        = np.nan
    distributor        = np.nan
    imdb_sim           = 0.0
    tmdb_sim           = 0.0

    # ── 1. IMDb bulk match ───────────────────────────────────────────────────
    imdb_match, imdb_sim = find_imdb_match(film_title, year)
    if imdb_match is not None:
        runtime_minutes = safe_int(imdb_match["runtimeMinutes"])
        movie_genre_raw = imdb_match["genres"]
        imdb_vote_count = safe_int(imdb_match["numVotes"])
        imdb_rating_val = imdb_match["averageRating"]
        print(f"       IMDb  ✓ → {imdb_match['primaryTitle']} (sim={imdb_sim:.2f},"
              f" votes={imdb_vote_count})")
    else:
        print(f"       IMDb  ✗ (best sim={imdb_sim:.2f})")

    # ── 2. TMDb (release month + MPAA rating) ───────────────────────────────
    if TMDB_BEARER_TOKEN != "PASTE_YOUR_TMDB_BEARER_TOKEN_HERE":
        results    = tmdb_search(film_title, year)
        best_tmdb, tmdb_sim = pick_tmdb(results, film_title, year)
        if best_tmdb:
            movie_id = best_tmdb["id"]
            rd = tmdb_release_dates(movie_id)
            movie_release_month = month_from_date(best_tmdb.get("release_date"))
            mpaa_rating         = us_certification(rd)
            print(f"       TMDb  ✓ → {best_tmdb.get('title')} (sim={tmdb_sim:.2f},"
                  f" month={movie_release_month}, mpaa={mpaa_rating})")
        else:
            print(f"       TMDb  ✗ (best sim={tmdb_sim:.2f})")
        time.sleep(TMDB_DELAY)
    else:
        print(f"       TMDb  — (no token set)")

    # ── 3. Wikidata distributor ──────────────────────────────────────────────
    distributor = wikidata_distributor(film_title, year)
    print(f"       Wikidata → {distributor}")
    time.sleep(WIKIDATA_DELAY)

    # ── Append results ───────────────────────────────────────────────────────
    new_cols["movie_release_month"].append(movie_release_month)
    new_cols["runtime_minutes"].append(runtime_minutes)
    new_cols["mpaa_rating"].append(mpaa_rating)
    new_cols["distributor"].append(distributor)
    new_cols["movie_genre_raw"].append(movie_genre_raw)
    new_cols["imdb_vote_count"].append(imdb_vote_count)
    new_cols["imdb_rating"].append(imdb_rating_val)

    # ── Flag weak matches for review ─────────────────────────────────────────
    needs_review = (
        (imdb_match is None) or
        (imdb_sim < 0.95) or
        (TMDB_BEARER_TOKEN != "PASTE_YOUR_TMDB_BEARER_TOKEN_HERE" and tmdb_sim < TMDB_SIM_THRESHOLD)
    )
    if needs_review:
        review_rows.append({
            "row_id"               : row["row_id"],
            "film_title"           : film_title,
            "movie_release_year"   : year,
            "imdb_matched_title"   : imdb_match["primaryTitle"] if imdb_match is not None else None,
            "imdb_sim"             : round(imdb_sim, 3),
            "tmdb_matched_title"   : best_tmdb.get("title") if (TMDB_BEARER_TOKEN != "PASTE_YOUR_TMDB_BEARER_TOKEN_HERE" and best_tmdb) else None,
            "tmdb_sim"             : round(tmdb_sim, 3),
            "runtime_filled"       : pd.notna(runtime_minutes),
            "votes_filled"         : pd.notna(imdb_vote_count),
            "month_filled"         : pd.notna(movie_release_month),
            "mpaa_filled"          : pd.notna(mpaa_rating),
        })

# ── WRITE OUTPUTS ─────────────────────────────────────────────────────────────

for col, vals in new_cols.items():
    df[col] = vals

df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
print(f"\nSaved enriched CSV → {OUTPUT_CSV}")

review_df = pd.DataFrame(review_rows)
review_df.to_csv(REVIEW_CSV, index=False, encoding="utf-8-sig")
print(f"Saved review CSV  → {REVIEW_CSV}  ({len(review_df)} rows flagged)")

# ── SUMMARY ───────────────────────────────────────────────────────────────────

print("\n" + "="*60)
print("ENRICHMENT SUMMARY")
print("="*60)
for col in new_cols:
    filled = df[col].notna().sum()
    print(f"  {col:<25}: {filled:>3}/200 filled ({200-filled} missing)")
print("="*60)
