"""
eda_top500.py — EDA for top_500_enriched.csv
Outputs charts to charts/eda/
"""
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
import os, sys

sys.stdout.reconfigure(encoding='utf-8')

os.makedirs("charts/eda", exist_ok=True)
sns.set_theme(style="whitegrid", palette="muted", font_scale=1.1)
BLUE, ORANGE = "#4C72B0", "#DD8452"

df = pd.read_csv("data/interim/top_500_enriched.csv", encoding='utf-8-sig')
df['log_gross'] = np.log(df['Domestic Gross'])
df['primary_genre'] = df['movie_genre_raw'].str.split(',').str[0]
df['decade'] = (df['Year'] // 10) * 10
df['is_book_label'] = df['is_book'].map({1: 'Book Adaptation', 0: 'Original / Other'})

# ── 1. Distribution of IMDb Rating ───────────────────────────────────────────
fig, ax = plt.subplots(figsize=(8, 4))
ax.hist(df['imdb_rating'].dropna(), bins=30, color=BLUE, edgecolor='white')
ax.axvline(df['imdb_rating'].mean(), color='red', linestyle='--', label=f"Mean = {df['imdb_rating'].mean():.2f}")
ax.set_xlabel("IMDb Rating")
ax.set_ylabel("Count")
ax.set_title("Distribution of IMDb Rating (Top 500 Films)")
ax.legend()
fig.tight_layout()
fig.savefig("charts/eda/fig1_imdb_rating_dist.png", dpi=150)
plt.close()
print("Saved fig1")

# ── 2. Distribution of log(Domestic Gross) ───────────────────────────────────
fig, ax = plt.subplots(figsize=(8, 4))
ax.hist(df['log_gross'], bins=30, color=ORANGE, edgecolor='white')
ax.axvline(df['log_gross'].mean(), color='red', linestyle='--', label=f"Mean = {df['log_gross'].mean():.2f}")
ax.set_xlabel("log(Domestic Gross)")
ax.set_ylabel("Count")
ax.set_title("Distribution of log(Domestic Gross)")
ax.legend()
fig.tight_layout()
fig.savefig("charts/eda/fig2_log_gross_dist.png", dpi=150)
plt.close()
print("Saved fig2")

# ── 3. Book vs Non-Book: IMDb Rating ─────────────────────────────────────────
fig, ax = plt.subplots(figsize=(7, 4))
for label, color in [('Book Adaptation', BLUE), ('Original / Other', ORANGE)]:
    vals = df[df['is_book_label'] == label]['imdb_rating'].dropna()
    ax.hist(vals, bins=25, alpha=0.6, label=label, color=color, edgecolor='white')
ax.set_xlabel("IMDb Rating")
ax.set_ylabel("Count")
ax.set_title("IMDb Rating: Book Adaptations vs. Other Films")
ax.legend()
fig.tight_layout()
fig.savefig("charts/eda/fig3_imdb_book_vs_other.png", dpi=150)
plt.close()
print("Saved fig3")

# ── 4. Book vs Non-Book: log(Gross) boxplot ───────────────────────────────────
fig, ax = plt.subplots(figsize=(6, 4))
data = [df[df['is_book']==1]['log_gross'].dropna(),
        df[df['is_book']==0]['log_gross'].dropna()]
bp = ax.boxplot(data, labels=['Book\nAdaptation', 'Original /\nOther'],
                patch_artist=True, widths=0.5)
for patch, color in zip(bp['boxes'], [BLUE, ORANGE]):
    patch.set_facecolor(color)
    patch.set_alpha(0.7)
ax.set_ylabel("log(Domestic Gross)")
ax.set_title("Box Office: Book Adaptations vs. Other Films")
fig.tight_layout()
fig.savefig("charts/eda/fig4_gross_boxplot.png", dpi=150)
plt.close()
print("Saved fig4")

# ── 5. IMDb Rating vs log(Gross) scatter ─────────────────────────────────────
fig, ax = plt.subplots(figsize=(7, 5))
colors = df['is_book'].map({1: BLUE, 0: ORANGE})
ax.scatter(df['imdb_rating'], df['log_gross'], c=colors, alpha=0.4, s=20)
from matplotlib.patches import Patch
legend_els = [Patch(facecolor=BLUE, label='Book Adaptation'),
              Patch(facecolor=ORANGE, label='Other')]
ax.legend(handles=legend_els)
ax.set_xlabel("IMDb Rating")
ax.set_ylabel("log(Domestic Gross)")
ax.set_title("IMDb Rating vs. log(Gross)")
fig.tight_layout()
fig.savefig("charts/eda/fig5_imdb_vs_gross.png", dpi=150)
plt.close()
print("Saved fig5")

# ── 6. Mean IMDb Rating by Primary Genre ─────────────────────────────────────
genre_counts = df['primary_genre'].value_counts()
top_genres = genre_counts[genre_counts >= 5].index
genre_df = df[df['primary_genre'].isin(top_genres)].groupby('primary_genre')['imdb_rating'].mean().sort_values()
fig, ax = plt.subplots(figsize=(8, 5))
genre_df.plot(kind='barh', ax=ax, color=BLUE)
ax.set_xlabel("Mean IMDb Rating")
ax.set_title("Mean IMDb Rating by Primary Genre")
ax.axvline(df['imdb_rating'].mean(), color='red', linestyle='--', label='Overall Mean')
ax.legend()
fig.tight_layout()
fig.savefig("charts/eda/fig6_imdb_by_genre.png", dpi=150)
plt.close()
print("Saved fig6")

# ── 7. Mean log(Gross) by MPAA Rating ────────────────────────────────────────
mpaa_order = ['G', 'PG', 'PG-13', 'R']
mpaa_df = df[df['mpaa_rating'].isin(mpaa_order)].groupby('mpaa_rating').agg(
    mean_gross=('log_gross','mean'), count=('log_gross','size')
).reindex(mpaa_order)
fig, ax = plt.subplots(figsize=(6, 4))
bars = ax.bar(mpaa_df.index, mpaa_df['mean_gross'], color=[BLUE, BLUE, ORANGE, ORANGE])
ax.set_ylabel("Mean log(Domestic Gross)")
ax.set_title("Mean Box Office by MPAA Rating")
for i, (v, n) in enumerate(zip(mpaa_df['mean_gross'], mpaa_df['count'])):
    ax.text(i, v + 0.01, f"n={n}", ha='center', fontsize=9)
fig.tight_layout()
fig.savefig("charts/eda/fig7_gross_by_mpaa.png", dpi=150)
plt.close()
print("Saved fig7")

# ── 8. Film count and mean gross by release month ────────────────────────────
months = df.dropna(subset=['movie_release_month']).copy()
months['movie_release_month'] = months['movie_release_month'].astype(int)
month_stats = months.groupby('movie_release_month').agg(
    count=('log_gross','size'), mean_gross=('log_gross','mean'))
month_labels = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

fig, ax1 = plt.subplots(figsize=(9, 4))
ax2 = ax1.twinx()
ax1.bar(month_stats.index, month_stats['count'], color=BLUE, alpha=0.6, label='Film Count')
ax2.plot(month_stats.index, month_stats['mean_gross'], color='red', marker='o', label='Mean log(Gross)')
ax1.set_xticks(range(1,13))
ax1.set_xticklabels(month_labels)
ax1.set_ylabel("Number of Films", color=BLUE)
ax2.set_ylabel("Mean log(Domestic Gross)", color='red')
ax1.set_title("Film Releases and Box Office by Month")
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1+lines2, labels1+labels2, loc='upper left')
fig.tight_layout()
fig.savefig("charts/eda/fig8_month_gross.png", dpi=150)
plt.close()
print("Saved fig8")

# ── 9. Runtime vs IMDb Rating ─────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(7, 5))
ax.scatter(df['runtime_minutes'], df['imdb_rating'], alpha=0.3, s=20, color=BLUE)
m, b = np.polyfit(df[['runtime_minutes','imdb_rating']].dropna()['runtime_minutes'],
                  df[['runtime_minutes','imdb_rating']].dropna()['imdb_rating'], 1)
xs = np.linspace(df['runtime_minutes'].min(), df['runtime_minutes'].max(), 100)
ax.plot(xs, m*xs+b, color='red', linewidth=1.5, label=f'r = {df["runtime_minutes"].corr(df["imdb_rating"]):.2f}')
ax.set_xlabel("Runtime (minutes)")
ax.set_ylabel("IMDb Rating")
ax.set_title("Runtime vs. IMDb Rating")
ax.legend()
fig.tight_layout()
fig.savefig("charts/eda/fig9_runtime_vs_imdb.png", dpi=150)
plt.close()
print("Saved fig9")

# ── 10. Goodreads Rating vs IMDb Rating (book subset) ────────────────────────
bk = df[df['is_book']==1].dropna(subset=['book_avg_rating','imdb_rating'])
fig, ax = plt.subplots(figsize=(7, 5))
ax.scatter(bk['book_avg_rating'], bk['imdb_rating'], alpha=0.6, color=BLUE, s=40)
m, b = np.polyfit(bk['book_avg_rating'], bk['imdb_rating'], 1)
xs = np.linspace(bk['book_avg_rating'].min(), bk['book_avg_rating'].max(), 100)
ax.plot(xs, m*xs+b, color='red', linewidth=1.5,
        label=f'r = {bk["book_avg_rating"].corr(bk["imdb_rating"]):.2f}')
ax.set_xlabel("Goodreads Average Rating")
ax.set_ylabel("IMDb Rating")
ax.set_title("Goodreads Rating vs. IMDb Rating (Book Adaptations Only)")
ax.legend()
fig.tight_layout()
fig.savefig("charts/eda/fig10_goodreads_vs_imdb.png", dpi=150)
plt.close()
print("Saved fig10")

# ── 11. Correlation heatmap ───────────────────────────────────────────────────
heat_cols = ['imdb_rating','log_gross','runtime_minutes','is_book',
             'movie_release_month','book_avg_rating','book_ratings_count',
             'book_page_count','book_series_indicator']
corr = df[heat_cols].corr()
fig, ax = plt.subplots(figsize=(9, 7))
mask = np.triu(np.ones_like(corr, dtype=bool))
sns.heatmap(corr, mask=mask, annot=True, fmt='.2f', cmap='coolwarm',
            center=0, ax=ax, linewidths=0.5)
ax.set_title("Correlation Matrix of Key Variables")
fig.tight_layout()
fig.savefig("charts/eda/fig11_corr_heatmap.png", dpi=150)
plt.close()
print("Saved fig11")

# ── 12. Decade trends ────────────────────────────────────────────────────────
dec = df[df['decade'] >= 1980].groupby('decade')[['imdb_rating','log_gross']].mean()
fig, ax1 = plt.subplots(figsize=(8, 4))
ax2 = ax1.twinx()
ax1.plot(dec.index, dec['imdb_rating'], marker='o', color=BLUE, label='Mean IMDb Rating')
ax2.plot(dec.index, dec['log_gross'], marker='s', color=ORANGE, label='Mean log(Gross)')
ax1.set_ylabel("Mean IMDb Rating", color=BLUE)
ax2.set_ylabel("Mean log(Gross)", color=ORANGE)
ax1.set_xlabel("Decade")
ax1.set_title("IMDb Rating and Box Office Trends by Decade (1980+)")
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1+lines2, labels1+labels2, loc='upper right')
fig.tight_layout()
fig.savefig("charts/eda/fig12_decade_trends.png", dpi=150)
plt.close()
print("Saved fig12")

print("\nAll 12 charts saved to charts/eda/")
