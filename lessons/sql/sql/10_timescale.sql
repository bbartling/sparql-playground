DO $$ BEGIN
 IF current_database() <> 'brickts_course' THEN
   RAISE EXCEPTION 'Course SQL requires dedicated database brickts_course; no writes performed';
 END IF;
END $$;

-- Opt-in week10: changes only course.sample in the dedicated database.
CREATE EXTENSION IF NOT EXISTS timescaledb;
SELECT extversion FROM pg_extension WHERE extname='timescaledb';
SELECT create_hypertable('course.sample',by_range('ts',interval '1 day'),
 migrate_data=>true,if_not_exists=>true);
SELECT time_bucket(interval '1 hour',ts) AS bucket,count(*) AS samples
FROM course.sample WHERE ts>='2026-01-05T00:00:00Z' AND ts<'2026-01-06T00:00:00Z'
GROUP BY bucket ORDER BY bucket;
