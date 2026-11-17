# Laboratório REA — evolução incremental do banco SQLite

Este laboratório implementa a proposta do Exercício 2 em SQLite, sem alterar
banco operacional. O `init` cria um banco demonstrativo `lab_*.db` com as
tabelas-base (`products`, `compatibility`, `orders` e `order_items`); `migrate`
aplica a migração aditiva 001 e grava o saldo existente como abertura T0. O T0
não representa reconstrução do histórico anterior.

Todas as operações da CLI exigem nome de banco `lab_*.db`, `lab_*.sqlite` ou
`lab_*.sqlite3`. O laboratório não habilita WAL, não sobrescreve banco, backup
ou restauração existentes e não contém credenciais nem dados reais. Faça o
backup antes de migrar bancos de laboratório preexistentes.

## Executar

Na raiz do repositório, com Python 3.10+:

```sh
python3 -m src.lab_db_extension init --db data/lab_rota2.db
python3 -m src.lab_db_extension backup --db data/lab_rota2.db
python3 -m src.lab_db_extension migrate --db data/lab_rota2.db
python3 -m src.lab_db_extension verify --db data/lab_rota2.db
python3 -m src.lab_db_extension adjust --db data/lab_rota2.db \
  --sku R2-FR-001 --quantity 15 --reason "inventario aula"
python3 -m src.lab_db_extension sell --db data/lab_rota2.db \
  --idempotency-key pedido-aula-001 --item R2-FR-001=2
python3 -m src.lab_db_extension verify --db data/lab_rota2.db
python3 -m src.lab_db_extension restore --db data/lab_rota2.db
```

`adjust` e `sell` gravam a alteração do saldo e seu movimento na mesma
transação `BEGIN IMMEDIATE`. A repetição da chave idempotente com os mesmos
itens retorna o pedido original; a mesma chave com itens diferentes é recusada.
`verify` exige a migração aplicada e falha se `integrity_check`, chaves
estrangeiras ou conciliação de saldo apresentarem divergência. `restore` valida
o SHA-256 do backup antes de restaurar para um novo arquivo e então executa as
verificações de integridade.

## Testes e limites

Execute os testes sem dependências externas:

```sh
python3 -m unittest src.test_lab_db_extension -v
```

Os testes incluem um caso RED (alteração direta de `stock`, detectada pela
conciliação), casos GREEN, falha intermediária com rollback, repetição
idempotente, estoque insuficiente, concorrência de replay, backup/restauração e
SHA-256.

Este repositório não contém a aplicação FastAPI nem sua CLI administrativa
originais. Foi adicionado um adaptador FastAPI de laboratório; os testes cobrem
API adaptadora e CLI de laboratório. A integração da ledger com os componentes
originais permanece **NÃO VERIFICADA**. Antes de usar um esquema-base diferente, confira se ele
possui as colunas consultadas pelo laboratório; `migrate` interrompe com erro
explícito se o contrato mínimo não for atendido.
