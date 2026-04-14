-- 分類結果テーブルと集計テーブルの作成
-- 実行前に対象スキーマを確認してください

-- 1. 閾値マスタテーブル
CREATE TABLE IF NOT EXISTS "IoT_schema".machine_thresholds (
    machine_id  TEXT        NOT NULL,
    state_name  TEXT        NOT NULL,  -- stopped / standby / running / high_load 等
    lower_kw    NUMERIC,               -- NULL = 下限なし
    upper_kw    NUMERIC,               -- NULL = 上限なし
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (machine_id, state_name)
);

COMMENT ON TABLE "IoT_schema".machine_thresholds IS '設備ごとの稼働状態閾値定義';

-- 2. 分類結果テーブル（energy_raw の各レコードに状態ラベルを付与）
CREATE TABLE IF NOT EXISTS "IoT_schema".machine_status (
    machine_id      TEXT        NOT NULL,
    measured_at     TIMESTAMPTZ NOT NULL,
    active_power_kw NUMERIC,
    status          TEXT        NOT NULL,  -- 状態ラベル
    classified_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (machine_id, measured_at)
);

CREATE INDEX IF NOT EXISTS idx_machine_status_machine_id
    ON "IoT_schema".machine_status (machine_id);
CREATE INDEX IF NOT EXISTS idx_machine_status_measured_at
    ON "IoT_schema".machine_status (measured_at);

COMMENT ON TABLE "IoT_schema".machine_status IS '各1分レコードの稼働状態分類結果';

-- 3. 日別集計テーブル
CREATE TABLE IF NOT EXISTS "IoT_schema".machine_daily_summary (
    machine_id       TEXT    NOT NULL,
    summary_date     DATE    NOT NULL,
    total_minutes    INTEGER NOT NULL,  -- 当日の計測分数
    stopped_minutes  INTEGER NOT NULL DEFAULT 0,
    standby_minutes  INTEGER NOT NULL DEFAULT 0,
    running_minutes  INTEGER NOT NULL DEFAULT 0,
    other_minutes    INTEGER NOT NULL DEFAULT 0,  -- 3状態以外の合計
    operation_rate   NUMERIC(5, 2),               -- 稼働率 (%)
    standby_rate     NUMERIC(5, 2),               -- 待機率 (%)
    avg_power_kw     NUMERIC,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (machine_id, summary_date)
);

COMMENT ON TABLE "IoT_schema".machine_daily_summary IS '日別・設備別の稼働率・待機時間集計';

-- 4. 日別集計ビュー（machine_status から動的に算出する場合の参考）
CREATE OR REPLACE VIEW "IoT_schema".v_machine_daily_summary AS
SELECT
    machine_id,
    DATE(measured_at AT TIME ZONE 'Asia/Tokyo') AS summary_date,
    COUNT(*)                                    AS total_minutes,
    COUNT(*) FILTER (WHERE status = 'stopped')  AS stopped_minutes,
    COUNT(*) FILTER (WHERE status = 'standby')  AS standby_minutes,
    COUNT(*) FILTER (WHERE status = 'running')  AS running_minutes,
    COUNT(*) FILTER (WHERE status NOT IN ('stopped', 'standby', 'running')) AS other_minutes,
    ROUND(
        COUNT(*) FILTER (WHERE status = 'running') * 100.0 / NULLIF(COUNT(*), 0),
        2
    ) AS operation_rate,
    ROUND(
        COUNT(*) FILTER (WHERE status = 'standby') * 100.0 / NULLIF(COUNT(*), 0),
        2
    ) AS standby_rate,
    ROUND(AVG(active_power_kw)::numeric, 3) AS avg_power_kw
FROM "IoT_schema".machine_status
GROUP BY machine_id, DATE(measured_at AT TIME ZONE 'Asia/Tokyo');
