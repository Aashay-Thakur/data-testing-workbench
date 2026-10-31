# Data testing workbench

Local proof of concept for reading a dbt project on Snowflake and scoring checks while a change is in progress. The browser never sees credentials. There is no login.

The API uses the query role from the environment. It rejects anything that is not a single `SELECT`, `SHOW`, `DESCRIBE`, or `information_schema` read, blocks unbounded `SELECT *`, and caps samples at 100 rows. It does not call `dbt run`, `dbt build`, or `dbt test`. `dbt parse` and `dbt compile` are allowed and write the query-role credentials into a temporary `profiles.yml` that is deleted after the command.

## Configure

```bash
cp .env.example .env
```

Fill in the Snowflake query-role settings and the read-only GitHub settings. Do not commit `.env`.

## API

```bash
cd api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

If `python3 -m venv` cannot create a virtualenv, install `virtualenv` and run `virtualenv .venv` instead.

Tests do not need Snowflake:

```bash
cd api
.venv/bin/pytest
```

## UI

In another shell:

```bash
cd web
npm install
npm run dev
```

Open http://127.0.0.1:5173. The dev server proxies `/api` to the API on port 8000.

SQLite under `api/data/` stores saved checks and run history only. It does not store secrets.
