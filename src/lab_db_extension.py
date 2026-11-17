"""Isolated SQLite lab for the REA inventory-ledger exercise.

Only databases named lab_*.db, lab_*.sqlite, or lab_*.sqlite3 are accepted.
This module does not replace or claim integration with an application API.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import uuid
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

MIGRATION_ID = "001_inventory_ledger"
MIGRATION_FILE = Path(__file__).parent / "migrations" / f"{MIGRATION_ID}.sql"
ALLOWED_SUFFIXES = {".db", ".sqlite", ".sqlite3"}


def safe_path(value: str | Path) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.name.lower().startswith("lab_") or path.suffix.lower() not in ALLOWED_SUFFIXES:
        raise ValueError("use um banco de laboratório chamado lab_*.db, lab_*.sqlite ou lab_*.sqlite3")
    return path


def connect(path: str | Path) -> sqlite3.Connection:
    db_path = safe_path(path)
    db = sqlite3.connect(db_path, timeout=15, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA busy_timeout = 15000")
    return db


@contextmanager
def _transaction(db: sqlite3.Connection) -> Iterator[None]:
    db.execute("BEGIN IMMEDIATE")
    try:
        yield
        db.execute("COMMIT")
    except BaseException:
        if db.in_transaction:
            db.execute("ROLLBACK")
        raise


def _statements(sql: str) -> Iterator[str]:
    pending = ""
    for line in sql.splitlines():
        pending += line + "\n"
        if sqlite3.complete_statement(pending):
            statement = pending.strip()
            if statement:
                yield statement
            pending = ""
    if pending.strip():
        raise ValueError("arquivo SQL contém uma instrução incompleta")


def _require_columns(db: sqlite3.Connection, table: str, expected: set[str]) -> None:
    columns = {
        row["name"] for row in db.execute(f'PRAGMA table_info("{table}")').fetchall()
    }
    if not expected.issubset(columns):
        missing = ", ".join(sorted(expected - columns))
        raise ValueError(f"esquema-base incompatível: {table} sem coluna(s): {missing}")


def _require_baseline(db: sqlite3.Connection) -> None:
    _require_columns(db, "products", {"id", "sku", "name", "category", "stock"})
    _require_columns(db, "compatibility", {"bike_id", "product_id"})
    _require_columns(db, "orders", {"id"})
    _require_columns(db, "order_items", {"order_id", "product_id", "quantity"})


def _require_migration(db: sqlite3.Connection) -> None:
    if not db.execute(
        "SELECT 1 FROM schema_migrations WHERE version = ?", (MIGRATION_ID,)
    ).fetchone():
        raise ValueError("migração pendente; execute migrate antes desta operação")


def init_database(path: str | Path) -> int:
    """Create a disposable example baseline; never overwrite an existing file."""
    db_path = safe_path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        db_path.open("xb").close()
    except FileExistsError:
        raise FileExistsError(f"banco já existe e não será sobrescrito: {db_path}") from None

    try:
        with closing(connect(db_path)) as db:
            db.executescript(
                """
                CREATE TABLE products (
                    id INTEGER PRIMARY KEY,
                    sku TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    stock INTEGER NOT NULL CHECK (stock >= 0)
                );
                CREATE TABLE compatibility (
                    id INTEGER PRIMARY KEY,
                    bike_id TEXT NOT NULL,
                    product_id INTEGER NOT NULL REFERENCES products(id),
                    UNIQUE (bike_id, product_id)
                );
                CREATE TABLE orders (
                    id TEXT PRIMARY KEY,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE order_items (
                    id INTEGER PRIMARY KEY,
                    order_id TEXT NOT NULL REFERENCES orders(id),
                    product_id INTEGER NOT NULL REFERENCES products(id),
                    quantity INTEGER NOT NULL CHECK (quantity > 0),
                    UNIQUE (order_id, product_id)
                );
                INSERT INTO products (sku, name, category, stock) VALUES
                    ('R2-FR-001', 'Pastilha de freio dianteira', 'Freios', 12),
                    ('R2-COR-002', 'Kit relação', 'Transmissão', 8),
                    ('R2-LUB-003', 'Óleo para motor', 'Lubrificantes', 0);
                INSERT INTO compatibility (bike_id, product_id) VALUES
                    ('MOTO-DEMO-150', 1),
                    ('MOTO-DEMO-150', 2);
                """
            )
    except BaseException:
        db_path.unlink(missing_ok=True)
        raise

    return 3


def migrate(path: str | Path) -> bool:
    db_path = safe_path(path)
    if not db_path.is_file():
        raise FileNotFoundError(f"banco não encontrado; execute init primeiro: {db_path}")

    sql = MIGRATION_FILE.read_text(encoding="utf-8")
    with closing(connect(db_path)) as db:
        _require_baseline(db)
        with _transaction(db):
            db.execute(
                """CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )"""
            )
            if db.execute(
                "SELECT 1 FROM schema_migrations WHERE version = ?", (MIGRATION_ID,)
            ).fetchone():
                return False

            for statement in _statements(sql):
                db.execute(statement)

            # T0 captures the current balance only; it does not reconstruct old sales.
            db.execute(
                """INSERT INTO inventory_movements
                       (product_id, delta_qty, movement_type, reason)
                   SELECT id, stock, 'OPENING', 'saldo no instante da migracao'
                   FROM products
                   WHERE stock <> 0"""
            )
            db.execute(
                "INSERT INTO schema_migrations (version) VALUES (?)", (MIGRATION_ID,)
            )
    return True


def adjust_stock(
    path: str | Path, sku: str, quantity: int, reason: str
) -> dict[str, Any]:
    if not sku.strip():
        raise ValueError("SKU obrigatório")
    if not 0 <= quantity <= 99_999:
        raise ValueError("estoque deve estar entre 0 e 99999")
    normalized_reason = reason.strip()
    if len(normalized_reason) < 5:
        raise ValueError("motivo obrigatório (mínimo 5 caracteres)")

    with closing(connect(path)) as db:
        with _transaction(db):
            _require_migration(db)
            product = db.execute(
                "SELECT id, stock FROM products WHERE sku = ?", (sku.strip(),)
            ).fetchone()
            if product is None:
                raise ValueError(f"SKU não encontrado: {sku}")

            old_stock = product["stock"]
            delta = quantity - old_stock
            if delta:
                db.execute(
                    "UPDATE products SET stock = ? WHERE id = ?",
                    (quantity, product["id"]),
                )
                db.execute(
                    """INSERT INTO inventory_movements
                           (product_id, delta_qty, movement_type, reason)
                       VALUES (?, ?, 'ADJUSTMENT', ?)""",
                    (product["id"], delta, normalized_reason),
                )
    return {"sku": sku.strip(), "before": old_stock, "after": quantity, "delta": delta}


def create_order(
    path: str | Path, idempotency_key: str, items: dict[str, int]
) -> dict[str, Any]:
    key = idempotency_key.strip()
    if not key or len(key) > 128:
        raise ValueError("idempotency-key deve conter de 1 a 128 caracteres")
    if not items:
        raise ValueError("o pedido precisa conter ao menos um produto")
    normalized: dict[str, int] = {}
    for sku, quantity in items.items():
        sku = sku.strip()
        if not sku or quantity <= 0:
            raise ValueError("cada item precisa de SKU e quantidade positiva")
        normalized[sku] = normalized.get(sku, 0) + quantity

    with closing(connect(path)) as db:
        with _transaction(db):
            _require_migration(db)
            existing = db.execute(
                "SELECT id FROM orders WHERE idempotency_key = ?", (key,)
            ).fetchone()
            if existing is not None:
                previous = {
                    row["sku"]: row["quantity"]
                    for row in db.execute(
                        """SELECT p.sku, oi.quantity
                           FROM order_items oi
                           JOIN products p ON p.id = oi.product_id
                           WHERE oi.order_id = ?""",
                        (existing["id"],),
                    )
                }
                if previous != normalized:
                    raise ValueError("idempotency-key já foi usada com itens diferentes")
                return {"order_id": existing["id"], "replayed": True}

            products: list[tuple[sqlite3.Row, int]] = []
            for sku, quantity in sorted(normalized.items()):
                product = db.execute(
                    "SELECT id, stock FROM products WHERE sku = ?", (sku,)
                ).fetchone()
                if product is None:
                    raise ValueError(f"SKU não encontrado: {sku}")
                if product["stock"] < quantity:
                    raise ValueError(f"estoque insuficiente para {sku}")
                products.append((product, quantity))

            order_id = str(uuid.uuid4())
            db.execute(
                "INSERT INTO orders (id, idempotency_key) VALUES (?, ?)",
                (order_id, key),
            )
            for product, quantity in products:
                updated = db.execute(
                    """UPDATE products SET stock = stock - ?
                       WHERE id = ? AND stock >= ?""",
                    (quantity, product["id"], quantity),
                )
                if updated.rowcount != 1:
                    raise ValueError("estoque insuficiente durante o débito")
                db.execute(
                    """INSERT INTO order_items (order_id, product_id, quantity)
                       VALUES (?, ?, ?)""",
                    (order_id, product["id"], quantity),
                )
                db.execute(
                    """INSERT INTO inventory_movements
                           (product_id, delta_qty, movement_type, order_id, reason)
                       VALUES (?, ?, 'SALE', ?, ?)""",
                    (product["id"], -quantity, order_id, f"venda pedido {order_id}"),
                )
    return {"order_id": order_id, "replayed": False}


def _reconcile_db(db: sqlite3.Connection) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in db.execute(
            """SELECT p.sku, p.stock,
                      COALESCE(SUM(m.delta_qty), 0) AS ledger_balance
               FROM products p
               LEFT JOIN inventory_movements m ON m.product_id = p.id
               GROUP BY p.id
               HAVING p.stock <> COALESCE(SUM(m.delta_qty), 0)
               ORDER BY p.sku"""
        )
    ]


def reconcile(path: str | Path) -> list[dict[str, Any]]:
    with closing(connect(path)) as db:
        _require_migration(db)
        return _reconcile_db(db)


def verify(path: str | Path) -> dict[str, Any]:
    with closing(connect(path)) as db:
        db.execute("BEGIN")
        try:
            _require_migration(db)
            integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
            foreign_keys = [tuple(row) for row in db.execute("PRAGMA foreign_key_check")]
            discrepancies = _reconcile_db(db)
            db.execute("COMMIT")
        except BaseException:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise
    result = {
        "sqlite_version": sqlite3.sqlite_version,
        "integrity_check": integrity,
        "foreign_key_violations": foreign_keys,
        "ledger_discrepancies": discrepancies,
        "passed": integrity == "ok" and not foreign_keys and not discrepancies,
    }
    if not result["passed"]:
        raise RuntimeError(json.dumps(result, ensure_ascii=False))
    return result


def backup(path: str | Path) -> tuple[Path, str]:
    source_path = safe_path(path)
    if not source_path.is_file():
        raise FileNotFoundError(f"banco não encontrado: {source_path}")
    backup_path = source_path.with_name(f"{source_path.stem}_backup{source_path.suffix}")
    if backup_path.exists():
        raise FileExistsError(f"backup já existe e não será sobrescrito: {backup_path}")

    try:
        backup_path.open("xb").close()
    except FileExistsError:
        raise FileExistsError(f"backup já existe e não será sobrescrito: {backup_path}") from None
    checksum_path = backup_path.with_suffix(backup_path.suffix + ".sha256")
    metadata_path = backup_path.with_suffix(backup_path.suffix + ".metadata.json")
    created_sidecars: list[Path] = []
    try:
        with closing(connect(source_path)) as source, closing(
            sqlite3.connect(backup_path)
        ) as destination:
            source.backup(destination)
        digest = hashlib.sha256(backup_path.read_bytes()).hexdigest()
        with checksum_path.open("x", encoding="utf-8") as checksum_file:
            created_sidecars.append(checksum_path)
            checksum_file.write(f"{digest}  {backup_path.name}\n")
        metadata = {
            "source": str(source_path),
            "backup": str(backup_path),
            "sha256": digest,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "sqlite_version": sqlite3.sqlite_version,
        }
        with metadata_path.open("x", encoding="utf-8") as metadata_file:
            created_sidecars.append(metadata_path)
            metadata_file.write(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    except BaseException:
        backup_path.unlink(missing_ok=True)
        for sidecar in created_sidecars:
            sidecar.unlink(missing_ok=True)
        raise
    return backup_path, digest


def restore(path: str | Path) -> tuple[Path, str]:
    source_path = safe_path(path)
    backup_path = source_path.with_name(f"{source_path.stem}_backup{source_path.suffix}")
    target_path = source_path.with_name(f"{source_path.stem}_restored{source_path.suffix}")
    if not backup_path.is_file():
        raise FileNotFoundError(f"backup ausente: {backup_path}")
    if target_path.exists():
        raise FileExistsError(f"restauração já existe e não será sobrescrita: {target_path}")

    checksum_path = backup_path.with_suffix(backup_path.suffix + ".sha256")
    checksum_fields = checksum_path.read_text(encoding="utf-8").split()
    if (
        not checksum_fields
        or len(checksum_fields[0]) != 64
        or any(character not in "0123456789abcdefABCDEF" for character in checksum_fields[0])
    ):
        raise ValueError("manifesto SHA-256 do backup inválido")
    expected_hash = checksum_fields[0]
    actual_hash = hashlib.sha256(backup_path.read_bytes()).hexdigest()
    if actual_hash != expected_hash:
        raise ValueError("SHA-256 do backup não confere")

    try:
        target_path.open("xb").close()
    except FileExistsError:
        raise FileExistsError(
            f"restauração já existe e não será sobrescrita: {target_path}"
        ) from None

    try:
        with closing(sqlite3.connect(backup_path)) as source, closing(
            sqlite3.connect(target_path)
        ) as destination:
            source.backup(destination)
        with closing(connect(target_path)) as restored:
            integrity = restored.execute("PRAGMA integrity_check").fetchone()[0]
            foreign_keys = list(restored.execute("PRAGMA foreign_key_check"))
            has_migration_table = restored.execute(
                """SELECT 1 FROM sqlite_master
                   WHERE type = 'table' AND name = 'schema_migrations'"""
            ).fetchone()
            migrated = (
                restored.execute(
                    "SELECT 1 FROM schema_migrations WHERE version = ?",
                    (MIGRATION_ID,),
                ).fetchone()
                if has_migration_table
                else None
            )
            if migrated:
                discrepancies = _reconcile_db(restored)
                if discrepancies:
                    raise ValueError(f"restauração com divergências de estoque: {discrepancies}")
            if integrity != "ok" or foreign_keys:
                raise ValueError(
                    f"restauração inválida: integrity={integrity}, "
                    f"foreign_key_violations={len(foreign_keys)}"
                )
    except BaseException:
        target_path.unlink(missing_ok=True)
        raise
    return target_path, actual_hash


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Laboratório isolado SQLite para o exercício REA (somente lab_*.db)"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ("init", "migrate", "backup", "restore", "verify"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--db", required=True)

    adjust_parser = subparsers.add_parser("adjust")
    adjust_parser.add_argument("--db", required=True)
    adjust_parser.add_argument("--sku", required=True)
    adjust_parser.add_argument("--quantity", required=True, type=int)
    adjust_parser.add_argument("--reason", required=True)

    order_parser = subparsers.add_parser("sell")
    order_parser.add_argument("--db", required=True)
    order_parser.add_argument("--idempotency-key", required=True)
    order_parser.add_argument(
        "--item",
        action="append",
        required=True,
        metavar="SKU=QUANTIDADE",
        help="pode ser repetido para incluir vários produtos",
    )
    return parser


def _parse_items(values: list[str]) -> dict[str, int]:
    items: dict[str, int] = {}
    for value in values:
        sku, separator, quantity = value.partition("=")
        if not separator:
            raise ValueError(f"item inválido {value!r}; use SKU=QUANTIDADE")
        try:
            parsed_quantity = int(quantity)
        except ValueError as exc:
            raise ValueError(f"quantidade inválida no item {value!r}") from exc
        items[sku] = items.get(sku, 0) + parsed_quantity
    return items


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "init":
            count = init_database(args.db)
            result: Any = {"initialized": True, "products": count}
        elif args.command == "migrate":
            result = {"migration_applied": migrate(args.db), "version": MIGRATION_ID}
        elif args.command == "backup":
            backup_path, digest = backup(args.db)
            result = {"backup": str(backup_path), "sha256": digest}
        elif args.command == "restore":
            restored_path, digest = restore(args.db)
            result = {"restored": str(restored_path), "sha256": digest}
        elif args.command == "adjust":
            result = adjust_stock(args.db, args.sku, args.quantity, args.reason)
        elif args.command == "sell":
            result = create_order(args.db, args.idempotency_key, _parse_items(args.item))
        else:
            result = verify(args.db)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, sqlite3.Error, ValueError, RuntimeError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
