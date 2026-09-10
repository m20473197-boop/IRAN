# Database Migrations

## Current strategy (stage 1)

- The schema is created with SQLAlchemy `Base.metadata.create_all`:
  - automatically on bot startup (via `post_init` in `main.py`),
  - or manually via `python scripts/init_db.py`.
- `create_all` only **adds missing tables** — it never drops or alters
  existing data, so player data survives bot restarts.

## Future strategy

As soon as the schema starts **changing** (new columns on existing tables,
renames, data migrations), [Alembic](https://alembic.sqlalchemy.org) will be
introduced and its version files will live in this package.

The models already attach a stable naming convention to all constraints,
which keeps that transition smooth.
