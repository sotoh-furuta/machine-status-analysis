-- Grafana パネル B/C: 日別稼働率・待機時間 (Bar / Time series)
-- 変数: $machine_id, $__timeFrom, $__timeTo

SELECT
    summary_date                        AS "time",
    operation_rate                      AS "Operation Rate (%)",
    standby_rate                        AS "Standby Rate (%)",
    stopped_minutes,
    standby_minutes,
    running_minutes,
    avg_power_kw                        AS "Avg Power (kW)"
FROM "IoT_schema".machine_daily_summary
WHERE machine_id   = '$machine_id'
  AND summary_date BETWEEN $__timeFrom::date AND $__timeTo::date
ORDER BY summary_date;
