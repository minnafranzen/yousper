# YouTube Organic Ranking Insights

Streamlit app for analyzing organic YouTube ranking exports by keyword, channel, views, title format and keyword-title relevance.

## What the app does

- Uploads an Excel file with YouTube ranking data
- Detects a `SERPs` sheet automatically when available
- Shows top-ranking YouTube accounts across all keywords
- Summarizes views per keyword
- Shows top channels per keyword
- Checks whether ranking video titles include the keyword
- Categorizes title formats with rule-based logic
- Lets users export enriched data as CSV

## Required input columns

The uploaded Excel file must contain these columns:

```text
title
channel_title
view_count
Keyword
```

Optional columns supported:

```text
published_date
thumbnail_url
subscriber_count
position
rank
ranking_position
```

If a ranking position column exists, the app will add average position, top 3 and top 10 ranking metrics.

## Local setup

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Recommended GitHub structure

```text
youtube-organic-serp-analyzer/
├── app.py
├── requirements.txt
├── README.md
└── .gitignore
```

## Notes

The title categorization is intentionally rule-based in the first version. That keeps the MVP transparent and avoids unpredictable AI classification. AI summaries can be added later once the core ranking analysis is stable.
