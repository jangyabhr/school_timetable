"""
xlsx_to_html.py
Reads 'final timetable for april 2026 (1).xlsx' and regenerates Timetable_Tools.html.

The All Sections sheet has class blocks stacked vertically:
  Row 0: 'ACADEMIC SESSION 2026-27'   (skip)
  Row 1: 'Timetable — Class X'        (class name)
  Row 2: header                        (skip)
  Row 3-8: Mon-Sat data
    col 0: day name
    col 1: None (merged)
    col 2: P1 content
    col 3: P2 content
    col 4: None (merged)
    col 5: P3 content
    col 6: P4 content
  Row 9: empty (separator)
Each block = 10 rows.
"""

import re
import openpyxl
from html_exporter import generate_html

FNAME = 'final timetable for april 2026 (1).xlsx'
OUT   = 'timetable tool from excel.html'

# Columns in the sheet that correspond to P1, P2, P3, P4 (0-indexed)
PERIOD_COLS = [2, 3, 5, 6]

# Subject names that should never appear as teacher names (xlsx data errors)
_SUBJECTS = {'Biology','Math','Science','English','SST','Hindi','Odia',
             'Sanskrit','CS','IT','Physics','Chemistry','Free','Library'}

def _normalise_teacher(name: str) -> str:
    """Normalise inconsistent teacher name spellings from the xlsx."""
    if not name or name in _SUBJECTS:
        return ''
    # Normalise apostrophe variants → "ma'am"
    # covers: maam, m'am, M'am, Ma'am, ma'am, mam
    name = re.sub(r"\bma['']?am\b|\bm['']am\b|\bmaam\b|\bmam\b", "ma'am",
                  name, flags=re.IGNORECASE)
    name = re.sub(r"\bsir\b", "sir", name, flags=re.IGNORECASE)
    # Collapse multiple spaces
    return ' '.join(name.split())

wb = openpyxl.load_workbook(FNAME)
ws = wb['All Sections']
rows = list(ws.iter_rows(values_only=True))

timetable_state = {}
idx = 0

i = 0
while i < len(rows):
    row = rows[i]
    # Detect class header: 'Timetable — Class X'
    if row[0] and str(row[0]).startswith('Timetable — Class '):
        cls = str(row[0]).replace('Timetable — Class ', '').strip()
        # row i+1 = column headers (skip)
        # rows i+2 .. i+7 = Mon..Sat
        for day_offset in range(6):
            data_row_idx = i + 2 + day_offset
            if data_row_idx >= len(rows):
                break
            data_row = rows[data_row_idx]
            if not data_row[0]:
                break  # hit empty row early
            for period_int, col_idx in enumerate(PERIOD_COLS):
                cell = data_row[col_idx] if col_idx < len(data_row) else None
                if not cell:
                    continue
                raw = str(cell).strip()
                if not raw:
                    continue
                parts = raw.split('\n', 1)
                subject_raw = parts[0].strip()
                teacher     = _normalise_teacher(parts[1].strip() if len(parts) > 1 else '')
                is_lab      = '(Lab)' in subject_raw or '(lab)' in subject_raw
                subject     = subject_raw.replace('(Lab)', '').replace('(lab)', '').strip()
                if not subject:
                    continue
                timetable_state[idx] = {
                    'class':   cls,
                    'day':     day_offset,   # 0=Mon .. 5=Sat
                    'period':  period_int,   # 0=P1 .. 3=P4
                    'subject': subject,
                    'teacher': teacher,
                    'is_lab':  is_lab,
                }
                idx += 1
        i += 9  # skip to next block
        continue
    i += 1

print(f"Parsed {idx} slots from {FNAME}")
generate_html(timetable_state, events=None, output_path=OUT)
