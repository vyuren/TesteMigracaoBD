# Matriz de requisitos e evidências do laboratório

Os testes listados são executáveis com `python3 -m unittest
src.test_lab_db_extension -v`. PASS nesta matriz significa que o teste local
correspondente passou; não é evidência de API externa, CI ou aprovação humana.

| Requisito | Tabela/fluxo | Teste ou comando | Gate |
|---|---|---|---|
| Extensão aditiva, preservação das tabelas e migração repetível | `schema_migrations`, `inventory_movements` | `test_migration_is_additive_idempotent_and_records_t0`; `migrate` | G-DB1 |
| Saldo de abertura observado em T0, sem reconstrução histórica | `inventory_movements` (`OPENING`) | mesmo teste; `verify` | G-DB1 |
| Reconciliação encontra divergência RED deliberada | `products.stock`, ledger | `test_red_unlogged_stock_change_is_detected` | G-DB1, G-DB3 |
| Ajuste atualiza estoque e ledger atomicamente | `products`, `inventory_movements` (`ADJUSTMENT`) | `test_adjustment_updates_stock_and_ledger_together` | G-DB3, G-DB5 (CLI laboratório) |
| Falha intermediária reverte todas as alterações | transação de ajuste | `test_ledger_failure_rolls_stock_update_back` | G-DB3 |
| Replay da chave não duplica débito; payload conflitante falha | `orders`, `order_items`, `inventory_movements` (`SALE`) | `test_order_replay_debits_once_and_conflicting_replay_fails` | G-DB3, G-DB4 |
| Estoque insuficiente não cria pedido ou movimento parcial | `products`, `orders`, ledger | `test_order_insufficient_stock_rolls_back_everything` | G-DB3 |
| Escritas concorrentes com replay não geram segundo pedido | transação `BEGIN IMMEDIATE` | `test_concurrent_replay_creates_one_order_and_one_debit` | G-DB3 |
| Integridade SQLite, FKs, CHECK e não-negatividade | esquema SQLite | `test_database_constraints_reject_invalid_stock_and_movements`; `verify` | G-DB2 |
| Backup consistente, SHA-256 e restauração validada | arquivo SQLite | `test_backup_restore_hash_and_integrity`; `test_baseline_backup_can_be_restored_before_migration`; `backup`, `restore` | G-DB2, G-DB4 |
| API do laboratório registra movimentos de estoque | adaptador FastAPI em `src/api.py` | `test_g_db5_api_and_cli_register_inventory_movements` | G-DB5 parcial |
| API FastAPI original registra movimentos | API original não fornecida | **NÃO VERIFICADO** | G-DB5 |
| CLI original/admin registra movimentos | CLI original não fornecida | **NÃO VERIFICADO**; o CLI de laboratório (`adjust`/`sell`) é testado | G-DB5 parcial |
| PostgreSQL é necessário para a carga real | não medido neste workspace | **NÃO VERIFICADO**; critérios de avaliação estão em [DATABASE_DESIGN.md](./DATABASE_DESIGN.md) | decisão futura |
| CI, branch/PR, auditoria independente e aprovação humana | fora do workspace | **NÃO VERIFICADO** | entrega/governança |

## Resultado honesto de execução

Os testes automatizados locais cobrem migração, T0, conciliação, rollback,
restrições, idempotência, concorrência, backup/restauração e o G-DB5 para o
adaptador FastAPI e a CLI do laboratório. Eles não demonstram uma alteração
histórica do projeto original, integração com a API/CLI administrativa real,
pipeline CI, PR ou aprovação humana.
