"""
enrich_top500_goodreads_pass2.py — targeted second pass for 14 remaining unmatched.
"""
import json, re, sys
import pandas as pd, numpy as np
from difflib import SequenceMatcher

sys.stdout.reconfigure(encoding="utf-8")

INPUT_CSV  = "data/interim/top_500_enriched.csv"
GR_JSON    = "data/raw/goodreads_books.json"

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

def safe_int(v):
    try: return int(float(v)) if v not in (None,'','None') else None
    except: return None

def safe_float(v):
    try: return float(v) if v not in (None,'','None') else None
    except: return None

df = pd.read_csv(INPUT_CSV, encoding='utf-8-sig')

# Map film title → actual book title to search
BOOK_TITLES = {
    "The Hunger Games: Catching Fire"                    : "Catching Fire",
    "The Hunger Games: Mockingjay - Part 1"              : "Mockingjay",
    "The Hunger Games: Mockingjay - Part 2"              : "Mockingjay",
    "The Hunger Games: The Ballad of Songbirds & Snakes" : "The Ballad of Songbirds and Snakes",
    "The Twilight Saga: New Moon"                        : "New Moon",
    "The Twilight Saga: Breaking Dawn - Part 1"          : "Breaking Dawn",
    "The Twilight Saga: Breaking Dawn - Part 2"          : "Breaking Dawn",
    "Project Hail Mary"                                  : "Project Hail Mary",
    "The Bourne Ultimatum"                               : "The Bourne Ultimatum",
    "The Bourne Supremacy"                               : "The Bourne Supremacy",
    "It: Chapter Two"                                    : "It",
    "Mary Poppins Returns"                               : "Mary Poppins",
    "Jason Bourne"                                       : "The Bourne Ultimatum",
    "The Chronicles of Narnia: Prince Caspian"           : "Prince Caspian",
}

targets = []
for _, row in df[(df['is_book']==1) & df['book_avg_rating'].isna()].iterrows():
    film = row['Title']
    book = BOOK_TITLES.get(film, film)
    targets.append({
        'df_index'  : row.name,
        'film_title': film,
        'book_title': book,
        'norm'      : norm(book),
        'toks'      : tokens(book, min_len=3),
        'pub_year'  : None,
    })
    print(f"  Target: \"{film}\" → search \"{book}\"")

tok_index = {}
for i, t in enumerate(targets):
    for w in t['toks']:
        tok_index.setdefault(w, set()).add(i)

print(f"\nStreaming {GR_JSON}...")
best = {t['df_index']: {'score': 0, 'rec': None} for t in targets}
count = 0

with open(GR_JSON, 'r', encoding='utf-8', errors='replace') as f:
    for line in f:
        line = line.strip()
        if not line: continue
        count += 1
        if count % 500_000 == 0:
            print(f"  {count:,} lines...")
        try:
            rec = json.loads(line)
        except: continue

        gr_title = rec.get('title','') or ''
        gr_toks  = set(norm(gr_title).split())

        candidate_idxs = set()
        for tok in gr_toks:
            if len(tok) >= 3 and tok in tok_index:
                candidate_idxs |= tok_index[tok]
        if not candidate_idxs: continue

        for i in candidate_idxs:
            tgt  = targets[i]
            didx = tgt['df_index']
            score = sim(gr_title, tgt['book_title'])
            if score < 75: continue
            try: rc = int(rec.get('ratings_count') or 0)
            except: rc = 0
            prev = best[didx]
            if score > prev['score'] or (score == prev['score'] and rc > (int(prev['rec'].get('ratings_count') or 0) if prev['rec'] else 0)):
                best[didx] = {'score': score, 'rec': rec}

print(f"Done. {count:,} lines scanned.\n")

filled = 0
for tgt in targets:
    didx = tgt['df_index']
    b = best[didx]
    if b['rec'] and b['score'] >= 80:
        rec    = b['rec']
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
        print(f"  ✓ {tgt['film_title'][:50]:<50} → \"{rec.get('title')}\" (score={b['score']}, ratings={rec.get('ratings_count')})")
    else:
        print(f"  ✗ {tgt['film_title'][:50]:<50}   (best={b['score']})")

df.to_csv(INPUT_CSV, index=False, encoding='utf-8-sig')
total = (df['is_book']==1) & df['book_avg_rating'].notna()
print(f"\nFilled: {filled}/{len(targets)}")
print(f"Total book adaptations with Goodreads data: {total.sum()}/74")
