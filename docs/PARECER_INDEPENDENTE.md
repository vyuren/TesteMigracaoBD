# Parecer independente — Exercício 2

**Projeto:** Rota 2 Motopeças — evolução incremental do banco SQLite  
**Universidade:** UNINASSAU - Olinda  
**Professor:** Fernando Garcia Marcal  
**Aluno:** Carlos Vinicius Alves de Araújo — matrícula 01906085  
**Estado:** pendente de preenchimento por revisor independente

## Itens a verificar

- [x] Modelagem atual e proposta estão coerentes com o banco laboratorial.
- [x] Migração 001 é aditiva e idempotente.
- [x] T0 não representa reconstrução histórica.
- [x] UPDATE do saldo e INSERT do movimento são atômicos.
- [x] Replay idempotente não gera segundo débito.
- [x] Falha intermediária retorna o estado anterior.
- [x] Backup, SHA-256 e restauração foram validados.
- [x] Limites sobre API/CLI originais estão explicitamente registrados.
- [x] Não há segredos, dados pessoais ou bancos reais publicados.

## Achados observados

| # | Severidade | Evidência / referência | Achado | Impacto |
|---|---|---|---|---|
| 1 | MÉDIA | [src/TRACEABILITY.md](/home/vyuren/works/TesteMigracaoBD/src/TRACEABILITY.md:20-21), [src/DATABASE_DESIGN.md](/home/vyuren/works/TesteMigracaoBD/src/DATABASE_DESIGN.md:127-132) | A API FastAPI original e a CLI administrativa original não estão no workspace. Apenas o adaptador e a CLI didáticos foram implementados em [src/api.py](/home/vyuren/works/TesteMigracaoBD/src/api.py:24-43). | Impede comprovar G-DB5 completo, regressões da aplicação real e a integração efetiva dos componentes originais com o ledger. |
| 2 | MÉDIA | [src/DATABASE_DESIGN.md](/home/vyuren/works/TesteMigracaoBD/src/DATABASE_DESIGN.md:82-112) | Os gatilhos para reavaliar SQLite/PostgreSQL estão definidos, mas não há volume, latência, concorrência, `SQLITE_BUSY`, RPO ou RTO medidos no ambiente real. | A decisão PostgreSQL continua não fundamentada por carga efetiva e deve ser mantida como não verificada. |
| 3 | BAIXA | [src/test_lab_db_extension.py](/home/vyuren/works/TesteMigracaoBD/src/test_lab_db_extension.py:195) | O teste integrado G-DB5 depende de FastAPI instalado e pode ser ignorado sem as dependências opcionais. | A prova G-DB5 precisa registrar explicitamente o ambiente e o conjunto de dependências utilizado. |
| 4 | POSITIVO | [src/lab_db_extension.py](/home/vyuren/works/TesteMigracaoBD/src/lab_db_extension.py:42-50) | UPDATE e INSERT são executados em transação `BEGIN IMMEDIATE`, com rollback em exceção. | A atomicidade está implementada nos fluxos laboratoriais. |
| 5 | POSITIVO | [src/test_lab_db_extension.py](/home/vyuren/works/TesteMigracaoBD/src/test_lab_db_extension.py:42-214) | Os testes cobrem migração, T0, RED/GREEN, rollback, replay, concorrência, restrições, backup e restauração. | Evidência local consistente da integridade e dos fluxos didáticos. |
| 6 | POSITIVO | [src/TRACEABILITY.md](/home/vyuren/works/TesteMigracaoBD/src/TRACEABILITY.md:3-31) | Os itens não comprovados estão classificados honestamente como não verificados ou parciais. | Evita atribuir PASS indevido à integração real, carga ou governança externa. |

**Conclusão preliminar:** não foi identificado bug crítico ou vulnerabilidade crítica nos fluxos laboratoriais examinados. Os achados pendentes são de completude da evidência externa, não de falha demonstrada do código laboratorial.

## Decisão

- [ ] Aprovar
- [x] Aprovar com ressalvas
- [ ] Rejeitar

**Revisor:** __________________________________  
**Data:** ____/____/______  
**Assinatura ou identificação eletrônica:** ________________________________
