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

PLOTLY_TEMPLATE = "plotly_white"
PRIMARY_COLOR = "#FF0033"
SECONDARY_COLOR = "#5B21B6"
ACCENT_COLOR = "#06B6D4"
DARK_TEXT = "#111827"
MUTED_TEXT = "#6B7280"


@dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    missing_columns: list[str]
    sheet_name: str | None = None


def apply_custom_css() -> None:
    st.markdown(
        """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

            html, body, [class*="css"] {
                font-family: 'Inter', sans-serif;
            }

            .stApp {
                background:
                    radial-gradient(circle at top left, rgba(255, 0, 51, 0.12), transparent 28rem),
                    radial-gradient(circle at top right, rgba(91, 33, 182, 0.12), transparent 32rem),
                    linear-gradient(180deg, #F8FAFC 0%, #EEF2F7 100%);
            }

            section[data-testid="stSidebar"] {
                background: #0F172A;
                color: #FFFFFF;
                border-right: 1px solid rgba(255,255,255,0.08);
            }

            section[data-testid="stSidebar"] label,
            section[data-testid="stSidebar"] p,
            section[data-testid="stSidebar"] span,
            section[data-testid="stSidebar"] h1,
            section[data-testid="stSidebar"] h2,
            section[data-testid="stSidebar"] h3 {
                color: #E5E7EB !important;
            }

            section[data-testid="stSidebar"] [data-testid="stFileUploader"] {
                background: rgba(255,255,255,0.06);
                border: 1px dashed rgba(255,255,255,0.22);
                border-radius: 18px;
                padding: 0.75rem;
            }

            .block-container {
                padding-top: 2.1rem;
                padding-bottom: 3rem;
                max-width: 1380px;
            }

            .hero {
                padding: 2rem 2.25rem;
                border-radius: 28px;
                color: white;
                background:
                    linear-gradient(135deg, rgba(15,23,42,0.98), rgba(30,41,59,0.96) 52%, rgba(255,0,51,0.95));
                box-shadow: 0 24px 70px rgba(15,23,42,0.25);
                border: 1px solid rgba(255,255,255,0.12);
                margin-bottom: 1.25rem;
            }

            .hero-eyebrow {
                font-size: 0.78rem;
                font-weight: 800;
                letter-spacing: 0.12em;
                text-transform: uppercase;
                color: rgba(255,255,255,0.72);
                margin-bottom: 0.65rem;
            }

            .hero-title {
                font-size: clamp(2rem, 4vw, 3.6rem);
                font-weight: 800;
                line-height: 1.02;
                margin: 0;
            }

            .hero-subtitle {
                font-size: 1.02rem;
                max-width: 780px;
                color: rgba(255,255,255,0.78);
                margin-top: 1rem;
                margin-bottom: 0;
            }

            .context-pill-wrap {
                display: flex;
                flex-wrap: wrap;
                gap: 0.55rem;
                margin-top: 1.15rem;
            }

            .context-pill {
                display: inline-flex;
                align-items: center;
                border-radius: 999px;
                padding: 0.46rem 0.78rem;
                background: rgba(255,255,255,0.11);
                border: 1px solid rgba(255,255,255,0.14);
                color: rgba(255,255,255,0.88);
                font-size: 0.82rem;
                font-weight: 600;
            }

            .section-card {
                background: rgba(255,255,255,0.88);
                border: 1px solid rgba(148,163,184,0.24);
                border-radius: 24px;
                padding: 1.25rem 1.35rem;
                box-shadow: 0 18px 45px rgba(15, 23, 42, 0.08);
                margin-bottom: 1.1rem;
            }

            .section-title {
                font-size: 1.25rem;
                font-weight: 800;
                color: #111827;
                margin-bottom: 0.15rem;
            }

            .section-subtitle {
                font-size: 0.92rem;
                color: #64748B;
                margin-bottom: 1rem;
            }

            div[data-testid="stMetric"] {
                background: rgba(255,255,255,0.92);
                border: 1px solid rgba(148,163,184,0.22);
                border-radius: 22px;
                padding: 1rem 1.1rem;
                box-shadow: 0 12px 34px rgba(15,23,42,0.08);
            }

            div[data-testid="stMetricLabel"] p {
                color: #64748B;
                font-weight: 700;
                font-size: 0.86rem;
            }

            div[data-testid="stMetricValue"] {
                color: #111827;
                font-weight: 800;
            }

            .stTabs [data-baseweb="tab-list"] {
                gap: 0.6rem;
                background: rgba(255,255,255,0.7);
                border-radius: 18px;
                padding: 0.45rem;
                border: 1px solid rgba(148,163,184,0.22);
            }

            .stTabs [data-baseweb="tab"] {
                border-radius: 14px;
                padding: 0.55rem 1rem;
                font-weight: 700;
                color: #475569;
            }

            .stTabs [aria-selected="true"] {
                background: #0F172A;
                color: white !important;
            }

            div[data-testid="stDataFrame"] {
                border-radius: 18px;
                overflow: hidden;
                border: 1px solid rgba(148,163,184,0.22);
            }

            .upload-empty-state {
                background: rgba(255,255,255,0.92);
                border: 1px solid rgba(148,163,184,0.24);
                border-radius: 28px;
                padding: 2rem;
                text-align: center;
                box-shadow: 0 18px 45px rgba(15,23,42,0.08);
            }

            .upload-empty-state h3 {
                margin-top: 0;
                font-size: 1.45rem;
            }

            .small-muted {
                color: #64748B;
                font-size: 0.9rem;
            }

            hr {
                border-color: rgba(148,163,184,0.25);
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_section_header(title: str, subtitle: str | None = None) -> None:
    subtitle_html = f'<div class="section-subtitle">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f"""
        <div class="section-title">{title}</div>
        {subtitle_html}
        """,
        unsafe_allow_html=True,
    )


def render_hero(market: str, language: str, sheet_name: str | None = None) -> None:
    sheet_pill = f'<span class="context-pill">Sheet: {sheet_name}</span>' if sheet_name else ""
    st.markdown(
        f"""
        <div class="hero">
            <div class="hero-eyebrow">YouTube organic search intelligence</div>
            <h1 class="hero-title">Ranking patterns, channels and title formats in one view.</h1>
            <p class="hero-subtitle">
                Analyze who wins visibility for your keyword set, which video formats dominate,
                and whether top-ranking titles actually use the searched keyword.
            </p>
            <div class="context-pill-wrap">
                <span class="context-pill">Market: {market}</span>
                <span class="context-pill">Language: {language}</span>
                {sheet_pill}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


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

    first_sheet = workbook.sheet_names[0]
    return pd.read_excel(workbook, sheet_name=first_sheet), first_sheet


def validate_input(df: pd.DataFrame, sheet_name: str) -> ValidationResult:
    missing = sorted(REQUIRED_COLUMNS - set(df.columns))
    return ValidationResult(is_valid=not missing, missing_columns=missing, sheet_name=sheet_name)


def get_position_column(columns: Iterable[str]) -> str | None:
    normalized = {str(col).casefold(): str(col) for col in columns}
    for candidate in ["position", "rank", "ranking_position"]:
        if candidate in normalized:
            return normalized[candidate]
    return None


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

    return (
        data.groupby("channel_title", dropna=False)
        .agg(**aggregations)
        .reset_index()
        .sort_values(["ranking_videos", "unique_keywords", "total_views"], ascending=False)
    )


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


def compact_number(value: float | int) -> str:
    value = float(value)
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return f"{int(value):,}"


def render_kpis(data: pd.DataFrame) -> None:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Keywords", f"{data['Keyword'].nunique():,}")
    col2.metric("Ranking videos", f"{len(data):,}")
    col3.metric("Unique channels", f"{data['channel_title'].nunique():,}")
    col4.metric("Total views", compact_number(data["view_count"].sum()))


def apply_chart_layout(fig, height: int) -> None:
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        height=height,
        margin=dict(l=10, r=18, t=48, b=18),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color=DARK_TEXT),
        title=dict(font=dict(size=18, family="Inter, sans-serif", color=DARK_TEXT)),
        hoverlabel=dict(bgcolor="#0F172A", font_size=13, font_family="Inter, sans-serif"),
    )
    fig.update_xaxes(showgrid=True, gridcolor="rgba(148,163,184,0.25)", zeroline=False)
    fig.update_yaxes(showgrid=False, zeroline=False)


def render_top_channels_chart(channel_summary: pd.DataFrame, top_n: int) -> None:
    chart_data = channel_summary.head(top_n).sort_values("ranking_videos", ascending=True)
    fig = px.bar(
        chart_data,
        x="ranking_videos",
        y="channel_title",
        orientation="h",
        hover_data={
            "unique_keywords": ":,",
            "total_views": ":,",
            "avg_views": ":,.0f",
            "ranking_videos": ":,",
            "channel_title": False,
        },
        labels={
            "channel_title": "Channel",
            "ranking_videos": "Ranking videos",
            "unique_keywords": "Unique keywords",
            "total_views": "Total views",
            "avg_views": "Average views",
        },
        title=f"Top {top_n} ranking YouTube accounts",
        color_discrete_sequence=[PRIMARY_COLOR],
    )
    apply_chart_layout(fig, max(430, top_n * 32))
    fig.update_layout(yaxis_title="", xaxis_title="Ranking videos")
    st.plotly_chart(fig, use_container_width=True)


def render_views_by_keyword_chart(keyword_views: pd.DataFrame, top_n: int) -> None:
    chart_data = keyword_views.head(top_n).sort_values("total_views", ascending=True)
    fig = px.bar(
        chart_data,
        x="total_views",
        y="Keyword",
        orientation="h",
        hover_data={
            "ranking_videos": ":,",
            "unique_channels": ":,",
            "avg_views": ":,.0f",
            "median_views": ":,.0f",
            "total_views": ":,",
            "Keyword": False,
        },
        labels={
            "Keyword": "Keyword",
            "total_views": "Total views",
            "ranking_videos": "Ranking videos",
            "unique_channels": "Unique channels",
            "avg_views": "Average views",
            "median_views": "Median views",
        },
        title=f"Top {top_n} keywords by summed views of ranking videos",
        color_discrete_sequence=[SECONDARY_COLOR],
    )
    apply_chart_layout(fig, max(430, top_n * 32))
    fig.update_layout(yaxis_title="", xaxis_title="Total views")
    st.plotly_chart(fig, use_container_width=True)


def render_title_category_chart(data: pd.DataFrame) -> None:
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
        hover_data={"total_views": ":,", "avg_views": ":,.0f", "videos": ":,", "title_category": False},
        title="Most common title formats",
        labels={"videos": "Videos", "title_category": "Title format"},
        color_discrete_sequence=[ACCENT_COLOR],
    )
    apply_chart_layout(fig, 430)
    fig.update_layout(yaxis_title="", xaxis_title="Videos")
    st.plotly_chart(fig, use_container_width=True)


def render_keyword_detail(data: pd.DataFrame) -> None:
    selected_keyword = st.selectbox("Select keyword", sorted(data["Keyword"].dropna().unique()))
    keyword_data = data[data["Keyword"] == selected_keyword].copy()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Videos", f"{len(keyword_data):,}")
    col2.metric("Channels", f"{keyword_data['channel_title'].nunique():,}")
    col3.metric("Exact title match", f"{keyword_data['has_exact_keyword'].mean() * 100:.1f}%")
    col4.metric("Views", compact_number(keyword_data["view_count"].sum()))

    top_channels = (
        keyword_data.groupby("channel_title")
        .agg(videos=("title", "count"), total_views=("view_count", "sum"), avg_views=("view_count", "mean"))
        .reset_index()
        .sort_values(["videos", "total_views"], ascending=False)
    )

    left, right = st.columns([0.42, 0.58])
    with left:
        st.markdown("**Top channels for selected keyword**")
        st.dataframe(format_number_columns(top_channels), use_container_width=True, hide_index=True)

    with right:
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


def render_empty_state() -> None:
    st.markdown(
        """
        <div class="upload-empty-state">
            <h3>Upload a YouTube ranking Excel file to start.</h3>
            <p class="small-muted">
                Required columns: <strong>title</strong>, <strong>channel_title</strong>,
                <strong>view_count</strong> and <strong>Keyword</strong>. A sheet named
                <strong>SERPs</strong> will be detected automatically when available.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(
        page_title="YouTube Search Visibility Analyzer",
        page_icon="▶️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    apply_custom_css()

    with st.sidebar:
        st.markdown("### YouTube Search Visibility")
        st.caption("Organic ranking analysis for cross-platform search consultants.")
        uploaded_file = st.file_uploader("Upload ranking Excel file", type=["xlsx", "xls"])
        st.markdown("---")
        market = st.text_input("Market", value="Sweden")
        language = st.text_input("Language", value="Swedish")
        top_n = st.slider("Top N in charts", min_value=5, max_value=50, value=15, step=5)
        st.markdown("---")
        st.caption("Tip: add a `position`, `rank` or `ranking_position` column to unlock top 3/top 10 metrics.")

    if uploaded_file is None:
        render_hero(market, language)
        render_empty_state()
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
    render_hero(market, language, sheet_name)
    render_kpis(data)

    channel_summary = summarize_channels(data)
    keyword_views = summarize_keyword_views(data)
    keyword_inclusion = summarize_keyword_inclusion(data)
    title_categories = summarize_title_categories(data)

    overview_tab, keyword_tab, title_tab, export_tab = st.tabs([
        "Overview",
        "Keyword deep-dive",
        "Title intelligence",
        "Export",
    ])

    with overview_tab:
        col1, col2 = st.columns([0.52, 0.48])
        with col1:
            with st.container():
                render_section_header(
                    "Top ranking accounts",
                    "Channels that appear most often across the uploaded keyword set.",
                )
                render_top_channels_chart(channel_summary, top_n)
        with col2:
            with st.container():
                render_section_header(
                    "Views by keyword",
                    "Summed views for videos ranking within each keyword landscape.",
                )
                render_views_by_keyword_chart(keyword_views, top_n)

        st.markdown("---")
        render_section_header("Channel performance table", "Sortable summary of ranking presence, views and optional position metrics.")
        st.dataframe(format_number_columns(channel_summary), use_container_width=True, hide_index=True)

    with keyword_tab:
        render_section_header(
            "Keyword deep-dive",
            "Inspect the ranking videos, channels and title-match rate for a single keyword.",
        )
        render_keyword_detail(data)

        st.markdown("---")
        render_section_header("Views by keyword table")
        st.dataframe(format_number_columns(keyword_views), use_container_width=True, hide_index=True)

    with title_tab:
        col1, col2 = st.columns([0.47, 0.53])
        with col1:
            render_section_header(
                "Keyword in title analysis",
                "Checks exact phrase matches and broader partial keyword matches.",
            )
            st.dataframe(format_number_columns(keyword_inclusion), use_container_width=True, hide_index=True)
        with col2:
            render_section_header(
                "Title format mix",
                "Rule-based categorization of ranking video titles.",
            )
            render_title_category_chart(data)

        st.markdown("---")
        render_section_header("Title categories by keyword")
        st.dataframe(format_number_columns(title_categories), use_container_width=True, hide_index=True)

        missing_keyword_titles = data[~data["has_any_keyword_match"]][
            ["Keyword", "title", "channel_title", "view_count", "keyword_match_type", "title_category"]
        ].sort_values(["Keyword", "view_count"], ascending=[True, False])

        with st.expander("Videos ranking without a clear keyword/title match", expanded=False):
            st.dataframe(missing_keyword_titles, use_container_width=True, hide_index=True)

    with export_tab:
        render_section_header(
            "Export analyzed data",
            "Download the enriched row-level dataset with keyword-match and title-category fields added.",
        )
        output = data.copy()
        csv = output.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="Download enriched CSV",
            data=csv,
            file_name="youtube_organic_ranking_insights.csv",
            mime="text/csv",
            use_container_width=True,
        )

        st.markdown("---")
        st.markdown("**Included enrichment columns**")
        st.code("keyword_match_type\nhas_exact_keyword\nhas_any_keyword_match\ntitle_category", language="text")


if __name__ == "__main__":
    main()
