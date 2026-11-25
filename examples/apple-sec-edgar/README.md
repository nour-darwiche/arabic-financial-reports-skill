# Real-data example: Apple Inc. (SEC EDGAR)

The main sample in this repo uses a fictional company. This example runs the same toolkit on **real published figures**, so you can check every number against the official filings.

**Output:** [Apple_report_AR.pdf](Apple_report_AR.pdf), 5 pages: cover, table of contents, executive summary, quarterly income statements, revenue growth, margins, operating expenses, data notes.

## What it tests that the fictional sample does not

- **A missing quarter.** Apple files no 10-Q for its fourth fiscal quarter. Q4 is derived as the annual 10-K figure minus Q1 to Q3, then checked with the same arithmetic as every other quarter (gross margin = revenue − cost of sales, operating expenses = R&D + SG&A, operating income = gross margin − operating expenses).
- **No budget.** The source has none, so the report compares each quarter with the same quarter of the previous year instead of inventing a target.
- **Latin text inside Arabic.** The company name and filing codes (`Apple Inc.`, `10-Q`, `10-K`) sit inside right-to-left sentences, which is where bidi bugs show up.
- **Claims backed by data.** Sentences such as "revenue grew in every quarter" are only written when the numbers confirm them; otherwise the script writes the actual count.

## Run

From the repository root:

```bash
python examples/apple-sec-edgar/apple_report.py
```

It reads `apple_financials.xlsx`, writes the extracted figures to `apple_data.json`, and builds the PDF. No network access is needed.

## Data

| | |
|---|---|
| Source | SEC EDGAR XBRL company facts API, company CIK 320193 |
| Filings | 10-Q (Q1 to Q3) and 10-K (full year), fiscal years 2025 and 2026 |
| Downloaded | 25 November 2026 |
| Units | USD millions, rounded from the filed USD values |
| Fiscal year | Ends on the last Saturday of September |

SEC EDGAR data is public domain. Later filings or amendments can change these figures; the workbook is a snapshot from the date above.

## Disclaimer

This example is not affiliated with or endorsed by Apple Inc. It demonstrates a reporting toolkit and is not investment analysis or advice.
