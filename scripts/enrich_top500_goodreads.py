"""
enrich_top500_goodreads.py

Streams goodreads_books.json once to fill missing Goodreads fields
for the 60 book adaptations in top_500_enriched.csv that have no
book metadata yet.

For series entries (Harry Potter, Hunger Games, etc.) the specific
book title is inferred from the film title by stripping "Part 1/2",
franchise prefixes, and matching to the closest Goodreads title.
"""

import json, re, sys
import pandas as pd
import numpy as np
from difflib import SequenceMatcher

sys.stdout.reconfigure(encoding="utf-8")

INPUT_CSV  = "data/interim/top_500_enriched.csv"
GR_JSON    = "data/raw/goodreads_books.json"
OUTPUT_CSV = "data/interim/top_500_enriched.csv"

# ── HELPERS ───────────────────────────────────────────────────────────────────

def norm(t):
    if not isinstance(t, str): return ''
    t = t.lower()
    t = re.sub(r'^(the|a|an)\s+', '', t)
    t = re.sub(r'[^a-z0-9 ]', ' ', t)
    return re.sub(r'\s+', ' ', t).strip()

def tokens(t, min_len=3):
    return set(w for w in norm(t).split() if len(w) >= min_len)

def sim(a, b):
    return int(SequenceMatcher(None, norm(a), norm(b)).ratio() * 100)

def infer_book_title(film_title, fiction_work_raw):
    """
    For series entries, infer the specific book title from the film title.
    e.g. 'Harry Potter and the Deathly Hallows: Part 2' -> 'Harry Potter and the Deathly Hallows'
         'The Hunger Games: Catching Fire' -> 'Catching Fire'
         'Jurassic World' -> 'Jurassic Park' (use fiction_work_raw title)
    """
    t = str(film_title)

    # Strip ": Part N" or "- Part N" or "Part N" suffix
    t = re.sub(r'[\s:\-–]+[Pp]art\s+\d+.*$', '', t).strip()
    # Strip volume/chapter suffixes
    t = re.sub(r'[\s:\-–]+(Volume|Vol|Chapter|Book)\s+\d+.*$', '', t, flags=re.IGNORECASE).strip()

    # If fiction_work_raw is NOT a series, use the actual book title from it
    if 'series' not in str(fiction_work_raw).lower():
        m = re.match(r'^(.+?)\s*\(', str(fiction_work_raw))
        if m:
            return m.group(1).strip()

    return t

def safe_int(v):
    try: return int(float(v)) if v not in (None, '', 'None') else None
    except: return None

def safe_float(v):
    try: return float(v) if v not in (None, '', 'None') else None
    except: return None

# ── LOAD DATA ─────────────────────────────────────────────────────────────────

df = pd.read_csv(INPUT_CSV, encoding='utf-8-sig')
wiki_raw = pd.read_csv('data/raw/fiction_to_feature_films_raw.csv', encoding='utf-8-sig')

def extract_film_norm(s):
    if not isinstance(s, str): return ''
    s = re.sub(r'\s*\(\d{4}\)\s*$', '', s).strip().lower()
    s = re.sub(r'[^a-z0-9 ]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()

wiki_raw['film_norm'] = wiki_raw['film_adaptations_raw'].apply(extract_film_norm)

# Build targets: rows missing book_avg_rating that are is_book=1
missing_mask = (df['is_book'] == 1) & (df['book_avg_rating'].isna())
missing_df = df[missing_mask].copy()
print(f"Targets: {len(missing_df)} films needing Goodreads data")

targets = []
for _, row in missing_df.iterrows():
    # Look up fiction_work_raw from wiki_raw
    match_str = str(row.get('is_book_match', ''))
    film_norm_key = extract_film_norm(match_str)
    hits = wiki_raw[wiki_raw['film_norm'] == film_norm_key]
    fiction_raw = hits.iloc[0]['fiction_work_raw'] if len(hits) > 0 else None

    book_title = infer_book_title(row['Title'], fiction_raw)
    pub_year_m = re.search(r'\b(1[89]\d{2}|20[012]\d)\b', str(fiction_raw)) if fiction_raw else None
    pub_year = int(pub_year_m.group(1)) if pub_year_m else None

    targets.append({
        'df_index'   : row.name,
        'film_title' : row['Title'],
        'film_year'  : row['Year'],
        'book_title' : book_title,
        'pub_year'   : pub_year,
        'norm'       : norm(book_title),
        'toks'       : tokens(book_title, min_len=3),
    })
    print(f"  [{int(row['Rank']):>3}] {row['Title']} → search: \"{book_title}\"")

# Build token index
tok_index = {}
for i, t in enumerate(targets):
    for w in t['toks']:
        tok_index.setdefault(w, set()).add(i)

# ── STREAM GOODREADS ──────────────────────────────────────────────────────────

print(f"\nStreaming {GR_JSON}...")
best = {t['df_index']: {'score': 0, 'rec': None} for t in targets}
count = 0
BATCH = 500_000

with open(GR_JSON, 'r', encoding='utf-8', errors='replace') as f:
    for line in f:
        line = line.strip()
        if not line: continue
        count += 1
        if count % BATCH == 0:
            print(f"  {count:,} lines scanned...")

        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue

        gr_title = rec.get('title', '') or ''
        gr_norm  = norm(gr_title)
        gr_toks  = set(gr_norm.split())

        # Pre-filter via token index
        candidate_idxs = set()
        for tok in gr_toks:
            if len(tok) >= 3 and tok in tok_index:
                candidate_idxs |= tok_index[tok]

        if not candidate_idxs:
            continue

        for i in candidate_idxs:
            tgt = targets[i]
            didx = tgt['df_index']
            title_score = sim(gr_title, tgt['book_title'])
            if title_score < 70:
                continue

            # Year check (loose — allow reprints up to 5 years)
            gr_year = rec.get('publication_year')
            try: gr_year = int(gr_year) if gr_year else None
            except: gr_year = None
            if tgt['pub_year'] and gr_year:
                if abs(gr_year - tgt['pub_year']) > 8:
                    continue

            try: rc = int(rec.get('ratings_count') or 0)
            except: rc = 0

            prev = best[didx]
            if title_score > prev['score'] or (
                title_score == prev['score'] and rc > (int(prev['rec'].get('ratings_count') or 0) if prev['rec'] else 0)
            ):
                best[didx] = {'score': title_score, 'rec': rec}

print(f"Done. Scanned {count:,} lines.")

# ── APPLY RESULTS ─────────────────────────────────────────────────────────────
print("\nApplying matches...")

GR_COLS = ['book_avg_rating','book_ratings_count','book_reviews_count',
           'book_page_count','book_series_indicator','book_description_length',
           'goodreads_match_score']

filled = 0
for tgt in targets:
    didx = tgt['df_index']
    b = best[didx]
    if b['rec'] and b['score'] >= 80:
        rec = b['rec']
        series = rec.get('series', [])
        desc   = (rec.get('description') or '').strip()
        df.at[didx, 'book_avg_rating']        = safe_float(rec.get('average_rating'))
        df.at[didx, 'book_ratings_count']      = safe_int(rec.get('ratings_count'))
        df.at[didx, 'book_reviews_count']      = safe_int(rec.get('text_reviews_count'))
        df.at[didx, 'book_page_count']         = safe_int(rec.get('num_pages'))
        df.at[didx, 'book_series_indicator']   = 1 if series else 0
        df.at[didx, 'book_description_length'] = len(desc) if desc else None
        df.at[didx, 'goodreads_match_score']   = b['score']
        filled += 1
        print(f"  ✓ [{int(df.at[didx,'Rank']):>3}] {tgt['film_title'][:45]:<45} → \"{rec.get('title')}\" (score={b['score']}, ratings={rec.get('ratings_count')})")
    else:
        score = b['score'] if b['rec'] else 0
        print(f"  ✗ [{int(df.at[didx,'Rank']):>3}] {tgt['film_title'][:45]:<45}   (best score={score})")

# ── SAVE ──────────────────────────────────────────────────────────────────────
df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
print(f"\nSaved → {OUTPUT_CSV}")
print(f"Filled: {filled}/{len(targets)}")
total_with_gr = (df['is_book'] == 1) & df['book_avg_rating'].notna()
print(f"Total book adaptations with Goodreads data: {total_with_gr.sum()}/74")
