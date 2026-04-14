"""
Step 1: 設備ごとの電力分布分析・グラフ出力

使い方:
    # 全 machine_id を処理
    python src/step1_histogram.py

    # 特定の machine_id のみ
    python src/step1_histogram.py --machine-id 01

    # 直近 N 日分のデータを使用（デフォルト 365）
    python src/step1_histogram.py --days 90
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # GUI なし環境対応
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from scipy.signal import find_peaks
from scipy.stats import gaussian_kde

# プロジェクトルートを sys.path に追加（直接実行時用）
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.config import output_dir
from src.utils.db import fetch_all_machine_ids, fetch_power_data, get_engine

# --------------------------------------------------------------------------- #
# グラフ生成
# --------------------------------------------------------------------------- #

def _auto_bins(n: int) -> int:
    """データ点数に応じて bin 数を 30〜100 で自動調整する。"""
    return int(np.clip(int(np.sqrt(n) * 1.5), 30, 100))


def _detect_valley_thresholds(values: np.ndarray, n_bins: int = 60) -> list[float]:
    """ヒストグラムの谷（極小点）から閾値候補を返す。"""
    counts, edges = np.histogram(values, bins=n_bins)
    mids = (edges[:-1] + edges[1:]) / 2

    # 谷 = カウントが局所的に小さい点
    valleys, _ = find_peaks(-counts, prominence=counts.max() * 0.05)
    return sorted(mids[valleys].tolist())


def _plot_histogram(ax: plt.Axes, values: np.ndarray, machine_id: str) -> list[float]:
    """1. ヒストグラム + KDE + 閾値候補"""
    n_bins = _auto_bins(len(values))
    ax.hist(values, bins=n_bins, color="steelblue", alpha=0.7,
            label="Histogram", density=True)

    # KDE
    kde = gaussian_kde(values, bw_method="scott")
    x = np.linspace(values.min(), values.max(), 500)
    ax.plot(x, kde(x), color="darkorange", lw=2, label="KDE")

    # 閾値候補（谷）
    thresholds = _detect_valley_thresholds(values, n_bins)
    for th in thresholds:
        ax.axvline(th, color="red", lw=1.2, linestyle="--", alpha=0.8)

    stats_txt = (
        f"n={len(values):,}  min={values.min():.2f}  "
        f"mean={values.mean():.2f}  max={values.max():.2f} kW"
    )
    ax.set_title(f"[{machine_id}] Power Distribution", fontsize=11)
    ax.set_xlabel("active_power_kw")
    ax.set_ylabel("Density")
    ax.legend(fontsize=8)
    ax.text(0.98, 0.97, stats_txt, transform=ax.transAxes,
            ha="right", va="top", fontsize=7,
            bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.7))
    return thresholds


def _plot_duration_curve(ax: plt.Axes, values: np.ndarray, machine_id: str) -> None:
    """2. 持続曲線（デュレーションカーブ）"""
    sorted_vals = np.sort(values)[::-1]
    pct = np.linspace(0, 100, len(sorted_vals))
    ax.plot(pct, sorted_vals, color="steelblue", lw=1.5)
    ax.set_title(f"[{machine_id}] Duration Curve", fontsize=11)
    ax.set_xlabel("Time (%)")
    ax.set_ylabel("active_power_kw")
    ax.xaxis.set_major_formatter(mticker.PercentFormatter())
    ax.grid(True, alpha=0.3)


def _plot_hourly_profile(ax: plt.Axes, df: pd.DataFrame, machine_id: str) -> None:
    """3. 時間帯プロファイル（24本の箱ひげ図）"""
    local_dt = df["measured_at"].dt.tz_convert("Asia/Tokyo")
    hour = local_dt.dt.hour
    groups = [df.loc[hour == h, "active_power_kw"].dropna().values for h in range(24)]

    bp = ax.boxplot(
        groups,
        positions=range(24),
        widths=0.6,
        patch_artist=True,
        showfliers=False,
        medianprops=dict(color="darkorange", lw=2),
        boxprops=dict(facecolor="steelblue", alpha=0.5),
        whiskerprops=dict(color="steelblue"),
        capprops=dict(color="steelblue"),
    )
    ax.set_title(f"[{machine_id}] Hourly Profile (JST)", fontsize=11)
    ax.set_xlabel("Hour of Day")
    ax.set_ylabel("active_power_kw")
    ax.set_xticks(range(24))
    ax.set_xticklabels([f"{h:02d}" for h in range(24)], fontsize=7)
    ax.grid(True, axis="y", alpha=0.3)


def _plot_timeseries(ax: plt.Axes, df: pd.DataFrame, machine_id: str,
                     days: int = 7) -> None:
    """4. 時系列サンプル（直近 N 日）"""
    cutoff = df["measured_at"].max() - pd.Timedelta(days=days)
    subset = df[df["measured_at"] >= cutoff]
    local_dt = subset["measured_at"].dt.tz_convert("Asia/Tokyo")
    ax.plot(local_dt, subset["active_power_kw"],
            color="steelblue", lw=0.6, alpha=0.8)
    ax.set_title(f"[{machine_id}] Time Series (last {days} days)", fontsize=11)
    ax.set_xlabel("Datetime (JST)")
    ax.set_ylabel("active_power_kw")
    ax.grid(True, alpha=0.3)
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right", fontsize=7)


# --------------------------------------------------------------------------- #
# メイン処理
# --------------------------------------------------------------------------- #

def analyze_machine(machine_id: str, engine, days: int = 365) -> None:
    """1台分の分析グラフを生成して保存する。"""
    print(f"[{machine_id}] データ取得中 ({days} 日分)...")
    df = fetch_power_data(machine_id, engine, days=days)

    if df.empty:
        print(f"[{machine_id}] データなし。スキップします。")
        return

    values = df["active_power_kw"].dropna().values
    print(f"[{machine_id}] {len(values):,} 件のデータを取得。")

    out = output_dir()

    # --- 4グラフ概要図 ---
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    fig.suptitle(f"Machine: {machine_id}  |  Period: last {days} days", fontsize=13)

    thresholds = _plot_histogram(axes[0, 0], values, machine_id)
    _plot_duration_curve(axes[0, 1], values, machine_id)
    _plot_hourly_profile(axes[1, 0], df, machine_id)
    _plot_timeseries(axes[1, 1], df, machine_id)

    plt.tight_layout()
    overview_path = out / f"{machine_id}_overview.png"
    fig.savefig(overview_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"[{machine_id}] 概要図保存: {overview_path}")

    # --- 個別詳細図（ヒストグラム拡大） ---
    fig2, ax2 = plt.subplots(figsize=(10, 5))
    _plot_histogram(ax2, values, machine_id)
    if thresholds:
        th_str = ", ".join(f"{t:.3f}" for t in thresholds)
        ax2.set_title(
            f"[{machine_id}] Power Distribution  |  Threshold candidates: {th_str} kW",
            fontsize=11
        )
    plt.tight_layout()
    detail_path = out / f"{machine_id}_histogram_detail.png"
    fig2.savefig(detail_path, dpi=150, bbox_inches="tight")
    plt.close(fig2)
    print(f"[{machine_id}] 詳細ヒストグラム保存: {detail_path}")

    if thresholds:
        print(f"[{machine_id}] 閾値候補 (kW): {thresholds}")
        print(f"  → config/thresholds.yaml に手動で記入してください。")
    else:
        print(f"[{machine_id}] 明確な谷が検出されませんでした（2状態へのフォールバックを検討）。")


def main() -> None:
    parser = argparse.ArgumentParser(description="稼働状況分析 Step1: 電力分布グラフ生成")
    parser.add_argument("--machine-id", "-m", default=None,
                        help="対象 machine_id（省略時は全台）")
    parser.add_argument("--days", "-d", type=int, default=365,
                        help="取得期間（日数、デフォルト 365）")
    args = parser.parse_args()

    engine = get_engine()

    if args.machine_id:
        machine_ids = [args.machine_id]
    else:
        machine_ids = fetch_all_machine_ids(engine)
        print(f"対象 machine_id: {machine_ids}")

    for mid in machine_ids:
        try:
            analyze_machine(mid, engine, days=args.days)
        except Exception as e:
            print(f"[{mid}] エラー: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
