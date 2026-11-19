"""Apply the SQL files in supabase/migrations/ in order.

Loads the repository .env and applies migrations with asyncpg; no psql needed.

Usage (PowerShell):
    $env:DATABASE_SYNC_URL = "postgresql://user:pass@host:port/db"
    python scripts/apply_migrations.py

Each file and its history record run in one transaction. Previously applied
files are skipped. Existing Docker-initialized databases are also supported.
"""
import asyncio
import os
import sys
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "supabase" / "migrations"
ORDER = sorted(path.name for path in MIGRATIONS_DIR.glob("*.sql"))


async def main() -> None:
    load_dotenv(MIGRATIONS_DIR.parent.parent / ".env")
    db_url = os.environ.get("DATABASE_SYNC_URL") or os.environ.get("DATABASE_URL")
    if not db_url:
        sys.exit("Set DATABASE_SYNC_URL (or DATABASE_URL) to your Postgres connection string.")
    db_url = db_url.replace("+asyncpg", "").replace("+psycopg2", "")

    conn = await asyncpg.connect(db_url)
    try:
        # Prevent simultaneous setup processes from applying the same file.
        await conn.execute("SELECT pg_advisory_lock(736812904)")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        # Ensure all existing tables with UUID primary key 'id' have DEFAULT gen_random_uuid()
        tables_with_id = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.columns 
            WHERE table_schema = 'public' 
              AND column_name = 'id' 
              AND udt_name = 'uuid' 
              AND column_default IS NULL
        """)
        for t in tables_with_id:
            tbl = t['table_name']
            try:
                await conn.execute(f'ALTER TABLE "{tbl}" ALTER COLUMN id SET DEFAULT gen_random_uuid()')
            except Exception:
                pass

        # Check if pgvector is available
        has_vector = False
        try:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            has_vector = True
        except Exception:
            print("   [INFO] PostgreSQL extension 'vector' is not installed locally. Using real[] fallback for embeddings.")

        # Ensure price_candles_1m is a partitioned table, not a stale regular table from a previous aborted run
        relkind = await conn.fetchval("SELECT relkind FROM pg_class WHERE relname = 'price_candles_1m'")
        if relkind and relkind != 'p':
            print("   [INFO] Resetting stale unpartitioned price_candles_1m table and partitions...")
            await conn.execute("DROP TABLE IF EXISTS price_candles_1m CASCADE")
            partitions = await conn.fetch("SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename LIKE 'price_candles_1m_%'")
            for p in partitions:
                await conn.execute(f"DROP TABLE IF EXISTS \"{p['tablename']}\" CASCADE")

        for name in ORDER:
            if await conn.fetchval("SELECT 1 FROM schema_migrations WHERE filename=$1", name):
                print(f"   already applied: {name}")
                continue
            sql = (MIGRATIONS_DIR / name).read_text(encoding="utf-8")

            if not has_vector:
                import re
                # Gracefully handle vector extension absence on Windows native Postgres
                sql = re.sub(r'CREATE\s+EXTENSION\s+IF\s+NOT\s+EXISTS\s+["\']?vector["\']?;?', '-- (vector extension skipped)', sql, flags=re.IGNORECASE)
                sql = re.sub(r'\bvector\s*\(\s*\d+\s*\)', 'real[]', sql, flags=re.IGNORECASE)
                sql = re.sub(
                    r'CREATE\s+INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?\w+\s+ON\s+\w+\s+USING\s+(?:ivfflat|hnsw)[^;]+;',
                    '-- (vector index skipped: pgvector not installed)',
                    sql,
                    flags=re.IGNORECASE | re.DOTALL
                )

            print(f"-> applying {name} ({len(sql):,} bytes)")
            async with conn.transaction():
                await conn.execute(sql)
                await conn.execute("INSERT INTO schema_migrations (filename) VALUES ($1) ON CONFLICT DO NOTHING", name)
            print(f"   ok: {name}")
    finally:
        await conn.close()
    print("All migrations applied.")


if __name__ == "__main__":
    asyncio.run(main())
