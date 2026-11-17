## Rota 2 Motopeças — extensão didática do banco de dados (Opção A) · REV05

Este pacote é uma PROPOSTA de implementação. Não é alteração já aplicada na main do GitHub.

### Arquivos
- `REA_GOVERNANCA_REV05_Complemento_Banco_Dados_OpA.pptx`: apresentação integral com complemento de banco.
- `Guia_Didatico_REA_REV05_Complemento_Banco_Dados_OpA.docx`: guia integral com Anexo A revisado.
- `Arquitetura_Dados_REA_OpA_REV05.png`: arquitetura revisada, com banco `lab_*.db`, fronteira transacional, ledger e governança.
- `schema_proposto_001_REV05.sql`: DDL conceitual; não executar isoladamente em produção.
- `lab_db_extension_REV05.py`: CLI isolada que aceita somente bancos `lab_*.db`; copiar para `scripts/lab_db_extension.py` no clone.
- `REA_REV05_Nota_Tecnica_Evolucao_Banco_Dados_OpA.docx`: nota técnica do complemento de persistência.
- `CHECKSUMS_SHA256_REV05.txt`: manifesto do pacote.

### Sequência recomendada
Execute com o interpretador da `.venv`, na raiz do repositório:

```powershell
.\.venv\Scripts\python.exe scripts\lab_db_extension.py init --db data\lab_rota2.db
.\.venv\Scripts\python.exe scripts\lab_db_extension.py backup --db data\lab_rota2.db
.\.venv\Scripts\python.exe scripts\lab_db_extension.py migrate --db data\lab_rota2.db
.\.venv\Scripts\python.exe scripts\lab_db_extension.py verify --db data\lab_rota2.db
.\.venv\Scripts\python.exe scripts\lab_db_extension.py backup --db data\lab_rota2_pos_migracao.db
```

Para o ensaio completo, mantenha dois ciclos: backup/restore do baseline e backup/restore pós-migração. A migração é aditiva e recuperável por restauração de backup; não há `down migration` lógica neste pacote.

### Limites
O ledger exige integração transacional em `app/main.py` e `app/manage.py` antes de novos pedidos/ajustes no mesmo banco. O PASS do script comprova somente integridade e conciliação do laboratório, não execução do Antigravity, integração da API/CLI ou atividade das Formas B/C.

### Mapeamento de gates
| Gate de dados | Gate principal |
|---|---|
| G-DB1 Esquema | G2 / G3 |
| G-DB2 Integridade | G4 |
| G-DB3 TDD, rollback e idempotência | G4 / G6 |
| G-DB4 Segurança e recuperação | G5 |
| G-DB5 Governança | G6 / G7 |
