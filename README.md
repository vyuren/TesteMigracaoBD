# Laboratório REA — evolução do banco de dados

Este projeto é um laboratório didático para o **Exercício 2** do PDF em
[`docs/Proposta_de_evolucao_REA_Exercicios_1_e_2 (1).pdf`](docs/Proposta_de_evolucao_REA_Exercicios_1_e_2%20(1).pdf).
Ele demonstra como evoluir, de forma incremental, um banco SQLite de uma loja
didática: adiciona uma versão de migração e um ledger (histórico) de movimentos
de estoque, registra um saldo inicial T0 e verifica se o saldo atual corresponde
à soma dos movimentos.

> **Este repositório não é a loja completa.** Não há interface web nem API
> FastAPI original nem CLI administrativa original. Foi adicionado um adaptador
> FastAPI didático que usa as mesmas operações de ajuste e venda do laboratório;
> a integração com os componentes reais da loja permanece **NÃO VERIFICADA**.

## O que a aplicação faz

- Cria um banco SQLite demonstrativo com produtos, compatibilidade, pedidos e
  itens de pedido.
- Aplica a migração aditiva `001_inventory_ledger`, preservando as tabelas-base
  e registrando os saldos existentes como `OPENING` (T0). Isso **não**
  reconstitui vendas anteriores à migração.
- Ajusta o estoque e registra o movimento correspondente dentro da mesma
  transação.
- Registra vendas, impede saldo negativo e trata a chave de idempotência para
  que repetir o mesmo pedido não debite o estoque novamente.
- Confere integridade do SQLite, chaves estrangeiras e conciliação do ledger.
- Faz backup consistente com SHA-256 e restaura para um arquivo novo.
- Só opera em arquivos chamados `lab_*.db`, `lab_*.sqlite` ou `lab_*.sqlite3`.
  Não sobrescreve banco, backup ou restauração existentes e não ativa WAL.

O código usa somente a biblioteca padrão do Python e o SQLite incluído nele;
não é necessário instalar dependências adicionais.

## Requisitos

- Python 3.10 ou superior.
- SQLite fornecido pelo módulo `sqlite3` do Python.
- Terminal aberto na pasta raiz do projeto.

Confira as versões instaladas:

```sh
python3 --version
python3 -c "import sqlite3; print(sqlite3.sqlite_version)"
```

No Windows, use `python` no lugar de `python3`, se esse for o comando
configurado no sistema.

## Como fazer funcionar

Os comandos abaixo criam o arquivo do banco na pasta `data/`; o próprio
laboratório cria essa pasta quando necessário. Se usar um banco já existente,
confira se ele é descartável e mantenha o nome `lab_*.db`.

### Linux ou macOS

```sh
# 1. Criar uma base didática nova
python3 -m src.lab_db_extension init --db data/lab_rota2.db

# 2. Criar e conferir o backup antes da migração
python3 -m src.lab_db_extension backup --db data/lab_rota2.db

# 3. Aplicar a migração aditiva 001 e conferir o resultado
python3 -m src.lab_db_extension migrate --db data/lab_rota2.db
python3 -m src.lab_db_extension verify --db data/lab_rota2.db
```

### Windows PowerShell

```powershell
# 1. Criar uma base didática nova
python -m src.lab_db_extension init --db data/lab_rota2.db

# 2. Criar e conferir o backup antes da migração
python -m src.lab_db_extension backup --db data/lab_rota2.db

# 3. Aplicar a migração aditiva 001 e conferir o resultado
python -m src.lab_db_extension migrate --db data/lab_rota2.db
python -m src.lab_db_extension verify --db data/lab_rota2.db
```

Uma verificação bem-sucedida informa `integrity_check: "ok"`, nenhuma violação
de chave estrangeira, nenhuma divergência no estoque e `"passed": true`.

### Exercitar ajustes e vendas

Após a migração, os seguintes exemplos podem ser executados em qualquer um dos
terminais acima, substituindo `python3` por `python` no Windows:

```sh
# Ajustar o saldo para 15 e registrar o motivo
python3 -m src.lab_db_extension adjust --db data/lab_rota2.db \
  --sku R2-FR-001 --quantity 15 --reason "inventario aula"

# Vender duas unidades, com uma chave idempotente
python3 -m src.lab_db_extension sell --db data/lab_rota2.db \
  --idempotency-key pedido-aula-001 --item R2-FR-001=2

# Repetir o mesmo comando de venda: retorna o pedido original sem novo débito
python3 -m src.lab_db_extension sell --db data/lab_rota2.db \
  --idempotency-key pedido-aula-001 --item R2-FR-001=2

# Confirmar integridade e conciliação depois das operações
python3 -m src.lab_db_extension verify --db data/lab_rota2.db
```

Para registrar vários produtos em um pedido, repita `--item`:

```sh
python3 -m src.lab_db_extension sell --db data/lab_rota2.db \
  --idempotency-key pedido-aula-002 \
  --item R2-FR-001=1 --item R2-COR-002=1
```

Uma chave idempotente já usada com itens diferentes é recusada. Ajustes exigem
motivo com pelo menos cinco caracteres, e vendas com estoque insuficiente
falham sem deixar alterações parciais.

### Restaurar o backup

O comando `restore` confere o manifesto SHA-256 e cria
`data/lab_rota2_restored.db`, sem substituir a base original. O nome reservado
deve ainda não existir. Se o backup foi feito antes da migração, aplique-a também
na base restaurada antes de executar `verify`:

```sh
python3 -m src.lab_db_extension restore --db data/lab_rota2.db
python3 -m src.lab_db_extension migrate --db data/lab_rota2_restored.db
python3 -m src.lab_db_extension verify --db data/lab_rota2_restored.db
```

Para PowerShell, troque `python3` por `python`.

## Testes

Execute na raiz do projeto:

```sh
python3 -m unittest src.test_lab_db_extension -v
```

No Windows, use `python -m unittest src.test_lab_db_extension -v`. Os testes
cobrem migração idempotente, T0, detecção de alteração de estoque sem movimento,
rollback, restrições, pedidos idempotentes, concorrência, backup/restauração e
SHA-256. Eles usam bancos temporários e não precisam dos comandos de inicialização
acima.

## Estrutura

```text
src/
  lab_db_extension.py                CLI e operações do laboratório
  migrations/001_inventory_ledger.sql Migração aditiva 001
  test_lab_db_extension.py           Testes automatizados
  DATABASE_DESIGN.md                Modelo, dicionário e decisão arquitetural
  TRACEABILITY.md                   Requisitos, testes e gates
  README.md                         Instruções detalhadas do laboratório
docs/
  Proposta_de_evolucao_REA_Exercicios_1_e_2 (1).pdf
  schema_proposto_001.sql
  rea_doc_esquema_atual.pdf
  relatorio_exercicio2.pdf
  Apresentacao_Exercicio_2_Banco_Dados.pptx
  PARECER_INDEPENDENTE.md
  APROVACAO_HUMANA.md
```

## Limites e segurança

O comando `init` só cria uma base nova e recusa um arquivo já existente.
`migrate` exige as tabelas-base e colunas esperadas; não adapta automaticamente
um esquema desconhecido. Para um banco de laboratório preexistente, confira o
esquema e faça backup antes de migrar. Nunca use dados pessoais, credenciais ou
uma base operacional. O laboratório não habilita WAL automaticamente.

Os testes comprovam os fluxos locais da API adaptadora e da CLI de laboratório.
A integração com a API FastAPI e a CLI administrativa originais, execução em CI,
PR e aprovação humana não fazem parte deste workspace e permanecem **NÃO
VERIFICADAS**. Consulte [`src/DATABASE_DESIGN.md`](src/DATABASE_DESIGN.md) e
[`src/TRACEABILITY.md`](src/TRACEABILITY.md) para detalhes do modelo, critérios e
limitações.
