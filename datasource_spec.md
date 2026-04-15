# データソース仕様書 — energy_raw テーブル

作成日: 2026-04-14
関連文書: 稼働状況分析 要件定義書

---

## 1. テーブル概要

| 項目           | 内容                                           |
|---------------|-----------------------------------------------|
| スキーマ       | `"IoT_schema"`                                 |
| テーブル名     | `energy_raw`                                   |
| 用途          | 全設備のエネルギーデータを統合した中央テーブル       |
| 記録粒度       | 1分                                            |
| データ投入方式  | IoT Data Share → 個別機械テーブル → pg_cronで統合  |
| 一意制約       | `UNIQUE (time, machine_id)` — 制約名: `uq_energy_raw_time_machine` |

## 2. カラム定義

| # | カラム名              | データ型（推定）  | NULL許容 | 説明                         | 本プロジェクトでの用途      |
|---|----------------------|----------------|---------|-----------------------------|-----------------------|
| 1 | time                 | TIMESTAMPTZ    | NOT NULL | 計測時刻                     | 時系列の軸             |
| 2 | machine_id           | VARCHAR        | NOT NULL | 設備識別子（例: '01', '02'）  | 分析対象の選択キー       |
| 3 | current_a            | NUMERIC        | —       | 電流現在値 [A]                | Phase 2: 電流異常検出   |
| 4 | active_power_kw      | NUMERIC        | —       | 有効電力 [kW]                 | Phase 1: 稼働状況分類   |
| 5 | active_energy_kwh    | NUMERIC        | —       | 有効電力量（累積） [kWh]       | 消費量の集計            |
| 6 | reactive_energy_kvarh| NUMERIC        | —       | 無効電力量（累積） [kvarh]     | 参考                   |
| 7 | gas_cumulative_m3    | NUMERIC        | —       | ガス積算値 [m³]               | 対象外（ガス系）         |
| 8 | gas_flow_m3          | NUMERIC        | —       | ガス瞬時流量 [m³]             | 対象外（ガス系）         |
| 9 | power_factor         | NUMERIC        | —       | 力率                          | Phase 2: 力率異常検出   |

※ データ型は過去のクエリから推定。実環境での確認を推奨。

### 2.1 確認用SQL

```sql
-- 実際のカラム名・データ型・NULL許容を確認
SELECT
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_schema = 'IoT_schema'
  AND table_name = 'energy_raw'
ORDER BY ordinal_position;

-- 制約の確認
SELECT
    conname AS constraint_name,
    contype AS type,
    pg_get_constraintdef(oid) AS definition
FROM pg_constraint
WHERE conrelid = '"IoT_schema".energy_raw'::regclass;
```

## 3. キー・制約

| 制約名                        | 種類    | 対象カラム              | 備考                        |
|------------------------------|--------|------------------------|----------------------------|
| uq_energy_raw_time_machine   | UNIQUE | (time, machine_id)     | 重複データ防止、ON CONFLICT対応 |

※ PRIMARY KEY の有無は未確認。UNIQUE制約は移行作業時に追加済み。

## 4. データフロー

```
電力/ガスメーター
    ↓ Modbus-TCP
Modbus-TCP変換器
    ↓ Modbus-TCP
IoT Data Share（ポーリング収集）
    ↓ INSERT
個別機械テーブル（約20テーブル）
  例: "IoT_schema"."LCR1", "IoT_schema"."PT8" 等
    ↓ pg_cron（日次統合）
energy_raw（本テーブル）
    ↓ SELECT
Grafana / Python分析スクリプト
```

## 5. 元テーブルとのカラム対応

個別機械テーブル（IoT Data Shareが直接書き込むテーブル）は
日本語カラム名を使用している。energy_rawへの統合時に英語名に変換される。

| energy_raw カラム       | 元テーブルのカラム名 | 備考               |
|------------------------|-------------------|-------------------|
| time                   | time              | 共通               |
| machine_id             | —                 | 統合時に付与        |
| current_a              | 電流現在値          |                    |
| active_power_kw        | 電力現在値          |                    |
| active_energy_kwh      | 電力量_消費         | 累積値             |
| reactive_energy_kvarh  | 電力量_無効         | 累積値             |
| gas_cumulative_m3      | ガス積算値          | 累積値             |
| gas_flow_m3            | ガス瞬時値          |                    |
| power_factor           | 力率               |                    |

### 5.1 確認済みの machine_id と元テーブルの対応

| machine_id | 元テーブル名 | 備考           |
|-----------|-------------|---------------|
| '01'      | LCR1        |               |
| '02'      | PT8         |               |
| '03'〜    | 未確認       | 約20テーブルあり |

※ 全machine_idの一覧は Step 0 のSQL実行結果で確認予定。

## 6. データの特性・注意点

### 6.1 累積値のロールオーバー

active_energy_kwh, reactive_energy_kvarh, gas_cumulative_m3 は
メーターの累積値であり、メーターの上限に達するとゼロに戻る
（ロールオーバー）。日次消費量の算出時には補正が必要。

### 6.2 欠損データ

IoT Data Shareのポーリング失敗やネットワーク障害により
欠損が発生する可能性がある。欠損率は Step 0 で確認予定。

### 6.3 NULL値

全カラムでNULLが入り得るかは未確認。
分析スクリプトでは `WHERE active_power_kw IS NOT NULL` で
フィルタする設計とする。

## 7. 本プロジェクトでの使用方針

| Phase   | 使用カラム          | 用途               |
|---------|--------------------|--------------------|
| Phase 1 | active_power_kw    | 稼働状態の分類       |
| Phase 2 | current_a          | 電流異常の検出       |
| Phase 2 | power_factor       | 力率異常の検出       |
| 将来    | active_energy_kwh  | 月次消費量の予測     |

---

## 変更履歴

| 日付       | 内容       |
|-----------|-----------|
| 2026-04-14 | 初版作成   |
