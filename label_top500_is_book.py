"""
label_top500_is_book.py

Adds is_book column to top_500_movies.csv:
  1 = confirmed book adaptation (matched against our adaptation dataset
      OR the full Wikipedia fiction-to-feature-films raw list)
  0 = no match found (likely original screenplay, comic, etc.)

Output: data/interim/top_500_movies_labeled.csv
"""

import sys, re, pandas as pd
from difflib import SequenceMatcher
sys.stdout.reconfigure(encoding='utf-8')

def norm(t):
    if not isinstance(t, str): return ''
    t = t.lower()
    t = re.sub(r'^(the|a|an)\s+', '', t)
    t = re.sub(r'[^a-z0-9 ]', ' ', t)
    return re.sub(r'\s+', ' ', t).strip()

def sim(a, b):
    return SequenceMatcher(None, norm(a), norm(b)).ratio()

def extract_year(s):
    if not isinstance(s, str): return None
    m = re.search(r'\b(19[0-9]{2}|20[0-2][0-9])\b', s)
    return int(m.group(1)) if m else None

# ── Load sources ──────────────────────────────────────────────────────────────

top = pd.read_csv('data/raw/top_500_movies.csv', encoding='utf-8-sig')
top['Year'] = pd.to_numeric(top['Year'], errors='coerce')
top['norm'] = top['Title'].apply(norm)

# Source 1: our 350 confirmed book adaptations
adaptations = pd.read_csv('data/final/book_movie_adaptations_final_200.csv', encoding='utf-8-sig')
adaptations['norm'] = adaptations['film_title'].apply(norm)

# Source 2: full Wikipedia raw list (3,728 rows, all years)
wiki_raw = pd.read_csv('data/raw/fiction_to_feature_films_raw.csv', encoding='utf-8-sig')
wiki_raw['film_year'] = wiki_raw['film_adaptations_raw'].apply(extract_year)
wiki_raw['film_norm'] = wiki_raw['film_adaptations_raw'].apply(
    lambda x: norm(re.sub(r'\s*\(\d{4}\)\s*$', '', str(x)).strip())
)

print(f"Top-500 films      : {len(top)}")
print(f"Our adaptations    : {len(adaptations)}")
print(f"Wikipedia raw list : {len(wiki_raw)}")
print()

# ── Match each top-500 film ───────────────────────────────────────────────────

SIM_THRESHOLD = 0.88
YEAR_TOLERANCE = 1

is_book    = []
match_src  = []
match_title = []

for _, trow in top.iterrows():
    t_norm = trow['norm']
    t_year = trow['Year']

    found = False
    src   = None
    mtitle = None

    # -- Check source 1: our 350 adaptations --
    pool1 = adaptations[
        adaptations['movie_release_year'].between(t_year - YEAR_TOLERANCE, t_year + YEAR_TOLERANCE)
    ] if pd.notna(t_year) else adaptations

    for _, arow in pool1.iterrows():
        s = sim(t_norm, arow['norm'])
        if s >= SIM_THRESHOLD:
            found  = True
            src    = 'adaptation_dataset'
            mtitle = arow['film_title']
            break

    # -- Check source 2: Wikipedia raw list --
    if not found:
        pool2 = wiki_raw[
            wiki_raw['film_year'].between(t_year - YEAR_TOLERANCE, t_year + YEAR_TOLERANCE)
        ] if pd.notna(t_year) else wiki_raw

        best_s = 0.0
        for _, wrow in pool2.iterrows():
            s = sim(t_norm, wrow['film_norm'])
            if s > best_s:
                best_s = s
                best_match = wrow['film_adaptations_raw']
        if best_s >= SIM_THRESHOLD:
            found  = True
            src    = 'wikipedia_raw'
            mtitle = best_match

    is_book.append(1 if found else 0)
    match_src.append(src)
    match_title.append(mtitle)

top['is_book']          = is_book
top['is_book_match_src'] = match_src
top['is_book_match']    = match_title
top = top.drop(columns=['norm'])

# ── Save ─────────────────────────────────────────────────────────────────────

top.to_csv('data/interim/top_500_movies_labeled.csv', index=False, encoding='utf-8-sig')

n_books = sum(is_book)
print(f"is_book = 1 : {n_books}/500")
print(f"is_book = 0 : {500 - n_books}/500")
print()
print("=== Confirmed book adaptations in top 500 ===")
confirmed = top[top['is_book'] == 1][['Rank','Title','Year','Domestic Gross','is_book_match_src','is_book_match']]
print(confirmed.to_string(index=False))
print()
print("Saved → data/interim/top_500_movies_labeled.csv")
