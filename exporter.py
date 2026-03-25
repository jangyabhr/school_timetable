# exporter.py

import openpyxl
from collections import defaultdict, Counter
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from constraints import (
    DAYS_PER_WEEK,
    PERIODS_PER_DAY,
)
from event_generator import CLASS_ORDER

# ---------------------------------------------------------------------------
# Colour palette  (openpyxl uses ARGB hex, no leading #)
# ---------------------------------------------------------------------------

COLOUR_FREE     = "FFD5D8DC"   # light grey-blue — Free (duty) periods

# Per-subject pastel palette (Material-Design-inspired, one colour per subject)
SUBJECT_COLOURS = {
    "Math":      "FFBBDEFB",  # pastel blue
    "English":   "FFB2EBF2",  # pastel cyan
    "Science":   "FFC8E6C9",  # pastel green
    "SST":       "FFFFF9C4",  # pastel yellow
    "Hindi":     "FFFFE0B2",  # pastel amber
    "Odia":      "FFFCE4EC",  # pastel pink
    "Sanskrit":  "FFE8EAF6",  # pastel indigo
    "CS":        "FFE0F2F1",  # pastel teal
    "IT":        "FFF3E5F5",  # pastel purple
    "Physics":   "FFE1F5FE",  # pastel light-blue
    "Chemistry": "FFFBE9E7",  # pastel deep-orange
    "Biology":   "FFE8F5E9",  # pastel light-green
    "Game":      "FFFFF3E0",  # pastel orange
    "CCA":       "FFEDE7F6",  # pastel deep-purple
    "Library":   "FFF9FBE7",  # pastel lime
    "WE":        "FFECE4D6",  # pastel warm-tan
}
COLOUR_EMPTY    = "FFF5F5F5"   # light grey   — empty cell
COLOUR_HEADER   = "FF2E4057"   # dark blue    — header row/col
COLOUR_SUBHEAD  = "FF4A6FA5"   # medium blue  — sub-headers
COLOUR_WHITE    = "FFFFFFFF"
COLOUR_DASH_H   = "FF1B2631"   # near-black   — dashboard section headers

# Per-section pastel palette (used on teacher-wise sheets to colour by class)
SECTION_COLOURS = {
    "6A":  "FFFADADD",   # rose
    "6B":  "FFFDE8D8",   # peach
    "7A":  "FFD5F5E3",   # mint
    "7B":  "FFD6EAF8",   # sky blue
    "8A":  "FFFFF3CD",   # pale yellow
    "8B":  "FFE8DAEF",   # lavender
    "9A":  "FFDBEAFE",   # cornflower
    "9B":  "FFD5D8DC",   # silver
    "10A": "FFFDEDEC",   # blush
    "10B": "FFE9F7EF",   # sage
    "11":  "FFFEF9E7",   # cream
    "12":  "FFEAF4FB",   # pale cyan
}

DAY_NAMES    = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
PERIOD_NAMES = [f"P{p+1}" for p in range(PERIODS_PER_DAY)]


def _get_fill(subject):
    if subject is None:
        return PatternFill("solid", fgColor=COLOUR_EMPTY)
    if subject == "Free":
        return PatternFill("solid", fgColor=COLOUR_FREE)
    color = SUBJECT_COLOURS.get(subject, COLOUR_WHITE)
    return PatternFill("solid", fgColor=color)


def _get_section_fill(section):
    """Return a pastel fill for a class section (used on teacher-wise sheets)."""
    color = SECTION_COLOURS.get(section, COLOUR_WHITE)
    return PatternFill("solid", fgColor=color)


def _thin_border():
    side = Side(style="thin", color="FFCCCCCC")
    return Border(left=side, right=side, top=side, bottom=side)


def _thick_border():
    side = Side(style="medium", color="FF888888")
    return Border(left=side, right=side, top=side, bottom=side)


def _header_fill():
    return PatternFill("solid", fgColor=COLOUR_HEADER)


def _subhead_fill():
    return PatternFill("solid", fgColor=COLOUR_SUBHEAD)


# ---------------------------------------------------------------------------
# Grid builder — days in rows, periods in columns
# grid[day][period] = (subject, teacher, is_lab)  or  None
# ---------------------------------------------------------------------------

def _build_class_grid(section, timetable_state):
    grid = [[None] * PERIODS_PER_DAY for _ in range(DAYS_PER_WEEK)]
    for key, placement in timetable_state.items():
        if placement["class"] != section:
            continue
        day     = placement["day"]
        period  = placement["period"]
        subject = placement["subject"]
        teacher = placement.get("teacher") or ""
        is_lab  = placement.get("is_lab", False)
        if not (0 <= day < DAYS_PER_WEEK and 0 <= period < PERIODS_PER_DAY):
            print(f"WARNING: {section} {subject} has out-of-range day={day} period={period}, skipping")
            continue
        grid[day][period] = (subject, teacher, is_lab)
    return grid


def _build_teacher_grid(teacher_name, timetable_state):
    """grid[day][period] = (subject, class_name, is_lab) or None"""
    grid = [[None] * PERIODS_PER_DAY for _ in range(DAYS_PER_WEEK)]
    for key, placement in timetable_state.items():
        if placement.get("teacher") != teacher_name:
            continue
        day     = placement["day"]
        period  = placement["period"]
        subject = placement["subject"]
        cls     = placement["class"]
        is_lab  = placement.get("is_lab", False)
        if not (0 <= day < DAYS_PER_WEEK and 0 <= period < PERIODS_PER_DAY):
            continue
        grid[day][period] = (subject, cls, is_lab)
    return grid


# ---------------------------------------------------------------------------
# Sheet writers
# ---------------------------------------------------------------------------

def _write_timetable_grid(ws, title, row_labels, col_labels, grid, cell_fill_fn, cell_value_fn, start_row=1):
    """
    Generic grid writer. Rows = days, cols = periods.
    row_labels : list of strings (one per data row)
    col_labels : list of strings (one per data column)
    grid       : grid[row][col] = cell_data or None
    cell_fill_fn(cell_data)  → PatternFill
    cell_value_fn(cell_data) → str
    Returns the next free row number.
    """
    num_cols = len(col_labels)

    # Title
    ws.merge_cells(start_row=start_row, start_column=1,
                   end_row=start_row,   end_column=num_cols + 1)
    tc = ws.cell(row=start_row, column=1, value=title)
    tc.font      = Font(bold=True, size=13, color=COLOUR_WHITE)
    tc.fill      = _header_fill()
    tc.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[start_row].height = 22

    # Header row: "Day" + period names
    header_row = start_row + 1
    day_hdr = ws.cell(row=header_row, column=1, value="Day")
    day_hdr.fill      = _header_fill()
    day_hdr.font      = Font(bold=True, color=COLOUR_WHITE)
    day_hdr.alignment = Alignment(horizontal="center")

    for ci, col_label in enumerate(col_labels):
        cell = ws.cell(row=header_row, column=ci + 2, value=col_label)
        cell.fill      = _header_fill()
        cell.font      = Font(bold=True, color=COLOUR_WHITE)
        cell.alignment = Alignment(horizontal="center")

    # Data rows
    for ri, row_label in enumerate(row_labels):
        data_row = header_row + 1 + ri
        ws.row_dimensions[data_row].height = 38

        lbl = ws.cell(row=data_row, column=1, value=row_label)
        lbl.fill      = _subhead_fill()
        lbl.font      = Font(bold=True, color=COLOUR_WHITE)
        lbl.alignment = Alignment(horizontal="center", vertical="center")

        for ci in range(num_cols):
            cell_data = grid[ri][ci]
            cell = ws.cell(row=data_row, column=ci + 2)
            cell.border    = _thin_border()
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.value     = cell_value_fn(cell_data)
            cell.fill      = cell_fill_fn(cell_data)

    # Column widths
    ws.column_dimensions["A"].width = 12
    for ci in range(num_cols):
        ws.column_dimensions[get_column_letter(ci + 2)].width = 16

    return header_row + 1 + len(row_labels)


def _write_class_sheet(ws, section, timetable_state):
    grid = _build_class_grid(section, timetable_state)

    def fill_fn(data):
        return _get_fill(data[0] if data else None)

    def val_fn(data):
        if not data:
            return "Free"
        subject, teacher, is_lab = data
        lab_suffix = " (Lab)" if is_lab else ""
        return f"{subject}{lab_suffix}\n{teacher}" if teacher else f"{subject}{lab_suffix}"

    _write_timetable_grid(
        ws,
        title      = f"Timetable — Class {section}",
        row_labels = DAY_NAMES,
        col_labels = PERIOD_NAMES,
        grid       = grid,
        cell_fill_fn  = fill_fn,
        cell_value_fn = val_fn,
    )


def _write_teacher_sheet(ws, teacher_name, timetable_state):
    grid = _build_teacher_grid(teacher_name, timetable_state)

    def fill_fn(data):
        if not data:
            return PatternFill("solid", fgColor=COLOUR_EMPTY)
        return _get_section_fill(data[1])   # data[1] = cls (section)

    def val_fn(data):
        if not data:
            return ""
        subject, cls, is_lab = data
        if subject == "Free":
            return f"Duty\n({cls})"
        lab_suffix = " (Lab)" if is_lab else ""
        return f"{subject}{lab_suffix}\n({cls})"

    _write_timetable_grid(
        ws,
        title      = f"Timetable — {teacher_name}",
        row_labels = DAY_NAMES,
        col_labels = PERIOD_NAMES,
        grid       = grid,
        cell_fill_fn  = fill_fn,
        cell_value_fn = val_fn,
    )


# ---------------------------------------------------------------------------
# Master aggregate sheets
# ---------------------------------------------------------------------------

def _write_master_sections_sheet(ws, timetable_state):
    """All class timetables stacked vertically with one blank row between each."""
    next_row = 1
    for section in CLASS_ORDER:
        grid = _build_class_grid(section, timetable_state)

        def fill_fn(data, _s=section):
            return _get_fill(data[0] if data else None)

        def val_fn(data):
            if not data:
                return "Free"
            subject, teacher, is_lab = data
            lab_suffix = " (Lab)" if is_lab else ""
            return f"{subject}{lab_suffix}\n{teacher}" if teacher else f"{subject}{lab_suffix}"

        next_row = _write_timetable_grid(
            ws,
            title         = f"Timetable — Class {section}",
            row_labels    = DAY_NAMES,
            col_labels    = PERIOD_NAMES,
            grid          = grid,
            cell_fill_fn  = fill_fn,
            cell_value_fn = val_fn,
            start_row     = next_row,
        )
        next_row += 1   # one blank row between tables


def _write_master_teachers_sheet(ws, timetable_state, teachers):
    """All teacher timetables stacked vertically with one blank row between each."""
    next_row = 1
    for teacher_name in teachers:
        grid = _build_teacher_grid(teacher_name, timetable_state)

        def fill_fn(data):
            if not data:
                return PatternFill("solid", fgColor=COLOUR_EMPTY)
            return _get_section_fill(data[1])   # data[1] = cls (section)

        def val_fn(data):
            if not data:
                return ""
            subject, cls, is_lab = data
            if subject == "Free":
                return f"Duty\n({cls})"
            lab_suffix = " (Lab)" if is_lab else ""
            return f"{subject}{lab_suffix}\n({cls})"

        next_row = _write_timetable_grid(
            ws,
            title         = f"Timetable — {teacher_name}",
            row_labels    = DAY_NAMES,
            col_labels    = PERIOD_NAMES,
            grid          = grid,
            cell_fill_fn  = fill_fn,
            cell_value_fn = val_fn,
            start_row     = next_row,
        )
        next_row += 1   # one blank row between tables


# ---------------------------------------------------------------------------
# Dashboard sheet
# ---------------------------------------------------------------------------

def _write_dashboard(ws, timetable_state, events):
    """
    Section 1: Teacher Load Summary — teacher → total periods/week
    Section 2: Weekly periods per subject per section (section × subject matrix)
    """
    bold_white  = Font(bold=True, color=COLOUR_WHITE)
    bold_dark   = Font(bold=True)
    center      = Alignment(horizontal="center", vertical="center")
    left        = Alignment(horizontal="left",   vertical="center")

    def _sec_header(row, col, text, width_cols):
        ws.merge_cells(start_row=row, start_column=col,
                       end_row=row,   end_column=col + width_cols - 1)
        c = ws.cell(row=row, column=col, value=text)
        c.fill      = PatternFill("solid", fgColor=COLOUR_DASH_H)
        c.font      = Font(bold=True, size=12, color=COLOUR_WHITE)
        c.alignment = center
        ws.row_dimensions[row].height = 20

    # ── Collect teacher load ─────────────────────────────────────────────────
    teacher_load = Counter()
    for placement in timetable_state.values():
        t = placement.get("teacher")
        if t:
            teacher_load[t] += 1

    sorted_teachers = sorted(teacher_load.keys())

    # ── Collect subject counts per section ──────────────────────────────────
    section_subject_counts = defaultdict(Counter)
    for placement in timetable_state.values():
        section_subject_counts[placement["class"]][placement["subject"]] += 1

    # Determine all subjects (sorted)
    all_subjects = sorted({placement["subject"] for placement in timetable_state.values()})

    # ════════════════════════════════════════════════════════════════════════
    # SECTION 1 — Teacher Load Summary  (starts at row 1)
    # ════════════════════════════════════════════════════════════════════════
    _sec_header(1, 1, "Teacher Load Summary (periods / week)", 3)

    # Column headers
    for col, hdr in enumerate(["Teacher", "Periods / Week"], start=1):
        c = ws.cell(row=2, column=col, value=hdr)
        c.fill = _subhead_fill()
        c.font = bold_white
        c.alignment = center
        c.border = _thin_border()

    for ri, teacher in enumerate(sorted_teachers, start=3):
        ws.cell(row=ri, column=1, value=teacher).border = _thin_border()
        ws.cell(row=ri, column=1).alignment = left
        load_cell = ws.cell(row=ri, column=2, value=teacher_load[teacher])
        load_cell.border    = _thin_border()
        load_cell.alignment = center
        ws.row_dimensions[ri].height = 16

    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 18

    load_end_row = 2 + len(sorted_teachers)

    # ════════════════════════════════════════════════════════════════════════
    # SECTION 2 — Weekly periods per subject per section
    # (placed to the right of section 1, starting at column 4)
    # ════════════════════════════════════════════════════════════════════════
    LEFT_COL = 4   # sections start here
    num_subjects = len(all_subjects)

    _sec_header(1, LEFT_COL, "Weekly Periods per Subject per Section",
                num_subjects + 1)

    # Row header: "Section" + subject names
    ws.cell(row=2, column=LEFT_COL, value="Section").fill = _subhead_fill()
    ws.cell(row=2, column=LEFT_COL).font      = bold_white
    ws.cell(row=2, column=LEFT_COL).alignment = center
    ws.cell(row=2, column=LEFT_COL).border    = _thin_border()

    for ci, subj in enumerate(all_subjects):
        c = ws.cell(row=2, column=LEFT_COL + 1 + ci, value=subj)
        c.fill      = _subhead_fill()
        c.font      = bold_white
        c.alignment = center
        c.border    = _thin_border()

    for ri, section in enumerate(CLASS_ORDER, start=3):
        sec_cell = ws.cell(row=ri, column=LEFT_COL, value=section)
        sec_cell.fill      = PatternFill("solid", fgColor=COLOUR_HEADER)
        sec_cell.font      = bold_white
        sec_cell.alignment = center
        sec_cell.border    = _thin_border()
        ws.row_dimensions[ri].height = 16

        for ci, subj in enumerate(all_subjects):
            count = section_subject_counts[section].get(subj, 0)
            c = ws.cell(row=ri, column=LEFT_COL + 1 + ci,
                        value=count if count > 0 else "")
            c.border    = _thin_border()
            c.alignment = center
            if count > 0:
                c.fill = _get_fill(subj)

    # Column widths for subject matrix
    ws.column_dimensions[get_column_letter(LEFT_COL)].width = 12
    for ci in range(num_subjects):
        ws.column_dimensions[get_column_letter(LEFT_COL + 1 + ci)].width = 11


# ---------------------------------------------------------------------------
# Validation check before export
# ---------------------------------------------------------------------------

def validate_before_export(timetable_state, events):
    violations = []
    seen_teacher = {}
    seen_class   = {}

    for key, p in timetable_state.items():
        day, period = p["day"], p["period"]

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

        ck = (p["class"], day, period)
        if ck in seen_class:
            violations.append(
                f"Class clash: {p['class']} at day={day} period={period} "
                f"— events {seen_class[ck]} and {key}"
            )
        else:
            seen_class[ck] = key

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
    print("── Running pre-export validation ──")
    unknown_classes = {p["class"] for p in timetable_state.values()} - set(CLASS_ORDER)
    if unknown_classes:
        print(f"WARNING: classes {sorted(unknown_classes)} not in CLASS_ORDER — skipped")
    violations = validate_before_export(timetable_state, events)

    if violations:
        print(f"   EXPORT WARNING — {len(violations)} violation(s) (exporting anyway):")
        for v in violations:
            print(f"   ⚠ {v}")

    print("   Validation passed. Writing Excel file...")

    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    teachers = sorted({p["teacher"] for p in timetable_state.values() if p.get("teacher")})

    # ── Sheet 1: Dashboard ──────────────────────────────────────────────────
    ws_dash = wb.create_sheet(title="Dashboard")
    _write_dashboard(ws_dash, timetable_state, events)

    # ── Sheet 2: Master — all sections stacked ──────────────────────────────
    ws_all_sec = wb.create_sheet(title="All Sections")
    _write_master_sections_sheet(ws_all_sec, timetable_state)

    # ── Sheet 3: Master — all teachers stacked ──────────────────────────────
    ws_all_tch = wb.create_sheet(title="All Teachers")
    _write_master_teachers_sheet(ws_all_tch, timetable_state, teachers)

    # ── Sheets 4+: Class-wise timetables (one sheet per class) ──────────────
    for section in CLASS_ORDER:
        ws = wb.create_sheet(title=f"Class {section}")
        _write_class_sheet(ws, section, timetable_state)

    # ── Sheets N+: Teacher-wise timetables (one sheet per teacher) ───────────
    for teacher in teachers:
        ws = wb.create_sheet(title=teacher[:31])   # Excel sheet name limit = 31 chars
        _write_teacher_sheet(ws, teacher, timetable_state)

    wb.save(output_path)
    print(f"── Timetable saved to: {output_path} ──")
