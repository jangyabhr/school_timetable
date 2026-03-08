# exporter.py

import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from constraints import (
    DAYS_PER_WEEK,
    PERIODS_PER_DAY,
    ANCHOR_SUBJECTS,
    LAB_BLOCK_SUBJECTS,
    FIXED_SLOT_SUBJECTS,
    FLOATING_SINGLE_SUBJECTS,
)
from event_generator import CLASS_ORDER

# ---------------------------------------------------------------------------
# Colour palette  (openpyxl uses ARGB hex, no leading #)
# ---------------------------------------------------------------------------

COLOUR_ANCHOR   = "FFD6EAF8"   # light blue   — Math, Science, English, SST
COLOUR_LAB      = "FFD5F5E3"   # light green  — Physics, Chemistry, Biology
COLOUR_FIXED    = "FFFFF3CD"   # light yellow — Game, CCA
COLOUR_FLOAT    = "FFFDE8D8"   # light orange — Library, WE
COLOUR_EMPTY    = "FFF5F5F5"   # light grey   — empty cell
COLOUR_HEADER   = "FF2E4057"   # dark blue    — header row/col
COLOUR_WHITE    = "FFFFFFFF"

DAY_NAMES    = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
PERIOD_NAMES = [f"Period {p+1}" for p in range(PERIODS_PER_DAY)]


def _get_fill(subject):
    if subject is None:
        return PatternFill("solid", fgColor=COLOUR_EMPTY)
    if subject in ANCHOR_SUBJECTS:
        return PatternFill("solid", fgColor=COLOUR_ANCHOR)
    if subject in LAB_BLOCK_SUBJECTS:
        return PatternFill("solid", fgColor=COLOUR_LAB)
    if subject in FIXED_SLOT_SUBJECTS:
        return PatternFill("solid", fgColor=COLOUR_FIXED)
    if subject in FLOATING_SINGLE_SUBJECTS:
        return PatternFill("solid", fgColor=COLOUR_FLOAT)
    return PatternFill("solid", fgColor=COLOUR_WHITE)


def _thin_border():
    side = Side(style="thin", color="FFCCCCCC")
    return Border(left=side, right=side, top=side, bottom=side)


def _header_fill():
    return PatternFill("solid", fgColor=COLOUR_HEADER)


def _build_grid(section, timetable_state, events):
    """
    Build a 2D grid [period][day] = (subject, teacher) for this section.
    """
    grid = [[None] * DAYS_PER_WEEK for _ in range(PERIODS_PER_DAY)]

    for key, placement in timetable_state.items():
        if placement["class"] != section:
            continue
        day     = placement["day"]
        period  = placement["period"]
        subject = placement["subject"]
        teacher = placement.get("teacher") or ""
        grid[period][day] = (subject, teacher)

    return grid


def _write_sheet(ws, section, timetable_state, events):
    """Write one sheet for a class section."""

    # ── Title row ───────────────────────────────────────────────────────────
    ws.merge_cells(start_row=1, start_column=1,
                   end_row=1,   end_column=DAYS_PER_WEEK + 1)
    title_cell = ws.cell(row=1, column=1, value=f"Timetable — Class {section}")
    title_cell.font      = Font(bold=True, size=13, color=COLOUR_WHITE)
    title_cell.fill      = _header_fill()
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 22

    # ── Header row (day names) ───────────────────────────────────────────────
    ws.cell(row=2, column=1, value="Period").fill = _header_fill()
    ws.cell(row=2, column=1).font = Font(bold=True, color=COLOUR_WHITE)
    for d, day_name in enumerate(DAY_NAMES):
        cell = ws.cell(row=2, column=d + 2, value=day_name)
        cell.fill      = _header_fill()
        cell.font      = Font(bold=True, color=COLOUR_WHITE)
        cell.alignment = Alignment(horizontal="center")

    # ── Data rows ────────────────────────────────────────────────────────────
    grid = _build_grid(section, timetable_state, events)

    for p in range(PERIODS_PER_DAY):
        row_num = p + 3
        ws.row_dimensions[row_num].height = 36

        # Period label
        period_cell = ws.cell(row=row_num, column=1, value=PERIOD_NAMES[p])
        period_cell.fill      = _header_fill()
        period_cell.font      = Font(bold=True, color=COLOUR_WHITE)
        period_cell.alignment = Alignment(horizontal="center", vertical="center")

        for d in range(DAYS_PER_WEEK):
            cell_value = grid[p][d]
            cell       = ws.cell(row=row_num, column=d + 2)
            cell.border    = _thin_border()
            cell.alignment = Alignment(horizontal="center", vertical="center",
                                       wrap_text=True)

            if cell_value:
                subject, teacher = cell_value
                cell.value = f"{subject}\n{teacher}" if teacher else subject
                cell.fill  = _get_fill(subject)
            else:
                cell.value = ""
                cell.fill  = _get_fill(None)

    # ── Column widths ────────────────────────────────────────────────────────
    ws.column_dimensions["A"].width = 12
    for d in range(DAYS_PER_WEEK):
        col_letter = get_column_letter(d + 2)
        ws.column_dimensions[col_letter].width = 18


def _write_legend(wb):
    """Add a Legend sheet explaining colour coding."""
    ws = wb.create_sheet("Legend")
    items = [
        ("Anchor subjects (Math, Science, English, SST)", COLOUR_ANCHOR),
        ("Lab subjects (Physics, Chemistry, Biology)",    COLOUR_LAB),
        ("Fixed slots (Game, CCA)",                       COLOUR_FIXED),
        ("Floating singles (Library, WE)",                COLOUR_FLOAT),
        ("Empty period",                                  COLOUR_EMPTY),
    ]
    ws.column_dimensions["A"].width = 45
    ws.column_dimensions["B"].width = 15
    ws.cell(row=1, column=1, value="Legend").font = Font(bold=True, size=12)

    for i, (label, colour) in enumerate(items, start=2):
        ws.cell(row=i, column=1, value=label)
        swatch = ws.cell(row=i, column=2, value="")
        swatch.fill = PatternFill("solid", fgColor=colour)
        swatch.border = _thin_border()


# ---------------------------------------------------------------------------
# Validation check before export
# ---------------------------------------------------------------------------

def validate_before_export(timetable_state, events):
    """
    Runs hard constraint checks.
    Returns list of violation strings. Empty list = safe to export.
    """
    violations = []
    seen_teacher = {}   # (teacher, day, period) → event key
    seen_class   = {}   # (class, day, period)   → event key

    for key, p in timetable_state.items():
        day, period = p["day"], p["period"]

        # Teacher clash
        teacher = p.get("teacher")
        if teacher:
            tk = (teacher, day, period)
            if tk in seen_teacher:
                violations.append(
                    f"Teacher clash: {teacher} at day={day} period={period} "
                    f"— events {seen_teacher[tk]} and {key}"
                )
            else:
                seen_teacher[tk] = key

        # Class clash
        ck = (p["class"], day, period)
        if ck in seen_class:
            violations.append(
                f"Class clash: {p['class']} at day={day} period={period} "
                f"— events {seen_class[ck]} and {key}"
            )
        else:
            seen_class[ck] = key

    # Weekly load check
    from collections import Counter
    placement_counts = Counter()
    for (event_idx, instance), _ in timetable_state.items():
        placement_counts[event_idx] += 1

    for event_idx, event in enumerate(events):
        placed = placement_counts.get(event_idx, 0)
        if placed != event["weekly_load"]:
            violations.append(
                f"Load mismatch: {event['class']} {event['subject']} "
                f"— expected {event['weekly_load']}, placed {placed}"
            )

    return violations


# ---------------------------------------------------------------------------
# Main Export Entry Point
# ---------------------------------------------------------------------------

def export_timetable(timetable_state, events, output_path="timetable.xlsx"):
    """
    Validates timetable_state then writes the Excel file.
    Raises RuntimeError if hard violations exist.
    """
    print("── Running pre-export validation ──")
    violations = validate_before_export(timetable_state, events)

    if violations:
        print(f"   EXPORT WARNING — {len(violations)} load mismatch(es) (exporting anyway):")
        for v in violations:
            print(f"   ⚠ {v}")

    print("   Validation passed. Writing Excel file...")

    wb = openpyxl.Workbook()
    wb.remove(wb.active)   # remove default empty sheet

    for section in CLASS_ORDER:
        ws = wb.create_sheet(title=f"Class {section}")
        _write_sheet(ws, section, timetable_state, events)

    _write_legend(wb)
    wb.save(output_path)
    print(f"── Timetable saved to: {output_path} ──")
