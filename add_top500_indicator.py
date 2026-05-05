import sys, re, pandas as pd
from difflib import SequenceMatcher
sys.stdout.reconfigure(encoding='utf-8')

df   = pd.read_csv('data/final/book_movie_adaptations_final_200.csv', encoding='utf-8-sig')
top  = pd.read_csv('data/raw/top_500_movies.csv', encoding='utf-8-sig')

def norm(t):
    if not isinstance(t, str): return ''
    t = t.lower()
    t = re.sub(r'^(the|a|an)\s+', '', t)
    t = re.sub(r'[^a-z0-9 ]', ' ', t)
    return re.sub(r'\s+', ' ', t).strip()

def sim(a, b):
    return SequenceMatcher(None, norm(a), norm(b)).ratio()

top['norm'] = top['Title'].apply(norm)
top['Year']  = pd.to_numeric(top['Year'], errors='coerce')

indicators = []
matched_titles = []

for _, row in df.iterrows():
    film_norm = norm(str(row['film_title']))
    year      = row['movie_release_year']

    # Filter top500 to ±1 year window
    pool = top[top['Year'].between(year - 1, year + 1)] if pd.notna(year) else top

    best_score = 0.0
    best_title = None
    for _, trow in pool.iterrows():
        s = sim(film_norm, trow['norm'])
        if s > best_score:
            best_score = s
            best_title = trow['Title']

    if best_score >= 0.88:
        indicators.append(1)
        matched_titles.append(f"{best_title} ({best_score:.2f})")
    else:
        indicators.append(0)
        matched_titles.append(None)

df['top_500_box_office'] = indicators
df.to_csv('data/final/book_movie_adaptations_final_200.csv', index=False, encoding='utf-8-sig')

hits = sum(indicators)
print(f'Adaptations in top-500 all-time domestic gross: {hits}/350')
print()
for i, (flag, title) in enumerate(zip(indicators, matched_titles)):
    if flag:
        row = df.iloc[i]
        print(f"  [{int(row['row_id']):>3}] {row['film_title']} ({int(row['movie_release_year'])}) → {title}")
