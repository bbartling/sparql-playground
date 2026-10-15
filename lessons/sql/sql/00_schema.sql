DO $$ BEGIN
 IF current_database() <> 'brickts_course' THEN
   RAISE EXCEPTION 'Course SQL requires dedicated database brickts_course; no writes performed';
 END IF;
END $$;

-- This file is course DDL, not an Open-FDD production migration.
BEGIN;
DO $$ BEGIN
 IF to_regnamespace('course') IS NOT NULL AND to_regclass('course.lab_meta') IS NULL THEN
   RAISE EXCEPTION 'Existing unmarked course schema: stop and review ownership';
 END IF;
END $$;
CREATE SCHEMA IF NOT EXISTS course;
CREATE SCHEMA IF NOT EXISTS student;
CREATE TABLE IF NOT EXISTS course.lab_meta (
 singleton boolean PRIMARY KEY CHECK(singleton), schema_version integer NOT NULL,
 purpose text NOT NULL CHECK(purpose='brickts synthetic SQL course')
);
INSERT INTO course.lab_meta VALUES (true,1,'brickts synthetic SQL course') ON CONFLICT DO NOTHING;
DO $$ BEGIN
 IF NOT EXISTS(SELECT FROM course.lab_meta WHERE singleton AND schema_version=1
  AND purpose='brickts synthetic SQL course') THEN RAISE EXCEPTION 'Wrong course schema revision'; END IF;
END $$;
CREATE TABLE IF NOT EXISTS course.site (
 site_id text PRIMARY KEY, label text NOT NULL, tz text NOT NULL
);
CREATE TABLE IF NOT EXISTS course.equipment (
 equipment_id uuid PRIMARY KEY, site_id text NOT NULL REFERENCES course.site,
 label text NOT NULL, kind text NOT NULL, UNIQUE(site_id,equipment_id)
);
CREATE TABLE IF NOT EXISTS course.point (
 point_id uuid PRIMARY KEY, site_id text NOT NULL, equipment_id uuid NOT NULL,
 role text NOT NULL CHECK(length(role)>0), unit text NOT NULL,
 UNIQUE(site_id,point_id), FOREIGN KEY(site_id,equipment_id)
 REFERENCES course.equipment(site_id,equipment_id)
);
CREATE TABLE IF NOT EXISTS course.sample (
 site_id text NOT NULL, point_id uuid NOT NULL, ts timestamptz NOT NULL,
 value double precision, quality text NOT NULL CHECK(quality IN ('good','bad','missing')),
 PRIMARY KEY(site_id,point_id,ts), FOREIGN KEY(site_id,point_id) REFERENCES course.point(site_id,point_id),
 CHECK(value IS NULL OR value NOT IN ('NaN'::float8,'Infinity'::float8,'-Infinity'::float8))
);
CREATE INDEX IF NOT EXISTS sample_point_time ON course.sample(point_id,ts DESC);
CREATE OR REPLACE VIEW course.history AS
 SELECT s.site_id,p.equipment_id,e.label AS equipment_label,e.kind AS equipment_kind,
 p.point_id,p.role,p.unit,s.ts,s.value,s.quality
 FROM course.sample s JOIN course.point p USING(site_id,point_id)
 JOIN course.equipment e ON (e.site_id,e.equipment_id)=(p.site_id,p.equipment_id);
CREATE OR REPLACE VIEW course.ahu_5m AS
 SELECT site_id,equipment_id,equipment_label,ts,
 max(value) FILTER(WHERE role='duct_static' AND quality='good') AS duct_static,
 max(value) FILTER(WHERE role='duct_static_sp' AND quality='good') AS duct_static_sp,
 max(value) FILTER(WHERE role='fan_status' AND quality='good') AS fan_status,
 max(value) FILTER(WHERE role='fan_speed_pct' AND quality='good') AS fan_speed_pct,
 max(value) FILTER(WHERE role='kw' AND quality='good') AS kw,
 max(value) FILTER(WHERE role='sat' AND quality='good') AS sat,
 max(value) FILTER(WHERE role='sat_sp' AND quality='good') AS sat_sp,
 max(value) FILTER(WHERE role='rat' AND quality='good') AS rat,
 max(value) FILTER(WHERE role='oat' AND quality='good') AS oat,
 max(value) FILTER(WHERE role='mat' AND quality='good') AS mat,
 max(value) FILTER(WHERE role='damper_pct' AND quality='good') AS damper_pct,
 max(value) FILTER(WHERE role='cooling_pct' AND quality='good') AS cooling_pct,
 max(value) FILTER(WHERE role='zone_temp' AND quality='good') AS zone_temp,
 max(value) FILTER(WHERE role='zone_temp_sp' AND quality='good') AS zone_temp_sp
 FROM course.history GROUP BY site_id,equipment_id,equipment_label,ts;
COMMIT;
