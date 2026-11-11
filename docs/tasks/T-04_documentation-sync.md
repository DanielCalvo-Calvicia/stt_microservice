# T-04 — Documentation sync

| | |
|---|---|
| Status | recurring |
| Kind | docs |
| Depends on | — |
| Blocks | — |

## Goal

A pass, repeated after every big task, that makes the documents describe the code and the evidence. It is the safety net of the rule in `CLAUDE.md` (every change updates its documents in the same change).

## When

After T-01, after T-02 and after T-03 (and whenever a task note says a document moved).

## Checklist

1. Counts: the test total, the contracts wheel version (F1: 0.15.0 pushed, 0.16.0 in the working tree), the Python versions tested: in `CLAUDE.md`, `README.md`, the header of `docs/architecture/architecture.md`.
2. The debt table (section 8 of the architecture document) and the requirements table: status, evidence and task for every row this plan touched (debts 1, 2, 3 and 7; FR-8; NFR-9, NFR-10, NFR-11).
3. The stt documents against the deployment ones: `docs/deployment/deployment.md` and `docs/configuration/environment-variables.md` against `deployment/docs/DEPLOYMENT.md` and the `[services.stt]` entry of `deployment/config/catalogue.toml` (`prepare`, volumes, `HF_HOME`, readiness).
4. The audit: [../deployment_audit/stt.md](../deployment_audit/stt.md) keeps its text as an audit; add a dated note where a finding changed.
5. The ADRs: ADR-008 and ADR-009 exist once their decisions are taken, and are in the list of section 6 of the architecture document and in the README's documentation table.
6. The tasks: the board in [README.md](README.md), [ORDER.md](ORDER.md) and every task file show the same state; links resolve; paths named in tasks still exist.
7. `brain_microservice\windows\Scripts\python.exe deployment\scripts\env_inventory.py --check` from the workspace root if an `.env.example` changed.
8. The `docs/tasks/` folder is listed in the README's documentation table.

## Log

| Pass | Date | Notes |
|---|---|---|
| 1 | 2026-11-06 | Plan written; nothing executed yet. |
| 2 | 2026-11-11 | Done after the restructure of that day. Counts: 152 tests, contracts wheel 0.16.0 committed in `8ee7c7d` (not pushed; the venv still has 0.15.0), HEAD `8ee7c7d` in `CLAUDE.md`, `README.md`, the architecture header, the requirements header and the API header. Debt 9 resolved; ADR-004, ADR-005 and ADR-009 (status lines, ADR-009 dated update) brought up to date; the paths of the code that moved (ports, DTOs, dependencies, the inbound HTTP folder, the constants of the configuration document). Not done: the audit and these task files keep their paths of the time (records); the `deployment` repository's documents were not read in this pass (item 3 of the checklist). |
