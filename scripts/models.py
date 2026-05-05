"""
models.py — OLS regression models for Report 2

Models:
  M1: imdb_rating    ~ runtime + mpaa + genre + summer + holiday + decade
  M2: log_gross      ~ runtime + mpaa + genre + summer + holiday + decade

Run from project root:
  python scripts/models.py
"""

import pandas as pd
import numpy as np
import statsmodels.formula.api as smf
import warnings
import sys
import os

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8")

os.makedirs("results", exist_ok=True)

# ── Load and prepare data ─────────────────────────────────────────────────────

df = pd.read_csv("data/interim/top_500_enriched.csv", encoding="utf-8-sig")
df["log_gross"] = np.log(df["Domestic Gross"])
df["primary_genre"] = df["movie_genre_raw"].str.split(",").str[0]
df["decade"] = (df["Year"] // 10) * 10

# Collapse genres with fewer than 10 films into "Other"
top_genres = df["primary_genre"].value_counts()
top_genres = top_genres[top_genres >= 10].index.tolist()
df["genre"] = df["primary_genre"].where(df["primary_genre"].isin(top_genres), "Other")

# Keep only standard MPAA ratings
df["mpaa"] = df["mpaa_rating"].where(df["mpaa_rating"].isin(["G", "PG", "PG-13", "R"]), np.nan)

# Release window flags
df["summer"]  = df["movie_release_month"].isin([5, 6, 7]).astype(float)
df["holiday"] = df["movie_release_month"].isin([11, 12]).astype(float)

# Drop rows missing any model variable
model_df = df.dropna(subset=["imdb_rating", "log_gross", "runtime_minutes", "mpaa", "genre", "summer", "holiday"]).copy()
print(f"Model sample: {len(model_df)} / 500 films\n")

# ── Model formulas ────────────────────────────────────────────────────────────

FORMULA_BASE = (
    '~ runtime_minutes'
    ' + C(mpaa, Treatment("PG-13"))'
    ' + C(genre, Treatment("Action"))'
    ' + summer + holiday + decade'
)

formula_m1 = "imdb_rating" + FORMULA_BASE
formula_m2 = "log_gross"   + FORMULA_BASE

# ── Fit models ────────────────────────────────────────────────────────────────

m1 = smf.ols(formula_m1, data=model_df).fit()
m2 = smf.ols(formula_m2, data=model_df).fit()

# ── Pretty-print results ──────────────────────────────────────────────────────

def print_model(model, name, outcome_label):
    print("=" * 70)
    print(f"  {name}: {outcome_label}")
    print("=" * 70)
    tbl = model.summary2().tables[1].copy()
    tbl.columns = ["Coeff", "SE", "t", "P>|t|", "CI_low", "CI_high"]
    # Simplify index labels
    tbl.index = (
        tbl.index
        .str.replace(r'C\(mpaa, Treatment\("PG-13"\)\)\[T\.', "MPAA: ", regex=True)
        .str.replace(r'C\(genre, Treatment\("Action"\)\)\[T\.', "Genre: ", regex=True)
        .str.replace(r'\]', "", regex=True)
    )
    # Significance stars
    def stars(p):
        if p < 0.001: return "***"
        if p < 0.01:  return "**"
        if p < 0.05:  return "*"
        if p < 0.10:  return "."
        return ""
    tbl["sig"] = tbl["P>|t|"].apply(stars)

    print(f"{'Predictor':<40} {'Coeff':>8} {'SE':>7} {'t':>7} {'p':>8}  {'':4}")
    print("-" * 70)
    for idx, row in tbl.iterrows():
        print(f"{idx:<40} {row['Coeff']:>8.4f} {row['SE']:>7.4f} {row['t']:>7.3f} {row['P>|t|']:>8.4f}  {row['sig']}")

    print("-" * 70)
    print(f"  R²={model.rsquared:.3f}  Adj R²={model.rsquared_adj:.3f}  "
          f"F({int(model.df_model)},{int(model.df_resid)})={model.fvalue:.2f}  "
          f"p={model.f_pvalue:.4f}  n={int(model.nobs)}")
    print()
    print("Significance: *** p<0.001  ** p<0.01  * p<0.05  . p<0.10\n")

print_model(m1, "Model 1", "IMDb Rating")
print_model(m2, "Model 2", "log(Domestic Gross)")

# ── Save results to CSV ───────────────────────────────────────────────────────

def save_results(model, path):
    tbl = model.summary2().tables[1].copy()
    tbl.columns = ["coeff", "se", "t", "p_value", "ci_low", "ci_high"]
    tbl.index.name = "predictor"
    tbl["r_squared"]     = model.rsquared
    tbl["adj_r_squared"] = model.rsquared_adj
    tbl["f_stat"]        = model.fvalue
    tbl["f_pvalue"]      = model.f_pvalue
    tbl["n"]             = int(model.nobs)
    tbl.to_csv(path)
    print(f"Saved: {path}")

save_results(m1, "results/model1_imdb.csv")
save_results(m2, "results/model2_loggross.csv")

# ── Model comparison summary ──────────────────────────────────────────────────

print("\n" + "=" * 70)
print("  Model Comparison Summary")
print("=" * 70)
print(f"{'Model':<30} {'R²':>6} {'Adj R²':>8} {'F':>8} {'p':>10} {'n':>5}")
print("-" * 70)
for m, label in [(m1, "M1: IMDb Rating"), (m2, "M2: log(Domestic Gross)")]:
    print(f"{label:<30} {m.rsquared:>6.3f} {m.rsquared_adj:>8.3f} "
          f"{m.fvalue:>8.2f} {m.f_pvalue:>10.4f} {int(m.nobs):>5}")
print()
