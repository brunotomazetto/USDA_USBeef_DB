"""
build_history.py
----------------
Roda UMA VEZ localmente para montar a série histórica completa.

Fonte: DataMart (MPR) - mpr.datamart.ams.usda.gov
  · Público, sem autenticação
  · Limite: 180 dias por request
  · Série disponível desde 02/04/2001 (início do LMR)

Uso:
  pip install requests pandas python-dateutil
  python scripts/build_history.py

Saída: data/beef_cutout.csv
"""

import time
import requests
import pandas as pd
from datetime import date, timedelta
from pathlib import Path

SLUG         = 2453
DATAMART_URL = "https://mpr.datamart.ams.usda.gov/services/v1.1/reports"
SERIES_START = date(2001, 4, 2)
MAX_WINDOW   = 180   # limite documentado do DataMart por request
SLEEP_SEC    = 0.5   # pausa entre requests para não sobrecarregar o servidor
OUT_PATH     = Path(__file__).parent.parent / "data" / "beef_cutout.csv"


def fetch_window(date_begin: date, date_end: date) -> pd.DataFrame:
    """Busca um intervalo de até 180 dias no DataMart e retorna DataFrame."""
    url = f"{DATAMART_URL}/{SLUG}"
    params = {
        "q": (
            f"report_date_begin={date_begin.strftime('%m/%d/%Y')};"
            f"report_date_end={date_end.strftime('%m/%d/%Y')};"
            "class=Cutout and Primal Values"
        ),
        "sort": "report_date",
    }

    try:
        r = requests.get(url, params=params, timeout=60)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"  [ERRO] {date_begin} → {date_end}: {e}")
        return pd.DataFrame()

    results = r.json().get("results", [])
    if not results:
        return pd.DataFrame()

    rows: dict[str, dict] = {}
    for item in results:
        d     = str(item.get("report_date", ""))[:10]
        label = str(item.get("label", ""))
        raw   = item.get("value") or item.get("Choice") or item.get("Select")
        if not d or raw is None:
            continue
        try:
            val = float(raw)
        except (ValueError, TypeError):
            continue

        if label == "Choice":
            rows.setdefault(d, {})["choice"] = val
        elif label == "Select":
            rows.setdefault(d, {})["select"] = val

    records = [
        {
            "date":   d,
            "choice": v["choice"],
            "select": v["select"],
            "spread": round(v["choice"] - v["select"], 2),
        }
        for d, v in rows.items()
        if "choice" in v and "select" in v
    ]
    return pd.DataFrame(records)


def main() -> None:
    all_frames: list[pd.DataFrame] = []
    window_start = SERIES_START
    today        = date.today()
    total_windows = 0

    print(f"Iniciando extração: {SERIES_START} → {today}")
    print(f"Janelas de {MAX_WINDOW} dias — aguarde...\n")

    while window_start < today:
        window_end = min(window_start + timedelta(days=MAX_WINDOW - 1), today)
        df = fetch_window(window_start, window_end)

        if not df.empty:
            all_frames.append(df)
            print(f"  ✓ {window_start} → {window_end}  ({len(df)} dias)")
        else:
            print(f"  – {window_start} → {window_end}  (sem dados)")

        window_start  = window_end + timedelta(days=1)
        total_windows += 1
        time.sleep(SLEEP_SEC)

    if not all_frames:
        print("\n[ERRO] Nenhum dado retornado. Verifique a conexão ou o slug.")
        return

    df_all = pd.concat(all_frames, ignore_index=True)
    df_all["date"] = pd.to_datetime(df_all["date"])
    df_all = (
        df_all
        .sort_values("date")
        .drop_duplicates("date")
        .reset_index(drop=True)
    )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df_all.to_csv(OUT_PATH, index=False, date_format="%Y-%m-%d")

    print(f"\n✓ Concluído.")
    print(f"  Janelas processadas : {total_windows}")
    print(f"  Dias com dados      : {len(df_all)}")
    print(f"  Período             : {df_all['date'].min().date()} → {df_all['date'].max().date()}")
    print(f"  Arquivo gerado      : {OUT_PATH}")


if __name__ == "__main__":
    main()
