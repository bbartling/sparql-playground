-- Educational gap-aware predicate, not complete production FC1. Good sample support is at most300s.
WITH flags AS (
 SELECT *,CASE WHEN fan_status IS NULL OR duct_static IS NULL OR duct_static_sp IS NULL
 THEN NULL ELSE fan_status=1 AND duct_static<0.9*duct_static_sp END AS raw_fault
 FROM course.ahu_5m WHERE ts>='2026-01-05T00:00:00Z' AND ts<'2026-01-07T00:00:00Z'
), boundaries AS (
 SELECT *,CASE WHEN raw_fault IS DISTINCT FROM lag(raw_fault) OVER w
 OR ts-lag(ts) OVER w>interval '5 minutes' THEN 1 ELSE 0 END AS new_group
 FROM flags WINDOW w AS(PARTITION BY site_id,equipment_id ORDER BY ts)
), groups AS (
 SELECT *,sum(new_group) OVER(PARTITION BY site_id,equipment_id ORDER BY ts) AS grp FROM boundaries
), streaks AS (
 SELECT *,row_number() OVER(PARTITION BY site_id,equipment_id,grp ORDER BY ts) AS streak FROM groups
)
SELECT site_id,equipment_id,equipment_label,
 count(*) FILTER(WHERE raw_fault)*300 AS raw_seconds,
 count(*) FILTER(WHERE raw_fault AND streak>=3)*300 AS confirmed_seconds,
 count(*) FILTER(WHERE raw_fault IS NULL)*300 AS unknown_seconds
FROM streaks GROUP BY site_id,equipment_id,equipment_label ORDER BY site_id,equipment_label;
