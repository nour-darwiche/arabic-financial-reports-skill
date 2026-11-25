"""
Regression tests for arabic_pdf.ar(): symbols, signs and Latin text must stay on
the correct side in the visual (left-to-right, as drawn) output.

    python scripts/test_bidi.py

Arabic is compared after shaping, so expected values are built with the same
reshaper and only the placement of the non-Arabic parts is asserted.
"""
import arabic_reshaper
import arabic_pdf as A


def shaped(word):
    """Visual form of a single Arabic word (shaped, letters reversed)."""
    return arabic_reshaper.reshape(word)[::-1]


ALONE = {                      # strings without Arabic stay left-to-right
    '+32.5%': '+32.5%', '(8.7%)': '(8.7%)', '19.0%': '19.0%',
    '24,390,400': '24,390,400', '$2,038,340': '$2,038,340',
    '(1,234)': '(1,234)', '($515,410)': '($515,410)', '10-Q': '10-Q',
}

IN_ARABIC = [                  # (logical text, visual fragment that must appear)
    ('بنسبة 15.1% لتبلغ', '15.1%'),
    ('بلغت $24,390,400 خلال', '$24,390,400'),
    ('نمو +32.5% هذا', '+32.5%'),
    ('خسارة (1,234) دولار', '(1,234)'),
    ('تقارير 10-Q الفصلية', '10-Q'),
    ('شركة Apple Inc.', 'Apple Inc.'),
]

ORDER = [                      # (logical text, expected full visual output)
    # sentence period goes to the far left (end of an RTL line)
    ('بنسبة 8.7%.', '.8.7% ' + shaped('بنسبة')),
    # a line that starts with a Latin name is still right-to-left
    ('Apple Inc. · تقرير', shaped('تقرير') + ' · Apple Inc.'),
]


def main():
    failures = 0
    for text, exp in ALONE.items():
        out = A.ar(text)
        if out != exp:
            failures += 1
            print(f'FAIL alone {text!r}: got {out!r}, want {exp!r}')
    for text, frag in IN_ARABIC:
        out = A.ar(text)
        if frag not in out:
            failures += 1
            print(f'FAIL in-sentence {text!r}: {frag!r} not in {out!r}')
    for text, exp in ORDER:
        out = A.ar(text)
        if out != exp:
            failures += 1
            print(f'FAIL order {text!r}: got {out!r}, want {exp!r}')
    total = len(ALONE) + len(IN_ARABIC) + len(ORDER)
    print(f'{total - failures}/{total} passed')
    raise SystemExit(1 if failures else 0)


if __name__ == '__main__':
    main()
