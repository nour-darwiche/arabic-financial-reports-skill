"""
example_report.py: end-to-end example. Excel -> one JSON source of truth ->
Arabic PDF with cover, clickable RTL table of contents, KPI strip, tables and
charts. Every sentence in the report is computed from the data.

    python scripts/make_sample_data.py      # writes assets/sample_company.xlsx
    python scripts/example_report.py        # writes assets/sample_report.pdf

Optional: --xlsx <file> --out <pdf> --color <hex>
The sample data is fictional (see make_sample_data.py).
"""
import argparse
import json
import shutil
import tempfile
from pathlib import Path

import numpy as np
from openpyxl import load_workbook

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import cm
from reportlab.platypus import (HRFlowable, Image, NextPageTemplate, PageBreak,
                                Paragraph, Spacer, KeepTogether)

import arabic_pdf as A

ROOT = Path(__file__).resolve().parent.parent
COMPANY_AR = 'شركة الأفق للتوزيع'
REPORT_AR = 'تقرير الأداء المالي'
N_MONTHS = 6
PERIOD_AR = f'من {A.MONTHS_AR[0]} حتى {A.MONTHS_AR[N_MONTHS - 1]} 2026'
REGION_AR = {'North': 'الشمال', 'Centre': 'الوسط', 'South': 'الجنوب'}
LINE_AR = {
    'Revenue': 'الإيرادات', 'Cost of goods sold': 'كلفة البضاعة المباعة',
    'Gross profit': 'إجمالي الربح', 'Total opex': 'المصاريف التشغيلية',
    'Net profit': 'صافي الربح',
}
COST_LINES = {'Cost of goods sold', 'Total opex'}   # lower than budget = favourable


# ---------------------------------------------------------------------------
# 1. Extraction: read every block once, validate, write JSON
# ---------------------------------------------------------------------------
def read_block(ws, title):
    """Find a block by its title cell and read label -> monthly values + YTD."""
    start = next(r for r in range(1, ws.max_row + 1) if ws.cell(r, 1).value == title)
    out, r = {}, start + 2
    while ws.cell(r, 1).value:
        vals = [ws.cell(r, c).value for c in range(2, 2 + N_MONTHS)]
        out[ws.cell(r, 1).value] = {'months': vals, 'ytd': ws.cell(r, 2 + N_MONTHS).value}
        r += 1
    return out


def extract(xlsx):
    wb = load_workbook(xlsx, data_only=True)
    pnl = wb['P&L']
    data = {'actual': read_block(pnl, 'ACTUAL (USD)'),
            'budget': read_block(pnl, 'BUDGET (USD)'),
            'regions': {}, 'volumes': {}, 'checks': []}

    for row in wb['Regions'].iter_rows(min_row=2, values_only=True):
        data['regions'].setdefault(row[0], {})[row[1]] = list(row[2:2 + N_MONTHS])
    for row in wb['Volumes'].iter_rows(min_row=2, values_only=True):
        data['volumes'][row[0]] = list(row[2:2 + N_MONTHS])

    # Structural checks: never trust a YTD column or a summary tab blindly.
    for block in ('actual', 'budget'):
        for line, v in data[block].items():
            ok = abs(sum(v['months']) - v['ytd']) < 1
            if not ok:
                data['checks'].append(f'{block} {line}: YTD does not equal sum of months')
    reg_rev = [sum(r['Revenue'][i] for r in data['regions'].values()) for i in range(N_MONTHS)]
    if reg_rev != data['actual']['Revenue']['months']:
        data['checks'].append('Regional revenue does not reconcile with P&L revenue')
    return data


# ---------------------------------------------------------------------------
# 2. Charts: raw Arabic straight into matplotlib (no ar()!)
# ---------------------------------------------------------------------------
def save(fig, tmp, name):
    path = tmp / f'{name}.png'
    fig.savefig(path, dpi=180, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return str(path)


def style_axes(ax):
    for side in ('top', 'right'):
        ax.spines[side].set_visible(False)
    ax.grid(axis='y', color='#E5E5E5', zorder=0)
    ax.tick_params(labelsize=8.5)


def chart_revenue(d, pal, tmp):
    b = np.array(d['budget']['Revenue']['months']) / 1e6
    a = np.array(d['actual']['Revenue']['months']) / 1e6
    x, w = np.arange(N_MONTHS), 0.38
    fig, ax = plt.subplots(figsize=(7, 3.1))
    ax.bar(x - w / 2, b, w, label='الموازنة', color='#BDBDBD', zorder=3)
    bars = ax.bar(x + w / 2, a, w, label='الفعلي', color=pal['mid'], zorder=3)
    for bar in bars:
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05,
                f'{bar.get_height():.2f}', ha='center', fontsize=7.5, color=pal['dark'])
    ax.set_xticks(x, A.MONTHS_AR[:N_MONTHS])
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f'{v:.0f}'))
    ax.set_ylabel('مليون دولار', fontsize=9)
    ax.set_title('الإيرادات الشهرية: الفعلي مقابل الموازنة', fontsize=11, color=pal['dark'])
    ax.legend(fontsize=8.5, frameon=False)
    ax.set_ylim(0, max(b.max(), a.max()) * 1.2)
    style_axes(ax)
    return save(fig, tmp, 'revenue')


def chart_margin_vs_volume(margin, volume, pal, tmp):
    x = np.arange(N_MONTHS)
    fig, ax = plt.subplots(figsize=(7, 3.1))
    ax.bar(x, volume, 0.55, color=pal['pale'], edgecolor=pal['light'], zorder=2,
           label='الكميات المباعة (ألف وحدة)')
    ax.set_ylabel('ألف وحدة', fontsize=9)
    ax2 = ax.twinx()
    ax2.plot(x, margin, marker='o', color=pal['dark'], lw=2, zorder=4, label='هامش الربح الإجمالي')
    for xi, m in zip(x, margin):
        ax2.text(xi, m + 0.35, f'{m:.1f}%', ha='center', fontsize=7.5, color=pal['dark'])
    ax2.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f'{v:.0f}%'))
    ax2.set_ylim(min(margin) - 3, max(margin) + 2)
    ax.set_xticks(x, A.MONTHS_AR[:N_MONTHS])
    ax.set_title('الكميات وهامش الربح الإجمالي شهريا', fontsize=11, color=pal['dark'])
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, fontsize=8, frameon=False, ncol=2,
              loc='upper center', bbox_to_anchor=(0.5, -0.1))
    style_axes(ax)
    ax2.spines['top'].set_visible(False)
    return save(fig, tmp, 'margin')


def chart_regions(d, pal, tmp):
    regs = list(d['regions'])
    rev = [sum(d['regions'][r]['Revenue']) / 1e6 for r in regs]
    gp = [sum(d['regions'][r]['Gross profit']) / 1e6 for r in regs]
    y, h = np.arange(len(regs)), 0.38
    fig, ax = plt.subplots(figsize=(7, 2.4))
    ax.barh(y + h / 2, rev, h, color=pal['mid'], label='الإيرادات', zorder=3)
    ax.barh(y - h / 2, gp, h, color=pal['light'], label='إجمالي الربح', zorder=3)
    ax.set_yticks(y, [REGION_AR[r] for r in regs])
    ax.invert_yaxis()   # first region on top, same order as the table
    ax.set_xlabel('مليون دولار', fontsize=9)
    ax.set_title('الإيرادات وإجمالي الربح حسب المنطقة', fontsize=11, color=pal['dark'])
    ax.legend(fontsize=8, frameon=False, loc='lower right')
    for side in ('top', 'right'):
        ax.spines[side].set_visible(False)
    ax.grid(axis='x', color='#E5E5E5', zorder=0)
    return save(fig, tmp, 'regions')


# ---------------------------------------------------------------------------
# 3. Report
# ---------------------------------------------------------------------------
def variance(line, b, a):
    diff = a - b
    pct = diff / abs(b) * 100 if b else None
    favourable = diff <= 0 if line in COST_LINES else diff >= 0
    return diff, pct, (A.GREEN if favourable else A.RED)


def build(d, out_pdf, base_color):
    pal = A.make_palette(base_color)
    S = A.make_styles(pal)
    tmp = Path(tempfile.mkdtemp(prefix='ar_report_'))
    act, bud = d['actual'], d['budget']

    rev_a, rev_b = act['Revenue']['ytd'], bud['Revenue']['ytd']
    gp_a, gp_b = act['Gross profit']['ytd'], bud['Gross profit']['ytd']
    np_a, np_b = act['Net profit']['ytd'], bud['Net profit']['ytd']
    gm_a, gm_b = gp_a / rev_a * 100, gp_b / rev_b * 100
    volume = [sum(v[i] for v in d['volumes'].values()) for i in range(N_MONTHS)]
    margin = [g / r * 100 for g, r in zip(act['Gross profit']['months'], act['Revenue']['months'])]
    r_vm = float(np.corrcoef(volume, margin)[0, 1])
    low = int(np.argmin(volume))
    low_drop = (volume[low] / volume[low - 1] - 1) * 100 if low else 0.0
    recovered = volume[-1] / volume[low - 1] * 100 if low else 100.0

    story = []
    # Cover
    cov = lambda size, color, bold=False: ParagraphStyle(
        'c', fontName=A.FONT_BOLD if bold else A.FONT, fontSize=size,
        leading=size * 1.5, textColor=A.rl(color), alignment=TA_CENTER)
    story += [Spacer(1, 6 * cm),
              Paragraph(A.ar(COMPANY_AR), cov(30, pal['dark'], True)),
              Spacer(1, 10),
              HRFlowable(width='50%', thickness=2.5, color=A.rl(pal['mid']), hAlign='CENTER'),
              Spacer(1, 14),
              Paragraph(A.ar(REPORT_AR), cov(17, pal['mid'])),
              Spacer(1, 8),
              Paragraph(A.ar(f'الفترة {PERIOD_AR}'), cov(12, pal['dark'], True)),
              NextPageTemplate('Body'), PageBreak()]

    # TOC
    toc = A.ArabicTOC()
    toc.levelStyles = [S['TOC0'], S['TOC1']]
    story += [Paragraph(A.ar('جدول المحتويات'), S['H1']), Spacer(1, 8), toc, PageBreak()]

    # 1. Executive summary
    story.append(A.h1('1. الملخص التنفيذي', S))
    story.append(A.kpi_strip([
        ('الإيرادات الفعلية', A.fmt_money(rev_a), None),
        ('هامش الربح الإجمالي', A.fmt_pct(gm_a), None),
        ('صافي الربح', A.fmt_money(np_a), A.GREEN if np_a >= 0 else A.RED),
        ('الكميات المباعة', f'{A.fmt_num(sum(volume))} ألف', None),
    ], S, pal))
    story.append(Spacer(1, 10))
    rev_var = (rev_a / rev_b - 1) * 100
    story.append(A.ArPara(
        f'بلغت الإيرادات الفعلية {A.fmt_money(rev_a)} خلال الفترة {PERIOD_AR}، '
        f'أي {"أعلى" if rev_var >= 0 else "أدنى"} من الموازنة بنسبة {abs(rev_var):.1f}%. '
        f'وسجل هامش الربح الإجمالي {gm_a:.1f}% مقابل {gm_b:.1f}% في الموازنة، '
        f'فيما بلغ صافي الربح {A.fmt_money(np_a)} مقابل {A.fmt_money(np_b)} مخططا.'))
    story.append(A.ArPara(
        f'الحدث الأبرز في الفترة هو تراجع الكميات في شهر {A.MONTHS_AR[low]} بنسبة '
        f'{abs(low_drop):.1f}% عن الشهر السابق، ترافق مع انخفاض هامش الربح إلى '
        f'{margin[low]:.1f}%. وعادت الكميات في {A.MONTHS_AR[N_MONTHS - 1]} إلى '
        f'{recovered:.0f}% من مستواها قبل التراجع.'))

    # 2. Income statement
    story.append(A.h1('2. قائمة الدخل', S))
    story.append(A.h2('الفعلي شهريا', S))
    lines = ['Revenue', 'Cost of goods sold', 'Gross profit', 'Total opex', 'Net profit']
    header = ['البند'] + A.MONTHS_AR[:N_MONTHS] + ['المجموع']
    rows = [[LINE_AR[l]] + [A.fmt_num(v) for v in act[l]['months']] + [A.fmt_num(act[l]['ytd'])]
            for l in lines]
    label_w, total_w = 3.0 * cm, 2.3 * cm
    widths = [label_w] + [(A.CONTENT_W - label_w - total_w) / N_MONTHS] * N_MONTHS + [total_w]
    story.append(A.data_table(header, rows, widths, S, pal, bold_last=True))
    story.append(Spacer(1, 4))
    story.append(A.ArPara('جميع المبالغ بالدولار الأميركي. الأرقام السالبة بين قوسين.',
                          size=8, color=A.GRAY, align='right'))

    story.append(A.h2('الفعلي مقابل الموازنة للفترة', S))
    rows = []
    for l in lines:
        b, a = bud[l]['ytd'], act[l]['ytd']
        diff, pct, col = variance(l, b, a)
        hexcol = col.hexval()[2:]
        rows.append([LINE_AR[l], A.fmt_num(b), A.fmt_num(a),
                     Paragraph(f'<font color="#{hexcol}">{A.ar(A.fmt_num(diff))}</font>', S['TD']),
                     Paragraph(f'<font color="#{hexcol}">{A.ar(A.fmt_pct(pct, signed=True))}</font>', S['TD'])])
    story.append(A.data_table(['البند', 'الموازنة', 'الفعلي', 'الفرق', 'نسبة الفرق'], rows,
                              [4.4 * cm] + [(A.CONTENT_W - 4.4 * cm) / 4] * 4, S, pal, bold_last=True))
    story.append(Spacer(1, 4))
    story.append(A.ArPara('الأخضر لصالح الشركة والأحمر في غير صالحها. في بنود الكلفة، '
                          'الفعلي الأدنى من الموازنة لصالح الشركة.', size=8, color=A.GRAY))

    # 3. Revenue
    story.append(PageBreak())
    story.append(A.h1('3. الإيرادات', S))
    story.append(Image(chart_revenue(d, pal, tmp), width=A.CONTENT_W, height=A.CONTENT_W * 0.45))
    months_above = sum(a >= b for a, b in zip(act['Revenue']['months'], bud['Revenue']['months']))
    above_txt = ('لم تتجاوز الإيرادات الفعلية الموازنة في أي شهر من أشهر الفترة. '
                 if months_above == 0 else
                 f'تجاوزت الإيرادات الفعلية الموازنة في {months_above} من أصل {N_MONTHS} أشهر. ')
    story.append(A.ArPara(
        above_txt +
        f'وأدنى شهر هو {A.MONTHS_AR[low]} بإيرادات {A.fmt_money(act["Revenue"]["months"][low])}.'))

    # 4. Margin and volume
    story.append(A.h1('4. هامش الربح والكميات', S))
    story.append(Image(chart_margin_vs_volume(margin, volume, pal, tmp),
                       width=A.CONTENT_W, height=A.CONTENT_W * 0.5))
    strength = 'قوية' if abs(r_vm) >= 0.7 else 'متوسطة' if abs(r_vm) >= 0.4 else 'ضعيفة'
    direction = 'طردية' if r_vm > 0 else 'عكسية'
    story.append(A.ArPara(
        f'معامل الارتباط (Pearson) بين الكميات المباعة وهامش الربح الإجمالي يبلغ {r_vm:.2f}، '
        f'أي علاقة {direction} {strength}. يعني ذلك أن الهامش يتحرك مع الكميات في هذه الفترة، '
        f'لكنه لا يثبت أن الكميات هي السبب: ستة أشهر عينة صغيرة، وارتفاع كلفة الوحدة في '
        f'{A.MONTHS_AR[low]} قد يفسر الأمرين معا.'))

    # 5. Regions
    story.append(PageBreak())
    story.append(A.h1('5. الأداء حسب المنطقة', S))
    story.append(Image(chart_regions(d, pal, tmp), width=A.CONTENT_W, height=A.CONTENT_W * 0.34))
    rows, tot_rev = [], rev_a
    for reg, v in d['regions'].items():
        r, g = sum(v['Revenue']), sum(v['Gross profit'])
        rows.append([REGION_AR[reg], A.fmt_num(r), A.fmt_num(g), A.fmt_pct(g / r * 100),
                     A.fmt_pct(r / tot_rev * 100)])
    rows.append(['المجموع', A.fmt_num(rev_a), A.fmt_num(gp_a), A.fmt_pct(gm_a), '100.0%'])
    story.append(KeepTogether(A.data_table(
        ['المنطقة', 'الإيرادات', 'إجمالي الربح', 'الهامش', 'الحصة من الإيرادات'], rows,
        [3.6 * cm] + [(A.CONTENT_W - 3.6 * cm) / 4] * 4, S, pal, bold_last=True)))
    story.append(Spacer(1, 6))
    drops = {reg: (v[low] / v[low - 1] - 1) * 100 for reg, v in d['volumes'].items()} if low else {}
    if drops:
        worst = min(drops, key=drops.get)
        story.append(A.ArPara(
            f'المنطقة الأكثر تأثرا بتراجع {A.MONTHS_AR[low]} هي {REGION_AR[worst]} '
            f'بانخفاض كميات {abs(drops[worst]):.1f}%.'))

    # 6. Data notes
    story.append(A.h1('6. ملاحظات البيانات', S))
    notes = [
        'المصدر ملف Excel واحد من ثلاث أوراق: قائمة الدخل (الفعلي وفوقه الموازنة في الورقة نفسها)، المناطق، والكميات.',
        'العملة الدولار الأميركي. الأرقام السالبة بين قوسين.',
        'تم التحقق من أن عمود المجموع يساوي مجموع الأشهر، وأن إيرادات المناطق تطابق إيرادات قائمة الدخل.'
        if not d['checks'] else 'تنبيه: ' + ' · '.join(d['checks']),
    ]
    for n in notes:
        story.append(A.ArPara('· ' + n))

    doc = A.ArabicDoc(str(out_pdf), header_text=f'{REPORT_AR}  ·  {PERIOD_AR}', palette=pal,
                      title=f'{REPORT_AR} · {COMPANY_AR}', author=COMPANY_AR)
    doc.multiBuild(story)
    shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--xlsx', default=ROOT / 'assets' / 'sample_company.xlsx')
    ap.add_argument('--out', default=ROOT / 'assets' / 'sample_report.pdf')
    ap.add_argument('--color', default='#1F4E79', help='brand base colour (hex)')
    args = ap.parse_args()

    A.register_fonts()
    data = extract(args.xlsx)
    json_path = Path(args.out).with_suffix('.json')
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
    build(data, args.out, args.color)
    print(f'Wrote {json_path}\nWrote {args.out}')


if __name__ == '__main__':
    main()
