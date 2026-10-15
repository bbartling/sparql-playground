DO $$ BEGIN
 IF current_database() <> 'brickts_course' THEN
   RAISE EXCEPTION 'Course SQL requires dedicated database brickts_course; no writes performed';
 END IF;
END $$;

-- Opt-in scratch aggregate. No automatic policy or retention job is installed.
CREATE MATERIALIZED VIEW IF NOT EXISTS student.hourly_point
WITH(timescaledb.continuous) AS
 SELECT site_id,point_id,time_bucket(interval '1 hour',ts) AS bucket,
 avg(value) FILTER(WHERE quality='good') AS mean_value,
 count(*) FILTER(WHERE quality='good' AND value IS NOT NULL) AS valid_samples
 FROM course.sample GROUP BY site_id,point_id,bucket WITH NO DATA;
CALL refresh_continuous_aggregate('student.hourly_point','2026-01-05T00:00:00Z','2026-01-07T00:00:00Z');
SELECT count(*) AS aggregate_rows FROM student.hourly_point;
