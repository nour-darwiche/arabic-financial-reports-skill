# Reference: Arabic Financial Report: Visual Spec, Chapter Template, Writing Rules

## Visual spec

**Brand color is a per-report parameter, never hardcoded.** Each company can have its own base
color (e.g. "dark green" for one company, "navy blue" for another). Derive four shades from
whatever base color is given, keeping this structure:

- **Dark anchor** (headers, cover title, section headings): the base color at near-full saturation/darkness
- **Mid accent** (accent rules, chart primary series, highlight text): the base color, one step lighter
- **Light accent** (secondary chart series, hover/accent details): a clearly lighter tint of the base
- **Pale tint** (table zebra rows, highlight box backgrounds): a very pale, near-white tint of the base

`arabic_pdf.make_palette(base_hex)` derives all four from one hex value.

Keep red for negative/warning figures and green for positive/favorable **regardless of the brand
color**: that's a separate, universal signal (variance coloring) and shouldn't be swallowed by a
rebrand, including when the brand color itself is green.

**Choosing the color: don't block on it.**
- If the user names a color or brand, use it (a name like "dark green" is enough; pick the hex yourself).
- Otherwise use the default **navy `#1F4E79`** without asking. Navy is the conventional finance
  color, prints well in grayscale, and leaves green and red free to mean favorable/unfavorable.
- In the chat message that hands over the draft (never inside the PDF), add one line saying the
  color is the default and can be changed with any color name or hex. A change is one parameter
  and a rebuild; nothing else moves.

**Confirm before generating a full draft** (these affect correctness, not taste):
- Whether to include an author/prepared-by line, and what it should say (don't default to a specific person's name unless told to).
- Whether the running header repeats the company name or just the report title (both reasonable; ask if unclear).
- The exact legal/brand company name to use; don't let a stale name from a raw source file leak into the output.

**Font**: one font that covers Arabic *and* Latin (digits, `$`, `%`, parentheses, English
terms) with a clean, formal register. Default: the bundled IBM Plex Sans Arabic Regular/Bold
(`assets/fonts/`, SIL Open Font License). On Windows, Segoe UI Semibold
(`C:/Windows/Fonts/seguisb.ttf`) also works well but cannot be redistributed. Confirm the font
resolves in both reportlab (arbitrary registration key) and matplotlib (needs the font's actual
internal family name via `FontProperties(fname=...).get_name()`, which can differ from the
registration key) before generating real content. `arabic_pdf.register_fonts()` does both.

**Cover page**: large company-name title, report subtitle, period line, thin horizontal rule,
prepared-by line only if requested.

**Running header** (every body page): report title + period, right-aligned in RTL; page number,
left-aligned.

**Table of contents**: clickable, via reportlab's two-pass `multiBuild` +
`bookmarkPage`/`notify('TOCEntry', ...)`. RTL (right-aligned) titles need a custom
`TableOfContents` subclass overriding `wrap()`: the built-in one assumes left-aligned titles and
misplaces the page number.

## Chapter template

Adapt to what the source data actually supports; don't force a chapter with nothing real to say.

1. Executive Summary: headline KPIs, the core story in a few paragraphs
2. Monthly Income Statement: full table, actual vs budget, every month + period total
3. Revenue and Volume Analysis: trend charts + tables
4. Margin Analysis: relationship between volume, cost, and margin over time (often the most interesting finding)
5. Segment / Business-Line Performance
6. Regional / Geographic Performance (if the business has a geographic dimension)
7. Correlation / Relationship Analysis: whatever genuine statistical relationships the investigation phase found
8. Recovery / Trend Status: if there's a shock-and-recovery story (a crisis, a seasonal collapse, a one-off event)
9. Risk Register: concrete criteria with real numbers, grouped by severity
10. Recommendations: tied explicitly to specific findings earlier in the report, not generic advice
11. Data Notes and Assumptions: currency basis, period coverage, known limitations, any conflicting sources found during investigation

## Arabic writing rules (default house style; adjust to your organisation)

- **No em-dashes and no hyphens anywhere in rendered text.** Use "·" or "،" or parentheses as
  separators. Date ranges: "من كانون الثاني حتى حزيران" not "كانون الثاني-حزيران". Dates:
  "18 آب 2026" not "2026-08-18". Applies to every string in the PDF including chart labels. A
  hyphen inside real data (a product or place name) is fine; a hyphen used as a separator or range
  marker is not.
- **Negative numbers in parentheses** (accounting convention), never a leading minus sign.
- **No AI-generic phrasing.** No hedge-everything language, no stock transitions, no restating the
  obvious. Write like a sharp, confident analyst briefing a manager: direct where the data
  supports it, hedged only where it genuinely should be.
- **No meta text in the report.** Nothing about how it was made: no "test", "sample", "generated
  by", tool or AI mentions, and no disclaimers such as "not investment advice", unless the user
  asks for them. Notes about the process or the default color belong in the chat message.
- **Formal professional Arabic (MSA)** unless a more colloquial register has been explicitly
  confirmed as right for this deliverable.
- Keep English technical terms only where natural and expected (Budget, Actual, KPI, YTD); don't
  force translation, don't sprinkle English gratuitously.

## What to do first, in order

1. Confirm folder path, list every file in it.
2. Open every sheet in every file, report back a summary (contents, period, anything inconsistent); wait for confirmation before extracting.
3. Propose a chapter list based on what the data actually supports, confirm before writing.
4. Build the extraction JSON (one source of truth, don't re-parse Excel per number), then the generator, then a first draft; walk through headline findings before polishing.
