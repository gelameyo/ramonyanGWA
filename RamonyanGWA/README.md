# RamonyanGWA

> Check your GWA and Dean's List standing.

**RamonyanGWA** is a lightweight, privacy-first web application designed for students of President Ramon Magsaysay State University to compute their semester General Weighted Average (GWA) and determine Dean's List eligibility. Figures match the official SIAS Term Grades screen and the printed Certificate of Grades (COG).

---

## Features

- **Accurate GWA Calculation:** Computes GWA rounded half-up to 4 decimal places over credited courses only.
- **Dean's List Evaluation:** Evaluates the 4 university Dean's List criteria:
  1. GWA $\le$ 1.75
  2. Lowest grade $\le$ 2.25 (no grades of 2.5, 2.75, 3.0, or 5.0)
  3. No 5.0, INC, or IP marks (INC/IP are excluded from GWA calculation and flagged provisional)
  4. Full semester load met or exceeded (credited units + non-credit units such as NSTP)
- **SIAS & COG Term Grades Verification:** Computes Equivalent Grade (all units, 2 decimals) and compares entered COG/SIAS GWA against official calculation.
- **Live Units Meter:** Real-time feedback comparing entered total units against your prescribed load.
- **Zero Data Retention:** No accounts, no student ID, and no names are recorded. The SQLite database only stores institutional reference tables (`grade_scale` and `dl_rule`).
- **Completely Self-Contained:** Zero external CDNs, fonts, or scripts. System fonts and inline SVG icons only.

---

## Project Structure

```text
RamonyanGWA/
├── app.py                # Flask application routes and SQLite configuration loading
├── dl_rules.py           # Pure Python module for business logic, validation, and evaluations
├── schema.sql            # Idempotent SQLite database schema and seed data
├── public/
│   ├── style.css         # Custom responsive CSS with university palette and dark mode
│   └── app.js            # Vanilla JS for live units meter and dynamic subject rows
├── templates/
│   ├── base.html         # Base Jinja template with header, footer, and info strip
│   ├── index.html        # Home calculation form with semester load and course entry
│   └── result.html       # Result screen with badge, standing bar, SIAS comparison, and rule cards
├── tests/
│   ├── conftest.py       # Pytest fixtures and database test initialization
│   ├── test_dl_rules.py  # Unit tests for TC-01 to TC-11, standing bar, and SIAS notices
│   └── test_app.py       # Integration tests for Flask routes, validation, and zero DB writes
├── requirements.txt      # Production dependencies (Flask)
├── requirements-dev.txt  # Development dependencies (pytest)
├── .gitignore            # Git ignore rules
└── README.md             # Project documentation and deployment guide
```

---

## Quick Start (Local Run)

### Prerequisites

- Python 3.10+

### Setup & Run

1. Clone or open the repository folder:
   ```bash
   cd RamonyanGWA
   ```

2. (Optional) Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # Windows PowerShell:
   .venv\Scripts\Activate.ps1
   # Linux / macOS:
   source .venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the Flask application:
   ```bash
   python app.py
   ```

5. Open your browser and navigate to:
   ```text
   http://127.0.0.1:5000/
   ```

---

## Running Tests

Install development requirements and run pytest:

```bash
pip install -r requirements-dev.txt
pytest -v
```

The test suite covers:
- **TC-01 to TC-11:** Qualifying cases, lowest-grade failures, GWA limit failures, 5.0/INC/IP failures, provisional GWA, full load checks, non-credit NSTP handling, and heavy semester loads (24+ units).
- **Standing Bar Position:** Validates exact math mapping across the 1.0 to 3.0 scale.
- **SIAS Notices:** Tests matching, equivalent grade differences, and discrepancy warnings.
- **Flask Endpoints:** Tests status 400 validation error preservation, redirects, and database read-only invariants.

---

## Deploying to Vercel

RamonyanGWA is built to deploy on Vercel with zero configuration from a Git repository:

1. Push this repository to GitHub or GitLab.
2. In the Vercel Dashboard, select **Add New Project** and import the repository.
3. Vercel will automatically detect the Python WSGI app via `app.py`.
4. When `VERCEL` is set in the runtime environment, the app automatically mounts reference data at `/tmp/deans_list.db` to work with Vercel's read-only serverless filesystem.
5. Static files located in `public/` are served automatically.

---

## Disclaimer

RamonyanGWA is made by a student for Ramonians. This application is not an official university system; please confirm your official academic standing with the registrar.
