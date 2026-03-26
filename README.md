# Beef Cutout Database — USDA AMS

Base de dados histórica e atualização diária automática dos preços de **Choice** e **Select** do boxed beef cutout (LM_XB403 / AMS_2453), publicados pelo USDA Agricultural Marketing Service.

---

## Estrutura do repositório

```
beef-cutout-db/
├── data/
│   └── beef_cutout.csv          ← série histórica completa (atualizada diariamente)
├── scripts/
│   ├── build_history.py         ← extração histórica (roda uma única vez)
│   └── update_beef.py           ← atualização diária (GitHub Actions)
├── .github/
│   └── workflows/
│       └── daily_update.yml     ← agendamento automático
├── requirements.txt
└── README.md
```

---

## Formato do CSV

| Coluna   | Tipo   | Descrição                                |
|----------|--------|------------------------------------------|
| `date`   | date   | Data do relatório (YYYY-MM-DD)           |
| `choice` | float  | Cutout Choice 600–900# (US$/cwt)         |
| `select` | float  | Cutout Select 600–900# (US$/cwt)         |
| `spread` | float  | Choice − Select (US$/cwt)                |

Fonte oficial: **USDA AMS LM_XB403** — National Daily Boxed Beef Cutout & Boxed Beef Cuts, Negotiated Sales – PM.

---

## Setup (passo a passo)

### 1. Clonar o repositório

```bash
git clone https://github.com/SEU_USER/beef-cutout-db.git
cd beef-cutout-db
pip install -r requirements.txt
```

### 2. Adicionar o secret da API key no GitHub

```
Repositório → Settings → Secrets and variables → Actions → New repository secret

  Name:  USDA_API_KEY
  Value: sua_api_key_do_mymarketnews
```

A key é usada para as atualizações diárias via MARS API. Para obtê-la:
[mymarketnews.ams.usda.gov](https://mymarketnews.ams.usda.gov) → Login → Account → API Key

### 3. Gerar o histórico completo (uma única vez, localmente)

```bash
python scripts/build_history.py
```

Isso puxa toda a série desde **02/04/2001** via DataMart público (sem autenticação), em janelas de 180 dias. O processo leva ~5 minutos e gera `data/beef_cutout.csv`.

### 4. Commitar o CSV gerado

```bash
git add data/beef_cutout.csv
git commit -m "data: série histórica inicial (2001–hoje)"
git push
```

### 5. Ativar o workflow

O arquivo `.github/workflows/daily_update.yml` já está configurado. Ele roda automaticamente de **segunda a sexta às 16h30 EST** (21h30 UTC).

Para rodar manualmente: `Actions → Daily USDA beef cutout update → Run workflow`

---

## Como consumir os dados no dashboard

O CSV fica disponível numa URL estável e pública (mesmo em repos privados, com token):

```python
import pandas as pd

URL = "https://raw.githubusercontent.com/SEU_USER/beef-cutout-db/main/data/beef_cutout.csv"
df = pd.read_csv(URL, parse_dates=["date"])
```

Compatível com qualquer ferramenta: Streamlit, Dash, Plotly, Looker Studio, Power BI, etc.

---

## Fontes de dados

| Script            | API                    | Auth         | Cobertura         |
|-------------------|------------------------|--------------|-------------------|
| `build_history.py`| DataMart (MPR) v1.1    | Pública      | 2001 → hoje       |
| `update_beef.py`  | MARS API v1.2 (+ fallback DataMart) | API key | Diária contínua |

---

## Notas

- Feriados e dias sem relatório são ignorados automaticamente (o script detecta e não gera commit vazio).
- O workflow só faz `git push` se o CSV realmente mudou — sem commits desnecessários.
- O fallback para o DataMart garante continuidade caso a MARS API esteja temporariamente indisponível.
