"""
arabic_pdf.py: reusable building blocks for right-to-left Arabic PDF reports
with reportlab, plus matplotlib setup for Arabic chart labels.

The two libraries need opposite treatment:
  * reportlab has no complex text layout. Every Arabic string must be shaped
    (arabic_reshaper) and bidi-reordered (python-bidi) before it is drawn.
    Use ar() for single-line text and ArPara for multi-line prose.
  * matplotlib (verified on 3.11) shapes Arabic itself. Pass raw Arabic to it;
    calling ar() on chart text double-processes it and scrambles the letters.

Contents
  register_fonts()      register an Arabic TTF pair in reportlab and matplotlib
  make_palette()        four brand shades derived from one base colour
  ar(), ar_wrap_lines() shaping helpers
  ArPara                multi-line RTL paragraph flowable
  ArabicTOC             right-aligned clickable table of contents
  ArabicDoc             cover + body page templates, running header, TOC hooks
  make_styles()         paragraph styles bound to a font and palette
  h1(), h2(), cell(), cell_wrap(), kpi_strip(), data_table()
  fmt_money(), fmt_pct(), fmt_num()  number formatting, negatives in parentheses

Requirements: reportlab arabic-reshaper python-bidi matplotlib
"""
import re
import time
from ast import literal_eval
from xml.sax.saxutils import escape
from pathlib import Path

import arabic_reshaper
from bidi.algorithm import get_display

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Flowable, Frame, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents

FONT_DIR = Path(__file__).resolve().parent.parent / 'assets' / 'fonts'
DEFAULT_REGULAR = FONT_DIR / 'IBMPlexSansArabic-Regular.ttf'
DEFAULT_BOLD = FONT_DIR / 'IBMPlexSansArabic-Bold.ttf'

PAGE_W, PAGE_H = A4
MARGIN = 2.2 * cm
CONTENT_W = PAGE_W - 2 * MARGIN

FONT = 'Arabic'          # reportlab registration keys (any name works)
FONT_BOLD = 'Arabic-Bold'

# Universal variance colours: never replaced by the brand palette.
RED = colors.HexColor('#B42318')
GREEN = colors.HexColor('#1E7B4A')
GRAY = colors.HexColor('#6C757D')
TEXT = colors.HexColor('#222222')


# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------
def register_fonts(regular=DEFAULT_REGULAR, bold=DEFAULT_BOLD):
    """Register the font pair in reportlab (under FONT / FONT_BOLD) and in
    matplotlib. Returns the matplotlib family name, which is the font's
    internal name and can differ from the reportlab key."""
    pdfmetrics.registerFont(TTFont(FONT, str(regular)))
    pdfmetrics.registerFont(TTFont(FONT_BOLD, str(bold)))

    import matplotlib.font_manager as fm
    import matplotlib.pyplot as plt
    fm.fontManager.addfont(str(regular))
    fm.fontManager.addfont(str(bold))
    family = fm.FontProperties(fname=str(regular)).get_name()
    plt.rcParams['font.family'] = family
    plt.rcParams['axes.unicode_minus'] = False
    return family


# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
def _mix(hex_a, hex_b, t):
    a = [int(hex_a[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(hex_b[i:i + 2], 16) for i in (1, 3, 5)]
    return '#' + ''.join(f'{round(x + (y - x) * t):02X}' for x, y in zip(a, b))


def make_palette(base_hex):
    """Four shades from one brand colour: dark anchor (headings, header band),
    mid accent (primary chart series), light accent (secondary series) and a
    pale tint (zebra rows, highlight boxes). Returns hex strings so the same
    dict serves reportlab (via colors.HexColor) and matplotlib."""
    base = base_hex.upper()
    return {
        'dark': _mix(base, '#000000', 0.25),
        'mid': base,
        'light': _mix(base, '#FFFFFF', 0.40),
        'pale': _mix(base, '#FFFFFF', 0.88),
        'rule': _mix(base, '#FFFFFF', 0.70),
    }


def rl(hex_str):
    return colors.HexColor(hex_str)


# ---------------------------------------------------------------------------
# Shaping
# ---------------------------------------------------------------------------
LRM = '‎'
_MARKS = str.maketrans('', '', '‎‏')
# A run of Latin words/codes: must contain a letter; may include digits and
# . - / & ' inside, and spaces between Latin words ("Apple Inc.", "10-Q", "SEC EDGAR").
_LATIN_RUN = re.compile(r"[A-Za-z0-9][A-Za-z0-9.\-/&']*(?:[ ]+[A-Za-z0-9][A-Za-z0-9.\-/&']*)*")
# A number with a sign, currency or percent attached; ends on a digit or %, so
# a sentence-final period is not swallowed.
_NUM_AFFIX = re.compile(r"(?<![\w.])[+\-−]?[$]?\d(?:[\d,.]*\d)?%?")
_ARABIC = re.compile('[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]')


def _protect_latin(text):
    """Wrap Latin runs, and numbers carrying a sign, $ or %, in left-to-right
    marks. Without them codes like 10-Q flip to Q-10, the period of 'Inc.'
    jumps to the far end of the line, and symbols land on the wrong side of
    their number. Plain numbers need no help and are left alone."""
    def wrap(m):
        run = m.group(0)
        return f'{LRM}{run}{LRM}' if re.search('[A-Za-z]', run) else run
    text = _LATIN_RUN.sub(wrap, str(text))
    # Keep sign, $ and % on their side of the number. python-bidi otherwise
    # draws 15.1% as %15.1, $2,038 as 2,038$ and +32.5% as 32.5%+.
    def wrap_num(m):
        n = m.group(0)
        return f'{LRM}{n}{LRM}' if any(c in n for c in '+-−$%') else n
    return _NUM_AFFIX.sub(wrap_num, text)


def _display(shaped):
    """Bidi-reorder, then drop the invisible marks before drawing. Any line
    containing Arabic is forced right-to-left: auto-detection would make a
    line that starts with a Latin word (a company name) left-to-right.
    Lines without Arabic (numbers, codes) stay left-to-right."""
    base = 'R' if _ARABIC.search(shaped) else 'L'
    return get_display(shaped, base_dir=base).translate(_MARKS)


def ar(text):
    """Shape and bidi-reorder one line for reportlab. Do NOT use for
    matplotlib text."""
    return _display(arabic_reshaper.reshape(_protect_latin(text)))


def ar_wrap_lines(text, font, size, max_width):
    """Wrap Arabic prose for reportlab: shape first, greedy word-wrap on real
    glyph widths, then bidi-reorder each line on its own. reportlab's
    Paragraph wraps after reordering, which puts words on the wrong lines."""
    reshaped = arabic_reshaper.reshape(_protect_latin(text))
    space_w = pdfmetrics.stringWidth(' ', font, size)
    lines, cur, cur_w = [], [], 0.0
    for word in reshaped.split(' '):
        if not word:
            continue
        ww = pdfmetrics.stringWidth(word.translate(_MARKS), font, size)
        add = ww if not cur else ww + space_w
        if cur and cur_w + add > max_width:
            lines.append(cur)
            cur, cur_w = [word], ww
        else:
            cur.append(word)
            cur_w += add
    if cur:
        lines.append(cur)
    return [_display(' '.join(line)) for line in lines]


class ArPara(Flowable):
    """Multi-line Arabic paragraph. align: 'right' (default) or 'center'.
    Wrapping happens in wrap(), so the paragraph fits whatever width the
    frame or table cell gives it."""

    def __init__(self, text, font=FONT, size=10, leading=16, color=TEXT,
                 space_after=6, align='right'):
        super().__init__()
        self.text, self.font, self.size, self.leading = text, font, size, leading
        self.color, self.space_after, self.align = color, space_after, align
        self.lines, self._w = [], CONTENT_W

    def wrap(self, avail_w, avail_h):
        self._w = avail_w
        self.lines = ar_wrap_lines(self.text, self.font, self.size, avail_w)
        return avail_w, len(self.lines) * self.leading + self.space_after

    def draw(self):
        c = self.canv
        c.setFont(self.font, self.size)
        c.setFillColor(self.color)
        y = self.space_after + (len(self.lines) - 1) * self.leading + self.leading * 0.25
        for line in self.lines:
            if self.align == 'center':
                c.drawCentredString(self._w / 2, y, line)
            else:
                c.drawRightString(self._w, y, line)
            y -= self.leading


# ---------------------------------------------------------------------------
# Table of contents
# ---------------------------------------------------------------------------
class ArabicTOC(TableOfContents):
    """Right-aligned titles, page number flush left, no dot leaders.
    The stock drawPageNumbers() measures free space from the end of the title
    text, which assumes left-aligned titles; with right-aligned titles the
    page numbers land in the wrong place. This wrap() replaces that logic."""

    def wrap(self, avail_w, avail_h):
        entries = self._lastEntries or [(0, 'Placeholder', 0, None)]

        def draw_entry_end(canvas, kind, label):
            page, level, _key = label.split(',')
            style = self.getLevelStyle(int(level))
            canvas.setFont(style.fontName, style.fontSize)
            canvas.setFillColor(style.textColor)
            canvas.drawString(0, canvas._curr_tx_info['cur_y'], str(page))

        self.canv.setNamedCB('drawTOCEntryEnd', draw_entry_end)

        rows = []
        for level, text, page, key in entries:
            style = self.getLevelStyle(level)
            if key:
                text = f'<a href="#{key}">{text}</a>'
                key_val = repr(key).replace(',', '\\x2c').replace('"', '\\x2c')
            else:
                key_val = None
            p = Paragraph(f'{text}<onDraw name="drawTOCEntryEnd" '
                          f'label="{page},{level},{key_val}"/>', style)
            if style.spaceBefore:
                rows.append([Spacer(1, style.spaceBefore)])
            rows.append([p])

        self._table = Table(rows, colWidths=(avail_w,), style=self.tableStyle)
        self.width, self.height = self._table.wrapOn(self.canv, avail_w, avail_h)
        return self.width, self.height


# ---------------------------------------------------------------------------
# Document
# ---------------------------------------------------------------------------
class ArabicDoc(BaseDocTemplate):
    """Two page templates: 'Cover' (full page, no header) and 'Body' (coloured
    header band with the report title on the right and the page number on the
    left). Paragraphs with style H1/H2 and a _bookmarkName become TOC entries.
    Build with doc.multiBuild(story) so TOC page numbers resolve.
    cover=False starts page 1 on the Body template (no cover page)."""

    def __init__(self, filename, header_text, palette, cover=True, **kw):
        kw.setdefault('pagesize', A4)
        kw.setdefault('leftMargin', MARGIN)
        kw.setdefault('rightMargin', MARGIN)
        kw.setdefault('topMargin', 1.8 * cm)
        kw.setdefault('bottomMargin', 1.6 * cm)
        super().__init__(filename, **kw)
        self.header_text, self.palette = header_text, palette
        cover_frame = Frame(MARGIN, MARGIN, CONTENT_W, PAGE_H - 2 * MARGIN, id='cover')
        body = Frame(MARGIN, 1.6 * cm, CONTENT_W, PAGE_H - 3.4 * cm, id='body')
        templates = [PageTemplate(id='Cover', frames=[cover_frame], onPage=self._cover),
                     PageTemplate(id='Body', frames=[body], onPage=self._body)]
        # The first template is used for page 1; without a cover, start on Body.
        self.addPageTemplates(templates if cover else templates[::-1])

    def beforeDocument(self):
        # reportlab stamps local time plus the machine's UTC offset into the
        # PDF properties; write UTC ("Z") instead so the file reveals no time zone.
        self.canv.setDateFormatter(_utc_pdf_date)

    def _cover(self, canvas, doc):
        canvas.saveState()
        canvas.setFillColor(rl(self.palette['dark']))
        canvas.rect(0, PAGE_H - 0.6 * cm, PAGE_W, 0.6 * cm, fill=1, stroke=0)
        canvas.rect(0, 0, PAGE_W, 0.6 * cm, fill=1, stroke=0)
        canvas.restoreState()

    def _body(self, canvas, doc):
        canvas.saveState()
        band = 1.1 * cm
        canvas.setFillColor(rl(self.palette['dark']))
        canvas.rect(0, PAGE_H - band, PAGE_W, band, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont(FONT, 8.5)
        y = PAGE_H - band / 2 - 3
        canvas.drawRightString(PAGE_W - MARGIN, y, ar(self.header_text))
        canvas.drawString(MARGIN, y, ar(f'صفحة {doc.page}'))
        canvas.restoreState()

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name in ('H1', 'H2'):
            key = getattr(flowable, '_bookmarkName', None)
            if key:
                level = 0 if flowable.style.name == 'H1' else 1
                self.canv.bookmarkPage(key)
                self.notify('TOCEntry', (level, flowable.getPlainText(), self.page, key))


# ---------------------------------------------------------------------------
# Styles and small helpers
# ---------------------------------------------------------------------------
def _utc_pdf_date(*_local_parts):
    return 'D:%04d%02d%02d%02d%02d%02dZ' % time.gmtime()[:6]


def make_styles(palette):
    dark, mid = rl(palette['dark']), rl(palette['mid'])
    s = {}
    s['H1'] = ParagraphStyle('H1', fontName=FONT_BOLD, fontSize=15, leading=22,
                             textColor=dark, alignment=TA_RIGHT, spaceBefore=14, spaceAfter=6)
    s['H2'] = ParagraphStyle('H2', fontName=FONT_BOLD, fontSize=11.5, leading=17,
                             textColor=mid, alignment=TA_RIGHT, spaceBefore=10, spaceAfter=4)
    s['TH'] = ParagraphStyle('TH', fontName=FONT_BOLD, fontSize=8, leading=11,
                             textColor=colors.white, alignment=TA_CENTER)
    s['TD'] = ParagraphStyle('TD', fontName=FONT, fontSize=8, leading=11,
                             textColor=TEXT, alignment=TA_RIGHT)
    s['TDB'] = ParagraphStyle('TDB', parent=s['TD'], fontName=FONT_BOLD, textColor=dark)
    s['TDC'] = ParagraphStyle('TDC', parent=s['TD'], alignment=TA_CENTER)
    s['KpiLbl'] = ParagraphStyle('KpiLbl', fontName=FONT, fontSize=8, leading=11,
                                 textColor=GRAY, alignment=TA_CENTER)
    s['KpiVal'] = ParagraphStyle('KpiVal', fontName=FONT_BOLD, fontSize=15, leading=21,
                                 textColor=dark, alignment=TA_CENTER)
    s['TOC0'] = ParagraphStyle('TOC0', fontName=FONT_BOLD, fontSize=11, leading=18,
                               textColor=dark, alignment=TA_RIGHT)
    s['TOC1'] = ParagraphStyle('TOC1', fontName=FONT, fontSize=9.5, leading=15,
                               textColor=GRAY, alignment=TA_RIGHT, rightIndent=18)
    return s


_bookmark = [0]


def _heading(text, style):
    _bookmark[0] += 1
    p = Paragraph(ar(text), style)
    p._bookmarkName = f'bm{_bookmark[0]}'
    return p


def h1(text, styles):
    return _heading(text, styles['H1'])


def h2(text, styles):
    return _heading(text, styles['H2'])


def cell(text, style):
    """Single-line table cell."""
    return Paragraph(escape(ar(text)), style)


def cell_wrap(text, width, style):
    """Table cell that may need several lines: pre-wrap with real glyph
    widths, then join with <br/> so reportlab never re-wraps bidi text."""
    lines = ar_wrap_lines(text, style.fontName, style.fontSize, width)
    return Paragraph('<br/>'.join(escape(l) for l in lines), style)


def data_table(header, rows, col_widths, styles, palette, bold_last=False):
    """RTL table: pass columns in reading order (first column = rightmost);
    they are reversed here so the first one is drawn on the right. Text that
    does not fit its column is pre-wrapped (cell_wrap), never left to
    reportlab, which would wrap the already reordered string wrongly."""
    pad = 12   # Table default: 6pt left + 6pt right
    data = [[cell_wrap(h, w - pad, styles['TH']) for h, w in zip(header, col_widths)]]
    for i, r in enumerate(rows):
        st = styles['TDB'] if bold_last and i == len(rows) - 1 else styles['TD']
        data.append([c if isinstance(c, Flowable) else cell_wrap(c, w - pad, st)
                     for c, w in zip(r, col_widths)])
    data = [list(reversed(r)) for r in data]
    t = Table(data, colWidths=list(reversed(col_widths)), repeatRows=1)
    cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), rl(palette['dark'])),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LINEBELOW', (0, 0), (-1, -1), 0.4, rl(palette['rule'])),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]
    for i in range(1, len(data)):
        if i % 2 == 0:
            cmds.append(('BACKGROUND', (0, i), (-1, i), rl(palette['pale'])))
    t.setStyle(TableStyle(cmds))
    return t


def kpi_strip(items, styles, palette):
    """items: list of (label, value_text, colour or None), reading order."""
    labels = [cell(lbl, styles['KpiLbl']) for lbl, _, _ in items]
    values = []
    for _, val, col in items:
        st = styles['KpiVal']
        if col is not None:
            st = ParagraphStyle('kv', parent=st, textColor=col)
        values.append(cell(val, st))
    w = CONTENT_W / len(items)
    t = Table([list(reversed(values)), list(reversed(labels))], colWidths=[w] * len(items))
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), rl(palette['pale'])),
        ('LINEAFTER', (0, 0), (-2, -1), 0.6, colors.white),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    return t


# ---------------------------------------------------------------------------
# Number formatting (accounting convention: negatives in parentheses)
# ---------------------------------------------------------------------------
NA = 'غير متوفر'


def fmt_num(n, decimals=0):
    if n is None:
        return NA
    s = f'{abs(n):,.{decimals}f}'
    return f'({s})' if n < 0 else s


def fmt_money(n, decimals=0, symbol='$'):
    if n is None:
        return NA
    s = f'{symbol}{abs(n):,.{decimals}f}'
    return f'({s})' if n < 0 else s


def fmt_pct(n, decimals=1, signed=False):
    if n is None:
        return NA
    s = f'{abs(n):.{decimals}f}%'
    if n < 0:
        return f'({s})'
    return f'+{s}' if signed and n > 0 else s


# Levantine month names (use Egyptian/Gulf names if the audience expects them).
MONTHS_AR = ['كانون الثاني', 'شباط', 'آذار', 'نيسان', 'أيار', 'حزيران',
             'تموز', 'آب', 'أيلول', 'تشرين الأول', 'تشرين الثاني', 'كانون الأول']
