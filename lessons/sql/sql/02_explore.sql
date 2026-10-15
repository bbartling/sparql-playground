-- First read-only fixture tour. Counts:2,3,42,24190; site labels are not keys.
SELECT current_database(),current_user,version();
SELECT * FROM course.site ORDER BY site_id;
SELECT site_id,label,kind,equipment_id FROM course.equipment ORDER BY site_id,label;
SELECT site_id,count(*) AS rows FROM course.sample GROUP BY site_id ORDER BY site_id;
SELECT role,unit,count(*) AS points FROM course.point GROUP BY role,unit ORDER BY role;
SELECT ts,duct_static,duct_static_sp,fan_status FROM course.ahu_5m
 WHERE site_id='SYN-NORTH' AND equipment_label='Supply A'
 AND ts>='2026-01-05T08:00:00Z' AND ts<'2026-01-05T09:00:00Z' ORDER BY ts;
