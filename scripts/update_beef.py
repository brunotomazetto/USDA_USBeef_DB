"""
update_beef.py
--------------
Roda todo dia via GitHub Actions.

Fonte: MyMarketNews MARS API - marsapi.ams.usda.gov
  · Requer API key (armazenada como GitHub Secret: USDA_API_KEY)
  · Autenticação: HTTP Basic Auth (key como usuário, senha vazia)
  · Cobre a série atual (cobertura diária contínua)

Fallback automático: se o MARS não retornar dados novos
  (ex: fora do período coberto), tenta o DataMart público.

Lógica:
  1. Lê beef_cutout.csv e identifica a última data registrada
  2. Busca os dias faltantes na API
  3. Faz append e salva o CSV atualizado
  4. O workflow faz git commit + push automaticamente
"""

import os
import sys
import requests
import pandas as pd
from datetime import date, timedelta
from pathlib import Path

MARS_URL     = "https://marsapi.ams.usda.gov/services/v1.2/reports/2453"
DATAMART_URL = "https://mpr.datamart.ams.usda.gov/services/v1.1/reports/2453"
CSV_PATH     = Path(__file__).parent.parent / "data" / "beef_cutout.csv"


def parse_results(results: list[dict]) -> pd.DataFrame:
    """Converte lista de resultados da API em DataFrame date/choice/select/spread."""
    rows: dict[str, dict] = {}
    for item in results:
        d     = str(item.get("report_date", ""))[:10]
        label = str(item.get("label", ""))
        raw   = item.get("value")
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


def fetch_mars(api_key: str, date_begin: date, date_end: date) -> pd.DataFrame:
    """Busca dados via MARS API (requer key)."""
    params = {
        "q": (
            f"report_begin_date={date_begin.strftime('%m/%d/%Y')}:"
            f"{date_end.strftime('%m/%d/%Y')};"
            "class=Cutout and Primal Values"
        ),
        "sort": "report_date",
    }
    r = requests.get(
        MARS_URL,
        params=params,
        auth=(api_key, ""),
        timeout=30,
    )
    r.raise_for_status()
    return parse_results(r.json().get("results", []))


def fetch_datamart(date_begin: date, date_end: date) -> pd.DataFrame:
    """Fallback: busca dados via DataMart público (sem autenticação)."""
    params = {
        "q": (
            f"report_date_begin={date_begin.strftime('%m/%d/%Y')};"
            f"report_date_end={date_end.strftime('%m/%d/%Y')};"
            "class=Cutout and Primal Values"
        ),
        "sort": "report_date",
    }
    r = requests.get(DATAMART_URL, params=params, timeout=30)
    r.raise_for_status()
    return parse_results(r.json().get("results", []))


def main() -> None:
    api_key = os.environ.get("USDA_API_KEY", "")
    if not api_key:
        print("[ERRO] Variável de ambiente USDA_API_KEY não definida.")
        sys.exit(1)

    if not CSV_PATH.exists():
        print(f"[ERRO] {CSV_PATH} não encontrado. Rode build_history.py primeiro.")
        sys.exit(1)

    df_hist = pd.read_csv(CSV_PATH, parse_dates=["date"])
    last_date = df_hist["date"].max().date()
    today     = date.today()

    # Relatório PM sai até ~15h30 EST. O cron roda às 21h30 UTC (16h30 EST).
    # Se hoje for fim de semana, não há relatório — encerra normalmente.
    if today.weekday() >= 5:
        print(f"Fim de semana ({today}). Sem relatório. Encerrando.")
        return

    if last_date >= today - timedelta(days=1):
        print(f"CSV já atualizado até {last_date}. Nada a fazer.")
        return

    date_begin = last_date + timedelta(days=1)
    print(f"Buscando dados: {date_begin} → {today}")

    # Tenta MARS primeiro; fallback para DataMart se vier vazio
    df_new = pd.DataFrame()
    try:
        df_new = fetch_mars(api_key, date_begin, today)
        if df_new.empty:
            print("  MARS sem dados — tentando DataMart...")
            df_new = fetch_datamart(date_begin, today)
        else:
            print(f"  Fonte: MARS API")
    except requests.RequestException as e:
        print(f"  MARS erro ({e}) — tentando DataMart...")
        try:
            df_new = fetch_datamart(date_begin, today)
            print(f"  Fonte: DataMart (fallback)")
        except requests.RequestException as e2:
            print(f"  [ERRO] DataMart também falhou: {e2}")
            sys.exit(1)

    if df_new.empty:
        print("Sem dados novos disponíveis (possível feriado ou relatório atrasado).")
        return

    df_new["date"] = pd.to_datetime(df_new["date"])
    df_out = (
        pd.concat([df_hist, df_new], ignore_index=True)
        .sort_values("date")
        .drop_duplicates("date")
        .reset_index(drop=True)
    )
    df_out.to_csv(CSV_PATH, index=False, date_format="%Y-%m-%d")

    print(f"✓ {len(df_new)} novo(s) dia(s) adicionado(s).")
    print(f"  Série atualizada: {df_out['date'].min().date()} → {df_out['date'].max().date()}")
    print(f"  Total de registros: {len(df_out)}")


if __name__ == "__main__":
    main()
