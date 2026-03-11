# exporter.py

import openpyxl
from collections import defaultdict, Counter
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from constraints import (
    DAYS_PER_WEEK,
    PERIODS_PER_DAY,
    ANCHOR_SUBJECTS,
    LAB_BLOCK_SUBJECTS,
    FIXED_SLOT_SUBJECTS,
    FLOATING_SINGLE_SUBJECTS,
    PERIOD_NAMES_DISPLAY,
    PERIOD_TIMES,
)
from event_generator import CLASS_ORDER

# ---------------------------------------------------------------------------
# Colour palette  (openpyxl uses ARGB hex, no leading #)
# ---------------------------------------------------------------------------

COLOUR_ANCHOR   = "FFD6EAF8"   # light blue   — Math, Science, English, SST
COLOUR_LAB      = "FFD5F5E3"   # light green  — Physics, Chemistry, Biology
COLOUR_FIXED    = "FFFFF3CD"   # light yellow — Game, CCA
COLOUR_FLOAT    = "FFFDE8D8"   # light orange — Library, WE
COLOUR_FREE     = "FFD5D8DC"   # light grey-blue — Free (duty) periods
COLOUR_EMPTY    = "FFF5F5F5"   # light grey   — empty cell
COLOUR_HEADER   = "FF2E4057"   # dark blue    — header row/col
COLOUR_SUBHEAD  = "FF4A6FA5"   # medium blue  — sub-headers
COLOUR_WHITE    = "FFFFFFFF"
COLOUR_DASH_H   = "FF1B2631"   # near-black   — dashboard section headers
COLOUR_DRILL    = "FFE8DAEF"   # light purple — Drill/Yoga period
COLOUR_BREAK    = "FFFFFDE7"   # light amber  — Breakfast break

DAY_NAMES    = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
PERIOD_NAMES = PERIOD_NAMES_DISPLAY   # ["Drill","P1","P2","Break","P3","P4","P5","P6"]


def _get_fill(subject):
    if subject is None:
        return PatternFill("solid", fgColor=COLOUR_EMPTY)
    if subject == "Free":
        return PatternFill("solid", fgColor=COLOUR_FREE)
    if subject == "Drill":
        return PatternFill("solid", fgColor=COLOUR_DRILL)
    if subject == "Breakfast":
        return PatternFill("solid", fgColor=COLOUR_BREAK)
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
        # Show period name + time on two lines (e.g. "P1\n7:30–8:10")
        time_label = PERIOD_TIMES[ci] if ci < len(PERIOD_TIMES) else ""
        cell_val   = f"{col_label}\n{time_label}" if time_label else col_label
        cell = ws.cell(row=header_row, column=ci + 2, value=cell_val)
        cell.fill      = _header_fill()
        cell.font      = Font(bold=True, color=COLOUR_WHITE, size=9)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.row_dimensions[header_row].height = 30

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
        return _get_fill(data[0] if data else None)

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
# Violations section (written into the Dashboard)
# ---------------------------------------------------------------------------

COLOUR_VIOL_HDR  = "FFC0392B"   # red      — violations section header
COLOUR_VIOL_ROW  = "FFFCE4D6"   # salmon   — violation row cells
COLOUR_OK_ROW    = "FFE9F7EF"   # pale green — all-clear row


def _write_violations_section(ws, violations, start_row):
    """
    Writes a Validation Report block starting at start_row, columns A–C.
    Each violation row shows: # | Violation | Suggested Fix
    """
    center = Alignment(horizontal="center", vertical="center")
    left   = Alignment(horizontal="left",   vertical="center", wrap_text=True)
    bold_white = Font(bold=True, color=COLOUR_WHITE)

    if not violations:
        ws.merge_cells(start_row=start_row, start_column=1,
                       end_row=start_row,   end_column=3)
        hdr = ws.cell(row=start_row, column=1,
                      value="Validation Report — All checks passed")
        hdr.fill      = PatternFill("solid", fgColor=COLOUR_DASH_H)
        hdr.font      = Font(bold=True, size=12, color=COLOUR_WHITE)
        hdr.alignment = center
        ws.row_dimensions[start_row].height = 20

        ok_row = start_row + 1
        ws.merge_cells(start_row=ok_row, start_column=1,
                       end_row=ok_row,   end_column=3)
        ok = ws.cell(row=ok_row, column=1, value="No violations found")
        ok.fill      = PatternFill("solid", fgColor=COLOUR_OK_ROW)
        ok.font      = Font(bold=True, color="FF1E8449")
        ok.alignment = center
        ok.border    = _thin_border()
        ws.row_dimensions[ok_row].height = 18
        return

    # Header
    ws.merge_cells(start_row=start_row, start_column=1,
                   end_row=start_row,   end_column=3)
    hdr = ws.cell(row=start_row, column=1,
                  value=f"Validation Report — {len(violations)} Violation(s) Found")
    hdr.fill      = PatternFill("solid", fgColor=COLOUR_VIOL_HDR)
    hdr.font      = Font(bold=True, size=12, color=COLOUR_WHITE)
    hdr.alignment = center
    ws.row_dimensions[start_row].height = 20

    # Column headers
    col_row = start_row + 1
    for col, label in enumerate(["#", "Violation", "Suggested Fix"], start=1):
        c = ws.cell(row=col_row, column=col, value=label)
        c.fill      = _subhead_fill()
        c.font      = bold_white
        c.alignment = center
        c.border    = _thin_border()
    ws.row_dimensions[col_row].height = 16

    # Violation rows
    for i, v in enumerate(violations, start=1):
        row = col_row + i
        ws.row_dimensions[row].height = 42

        num_c = ws.cell(row=row, column=1, value=i)
        num_c.fill      = PatternFill("solid", fgColor=COLOUR_VIOL_ROW)
        num_c.border    = _thin_border()
        num_c.alignment = center
        num_c.font      = Font(bold=True)

        msg_c = ws.cell(row=row, column=2, value=v["message"])
        msg_c.fill      = PatternFill("solid", fgColor=COLOUR_VIOL_ROW)
        msg_c.border    = _thin_border()
        msg_c.alignment = left

        sug_c = ws.cell(row=row, column=3, value=v["suggestion"])
        sug_c.fill      = PatternFill("solid", fgColor=COLOUR_VIOL_ROW)
        sug_c.border    = _thin_border()
        sug_c.alignment = left

    # Widen columns B and C to accommodate violation text
    ws.column_dimensions["B"].width = 55
    ws.column_dimensions["C"].width = 55


# ---------------------------------------------------------------------------
# Dashboard sheet
# ---------------------------------------------------------------------------

def _write_dashboard(ws, timetable_state, events, violations=None):
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

    # ════════════════════════════════════════════════════════════════════════
    # SECTION 3 — Validation Report  (below Teacher Load, columns A–C)
    # ════════════════════════════════════════════════════════════════════════
    violations_start = load_end_row + 2
    _write_violations_section(ws, violations or [], violations_start)


# ---------------------------------------------------------------------------
# Validation check before export
# ---------------------------------------------------------------------------

def validate_before_export(timetable_state, events):
    """
    Returns a list of violation dicts, each with keys:
      "message"    — human-readable description of the problem
      "suggestion" — recommended corrective action
    """
    violations = []
    seen_teacher = {}
    seen_class   = {}

    for key, p in timetable_state.items():
        day, period = p["day"], p["period"]
        subject = p.get("subject", "?")
        cls     = p.get("class", "?")
        day_label    = DAY_NAMES[day] if 0 <= day < len(DAY_NAMES) else f"Day{day}"
        period_label = PERIOD_NAMES[period] if 0 <= period < len(PERIOD_NAMES) else f"P{period}"

        teacher = p.get("teacher")
        if teacher:
            tk = (teacher, day, period)
            if tk in seen_teacher:
                other_p = timetable_state[seen_teacher[tk]]
                violations.append({
                    "message": (
                        f"Teacher clash: {teacher} is double-booked — "
                        f"{cls} {subject} and {other_p['class']} {other_p['subject']} "
                        f"both at {day_label} {period_label}"
                    ),
                    "suggestion": (
                        f"Move {cls} {subject} or {other_p['class']} {other_p['subject']} "
                        f"to any free period for {teacher}"
                    ),
                })
            else:
                seen_teacher[tk] = key

        ck = (cls, day, period)
        if ck in seen_class:
            other_p = timetable_state[seen_class[ck]]
            violations.append({
                "message": (
                    f"Class clash: {cls} has {subject} and {other_p['subject']} "
                    f"both at {day_label} {period_label}"
                ),
                "suggestion": (
                    f"Move {subject} or {other_p['subject']} for {cls} "
                    f"to a different day or period"
                ),
            })
        else:
            seen_class[ck] = key

    placement_counts = Counter()
    for (event_idx, instance), _ in timetable_state.items():
        placement_counts[event_idx] += 1

    for event_idx, event in enumerate(events):
        placed   = placement_counts.get(event_idx, 0)
        expected = event["weekly_load"]
        if placed != expected:
            if placed < expected:
                suggestion = (
                    f"Re-run solver or manually add {expected - placed} more "
                    f"period(s) of {event['subject']} for {event['class']}"
                )
            else:
                suggestion = (
                    f"Remove {placed - expected} extra period(s) of "
                    f"{event['subject']} for {event['class']} from the timetable"
                )
            violations.append({
                "message": (
                    f"Load mismatch: {event['class']} {event['subject']} "
                    f"— expected {expected} period(s)/week, placed {placed}"
                ),
                "suggestion": suggestion,
            })

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
        print(f"   EXPORT WARNING — {len(violations)} violation(s) (see Dashboard sheet):")
        for v in violations:
            print(f"   ⚠  {v['message']}")
            print(f"      → {v['suggestion']}")
    else:
        print("   Validation passed — no violations found.")

    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    # ── Sheet 1: Class-wise timetables (one sheet per class) ────────────────
    for section in CLASS_ORDER:
        ws = wb.create_sheet(title=f"Class {section}")
        _write_class_sheet(ws, section, timetable_state)

    # ── Sheet 2: Teacher-wise timetables (one sheet per teacher) ────────────
    teachers = sorted({p["teacher"] for p in timetable_state.values() if p.get("teacher")})
    for teacher in teachers:
        ws = wb.create_sheet(title=teacher[:31])   # Excel sheet name limit = 31 chars
        _write_teacher_sheet(ws, teacher, timetable_state)

    # ── Sheet 3: Dashboard ──────────────────────────────────────────────────
    ws_dash = wb.create_sheet(title="Dashboard")
    _write_dashboard(ws_dash, timetable_state, events, violations)

    wb.save(output_path)
    print(f"── Timetable saved to: {output_path} ──")
