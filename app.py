from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable

import pandas as pd
import plotly.express as px
import streamlit as st


REQUIRED_COLUMNS = {
    "title",
    "channel_title",
    "view_count",
    "Keyword",
}

OPTIONAL_COLUMNS = {
    "published_date",
    "thumbnail_url",
    "subscriber_count",
    "position",
    "rank",
    "ranking_position",
}

STOPWORDS = {
    "en", "ett", "och", "eller", "att", "för", "med", "utan", "som", "vad", "hur", "vilken", "vilka",
    "the", "a", "an", "and", "or", "to", "for", "with", "without", "which", "what", "how", "best",
}

TITLE_CATEGORY_RULES: list[tuple[str, list[str]]] = [
    ("Test / Review", [
        "test", "tested", "testing", "review", "recension", "recenserar", "testar", "provkör", "hands on",
    ]),
    ("Comparison", [
        " vs ", "versus", "compare", "comparison", "jämför", "jämförelse", "eller", "against", "bäst av",
    ]),
    ("Guide / Explainer", [
        "guide", "explained", "förklarar", "så fungerar", "how to", "så gör", "tips", "tutorial",
    ]),
    ("Cost / Ownership", [
        "price", "cost", "cheap", "budget", "pris", "kostnad", "billig", "billigast", "värde", "ägandekostnad",
    ]),
    ("List / Ranking", [
        "top ", "top-", "best", "bästa", "ranking", "ranked", "topp", "5 bästa", "10 bästa",
    ]),
    ("News / Update", [
        "new", "ny", "nyhet", "lansering", "launch", "update", "uppdatering", "2024", "2025", "2026",
    ]),
    ("Experience / Personal", [
        "my", "min", "mitt", "jag", "we tried", "vi testar", "erfarenhet", "så gick det", "living with",
    ]),
    ("Question-led", [
        "hur ", "vad ", "vilken ", "vilka ", "varför ", "kan ", "är ", "should ", "what ", "how ", "which ", "why ",
    ]),
]


@dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    missing_columns: list[str]
    sheet_name: str | None = None


def normalize_text(value: object) -> str:
    """Lowercase, remove accents/punctuation noise and collapse spaces."""
    if pd.isna(value):
        return ""
    text = str(value).casefold().strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-z0-9åäöæø\s]+", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize(value: object) -> list[str]:
    text = normalize_text(value)
    tokens = [token for token in text.split() if token and token not in STOPWORDS]
    return tokens


def keyword_match_type(title: object, keyword: object) -> str:
    title_norm = normalize_text(title)
    keyword_norm = normalize_text(keyword)

    if not title_norm or not keyword_norm:
        return "No clear match"

    if keyword_norm in title_norm:
        return "Exact keyword phrase"

    keyword_tokens = set(tokenize(keyword_norm))
    title_tokens = set(tokenize(title_norm))

    if not keyword_tokens:
        return "No clear match"

    overlap = len(keyword_tokens & title_tokens) / len(keyword_tokens)
    if overlap >= 0.6:
        return "Partial keyword match"

    return "No clear match"


def categorize_title(title: object) -> str:
    title_norm = f" {normalize_text(title)} "
    if not title_norm.strip():
        return "Uncategorized"

    for category, patterns in TITLE_CATEGORY_RULES:
        for pattern in patterns:
            if normalize_text(pattern) in title_norm:
                return category

    return "Other"


def find_serp_sheet(uploaded_file) -> tuple[pd.DataFrame, str]:
    workbook = pd.ExcelFile(uploaded_file)

    preferred_sheets = [sheet for sheet in workbook.sheet_names if sheet.casefold() == "serps"]
    candidate_sheets = preferred_sheets + [sheet for sheet in workbook.sheet_names if sheet not in preferred_sheets]

    for sheet in candidate_sheets:
        df = pd.read_excel(workbook, sheet_name=sheet)
        if REQUIRED_COLUMNS.issubset(set(df.columns)):
            return df, sheet

    # Fallback: return first sheet so validation can show useful missing-column errors.
    first_sheet = workbook.sheet_names[0]
    return pd.read_excel(workbook, sheet_name=first_sheet), first_sheet


def validate_input(df: pd.DataFrame, sheet_name: str) -> ValidationResult:
    missing = sorted(REQUIRED_COLUMNS - set(df.columns))
    return ValidationResult(is_valid=not missing, missing_columns=missing, sheet_name=sheet_name)


def prepare_data(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()

    data["title"] = data["title"].fillna("").astype(str)
    data["channel_title"] = data["channel_title"].fillna("Unknown channel").astype(str)
    data["Keyword"] = data["Keyword"].fillna("Unknown keyword").astype(str)
    data["view_count"] = pd.to_numeric(data["view_count"], errors="coerce").fillna(0).astype(int)

    if "subscriber_count" in data.columns:
        data["subscriber_count"] = pd.to_numeric(data["subscriber_count"], errors="coerce")

    if "published_date" in data.columns:
        data["published_date"] = pd.to_datetime(data["published_date"], errors="coerce")

    position_col = get_position_column(data.columns)
    if position_col:
        data[position_col] = pd.to_numeric(data[position_col], errors="coerce")

    data["keyword_match_type"] = data.apply(
        lambda row: keyword_match_type(row["title"], row["Keyword"]), axis=1
    )
    data["has_exact_keyword"] = data["keyword_match_type"].eq("Exact keyword phrase")
    data["has_any_keyword_match"] = data["keyword_match_type"].isin([
        "Exact keyword phrase",
        "Partial keyword match",
    ])
    data["title_category"] = data["title"].apply(categorize_title)

    return data


def get_position_column(columns: Iterable[str]) -> str | None:
    normalized = {str(col).casefold(): str(col) for col in columns}
    for candidate in ["position", "rank", "ranking_position"]:
        if candidate in normalized:
            return normalized[candidate]
    return None


def summarize_channels(data: pd.DataFrame) -> pd.DataFrame:
    aggregations = {
        "ranking_videos": ("title", "count"),
        "unique_keywords": ("Keyword", "nunique"),
        "total_views": ("view_count", "sum"),
        "avg_views": ("view_count", "mean"),
    }

    if "subscriber_count" in data.columns:
        aggregations["avg_subscribers"] = ("subscriber_count", "mean")

    position_col = get_position_column(data.columns)
    if position_col:
        aggregations["avg_position"] = (position_col, "mean")
        aggregations["top_3_rankings"] = (position_col, lambda x: int((x <= 3).sum()))
        aggregations["top_10_rankings"] = (position_col, lambda x: int((x <= 10).sum()))

    summary = (
        data.groupby("channel_title", dropna=False)
        .agg(**aggregations)
        .reset_index()
        .sort_values(["ranking_videos", "unique_keywords", "total_views"], ascending=False)
    )
    return summary


def summarize_keyword_views(data: pd.DataFrame) -> pd.DataFrame:
    return (
        data.groupby("Keyword", dropna=False)
        .agg(
            ranking_videos=("title", "count"),
            unique_channels=("channel_title", "nunique"),
            total_views=("view_count", "sum"),
            avg_views=("view_count", "mean"),
            median_views=("view_count", "median"),
            max_views=("view_count", "max"),
        )
        .reset_index()
        .sort_values("total_views", ascending=False)
    )


def summarize_keyword_inclusion(data: pd.DataFrame) -> pd.DataFrame:
    summary = (
        data.groupby("Keyword", dropna=False)
        .agg(
            videos_analyzed=("title", "count"),
            exact_keyword_titles=("has_exact_keyword", "sum"),
            any_keyword_match_titles=("has_any_keyword_match", "sum"),
        )
        .reset_index()
    )
    summary["exact_keyword_inclusion_pct"] = (
        summary["exact_keyword_titles"] / summary["videos_analyzed"] * 100
    ).round(1)
    summary["any_keyword_match_pct"] = (
        summary["any_keyword_match_titles"] / summary["videos_analyzed"] * 100
    ).round(1)
    return summary.sort_values("exact_keyword_inclusion_pct", ascending=False)


def summarize_title_categories(data: pd.DataFrame) -> pd.DataFrame:
    return (
        data.groupby(["Keyword", "title_category"], dropna=False)
        .agg(
            videos=("title", "count"),
            total_views=("view_count", "sum"),
            avg_views=("view_count", "mean"),
        )
        .reset_index()
        .sort_values(["Keyword", "videos", "total_views"], ascending=[True, False, False])
    )


def format_number_columns(df: pd.DataFrame) -> pd.DataFrame:
    formatted = df.copy()
    for col in formatted.columns:
        if pd.api.types.is_float_dtype(formatted[col]):
            formatted[col] = formatted[col].round(1)
    return formatted


def render_kpis(data: pd.DataFrame) -> None:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Keywords", f"{data['Keyword'].nunique():,}")
    col2.metric("Ranking videos", f"{len(data):,}")
    col3.metric("Unique channels", f"{data['channel_title'].nunique():,}")
    col4.metric("Total views", f"{int(data['view_count'].sum()):,}")


def render_top_channels_chart(channel_summary: pd.DataFrame, top_n: int) -> None:
    chart_data = channel_summary.head(top_n).sort_values("ranking_videos", ascending=True)
    fig = px.bar(
        chart_data,
        x="ranking_videos",
        y="channel_title",
        orientation="h",
        hover_data=["unique_keywords", "total_views", "avg_views"],
        labels={
            "channel_title": "Channel",
            "ranking_videos": "Ranking videos",
            "unique_keywords": "Unique keywords",
            "total_views": "Total views",
            "avg_views": "Average views",
        },
        title=f"Top {top_n} ranking YouTube accounts",
    )
    fig.update_layout(yaxis_title="", xaxis_title="Ranking videos", height=max(420, top_n * 28))
    st.plotly_chart(fig, use_container_width=True)


def render_views_by_keyword_chart(keyword_views: pd.DataFrame, top_n: int) -> None:
    chart_data = keyword_views.head(top_n).sort_values("total_views", ascending=True)
    fig = px.bar(
        chart_data,
        x="total_views",
        y="Keyword",
        orientation="h",
        hover_data=["ranking_videos", "unique_channels", "avg_views", "median_views"],
        labels={
            "Keyword": "Keyword",
            "total_views": "Total views",
            "ranking_videos": "Ranking videos",
            "unique_channels": "Unique channels",
            "avg_views": "Average views",
            "median_views": "Median views",
        },
        title=f"Top {top_n} keywords by summed views of ranking videos",
    )
    fig.update_layout(yaxis_title="", xaxis_title="Total views", height=max(420, top_n * 28))
    st.plotly_chart(fig, use_container_width=True)


def render_keyword_detail(data: pd.DataFrame) -> None:
    st.subheader("Keyword deep-dive")
    selected_keyword = st.selectbox("Select keyword", sorted(data["Keyword"].dropna().unique()))
    keyword_data = data[data["Keyword"] == selected_keyword].copy()

    col1, col2, col3 = st.columns(3)
    col1.metric("Videos", f"{len(keyword_data):,}")
    col2.metric("Channels", f"{keyword_data['channel_title'].nunique():,}")
    col3.metric("Exact keyword in title", f"{keyword_data['has_exact_keyword'].mean() * 100:.1f}%")

    top_channels = (
        keyword_data.groupby("channel_title")
        .agg(videos=("title", "count"), total_views=("view_count", "sum"), avg_views=("view_count", "mean"))
        .reset_index()
        .sort_values(["videos", "total_views"], ascending=False)
    )
    st.markdown("**Top channels for selected keyword**")
    st.dataframe(format_number_columns(top_channels), use_container_width=True, hide_index=True)

    video_cols = ["title", "channel_title", "view_count", "keyword_match_type", "title_category"]
    position_col = get_position_column(keyword_data.columns)
    if position_col:
        video_cols.insert(0, position_col)
    if "published_date" in keyword_data.columns:
        video_cols.append("published_date")
    if "thumbnail_url" in keyword_data.columns:
        video_cols.append("thumbnail_url")

    st.markdown("**Ranking videos for selected keyword**")
    st.dataframe(keyword_data[video_cols], use_container_width=True, hide_index=True)


def main() -> None:
    st.set_page_config(
        page_title="YouTube Organic Ranking Insights",
        page_icon="▶️",
        layout="wide",
    )

    st.title("YouTube Organic Ranking Insights")
    st.caption("Analyze top-ranking YouTube videos by keyword, channel, views, title format and keyword-title relevance.")

    with st.sidebar:
        st.header("Input")
        uploaded_file = st.file_uploader("Upload YouTube ranking Excel file", type=["xlsx", "xls"])
        market = st.text_input("Market", value="Sweden")
        language = st.text_input("Language", value="Swedish")
        top_n = st.slider("Top N in charts", min_value=5, max_value=50, value=15, step=5)

    if uploaded_file is None:
        st.info("Upload an Excel file to start. The file should contain a SERPs sheet with title, channel_title, view_count and Keyword columns.")
        return

    try:
        raw_data, sheet_name = find_serp_sheet(uploaded_file)
    except Exception as exc:
        st.error(f"Could not read the uploaded Excel file: {exc}")
        return

    validation = validate_input(raw_data, sheet_name)
    if not validation.is_valid:
        st.error(
            "The uploaded file is missing required columns from the detected sheet "
            f"'{validation.sheet_name}': {', '.join(validation.missing_columns)}"
        )
        st.write("Detected columns:", list(raw_data.columns))
        return

    data = prepare_data(raw_data)

    st.markdown(f"**Market:** {market}  |  **Language:** {language}  |  **Data sheet:** {sheet_name}")
    render_kpis(data)

    channel_summary = summarize_channels(data)
    keyword_views = summarize_keyword_views(data)
    keyword_inclusion = summarize_keyword_inclusion(data)
    title_categories = summarize_title_categories(data)

    st.divider()
    st.subheader("Top ranking accounts")
    render_top_channels_chart(channel_summary, top_n)
    st.dataframe(format_number_columns(channel_summary), use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Views by keyword")
    render_views_by_keyword_chart(keyword_views, top_n)
    st.dataframe(format_number_columns(keyword_views), use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Keyword in title analysis")
    st.dataframe(format_number_columns(keyword_inclusion), use_container_width=True, hide_index=True)

    missing_keyword_titles = data[~data["has_any_keyword_match"]][
        ["Keyword", "title", "channel_title", "view_count", "keyword_match_type", "title_category"]
    ].sort_values(["Keyword", "view_count"], ascending=[True, False])

    with st.expander("Videos ranking without a clear keyword/title match"):
        st.dataframe(missing_keyword_titles, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Title format analysis")
    st.dataframe(format_number_columns(title_categories), use_container_width=True, hide_index=True)

    category_overall = (
        data.groupby("title_category")
        .agg(videos=("title", "count"), total_views=("view_count", "sum"), avg_views=("view_count", "mean"))
        .reset_index()
        .sort_values(["videos", "total_views"], ascending=False)
    )
    fig = px.bar(
        category_overall.sort_values("videos", ascending=True),
        x="videos",
        y="title_category",
        orientation="h",
        hover_data=["total_views", "avg_views"],
        title="Most common title formats",
        labels={"videos": "Videos", "title_category": "Title format"},
    )
    fig.update_layout(yaxis_title="", xaxis_title="Videos")
    st.plotly_chart(fig, use_container_width=True)

    st.divider()
    render_keyword_detail(data)

    st.divider()
    st.subheader("Export analyzed data")
    output = data.copy()
    csv = output.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="Download enriched CSV",
        data=csv,
        file_name="youtube_organic_ranking_insights.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    main()
