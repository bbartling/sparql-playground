DO $$ BEGIN
 IF current_database() <> 'brickts_course' THEN
   RAISE EXCEPTION 'Course SQL requires dedicated database brickts_course';
 END IF;
 IF NOT EXISTS (SELECT FROM timescaledb_information.hypertables
   WHERE hypertable_schema='course' AND hypertable_name='sample') THEN
   RAISE EXCEPTION 'course.sample is not a hypertable';
 END IF;
 IF (SELECT count(*) FROM student.hourly_point)<>2016 THEN
   RAISE EXCEPTION 'continuous aggregate row count';
 END IF;
 IF NOT EXISTS (
   SELECT FROM student.hourly_point h JOIN course.point p USING(site_id,point_id)
   JOIN course.equipment e USING(site_id,equipment_id)
   WHERE h.site_id='SYN-NORTH' AND e.label='Supply A' AND p.role='kw'
    AND h.bucket='2026-01-05T15:00:00Z'::timestamptz
    AND h.valid_samples=11 AND abs(h.mean_value-12)<1e-8
 ) THEN RAISE EXCEPTION 'continuous aggregate lost quality policy'; END IF;
END $$;
SELECT 'PASS: hypertable and 2016 hourly aggregates, including bad-sample coverage' AS result;
