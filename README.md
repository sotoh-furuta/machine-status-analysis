# machine-status-analysis

IoT計測済み設備の電力データから稼働状態を分類し、待機時間・稼働率を可視化する分析ツール。

## セットアップ

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # Mac/Linux

pip install -r requirements.txt
```

DB接続情報を設定:

```bash
cp config/db.yaml.example config/db.yaml
# config/db.yaml を編集して接続情報を入力
```

## 使い方

### Step 0: データ確認

`sql/step0_check_data.sql` をDBクライアントで実行し、対象 machine_id とデータ品質を確認する。

### Step 1: 電力分布グラフの生成

```bash
# 全設備
python src/step1_histogram.py

# 特定設備のみ
python src/step1_histogram.py --machine-id 01

# 直近90日分
python src/step1_histogram.py --days 90
```

グラフは `output/histograms/` に保存される。  
コンソールに出力される **閾値候補 (kW)** を確認し、`config/thresholds.yaml` に記入する。

### Step 2: 分類・DB書き込み

`config/thresholds.yaml` に閾値を設定後:

```bash
# thresholds.yaml に定義済みの設備を処理
python src/step2_classify.py

# 特定設備のみ
python src/step2_classify.py --machine-id 01

# DB書き込みせずに確認
python src/step2_classify.py --dry-run

# 閾値未設定の設備もフォールバック（stopped/running）で処理
python src/step2_classify.py --all
```

### Step 3: テーブル作成（初回のみ）

```bash
psql -h <host> -U <user> -d <dbname> -f sql/create_tables.sql
```

## リポジトリ構成

```
machine-status-analysis/
├── README.md
├── requirements.txt
├── config/
│   ├── db.yaml               # DB接続情報（.gitignore対象）
│   ├── db.yaml.example
│   └── thresholds.yaml       # 設備ごとの閾値定義
├── sql/
│   ├── step0_check_data.sql
│   ├── create_tables.sql
│   └── queries/              # Grafana用クエリ
├── src/
│   ├── step1_histogram.py    # グラフ生成・閾値候補検出
│   ├── step2_classify.py     # 分類・DB書き込み
│   └── utils/
│       ├── db.py
│       └── config.py
└── output/
    └── histograms/           # 出力グラフ（.gitignore対象）
```
