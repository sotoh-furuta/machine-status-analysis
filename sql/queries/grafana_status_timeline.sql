-- Grafana パネル A: 稼働状態タイムライン (State timeline)
-- 変数: $machine_id, $__timeFrom, $__timeTo

SELECT
    measured_at                         AS "time",
    CASE status
        WHEN 'stopped'   THEN 0
        WHEN 'standby'   THEN 1
        WHEN 'running'   THEN 2
        WHEN 'high_load' THEN 3
        ELSE -1
    END                                 AS "status_code",
    status                              AS "status"
FROM "IoT_schema".machine_status
WHERE machine_id  = '$machine_id'
  AND measured_at BETWEEN $__timeFrom AND $__timeTo
ORDER BY measured_at;
