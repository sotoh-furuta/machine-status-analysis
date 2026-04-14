"""設定ファイルの読み込みユーティリティ"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

_ROOT = Path(__file__).parent.parent.parent  # リポジトリルート


def load_db_config(path: str | None = None) -> dict[str, Any]:
    """config/db.yaml を読み込む。"""
    config_path = Path(path) if path else _ROOT / "config" / "db.yaml"
    if not config_path.exists():
        raise FileNotFoundError(
            f"DB設定ファイルが見つかりません: {config_path}\n"
            f"config/db.yaml.example をコピーして config/db.yaml を作成してください。"
        )
    with config_path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_thresholds(path: str | None = None) -> dict[str, list[dict[str, Any]]]:
    """config/thresholds.yaml を読み込み、machine_id → 閾値リストのマップを返す。"""
    config_path = Path(path) if path else _ROOT / "config" / "thresholds.yaml"
    with config_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("machines", {})


def output_dir() -> Path:
    """output/histograms/ ディレクトリのパスを返す（存在しない場合は作成）。"""
    d = _ROOT / "output" / "histograms"
    d.mkdir(parents=True, exist_ok=True)
    return d
