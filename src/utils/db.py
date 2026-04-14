"""PostgreSQL 接続ユーティリティ"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from .config import load_db_config

_TABLE_RAW = '"IoT_schema".energy_raw'
_TABLE_STATUS = '"IoT_schema".machine_status'


def _build_dsn(cfg: dict[str, Any]) -> str:
    return (
        f"postgresql+psycopg2://{cfg['user']}:{cfg['password']}"
        f"@{cfg['host']}:{cfg['port']}/{cfg['dbname']}"
    )


def get_engine(db_config: dict[str, Any] | None = None) -> Engine:
    """SQLAlchemy エンジンを返す。"""
    cfg = db_config or load_db_config()
    return create_engine(_build_dsn(cfg))


def fetch_power_data(
    machine_id: str,
    engine: Engine,
    days: int = 365,
) -> pd.DataFrame:
    """energy_raw から active_power_kw を取得する（直近 days 日分）。

    Returns:
        DataFrame: columns = [measured_at, active_power_kw]
    """
    # INTERVAL には bind parameter が使えないため days は int 型のまま f-string で埋め込む
    sql = text(
        f"""
        SELECT measured_at, active_power_kw
        FROM {_TABLE_RAW}
        WHERE machine_id  = :mid
          AND measured_at >= NOW() - INTERVAL '{days} days'
          AND active_power_kw IS NOT NULL
        ORDER BY measured_at
        """
    )
    with engine.connect() as conn:
        df = pd.read_sql(sql, conn, params={"mid": machine_id})
    df["measured_at"] = pd.to_datetime(df["measured_at"], utc=True)
    return df


def fetch_all_machine_ids(engine: Engine) -> list[str]:
    """energy_raw に存在する machine_id 一覧を返す。"""
    sql = text(
        f"SELECT DISTINCT machine_id FROM {_TABLE_RAW} ORDER BY machine_id"
    )
    with engine.connect() as conn:
        result = conn.execute(sql)
        return [row[0] for row in result]


def upsert_status(df: pd.DataFrame, engine: Engine) -> int:
    """分類結果を machine_status テーブルへ upsert する。

    Args:
        df: columns = [machine_id, measured_at, active_power_kw, status]

    Returns:
        挿入/更新件数
    """
    records = df.to_dict(orient="records")
    upsert_sql = text(
        f"""
        INSERT INTO {_TABLE_STATUS}
            (machine_id, measured_at, active_power_kw, status, classified_at)
        VALUES
            (:machine_id, :measured_at, :active_power_kw, :status, NOW())
        ON CONFLICT (machine_id, measured_at) DO UPDATE
            SET active_power_kw = EXCLUDED.active_power_kw,
                status          = EXCLUDED.status,
                classified_at   = EXCLUDED.classified_at
        """
    )
    with engine.begin() as conn:
        conn.execute(upsert_sql, records)
    return len(records)
