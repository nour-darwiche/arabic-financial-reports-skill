"""
Writes assets/sample_company.xlsx: six months of FICTIONAL figures for a
made-up distributor, "Horizon Distribution Co." (شركة الأفق للتوزيع).
No real company, person or location is represented.

Layout mirrors what real finance workbooks look like, including the traps the
skill warns about:
  * 'P&L' holds Actual on top and Budget in a second block lower on the same
    sheet (easy to miss on a first pass).
  * A YTD column that should equal the sum of the months (check it).
  * 'Regions' and 'Volumes' tabs that must reconcile with the P&L.
"""
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font

OUT = Path(__file__).resolve().parent.parent / 'assets' / 'sample_company.xlsx'
MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun']

# Units sold (thousands) per region. March has a supply disruption.
UNITS = {
    'North':  [118, 122, 81, 104, 121, 128],
    'Centre': [205, 211, 150, 188, 214, 226],
    'South':  [92, 95, 70, 80, 90, 99],
}
PRICE = [10.0, 10.1, 10.4, 10.3, 10.2, 10.2]       # $ per unit
UNIT_COST = [8.05, 8.02, 8.75, 8.45, 8.31, 8.12]   # $ per unit
# Regional price and cost multipliers, so regions differ in margin.
REGION_PRICE = {'North': 1.00, 'Centre': 0.97, 'South': 1.06}
REGION_COST = {'North': 1.00, 'Centre': 0.985, 'South': 1.01}
FIXED_OPEX = {'Salaries': 260_000, 'Rent': 95_000, 'Utilities': 38_000, 'Other': 41_000}

BUDGET_UNITS = [420, 430, 440, 445, 450, 460]
BUDGET_PRICE = 10.1
BUDGET_COST = 8.15


def region_lines(reg):
    units = UNITS[reg]
    rev = [round(u * 1000 * p * REGION_PRICE[reg]) for u, p in zip(units, PRICE)]
    cogs = [round(u * 1000 * c * REGION_COST[reg]) for u, c in zip(units, UNIT_COST)]
    return rev, cogs


def pnl_rows(rev, cogs):
    gp = [r - c for r, c in zip(rev, cogs)]
    opex = {k: [v] * 6 for k, v in FIXED_OPEX.items()}
    opex_total = [sum(v[i] for v in opex.values()) for i in range(6)]
    net = [g - o for g, o in zip(gp, opex_total)]
    rows = [('Revenue', rev), ('Cost of goods sold', cogs), ('Gross profit', gp)]
    rows += [(f'Opex: {k}', v) for k, v in opex.items()]
    rows += [('Total opex', opex_total), ('Net profit', net)]
    return rows


def write_block(ws, start_row, title, rows):
    ws.cell(start_row, 1, title).font = Font(bold=True)
    ws.cell(start_row + 1, 1, 'Line item').font = Font(bold=True)
    for j, m in enumerate(MONTHS + ['YTD']):
        ws.cell(start_row + 1, 2 + j, m).font = Font(bold=True)
    for i, (label, vals) in enumerate(rows):
        r = start_row + 2 + i
        ws.cell(r, 1, label)
        for j, v in enumerate(vals):
            ws.cell(r, 2 + j, v)
        ws.cell(r, 8, sum(vals))
    return start_row + 2 + len(rows)


def main():
    wb = Workbook()
    ws = wb.active
    ws.title = 'P&L'
    per_region = {reg: region_lines(reg) for reg in UNITS}
    rev = [sum(per_region[r][0][i] for r in UNITS) for i in range(6)]
    cogs = [sum(per_region[r][1][i] for r in UNITS) for i in range(6)]
    end = write_block(ws, 1, 'ACTUAL (USD)', pnl_rows(rev, cogs))
    b_rev = [round(u * 1000 * BUDGET_PRICE) for u in BUDGET_UNITS]
    b_cogs = [round(u * 1000 * BUDGET_COST) for u in BUDGET_UNITS]
    write_block(ws, end + 3, 'BUDGET (USD)', pnl_rows(b_rev, b_cogs))
    ws.column_dimensions['A'].width = 24

    wr = wb.create_sheet('Regions')
    wr.append(['Region', 'Metric'] + MONTHS)
    for reg, (r_rev, r_cogs) in per_region.items():
        wr.append([reg, 'Revenue'] + r_rev)
        wr.append([reg, 'Gross profit'] + [r - c for r, c in zip(r_rev, r_cogs)])

    wv = wb.create_sheet('Volumes')
    wv.append(['Region', 'Unit'] + MONTHS)
    for reg, units in UNITS.items():
        wv.append([reg, 'thousand units'] + units)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT)
    print(f'Wrote {OUT}')


if __name__ == '__main__':
    main()
