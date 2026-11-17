# Modelo de dados e decisão arquitetural

## Escopo e evidência

`src/lab_db_extension.py` constrói o banco-base demonstrativo descrito abaixo.
Como o repositório não contém a aplicação original nem um arquivo SQLite
preexistente, este modelo documenta o laboratório implementado, não uma
inspeção do banco ou da API de produção. A migração rejeita esquemas
incompatíveis e só deve ser usada em bancos de laboratório com nome `lab_*`.

## DER-base do laboratório

```text
products 1 ───────< compatibility
    │
    ├─────────────< order_items >──────────── orders
    │
    └─────────────< inventory_movements >─── orders (opcional)

schema_migrations (controle de versões; sem relação de negócio)
```

## DER proposto

A evolução é aditiva. Preserva as quatro tabelas operacionais e acrescenta
`schema_migrations` e `inventory_movements`. `OPENING` registra o saldo T0
observado na migração; `SALE`, `ADJUSTMENT` e `RETURN` registram eventos
posteriores. Não se infere nem se reconstitui histórico de vendas anterior ao T0.

```text
products 1 ───────< compatibility
    │
    ├─────────────< order_items >──────────── orders
    │                                      │
    └─────────────< inventory_movements >──┘

schema_migrations (versão e instante de aplicação)
```

## Dicionário de dados

| Tabela | Campo | Tipo/regra | Significado |
|---|---|---|---|
| `products` | `id` | INTEGER PK | Identificador do produto. |
| `products` | `sku` | TEXT UNIQUE NOT NULL | Código do produto. |
| `products` | `name` | TEXT NOT NULL | Nome demonstrativo. |
| `products` | `category` | TEXT NOT NULL | Categoria do catálogo. |
| `products` | `stock` | INTEGER NOT NULL, CHECK >= 0 | Saldo atual, conciliado ao ledger. |
| `compatibility` | `id` | INTEGER PK | Identificador da compatibilidade. |
| `compatibility` | `bike_id` | TEXT NOT NULL | Identificador demonstrativo da motocicleta. |
| `compatibility` | `product_id` | INTEGER FK | Produto compatível; par bicicleta/produto único. |
| `orders` | `id` | TEXT PK | UUID do pedido. |
| `orders` | `idempotency_key` | TEXT UNIQUE NOT NULL | Chave para replay sem segundo débito. |
| `orders` | `created_at` | TEXT NOT NULL | Instante de criação em UTC do SQLite. |
| `order_items` | `id` | INTEGER PK | Identificador do item. |
| `order_items` | `order_id` | TEXT FK | Pedido proprietário do item. |
| `order_items` | `product_id` | INTEGER FK | Produto vendido. |
| `order_items` | `quantity` | INTEGER CHECK > 0 | Quantidade do item. |
| `schema_migrations` | `version` | TEXT PK | Identificador da migração aplicada. |
| `schema_migrations` | `applied_at` | TEXT NOT NULL | Instante de aplicação. |
| `inventory_movements` | `id` | INTEGER PK | Identificador sequencial do movimento. |
| `inventory_movements` | `product_id` | INTEGER FK, ON DELETE RESTRICT | Produto movimentado. |
| `inventory_movements` | `delta_qty` | INTEGER CHECK <> 0 | Variação assinada do saldo. |
| `inventory_movements` | `movement_type` | TEXT CHECK | `OPENING`, `SALE`, `ADJUSTMENT` ou `RETURN`. |
| `inventory_movements` | `order_id` | TEXT FK, opcional | Pedido de origem; obrigatório para `SALE`. |
| `inventory_movements` | `reason` | TEXT CHECK tamanho mínimo 5 | Contexto auditável do evento. |
| `inventory_movements` | `created_at` | TEXT NOT NULL | Instante do registro. |

### Invariantes

1. Para cada produto, `products.stock = SUM(inventory_movements.delta_qty)`.
2. `stock` nunca pode ser negativo; um débito de venda exige saldo suficiente.
3. Atualização do saldo e inserção do movimento pertencem à mesma transação.
4. Um replay da mesma chave idempotente e mesmos itens não cria novo pedido nem
   novo débito; reutilização da chave com itens diferentes falha.
5. A primeira migração registra no máximo uma abertura por produto com saldo
   diferente de zero. Produto com saldo zero tem saldo conciliado zero sem linha
   de abertura.
6. As FKs são verificadas em conexão e em `verify`; a restrição CHECK protege
   os limites locais mesmo quando uma operação ignora a camada de domínio.

## ADR-001 — manter SQLite no laboratório

**Status:** adotado para o exercício isolado; não é aprovação para produção.

**Contexto:** o material de referência recomenda preservar SQLite e evoluir o
esquema incrementalmente. O workspace recebido não inclui o backend original,
portanto não há medição real de carga, latência ou concorrência que justifique
uma migração de SGBD.

**Decisão:** usar o módulo `sqlite3` da biblioteca padrão, transações
`BEGIN IMMEDIATE`, FKs habilitadas por conexão, migração SQL aditiva e backup
pela API de backup do SQLite. Não habilitar WAL automaticamente. SQL de dados é
parametrizado e o CLI só aceita arquivos com nome de laboratório.

**Consequências:** simples execução local e fácil restauração; há um escritor
por vez e não se presume alta disponibilidade distribuída. A decisão não
impede futura migração a PostgreSQL.

**Gatilhos propostos para reavaliar PostgreSQL (ainda não medidos):**

- teste representativo de sete dias mostra `SQLITE_BUSY` em mais de 1% das
  escritas ou p95 de transação de escrita acima de 200 ms;
- requisito de múltiplas instâncias em hosts distintos com escrita concorrente;
- RPO inferior a 15 minutos ou RTO inferior a 60 minutos que não possa ser
  atendido e demonstrado pelos backups do ambiente;
- necessidade de controles operacionais, replicação ou disponibilidade que o
  desenho local não atende.

Antes de decidir, registrar duração, volume, concorrência, p50/p95/p99, erros de
bloqueio, tamanho da base, RPO/RTO e resultado de teste de restauração. Os
valores acima são limites sugeridos para o experimento, não resultados medidos.

## Migração, backup e recuperação

1. Criar uma cópia consistente do arquivo usando o backup API do SQLite.
2. Registrar SHA-256 do arquivo e metadados de horário/versão SQLite.
3. Aplicar `001_inventory_ledger.sql` em transação `BEGIN IMMEDIATE`, sem
   executar comandos DDL parcialmente em caso de falha.
4. Registrar T0 e versão 001 na mesma transação. Repetir a migração não duplica
   estruturas nem saldos de abertura.
5. Em falha, a transação reverte. O rollback de recuperação é restaurar o
   backup verificado para um arquivo novo; não há migração `down` destrutiva.
6. Validar o SHA-256 do backup, `integrity_check`, `foreign_key_check` e ledger
   após a restauração. O CLI nunca sobrescreve o arquivo restaurado existente.

## Segurança e limitações

O laboratório usa apenas dados demonstrativos, não inclui pagamentos, segredos
ou dados pessoais, parametriza valores e não habilita WAL. Os testes são locais
e não atestam segurança operacional, implantação ou integração com serviço
externo. Integração de uma API FastAPI e da CLI original é **NÃO VERIFICADA**,
pois esses componentes não foram fornecidos neste workspace.
