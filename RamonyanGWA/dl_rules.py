"""
Core business rules and calculations for RamonyanGWA.
Pure Python module with no Flask or database dependencies.
Uses dataclasses and decimal.Decimal (ROUND_HALF_UP).
"""

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
import math
import re
from typing import Dict, List, Optional, Tuple, Any


@dataclass(frozen=True)
class DLRuleConfig:
    rule_id: int = 1
    max_gwa: Decimal = Decimal("1.75")
    worst_allowed_grade: Decimal = Decimal("2.25")
    require_full_load: int = 1
    max_subject_units: Decimal = Decimal("12")
    max_prescribed_units: Decimal = Decimal("40")
    noncredit_checked_for_grade_rules: int = 1


@dataclass(frozen=True)
class GradeScaleItem:
    mark: str
    grade_point: Optional[Decimal]
    min_percent: Optional[int]
    max_percent: Optional[int]
    blocks_dl: int


@dataclass
class SubjectInput:
    row_index: int
    name: str
    subject_type: str  # "credit" or "noncredit"
    units: Decimal
    mark: str
    grade_point: Optional[Decimal] = None
    blocks_dl: bool = False


@dataclass
class SubjectDisplay:
    name: str
    subject_type: str
    units_display: str
    raw_units: Decimal
    mark: str
    in_gwa: bool
    reason_not_in_gwa: Optional[str] = None


@dataclass
class RuleResult:
    label: str
    passed: bool
    actual_value: str
    requirement: str
    detail: str = ""


@dataclass
class EvaluationResult:
    is_qualified: bool
    status_text: str  # "Qualified" or "Not qualified"
    status_sentence: str
    computed_gwa: Optional[Decimal]
    gwa_display: str
    is_provisional: bool
    standing_position: float
    total_units: Decimal
    credited_units: Decimal
    noncredit_units: Decimal
    wavg_working: str
    equiv_grade: Optional[Decimal]
    equiv_grade_display: str
    units_summary_text: str
    sias_notice: Optional[str]
    rule_results: List[RuleResult]
    failed_rule_count: int
    subjects_display: List[SubjectDisplay]


def compute_standing_position(gwa: Optional[Decimal]) -> float:
    """
    Computes the standing bar position clamped between 0.0 and 1.0.
    position = (gwa - 1.0) / 2.0
    1.0 gives 0, 1.75 gives 0.375, 2.0 gives 0.5, 3.0+ gives 1.0, <1.0 gives 0.0.
    """
    if gwa is None:
        return 0.0
    val = float((Decimal(str(gwa)) - Decimal("1.0")) / Decimal("2.0"))
    if val < 0.0:
        return 0.0
    if val > 1.0:
        return 1.0
    return val


def compute_gwa(subjects: List[SubjectInput]) -> Tuple[Optional[Decimal], Decimal, Decimal, bool]:
    """
    Computes GWA over CREDIT subjects that have a numeric grade point.
    Returns: (gwa_rounded_4_dec, total_points, credited_units, is_provisional)
    """
    credit_points = Decimal("0")
    credit_units_with_grade = Decimal("0")
    total_credit_units = Decimal("0")
    has_inc_or_ip_credit = False

    for s in subjects:
        if s.subject_type == "credit":
            total_credit_units += s.units
            if s.grade_point is not None:
                credit_points += s.units * s.grade_point
                credit_units_with_grade += s.units
            else:
                # Mark has no grade value (INC, IP)
                has_inc_or_ip_credit = True

    if credit_units_with_grade > Decimal("0"):
        raw_gwa = credit_points / credit_units_with_grade
        gwa_rounded = raw_gwa.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    else:
        gwa_rounded = None

    return gwa_rounded, credit_points, total_credit_units, has_inc_or_ip_credit


def compute_equiv_grade(subjects: List[SubjectInput]) -> Optional[Decimal]:
    """
    Computes Equiv Grade (all units) over ALL subjects (credit and non-credit)
    that have a numeric grade point, rounded to 2 decimals.
    """
    total_points = Decimal("0")
    total_units_graded = Decimal("0")

    for s in subjects:
        if s.grade_point is not None:
            total_points += s.units * s.grade_point
            total_units_graded += s.units

    if total_units_graded > Decimal("0"):
        raw_equiv = total_points / total_units_graded
        return raw_equiv.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return None


def compare_sias(
    computed_gwa: Optional[Decimal],
    equiv_grade: Optional[Decimal],
    entered_cog_gwa: Optional[Decimal],
    has_noncredit: bool,
) -> Optional[str]:
    """
    Produces SIAS notice message comparing computed GWA and entered COG/SIAS GWA.
    """
    if entered_cog_gwa is None:
        return None

    if computed_gwa is not None and abs(computed_gwa - entered_cog_gwa) <= Decimal("0.0001"):
        return "Matches: this is the same as the GWA you entered from your COG/SIAS."

    if has_noncredit and equiv_grade is not None:
        entered_rounded_2 = entered_cog_gwa.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if entered_rounded_2 == equiv_grade:
            return (
                "Heads up: the value you entered matches the equivalent grade / total, "
                "which includes non-credit units. The GWA uses credit units only."
            )

    return (
        "Heads up: your COG/SIAS GWA differs from this result. Check that the subjects "
        "and units you entered match the ones counted on your COG (non-credit units "
        "such as NSTP are shown in parentheses and are not counted in the GWA)."
    )


def validate_form(
    raw_form: Any,
    rule_config: DLRuleConfig,
    grade_scale_dict: Dict[str, GradeScaleItem],
) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """
    Validates form data from request.form.
    Returns: (cleaned_data_dict, list_of_error_strings)
    """
    errors: List[str] = []

    # 1. Prescribed units validation
    raw_prescribed = raw_form.get("prescribed_units", "").strip()
    if not raw_prescribed:
        errors.append("Prescribed units is required.")
        prescribed_units = None
    else:
        try:
            val = Decimal(raw_prescribed)
            if math.isnan(float(val)) or math.isinf(float(val)) or val <= Decimal("0") or val > rule_config.max_prescribed_units:
                errors.append(
                    f'"Prescribed units" must be a number greater than 0 and at most {rule_config.max_prescribed_units}.'
                )
                prescribed_units = None
            else:
                prescribed_units = val
        except (InvalidOperation, ValueError):
            errors.append('"Prescribed units" must be a valid number.')
            prescribed_units = None

    # 2. Optional COG/SIAS GWA validation
    raw_cog_gwa = raw_form.get("cog_gwa", "").strip()
    cog_gwa = None
    if raw_cog_gwa:
        try:
            val = Decimal(raw_cog_gwa)
            if math.isnan(float(val)) or math.isinf(float(val)) or val <= Decimal("0"):
                errors.append('"GWA shown in COG/SIAS" must be a valid positive number.')
            else:
                cog_gwa = val
        except (InvalidOperation, ValueError):
            errors.append('"GWA shown in COG/SIAS" must be a valid number.')

    # 3. Extract and validate rows
    row_indices = set()
    key_pattern = re.compile(r"^(name|type|units|mark)_(\d+)$")
    for k in raw_form.keys():
        match = key_pattern.match(k)
        if match:
            row_indices.add(int(match.group(2)))

    sorted_indices = sorted(list(row_indices))
    subjects: List[SubjectInput] = []

    for idx in sorted_indices:
        display_num = idx + 1
        name = raw_form.get(f"name_{idx}", "").strip()
        stype = raw_form.get(f"type_{idx}", "credit").strip().lower()
        units_str = raw_form.get(f"units_{idx}", "").strip()
        mark = raw_form.get(f"mark_{idx}", "").strip()

        # Check if row is completely blank (ignored)
        if not name and not units_str and not mark:
            continue

        row_has_error = False

        # Subject type validation
        if stype not in ("credit", "noncredit"):
            errors.append(f'Subject {display_num}: "Type" must be either credit or noncredit.')
            row_has_error = True

        # Units validation
        if not units_str:
            errors.append(f'Subject {display_num}: "Units" is required.')
            row_has_error = True
            row_units = None
        else:
            try:
                u_val = Decimal(units_str)
                if math.isnan(float(u_val)) or math.isinf(float(u_val)) or u_val <= Decimal("0"):
                    errors.append(f'Subject {display_num}: "Units" must be a number greater than 0.')
                    row_has_error = True
                    row_units = None
                elif u_val > rule_config.max_subject_units:
                    errors.append(
                        f'Subject {display_num}: "Units" cannot exceed {rule_config.max_subject_units}.'
                    )
                    row_has_error = True
                    row_units = None
                else:
                    row_units = u_val
            except (InvalidOperation, ValueError):
                errors.append(f'Subject {display_num}: "Units" must be a valid number.')
                row_has_error = True
                row_units = None

        # Final grade validation
        if not mark:
            errors.append(f'Subject {display_num}: "Final grade" is required.')
            row_has_error = True
        elif mark not in grade_scale_dict:
            errors.append(f'Subject {display_num}: "{mark}" is not a valid grade mark.')
            row_has_error = True

        if not row_has_error and row_units is not None and mark in grade_scale_dict:
            gs_item = grade_scale_dict[mark]
            subjects.append(
                SubjectInput(
                    row_index=idx,
                    name=name,
                    subject_type=stype,
                    units=row_units,
                    mark=mark,
                    grade_point=gs_item.grade_point,
                    blocks_dl=bool(gs_item.blocks_dl),
                )
            )

    if not subjects and not any("Subject" in e for e in errors):
        errors.append("At least one subject is required.")

    if errors:
        return None, errors

    cleaned_data = {
        "prescribed_units": prescribed_units,
        "cog_gwa": cog_gwa,
        "subjects": subjects,
    }
    return cleaned_data, []


def evaluate(
    prescribed_units: Decimal,
    subjects: List[SubjectInput],
    rule_config: DLRuleConfig,
    grade_scale_dict: Dict[str, GradeScaleItem],
    entered_cog_gwa: Optional[Decimal] = None,
) -> EvaluationResult:
    """
    Evaluates Dean's List eligibility and returns complete EvaluationResult.
    """
    computed_gwa, credit_points, credited_units, is_provisional = compute_gwa(subjects)
    equiv_grade = compute_equiv_grade(subjects)

    total_units = sum(s.units for s in subjects)
    noncredit_units = sum(s.units for s in subjects if s.subject_type == "noncredit")
    has_noncredit = noncredit_units > Decimal("0")

    # Working string
    if credited_units > Decimal("0") and credit_points is not None:
        pts_norm = credit_points.normalize()
        pts_str = f"{pts_norm:f}" if "." in f"{pts_norm:f}" else f"{pts_norm}"
        # If integer, e.g. 26.5 vs 26
        pts_display = str(credit_points.quantize(Decimal("0.01"))).rstrip("0").rstrip(".") if "." in str(credit_points) else str(credit_points)
        wavg_working = f"{pts_display} divided by {credited_units} units"
    else:
        wavg_working = "N/A"

    gwa_display = f"{computed_gwa:.4f}" if computed_gwa is not None else "N/A"
    equiv_grade_display = f"{equiv_grade:.2f}" if equiv_grade is not None else "N/A"
    standing_pos = compute_standing_position(computed_gwa)

    units_summary_text = f"{total_units} total, {credited_units} credited, {noncredit_units} non-credit"

    # Evaluate Rules
    rules: List[RuleResult] = []

    # Rule 1: GWA <= max_gwa
    if computed_gwa is not None:
        rule_1_pass = computed_gwa <= rule_config.max_gwa
        rule_1_val = f"{computed_gwa:.4f}"
    else:
        rule_1_pass = False
        rule_1_val = "N/A"
    rules.append(
        RuleResult(
            label="GWA",
            passed=rule_1_pass,
            actual_value=f"GWA {rule_1_val}",
            requirement=f"<= {rule_config.max_gwa:.2f}",
            detail="Computed from credit subjects with numerical grades.",
        )
    )

    # Rule 2: Lowest grade <= worst_allowed_grade (2.25)
    # Check credit subjects, and non-credit if noncredit_checked_for_grade_rules == 1
    grade_check_subjects = [
        s for s in subjects
        if s.subject_type == "credit" or rule_config.noncredit_checked_for_grade_rules == 1
    ]

    numeric_grades = [s.grade_point for s in grade_check_subjects if s.grade_point is not None]
    if numeric_grades:
        worst_grade = max(numeric_grades)
        rule_2_pass = worst_grade <= rule_config.worst_allowed_grade
        rule_2_val = f"{worst_grade:.2f}"
    else:
        # If no numeric grades (e.g. only INC/IP), cannot evaluate passing worst grade
        rule_2_pass = False
        rule_2_val = "None"

    rules.append(
        RuleResult(
            label="Lowest grade",
            passed=rule_2_pass,
            actual_value=f"Lowest grade {rule_2_val}",
            requirement=f"<= {rule_config.worst_allowed_grade:.2f}",
            detail="No grade lower than 2.25 allowed.",
        )
    )

    # Rule 3: No 5.0, INC, or IP marks
    blocking_marks_found = [
        s.mark for s in grade_check_subjects
        if s.mark in ("5.0", "INC", "IP") or s.blocks_dl
    ]
    rule_3_pass = len(blocking_marks_found) == 0
    rule_3_val = "None found" if rule_3_pass else f"{', '.join(sorted(set(blocking_marks_found)))} found"
    rules.append(
        RuleResult(
            label="No 5.0, INC, or IP marks",
            passed=rule_3_pass,
            actual_value=rule_3_val,
            requirement="No 5.0, INC, or IP",
            detail="Failing, incomplete, and in-progress marks disqualify.",
        )
    )

    # Rule 4: Full load (total units >= prescribed_units)
    if rule_config.require_full_load:
        rule_4_pass = total_units >= prescribed_units
    else:
        rule_4_pass = True
    rules.append(
        RuleResult(
            label="Full load",
            passed=rule_4_pass,
            actual_value=f"{total_units} total units",
            requirement=f">= {prescribed_units} prescribed",
            detail="Includes both credit and non-credit units.",
        )
    )

    # Order rules: FAILED rules first!
    failed_rules = [r for r in rules if not r.passed]
    passed_rules = [r for r in rules if r.passed]
    ordered_rules = failed_rules + passed_rules
    failed_count = len(failed_rules)

    is_qualified = (failed_count == 0)
    status_text = "Qualified" if is_qualified else "Not qualified"
    if is_qualified:
        status_sentence = "All 4 Dean's List rules passed."
    else:
        status_sentence = f"{failed_count} of 4 rules failed. They are listed first below."

    # Subject display records
    subjects_display: List[SubjectDisplay] = []
    for s in subjects:
        u_str = f"({s.units})" if s.subject_type == "noncredit" else f"{s.units}"
        if s.subject_type == "noncredit":
            in_gwa = False
            reason = "Non-credit"
        elif s.grade_point is None:
            in_gwa = False
            reason = f"Mark {s.mark} has no grade value"
        else:
            in_gwa = True
            reason = None

        subjects_display.append(
            SubjectDisplay(
                name=s.name if s.name else "Subject",
                subject_type="Non-credit" if s.subject_type == "noncredit" else "Credit",
                units_display=u_str,
                raw_units=s.units,
                mark=s.mark,
                in_gwa=in_gwa,
                reason_not_in_gwa=reason,
            )
        )

    sias_notice = compare_sias(computed_gwa, equiv_grade, entered_cog_gwa, has_noncredit)

    return EvaluationResult(
        is_qualified=is_qualified,
        status_text=status_text,
        status_sentence=status_sentence,
        computed_gwa=computed_gwa,
        gwa_display=gwa_display,
        is_provisional=is_provisional,
        standing_position=standing_pos,
        total_units=total_units,
        credited_units=credited_units,
        noncredit_units=noncredit_units,
        wavg_working=wavg_working,
        equiv_grade=equiv_grade,
        equiv_grade_display=equiv_grade_display,
        units_summary_text=units_summary_text,
        sias_notice=sias_notice,
        rule_results=ordered_rules,
        failed_rule_count=failed_count,
        subjects_display=subjects_display,
    )
