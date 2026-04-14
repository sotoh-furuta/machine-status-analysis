"""
Step 2: 稼働状態の分類・DB書き込み

使い方:
    # 全 machine_id を処理（thresholds.yaml に定義済みの設備のみ）
    python src/step2_classify.py

    # 特定の machine_id のみ
    python src/step2_classify.py --machine-id 01

    # 直近 N 日分のみ更新
    python src/step2_classify.py --days 7

    # DB書き込みせずに分類結果を確認（dry-run）
    python src/step2_classify.py --dry-run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.config import load_thresholds
from src.utils.db import fetch_all_machine_ids, fetch_power_data, get_engine, upsert_status


# --------------------------------------------------------------------------- #
# 分類ロジック
# --------------------------------------------------------------------------- #

def classify_power(kw: float, rules: list[dict[str, Any]]) -> str:
    """単一の kW 値を閾値ルールに基づいて状態ラベルに変換する。

    rules の例:
        [
            {"state": "stopped",  "lower_kw": None, "upper_kw": 0.5},
            {"state": "standby",  "lower_kw": 0.5,  "upper_kw": 5.0},
            {"state": "running",  "lower_kw": 5.0,  "upper_kw": None},
        ]
    """
    for rule in rules:
        lo = rule.get("lower_kw")
        hi = rule.get("upper_kw")
        if (lo is None or kw >= lo) and (hi is None or kw < hi):
            return rule["state"]
    return "unknown"


def classify_dataframe(
    df: pd.DataFrame, rules: list[dict[str, Any]]
) -> pd.DataFrame:
    """DataFrame の active_power_kw 列を分類し、status 列を付加して返す。"""
    df = df.copy()
    df["status"] = df["active_power_kw"].apply(
        lambda kw: classify_power(kw, rules) if pd.notna(kw) else "unknown"
    )
    return df


def fallback_classify(df: pd.DataFrame, threshold_kw: float = 0.5) -> pd.DataFrame:
    """閾値未設定の設備向けの2状態フォールバック分類。"""
    df = df.copy()
    df["status"] = df["active_power_kw"].apply(
        lambda kw: "stopped" if (pd.isna(kw) or kw < threshold_kw) else "running"
    )
    return df


# --------------------------------------------------------------------------- #
# レポート出力
# --------------------------------------------------------------------------- #

def print_summary(machine_id: str, df: pd.DataFrame) -> None:
    """分類結果のサマリーをコンソール出力する。"""
    total = len(df)
    summary = df["status"].value_counts()
    print(f"\n[{machine_id}] 分類結果サマリー (total={total:,})")
    for state, cnt in summary.items():
        pct = cnt / total * 100
        print(f"  {state:<12}: {cnt:>8,} 件 ({pct:.1f}%)")


# --------------------------------------------------------------------------- #
# メイン処理
# --------------------------------------------------------------------------- #

def process_machine(
    machine_id: str,
    rules: list[dict[str, Any]] | None,
    engine,
    days: int,
    dry_run: bool,
) -> None:
    print(f"\n[{machine_id}] データ取得中 ({days} 日分)...")
    df = fetch_power_data(machine_id, engine, days=days)

    if df.empty:
        print(f"[{machine_id}] データなし。スキップします。")
        return

    df["machine_id"] = machine_id

    if rules:
        df = classify_dataframe(df, rules)
    else:
        print(f"[{machine_id}] 閾値未設定 → フォールバック分類（stopped / running）を適用。")
        df = fallback_classify(df)

    print_summary(machine_id, df)

    if dry_run:
        print(f"[{machine_id}] dry-run モード: DB書き込みをスキップしました。")
        return

    n = upsert_status(
        df[["machine_id", "measured_at", "active_power_kw", "status"]],
        engine,
    )
    print(f"[{machine_id}] {n:,} 件を machine_status テーブルへ書き込みました。")


def main() -> None:
    parser = argparse.ArgumentParser(description="稼働状況分析 Step2: 分類・DB書き込み")
    parser.add_argument("--machine-id", "-m", default=None,
                        help="対象 machine_id（省略時はthresholds.yamlの全設備）")
    parser.add_argument("--all", action="store_true",
                        help="thresholds.yaml 未設定の設備もフォールバックで処理")
    parser.add_argument("--days", "-d", type=int, default=365,
                        help="取得期間（日数、デフォルト 365）")
    parser.add_argument("--dry-run", action="store_true",
                        help="DB書き込みを行わずに分類結果のみ確認")
    args = parser.parse_args()

    thresholds = load_thresholds()
    engine = get_engine()

    if args.machine_id:
        machine_ids = [args.machine_id]
    elif args.all:
        machine_ids = fetch_all_machine_ids(engine)
    else:
        machine_ids = list(thresholds.keys())
        if not machine_ids:
            print(
                "thresholds.yaml に設備が定義されていません。\n"
                "先に step1_histogram.py でグラフを確認し、閾値を設定してください。\n"
                "全設備をフォールバック分類で処理する場合は --all を指定してください。"
            )
            sys.exit(0)

    print(f"対象 machine_id: {machine_ids}")

    for mid in machine_ids:
        try:
            process_machine(
                mid,
                rules=thresholds.get(mid),
                engine=engine,
                days=args.days,
                dry_run=args.dry_run,
            )
        except Exception as e:
            print(f"[{mid}] エラー: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
