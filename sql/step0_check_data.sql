-- Step 0: データ確認クエリ
-- 対象テーブル: "IoT_schema".energy_raw
-- 目的: 分析対象 machine_id の選定と、データ品質の把握

-- 1. 全 machine_id と計測期間、レコード数の確認
SELECT
    machine_id,
    COUNT(*)                          AS record_count,
    MIN(time)                         AS oldest,
    MAX(time)                         AS latest,
    ROUND(AVG(active_power_kw)::numeric, 3) AS avg_kw,
    ROUND(MIN(active_power_kw)::numeric, 3) AS min_kw,
    ROUND(MAX(active_power_kw)::numeric, 3) AS max_kw,
    COUNT(*) FILTER (WHERE active_power_kw IS NULL) AS null_count
FROM "IoT_schema".energy_raw
WHERE time >= NOW() - INTERVAL '1 year'
GROUP BY machine_id
ORDER BY machine_id;

-- 2. 直近7日のサンプル確認（machine_id を指定して実行）
-- SELECT *
-- FROM "IoT_schema".energy_raw
-- WHERE machine_id = '<対象のmachine_id>'
--   AND time >= NOW() - INTERVAL '7 days'
-- ORDER BY time;

-- 3. 欠損分数の確認（1分粒度であれば 1440*365 = 525600 が上限）
SELECT
    machine_id,
    COUNT(*) AS actual_count,
    EXTRACT(DAY FROM (MAX(time) - MIN(time))) * 1440 AS expected_minutes,
    ROUND(
        COUNT(*) * 100.0
        / NULLIF(EXTRACT(DAY FROM (MAX(time) - MIN(time))) * 1440, 0),
        1
    ) AS coverage_pct
FROM "IoT_schema".energy_raw
WHERE time >= NOW() - INTERVAL '1 year'
GROUP BY machine_id
ORDER BY coverage_pct DESC;
