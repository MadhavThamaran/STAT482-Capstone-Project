"""
enrich_top500_metadata.py

Enriches data/interim/top_500_movies_labeled.csv with:
  - IMDb: imdb_rating, imdb_vote_count, runtime_minutes, movie_genre_raw  (bulk TSV)
  - TMDb: movie_release_month, mpaa_rating                                (REST API)
  - Wikidata: distributor                                                  (SPARQL)

Then joins Goodreads book fields for the 74 is_book=1 films from the
existing 350-film adaptation dataset.

Output: data/interim/top_500_enriched.csv
        data/interim/top_500_review.csv  (weak/missing matches for manual check)
"""

import re, sys, time, os
import numpy as np
import pandas as pd
import requests
from difflib import SequenceMatcher

sys.stdout.reconfigure(encoding="utf-8")

# ── CONFIG ────────────────────────────────────────────────────────────────────
INPUT_CSV       = "data/interim/top_500_movies_labeled.csv"
ADAPTATIONS_CSV = "data/final/book_movie_adaptations_final_200.csv"
IMDB_BASICS     = "data/raw/title.basics.tsv"
IMDB_RATINGS    = "data/raw/title.ratings.tsv"
OUTPUT_CSV      = "data/interim/top_500_enriched.csv"
REVIEW_CSV      = "data/interim/top_500_review.csv"

IMDB_SIM_THRESHOLD  = 0.85
TMDB_SIM_THRESHOLD  = 0.80
YEAR_TOLERANCE      = 1
TMDB_DELAY          = 0.26
WIKIDATA_DELAY      = 0.5

# Load .env for TMDb token
_env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(_env_file):
    with open(_env_file) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

TMDB_BEARER_TOKEN = os.environ.get("TMDB_BEARER_TOKEN", "")
if not TMDB_BEARER_TOKEN:
    raise EnvironmentError("TMDB_BEARER_TOKEN not set. Add it to .env file.")

TMDB_HEADERS = {
    "Authorization": f"Bearer {TMDB_BEARER_TOKEN}",
    "accept": "application/json",
}

# ── HELPERS ───────────────────────────────────────────────────────────────────

def norm(text):
    if pd.isna(text) or not isinstance(text, str): return ""
    t = text.lower().strip()
    t = t.replace("&", "and").replace("'s", "s")
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()

def sim(a, b):
    return SequenceMatcher(None, norm(a), norm(b)).ratio()

def month_from_date(d):
    if not d or pd.isna(d): return np.nan
    try: return int(str(d).split("-")[1])
    except: return np.nan

def safe_int(v):
    try: return int(float(v)) if pd.notna(v) else np.nan
    except: return np.nan

def safe_float(v):
    try: return float(v) if pd.notna(v) else np.nan
    except: return np.nan

# ── LOAD DATA ─────────────────────────────────────────────────────────────────
print("Loading data...")
df = pd.read_csv(INPUT_CSV, encoding="utf-8-sig")
df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
print(f"  Top-500: {len(df)} rows")

adaptations = pd.read_csv(ADAPTATIONS_CSV, encoding="utf-8-sig")
print(f"  Adaptations: {len(adaptations)} rows")

# ── LOAD IMDb ─────────────────────────────────────────────────────────────────
print("\nLoading IMDb basics...")
basics = pd.read_csv(IMDB_BASICS, sep="\t", na_values="\\N", low_memory=False,
                     usecols=["tconst","titleType","primaryTitle","startYear",
                               "runtimeMinutes","genres"])
basics = basics[basics["titleType"] == "movie"].copy()
basics["startYear"]       = pd.to_numeric(basics["startYear"], errors="coerce")
basics["runtimeMinutes"]  = pd.to_numeric(basics["runtimeMinutes"], errors="coerce")
basics["primaryTitle_norm"] = basics["primaryTitle"].map(norm)

print("Loading IMDb ratings...")
ratings = pd.read_csv(IMDB_RATINGS, sep="\t", na_values="\\N", low_memory=False,
                      usecols=["tconst","averageRating","numVotes"])
ratings["numVotes"]      = pd.to_numeric(ratings["numVotes"],      errors="coerce")
ratings["averageRating"] = pd.to_numeric(ratings["averageRating"], errors="coerce")
imdb = basics.merge(ratings, on="tconst", how="left")
print(f"  {len(imdb):,} movies in IMDb")

def find_imdb(title, year):
    if pd.isna(year): return None, 0.0
    t_norm = norm(title)
    pool = imdb[imdb["startYear"].between(year - YEAR_TOLERANCE,
                                           year + YEAR_TOLERANCE, inclusive="both")].copy()
    if pool.empty: return None, 0.0
    pool["_s"] = pool["primaryTitle_norm"].map(lambda x: sim(t_norm, x))
    pool = pool.sort_values(["_s","numVotes"], ascending=[False,False])
    best = pool.iloc[0]
    score = float(best["_s"])
    return (best, score) if score >= IMDB_SIM_THRESHOLD else (None, score)

# ── TMDb FUNCTIONS ────────────────────────────────────────────────────────────

def tmdb_search(title, year):
    url = "https://api.themoviedb.org/3/search/movie"
    params = {"query": title, "language": "en-US", "page": 1}
    if pd.notna(year): params["year"] = int(year)
    try:
        r = requests.get(url, headers=TMDB_HEADERS, params=params, timeout=30)
        r.raise_for_status()
        return r.json().get("results", [])
    except: return []

def tmdb_release_dates(movie_id):
    try:
        r = requests.get(f"https://api.themoviedb.org/3/movie/{movie_id}/release_dates",
                         headers=TMDB_HEADERS, timeout=30)
        r.raise_for_status()
        return r.json()
    except: return {}

def us_cert(rd_json):
    for block in rd_json.get("results", []):
        if block.get("iso_3166_1") == "US":
            for item in block.get("release_dates", []):
                cert = item.get("certification","").strip()
                if cert: return cert
    return np.nan

def pick_tmdb(results, title, year):
    if not results: return None, 0.0
    t_norm = norm(title)
    scored = []
    for res in results:
        s = sim(t_norm, norm(res.get("title","")))
        cy = None
        if res.get("release_date"):
            try: cy = int(res["release_date"][:4])
            except: pass
        if cy and pd.notna(year) and abs(cy - int(year)) > 1: s -= 0.10
        scored.append((s, res))
    scored.sort(key=lambda x: x[0], reverse=True)
    best_s, best = scored[0]
    return (best, best_s) if best_s >= TMDB_SIM_THRESHOLD else (None, best_s)

# ── WIKIDATA ──────────────────────────────────────────────────────────────────

WD_ENDPOINT = "https://query.wikidata.org/sparql"
WD_HEADERS  = {"Accept": "application/sparql-results+json",
               "User-Agent": "Mozilla/5.0 STAT482-Capstone academic project"}

def wikidata_distributor(title, year):
    escaped = title.replace('"', '\\"')
    yf = f'FILTER(!BOUND(?year) || ABS(?year - {int(year)}) <= 2)' if pd.notna(year) else ""
    query = f"""
SELECT ?distributorLabel WHERE {{
  ?film wdt:P31 wd:Q11424 ; rdfs:label "{escaped}"@en .
  OPTIONAL {{ ?film wdt:P577 ?pubdate . BIND(YEAR(?pubdate) AS ?year) }}
  OPTIONAL {{ ?film wdt:P750 ?distributor . }}
  {yf}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
}} LIMIT 10"""
    try:
        r = requests.get(WD_ENDPOINT, params={"query": query, "format": "json"},
                         headers=WD_HEADERS, timeout=60)
        r.raise_for_status()
        names = [b["distributorLabel"]["value"]
                 for b in r.json()["results"]["bindings"] if "distributorLabel" in b]
        return " | ".join(dict.fromkeys(names)) if names else np.nan
    except: return np.nan

# ── MAIN ENRICHMENT LOOP ──────────────────────────────────────────────────────
cols = {c: [] for c in ["imdb_rating","imdb_vote_count","runtime_minutes",
                         "movie_genre_raw","movie_release_month","mpaa_rating","distributor"]}
review_rows = []

print(f"\nEnriching {len(df)} films...\n")
for i, row in df.iterrows():
    title = str(row["Title"])
    year  = row["Year"]
    print(f"[{int(row['Rank']):>3}] {title} ({int(year) if pd.notna(year) else '?'})", end="  ")

    imdb_match, imdb_s = find_imdb(title, year)
    runtime  = safe_int(imdb_match["runtimeMinutes"]) if imdb_match is not None else np.nan
    genres   = imdb_match["genres"]                   if imdb_match is not None else np.nan
    votes    = safe_int(imdb_match["numVotes"])        if imdb_match is not None else np.nan
    rating   = safe_float(imdb_match["averageRating"]) if imdb_match is not None else np.nan
    if imdb_match is not None:
        print(f"IMDb✓({imdb_s:.2f})", end="  ")
    else:
        print(f"IMDb✗({imdb_s:.2f})", end="  ")

    results = tmdb_search(title, year)
    best_tmdb, tmdb_s = pick_tmdb(results, title, year)
    month = mpaa = np.nan
    if best_tmdb:
        rd = tmdb_release_dates(best_tmdb["id"])
        month = month_from_date(best_tmdb.get("release_date"))
        mpaa  = us_cert(rd)
        print(f"TMDb✓({tmdb_s:.2f})", end="  ")
    else:
        print(f"TMDb✗({tmdb_s:.2f})", end="  ")
    time.sleep(TMDB_DELAY)

    distributor = wikidata_distributor(title, year)
    print(f"WD→{str(distributor)[:30]}")
    time.sleep(WIKIDATA_DELAY)

    cols["imdb_rating"].append(rating)
    cols["imdb_vote_count"].append(votes)
    cols["runtime_minutes"].append(runtime)
    cols["movie_genre_raw"].append(genres)
    cols["movie_release_month"].append(month)
    cols["mpaa_rating"].append(mpaa)
    cols["distributor"].append(distributor)

    if imdb_s < 0.95 or (best_tmdb is None):
        review_rows.append({
            "rank": row["Rank"], "title": title, "year": year,
            "imdb_matched": imdb_match["primaryTitle"] if imdb_match is not None else None,
            "imdb_sim": round(imdb_s, 3),
            "tmdb_matched": best_tmdb.get("title") if best_tmdb else None,
            "tmdb_sim": round(tmdb_s, 3),
        })

for c, v in cols.items():
    df[c] = v

# ── JOIN GOODREADS FOR is_book=1 FILMS ────────────────────────────────────────
print("\nJoining Goodreads data for book adaptations...")

GR_COLS = ["book_avg_rating","book_ratings_count","book_reviews_count",
           "book_page_count","book_series_indicator","book_description_length",
           "goodreads_match_score"]
for c in GR_COLS:
    df[c] = np.nan

adaptations["_norm"] = adaptations["film_title"].apply(norm)
adaptations["_year"] = pd.to_numeric(adaptations["movie_release_year"], errors="coerce")

gr_joined = 0
for idx, row in df[df["is_book"] == 1].iterrows():
    t_norm = norm(str(row["Title"]))
    year   = row["Year"]
    pool = adaptations[adaptations["_year"].between(year - 1, year + 1)] if pd.notna(year) else adaptations
    best_s, best_row = 0.0, None
    for _, arow in pool.iterrows():
        s = sim(t_norm, arow["_norm"])
        if s > best_s:
            best_s, best_row = s, arow
    if best_s >= 0.85 and best_row is not None:
        for c in GR_COLS:
            if c in best_row.index:
                df.at[idx, c] = best_row[c]
        gr_joined += 1

print(f"  Goodreads fields joined for {gr_joined}/74 book adaptations")

# ── SAVE ──────────────────────────────────────────────────────────────────────
df.drop(columns=["_norm","_year"], errors="ignore").to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
pd.DataFrame(review_rows).to_csv(REVIEW_CSV, index=False, encoding="utf-8-sig")

print(f"\nSaved → {OUTPUT_CSV}")
print(f"Review → {REVIEW_CSV}  ({len(review_rows)} flagged)")
print()
print("=== COVERAGE SUMMARY ===")
for c in ["imdb_rating","imdb_vote_count","runtime_minutes","movie_genre_raw",
          "movie_release_month","mpaa_rating","distributor"]:
    n = df[c].notna().sum()
    print(f"  {c:<25}: {n}/500")
