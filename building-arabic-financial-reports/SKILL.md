---
name: building-arabic-financial-reports
description: Use when building a financial analysis PDF report in Arabic from raw Excel workbooks, or when asked to replicate a previous Arabic financial report's style/format for a new company. Triggers include "write a financial report in Arabic", "same style as before but for [company]", RTL PDF generation, or Arabic text rendering as garbled/reversed/mojibake in a PDF or chart.
---

# Building Arabic Financial Reports

## Overview

A stakeholder-ready Arabic financial PDF is not raw Excel turned into RTL sentences. It requires (1) reading every sheet before writing anything, (2) computing real relationships instead of asserting them, and (3) a specific reportlab/matplotlib stack because Arabic shaping breaks both libraries in opposite ways. Skipping any of these produces a report that looks plausible but is either wrong or unreadable.

## When to use

- Any request for a financial/analytical PDF report written in Arabic.
- "Do the same report as [previous company] but for [new company]": style transfer requests.
- Debugging: Arabic text renders reversed, disconnected letters, or garbled in a PDF or matplotlib chart.

Not for: English-only reports (skip the shaping/bidi steps entirely; plain reportlab `Paragraph` works fine). Not for PowerPoint output.

## Requirements

```
pip install reportlab arabic-reshaper python-bidi matplotlib openpyxl numpy pymupdf
```

## Investigation phase (do this before writing any code)

Open **every sheet in every workbook**. A second data block (budget under actuals, a per-region tab, a stale-labeled sheet) is routinely missed on a first pass. Cross-validate any figure that could come from two places (sum the detailed files, compare to the summary; don't trust whichever you opened first). Verify structure by checking arithmetic relationships (do monthly columns sum to the YTD column?), not by trusting header labels. Report findings back before writing the generator.

## Analytical discipline

Every KPI needs a driver from other data in the workbook, not just the number. Compute real relationships (Pearson r, actual ratios) instead of writing "significantly"/"notably" with nothing behind it. Hedge causation explicitly when the data only supports correlation. Never invent a budget/target that isn't in the source. Full methodology, chapter template, and writing-style rules: see [reference.md](reference.md).

## The Arabic rendering stack: this is the part that breaks

| Library | Needs Arabic pre-shaped? | Why |
|---|---|---|
| reportlab (PDF text) | **Yes**: `get_display(arabic_reshaper.reshape(text))` before every draw call | No native complex-text-layout support |
| matplotlib (charts) | **No**: pass raw Arabic directly (verified on matplotlib 3.11) | Shapes/reorders natively; pre-shaping double-processes and corrupts it |

Multi-line body text needs a custom flowable (reportlab's own `Paragraph` mis-wraps already-shaped bidi text: wrap on real glyph widths of the *unshaped* text, then bidi-reorder each wrapped line). A right-aligned TOC also needs a custom `wrap()` override; reportlab's built-in `TableOfContents` assumes left-aligned titles and misplaces page numbers.

The font must cover **both Arabic and Latin**, including digits, `$`, `%` and parentheses. Many Arabic fonts (for example Noto Naskh Arabic) have no Latin glyphs, so numbers with symbols and English terms silently render blank. The bundled IBM Plex Sans Arabic (SIL Open Font License) covers both.

**Working implementation to copy from:** [scripts/arabic_pdf.py](scripts/arabic_pdf.py) (font registration, palette from one brand colour, the wrap-then-bidi paragraph class, the RTL TOC subclass, cover/header page templates, RTL tables and KPI strip, accounting number formats). Run [scripts/example_report.py](scripts/example_report.py) on [assets/sample_company.xlsx](assets/sample_company.xlsx) to see a complete report built from fictional data; the output is [assets/sample_report.pdf](assets/sample_report.pdf) and the extracted single source of truth is [assets/sample_report.json](assets/sample_report.json).

## Verification

`pypdf`/PyMuPDF **text extraction** cannot reliably substring-search shaped Arabic, so a real bug can silently pass a text-based check. Render pages to PNG (`fitz`/PyMuPDF `get_pixmap`) and look at them, especially after touching fonts, column widths, or chart text. Treat any matplotlib "Glyph ... missing from font" warning as a failure. Run `python scripts/test_bidi.py` after any change to the shaping helpers. Do not judge which side of a number `%` or `$` sits on by eye in Arabic text; measure it from character positions (`page.get_text('rawdict')`). Spot-check every number against the source JSON independently; a correct extraction doesn't guarantee a correct render.

## Common mistakes

| Mistake | Fix |
|---|---|
| Pre-shaping Arabic before passing to matplotlib | Pass raw Arabic to matplotlib; only reportlab needs `arabic_reshaper`+bidi |
| Using reportlab's stock `Paragraph`/`TableOfContents` for RTL | Use the custom wrap-then-bidi flowable and RTL-aware TOC subclass |
| An Arabic-only font | `$`, `%`, `(`, `)` and Latin words vanish. Use a font covering both scripts and check the glyph-missing warnings |
| Letting bidi auto-detect the line direction | A line starting with a Latin word ("Apple Inc. · تقرير") turns left-to-right. Force RTL for any line containing Arabic, LTR for pure numbers (`ar()` does this) |
| Bare symbols and codes inside Arabic sentences | python-bidi draws `15.1%` as `%15.1`, `$2,038` as `2,038$`, `+7.9%` as `7.9%+`, `10-Q` as `Q-10`, and moves the period of `Inc.` to the line end. Wrap those runs in LRM marks, strip the marks after reordering (`ar()` does this); `scripts/test_bidi.py` guards it |
| Long table headers in stock `Paragraph` cells | They wrap in the wrong word order; pre-wrap every cell with `cell_wrap()` (`data_table()` does this) |
| Trusting `pypdf`/text-extraction to verify Arabic PDF content | Render to PNG and look, or verify against the source JSON directly |
| "Don't round the numbers" taken literally as full decimal precision everywhere | Usually means "stop abbreviating (1940→2K)", not "show 28.52 instead of 29"; confirm scope before a broad precision change |
| Editing formatter strings containing `\xa0`/U+2212 minus sign with plain-text find/replace | These aren't the ASCII characters they look like; inspect via `repr()` and do an assert-verified line replacement |

Visual/structural spec (palette, cover/header/chapter template) and full writing-style rules: [reference.md](reference.md).
