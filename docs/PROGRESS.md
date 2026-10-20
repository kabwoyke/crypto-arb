# Progress

Tick an item only when its evidence (test name / report) exists.

- [ ] **P0** Decisions & scaffolding — `make up/test/lint` green; CI green; OQ-1,2,3,5,6 reviewed
  - [x] `make up` (postgres + redis healthy), `make test` (8 passed), `make lint` (ruff + mypy clean) verified locally
  - [x] Repo layout, ADR-0001, pre-commit, CI workflow written; architecture tests in `tests/unit/test_architecture.py`
  - [ ] CI green on GitHub — blocked, see OQ-12
  - [ ] Client review of OQ-1, 2, 3, 5, 6 — blocked, see OQ-11
- [ ] **P1** Foundations — ledger invariants; §25 example; secrets never logged; migrations up/down
- [ ] **P2** Exchange layer — contract tests (simulator + testnets); market data for hundreds of pairs; readiness reasons; fault injection
- [ ] **P3** Math core — all spec examples as tests; property tests; mypy strict
- [ ] **P4** Scanner/rotation — $100k vs $45k example; 90% cap under concurrency; 24h paper run + report → **go/no-go**
- [ ] **P5** Execution — no duplicates under timeout-after-success; deadlines; kill switch; shadow == live decisions
- [ ] **P6** Recovery/reconciliation — §17–§27 scenarios; crash-point convergence; loan = 0 verified
- [ ] **P7** Inventory/transfers — no equalization; mode lock; address allowlist; pause drains to loan = 0
- [ ] **P8** User app — onboarding E2E; dashboard == ledger; ROI feed rules
- [ ] **P9** Hardening — chaos, soak, security review, runbooks, restore drill
- [ ] **P10** Canary/rollout — staged caps, clean reconciliation streak
- [ ] **P11** Triangular (optional)
