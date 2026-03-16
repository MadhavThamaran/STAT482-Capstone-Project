"""
eda_charts.py — Generate all EDA charts for the book-to-movie adaptation dataset.
Run from the project root: python scripts/eda_charts.py
"""

import os, pandas as pd
import numpy as np
import matplotlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA  = os.path.join(ROOT, "data", "final", "book_movie_adaptations_final_200.csv")
OUTDIR = os.path.join(ROOT, "charts", "eda")
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.gridspec import GridSpec
import warnings
warnings.filterwarnings("ignore")

df = pd.read_csv(DATA, encoding="utf-8-sig")

PALETTE = [
    "#2E4057", "#048A81", "#54C6EB", "#EF8354", "#D4A5A5",
    "#8338EC", "#FB5607", "#3A86FF", "#FFBE0B", "#06D6A0",
]
plt.rcParams.update({
    "figure.dpi": 150,
    "font.family": "sans-serif",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.titlesize": 13,
    "axes.labelsize": 11,
})


# ── 1. GENRE DISTRIBUTION ────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(9, 5))
counts = df["genre_bucket"].value_counts().sort_values()
colors = PALETTE[:len(counts)]
bars = ax.barh(counts.index, counts.values, color=colors[::-1], edgecolor="white", height=0.65)
for bar, val in zip(bars, counts.values):
    ax.text(val + 0.4, bar.get_y() + bar.get_height() / 2,
            str(val), va="center", ha="left", fontsize=10)
ax.set_xlabel("Number of Films")
ax.set_title("Genre Distribution of 200 Book-to-Movie Adaptations")
ax.set_xlim(0, counts.max() + 8)
plt.tight_layout()
plt.savefig(os.path.join(OUTDIR, "eda_01_genre_distribution.png"))
plt.close()
print("Saved eda_01_genre_distribution.png")


# ── 2. MOVIE RELEASE YEAR DISTRIBUTION ───────────────────────────────────────
fig, ax = plt.subplots(figsize=(9, 4))
bins = range(2000, 2026)
ax.hist(df["movie_release_year"], bins=bins, color=PALETTE[0], edgecolor="white", rwidth=0.85)
ax.set_xlabel("Release Year")
ax.set_ylabel("Number of Films")
ax.set_title("Movie Release Year Distribution (2000–2024)")
ax.xaxis.set_major_locator(mticker.MultipleLocator(2))
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig(os.path.join(OUTDIR, "eda_02_movie_release_year.png"))
plt.close()
print("Saved eda_02_movie_release_year.png")


# ── 3. BOOK PUBLICATION YEAR DISTRIBUTION ────────────────────────────────────
fig, ax = plt.subplots(figsize=(9, 4))
decades = (df["book_publication_year"] // 10) * 10
decade_counts = decades.value_counts().sort_index()
ax.bar(decade_counts.index.astype(str), decade_counts.values, color=PALETTE[1], edgecolor="white", width=0.7)
for i, (x, v) in enumerate(zip(decade_counts.index, decade_counts.values)):
    ax.text(i, v + 0.3, str(v), ha="center", va="bottom", fontsize=9)
ax.set_xlabel("Decade of Publication")
ax.set_ylabel("Number of Books")
ax.set_title("Source Book Publication Decade")
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig(os.path.join(OUTDIR, "eda_03_book_publication_decade.png"))
plt.close()
print("Saved eda_03_book_publication_decade.png")


# ── 4. IMDB RATING DISTRIBUTION ──────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(8, 4))
ax.hist(df["imdb_rating"].dropna(), bins=18, color=PALETTE[2], edgecolor="white")
ax.axvline(df["imdb_rating"].mean(), color=PALETTE[3], linestyle="--", linewidth=1.8,
           label=f'Mean = {df["imdb_rating"].mean():.2f}')
ax.axvline(df["imdb_rating"].median(), color=PALETTE[4], linestyle=":", linewidth=1.8,
           label=f'Median = {df["imdb_rating"].median():.2f}')
ax.set_xlabel("IMDb Rating")
ax.set_ylabel("Count")
ax.set_title("Distribution of IMDb Ratings")
ax.legend()
plt.tight_layout()
plt.savefig(os.path.join(OUTDIR, "eda_04_imdb_rating_dist.png"))
plt.close()
print("Saved eda_04_imdb_rating_dist.png")


# ── 5. BOOK AVG RATING DISTRIBUTION ─────────────────────────────────────────
fig, ax = plt.subplots(figsize=(8, 4))
ax.hist(df["book_avg_rating"].dropna(), bins=16, color=PALETTE[5], edgecolor="white")
ax.axvline(df["book_avg_rating"].mean(), color=PALETTE[3], linestyle="--", linewidth=1.8,
           label=f'Mean = {df["book_avg_rating"].mean():.2f}')
ax.set_xlabel("Goodreads Average Rating")
ax.set_ylabel("Count")
ax.set_title("Distribution of Goodreads Book Ratings")
ax.legend()
plt.tight_layout()
plt.savefig(os.path.join(OUTDIR, "eda_05_book_rating_dist.png"))
plt.close()
print("Saved eda_05_book_rating_dist.png")


# ── 6. SCATTER: BOOK RATING vs IMDB RATING ──────────────────────────────────
fig, ax = plt.subplots(figsize=(7, 6))
sub = df.dropna(subset=["book_avg_rating", "imdb_rating"])
genres = sub["genre_bucket"].unique()
cmap = {g: PALETTE[i % len(PALETTE)] for i, g in enumerate(genres)}
for genre, grp in sub.groupby("genre_bucket"):
    ax.scatter(grp["book_avg_rating"], grp["imdb_rating"],
               label=genre, color=cmap[genre], alpha=0.75, s=50, edgecolors="white", linewidths=0.4)
# Correlation
corr = sub["book_avg_rating"].corr(sub["imdb_rating"])
ax.set_xlabel("Goodreads Avg Rating")
ax.set_ylabel("IMDb Rating")
ax.set_title(f"Book Rating vs. IMDb Rating  (r = {corr:.2f})")
ax.legend(fontsize=7, loc="upper left", framealpha=0.6)
plt.tight_layout()
plt.savefig(os.path.join(OUTDIR, "eda_06_rating_scatter.png"))
plt.close()
print("Saved eda_06_rating_scatter.png")


# ── 7. IMDB RATING BY GENRE (box plot) ───────────────────────────────────────
fig, ax = plt.subplots(figsize=(10, 5))
genre_order = df.groupby("genre_bucket")["imdb_rating"].median().sort_values(ascending=False).index
data_by_genre = [df[df["genre_bucket"] == g]["imdb_rating"].dropna().values for g in genre_order]
bp = ax.boxplot(data_by_genre, patch_artist=True, widths=0.55,
                medianprops=dict(color="white", linewidth=2))
for patch, color in zip(bp["boxes"], PALETTE):
    patch.set_facecolor(color)
ax.set_xticks(range(1, len(genre_order) + 1))
ax.set_xticklabels([g.replace("_", "\n") for g in genre_order], fontsize=8)
ax.set_ylabel("IMDb Rating")
ax.set_title("IMDb Rating by Genre")
plt.tight_layout()
plt.savefig(os.path.join(OUTDIR, "eda_07_imdb_by_genre.png"))
plt.close()
print("Saved eda_07_imdb_by_genre.png")


# ── 8. MPAA RATING DISTRIBUTION ──────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(7, 4))
mpaa_order = ["G", "PG", "PG-13", "R", "NR"]
mpaa_counts = df["mpaa_rating"].value_counts().reindex(mpaa_order).dropna()
bars = ax.bar(mpaa_counts.index, mpaa_counts.values, color=PALETTE[:len(mpaa_counts)], edgecolor="white", width=0.6)
for bar, val in zip(bars, mpaa_counts.values):
    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
            str(int(val)), ha="center", va="bottom", fontsize=10)
ax.set_xlabel("MPAA Rating")
ax.set_ylabel("Number of Films")
ax.set_title("MPAA Rating Distribution (167 rated films)")
plt.tight_layout()
plt.savefig(os.path.join(OUTDIR, "eda_08_mpaa_rating.png"))
plt.close()
print("Saved eda_08_mpaa_rating.png")


# ── 9. RELEASE MONTH (SEASONALITY) ───────────────────────────────────────────
fig, ax = plt.subplots(figsize=(9, 4))
month_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
month_counts = df["movie_release_month"].value_counts().sort_index()
ax.bar([month_names[int(m)-1] for m in month_counts.index], month_counts.values,
       color=PALETTE[1], edgecolor="white", width=0.7)
for i, (m, v) in enumerate(month_counts.items()):
    ax.text(i, v + 0.3, str(v), ha="center", va="bottom", fontsize=9)
ax.set_xlabel("Release Month")
ax.set_ylabel("Number of Films")
ax.set_title("Film Release Month Distribution (Seasonality)")
plt.tight_layout()
plt.savefig(os.path.join(OUTDIR, "eda_09_release_month.png"))
plt.close()
print("Saved eda_09_release_month.png")


# ── 10. RUNTIME DISTRIBUTION ─────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(8, 4))
ax.hist(df["runtime_minutes"].dropna(), bins=20, color=PALETTE[6], edgecolor="white")
ax.axvline(df["runtime_minutes"].mean(), color=PALETTE[0], linestyle="--", linewidth=1.8,
           label=f'Mean = {df["runtime_minutes"].mean():.0f} min')
ax.set_xlabel("Runtime (minutes)")
ax.set_ylabel("Count")
ax.set_title("Distribution of Film Runtimes")
ax.legend()
plt.tight_layout()
plt.savefig(os.path.join(OUTDIR, "eda_10_runtime_dist.png"))
plt.close()
print("Saved eda_10_runtime_dist.png")


# ── 11. TOP DISTRIBUTORS ─────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(9, 5))
dist_counts = df["distributor"].dropna().value_counts().head(12)
bars = ax.barh(dist_counts.index[::-1], dist_counts.values[::-1],
               color=PALETTE[7], edgecolor="white", height=0.65)
for bar, val in zip(bars, dist_counts.values[::-1]):
    ax.text(val + 0.1, bar.get_y() + bar.get_height() / 2,
            str(val), va="center", ha="left", fontsize=10)
ax.set_xlabel("Number of Films")
ax.set_title("Top 12 Film Distributors")
ax.set_xlim(0, dist_counts.max() + 5)
plt.tight_layout()
plt.savefig(os.path.join(OUTDIR, "eda_11_top_distributors.png"))
plt.close()
print("Saved eda_11_top_distributors.png")


# ── 12. MISSING VALUE SUMMARY ─────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(9, 5))
fillable = ["book_avg_rating","book_ratings_count","book_reviews_count",
            "book_page_count","book_series_indicator","book_description",
            "movie_release_month","runtime_minutes","mpaa_rating",
            "distributor","movie_genre_raw","imdb_vote_count","imdb_rating"]
missing_pct = df[fillable].isnull().mean() * 100
missing_pct = missing_pct.sort_values(ascending=True)
colors_mv = [PALETTE[3] if v > 20 else PALETTE[1] for v in missing_pct.values]
bars = ax.barh(missing_pct.index, missing_pct.values, color=colors_mv, edgecolor="white", height=0.65)
for bar, val in zip(bars, missing_pct.values):
    ax.text(val + 0.3, bar.get_y() + bar.get_height() / 2,
            f"{val:.1f}%", va="center", ha="left", fontsize=9)
ax.set_xlabel("Missing (%)")
ax.set_title("Missing Value Rate by Field")
ax.set_xlim(0, missing_pct.max() + 10)
plt.tight_layout()
plt.savefig(os.path.join(OUTDIR, "eda_12_missing_values.png"))
plt.close()
print("Saved eda_12_missing_values.png")


# ── 13. BOOK PAGE COUNT DISTRIBUTION ─────────────────────────────────────────
fig, ax = plt.subplots(figsize=(8, 4))
ax.hist(df["book_page_count"].dropna(), bins=20, color=PALETTE[8], edgecolor="white")
ax.axvline(df["book_page_count"].median(), color=PALETTE[3], linestyle="--", linewidth=1.8,
           label=f'Median = {df["book_page_count"].median():.0f} pages')
ax.set_xlabel("Page Count")
ax.set_ylabel("Count")
ax.set_title("Distribution of Source Book Page Counts")
ax.legend()
plt.tight_layout()
plt.savefig(os.path.join(OUTDIR, "eda_13_book_page_count.png"))
plt.close()
print("Saved eda_13_book_page_count.png")


# ── 14. IMDB VOTE COUNT (log scale) ──────────────────────────────────────────
fig, ax = plt.subplots(figsize=(8, 4))
votes = df["imdb_vote_count"].dropna()
ax.hist(np.log10(votes + 1), bins=20, color=PALETTE[9], edgecolor="white")
ax.set_xlabel("log₁₀(IMDb Vote Count)")
ax.set_ylabel("Count")
ax.set_title("Distribution of IMDb Vote Counts (log scale)")
xticks = [3, 4, 5, 6, 7]
ax.set_xticks(xticks)
ax.set_xticklabels([f"10^{x}" for x in xticks])
plt.tight_layout()
plt.savefig(os.path.join(OUTDIR, "eda_14_imdb_votes_log.png"))
plt.close()
print("Saved eda_14_imdb_votes_log.png")

print("\nAll 14 charts saved.")
