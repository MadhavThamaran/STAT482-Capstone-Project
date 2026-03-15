"""
build_final_200.py

Reads the 838-row candidate pool (fiction_to_feature_films_2000_2024_guess.csv),
applies inclusion/exclusion rules, assigns genre buckets, enforces year and genre
diversity, and selects the final 200 book-to-movie adaptations.

Outputs:
  book_movie_adaptations_final_200.csv      -- final 200 rows
  book_movie_adaptations_excluded.csv       -- dropped rows with reason
"""

import pandas as pd
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

# ---------------------------------------------------------------------------
# 1. Load candidate pool
# ---------------------------------------------------------------------------
df = pd.read_csv("fiction_to_feature_films_2000_2024_guess.csv", encoding="utf-8-sig")
print(f"Loaded {len(df)} candidate rows")

# ---------------------------------------------------------------------------
# 2. Parse book title, book author, film title from raw text
# ---------------------------------------------------------------------------

def parse_book_info(raw):
    """
    Input examples:
      'About a Boy (1998), Nick Hornby'
      'The Adventures of Pinocchio (Italian: ...) (1883), Carlo Collodi'
    Returns (book_title, book_author)
    """
    if not isinstance(raw, str):
        return None, None

    # Strip leading article translations like "English: ..." inside parentheses
    text = raw.strip()

    # Grab author: everything after the last '), ' pattern
    author_match = re.search(r'\)\s*,\s*(.+)$', text)
    book_author = author_match.group(1).strip() if author_match else None

    # Book title: everything before the first '(' that looks like a year or language note
    title_match = re.match(r'^(.+?)\s*\(', text)
    book_title = title_match.group(1).strip() if title_match else text.split(',')[0].strip()

    return book_title, book_author


def parse_film_title(raw):
    """
    Input examples:
      'About a Boy (2002)'
      'Crime Is Our Business (French: Le Crime est notre affaire) (2008)'
    Returns film_title (without year)
    """
    if not isinstance(raw, str):
        return None
    # Remove trailing (year)
    title = re.sub(r'\s*\(\d{4}\)\s*$', '', raw.strip())
    # Remove language annotation like (French: ...) at the end if it remains
    title = re.sub(r'\s*\([A-Za-z]+:\s*[^)]+\)\s*$', '', title).strip()
    return title if title else None


df["book_title"] = df["fiction_work_raw"].apply(lambda x: parse_book_info(x)[0])
df["book_author"] = df["fiction_work_raw"].apply(lambda x: parse_book_info(x)[1])
df["film_title"] = df["film_adaptation_raw"].apply(parse_film_title)
df["film_year"] = df["film_release_year_guess"].astype("Int64")
df["book_year"] = df["book_publication_year_guess"].astype("Int64")

# ---------------------------------------------------------------------------
# 3. Hard exclusion filters
# ---------------------------------------------------------------------------

excluded_rows = []

def exclude(mask, reason, df_pool, exc_list):
    to_drop = df_pool[mask].copy()
    to_drop["exclusion_reason"] = reason
    exc_list.append(to_drop)
    return df_pool[~mask].copy()


# 3a. Must have film year in 2000–2024
mask = ~df["film_year"].between(2000, 2024)
df = exclude(mask, "film_year_outside_2000_2024", df, excluded_rows)

# 3b. Must have a parseable film title
mask = df["film_title"].isna() | (df["film_title"].str.strip() == "")
df = exclude(mask, "missing_film_title", df, excluded_rows)

# 3c. Must have a parseable book title and author
mask = df["book_title"].isna() | df["book_author"].isna()
df = exclude(mask, "missing_book_title_or_author", df, excluded_rows)

# 3d. Book must be published before movie
mask = df["book_year"].notna() & (df["book_year"] >= df["film_year"])
df = exclude(mask, "book_not_published_before_film", df, excluded_rows)

# 3d2. Book must be published after 1850 (pre-1851 books lack consistent Goodreads metadata)
# Also exclude rows where publication year is unknown — cannot verify post-1850 compliance
mask = df["book_year"].isna() | (df["book_year"] <= 1850)
df = exclude(mask, "book_published_1850_or_earlier_or_unknown_year", df, excluded_rows)

# 3e. Exclude series / multi-book sources
series_pattern = r'\b(series|trilogy|saga|cycle|sequence|franchise)\b'
mask = df["fiction_work_raw"].str.contains(series_pattern, case=False, na=False)
df = exclude(mask, "source_is_series_not_single_book", df, excluded_rows)

# 3f. Exclude obvious non-book sources (plays, comics, short story collections)
non_book_pattern = r'\b(play|comic|manga|graphic novel|short stor|novella collection|anthology|screenplay)\b'
mask = df["fiction_work_raw"].str.contains(non_book_pattern, case=False, na=False)
df = exclude(mask, "source_is_not_novel_or_single_book", df, excluded_rows)

# 3g. Exclude films whose titles are clearly TV or direct-to-video markers
tv_pattern = r'\b(TV|television|miniseries|mini-series|episode|direct.to.video|straight.to.video)\b'
mask = df["film_adaptation_raw"].str.contains(tv_pattern, case=False, na=False)
df = exclude(mask, "film_appears_to_be_tv_or_dtv", df, excluded_rows)

# 3h. Exclude rows where film title looks like a sequel number (e.g. "Part 2", "2: ...")
# that suggests the adaptation is of the whole series, not one book
sequel_prefix = r'^(Part\s+\d|Chapter\s+\d|\d+\s*:)'
mask = df["film_title"].str.contains(sequel_prefix, case=False, na=False)
df = exclude(mask, "film_title_suggests_sequel_of_series", df, excluded_rows)

print(f"After hard filters: {len(df)} rows remain")

# ---------------------------------------------------------------------------
# 4. Deduplicate: keep one adaptation per source book
#    Priority: most English-looking title, then most recent film year
# ---------------------------------------------------------------------------

def english_score(title):
    """Higher score = more likely to be a mainstream English-language film."""
    if not isinstance(title, str):
        return 0
    score = 0
    # Prefer titles with only ASCII chars
    if all(ord(c) < 128 for c in title):
        score += 2
    # Penalise obvious foreign language markers
    foreign_markers = ['french:', 'german:', 'italian:', 'japanese:', 'spanish:',
                       'chinese:', 'korean:', 'portuguese:', 'russian:', 'hebrew:',
                       'hindi:', 'arabic:']
    raw_lower = title.lower()
    if any(m in raw_lower for m in foreign_markers):
        score -= 3
    return score

df["_eng_score"] = df["film_adaptation_raw"].apply(english_score)

# Normalise book title for dedup grouping
df["_book_key"] = (
    df["book_title"]
    .str.lower()
    .str.replace(r'[^a-z0-9 ]', '', regex=True)
    .str.strip()
)

# Within each source book, keep the row with (1) highest English score, then (2) latest film year
df = (
    df.sort_values(["_book_key", "_eng_score", "film_year"], ascending=[True, False, False])
    .drop_duplicates(subset=["_book_key"], keep="first")
    .copy()
)

print(f"After deduplication (one adaptation per book): {len(df)} rows")

# ---------------------------------------------------------------------------
# 5. Prefer English-language / mainstream films
#    Drop rows whose film title contains obvious foreign-only markers
# ---------------------------------------------------------------------------

foreign_title_pattern = (
    r'(\bFrench\b|\bGerman\b|\bItalian\b|\bSpanish\b|\bJapanese\b|\bChinese\b'
    r'|\bKorean\b|\bPortuguese\b|\bRussian\b|\bHindi\b|\bHebrew\b|\bArabic\b'
    r'|\bDutch\b|\bSwedish\b|\bNorwegian\b|\bDanish\b|\bFinnish\b|\bTurkish\b'
    r'|\bPolish\b|\bGreek\b)'
)
mask = df["film_adaptation_raw"].str.contains(foreign_title_pattern, case=False, na=False)
foreign_df = df[mask].copy()
foreign_df["exclusion_reason"] = "likely_non_english_language_film"
excluded_rows.append(foreign_df)
df = df[~mask].copy()
print(f"After removing likely non-English films: {len(df)} rows")

# ---------------------------------------------------------------------------
# 6. Assign genre buckets (keyword-based on fiction_work_raw + film title)
# ---------------------------------------------------------------------------

GENRE_BUCKETS = [
    "Drama_Literary",
    "Fantasy_SciFi",
    "Romance",
    "Thriller_Mystery_Crime",
    "Horror",
    "Historical_Biography",
    "Family_Children_YA",
    "Action_Adventure",
    "Comedy_Satire",
    "Other",
]

GENRE_KEYWORDS = {
    "Horror": [
        "horror", "haunting", "ghost", "vampire", "zombie", "demon", "witch",
        "creature", "monster", "terror", "nightmare", "evil", "occult",
        "possession", "exorcis", "slasher", "lovecraft",
        # authors
        "stephen king", "dean koontz", "peter straub", "shirley jackson",
        "clive barker", "anne rice", "r.l. stine", "joe hill",
        # titles/keywords
        "dracula", "frankenstein", "the shining", "it ", "carrie",
        "misery", "the haunting", "pet sematary", "the fog", "amityville",
        "paranormal", "poltergeist", "séance", "seance", "cursed",
    ],
    "Fantasy_SciFi": [
        "fantasy", "science fiction", "sci-fi", "scifi", "wizard", "magic",
        "dragon", "elf", "dwarf", "hobbit", "narnia", "dystopia", "dystopian",
        "utopia", "futur", "space", "alien", "robot", "android", "time travel",
        "parallel world", "supernatural", "enchant", "sorcerer", "sorcery",
        "warlock", "prophecy", "realm", "kingdom", "orcs", "magical",
        # authors
        "tolkien", "rowling", "c.s. lewis", "ursula le guin", "philip pullman",
        "george r.r. martin", "terry pratchett", "neil gaiman", "suzanne collins",
        "veronica roth", "james dashner", "rick riordan", "cassandra clare",
        "brandon sanderson", "robin hobb", "patrick rothfuss",
        "orson scott card", "arthur c. clarke", "isaac asimov", "ray bradbury",
        "philip k. dick", "h.g. wells", "michael crichton",
        # titles
        "harry potter", "lord of the rings", "the hobbit", "golden compass",
        "his dark materials", "eragon", "maze runner", "divergent",
        "hunger games", "ender's game", "the giver", "dune", "jurassic",
        "percy jackson", "mortal instruments", "twilight", "the host",
        "beautiful creatures", "ready player", "wool", "snowpiercer",
        "the road", "never let me go",
    ],
    "Romance": [
        "romance", "love story", "love affair", "falling in love", "chick lit",
        "bridget jones", "pride and prejudice",
        # authors
        "nicholas sparks", "jojo moyes", "nora roberts", "danielle steel",
        "jane austen", "emily brontë", "emily bronte", "charlotte brontë",
        "charlotte bronte", "cecelia ahern", "marian keyes", "sophie kinsella",
        "helen fielding", "e.l. james", "sylvia day", "colleen hoover",
        "taylor jenkins reid",
        # titles
        "the notebook", "a walk to remember", "dear john", "the lucky one",
        "me before you", "after", "fifty shades", "outlander",
        "wuthering heights", "sense and sensibility", "emma", "persuasion",
        "northanger abbey", "the rosie project", "ps i love you",
        "confessions of a shopaholic",
    ],
    "Thriller_Mystery_Crime": [
        "thriller", "mystery", "crime", "detective", "murder", "killer",
        "spy", "espionage", "assassination", "forensic", "police", "fugitive",
        "conspiracy", "heist", "serial killer", "investigation", "whodunit",
        "noir", "suspense", "kidnap", "missing", "hitman", "assassin",
        # authors
        "agatha christie", "john grisham", "james patterson", "lee child",
        "dan brown", "stieg larsson", "gillian flynn", "tana french",
        "michael connelly", "thomas harris", "patricia cornwell",
        "harlan coben", "david baldacci", "lisa gardner", "karin slaughter",
        "jo nesbø", "jo nesbo", "henning mankell", "peter james",
        "ian rankin", "val mcdermid", "kate atkinson", "jeffrey deaver",
        "robert ludlum", "john le carré", "john le carre", "tom clancy",
        "vince flynn", "brad thor", "daniel silva",
        # titles
        "girl with the dragon tattoo", "gone girl", "the girl on the train",
        "big little lies", "sharp objects", "in cold blood", "silence of the lambs",
        "hannibal", "red dragon", "the da vinci code", "angels and demons",
        "jack reacher", "the firm", "the pelican brief", "the client",
        "sherlock holmes", "hercule poirot", "miss marple",
        "twenty-four hours", "the girl who",
    ],
    "Historical_Biography": [
        "historical", "history", "biography", "memoir", "war", "civil war",
        "world war", "wwii", "ww2", "ww1", "napoleon", "medieval", "colonial",
        "victorian", "elizabethan", "revolution", "empire",
        "century", "nonfiction", "non-fiction", "autobiography",
        "gladiator", "roman", "greek", "ancient",
        # authors / titles
        "hilary mantel", "ken follett", "colm tóibín", "colm toibin",
        "sebastian faulks", "pat barker", "bernard cornwell",
        "philippa gregory", "sarah waters", "kate mosse",
        "laura hillenbrand", "erik larson", "david grann",
        "the crown", "wolf hall", "bring up the bodies",
        "seabiscuit", "unbroken", "the boys in the boat",
        "the zookeeper's wife", "the nightingale", "all the light",
        "the pillars of the earth", "the bronze horseman",
        "gone with the wind", "cold mountain",
        "schindler", "the pianist", "life is beautiful",
        "atonement", "the english patient",
    ],
    "Family_Children_YA": [
        "children", "child", "young adult", "ya fiction", "teen", "teenage",
        "adolescent", "juvenile", "family", "fairy tale", "fairy-tale",
        "fable", "picture book",
        # authors
        "roald dahl", "judy blume", "beverly cleary", "lemony snicket",
        "e.b. white", "a.a. milne", "beatrix potter", "dr. seuss",
        "shel silverstein", "r.l. stine", "christopher paolini",
        "meg cabot", "sarah dessen", "john green", "rainbow rowell",
        "david levithan", "e. lockhart", "laurie halse anderson",
        "walter dean myers", "louis sachar",
        # titles
        "a series of unfortunate", "charlie and the chocolate",
        "charlotte's web", "winnie the pooh", "the lion the witch",
        "matilda", "james and the giant peach", "fantastic mr fox",
        "the bfg", "charlie bucket", "coraline", "the spiderwick",
        "inkheart", "holes", "because of winn-dixie", "the sisterhood",
        "diary of a wimpy", "captain underpants", "the secret garden",
        "a little princess", "little women", "little men",
        "the fault in our stars", "looking for alaska",
        "an abundance of katherines", "paper towns", "turtles all the way",
        "wonder", "the one and only ivan", "bridge to terabithia",
        "tuck everlasting", "hatchet", "island of the blue dolphins",
        "the outsiders", "speak", "thirteen reasons why",
        "the perks of being", "eleanor and park", "fangirl",
        "where the wild things", "pinocchio", "geppetto",
    ],
    "Action_Adventure": [
        "adventure", "action", "quest", "explorer", "expedition", "treasure",
        "pirate", "soldier", "warrior", "battle", "siege",
        "survival", "jungle", "island", "sea voyage", "ship",
        "hunt", "wild", "bounty hunter", "mercenary",
        # authors
        "clive cussler", "matthew reilly", "wilbur smith", "james rollins",
        "vince flynn", "brad thor",
        # titles
        "count of monte cristo", "three musketeers", "20000 leagues",
        "journey to the center", "around the world", "robinson crusoe",
        "treasure island", "king solomon's mines", "the lost world",
        "the jungle book", "tarzan", "call of the wild", "white fang",
        "old man and the sea", "the last of the mohicans",
        "master and commander", "captain blood", "hornblower",
        "national treasure", "the mummy", "the legend of zorro",
        "the lone ranger",
    ],
    "Comedy_Satire": [
        "comedy", "satire", "satirical", "humour", "humor", "funny", "farce",
        "parody", "mockery", "wit", "absurd", "slapstick", "irony", "ironic",
        "comic novel",
        # authors
        "terry pratchett", "douglas adams", "p.g. wodehouse", "evelyn waugh",
        "joseph heller", "kurt vonnegut", "carl hiaasen", "christopher buckley",
        "tom perrotta", "nick hornby", "david sedaris",
        # titles
        "hitchhiker's guide", "catch-22", "slaughterhouse", "bridget jones",
        "about a boy", "high fidelity", "fever pitch", "the hundred-year-old",
        "confessions of a shopaholic", "waking ned", "election",
    ],
    "Drama_Literary": [
        "literary", "drama", "literary fiction", "coming of age", "bildungsroman",
        "family drama", "domestic", "social novel", "realism", "character study",
        "prize", "booker", "pulitzer", "nobel", "man booker",
        # authors (literary fiction writers)
        "ian mcewan", "kazuo ishiguro", "jhumpa lahiri", "zadie smith",
        "colm tóibín", "richard russo", "jonathan franzen", "jeffrey eugenides",
        "michael ondaatje", "ann patchett", "marilynne robinson",
        "edward p. jones", "andre dubus", "alice munro", "cormac mccarthy",
        "toni morrison", "john updike", "philip roth", "saul bellow",
        "don delillo", "thomas pynchon", "david foster wallace",
        "f. scott fitzgerald", "ernest hemingway", "william faulkner",
        "john steinbeck", "harper lee", "truman capote", "flannery o'connor",
        "william styron", "richard yates", "revolutionary road",
        "anne tyler", "larry mcmurtry", "larry brown", "richard ford",
        "tobias wolff", "tim o'brien", "amy tan", "chang-rae lee",
        "edwidge danticat", "junot díaz", "junot diaz",
        "gabriel garcía márquez", "gabriel garcia marquez",
        "isabel allende", "mario vargas llosa", "milan kundera",
        "günter grass", "gunter grass", "naguib mahfouz",
        "orhan pamuk", "haruki murakami", "banana yoshimoto",
        # titles
        "atonement", "the remains of the day", "never let me go",
        "on chesil beach", "saturday", "amsterdam",
        "the kite runner", "a thousand splendid suns",
        "the god of small things", "interpreter of maladies",
        "the corrections", "freedom", "middlesex",
        "the virgin suicides", "the hours", "mrs dalloway",
        "to kill a mockingbird", "the great gatsby",
        "of mice and men", "east of eden", "grapes of wrath",
        "the old man and the sea", "for whom the bell tolls",
        "a farewell to arms", "the sun also rises",
        "beloved", "the color purple", "their eyes were watching",
        "one hundred years of solitude", "love in the time of cholera",
        "the alchemist", "like water for chocolate",
        "captain corelli", "captain corelli's mandolin",
        "cold mountain", "the english patient",
    ],
}

# Genre target ranges (min, max) per bucket
GENRE_TARGETS = {
    "Drama_Literary":        (20, 53),  # broad catch-all for literary fiction
    "Fantasy_SciFi":         (20, 30),
    "Romance":               (10, 20),
    "Thriller_Mystery_Crime":(20, 30),
    "Horror":                (10, 20),
    "Historical_Biography":  (10, 20),
    "Family_Children_YA":    (15, 30),
    "Action_Adventure":      (15, 25),
    "Comedy_Satire":         (5,  15),
    "Other":                 (0,  10),
}


def assign_genre(fiction_raw, film_raw):
    combined = (str(fiction_raw) + " " + str(film_raw)).lower()

    scores = {genre: 0 for genre in GENRE_BUCKETS}
    for genre, keywords in GENRE_KEYWORDS.items():
        for kw in keywords:
            if kw in combined:
                scores[genre] += 1

    # Pick highest scoring genre (excluding "Other")
    best = max(
        (g for g in GENRE_BUCKETS if g != "Other"),
        key=lambda g: scores[g],
    )
    # Only assign "Other" if truly no keyword matched at all;
    # otherwise fall back to Drama_Literary (most literary fiction
    # that doesn't match a specific genre is dramatic/literary by nature)
    if scores[best] > 0:
        return best
    return "Drama_Literary"


df["genre_bucket"] = df.apply(
    lambda r: assign_genre(r["fiction_work_raw"], r["film_adaptation_raw"]), axis=1
)

print("\nGenre distribution in filtered pool:")
print(df["genre_bucket"].value_counts().to_string())

# ---------------------------------------------------------------------------
# 7. Assign release period
# ---------------------------------------------------------------------------

def release_period(year):
    if pd.isna(year):
        return None
    y = int(year)
    if y <= 2004:   return "2000_2004"
    if y <= 2009:   return "2005_2009"
    if y <= 2014:   return "2010_2014"
    if y <= 2019:   return "2015_2019"
    return "2020_2024"

df["release_period"] = df["film_year"].apply(release_period)

print("\nRelease period distribution in filtered pool:")
print(df["release_period"].value_counts().sort_index().to_string())

# ---------------------------------------------------------------------------
# 8. Select final 200 with genre and year diversity
# ---------------------------------------------------------------------------
# Strategy: stratified selection respecting genre targets and year balance.
# Within each genre, sort by year spread to ensure temporal diversity.

TARGET_TOTAL = 200
YEAR_PERIODS = ["2000_2004", "2005_2009", "2010_2014", "2015_2019", "2020_2024"]
MIN_PER_PERIOD = 25  # soft target

selected_indices = []
genre_counts = {g: 0 for g in GENRE_BUCKETS}
period_counts = {p: 0 for p in YEAR_PERIODS}

# Sort candidates: prefer titles with ASCII-only film titles (more likely English),
# and spread evenly across years within each genre.
df = df.sort_values(["genre_bucket", "release_period", "_eng_score"],
                    ascending=[True, True, False]).reset_index(drop=True)

# Pass 1: fill up to genre minimums, spread across years
for genre in GENRE_BUCKETS:
    genre_min = GENRE_TARGETS[genre][0]
    genre_max = GENRE_TARGETS[genre][1]
    pool = df[df["genre_bucket"] == genre].copy()

    if len(pool) == 0:
        continue

    # Distribute across periods as evenly as possible
    period_groups = {p: pool[pool["release_period"] == p].index.tolist()
                     for p in YEAR_PERIODS}

    added = 0
    round_robin = True
    period_iters = {p: iter(period_groups[p]) for p in YEAR_PERIODS}

    while added < genre_min:
        made_progress = False
        for period in YEAR_PERIODS:
            if added >= genre_min:
                break
            try:
                idx = next(period_iters[period])
                if idx not in selected_indices:
                    selected_indices.append(idx)
                    genre_counts[genre] += 1
                    period_counts[period] += 1
                    added += 1
                    made_progress = True
            except StopIteration:
                pass
        if not made_progress:
            break

print(f"\nAfter pass 1 (fill genre minimums): {len(selected_indices)} selected")

# Pass 2: fill remaining slots up to 200, respecting genre maximums
remaining_needed = TARGET_TOTAL - len(selected_indices)

# Prioritise underrepresented year periods first
all_remaining = [i for i in df.index if i not in selected_indices]

# Sort remaining by (period_count ascending, genre_count ascending)
def priority_key(idx):
    row = df.loc[idx]
    pc = period_counts.get(row["release_period"], 0)
    gc = genre_counts.get(row["genre_bucket"], 0)
    gmax = GENRE_TARGETS[row["genre_bucket"]][1]
    # Penalise if genre is at max
    at_max = 1 if gc >= gmax else 0
    return (at_max, pc, gc)

all_remaining_sorted = sorted(all_remaining, key=priority_key)

for idx in all_remaining_sorted:
    if len(selected_indices) >= TARGET_TOTAL:
        break
    row = df.loc[idx]
    genre = row["genre_bucket"]
    period = row["release_period"]
    if genre_counts[genre] >= GENRE_TARGETS[genre][1]:
        continue
    selected_indices.append(idx)
    genre_counts[genre] += 1
    period_counts[period] += 1

print(f"After pass 2 (fill to 200): {len(selected_indices)} selected")

# ---------------------------------------------------------------------------
# 9. Build final and excluded DataFrames
# ---------------------------------------------------------------------------

final_df = df.loc[selected_indices].copy().reset_index(drop=True)
final_df["row_id"] = range(1, len(final_df) + 1)
final_df["match_confidence"] = "medium"  # to be upgraded after manual review

# Clean up helper columns
final_df = final_df[[
    "row_id",
    "book_title",
    "book_author",
    "book_year",
    "film_title",
    "film_year",
    "release_period",
    "genre_bucket",
    "match_confidence",
    "fiction_work_raw",
    "film_adaptation_raw",
    "source_page_url",
]].rename(columns={
    "book_year": "book_publication_year",
    "film_year": "movie_release_year",
})

# Not-selected from the filtered pool
not_selected = df.loc[[i for i in df.index if i not in selected_indices]].copy()
not_selected["exclusion_reason"] = "not_selected_sampling_design"

# Combine all excluded
all_excluded = pd.concat(
    [pd.concat(excluded_rows, ignore_index=True) if excluded_rows else pd.DataFrame(),
     not_selected],
    ignore_index=True
)
excl_cols = ["book_title", "book_author", "film_title", "film_year",
             "fiction_work_raw", "film_adaptation_raw", "exclusion_reason"]
excl_cols = [c for c in excl_cols if c in all_excluded.columns]
excluded_out = all_excluded[excl_cols].copy()

# ---------------------------------------------------------------------------
# 10. Print summary and save
# ---------------------------------------------------------------------------

print("\n=== FINAL 200 SUMMARY ===")
print(f"Total rows: {len(final_df)}")
print("\nGenre distribution:")
print(final_df["genre_bucket"].value_counts().to_string())
print("\nRelease period distribution:")
print(final_df["release_period"].value_counts().sort_index().to_string())
print(f"\nYear range: {final_df['movie_release_year'].min()} – {final_df['movie_release_year'].max()}")
print(f"Excluded rows total: {len(excluded_out)}")

final_df.to_csv("book_movie_adaptations_final_200.csv", index=False, encoding="utf-8-sig")
excluded_out.to_csv("book_movie_adaptations_excluded.csv", index=False, encoding="utf-8-sig")

print("\nSaved:")
print("  book_movie_adaptations_final_200.csv")
print("  book_movie_adaptations_excluded.csv")
