"""
RamonyanGWA - Flask Application
Exposes `app` for running locally and deploying on Vercel.
Routes and SQLite configuration loading only, no rule logic.
"""

import os
import re
import sqlite3
from decimal import Decimal
from flask import Flask, render_template, request, redirect, url_for, g

from dl_rules import (
    DLRuleConfig,
    GradeScaleItem,
    validate_form,
    evaluate,
)

app = Flask(__name__, static_folder="public", static_url_path="")


def get_db_path() -> str:
    """Returns /tmp/deans_list.db on Vercel, otherwise deans_list.db in project dir."""
    if os.environ.get("VERCEL"):
        return "/tmp/deans_list.db"
    return os.path.join(os.path.dirname(__file__), "deans_list.db")


def get_db() -> sqlite3.Connection:
    """Gets or creates SQLite connection in Flask's application context."""
    if "db" not in g:
        db_path = get_db_path()
        init_needed = not os.path.exists(db_path)
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row
        if init_needed:
            init_db(g.db)
        else:
            check_and_migrate_db(g.db)
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    """Closes database connection at end of request."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(conn: sqlite3.Connection):
    """Initializes the database using schema.sql."""
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    if os.path.exists(schema_path):
        with open(schema_path, "r", encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.commit()


def check_and_migrate_db(conn: sqlite3.Connection):
    """Checks for existing tables and performs migrations if any columns are missing."""
    cur = conn.cursor()
    # Check if tables exist
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='dl_rule'")
    if not cur.fetchone():
        init_db(conn)
        return

    # Check dl_rule columns
    cur.execute("PRAGMA table_info(dl_rule)")
    existing_cols = {row["name"] for row in cur.fetchall()}
    needed_cols = {
        "rule_id": "INTEGER PRIMARY KEY CHECK (rule_id = 1)",
        "max_gwa": "REAL NOT NULL DEFAULT 1.75",
        "worst_allowed_grade": "REAL NOT NULL DEFAULT 2.25",
        "require_full_load": "INTEGER NOT NULL DEFAULT 1",
        "max_subject_units": "REAL NOT NULL DEFAULT 12",
        "max_prescribed_units": "REAL NOT NULL DEFAULT 40",
        "noncredit_checked_for_grade_rules": "INTEGER NOT NULL DEFAULT 1",
    }
    for col, col_def in needed_cols.items():
        if col not in existing_cols:
            cur.execute(f"ALTER TABLE dl_rule ADD COLUMN {col} {col_def}")
    conn.commit()


def load_grade_scale(conn: sqlite3.Connection):
    """Loads grade_scale rows and returns dict of GradeScaleItem and list for display."""
    cur = conn.cursor()
    cur.execute(
        "SELECT mark, grade_point, min_percent, max_percent, blocks_dl "
        "FROM grade_scale ORDER BY "
        "CASE WHEN grade_point IS NULL THEN 999 ELSE grade_point END ASC"
    )
    rows = cur.fetchall()
    gs_dict = {}
    gs_list = []
    for r in rows:
        item = GradeScaleItem(
            mark=r["mark"],
            grade_point=Decimal(str(r["grade_point"])) if r["grade_point"] is not None else None,
            min_percent=r["min_percent"],
            max_percent=r["max_percent"],
            blocks_dl=r["blocks_dl"],
        )
        gs_dict[r["mark"]] = item
        gs_list.append(item)
    return gs_dict, gs_list


def load_dl_rule(conn: sqlite3.Connection) -> DLRuleConfig:
    """Loads dl_rule row."""
    cur = conn.cursor()
    cur.execute("SELECT * FROM dl_rule WHERE rule_id = 1")
    r = cur.fetchone()
    if not r:
        init_db(conn)
        cur.execute("SELECT * FROM dl_rule WHERE rule_id = 1")
        r = cur.fetchone()

    return DLRuleConfig(
        rule_id=r["rule_id"],
        max_gwa=Decimal(str(r["max_gwa"])),
        worst_allowed_grade=Decimal(str(r["worst_allowed_grade"])),
        require_full_load=r["require_full_load"],
        max_subject_units=Decimal(str(r["max_subject_units"])),
        max_prescribed_units=Decimal(str(r["max_prescribed_units"])),
        noncredit_checked_for_grade_rules=r["noncredit_checked_for_grade_rules"],
    )


def extract_form_rows(form: dict, min_rows: int = 8) -> list:
    """Extracts subject rows from form data and ensures at least min_rows."""
    key_pattern = re.compile(r"^(name|type|units|mark)_(\d+)$")
    row_indices = set()
    for k in form.keys():
        match = key_pattern.match(k)
        if match:
            row_indices.add(int(match.group(2)))

    sorted_indices = sorted(list(row_indices))
    rows = []
    for idx in sorted_indices:
        rows.append({
            "index": idx,
            "name": form.get(f"name_{idx}", "").strip(),
            "type": form.get(f"type_{idx}", "credit").strip().lower(),
            "units": form.get(f"units_{idx}", "").strip(),
            "mark": form.get(f"mark_{idx}", "").strip(),
        })

    # Pad with empty rows if needed
    next_idx = max(sorted_indices) + 1 if sorted_indices else 0
    while len(rows) < min_rows:
        rows.append({
            "index": next_idx,
            "name": "",
            "type": "credit",
            "units": "",
            "mark": "",
        })
        next_idx += 1

    return rows


@app.route("/", methods=["GET"])
def index():
    """Home page with 8 default empty rows."""
    conn = get_db()
    gs_dict, gs_list = load_grade_scale(conn)
    dl_config = load_dl_rule(conn)

    default_rows = [
        {"index": i, "name": "", "type": "credit", "units": "", "mark": ""}
        for i in range(8)
    ]

    return render_template(
        "index.html",
        prescribed_units="",
        cog_gwa="",
        rows=default_rows,
        errors=[],
        grade_scale_list=gs_list,
        dl_config=dl_config,
    )


@app.route("/result", methods=["GET"])
def result_get():
    """Redirect GET /result to /."""
    return redirect(url_for("index"))


@app.route("/result", methods=["POST"])
def result_post():
    """Validates input, runs Dean's List evaluation, and renders result or error."""
    conn = get_db()
    gs_dict, gs_list = load_grade_scale(conn)
    dl_config = load_dl_rule(conn)

    cleaned_data, errors = validate_form(request.form, dl_config, gs_dict)

    if errors:
        rows = extract_form_rows(request.form)
        return (
            render_template(
                "index.html",
                prescribed_units=request.form.get("prescribed_units", "").strip(),
                cog_gwa=request.form.get("cog_gwa", "").strip(),
                rows=rows,
                errors=errors,
                grade_scale_list=gs_list,
                dl_config=dl_config,
            ),
            400,
        )

    # Validated, evaluate rules
    eval_result = evaluate(
        prescribed_units=cleaned_data["prescribed_units"],
        subjects=cleaned_data["subjects"],
        rule_config=dl_config,
        grade_scale_dict=gs_dict,
        entered_cog_gwa=cleaned_data["cog_gwa"],
    )

    # Raw rows for Edit grades form submission
    raw_subjects = [
        {
            "name": s.name,
            "type": s.subject_type,
            "units": str(s.units),
            "mark": s.mark,
        }
        for s in cleaned_data["subjects"]
    ]

    return render_template(
        "result.html",
        eval_result=eval_result,
        prescribed_units=str(cleaned_data["prescribed_units"]),
        cog_gwa=str(cleaned_data["cog_gwa"]) if cleaned_data["cog_gwa"] is not None else "",
        raw_subjects=raw_subjects,
        grade_scale_list=gs_list,
        dl_config=dl_config,
    )


@app.route("/edit", methods=["GET"])
def edit_get():
    """Redirect GET /edit to /."""
    return redirect(url_for("index"))


@app.route("/edit", methods=["POST"])
def edit_post():
    """Preserves all previously entered values and returns to index page."""
    conn = get_db()
    gs_dict, gs_list = load_grade_scale(conn)
    dl_config = load_dl_rule(conn)

    rows = extract_form_rows(request.form)

    return render_template(
        "index.html",
        prescribed_units=request.form.get("prescribed_units", "").strip(),
        cog_gwa=request.form.get("cog_gwa", "").strip(),
        rows=rows,
        errors=[],
        grade_scale_list=gs_list,
        dl_config=dl_config,
    )


# Ensure DB is created if running directly
with app.app_context():
    get_db()

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
