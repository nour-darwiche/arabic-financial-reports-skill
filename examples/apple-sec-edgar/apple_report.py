"""
Real-data example: Arabic report on Apple Inc.'s published results (SEC EDGAR,
public domain), built only with the skill's arabic_pdf.py.

    python examples/apple-sec-edgar/apple_report.py

What it exercises that the fictional sample does not:
  * Q4 is never filed on its own; it is derived as the annual 10-K figure minus
    the three 10-Q quarters, then checked with the same arithmetic as the others.
  * No budget exists in the source, so every comparison is with the same quarter
    of the previous fiscal year (never an invented target).
  * Latin names and filing codes (Apple Inc., 10-Q) inside Arabic sentences.
  * Every claim ("grew in every quarter") is written only when the data confirms it.
"""
import json, shutil, sys, tempfile
from pathlib import Path

import numpy as np
from openpyxl import load_workbook
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import HRFlowable, Image, NextPageTemplate, PageBreak, Paragraph, Spacer

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'building-arabic-financial-reports' / 'scripts'))
import arabic_pdf as A

QN = ['الربع الأول', 'الربع الثاني', 'الربع الثالث', 'الربع الرابع']
QS = ['ر1', 'ر2', 'ر3', 'ر4']
FYS = [2025, 2026]
LINES = {
    'Revenue': 'الإيرادات', 'Cost of sales': 'كلفة المبيعات', 'Gross margin': 'إجمالي الربح',
    'Research and development': 'البحث والتطوير',
    'Selling, general and administrative': 'المصاريف البيعية والإدارية',
    'Total operating expenses': 'إجمالي المصاريف التشغيلية',
    'Operating income': 'الدخل التشغيلي', 'Net income': 'صافي الدخل',
}


# ---------------------------------------------------------------------------
# Extraction: quarterly sheet + annual sheet -> 8 full quarters, validated
# ---------------------------------------------------------------------------
def extract(xlsx):
    wb = load_workbook(xlsx, data_only=True)
    q = {r[0]: list(r[1:]) for r in wb['Quarterly 10-Q'].iter_rows(min_row=4, values_only=True)}
    a = {r[0]: list(r[1:]) for r in wb['Annual 10-K'].iter_rows(min_row=4, values_only=True)}
    data, checks = {}, []
    for j, fy in enumerate(FYS):
        for k in q:
            reported = q[k][3 * j:3 * j + 3]
            data.setdefault(k, {})[fy] = reported + [a[k][j] - sum(reported)]   # Q4 = FY minus Q1..Q3
    for fy in FYS:
        for i in range(4):
            g = lambda k: data[k][fy][i]
            if g('Revenue') - g('Cost of sales') != g('Gross margin'):
                checks.append(f'FY{fy} Q{i+1}: gross margin mismatch')
            if g('Research and development') + g('Selling, general and administrative') != g('Total operating expenses'):
                checks.append(f'FY{fy} Q{i+1}: opex mismatch')
            if g('Gross margin') - g('Total operating expenses') != g('Operating income'):
                checks.append(f'FY{fy} Q{i+1}: operating income mismatch')
    return {'quarters': data, 'annual': {k: dict(zip(FYS, v)) for k, v in a.items()}, 'checks': checks}


def yoy(new, old):
    return (new / old - 1) * 100


# ---------------------------------------------------------------------------
# Charts (raw Arabic into matplotlib)
# ---------------------------------------------------------------------------
def _axes(ax):
    for s in ('top', 'right'):
        ax.spines[s].set_visible(False)
    ax.grid(axis='y', color='#E5E5E5', zorder=0)
    ax.tick_params(labelsize=8.5)


def save(fig, tmp, name):
    p = tmp / f'{name}.png'
    fig.savefig(p, dpi=180, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return str(p)


def chart_revenue(Q, pal, tmp):
    x, w = np.arange(4), 0.38
    old = np.array(Q['Revenue'][2025]) / 1000
    new = np.array(Q['Revenue'][2026]) / 1000
    fig, ax = plt.subplots(figsize=(7, 3.1))
    ax.bar(x - w / 2, old, w, color='#BDBDBD', label='السنة المالية 2025', zorder=3)
    bars = ax.bar(x + w / 2, new, w, color=pal['mid'], label='السنة المالية 2026', zorder=3)
    for b, o in zip(bars, old):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 2, f'+{(b.get_height() / o - 1) * 100:.1f}%',
                ha='center', fontsize=7.5, color=pal['dark'])
    ax.set_xticks(x, QN)
    ax.set_ylabel('مليار دولار', fontsize=9)
    ax.set_title('الإيرادات الفصلية مقارنة بالفصل نفسه من السنة السابقة', fontsize=11, color=pal['dark'])
    ax.legend(fontsize=8.5, frameon=False)
    ax.set_ylim(0, new.max() * 1.18)
    _axes(ax)
    return save(fig, tmp, 'rev')


def chart_margins(Q, pal, tmp):
    labels, gm, om = [], [], []
    for fy in FYS:
        for i in range(4):
            r = Q['Revenue'][fy][i]
            labels.append(f'{QS[i]}\n{fy}')
            gm.append(Q['Gross margin'][fy][i] / r * 100)
            om.append(Q['Operating income'][fy][i] / r * 100)
    x = np.arange(8)
    fig, ax = plt.subplots(figsize=(7, 3.1))
    ax.plot(x, gm, marker='o', lw=2, color=pal['dark'], label='هامش الربح الإجمالي', zorder=3)
    ax.plot(x, om, marker='s', lw=2, color=pal['light'], label='الهامش التشغيلي', zorder=3)
    for xi, g, o in zip(x, gm, om):
        ax.text(xi, g + 0.8, f'{g:.1f}%', ha='center', fontsize=7, color=pal['dark'])
        ax.text(xi, o - 2.2, f'{o:.1f}%', ha='center', fontsize=7, color=pal['mid'])
    ax.axvline(3.5, color='#CCCCCC', lw=1, ls='--')
    ax.set_xticks(x, labels)
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f'{v:.0f}%'))
    ax.set_ylim(20, 54)
    ax.set_title('الهوامش الفصلية خلال ثمانية فصول', fontsize=11, color=pal['dark'])
    ax.legend(fontsize=8.5, frameon=False, ncol=2, loc='upper center', bbox_to_anchor=(0.5, -0.2))
    _axes(ax)
    return save(fig, tmp, 'margins')


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def build(d, out_pdf):
    pal = A.make_palette('#2B3A55')
    S = A.make_styles(pal)
    tmp = Path(tempfile.mkdtemp(prefix='aapl_ar_'))
    Q, Y = d['quarters'], d['annual']
    f = lambda k, fy=2026: Y[k][fy]
    rev_g = yoy(f('Revenue'), f('Revenue', 2025))
    ni_g = yoy(f('Net income'), f('Net income', 2025))
    gm26, gm25 = f('Gross margin') / f('Revenue') * 100, f('Gross margin', 2025) / f('Revenue', 2025) * 100
    om26, om25 = f('Operating income') / f('Revenue') * 100, f('Operating income', 2025) / f('Revenue', 2025) * 100
    rd_g = yoy(f('Research and development'), f('Research and development', 2025))
    sga_g = yoy(f('Selling, general and administrative'), f('Selling, general and administrative', 2025))
    opex_g = yoy(f('Total operating expenses'), f('Total operating expenses', 2025))
    oi_g = yoy(f('Operating income'), f('Operating income', 2025))
    q_rev_g = [yoy(Q['Revenue'][2026][i], Q['Revenue'][2025][i]) for i in range(4)]
    best_q = int(np.argmax(q_rev_g))
    q1_share = Q['Revenue'][2026][0] / f('Revenue') * 100
    q1_biggest = all(Q['Revenue'][fy][0] == max(Q['Revenue'][fy]) for fy in FYS)
    gm_q = {fy: [Q['Gross margin'][fy][i] / Q['Revenue'][fy][i] for i in range(4)] for fy in FYS}
    gm_up_n = sum(gm_q[2026][i] > gm_q[2025][i] for i in range(4))
    gm_up_all = gm_up_n == 4
    period = 'السنة المالية 2026 (من 28 أيلول 2025 حتى 26 أيلول 2026)'

    cov = lambda size, color, bold=False: ParagraphStyle(
        'c', fontName=A.FONT_BOLD if bold else A.FONT, fontSize=size, leading=size * 1.5,
        textColor=A.rl(color), alignment=TA_CENTER)
    story = [Spacer(1, 6 * cm), Paragraph(A.ar('شركة Apple Inc.'), cov(30, pal['dark'], True)), Spacer(1, 10),
             HRFlowable(width='50%', thickness=2.5, color=A.rl(pal['mid']), hAlign='CENTER'), Spacer(1, 14),
             Paragraph(A.ar('قراءة في النتائج المالية الفصلية'), cov(17, pal['mid'])), Spacer(1, 8),
             Paragraph(A.ar(period), cov(11.5, pal['dark'], True)),
             NextPageTemplate('Body'), PageBreak()]
    toc = A.ArabicTOC(); toc.levelStyles = [S['TOC0'], S['TOC1']]
    story += [Paragraph(A.ar('جدول المحتويات'), S['H1']), Spacer(1, 8), toc, PageBreak()]

    # 1
    story.append(A.h1('1. الملخص التنفيذي', S))
    story.append(A.kpi_strip([
        ('الإيرادات (مليون دولار)', A.fmt_num(f('Revenue')), None),
        ('هامش الربح الإجمالي', A.fmt_pct(gm26), None),
        ('الهامش التشغيلي', A.fmt_pct(om26), None),
        ('صافي الدخل (مليون دولار)', A.fmt_num(f('Net income')), None),
    ], S, pal))
    story.append(Spacer(1, 10))
    story.append(A.ArPara(
        f'نمت إيرادات السنة المالية 2026 بنسبة {rev_g:.1f}% لتبلغ {A.fmt_num(f("Revenue"))} مليون دولار، '
        f'ونما صافي الدخل بنسبة {ni_g:.1f}% إلى {A.fmt_num(f("Net income"))} مليون دولار. '
        f'ارتفع هامش الربح الإجمالي من {gm25:.1f}% إلى {gm26:.1f}%، وارتفع الهامش التشغيلي من '
        f'{om25:.1f}% إلى {om26:.1f}%.'))
    if ni_g > rev_g and gm26 > gm25 and opex_g > rev_g:
        story.append(A.ArPara(
            f'نمو صافي الدخل أسرع من نمو الإيرادات، والسبب الرئيسي في الأرقام هو تحسن هامش الربح الإجمالي، '
            f'وليس ضبط المصاريف: المصاريف التشغيلية نمت بنسبة {opex_g:.1f}%، أي أسرع من الإيرادات، '
            f'بقيادة البحث والتطوير الذي ارتفع {rd_g:.1f}%.'))

    # 2
    story.append(A.h1('2. قائمة الدخل الفصلية', S))
    for fy in FYS:
        story.append(A.h2(f'السنة المالية {fy}', S))
        keys = ['Revenue', 'Cost of sales', 'Gross margin', 'Research and development',
                'Selling, general and administrative', 'Operating income', 'Net income']
        rows = [[LINES[k]] + [A.fmt_num(v) for v in Q[k][fy]] + [A.fmt_num(Y[k][fy])] for k in keys]
        lw, tw = 4.2 * cm, 2.4 * cm
        widths = [lw] + [(A.CONTENT_W - lw - tw) / 4] * 4 + [tw]
        story.append(A.data_table(['البند'] + QN + ['السنة'], rows, widths, S, pal, bold_last=True))
        story.append(Spacer(1, 4))
    story.append(A.ArPara('بملايين الدولارات. الربع الرابع غير منشور منفردا، وقد احتسب بطرح الأرباع الثلاثة '
                          'الأولى من الأرقام السنوية.', size=8, color=A.GRAY))

    # 3
    story.append(PageBreak())
    story.append(A.h1('3. نمو الإيرادات فصلا بفصل', S))
    story.append(Image(chart_revenue(Q, pal, tmp), width=A.CONTENT_W, height=A.CONTENT_W * 0.45))
    story.append(A.ArPara(
        (f'نمت الإيرادات في كل فصل من فصول السنة مقارنة بالفصل نفسه من السنة السابقة، وأعلى نمو كان في '
         if all(g > 0 for g in q_rev_g) else
         f'نمت الإيرادات في {sum(g > 0 for g in q_rev_g)} من أصل 4 فصول مقارنة بالفصل نفسه من السنة السابقة، وأعلى نمو كان في ')+
        f'{QN[best_q]} بنسبة {q_rev_g[best_q]:.1f}%. '
        + (f'الربع الأول هو الأكبر في السنتين لأنه يشمل موسم الأعياد، وقد شكل {q1_share:.1f}% من إيرادات '
           f'السنة، لذلك لا تصح مقارنة فصل بالفصل الذي يليه، والمقارنة الصحيحة هي بالفصل نفسه من السنة السابقة.'
           if q1_biggest else '')))

    # 4
    story.append(A.h1('4. الهوامش', S))
    story.append(Image(chart_margins(Q, pal, tmp), width=A.CONTENT_W, height=A.CONTENT_W * 0.5))
    gms = [Q['Gross margin'][fy][i] / Q['Revenue'][fy][i] * 100 for fy in FYS for i in range(4)]
    story.append(A.ArPara(
        f'تراوح هامش الربح الإجمالي بين {min(gms):.1f}% و{max(gms):.1f}% خلال الفصول الثمانية، '
        + (f'وكان أعلى في كل فصل من السنة المالية 2026 منه في الفصل المقابل من 2025. ' if gm_up_all else
           f'وكان أعلى في {gm_up_n} من أصل 4 فصول في السنة المالية 2026 مقارنة بالفصل المقابل من 2025. ')
        + 
        f'البيانات المتاحة لا تفصل بين المنتجات والخدمات، لذلك لا يمكن من هذه الأرقام وحدها تحديد '
        f'ما إذا كان التحسن ناتجا عن تغير مزيج المبيعات أم عن تكاليف أقل.'))

    # 5
    story.append(PageBreak())
    story.append(A.h1('5. المصاريف التشغيلية', S))
    rows = []
    for k in ['Research and development', 'Selling, general and administrative', 'Total operating expenses']:
        o, n = Y[k][2025], Y[k][2026]
        rows.append([LINES[k], A.fmt_num(o), A.fmt_num(n), A.fmt_pct(yoy(n, o), signed=True),
                     A.fmt_pct(n / f('Revenue') * 100)])
    story.append(A.data_table(['البند', 'السنة المالية 2025', 'السنة المالية 2026', 'النمو', 'نسبة من الإيرادات 2026'],
                              rows, [4.6 * cm] + [(A.CONTENT_W - 4.6 * cm) / 4] * 4, S, pal, bold_last=True))
    story.append(Spacer(1, 8))
    rd25 = f('Research and development', 2025) / f('Revenue', 2025) * 100
    rd26 = f('Research and development') / f('Revenue') * 100
    story.append(A.ArPara(
        f'ارتفعت حصة البحث والتطوير من الإيرادات من {rd25:.1f}% إلى {rd26:.1f}%، بينما نمت المصاريف البيعية '
        f'والإدارية بنسبة {sga_g:.1f}% فقط. ورغم أن المصاريف التشغيلية نمت أسرع من الإيرادات، نما الدخل '
        f'التشغيلي بنسبة {oi_g:.1f}% لأن الزيادة في إجمالي الربح فاقت الزيادة في المصاريف.'))

    # 6
    story.append(A.h1('6. ملاحظات البيانات', S))
    notes = [
        'المصدر: قاعدة بيانات SEC EDGAR العامة (تقارير 10-Q الفصلية و10-K السنوية)، تم التنزيل في 25 تشرين الثاني 2026.',
        'تنتهي السنة المالية في آخر سبت من شهر أيلول.',
        'الربع الرابع محتسب: الرقم السنوي ناقص مجموع الأرباع الثلاثة الأولى.',
        'لا توجد موازنة في المصدر، لذلك كل المقارنات مع الفترة نفسها من السنة السابقة.',
        'تم التحقق في كل فصل من أن إجمالي الربح يساوي الإيرادات ناقص كلفة المبيعات، وأن المصاريف التشغيلية '
        'تساوي مجموع بنديها، وأن الدخل التشغيلي يساوي إجمالي الربح ناقص المصاريف التشغيلية.'
        if not d['checks'] else 'تنبيه: ' + ' · '.join(d['checks']),
    ]
    for n in notes:
        story.append(A.ArPara('· ' + n))

    doc = A.ArabicDoc(str(out_pdf), header_text='Apple Inc.  ·  قراءة في النتائج الفصلية للسنة المالية 2026',
                      palette=pal, title='Apple Inc. قراءة في النتائج الفصلية', author='Apple Inc.')
    doc.multiBuild(story)
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    A.register_fonts()
    data = extract(HERE / 'apple_financials.xlsx')
    (HERE / 'apple_data.json').write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
    build(data, HERE / 'Apple_report_AR.pdf')
    print('checks:', data['checks'] or 'all passed')
