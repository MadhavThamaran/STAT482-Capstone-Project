# Book-to-Movie Adaptation Prediction Project Plan

## Project Title

**Predicting Movie Success from Book Characteristics:  
A Study of Book-to-Movie Adaptations Released from 2000–2024**

---

## 1. Project Overview

This project studies whether characteristics of a **book** can help predict the success of its **movie adaptation**. The focus is on movies released between **2000 and 2024** that are based on previously published books. For each adaptation, the goal is to predict two outcomes:

1. **Movie rating**  
   - Suggested target: IMDb rating

2. **Opening weekend box office performance**  
   - Suggested target: domestic opening weekend gross

This is a strong applied data science project because it combines:
- real-world data collection from multiple sources,
- data cleaning and matching,
- exploratory data analysis,
- predictive modeling,
- and interpretation of which book or adaptation features matter most.

The final report can naturally address the assignment requirements by including:
- an introduction with motivation and research goals,
- a description of the real dataset,
- an exploratory data analysis section,
- and model-based results.

---

## 2. Core Research Question

**Given that a book is adapted into a movie, can we predict the movie’s IMDb rating and opening weekend box office using information about the original book and the adaptation context?**

### Secondary questions
- Do more highly rated books tend to become more highly rated movies?
- Does book popularity help predict commercial success more than critical or audience rating?
- Are some genres more predictable than others?
- Does the time gap between book publication and film release matter?

---

## 3. Recommended Scope

### Time window
- **Movies released from 2000 through 2024**

### Dataset size
- **200 book-to-movie adaptations**

### Why 200?
A dataset of 200 adaptations is a good size for this assignment because it is:
- large enough for meaningful EDA and modeling,
- small enough to manually inspect and clean,
- realistic for a project involving cross-source matching,
- and manageable if Claude is helping compile and clean the data.

A much larger dataset would create too much ambiguity in matching books to their corresponding films. A much smaller dataset would reduce the value of the modeling and make genre or year comparisons less meaningful.

---

## 4. Why Restrict to 2000–2024?

Using adaptations from **2000–2024** gives the project a modern and relatively consistent sample.

### Benefits of this time restriction
- **Better data availability**: newer movies are much more likely to have accessible box office, rating, and metadata.
- **More consistent market conditions**: older films are harder to compare because of inflation, different release strategies, and weaker digital records.
- **Cleaner book metadata**: recent books are more likely to have consistent Goodreads and online metadata.
- **More relevant conclusions**: the results will reflect the modern adaptation ecosystem rather than mixing in films from very different eras.

### Practical benefit
This range reduces the number of missing values and simplifies cleaning.

---

## 5. Suggested Data Sources

This project will likely need data merged from multiple sources.

## Movie-side data
### IMDb
Use IMDb for:
- movie title
- release year
- genre
- runtime
- IMDb rating
- number of IMDb votes

IMDb provides non-commercial datasets with title metadata and ratings.

### Box Office Mojo or The Numbers
Use for:
- opening weekend domestic gross
- total domestic gross if desired
- release date
- distributor if available

Opening **weekend** gross is preferable to opening **day** gross because it is much easier to obtain consistently.

## Book-side data
### Goodreads / UCSD Goodreads datasets / Book Graph
Use for:
- book title
- author
- publication year
- average book rating
- number of book ratings
- number of book reviews
- page count
- description or summary
- genre or shelves/tags if available

These sources provide large-scale book metadata and reader feedback.

## Adaptation matching source
### Wikipedia / Wikidata / curated adaptation lists
Use to identify:
- which movies are based on books
- source title and author
- occasionally the exact source novel when multiple works share a similar name

This is helpful because IMDb alone may not cleanly give the original source book in a structured way for all cases.

---

## 6. Proposed Outcome Variables

The project has **two main response variables**.

### Response 1: IMDb rating
- Continuous variable
- Good for modeling audience or broad public reception

### Response 2: Opening weekend domestic box office
- Continuous variable
- Strong measure of early commercial success
- Likely should be transformed using a logarithm because box office values are usually right-skewed

### Suggested transformed variable
- `log_opening_weekend_gross = log(opening_weekend_gross + 1)`

This usually improves model behavior and makes EDA easier.

---

## 7. Why This Is a Good Statistical / Data Science Project

This project is valuable because it blends:
- **data integration**,
- **feature engineering**,
- **exploratory analysis**,
- **supervised learning**,
- and **interpretation**.

It is also interesting because movie success is multi-dimensional:
- a movie may make a lot of money but have poor ratings,
- or it may earn modest revenue but receive strong ratings.

That means predicting **rating** and **box office** separately is more informative than using only one definition of success.

---

## 8. Sampling Strategy for the 200 Books

This is one of the most important design choices in the project.

You should **not** simply take the first 200 adaptations you find, and you should also **not** force a perfectly equal number of movies in every genre unless that causes unnatural sampling.

The best approach is a **semi-balanced, intentionally diverse sample**.

### Recommended sampling principle
Build a dataset of 200 adaptations that is:
- spread across the years 2000–2024,
- diverse in genre,
- varied in popularity level,
- and broad in commercial scale.

This produces a dataset that better reflects the real adaptation landscape while still allowing comparisons.

---

## 9. Rationale for How to Pick the 200 Books

### A. Why not use a purely random sample?
A purely random sample sounds objective, but in practice it can create problems:
- some genres may dominate the dataset,
- blockbuster franchises may appear too often,
- small genres may disappear entirely,
- and the resulting data may be unbalanced in a way that weakens EDA and modeling.

For example, if the random sample overrepresents fantasy, thriller, and YA adaptations, then your models may mostly learn those patterns and perform poorly across other genres.

### B. Why not force perfectly balanced genres?
A perfectly balanced design, such as taking exactly 25 titles from 8 genres, also has drawbacks:
- the real world is not perfectly balanced,
- some genres have many more adaptations than others,
- forcing equal counts may overrepresent rare categories,
- and it can make the dataset less realistic.

### C. Best option: semi-balanced genre coverage
A better approach is to intentionally ensure that major genres are represented, while still roughly reflecting the real adaptation market.

This means:
- include all major genre families,
- avoid extreme overrepresentation of one genre,
- but do not require exact equality.

### D. Why genre diversity matters
Genre likely affects both:
- rating patterns,
- and commercial performance.

A genre-diverse sample allows you to answer more interesting questions:
- Are drama adaptations rated more highly than action adaptations?
- Are fantasy adaptations more commercially successful?
- Does genre interact with book popularity?

---

## 10. Recommended Sampling Design

A practical design is to create broad genre buckets and assign approximate targets.

### Possible genre buckets
- Drama / Literary fiction
- Fantasy / Sci-fi
- Romance
- Thriller / Mystery / Crime
- Horror
- Historical / War / Biography
- Family / Children / Animation-linked source books
- Young Adult / Teen
- Action / Adventure
- Comedy / Satire

Because many books fit multiple genres, the exact bucket assignment does not need to be perfect. The goal is coverage, not perfection.

### Suggested rule
Try to avoid any one genre making up more than about **20–25%** of the sample unless the raw adaptation landscape strongly supports it.

### Additional diversity goals
The 200 titles should also vary by:
- release year,
- book popularity,
- movie popularity,
- franchise vs standalone,
- prestige adaptation vs commercial adaptation.

---

## 11. Recommended Inclusion Criteria

A title should be included if:

1. The movie was released between **2000 and 2024**
2. The movie is a **feature film**
3. The movie is based primarily on a **single identifiable book or novel**
4. The source book was published before the movie
5. The movie has an identifiable IMDb rating
6. The movie has accessible opening weekend box office data
7. The source book has accessible metadata such as average rating and ratings count

---

## 12. Recommended Exclusion Criteria

A title should be excluded if:

1. The source material is ambiguous or hard to identify
2. The movie is based on:
   - a short story collection,
   - a comic universe rather than a specific book,
   - a play,
   - a vague “inspired by” literary source,
   - or multiple books with no clean primary source
3. The movie is a TV miniseries rather than a theatrical feature film
4. Key variables are missing and cannot be reasonably recovered
5. The adaptation relationship is too unclear for confident matching

### Why exclude ambiguous cases?
Because the biggest threat to the project is bad matching.  
A smaller but cleaner dataset is much better than a larger noisy one.

---

## 13. Variables to Collect

### A. Identifier variables
- `movie_title`
- `movie_release_year`
- `book_title`
- `book_author`

### B. Movie outcome variables
- `imdb_rating`
- `imdb_vote_count`
- `opening_weekend_domestic`
- `total_domestic_gross` (optional)

### C. Movie predictor variables
- `movie_genre_main`
- `movie_genre_secondary`
- `runtime_minutes`
- `release_month`
- `mpaa_rating` (if available)
- `distributor` (optional)
- `franchise_indicator` (optional)

### D. Book predictor variables
- `book_publication_year`
- `book_avg_rating`
- `book_ratings_count`
- `book_reviews_count`
- `page_count`
- `book_genre_main`
- `book_genre_secondary`
- `book_description_length`
- `book_series_indicator` (optional)

### E. Adaptation-derived variables
- `years_between_book_and_movie`
- `log_book_ratings_count`
- `log_book_reviews_count`
- `log_imdb_vote_count`
- `log_opening_weekend_domestic`
- `book_popularity_bucket`
- `movie_release_period`

---

## 14. Practical Matching Rules

Because this project combines several sources, Claude should use consistent rules when matching books and movies.

### Matching priority
1. Confirm the adaptation relationship through a trusted adaptation list or Wikipedia/Wikidata
2. Match the movie title and release year to IMDb/box office records
3. Match the book title and author to Goodreads or the chosen book dataset
4. Record uncertain matches in a review table rather than forcing them into the final sample

### Important rule
If a match is uncertain, it should be flagged and reviewed manually.  
Do not silently include uncertain matches.

### Good documentation practice
Maintain a field such as:
- `match_confidence = high / medium / low`

Only `high` and maybe some `medium` confidence matches should remain in the final analysis dataset.

---

## 15. Data Cleaning Plan

Claude should be used for the cleaning and compilation process, but the workflow should be explicit.

### Step 1: Build the initial candidate list
Compile a raw list of adaptations from 2000–2024.

### Step 2: Standardize titles
Normalize:
- capitalization,
- punctuation,
- spacing,
- subtitle usage,
- and release-year formatting.

### Step 3: Remove duplicates
Some books have multiple adaptations.  
Decide on a consistent rule, such as:
- keep the most prominent theatrical adaptation in the period,
- or allow multiple adaptations only if they are clearly distinct and still fit the 200-title design.

### Step 4: Verify the source book
Ensure the movie is actually based on the listed book.

### Step 5: Handle missing values
- remove titles missing core outcomes,
- impute only when reasonable for non-core features,
- document all removals.

### Step 6: Transform skewed variables
Likely apply logs to:
- book ratings count,
- book reviews count,
- IMDb vote count,
- opening weekend gross.

### Step 7: Standardize genres
Genres from different sources will not align perfectly.  
Claude should map them into a smaller set of broad genre buckets.

### Step 8: Create derived variables
Examples:
- years between book publication and film release
- popularity buckets
- release decade or release period
- whether the source book is part of a series

---

## 16. Recommended Genre Strategy in Detail

This project should use **broad genre buckets** rather than very fine genre labels.

### Why broad buckets?
Fine labels are messy and inconsistent across data sources.  
For example:
- one source may say “speculative fiction,”
- another says “science fiction,”
- another says “fantasy/scifi,”
- another uses multiple tags.

Broad buckets reduce noise.

### Example broad genre mapping
- Fantasy / Sci-fi
- Drama / Literary
- Romance
- Thriller / Mystery / Crime
- Horror
- Historical / Biography
- Action / Adventure
- Family / Children / YA
- Comedy / Satire
- Other

### Should classes be balanced?
Not perfectly.  
Instead, use a **coverage-aware sample**:
- make sure each major bucket appears enough to analyze,
- but allow common adaptation genres to appear more often.

### Recommended rationale to state in the report
> The sample was designed to be genre-diverse rather than strictly genre-balanced. This approach avoids severe overrepresentation of dominant genres while still preserving a realistic view of the adaptation market.

That is a strong and defensible methodological choice.

---

## 17. Exploratory Data Analysis Plan

The EDA section should describe both the structure of the dataset and the initial patterns.

### A. Basic summaries
- number of observations
- year range
- genre counts
- missingness summary
- means, medians, standard deviations

### B. Distribution plots
- histogram of IMDb ratings
- histogram of opening weekend gross
- histogram of log opening weekend gross
- histogram of book ratings
- histogram of book popularity variables

### C. Relationship plots
- scatterplot: book average rating vs IMDb rating
- scatterplot: book ratings count vs opening weekend gross
- scatterplot: years between publication and movie release vs IMDb rating
- scatterplot: page count vs runtime
- boxplots of IMDb rating by genre
- boxplots of opening weekend by genre

### D. Correlation analysis
For numeric variables:
- book average rating
- book ratings count
- review count
- page count
- runtime
- IMDb votes
- IMDb rating
- opening weekend gross

### E. Missing data analysis
Show:
- which variables had missing values,
- how many records were removed,
- whether missingness clustered in older films or certain genres.

### F. Useful narrative questions for EDA
- Do more popular books become bigger openings?
- Do highly rated books become highly rated films?
- Are franchise-adjacent books different from standalone books?
- Are certain genres more commercially successful but less highly rated?

---

## 18. Modeling Plan

After cleaning and EDA, the project should model the two main outcomes.

### Model target 1: IMDb rating
Suggested models:
- Linear regression
- Ridge regression
- Lasso regression
- Random forest regression
- Gradient boosting / XGBoost if available

### Model target 2: Opening weekend gross
Suggested models:
- Linear regression on `log_opening_weekend_domestic`
- Ridge / Lasso
- Random forest regression
- Gradient boosting / XGBoost

### Why start with simple models?
Simple models:
- are easier to explain,
- create a baseline,
- and help show whether the problem is meaningfully predictable.

### Why include tree-based models?
Tree-based models may capture:
- non-linear relationships,
- threshold effects,
- and interactions between popularity, genre, and release context.

---

## 19. Evaluation Metrics

For both targets, use:
- **RMSE**
- **MAE**
- **R²**

### Recommended split
- Train/test split, such as 80/20
- Or cross-validation if time allows

### For box office
Because the distribution is skewed, the model should likely be trained on the logged response.  
Interpret results carefully and note that log-scale modeling improves stability.

---

## 20. What Claude Should Help With

Claude can be used heavily for:
- compiling a candidate list of 200 adaptations,
- documenting inclusion and exclusion decisions,
- standardizing titles,
- mapping genres into buckets,
- helping write cleaning scripts,
- generating summaries of missing data,
- drafting EDA insights,
- and helping explain plots and variable construction.

### Claude should not be trusted blindly for:
- uncertain book-to-movie matches,
- duplicate resolution without explicit rules,
- or filling in missing values without documentation.

The best workflow is:
1. Claude compiles and structures
2. You spot-check
3. Claude cleans and summarizes
4. You review ambiguous cases

---

## 21. Recommended Dataset Construction Workflow for Claude

### Phase 1: Candidate collection
Ask Claude to compile a long list of adaptations from 2000–2024.

### Phase 2: Filtering
Apply:
- feature film only
- clear source book only
- has IMDb and opening weekend data
- has accessible book metadata

### Phase 3: Sampling
Select 200 titles using:
- broad year coverage,
- broad genre coverage,
- varied popularity levels,
- and clear matches.

### Phase 4: Cleaning
Have Claude:
- standardize titles,
- standardize author names,
- map genres,
- create derived variables,
- document missingness,
- and output a clean CSV-ready table.

### Phase 5: EDA
Have Claude:
- suggest plots,
- describe preliminary patterns,
- identify skewness,
- recommend transformations,
- and summarize differences by genre and time period.

---

## 22. Suggested Research Hypotheses

You may want to include one or more hypotheses in the report.

### Hypothesis 1
Books with higher reader ratings tend to produce movies with higher IMDb ratings.

### Hypothesis 2
Book popularity, measured by ratings count or reviews count, is more strongly related to opening weekend box office than to IMDb rating.

### Hypothesis 3
Genre plays a meaningful role in both commercial and rating outcomes.

### Hypothesis 4
The adaptation gap between book publication and movie release may influence success, possibly reflecting whether the source material was a fresh trend or an established classic.

---

## 23. Possible Limitations

This section will strengthen the report.

### Key limitations
- Matching books to movies may involve some manual judgment
- Goodreads-style ratings are not perfect measures of literary quality
- Opening weekend depends on marketing and distribution, not just source material
- Some film success drivers are not observed, such as cast power or advertising budget
- Genre labels can be inconsistent across sources
- The final sample may not represent all adaptations equally

These are normal limitations and should be stated clearly.

---

## 24. Suggested Report Structure

### 1. Introduction
State:
- why book-to-movie adaptations are interesting,
- why predicting success matters,
- and the study goals.

### 2. Dataset
Describe:
- sources used,
- inclusion and exclusion criteria,
- sample construction,
- variables collected,
- and cleaning procedures.

### 3. Exploratory Data Analysis
Include:
- summary statistics,
- plots,
- missingness,
- and preliminary relationships.

### 4. Methods
Explain:
- targets,
- transformations,
- train/test split,
- models used,
- and evaluation metrics.

### 5. Results
Compare models and identify the most important predictors.

### 6. Conclusion
Summarize findings and discuss limitations and future work.

---

## 25. Final Recommendation

The best version of this project is a **clean, thoughtfully sampled dataset of 200 adaptations** from **2000–2024** that is:

- modern,
- diverse in genre,
- varied in popularity,
- and carefully matched across sources.

The sampling should be **semi-balanced rather than perfectly balanced**:
- broad enough to support meaningful comparisons,
- but realistic enough to reflect the actual adaptation market.

That design gives the project the strongest balance of:
- statistical usefulness,
- practical feasibility,
- interpretability,
- and quality of final report writing.

---

## 26. One-Sentence Summary for the Assignment

> This project investigates whether features of books and their adaptation context can be used to predict the IMDb rating and opening weekend box office of movie adaptations released between 2000 and 2024, using a cleaned and genre-diverse dataset of 200 book-to-film adaptations.

---