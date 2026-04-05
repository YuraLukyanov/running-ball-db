# running-ball-db

Production PostgreSQL schema and data ingestion pipeline for **sports match statistics**.
Target: **Amazon RDS PostgreSQL 15+**

---

## Repository Structure

```
running-ball-db/
├── migrations/              # Versioned DDL scripts (applied in order)
│   ├── V001__baseline_schema.sql
│   ├── V002__indexes.sql
│   └── V003__materialized_views.sql
├── seeds/                   # Reference / lookup data
│   ├── S001__stat_types.sql
│   └── S002__event_types.sql
├── scripts/                 # Tooling
│   ├── ingest.py            # CSV/XLS → RDS bulk ingestion
│   └── refresh_views.py     # Refresh materialized views
├── data/
│   └── raw/                 # Drop input files here (.csv / .xls / .xlsx)
├── tests/
│   └── test_ingest.py
├── docs/
│   └── schema_diagram.md
├── .env.example             # Connection string template
├── requirements.txt
└── README.md
```

---

## Quick Start

### 1. Clone & install dependencies

```bash
git clone <repo-url>
cd running-ball-db
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure connection

```bash
cp .env.example .env
# Edit .env with your RDS credentials
```

### 3. Apply migrations

```bash
python scripts/migrate.py
```

### 4. Run ingestion

```bash
# Single file
python scripts/ingest.py --file data/raw/match_2273387.xls

# All files in a directory
python scripts/ingest.py --dir data/raw/

# Dry run (prints SQL, no DB writes)
python scripts/ingest.py --dir data/raw/ --dry-run
```

---

## Migration Versioning

Migrations follow **Flyway-style naming**: `V{version}__{description}.sql`
Applied in version order; each migration is checksummed and tracked in the
`schema_migrations` table (auto-created on first run).

---

## Schema Summary

| Table                | Purpose                                         |
|----------------------|-------------------------------------------------|
| `countries`          | Country reference (ISO codes)                   |
| `competitions`       | Leagues / tournaments                           |
| `teams`              | Team master data                                |
| `matches`            | Fixture metadata & final scores                 |
| `statistic_types`    | EAV catalog of all stat metrics                 |
| `match_statistics`   | Per-team, per-period stat values (EAV)          |
| `event_types`        | Event code catalog (from feed provider)         |
| `match_events`       | Append-only match timeline                      |
| `match_periods`      | Half/period start–end times                     |

---

## Environment Variables

| Variable              | Description                                        |
|-----------------------|----------------------------------------------------|
| `DB_URL`              | SQLAlchemy URL `postgresql://user:pw@host:5432/db` |
| `DB_POOL_SIZE`        | Connection pool size (default: 5)                  |
| `DB_BATCH_SIZE`       | Rows per bulk insert batch (default: 500)          |
| `LOG_LEVEL`           | `DEBUG` / `INFO` / `WARNING` (default: `INFO`)     |
