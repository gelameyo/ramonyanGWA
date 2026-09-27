import os
import sqlite3
import pytest
from decimal import Decimal
from dl_rules import DLRuleConfig, GradeScaleItem


@pytest.fixture
def db_conn(tmp_path):
    """Creates a fresh test SQLite database populated from schema.sql."""
    db_file = tmp_path / "test_deans_list.db"
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    with open("schema.sql", "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    yield conn
    conn.close()


@pytest.fixture
def grade_scale_dict(db_conn):
    """Loads grade_scale from database as dict of GradeScaleItem."""
    cur = db_conn.cursor()
    cur.execute("SELECT mark, grade_point, min_percent, max_percent, blocks_dl FROM grade_scale")
    result = {}
    for row in cur.fetchall():
        result[row["mark"]] = GradeScaleItem(
            mark=row["mark"],
            grade_point=Decimal(str(row["grade_point"])) if row["grade_point"] is not None else None,
            min_percent=row["min_percent"],
            max_percent=row["max_percent"],
            blocks_dl=row["blocks_dl"],
        )
    return result


@pytest.fixture
def dl_rule_config(db_conn):
    """Loads dl_rule from database as DLRuleConfig."""
    cur = db_conn.cursor()
    cur.execute("SELECT * FROM dl_rule WHERE rule_id = 1")
    row = cur.fetchone()
    return DLRuleConfig(
        rule_id=row["rule_id"],
        max_gwa=Decimal(str(row["max_gwa"])),
        worst_allowed_grade=Decimal(str(row["worst_allowed_grade"])),
        require_full_load=row["require_full_load"],
        max_subject_units=Decimal(str(row["max_subject_units"])),
        max_prescribed_units=Decimal(str(row["max_prescribed_units"])),
        noncredit_checked_for_grade_rules=row["noncredit_checked_for_grade_rules"],
    )
