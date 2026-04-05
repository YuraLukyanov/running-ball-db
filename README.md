# running-ball-db

Versioned PostgreSQL schema management for the **sports match statistics** platform.
Target: **Amazon RDS PostgreSQL 15+**

> Data ingestion and transformation scripts live in the companion repository:
> [`running-ball-export-transformer`](https://github.com/YuraLukyanov/running-ball-export-transformer)

---

## Repository Structure

```
running-ball-db/
├── migrations/                  # Versioned DDL scripts (applied in order)
│   ├── V001__baseline_schema.sql
│   ├── V002__indexes.sql
│   └── V003__materialized_views.sql
├── seeds/                       # Static reference / lookup data
│   ├── S001__stat_types.sql
│   └── S002__event_types.sql
├── scripts/
│   └── migrate.py               # Migration runner (Flyway-style)
└── docs/
    └── schema_diagram.md
```

---

## Quick Start

### 1. Install dependencies

```bash
pip install sqlalchemy psycopg2-binary python-dotenv click
```

### 2. Configure connection

```bash
cp .env.example .env
# Edit .env — set DB_URL to your RDS connection string
```

### 3. Apply migrations

```bash
# Apply DDL migrations only
python scripts/migrate.py

# Apply DDL + seed reference data
python scripts/migrate.py --seeds
```

### 4. Dry run (print SQL without executing)

```bash
python scripts/migrate.py --dry-run
```

---

## Migration Versioning

Migrations follow **Flyway-style naming**: `V{version}__{description}.sql`

- Applied in strict version order
- Each migration is checksummed and tracked in `schema_migrations` table (auto-created on first run)
- Re-running is fully idempotent — already-applied migrations are skipped

**Adding a new migration:**

```bash
# Create the next version file
touch migrations/V004__add_player_stats.sql
# Edit it, then apply:
python scripts/migrate.py
```

---

## Schema Summary

| Table                | Purpose                                           |
|----------------------|---------------------------------------------------|
| `countries`          | Country reference (ISO codes)                     |
| `competitions`       | Leagues / tournaments per country & season        |
| `teams`              | Team master data                                  |
| `matches`            | Fixture metadata & scores                         |
| `statistic_types`    | EAV catalog — all stat metrics (no hardcoded cols)|
| `match_statistics`   | Per-team, per-period stat values (EAV)            |
| `event_types`        | Event code catalog (from feed provider)           |
| `match_events`       | Append-only match timeline                        |
| `match_periods`      | Half/period start–end wall-clock times            |

See [`docs/schema_diagram.md`](docs/schema_diagram.md) for the full ER diagram.

---

## Environment Variables

| Variable       | Description                                           |
|----------------|-------------------------------------------------------|
| `DB_URL`       | `postgresql://user:password@rds-host:5432/sports_db`  |
| `LOG_LEVEL`    | `DEBUG` / `INFO` / `WARNING` (default: `INFO`)        |
