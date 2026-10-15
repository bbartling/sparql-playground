DO $$ BEGIN
 IF current_database() <> 'brickts_course' THEN
   RAISE EXCEPTION 'Course SQL requires dedicated database brickts_course; no writes performed';
 END IF;
END $$;

BEGIN;
INSERT INTO course.site VALUES ('SYN-NORTH','Synthetic North','America/Chicago'),
 ('SYN-SOUTH','Synthetic South','America/New_York') ON CONFLICT(site_id) DO NOTHING;
INSERT INTO course.equipment(equipment_id,site_id,label,kind) VALUES ('1c58e3a1-a7b0-5816-a319-d3f846785281','SYN-NORTH','Supply A','ahu'),('98377177-dee0-5f28-93f7-f78650f57a48','SYN-NORTH','Supply B','ahu'),('2c0c3077-c005-5a27-b4d2-06a2976650df','SYN-SOUTH','Supply A','ahu')
 ON CONFLICT(equipment_id) DO NOTHING;
INSERT INTO course.point(point_id,site_id,equipment_id,role,unit) VALUES ('7ac98403-4a93-59b9-8bda-603d8d1949f3','SYN-NORTH','1c58e3a1-a7b0-5816-a319-d3f846785281','duct_static','Pa'),('b49d7f7d-79a9-5e8c-a1d0-83dedace17b2','SYN-NORTH','1c58e3a1-a7b0-5816-a319-d3f846785281','duct_static_sp','Pa'),('471cd2bb-e6da-509a-a509-184ad2a68f2e','SYN-NORTH','1c58e3a1-a7b0-5816-a319-d3f846785281','fan_status','bool'),('44076c9a-a20d-517c-b561-fe36e6697f04','SYN-NORTH','1c58e3a1-a7b0-5816-a319-d3f846785281','fan_speed_pct','%'),('1735c7d7-68fa-514b-b246-701748a3e7d6','SYN-NORTH','1c58e3a1-a7b0-5816-a319-d3f846785281','kw','kW'),('ef52075c-0dc4-5298-88f6-d2239f91322c','SYN-NORTH','1c58e3a1-a7b0-5816-a319-d3f846785281','sat','degC'),('b46d3fa0-017a-5fcd-bbd7-8923b93f2ef9','SYN-NORTH','1c58e3a1-a7b0-5816-a319-d3f846785281','sat_sp','degC'),('6e866be7-270c-5d88-9c2d-ea09121b0a12','SYN-NORTH','1c58e3a1-a7b0-5816-a319-d3f846785281','rat','degC'),('7d4b605a-b12a-5186-b599-7ae883360a21','SYN-NORTH','1c58e3a1-a7b0-5816-a319-d3f846785281','oat','degC'),('69c03c57-e853-54bc-b86a-c0d3a87e9402','SYN-NORTH','1c58e3a1-a7b0-5816-a319-d3f846785281','mat','degC'),('5a9e0112-0f80-5c85-b6c4-38c6175a5c1f','SYN-NORTH','1c58e3a1-a7b0-5816-a319-d3f846785281','damper_pct','%'),('6e51b0df-a70f-5853-9e4c-72bd2814ef0b','SYN-NORTH','1c58e3a1-a7b0-5816-a319-d3f846785281','cooling_pct','%'),('0a7b2f78-dec9-555b-a543-b789fde86271','SYN-NORTH','1c58e3a1-a7b0-5816-a319-d3f846785281','zone_temp','degC'),('cd6eab99-5ea0-5fcd-a094-5512b79824fc','SYN-NORTH','1c58e3a1-a7b0-5816-a319-d3f846785281','zone_temp_sp','degC'),('dbb90906-1932-5ca9-99d0-36a109416072','SYN-NORTH','98377177-dee0-5f28-93f7-f78650f57a48','duct_static','Pa'),('e3dd9450-91a3-5bae-8ed2-827f844f1d06','SYN-NORTH','98377177-dee0-5f28-93f7-f78650f57a48','duct_static_sp','Pa'),('381a7097-1793-525f-ba3f-b35e02526d7c','SYN-NORTH','98377177-dee0-5f28-93f7-f78650f57a48','fan_status','bool'),('a412d34f-9857-5ea7-89c3-87b8e96355f8','SYN-NORTH','98377177-dee0-5f28-93f7-f78650f57a48','fan_speed_pct','%'),('d3e64048-d25e-5625-a31e-19a06097d16a','SYN-NORTH','98377177-dee0-5f28-93f7-f78650f57a48','kw','kW'),('3ac22bf7-780b-5874-b260-56a193278e89','SYN-NORTH','98377177-dee0-5f28-93f7-f78650f57a48','sat','degC'),('a12d19f4-8f19-59a4-b5bc-a9156dae8ed4','SYN-NORTH','98377177-dee0-5f28-93f7-f78650f57a48','sat_sp','degC'),('ad1e78a4-77e9-5370-b062-04deb98d9b7d','SYN-NORTH','98377177-dee0-5f28-93f7-f78650f57a48','rat','degC'),('6cd00321-8f06-5e7e-8c04-fdf9d952e523','SYN-NORTH','98377177-dee0-5f28-93f7-f78650f57a48','oat','degC'),('579328e5-c800-5667-bcab-b978be3bcc26','SYN-NORTH','98377177-dee0-5f28-93f7-f78650f57a48','mat','degC'),('8d97a515-f962-5405-846c-c5c8d819519a','SYN-NORTH','98377177-dee0-5f28-93f7-f78650f57a48','damper_pct','%'),('3491d479-22d0-5476-9bff-baaff3d15f39','SYN-NORTH','98377177-dee0-5f28-93f7-f78650f57a48','cooling_pct','%'),('a85481c7-9d6e-55cc-9bd5-2a911ecab2fe','SYN-NORTH','98377177-dee0-5f28-93f7-f78650f57a48','zone_temp','degC'),('3147910d-f6fa-56ed-b824-821c17b5554f','SYN-NORTH','98377177-dee0-5f28-93f7-f78650f57a48','zone_temp_sp','degC'),('62c5b317-cc4a-5946-b5ec-985919880084','SYN-SOUTH','2c0c3077-c005-5a27-b4d2-06a2976650df','duct_static','Pa'),('2b1fdb49-fa26-519c-9683-f977ada2c659','SYN-SOUTH','2c0c3077-c005-5a27-b4d2-06a2976650df','duct_static_sp','Pa'),('ecc072fb-58b9-5e05-9cdb-9276d2912d9c','SYN-SOUTH','2c0c3077-c005-5a27-b4d2-06a2976650df','fan_status','bool'),('80d7640e-91eb-5272-915f-9e84de7f7691','SYN-SOUTH','2c0c3077-c005-5a27-b4d2-06a2976650df','fan_speed_pct','%'),('b355184c-e03b-5b19-b424-07e2fdf2dc7c','SYN-SOUTH','2c0c3077-c005-5a27-b4d2-06a2976650df','kw','kW'),('ee368b41-8a82-500c-a913-d701c94c917a','SYN-SOUTH','2c0c3077-c005-5a27-b4d2-06a2976650df','sat','degC'),('d6beb051-3a3a-5c7e-9379-6d7aa7de0873','SYN-SOUTH','2c0c3077-c005-5a27-b4d2-06a2976650df','sat_sp','degC'),('617f33e0-4f01-5beb-949c-a6d75b23e29d','SYN-SOUTH','2c0c3077-c005-5a27-b4d2-06a2976650df','rat','degC'),('e5dddc4c-1537-5f66-a663-41baf8d46473','SYN-SOUTH','2c0c3077-c005-5a27-b4d2-06a2976650df','oat','degC'),('6c916383-54a9-507c-ab41-c09553456355','SYN-SOUTH','2c0c3077-c005-5a27-b4d2-06a2976650df','mat','degC'),('3d7b67d6-1039-5411-a46a-bffbd9a24659','SYN-SOUTH','2c0c3077-c005-5a27-b4d2-06a2976650df','damper_pct','%'),('762b5d2b-de90-5a54-bc4e-8553b26802fe','SYN-SOUTH','2c0c3077-c005-5a27-b4d2-06a2976650df','cooling_pct','%'),('77bcad12-10fc-52df-abf8-616b0d23abcf','SYN-SOUTH','2c0c3077-c005-5a27-b4d2-06a2976650df','zone_temp','degC'),('95301bd4-555b-5c3f-b63d-65c4aac1e121','SYN-SOUTH','2c0c3077-c005-5a27-b4d2-06a2976650df','zone_temp_sp','degC')
 ON CONFLICT(point_id) DO NOTHING;
WITH grid AS (
 SELECT p.*,t AS ts,extract(hour FROM t AT TIME ZONE 'UTC') AS hour_utc
 FROM course.point p CROSS JOIN generate_series('2026-01-05T00:00:00Z'::timestamptz,
 '2026-01-06T23:55:00Z'::timestamptz,interval '5 minutes') t
), operating AS (
 SELECT *,CASE WHEN equipment_id='1c58e3a1-a7b0-5816-a319-d3f846785281' THEN hour_utc>=6 AND hour_utc<18
 WHEN equipment_id='98377177-dee0-5f28-93f7-f78650f57a48' THEN hour_utc>=10 AND hour_utc<16
 ELSE hour_utc>=22 OR hour_utc<4 END AS fan_on FROM grid
)
INSERT INTO course.sample(site_id,point_id,ts,value,quality)
SELECT site_id,point_id,ts,
 CASE WHEN role='kw' AND equipment_id='1c58e3a1-a7b0-5816-a319-d3f846785281' AND ts='2026-01-05T15:10:00Z' THEN NULL
 WHEN role='fan_status' THEN fan_on::int::float8
 WHEN role='fan_speed_pct' THEN CASE WHEN fan_on THEN 70 ELSE 0 END
 WHEN role='kw' THEN CASE WHEN NOT fan_on THEN 0 WHEN equipment_id='1c58e3a1-a7b0-5816-a319-d3f846785281' THEN 12
  WHEN equipment_id='98377177-dee0-5f28-93f7-f78650f57a48' THEN 6 ELSE 9 END
 WHEN role='duct_static' THEN CASE WHEN NOT fan_on THEN 0
  WHEN equipment_id='1c58e3a1-a7b0-5816-a319-d3f846785281' AND ts>='2026-01-05T08:00:00Z' AND ts<'2026-01-05T09:00:00Z' THEN 100 ELSE 260 END
 WHEN role='duct_static_sp' THEN 250
 WHEN role='sat' THEN CASE WHEN equipment_id='98377177-dee0-5f28-93f7-f78650f57a48' AND ts>='2026-01-05T12:00:00Z' AND ts<'2026-01-05T13:00:00Z' THEN 20 ELSE 13 END
 WHEN role='sat_sp' THEN 13 WHEN role='rat' THEN 22 WHEN role='oat' THEN 8+hour_utc*0.5
 WHEN role='mat' THEN 0.2*(8+hour_utc*0.5)+0.8*22
 WHEN role='damper_pct' THEN 20 WHEN role='cooling_pct' THEN CASE WHEN hour_utc>=12 AND hour_utc<16 THEN 30 ELSE 0 END
 WHEN role='zone_temp' THEN CASE WHEN equipment_id='1c58e3a1-a7b0-5816-a319-d3f846785281' AND ts>='2026-01-05T14:00:00Z' AND ts<'2026-01-05T15:00:00Z' THEN 28 ELSE 22 END
 WHEN role='zone_temp_sp' THEN 22 END,
 CASE WHEN role='kw' AND equipment_id='1c58e3a1-a7b0-5816-a319-d3f846785281' AND ts='2026-01-05T15:10:00Z' THEN 'bad' ELSE 'good' END
FROM operating WHERE NOT(role='duct_static' AND equipment_id='1c58e3a1-a7b0-5816-a319-d3f846785281'
 AND ts IN ('2026-01-05T08:25:00Z'::timestamptz,'2026-01-05T08:30:00Z'::timestamptz))
ON CONFLICT(site_id,point_id,ts) DO NOTHING;
COMMIT;
