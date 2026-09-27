CREATE TABLE IF NOT EXISTS grade_scale (
  mark         TEXT PRIMARY KEY,           -- '1.0','1.25',...,'3.0','5.0','INC','IP'
  grade_point  REAL,                       -- NULL for INC and IP
  min_percent  INTEGER,
  max_percent  INTEGER,
  blocks_dl    INTEGER NOT NULL DEFAULT 0  -- 1 for '5.0','INC','IP'
);

CREATE TABLE IF NOT EXISTS dl_rule (
  rule_id                           INTEGER PRIMARY KEY CHECK (rule_id = 1),
  max_gwa                           REAL    NOT NULL DEFAULT 1.75,
  worst_allowed_grade               REAL    NOT NULL DEFAULT 2.25,
  require_full_load                 INTEGER NOT NULL DEFAULT 1,
  max_subject_units                 REAL    NOT NULL DEFAULT 12,
  max_prescribed_units              REAL    NOT NULL DEFAULT 40,
  noncredit_checked_for_grade_rules INTEGER NOT NULL DEFAULT 1
);

INSERT OR IGNORE INTO grade_scale (mark, grade_point, min_percent, max_percent, blocks_dl) VALUES
  ('1.0',1.0,99,100,0), ('1.25',1.25,96,98,0), ('1.5',1.5,93,95,0), ('1.75',1.75,90,92,0),
  ('2.0',2.0,87,89,0), ('2.25',2.25,84,86,0), ('2.5',2.5,81,83,0), ('2.75',2.75,78,80,0),
  ('3.0',3.0,75,77,0), ('5.0',5.0,NULL,NULL,1), ('INC',NULL,NULL,NULL,1), ('IP',NULL,NULL,NULL,1);

INSERT OR IGNORE INTO dl_rule (rule_id) VALUES (1);
