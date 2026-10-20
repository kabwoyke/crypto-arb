# Open Questions (client / product decisions)

Status: OPEN unless stated. Each has a default the build will use behind a config flag until answered.

| ID | Question | Default used | Needed by |
|---|---|---|---|
| OQ-1 | **RESOLVED:** Binance + Bitget, extensible. Open: default margin mode and borrowable-coin universe per exchange; testnet availability for margin on each | Cross margin; universe computed per direction | Phase 2 |
| OQ-2 | On a successful trade, how is B's borrowed coin repaid — A→B withdrawal of the purchased coin (settlement transfer), or buy-back on B? Max acceptable loan-open time? | A→B settlement transfer; interest and fees modelled in net ROI | Phase 3 |
| OQ-3 | Where is the 5% reserve held (A, B, both)? In what asset? | USDT on B | Phase 2 |
| OQ-4 | Rotation ordering rule when demand > 90% capacity | Least-recently-served first, then size packing | Phase 4 |
| OQ-5 | Values: min net ROI, max slippage, max execution/recovery time, scan interval | Conservative placeholders in config | Phase 3 |
| OQ-6 | Custody/legal model; are withdrawal-permission API keys acceptable; licensing per jurisdiction | Automatic transfer only to whitelisted addresses with caps | Phase 7 |
| OQ-7 | Minimum client size; how U is measured across A and B | Min-viable-trade eligibility check | Phase 2 |
| OQ-8 | Cross vs isolated margin on B; borrowable-coin universe | Cross margin; universe = A-spot ∩ B-borrowable | Phase 2 |
| OQ-9 | Legal review of publishing only positive realized ROI (§58) while omitting losses | Filtered view; full statement per client | Before Phase 8 ships |
| OQ-10 | Confirm tech stack, hosting, KYC provider | Python/Postgres/Redis/Next.js, containers (ADR-0001) | Phase 0 |
| OQ-11 | Phase 0 exit needs client review of OQ-1, 2, 3, 5, 6. No reviewer sign-off exists yet | Phase 0 left unticked in PROGRESS.md until the client confirms or accepts the defaults | Phase 0 exit |
| OQ-12 | CI green cannot be verified: the repo has no git remote, so the GitHub Actions workflow has never run (only the same `make lint` / `make test` commands run locally) | Push to a remote and confirm the workflow passes | Phase 0 exit |
| OQ-13 | CLAUDE.md says "ruff bans `float` in `engine/`, `ledger/`, `exchanges/`", but ruff has no such rule | Enforced by AST test `test_no_float_in_money_critical_packages` instead | Phase 0 |
| OQ-14 | Dev host ports 5432/6379 were already in use on the dev machine | Compose defaults moved to 5433 (Postgres) and 6380 (Redis), configurable in `.env` | Phase 0 |
