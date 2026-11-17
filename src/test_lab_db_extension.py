from __future__ import annotations

import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from pathlib import Path

try:
    from fastapi.testclient import TestClient
except ImportError:
    TestClient = None

try:
    from src.api import create_app
except ImportError:
    create_app = None
from src.lab_db_extension import (
    adjust_stock,
    backup,
    connect,
    create_order,
    init_database,
    main,
    migrate,
    reconcile,
    restore,
    verify,
)


class InventoryLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "lab_test.db"
        init_database(self.db_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_migration_is_additive_idempotent_and_records_t0(self) -> None:
        self.assertTrue(migrate(self.db_path))
        self.assertFalse(migrate(self.db_path))
        with closing(connect(self.db_path)) as db:
            self.assertEqual(
                db.execute("SELECT COUNT(*) FROM products").fetchone()[0], 3
            )
            opening = db.execute(
                """SELECT p.sku, m.delta_qty FROM inventory_movements m
                   JOIN products p ON p.id = m.product_id
                   WHERE m.movement_type = 'OPENING' ORDER BY p.sku"""
            ).fetchall()
            self.assertEqual(
                [(row["sku"], row["delta_qty"]) for row in opening],
                [("R2-COR-002", 8), ("R2-FR-001", 12)],
            )
        self.assertTrue(verify(self.db_path)["passed"])

    def test_failed_migration_rolls_back_schema_and_version(self) -> None:
        with closing(connect(self.db_path)) as db:
            db.executescript(
                """CREATE TABLE schema_migrations (
                       version TEXT PRIMARY KEY,
                       applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                   );
                   CREATE TRIGGER reject_migration_record
                   BEFORE INSERT ON schema_migrations
                   BEGIN SELECT RAISE(ABORT, 'simulated migration failure'); END;"""
            )
        with self.assertRaises(sqlite3.IntegrityError):
            migrate(self.db_path)
        with closing(connect(self.db_path)) as db:
            tables = {
                row["name"]
                for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            self.assertIn("schema_migrations", tables)
            self.assertNotIn("inventory_movements", tables)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0], 0)

    def test_red_unlogged_stock_change_is_detected(self) -> None:
        migrate(self.db_path)
        with closing(connect(self.db_path)) as db:
            db.execute("UPDATE products SET stock = stock + 1 WHERE sku = ?", ("R2-FR-001",))
        discrepancies = reconcile(self.db_path)
        self.assertEqual(len(discrepancies), 1)
        self.assertEqual(discrepancies[0]["sku"], "R2-FR-001")
        with self.assertRaises(RuntimeError):
            verify(self.db_path)

    def test_adjustment_updates_stock_and_ledger_together(self) -> None:
        migrate(self.db_path)
        outcome = adjust_stock(self.db_path, "R2-FR-001", 15, "inventario aula")
        self.assertEqual(outcome["delta"], 3)
        self.assertTrue(verify(self.db_path)["passed"])

    def test_ledger_failure_rolls_stock_update_back(self) -> None:
        migrate(self.db_path)
        with closing(connect(self.db_path)) as db:
            db.execute(
                """CREATE TRIGGER reject_adjustment
                   BEFORE INSERT ON inventory_movements
                   WHEN NEW.movement_type = 'ADJUSTMENT'
                   BEGIN SELECT RAISE(ABORT, 'simulated failure'); END"""
            )
        with self.assertRaises(sqlite3.IntegrityError):
            adjust_stock(self.db_path, "R2-FR-001", 15, "inventario aula")
        with closing(connect(self.db_path)) as db:
            stock = db.execute(
                "SELECT stock FROM products WHERE sku = ?", ("R2-FR-001",)
            ).fetchone()[0]
        self.assertEqual(stock, 12)

    def test_order_replay_debits_once_and_conflicting_replay_fails(self) -> None:
        migrate(self.db_path)
        first = create_order(
            self.db_path, "request-123", {"R2-FR-001": 2, "R2-COR-002": 1}
        )
        replay = create_order(
            self.db_path, "request-123", {"R2-COR-002": 1, "R2-FR-001": 2}
        )
        self.assertFalse(first["replayed"])
        self.assertTrue(replay["replayed"])
        with self.assertRaisesRegex(ValueError, "itens diferentes"):
            create_order(self.db_path, "request-123", {"R2-FR-001": 1})
        with closing(connect(self.db_path)) as db:
            self.assertEqual(
                db.execute("SELECT stock FROM products WHERE sku = 'R2-FR-001'").fetchone()[0],
                10,
            )
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) FROM inventory_movements WHERE movement_type = 'SALE'"
                ).fetchone()[0],
                2,
            )
        self.assertTrue(verify(self.db_path)["passed"])

    def test_order_insufficient_stock_rolls_back_everything(self) -> None:
        migrate(self.db_path)
        with self.assertRaisesRegex(ValueError, "estoque insuficiente"):
            create_order(self.db_path, "request-fail", {"R2-FR-001": 13})
        with closing(connect(self.db_path)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM orders").fetchone()[0], 0)
            self.assertEqual(
                db.execute("SELECT stock FROM products WHERE sku = 'R2-FR-001'").fetchone()[0],
                12,
            )

    def test_concurrent_replay_creates_one_order_and_one_debit(self) -> None:
        migrate(self.db_path)
        results: list[dict[str, object]] = []
        errors: list[BaseException] = []

        def place_order() -> None:
            try:
                results.append(
                    create_order(self.db_path, "concurrent-key", {"R2-FR-001": 2})
                )
            except BaseException as exc:
                errors.append(exc)

        workers = [threading.Thread(target=place_order) for _ in range(2)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
        self.assertEqual(errors, [])
        self.assertEqual(sum(not result["replayed"] for result in results), 1)
        with closing(connect(self.db_path)) as db:
            self.assertEqual(
                db.execute("SELECT stock FROM products WHERE sku = 'R2-FR-001'").fetchone()[0],
                10,
            )
            self.assertEqual(db.execute("SELECT COUNT(*) FROM orders").fetchone()[0], 1)
        self.assertTrue(verify(self.db_path)["passed"])

    def test_backup_restore_hash_and_integrity(self) -> None:
        migrate(self.db_path)
        backup_path, digest = backup(self.db_path)
        restored_path, restored_digest = restore(self.db_path)
        self.assertEqual(backup_path.name, "lab_test_backup.db")
        self.assertEqual(restored_path.name, "lab_test_restored.db")
        self.assertEqual(digest, restored_digest)
        self.assertTrue(verify(restored_path)["passed"])

    def test_restore_rejects_backup_with_invalid_hash(self) -> None:
        backup_path, _ = backup(self.db_path)
        backup_path.with_suffix(backup_path.suffix + ".sha256").write_text(
            "not-a-hash\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            restore(self.db_path)
        self.assertFalse(self.db_path.with_name("lab_test_restored.db").exists())

    def test_baseline_backup_can_be_restored_before_migration(self) -> None:
        backup(self.db_path)
        restored_path, _ = restore(self.db_path)
        self.assertTrue(migrate(restored_path))
        self.assertTrue(verify(restored_path)["passed"])

    @unittest.skipUnless(
        TestClient is not None and create_app is not None,
        "dependências opcionais FastAPI não instaladas",
    )
    def test_g_db5_api_and_cli_register_inventory_movements(self) -> None:
        migrate(self.db_path)

        client = TestClient(create_app(self.db_path))
        api_response = client.post(
            "/inventory/adjust",
            json={
                "sku": "R2-FR-001",
                "quantity": 15,
                "reason": "inventario via API",
            },
        )
        self.assertEqual(api_response.status_code, 200)

        cli_result = main([
            "sell",
            "--db",
            str(self.db_path),
            "--idempotency-key",
            "g-db5-cli-pedido",
            "--item",
            "R2-FR-001=2",
        ])
        self.assertEqual(cli_result, 0)

        with closing(connect(self.db_path)) as db:
            stock = db.execute(
                "SELECT stock FROM products WHERE sku = 'R2-FR-001'"
            ).fetchone()[0]
            movements = db.execute(
                """SELECT movement_type, delta_qty
                   FROM inventory_movements
                   JOIN products ON products.id = inventory_movements.product_id
                   WHERE products.sku = 'R2-FR-001'
                     AND movement_type IN ('ADJUSTMENT', 'SALE')
                   ORDER BY inventory_movements.id"""
            ).fetchall()

        self.assertEqual(stock, 13)
        self.assertEqual(
            [(row["movement_type"], row["delta_qty"]) for row in movements],
            [("ADJUSTMENT", 3), ("SALE", -2)],
        )
        self.assertTrue(verify(self.db_path)["passed"])

    def test_database_constraints_reject_invalid_stock_and_movements(self) -> None:
        migrate(self.db_path)
        with closing(connect(self.db_path)) as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE products SET stock = -1 WHERE sku = 'R2-FR-001'")
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute(
                    """INSERT INTO inventory_movements
                           (product_id, delta_qty, movement_type, reason)
                       VALUES (1, 0, 'ADJUSTMENT', 'invalid zero')"""
                )
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute(
                    """INSERT INTO inventory_movements
                           (product_id, delta_qty, movement_type, reason)
                       VALUES (999, 1, 'ADJUSTMENT', 'missing product')"""
                )
        self.assertTrue(verify(self.db_path)["passed"])

    def test_rejects_non_lab_database_name(self) -> None:
        with self.assertRaisesRegex(ValueError, "lab_"):
            init_database(self.db_path.with_name("production.db"))


if __name__ == "__main__":
    unittest.main()
