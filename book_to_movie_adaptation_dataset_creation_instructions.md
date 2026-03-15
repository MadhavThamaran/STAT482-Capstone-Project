# Claude Execution Guide: Building the 200-Title Book-to-Movie Adaptation Dataset

## Purpose

This document tells Claude exactly how to build the **200-title dataset** for the project:

**Predict the IMDb rating and opening weekend box office of movies adapted from books, using adaptations released from 2000–2024.**

The goal is to produce a **clean, documented, analysis-ready CSV** containing **200 book-to-movie adaptations** with consistent metadata from the book side and movie side.

This guide is focused on:
- how to build the 200-title list,
- how to choose titles,
- how to enforce genre diversity,
- how to document uncertain matches,
- and what the final CSV schema should look like.

---

## 1. Final Objective

Claude should help build a dataset with:

- **exactly 200 rows**
- each row representing **one movie adaptation of one identifiable source book**
- movie release year between **2000 and 2024**
- cleaned and standardized variables for:
  - book metadata
  - movie metadata
  - IMDb rating
  - opening weekend domestic box office
  - genre buckets
  - derived variables used for EDA and modeling

The final output should include:

1. **Main final CSV** with 200 usable observations  
2. **Exclusion log CSV** for dropped titles  
3. **Ambiguity review CSV** for uncertain matches  
4. **Data dictionary** describing every variable  
5. **Short build summary** documenting how the 200 titles were chosen

---

## 2. High-Level Dataset Philosophy

The 200-title list should be:

- **cleaner rather than larger**
- **genre-diverse rather than perfectly balanced**
- **modern and comparable**
- **built from identifiable book-to-film pairs**
- **suitable for EDA and predictive modeling**

Claude should prefer:
- fewer ambiguous titles,
- more consistent metadata,
- and clearer inclusion logic.

Do **not** maximize quantity at the expense of quality.

---

## 3. Core Inclusion Rules

A title can be included only if all of the following are true:

1. The **movie release year** is between **2000 and 2024**, inclusive
2. The movie is a **feature film**
3. The movie is based primarily on a **single identifiable book or novel**
4. The source book was published **after 1850** and **before** the movie release
5. The movie has an available **IMDb rating**
6. The movie has available **opening weekend domestic box office**
7. The source book has accessible metadata such as:
   - title
   - author
   - publication year
   - average rating
   - ratings count or review count
8. The match between book and movie is at least **medium confidence**, and most final titles should be **high confidence**

---

## 4. Core Exclusion Rules

A title should be excluded if any of the following hold:

1. The source material is ambiguous
2. The movie is based on:
   - multiple books with no clear primary source,
   - a comic franchise rather than a single book,
   - a short story collection,
   - a play,
   - a TV series,
   - or a vague “inspired by” literary work
3. The title is a TV movie, limited series, or miniseries rather than a theatrical feature film
4. Key outcome data is missing
5. The source book cannot be matched confidently to book metadata
6. There are duplicate records for the same adaptation and the duplicate cannot be resolved cleanly
7. The source book was published **in 1850 or earlier** (pre-1851 books are excluded due to insufficient and inconsistent metadata availability on modern platforms such as Goodreads)

---

## 5. One Row = One Adaptation Rule

Each row should represent:

> one movie adaptation matched to one primary source book

### Important implications
- If one book has several movie adaptations, only include one unless there is a strong reason to include multiple distinct adaptations.
- If one movie draws from several books, exclude it unless one book is clearly the primary source.
- If the same book has both an original film and remake within 2000–2024, pick only one unless both are especially important and do not distort the sample.

### Default duplicate rule
If the same source book appears multiple times:
- keep the **most widely recognized theatrical adaptation in 2000–2024**
- log the others in the exclusion file with reason:
  - `duplicate_source_book`
  - `duplicate_adaptation_version`

---

## 6. Recommended Build Process

Claude should follow the process below in order.

---

## 7. Phase A: Build a Large Candidate Pool

### Goal
Create an initial pool of **at least 300–400 candidate adaptations** before filtering down to the final 200.

### Why?
Because:
- some titles will be ambiguous,
- some will be missing box office data,
- some will have weak book matches,
- and some genres may be overrepresented.

### Candidate sources
Claude should use trusted adaptation sources such as:
- Wikipedia adaptation lists
- Wikidata-style “based on” relationships
- curated book-to-film adaptation lists
- movie pages that explicitly state the source book

### Required fields in the candidate pool
For each candidate, capture at minimum:

- `candidate_movie_title`
- `candidate_movie_release_year`
- `candidate_book_title`
- `candidate_book_author`
- `candidate_adaptation_source`
- `notes`

### Candidate pool file name
`candidate_adaptations_raw.csv`

---

## 8. Phase B: Initial Screening

Apply the hard filters first.

### Remove titles that are:
- outside 2000–2024
- not feature films
- not clearly based on a single identifiable book
- lacking obvious movie or book metadata sources
- clearly missing opening weekend data

### Output after screening
A smaller file:
`candidate_adaptations_screened.csv`

### Suggested target size after screening
Around **250–300 titles**

---

## 9. Phase C: Assign Broad Genre Buckets

Before choosing the final 200, every screened candidate should be assigned to a **broad genre bucket**.

### Why assign genre before final selection?
Because the final sample should be intentionally diverse, not accidentally dominated by one type of adaptation.

### Rule
Claude should assign **one primary genre bucket** to each title using the **source book** as the main basis, with movie genre used as a secondary reference if needed.

### Allowed genre buckets
Use exactly these broad buckets:

1. `Drama_Literary`
2. `Fantasy_SciFi`
3. `Romance`
4. `Thriller_Mystery_Crime`
5. `Horror`
6. `Historical_Biography`
7. `Family_Children_YA`
8. `Action_Adventure`
9. `Comedy_Satire`
10. `Other`

### Notes
- Use only one primary bucket per row
- If a title clearly fits multiple buckets, choose the one that best reflects the book’s main market identity
- Keep a free-text `genre_assignment_notes` field for difficult cases

---

## 10. Genre Quota Strategy

The dataset should be **semi-balanced**, not perfectly balanced.

### Why not perfectly balanced?
Because a perfectly equal allocation is unrealistic and may overrepresent rare adaptation categories.

### Why not completely unconstrained?
Because then one or two popular genres could dominate the data.

### Final genre quota rule
Use the following **soft target ranges** for the final 200 titles:

| Genre Bucket | Target Range |
|---|---:|
| Drama_Literary | 20–30 |
| Fantasy_SciFi | 20–30 |
| Romance | 10–20 |
| Thriller_Mystery_Crime | 20–30 |
| Horror | 10–20 |
| Historical_Biography | 10–20 |
| Family_Children_YA | 20–30 |
| Action_Adventure | 15–25 |
| Comedy_Satire | 5–15 |
| Other | 0–10 |

### Hard balancing rules
- No single bucket should exceed **30 titles**
- No major bucket should have fewer than **10 titles** unless there are strong data limitations
- At least **7 distinct buckets** must appear in the final 200
- Prefer all **9 major buckets** before relying on `Other`

---

## 11. Year Coverage Strategy

The final sample should also be spread across the 2000–2024 window.

### Goal
Avoid a final dataset that is concentrated only in recent years.

### Recommended year grouping
Claude should track counts by these release periods:

- `2000–2004`
- `2005–2009`
- `2010–2014`
- `2015–2019`
- `2020–2024`

### Soft target
Try to ensure that each period has at least **25 titles**, unless data limitations make this impossible.

### Why?
This helps:
- reduce time-period bias,
- support EDA by era,
- and prevent the dataset from being overwhelmingly recent.

---

## 12. Popularity Diversity Strategy

The final dataset should include both:
- blockbuster/high-visibility adaptations
- and mid-scale or lower-visibility adaptations

### Reason
If the dataset only includes famous titles, the box office distribution may be too distorted and the conclusions may not generalize well.

### Suggested popularity indicators
Claude should track whether titles appear to be:
- very high popularity,
- medium popularity,
- lower popularity

Use rough indicators such as:
- IMDb vote count
- book ratings count
- opening weekend magnitude

### Rule
Do not intentionally fill the entire sample with only best-known franchises.

---

## 13. Phase D: Build the Final 200 by Controlled Selection

Once the screened pool has:
- adaptation candidates,
- genre buckets,
- year coverage,
- and enough metadata,

Claude should select the final 200 using this priority order:

### Priority 1: Clean match quality
Prefer titles with:
- clear source book
- clear film identity
- available IMDb and box office data
- available book metadata

### Priority 2: Genre coverage
Ensure the final dataset stays within the genre target ranges.

### Priority 3: Year coverage
Avoid concentrating the sample too heavily in one era.

### Priority 4: Popularity diversity
Preserve a mix of:
- blockbuster,
- moderate,
- and less dominant titles.

### Priority 5: Data completeness
Prefer rows with fewer missing non-core fields.

---

## 14. Match Confidence Rules

Every candidate should receive a match confidence label:

- `high`
- `medium`
- `low`

### High confidence
Use when:
- the movie is explicitly documented as based on the identified book,
- the book author is confirmed,
- the year and title align cleanly,
- and metadata sources agree.

### Medium confidence
Use when:
- the match is probably correct,
- but one part required reasonable judgment,
- such as minor title variation or incomplete structured metadata.

### Low confidence
Use when:
- there is meaningful ambiguity,
- multiple possible source books exist,
- or the source relationship is not cleanly documented.

### Final inclusion rule
- Include all `high`
- Include `medium` only if necessary and clearly documented
- Exclude all `low`

---

## 15. Required Side Files

Claude should not only output the final CSV. It should also produce supporting files.

### A. Main dataset
`book_movie_adaptations_final.csv`

### B. Exclusion log
`book_movie_adaptations_excluded.csv`

Columns:
- `movie_title`
- `movie_release_year`
- `book_title`
- `book_author`
- `exclusion_reason`
- `notes`

### C. Ambiguity review file
`book_movie_adaptations_ambiguity_review.csv`

Columns:
- `movie_title`
- `movie_release_year`
- `possible_book_match_1`
- `possible_book_match_2`
- `confidence`
- `ambiguity_notes`
- `resolution_status`

### D. Data dictionary
`book_movie_adaptations_data_dictionary.md`

### E. Build summary
`build_summary.md`

---

## 16. Detailed Step-by-Step Instructions for Claude

### Step 1
Create a raw candidate pool of at least **300–400** book-to-film adaptations released from 2000–2024.

### Step 2
For each candidate, capture:
- movie title
- release year
- source book title
- source author
- source link or citation note
- preliminary notes

### Step 3
Remove candidates that fail obvious inclusion rules:
- not a feature film
- missing core adaptation identity
- not clearly based on a single book
- outside date range

### Step 4
Assign a primary genre bucket using the broad bucket list in this document.

### Step 5
Search for or attach movie-side metadata:
- IMDb rating
- IMDb vote count
- release date
- runtime
- genre
- opening weekend domestic box office

### Step 6
Search for or attach book-side metadata:
- publication year
- average rating
- ratings count
- reviews count
- page count
- broad genre identity
- series indicator if available

### Step 7
Assign `match_confidence` for every row.

### Step 8
Move all low-confidence cases to the ambiguity or exclusion files.

### Step 9
Check genre counts and year counts for the remaining pool.

### Step 10
Select the final 200 rows while respecting:
- genre target ranges,
- year coverage,
- and data completeness.

### Step 11
Standardize all names, dates, and categories.

### Step 12
Create derived variables.

### Step 13
Output:
- final CSV,
- exclusion file,
- ambiguity file,
- dictionary,
- and summary.

---

## 17. Standardization Rules

Claude should apply the following cleaning rules consistently.

### Titles
- preserve official title text in a display column
- also create normalized columns for matching
- remove extra spaces
- standardize punctuation where possible
- keep subtitles if they are part of the official title

### Author names
- store in a consistent `First Last` format when possible
- avoid mixing initials and full names unless the source only provides initials

### Years
- numeric four-digit year only

### Currency fields
- numeric, no dollar signs, no commas in stored CSV values

### Counts
- numeric only
- use integers for vote counts, rating counts, review counts

### Missing values
- use blank or standardized NA representation consistently
- do not mix `NA`, `null`, `unknown`, and `-`

---

## 18. Derived Variables to Create

Claude should create these derived columns in the final dataset:

- `years_between_book_and_movie`
- `log_book_ratings_count`
- `log_book_reviews_count`
- `log_imdb_vote_count`
- `log_opening_weekend_domestic`
- `movie_release_period`
- `book_popularity_bucket`
- `movie_popularity_bucket`

### Formula rules
- `years_between_book_and_movie = movie_release_year - book_publication_year`
- log variables should use `log(x + 1)` if zero values are possible

---

## 19. Target Final CSV Schema

The final CSV should use the following column structure.

### Identifier columns
- `row_id`
- `movie_title`
- `movie_title_normalized`
- `movie_release_year`
- `book_title`
- `book_title_normalized`
- `book_author`

### Match quality and source tracking
- `match_confidence`
- `adaptation_source_note`
- `genre_assignment_notes`

### Movie outcome variables
- `imdb_rating`
- `imdb_vote_count`
- `opening_weekend_domestic`
- `total_domestic_gross`

### Movie predictor variables
- `movie_release_date`
- `movie_release_month`
- `movie_runtime_minutes`
- `movie_genre_raw`
- `movie_genre_bucket`
- `mpaa_rating`
- `distributor`
- `franchise_indicator`

### Book predictor variables
- `book_publication_year`
- `book_avg_rating`
- `book_ratings_count`
- `book_reviews_count`
- `book_page_count`
- `book_genre_raw`
- `book_genre_bucket`
- `book_series_indicator`
- `book_description_length`

### Derived variables
- `years_between_book_and_movie`
- `log_book_ratings_count`
- `log_book_reviews_count`
- `log_imdb_vote_count`
- `log_opening_weekend_domestic`
- `movie_release_period`
- `book_popularity_bucket`
- `movie_popularity_bucket`

### Optional notes column
- `record_notes`

---

## 20. Required Column Types

Claude should enforce or report the following expected types.

### Text columns
- titles
- author
- raw genres
- notes
- distributor
- MPAA rating
- confidence labels

### Integer columns
- release year
- publication year
- vote counts
- ratings counts
- review counts
- runtime minutes
- page count

### Float columns
- IMDb rating
- opening weekend domestic
- total domestic gross
- log-transformed variables

### Binary indicator columns
Prefer `0/1` for:
- `franchise_indicator`
- `book_series_indicator`

---

## 21. Recommended Values for Categorical Buckets

### `movie_release_period`
Allowed values:
- `2000_2004`
- `2005_2009`
- `2010_2014`
- `2015_2019`
- `2020_2024`

### `book_popularity_bucket`
Suggested rule based on ratings count:
- `low`
- `medium`
- `high`

Claude may define thresholds based on quantiles of the final sample.

### `movie_popularity_bucket`
Suggested rule based on IMDb vote count or opening weekend:
- `low`
- `medium`
- `high`

Again, thresholds may be based on quantiles.

---

## 22. Handling Ambiguous Cases

If a candidate title is ambiguous, Claude should never silently force a match.

### Instead:
1. place it in the ambiguity review file
2. record the possible matches
3. describe the ambiguity
4. give a confidence label
5. leave it out of the final 200 unless resolved

### Common ambiguity examples
- same title used by multiple books
- remake based on an older adaptation rather than directly on the book
- multiple books in a series possibly serving as the source
- book vs memoir vs loosely inspired source confusion

---

## 23. Handling Missing Data

### Core variables that must not be missing in the final 200
- `movie_title`
- `movie_release_year`
- `book_title`
- `book_author`
- `imdb_rating`
- `opening_weekend_domestic`
- `book_avg_rating`
- `book_ratings_count`
- `book_publication_year`
- `book_genre_bucket`
- `match_confidence`

### Variables that may be missing if necessary
- `page_count`
- `mpaa_rating`
- `distributor`
- `total_domestic_gross`
- `book_description_length`
- `book_reviews_count`

### Rule
If too many non-core variables are missing for a title, prefer replacing it with a cleaner candidate.

---

## 24. Quality Checks Before Finalizing

Claude should run these checks before finalizing the dataset.

### Row count checks
- exactly 200 rows in final CSV
- no duplicate row IDs
- no exact duplicate movie-title-year pairs

### Match checks
- no low-confidence rows in final CSV
- no unresolved ambiguity included

### Type checks
- numeric fields are truly numeric
- year fields are valid
- no commas or currency symbols in numeric columns

### Coverage checks
- genre counts fall within target ranges as closely as possible
- year periods are reasonably represented
- there is visible variation in book popularity and movie popularity

### Missingness checks
- no missing values in required core columns
- document any allowed missing fields

---

## 25. Suggested Summary Statistics to Produce Alongside the Dataset

Claude should also produce a short summary after the final dataset is built.

### Include:
- total number of final titles
- counts by genre bucket
- counts by release period
- number of excluded titles
- number of ambiguity cases
- median IMDb rating
- median opening weekend gross
- median book ratings count

This will make it easier to transition into EDA.

---

## 26. Build Summary Template

Claude should write a short narrative summary like this:

> We constructed a dataset of 200 book-to-movie adaptations released from 2000 to 2024. Candidate titles were collected from adaptation lists and screened using inclusion criteria requiring a feature film, a clear single source book, available IMDb rating, available opening weekend domestic box office, and accessible book metadata. The final sample was selected using a semi-balanced design to ensure broad genre coverage and year coverage while prioritizing high-confidence book-to-movie matches and complete outcome data.

Claude should also mention:
- how many titles were screened
- how many were excluded
- what the most common exclusion reasons were

---

## 27. Recommended Output File Set

At the end, Claude should produce:

1. `book_movie_adaptations_final.csv`
2. `book_movie_adaptations_excluded.csv`
3. `book_movie_adaptations_ambiguity_review.csv`
4. `book_movie_adaptations_data_dictionary.md`
5. `build_summary.md`

Optional:
6. `genre_counts.csv`
7. `missingness_summary.csv`

---

## 28. Final Instruction to Claude

When building this dataset, prioritize:
- **match quality over quantity**
- **genre diversity over accidental imbalance**
- **clarity over aggressive inclusion**
- **documented judgment over hidden assumptions**

If there is uncertainty, log it.  
If a title is ambiguous, exclude it unless resolved.  
If a bucket is becoming too dominant, select from other strong candidates to preserve diversity.  
The end goal is not just 200 rows. The end goal is **200 credible, analysis-ready rows**.

---