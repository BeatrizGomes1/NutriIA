"""Guarded Prisma deployment to nutriIA_test only; never changes .env.

Default: read-only preflight. --apply deploys the one expected migration.
--integration runs the existing rollback-isolated PostgreSQL integration tests.
"""
import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

BACKEND = Path(__file__).resolve().parents[1]
DATABASE = "nutriIA_test"
TARGET = "20261117000000_link_capture_analysis"
PREVIOUS = {
    "20261017000000_init_nutriia", "20261103000000_add_user_password_hash",
    "20261104000000_add_refresh_and_reset_tokens",
}
COLUMNS = {"request_id": "uuid", "analysis_id": "uuid",
           "analysis_origin": "character varying", "processing_status": "character varying"}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def identity(engine):
    with engine.connect() as connection:
        require(connection.scalar(text("SELECT current_database()")) == DATABASE,
                "STOP: database identity mismatch")


def preflight(engine):
    identity(engine)
    with engine.connect() as connection:
        rows = connection.execute(text('SELECT migration_name, checksum, finished_at, rolled_back_at '
                                       'FROM "_prisma_migrations" ORDER BY started_at')).mappings().all()
        names = []
        for row in rows:
            name = row["migration_name"]
            require(name in PREVIOUS | {TARGET}, "STOP: unexpected migration in database history")
            path = BACKEND / "prisma" / "migrations" / name / "migration.sql"
            require(row["finished_at"] is not None and row["rolled_back_at"] is None,
                    "STOP: failed, incomplete or rolled-back migration")
            require(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == row["checksum"],
                    f"STOP: migration checksum divergence: {name}")
            names.append(name)
        require(len(names) == len(set(names)) and PREVIOUS <= set(names),
                "STOP: missing or repeated migration history entries")
        local = {p.name for p in (BACKEND / "prisma" / "migrations").iterdir() if p.is_dir()}
        require(local == PREVIOUS | {TARGET}, "STOP: unexpected local migration directories")
        columns = connection.execute(text("SELECT column_name, data_type, is_nullable, character_maximum_length "
            "FROM information_schema.columns WHERE table_schema='public' AND table_name='product_captures'"))
        actual = {row.column_name: row for row in columns}
        applied = TARGET in names
        require(set(COLUMNS) <= set(actual) if applied else not set(COLUMNS).intersection(actual),
                "STOP: schema and migration history disagree")
        if applied:
            for name, datatype in COLUMNS.items():
                require(actual[name].data_type == datatype and actual[name].is_nullable == "YES",
                        "STOP: column type/nullability mismatch")
                if datatype == "character varying":
                    require(actual[name].character_maximum_length == 16, "STOP: column length mismatch")
        print(f"Database confirmed: {DATABASE}; checksums valid; target "
              f"{'applied' if applied else 'pending'}", flush=True)
        return applied


def snapshot(engine):
    identity(engine)
    with engine.connect() as connection:
        tables = connection.scalars(text("SELECT tablename FROM pg_tables WHERE schemaname='public' "
                                        "AND tablename <> '_prisma_migrations' ORDER BY tablename")).all()
        result = {}
        for table in tables:
            require(re.fullmatch(r"[a-z_]+", table), "STOP: unexpected application table name")
            # Exclude the four newly added NULL attributes when comparing legacy rows.
            excluded = "ARRAY['request_id','analysis_id','analysis_origin','processing_status']::text[]" if table == "product_captures" else "ARRAY[]::text[]"
            result[table] = tuple(connection.execute(text(
                f'SELECT count(*), md5(COALESCE(string_agg((to_jsonb(t) - {excluded})::text, '
                f"E'\\n' ORDER BY t.id), '')) FROM \"{table}\" t")).one())
        return result


def constraints(engine):
    identity(engine)
    with engine.connect() as connection:
        unique = connection.scalar(text("SELECT count(*) FROM pg_index i "
            "JOIN pg_class t ON t.oid=i.indrelid JOIN pg_namespace n ON n.oid=t.relnamespace "
            "WHERE n.nspname='public' AND t.relname='product_captures' AND i.indisunique "
            "AND i.indisvalid AND i.indpred IS NULL AND i.indnkeyatts=1 "
            "AND pg_get_indexdef(i.indexrelid,1,true)='request_id'"))
        fk = connection.scalar(text("SELECT count(*) FROM pg_constraint c "
            "WHERE c.conrelid='public.product_captures'::regclass AND c.contype='f' "
            "AND c.convalidated AND c.confrelid='public.analysis_results'::regclass AND c.confdeltype='n' "
            "AND pg_get_constraintdef(c.oid) LIKE 'FOREIGN KEY (analysis_id) REFERENCES analysis_results(id)%'"))
        require(unique == 1 and fk == 1, "STOP: request uniqueness or analysis foreign key mismatch")
        invalid = connection.scalar(text("SELECT count(*) FROM product_captures c "
            "LEFT JOIN analysis_results a ON a.id=c.analysis_id WHERE c.analysis_id IS NOT NULL "
            "AND (a.id IS NULL OR a.user_id<>c.user_id OR a.product_id<>c.product_id OR c.product_id IS NULL)"))
        require(invalid == 0, "STOP: invalid capture/analysis ownership or product links")
        print("Validated: 4 nullable columns, UUID request uniqueness, analysis FK/SET NULL, no invalid links", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--integration", action="store_true")
    args = parser.parse_args()
    explicit = os.environ.get("NUTRIIA_TEST_DATABASE_URL")
    source = explicit or os.environ.get("DATABASE_URL") or dotenv_values(BACKEND / ".env").get("DATABASE_URL")
    require(bool(source), "STOP: no PostgreSQL connection configuration")
    url = make_url(source)
    require(url.get_backend_name() in {"postgres", "postgresql"}, "STOP: PostgreSQL required")
    require(not explicit or url.database == DATABASE, "STOP: explicit test URL selects another database")
    url = url.set(drivername="postgresql", database=DATABASE)
    environment = os.environ.copy()
    environment["DATABASE_URL"] = url.render_as_string(hide_password=False)
    environment["NUTRIIA_TEST_DATABASE_URL"] = environment["DATABASE_URL"]
    query = dict(url.query)
    query.pop("schema", None)
    query["connect_timeout"] = "5"
    engine = create_engine(url.set(drivername="postgresql+psycopg", query=query), hide_parameters=True)
    node = shutil.which("node")
    cli = BACKEND / "node_modules" / "prisma" / "build" / "index.js"

    def prisma(*arguments, pending=False):
        identity(engine)  # Actual DB check immediately before every Prisma command.
        require(node and cli.is_file(), "STOP: local Prisma/Node missing; no network install attempted")
        result = subprocess.run([node, str(cli), *arguments, "--schema", "prisma/schema.prisma"],
            cwd=BACKEND, env=environment, capture_output=True, text=True, timeout=120)
        output = result.stdout + result.stderr
        safe = re.sub(r"postgres(?:ql)?://[^\s\"']+", "<database-url-redacted>", output)
        if url.password:
            safe = safe.replace(url.password, "<redacted>")
        print(safe.strip(), flush=True)
        require(result.returncode == 0 or pending and result.returncode == 1
                and TARGET in output and "P100" not in output and "Error:" not in output,
                "STOP: Prisma command failed; no further operations executed")

    try:
        applied = preflight(engine)
        before = snapshot(engine)
        prisma("validate")
        prisma("migrate", "status", pending=not applied)
        if args.apply and not applied:
            preflight(engine)
            prisma("migrate", "deploy")
            require(preflight(engine), "STOP: target migration not recorded")
            constraints(engine)
            require(snapshot(engine) == before, "STOP: application data changed during migration")
            print("Migration applied; all pre-existing application rows preserved", flush=True)
            prisma("migrate", "status")
            applied = True
        elif applied:
            constraints(engine)
        if args.integration:
            require(applied, "STOP: apply the target migration before integration validation")
            identity(engine)
            environment["NUTRIIA_RUN_DB_TESTS"] = "1"
            environment.pop("NUTRIIA_AUDIT_REAL_OFF", None)
            result = subprocess.run([sys.executable, "-B", "-m", "pytest", "tests/test_postgres_integration.py",
                "-q", "-s", "-p", "no:cacheprovider"], cwd=BACKEND, env=environment, timeout=180)
            require(result.returncode == 0, "STOP: integration tests failed")
            require(snapshot(engine) == before, "STOP: integration fixtures survived rollback")
            constraints(engine)
            print("Integration passed; application data unchanged", flush=True)
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Never expose connection strings, SQL parameters, credentials or test payloads.
        print(str(error) if isinstance(error, RuntimeError) else f"STOP: {type(error).__name__}; details suppressed",
              file=sys.stderr, flush=True)
        sys.exit(1)
