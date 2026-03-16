import pandas as pd
import re
import requests
import io
from urllib.parse import unquote

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

URLS = [
    "https://en.wikipedia.org/wiki/List_of_fiction_works_made_into_feature_films_(0%E2%80%939,_A%E2%80%93C)",
    "https://en.wikipedia.org/wiki/List_of_fiction_works_made_into_feature_films_(D%E2%80%93J)",
    "https://en.wikipedia.org/wiki/List_of_fiction_works_made_into_feature_films_(K%E2%80%93R)",
    "https://en.wikipedia.org/wiki/List_of_fiction_works_made_into_feature_films_(S%E2%80%93Z)",
]

RAW_OUT = "fiction_to_feature_films_raw.csv"
LONG_OUT = "fiction_to_feature_films_long.csv"


def clean_text(x):
    if pd.isna(x):
        return None
    x = str(x)
    x = x.replace("\xa0", " ")
    x = re.sub(r"\[\s*N\s*\d+\s*\]", "", x)   # remove note markers like [ N 1 ]
    x = re.sub(r"\[\d+\]", "", x)             # remove citation markers if any
    x = re.sub(r"\s+", " ", x).strip()
    return x


def normalize_colname(col):
    if isinstance(col, tuple):
        col = " ".join([str(c) for c in col if str(c) != "nan"])
    col = str(col)
    col = re.sub(r"\s+", " ", col).strip().lower()
    return col


def get_page_label(url):
    slug = url.split("/wiki/")[-1]
    slug = unquote(slug)
    return slug


def extract_years(text):
    """
    Returns all 4-digit years found in a string.
    """
    if not text:
        return []
    years = re.findall(r"(?<!\d)(1[5-9]\d{2}|20\d{2}|21\d{2})(?!\d)", text)
    return [int(y) for y in years]


def split_adaptation_lines(text):
    """
    Wikipedia cells often contain multiple film adaptations separated by line breaks.
    pandas.read_html usually preserves them with '\n'.
    """
    if text is None:
        return []

    parts = re.split(r"\n+", str(text))
    parts = [clean_text(p) for p in parts]
    parts = [p for p in parts if p and p.lower() not in {"nan", "none"}]
    return parts


def parse_book_side(text):
    """
    Heuristic parser for the fiction-work side.
    Keeps raw text, and tries to pull out a publication year.
    Do not over-trust this parser; keep raw fields.
    """
    text = clean_text(text)
    years = extract_years(text)
    publication_year = years[0] if years else None
    return {
        "fiction_work_raw": text,
        "book_publication_year_guess": publication_year,
    }


def parse_film_side(text):
    """
    Heuristic parser for one adaptation line.
    Keeps raw text, and tries to pull out the film year.
    """
    text = clean_text(text)
    years = extract_years(text)
    film_year = years[-1] if years else None
    return {
        "film_adaptation_raw": text,
        "film_release_year_guess": film_year,
    }


def is_adaptation_table(df):
    cols = [normalize_colname(c) for c in df.columns]

    fiction_like = any("fiction work" in c for c in cols)
    film_like = any("film adaptation" in c for c in cols)

    if fiction_like and film_like:
        return True

    # fallback for slightly messy headers
    if len(cols) >= 2:
        joined = " | ".join(cols)
        if "fiction" in joined and "film" in joined:
            return True

    return False


def standardize_table(df, page_url, table_index):
    original_cols = list(df.columns)
    norm_cols = [normalize_colname(c) for c in original_cols]
    col_map = dict(zip(original_cols, norm_cols))
    df = df.rename(columns=col_map).copy()

    fiction_col = None
    film_col = None

    for c in df.columns:
        if "fiction work" in c and fiction_col is None:
            fiction_col = c
        if "film adaptation" in c and film_col is None:
            film_col = c

    # fallback: use first two columns
    if fiction_col is None or film_col is None:
        if len(df.columns) >= 2:
            fiction_col = df.columns[0]
            film_col = df.columns[1]
        else:
            return None

    out = df[[fiction_col, film_col]].copy()
    out.columns = ["fiction_work_raw", "film_adaptations_raw"]

    out["fiction_work_raw"] = out["fiction_work_raw"].map(clean_text)
    out["film_adaptations_raw"] = out["film_adaptations_raw"].map(clean_text)

    out = out[
        out["fiction_work_raw"].notna() &
        out["film_adaptations_raw"].notna()
    ].copy()

    out["source_page_url"] = page_url
    out["source_page_label"] = get_page_label(page_url)
    out["source_table_index"] = table_index
    return out


def scrape_pages(urls):
    raw_tables = []

    for url in urls:
        print(f"Reading tables from: {url}")
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        tables = pd.read_html(io.StringIO(resp.text))

        for i, df in enumerate(tables):
            if is_adaptation_table(df):
                std = standardize_table(df, url, i)
                if std is not None and not std.empty:
                    raw_tables.append(std)

    if not raw_tables:
        raise RuntimeError("No adaptation tables found. Wikipedia layout may have changed.")

    raw_df = pd.concat(raw_tables, ignore_index=True)
    raw_df = raw_df.drop_duplicates().reset_index(drop=True)
    return raw_df


def build_long_format(raw_df):
    rows = []

    for _, row in raw_df.iterrows():
        fiction_raw = row["fiction_work_raw"]
        film_raw_block = row["film_adaptations_raw"]

        fiction_info = parse_book_side(fiction_raw)
        film_lines = split_adaptation_lines(film_raw_block)

        if not film_lines:
            film_lines = [film_raw_block]

        for idx, film_line in enumerate(film_lines, start=1):
            film_info = parse_film_side(film_line)

            rows.append({
                "source_page_url": row["source_page_url"],
                "source_page_label": row["source_page_label"],
                "source_table_index": row["source_table_index"],
                "fiction_work_raw": fiction_info["fiction_work_raw"],
                "book_publication_year_guess": fiction_info["book_publication_year_guess"],
                "film_adaptation_raw": film_info["film_adaptation_raw"],
                "film_release_year_guess": film_info["film_release_year_guess"],
                "adaptation_line_number": idx,
            })

    long_df = pd.DataFrame(rows)

    # basic cleanup
    long_df["book_publication_year_guess"] = pd.to_numeric(
        long_df["book_publication_year_guess"], errors="coerce"
    )
    long_df["film_release_year_guess"] = pd.to_numeric(
        long_df["film_release_year_guess"], errors="coerce"
    )

    # helpful filter column for your project
    long_df["is_movie_2000_2024_guess"] = long_df["film_release_year_guess"].between(2000, 2024, inclusive="both")

    return long_df


if __name__ == "__main__":
    raw_df = scrape_pages(URLS)
    raw_df.to_csv(RAW_OUT, index=False, encoding="utf-8-sig")
    print(f"Wrote raw table scrape to {RAW_OUT} with {len(raw_df)} rows")

    long_df = build_long_format(raw_df)
    long_df.to_csv(LONG_OUT, index=False, encoding="utf-8-sig")
    print(f"Wrote long-format adaptation file to {LONG_OUT} with {len(long_df)} rows")

    # optional: quick filtered file for your project window
    movies_2000_2024 = long_df[long_df["is_movie_2000_2024_guess"]].copy()
    movies_2000_2024.to_csv("fiction_to_feature_films_2000_2024_guess.csv", index=False, encoding="utf-8-sig")
    print(f"Wrote filtered project-window file with {len(movies_2000_2024)} rows")