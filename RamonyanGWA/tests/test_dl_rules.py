from decimal import Decimal
import pytest
from dl_rules import (
    DLRuleConfig,
    SubjectInput,
    compute_standing_position,
    compute_gwa,
    compute_equiv_grade,
    compare_sias,
    validate_form,
    evaluate,
)


def make_subject(idx: int, units: float, mark: str, stype: str = "credit", grade_scale_dict=None) -> SubjectInput:
    gp = grade_scale_dict[mark].grade_point if grade_scale_dict and mark in grade_scale_dict else None
    blocks = bool(grade_scale_dict[mark].blocks_dl) if grade_scale_dict and mark in grade_scale_dict else False
    return SubjectInput(
        row_index=idx,
        name=f"Subj {idx}",
        subject_type=stype,
        units=Decimal(str(units)),
        mark=mark,
        grade_point=gp,
        blocks_dl=blocks,
    )


# TC-01: 3x1.5, 3x1.25, 3x1.75, 3x1.5, 2x1.25, 3x1.5, load 17 -> GWA 1.4706, qualifies.
def test_tc01_qualifies(dl_rule_config, grade_scale_dict):
    subjects = [
        make_subject(0, 3, "1.5", grade_scale_dict=grade_scale_dict),
        make_subject(1, 3, "1.25", grade_scale_dict=grade_scale_dict),
        make_subject(2, 3, "1.75", grade_scale_dict=grade_scale_dict),
        make_subject(3, 3, "1.5", grade_scale_dict=grade_scale_dict),
        make_subject(4, 2, "1.25", grade_scale_dict=grade_scale_dict),
        make_subject(5, 3, "1.5", grade_scale_dict=grade_scale_dict),
    ]
    res = evaluate(Decimal("17"), subjects, dl_rule_config, grade_scale_dict)
    assert res.computed_gwa == Decimal("1.4706")
    assert res.is_qualified is True
    assert res.status_text == "Qualified"
    assert res.status_sentence == "All 4 Dean's List rules passed."
    assert res.failed_rule_count == 0


# TC-02: 3x1.25 (three subjects), 3x1.5, 3x2.5, 2x1.25, load 17 -> GWA 1.5147, fails lowest-grade rule.
def test_tc02_fails_lowest_grade(dl_rule_config, grade_scale_dict):
    subjects = [
        make_subject(0, 3, "1.25", grade_scale_dict=grade_scale_dict),
        make_subject(1, 3, "1.25", grade_scale_dict=grade_scale_dict),
        make_subject(2, 3, "1.25", grade_scale_dict=grade_scale_dict),
        make_subject(3, 3, "1.5", grade_scale_dict=grade_scale_dict),
        make_subject(4, 3, "2.5", grade_scale_dict=grade_scale_dict),
        make_subject(5, 2, "1.25", grade_scale_dict=grade_scale_dict),
    ]
    res = evaluate(Decimal("17"), subjects, dl_rule_config, grade_scale_dict)
    assert res.computed_gwa == Decimal("1.5147")
    assert res.is_qualified is False
    assert res.status_text == "Not qualified"
    assert res.failed_rule_count == 1
    assert res.rule_results[0].label == "Lowest grade"
    assert res.rule_results[0].passed is False


# TC-03: 17 units all 2.0 -> GWA 2.0, fails GWA rule.
def test_tc03_fails_gwa(dl_rule_config, grade_scale_dict):
    subjects = [
        make_subject(0, 17, "2.0", grade_scale_dict=grade_scale_dict),
    ]
    res = evaluate(Decimal("17"), subjects, dl_rule_config, grade_scale_dict)
    assert res.computed_gwa == Decimal("2.0000")
    assert res.is_qualified is False
    assert res.failed_rule_count == 1
    assert res.rule_results[0].label == "GWA"
    assert res.rule_results[0].passed is False


# TC-04: 14 units 1.0 + 3 units 5.0 -> GWA 1.7059, fails lowest-grade and no-5.0 rules.
def test_tc04_fails_lowest_grade_and_no_5(dl_rule_config, grade_scale_dict):
    subjects = [
        make_subject(0, 14, "1.0", grade_scale_dict=grade_scale_dict),
        make_subject(1, 3, "5.0", grade_scale_dict=grade_scale_dict),
    ]
    res = evaluate(Decimal("17"), subjects, dl_rule_config, grade_scale_dict)
    assert res.computed_gwa == Decimal("1.7059")
    assert res.is_qualified is False
    assert res.failed_rule_count == 2
    failed_labels = [r.label for r in res.rule_results[:2]]
    assert "Lowest grade" in failed_labels
    assert "No 5.0, INC, or IP marks" in failed_labels


# TC-05: 14 units 1.5 + 3 units INC -> provisional GWA 1.5, fails INC rule.
def test_tc05_provisional_and_fails_inc(dl_rule_config, grade_scale_dict):
    subjects = [
        make_subject(0, 14, "1.5", grade_scale_dict=grade_scale_dict),
        make_subject(1, 3, "INC", grade_scale_dict=grade_scale_dict),
    ]
    res = evaluate(Decimal("17"), subjects, dl_rule_config, grade_scale_dict)
    assert res.computed_gwa == Decimal("1.5000")
    assert res.is_provisional is True
    assert res.is_qualified is False
    assert res.failed_rule_count == 1
    assert res.rule_results[0].label == "No 5.0, INC, or IP marks"


# TC-06: 15 units all 1.5, prescribed 17 -> fails full-load rule.
def test_tc06_fails_full_load(dl_rule_config, grade_scale_dict):
    subjects = [
        make_subject(0, 15, "1.5", grade_scale_dict=grade_scale_dict),
    ]
    res = evaluate(Decimal("17"), subjects, dl_rule_config, grade_scale_dict)
    assert res.computed_gwa == Decimal("1.5000")
    assert res.is_qualified is False
    assert res.failed_rule_count == 1
    assert res.rule_results[0].label == "Full load"


# TC-07: 9 units 1.25 + 9 units 2.25, load 18 -> GWA 1.75, qualifies.
def test_tc07_boundary_qualifies(dl_rule_config, grade_scale_dict):
    subjects = [
        make_subject(0, 9, "1.25", grade_scale_dict=grade_scale_dict),
        make_subject(1, 9, "2.25", grade_scale_dict=grade_scale_dict),
    ]
    res = evaluate(Decimal("18"), subjects, dl_rule_config, grade_scale_dict)
    assert res.computed_gwa == Decimal("1.7500")
    assert res.is_qualified is True
    assert res.failed_rule_count == 0


# TC-08: 3x1.25, 3x1.5, 3x2.0, 3x1.5, 2x1.25, 3x1.75 credit (17 units) + NSTP 3x1.25 non-credit -> GWA 1.5588, credited 17, total 20, non-credit 3, Equiv Grade 1.51, qualifies with prescribed 17 AND with prescribed 20.
def test_tc08_noncredit_nstp(dl_rule_config, grade_scale_dict):
    subjects = [
        make_subject(0, 3, "1.25", grade_scale_dict=grade_scale_dict),
        make_subject(1, 3, "1.5", grade_scale_dict=grade_scale_dict),
        make_subject(2, 3, "2.0", grade_scale_dict=grade_scale_dict),
        make_subject(3, 3, "1.5", grade_scale_dict=grade_scale_dict),
        make_subject(4, 2, "1.25", grade_scale_dict=grade_scale_dict),
        make_subject(5, 3, "1.75", grade_scale_dict=grade_scale_dict),
        make_subject(6, 3, "1.25", stype="noncredit", grade_scale_dict=grade_scale_dict),
    ]
    res17 = evaluate(Decimal("17"), subjects, dl_rule_config, grade_scale_dict)
    assert res17.computed_gwa == Decimal("1.5588")
    assert res17.credited_units == Decimal("17")
    assert res17.total_units == Decimal("20")
    assert res17.noncredit_units == Decimal("3")
    assert res17.equiv_grade == Decimal("1.51")
    assert res17.is_qualified is True

    res20 = evaluate(Decimal("20"), subjects, dl_rule_config, grade_scale_dict)
    assert res20.is_qualified is True


# TC-09: same as TC-08 but NSTP is 3x5.0 non-credit -> GWA 1.5588, fails lowest-grade and no-5.0 rules with the default setting; passes them when noncredit_checked_for_grade_rules = 0.
def test_tc09_noncredit_failing_grade(dl_rule_config, grade_scale_dict):
    subjects = [
        make_subject(0, 3, "1.25", grade_scale_dict=grade_scale_dict),
        make_subject(1, 3, "1.5", grade_scale_dict=grade_scale_dict),
        make_subject(2, 3, "2.0", grade_scale_dict=grade_scale_dict),
        make_subject(3, 3, "1.5", grade_scale_dict=grade_scale_dict),
        make_subject(4, 2, "1.25", grade_scale_dict=grade_scale_dict),
        make_subject(5, 3, "1.75", grade_scale_dict=grade_scale_dict),
        make_subject(6, 3, "5.0", stype="noncredit", grade_scale_dict=grade_scale_dict),
    ]
    # Default: noncredit_checked_for_grade_rules = 1 -> fails lowest-grade & no-5.0
    res_default = evaluate(Decimal("17"), subjects, dl_rule_config, grade_scale_dict)
    assert res_default.computed_gwa == Decimal("1.5588")
    assert res_default.is_qualified is False
    assert res_default.failed_rule_count == 2
    failed_labels = [r.label for r in res_default.rule_results[:2]]
    assert "Lowest grade" in failed_labels
    assert "No 5.0, INC, or IP marks" in failed_labels

    # When noncredit_checked_for_grade_rules = 0 -> passes
    cfg_ignored = DLRuleConfig(
        max_gwa=dl_rule_config.max_gwa,
        worst_allowed_grade=dl_rule_config.worst_allowed_grade,
        require_full_load=dl_rule_config.require_full_load,
        max_subject_units=dl_rule_config.max_subject_units,
        max_prescribed_units=dl_rule_config.max_prescribed_units,
        noncredit_checked_for_grade_rules=0,
    )
    res_ignored = evaluate(Decimal("17"), subjects, cfg_ignored, grade_scale_dict)
    assert res_ignored.is_qualified is True
    assert res_ignored.failed_rule_count == 0


# TC-10: 8 subjects of 3 units each, all 1.5 (24 units), prescribed 24 -> GWA 1.5, qualifies (no unit cap).
def test_tc10_heavy_load_no_cap(dl_rule_config, grade_scale_dict):
    subjects = [make_subject(i, 3, "1.5", grade_scale_dict=grade_scale_dict) for i in range(8)]
    res = evaluate(Decimal("24"), subjects, dl_rule_config, grade_scale_dict)
    assert res.total_units == Decimal("24")
    assert res.computed_gwa == Decimal("1.5000")
    assert res.is_qualified is True


# TC-11 (SIAS screen): CC 101 1.25x3, GEC 1 1.5x3, GEC 4 2.0x3, GEC 7 1.5x3, NSTP 1 1.25x3 non-credit, EN+ 1.75x3, PE 1 1.25x2, prescribed 20 -> WAvg 1.5588, Equiv Grade 1.51, total 20, credited 17, qualifies. Prescribed 17 also qualifies. Prescribed 21 fails only the full-load rule.
def test_tc11_sias_screen(dl_rule_config, grade_scale_dict):
    subjects = [
        SubjectInput(0, "CC 101", "credit", Decimal("3"), "1.25", Decimal("1.25"), False),
        SubjectInput(1, "GEC 1", "credit", Decimal("3"), "1.5", Decimal("1.5"), False),
        SubjectInput(2, "GEC 4", "credit", Decimal("3"), "2.0", Decimal("2.0"), False),
        SubjectInput(3, "GEC 7", "credit", Decimal("3"), "1.5", Decimal("1.5"), False),
        SubjectInput(4, "NSTP 1", "noncredit", Decimal("3"), "1.25", Decimal("1.25"), False),
        SubjectInput(5, "EN+", "credit", Decimal("3"), "1.75", Decimal("1.75"), False),
        SubjectInput(6, "PE 1", "credit", Decimal("2"), "1.25", Decimal("1.25"), False),
    ]
    res20 = evaluate(Decimal("20"), subjects, dl_rule_config, grade_scale_dict)
    assert res20.computed_gwa == Decimal("1.5588")
    assert res20.equiv_grade == Decimal("1.51")
    assert res20.total_units == Decimal("20")
    assert res20.credited_units == Decimal("17")
    assert res20.is_qualified is True

    res17 = evaluate(Decimal("17"), subjects, dl_rule_config, grade_scale_dict)
    assert res17.is_qualified is True

    res21 = evaluate(Decimal("21"), subjects, dl_rule_config, grade_scale_dict)
    assert res21.is_qualified is False
    assert res21.failed_rule_count == 1
    assert res21.rule_results[0].label == "Full load"


def test_standing_bar_position():
    # 1.0 gives 0, 1.75 gives 0.375, 2.0 gives 0.5, 3.0 and above give 1, values below 1.0 give 0
    assert compute_standing_position(Decimal("1.0")) == 0.0
    assert compute_standing_position(Decimal("1.75")) == 0.375
    assert compute_standing_position(Decimal("2.0")) == 0.5
    assert compute_standing_position(Decimal("3.0")) == 1.0
    assert compute_standing_position(Decimal("3.5")) == 1.0
    assert compute_standing_position(Decimal("0.8")) == 0.0
    assert compute_standing_position(None) == 0.0


def test_sias_notices():
    # Notice 1: matches COG/SIAS GWA within 0.0001
    n1 = compare_sias(Decimal("1.5588"), Decimal("1.51"), Decimal("1.5588"), has_noncredit=True)
    assert "Matches: this is the same as the GWA you entered" in n1

    # Notice 2: matches equiv grade (noncredit units present)
    n2 = compare_sias(Decimal("1.5588"), Decimal("1.51"), Decimal("1.51"), has_noncredit=True)
    assert "matches the equivalent grade / total" in n2

    # Notice 3: differs
    n3 = compare_sias(Decimal("1.5588"), Decimal("1.51"), Decimal("1.45"), has_noncredit=True)
    assert "Heads up: your COG/SIAS GWA differs from this result." in n3


def test_validation_form(dl_rule_config, grade_scale_dict):
    # Empty prescribed units
    data, errs = validate_form({}, dl_rule_config, grade_scale_dict)
    assert any("Prescribed units is required." in e for e in errs)

    # Subject error naming fields: units <= 0, missing grade
    form = {
        "prescribed_units": "18",
        "name_0": "Algebra",
        "units_0": "0",
        "mark_0": "1.5",
        "name_1": "Physics",
        "units_1": "3",
        "mark_1": "",
    }
    data, errs = validate_form(form, dl_rule_config, grade_scale_dict)
    assert any('Subject 1: "Units" must be a number greater than 0.' in e for e in errs)
    assert any('Subject 2: "Final grade" is required.' in e for e in errs)

    # Blank row ignored
    form_blank = {
        "prescribed_units": "18",
        "name_0": "",
        "units_0": "",
        "mark_0": "",
        "name_1": "Calculus",
        "units_1": "3",
        "mark_1": "1.5",
    }
    data, errs = validate_form(form_blank, dl_rule_config, grade_scale_dict)
    assert len(errs) == 0
    assert len(data["subjects"]) == 1
    assert data["subjects"][0].name == "Calculus"
