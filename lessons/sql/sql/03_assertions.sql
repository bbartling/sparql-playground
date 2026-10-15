DO $$ BEGIN
 IF current_database() <> 'brickts_course' THEN
   RAISE EXCEPTION 'Course SQL requires dedicated database brickts_course; no writes performed';
 END IF;
END $$;

-- These are fixture and integrity checks, not solutions to weekly challenges.
BEGIN;
DO $$ BEGIN
 IF (SELECT count(*) FROM course.site)<>2 THEN RAISE EXCEPTION 'site count'; END IF;
 IF (SELECT count(*) FROM course.equipment)<>3 THEN RAISE EXCEPTION 'equipment count'; END IF;
 IF (SELECT count(*) FROM course.point)<>42 THEN RAISE EXCEPTION 'point count'; END IF;
 IF (SELECT count(*) FROM course.sample)<>24190 THEN RAISE EXCEPTION 'sample count'; END IF;
 IF (SELECT count(*) FROM course.sample WHERE quality='bad' AND value IS NULL)<>1 THEN RAISE EXCEPTION 'quality count'; END IF;
 IF (SELECT count(*) FROM course.sample WHERE site_id='SYN-NORTH')<>16126 THEN RAISE EXCEPTION 'north count'; END IF;
 IF abs((SELECT sum(value)*300.0/3600 FROM course.history WHERE role='kw' AND quality='good')-467)>1e-8 THEN RAISE EXCEPTION 'energy integral'; END IF;
 IF (SELECT count(*) FROM course.ahu_5m WHERE site_id='SYN-NORTH' AND equipment_label='Supply A' AND fan_status=1)<>288 THEN RAISE EXCEPTION 'runtime'; END IF;
 IF (SELECT count(*) FROM course.ahu_5m WHERE fan_status=1 AND duct_static<0.9*duct_static_sp)<>10 THEN RAISE EXCEPTION 'raw teaching fault'; END IF;
END $$;
-- Reject a cross-site point even though both individual ids are otherwise valid.
DO $$ BEGIN
 BEGIN
 INSERT INTO course.sample SELECT 'SYN-SOUTH',point_id,'2030-01-01T00:00:00Z',1,'good'
 FROM course.point WHERE site_id='SYN-NORTH' LIMIT 1;
 RAISE EXCEPTION 'cross-site negative unexpectedly accepted';
 EXCEPTION WHEN foreign_key_violation THEN NULL; END;
 BEGIN
 INSERT INTO course.sample SELECT site_id,point_id,'2030-01-01T00:00:00Z','NaN'::float8,'good' FROM course.point LIMIT 1;
 RAISE EXCEPTION 'nonfinite negative unexpectedly accepted';
 EXCEPTION WHEN check_violation THEN NULL; END;
END $$;
ROLLBACK;
SELECT 'PASS: fixture counts, units-based integral, sample identity and negative constraints' AS result;
