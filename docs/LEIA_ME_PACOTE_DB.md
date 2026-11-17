# Rota 2 Motopeças — extensão didática do banco de dados (Opção A)

Este pacote é PROPOSTA de implementação, não uma alteração já aplicada no GitHub.

- `REA_GOVERNANCA_REV04_Complemento_Banco_Dados_OpA.pptx`: a apresentação REV04 integral, com 10 novos slides anexados (86 a 95). As 85 lâminas anteriores foram mantidas.
- `Guia_Didatico_REA_REV04_Complemento_Banco_Dados_OpA.docx`: o guia REV04 integral com Anexo A para o laboratório.
- `Arquitetura_Dados_REA_OpA.png`: esquema para aula.
- `schema_proposto_001.sql`: DDL conceitual para revisão, NÃO executar diretamente em produção.
- `lab_db_extension.py`: CLI isolada que aceita SOMENTE bancos `lab_*.db`; copiar para `scripts/` no clone do GitHub.

Não há prova de execução do vídeo indicado nem de uso de Antigravity em sessão real.
O conteúdo do vídeo não pôde ser extraído por fonte pública verificável. A base é o código
existente da Rota 2 e recomendações oficiais de SQLite, PostgreSQL, OWASP e NIST.

## Teste isolado após copiar script para `scripts/` do clone

```powershell
.\.venv\Scripts\python.exe scripts/lab_db_extension.py init --db data/lab_rota2.db
.\.venv\Scripts\python.exe scripts/lab_db_extension.py backup --db data/lab_rota2.db
.\.venv\Scripts\python.exe scripts/lab_db_extension.py restore --db data/lab_rota2.db
.\.venv\Scripts\python.exe scripts/lab_db_extension.py migrate --db data/lab_rota2.db
.\.venv\Scripts\python.exe scripts/lab_db_extension.py verify --db data/lab_rota2.db
```

O ledger após a migração exige integração transacional em `app/main.py` e `app/manage.py`
antes de novos pedidos/ajustes no mesmo banco. Até então, não considerar a API integrada.
Não sugerir PASS para uma execução não realizada.
