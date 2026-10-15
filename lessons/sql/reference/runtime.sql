-- Read after attempting the runtime exercises. Valid only under the declared five-minute fixture convention.
SELECT site_id,equipment_id,equipment_label,
 count(*) FILTER(WHERE fan_status=1)*300.0/3600 AS observed_run_hours,
 count(fan_status)*300.0/3600 AS known_status_hours
FROM course.ahu_5m WHERE ts>='2026-01-05T00:00:00Z' AND ts<'2026-01-07T00:00:00Z'
GROUP BY site_id,equipment_id,equipment_label ORDER BY site_id,equipment_label;
