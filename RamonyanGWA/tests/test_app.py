import html
import pytest
from app import app, get_db


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        with app.app_context():
            get_db()
        yield client


def test_home_page(client):
    res = client.get("/")
    assert res.status_code == 200
    page_text = res.data.decode("utf-8")
    assert "RamonyanGWA" in page_text
    assert "Check your GWA and Dean's List standing" in page_text
    # Check 8 default rows exist
    for i in range(8):
        assert f'name="units_{i}"' in page_text
        assert f'name="mark_{i}"' in page_text


def test_redirects(client):
    res_result = client.get("/result")
    assert res_result.status_code == 302
    assert res_result.headers["Location"] == "/"

    res_edit = client.get("/edit")
    assert res_edit.status_code == 302
    assert res_edit.headers["Location"] == "/"


def test_post_result_validation_failure(client):
    # Missing prescribed units, invalid units, missing grade
    data = {
        "prescribed_units": "",
        "name_0": "Math 101",
        "type_0": "credit",
        "units_0": "-2",
        "mark_0": "",
    }
    res = client.post("/result", data=data)
    assert res.status_code == 400
    page_text = html.unescape(res.data.decode("utf-8"))
    assert "Prescribed units is required." in page_text
    assert 'Subject 1: "Units" must be a number greater than 0.' in page_text
    assert 'Subject 1: "Final grade" is required.' in page_text
    # Retains entered value
    assert "Math 101" in page_text


def test_post_result_unqualified_shows_wavg_and_equiv(client):
    # Fails GWA rule: 5x3 units + 1x2 units all 2.0 = 17 units at 2.0 (GWA = 2.0)
    data = {
        "prescribed_units": "17",
        "name_0": "Subject 1", "type_0": "credit", "units_0": "3", "mark_0": "2.0",
        "name_1": "Subject 2", "type_1": "credit", "units_1": "3", "mark_1": "2.0",
        "name_2": "Subject 3", "type_2": "credit", "units_2": "3", "mark_2": "2.0",
        "name_3": "Subject 4", "type_3": "credit", "units_3": "3", "mark_3": "2.0",
        "name_4": "Subject 5", "type_4": "credit", "units_4": "3", "mark_4": "2.0",
        "name_5": "Subject 6", "type_5": "credit", "units_5": "2", "mark_5": "2.0",
    }
    res = client.post("/result", data=data)
    assert res.status_code == 200
    page_text = res.data.decode("utf-8")
    assert "Not qualified" in page_text
    # SIAS Comparison Card shown even when unqualified
    assert "Semester GWA" in page_text
    assert "WAvg (credit units only)" in page_text
    assert "Equiv Grade (all units)" in page_text
    assert "2.0000" in page_text


def test_post_edit_preserves_values_and_type(client):
    data = {
        "prescribed_units": "20",
        "cog_gwa": "1.5588",
        "name_0": "NSTP 1",
        "type_0": "noncredit",
        "units_0": "3",
        "mark_0": "1.25",
        "name_1": "CC 101",
        "type_1": "credit",
        "units_1": "3",
        "mark_1": "1.5",
    }
    res = client.post("/edit", data=data)
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert 'value="20"' in html
    assert 'value="1.5588"' in html
    assert 'value="NSTP 1"' in html
    # Verify noncredit is selected
    assert 'value="noncredit" selected' in html or 'selected value="noncredit"' in html or '<option value="noncredit" selected>' in html


def test_no_user_data_written_to_db(client):
    with app.app_context():
        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT COUNT(*) FROM grade_scale")
        gs_count_before = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM dl_rule")
        dl_count_before = cur.fetchone()[0]

    data = {
        "prescribed_units": "18",
        "cog_gwa": "1.5000",
        "name_0": "Secret Course",
        "type_0": "credit",
        "units_0": "3",
        "mark_0": "1.5",
    }
    client.post("/result", data=data)

    with app.app_context():
        db = get_db()
        cur = db.cursor()
        # Verify no new tables created
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        assert set(tables) == {"grade_scale", "dl_rule"}

        # Verify no new rows in grade_scale or dl_rule
        cur.execute("SELECT COUNT(*) FROM grade_scale")
        assert cur.fetchone()[0] == gs_count_before
        cur.execute("SELECT COUNT(*) FROM dl_rule")
        assert cur.fetchone()[0] == dl_count_before
