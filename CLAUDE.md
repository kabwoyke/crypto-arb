# CLAUDE.md — Oddtrue Arbitrage Engine

Read this file fully at the start of every session. Then read the **current phase** in `docs/IMPLEMENTATION_PLAN.md`.
The client specification is `docs/SPEC.md` (sections are cited as §N). It is the source of truth; if code and spec disagree, the spec wins — or raise it in `docs/OPEN_QUESTIONS.md`.

## What we are building

Oddtrue is a multi-client, cross-exchange crypto arbitrage platform. It is **an execution + recovery + liquidity + inventory management engine, not an arbitrage calculator** (§42).

Primary strategy (§4): on Exchange A **buy** a coin with USDT; on Exchange B **borrow** the same coin (margin) and **sell** it for USDT. Both directions are evaluated (A→B and B→A). Triangular routes are a *separate* opportunity class (§34).

It handles real client money. **Correctness and safety beat speed and features.** Every decision below follows from that.

## Working method (phased delivery)

1. Work on **one phase at a time**, in order. Do not start phase N+1 until phase N's *Exit Criteria* are met and checked off in `docs/PROGRESS.md`.
2. At the start of a phase: restate the scope, list the spec sections covered, and make a task list. At the end: run the full test suite, tick the exit criteria, update `docs/PROGRESS.md`, and commit.
3. Anything ambiguous in the spec → add it to `docs/OPEN_QUESTIONS.md` with your proposed default, use the default behind a config flag, and keep going. Do not silently invent business rules.
4. Small commits, one concern each. Conventional commit style (`feat(engine): …`, `test(math): …`).
5. No phase is "done" without tests. Math and state-machine code require property-based tests (hypothesis).

## Non-negotiable invariants

These come straight from the spec. Each must have a dedicated test that fails if the rule is broken.

**Money & math**
- Never use `float` for money, price or quantity. Use `decimal.Decimal` (via `oddtrue.core.money`). Lint rule bans `float` in `engine/`, `ledger/`, `exchanges/`.
- Order-book walking and VWAP use **every level consumed**, never only top-of-book (§5).
- Executable liquidity = only what fits inside the configured max slippage (§5).
- Rounding: quantities round **down** to the exchange step, never up; verify the rounded order still satisfies the 95% and 90% limits (§9).

**The four controls (never conflate them — §42)**
- `95%` — per-client execution capacity: `Trade Capacity = U × 0.95` (§2, §7).
- `5%` — per-client reserve, **never auto-spent**; only for interest acquisition during recovery, small-account needs, permitted recovery costs, headroom (§2, §21).
- `90%` — cap on total market liquidity consumed **across all clients combined** for one opportunity (§6). Enforced with a shared atomic liquidity budget, not per-client.
- `Rotation` — fair allocation when client demand > 90% capacity. A client not executing is **not** failed (§8).
- Final allocation = `MIN(95% client cap, 90% market cap, available capital, borrowable qty, exchange limits)`, then lot-size / min-notional validated (§7).

**Master constraint (§41)** — a single pure function `validate_trade_constraints()` must check all of: allocation ≤ 95% of U; market execution ≤ 90% of executable liquidity; borrow ≤ actual available-to-borrow; qty within [min, max]; qty conforms to step; notional ≥ min notional; expected net ROI ≥ configured minimum. Nothing reaches an exchange without passing it.

**Execution safety**
- Pre-check B sell liquidity **before borrowing**; insufficient → **DO NOT BORROW** (§10).
- Pre-check borrow capacity; insufficient → do not execute (§11).
- Re-query everything and recompute immediately before execution; below threshold → **cancel before execution** (§12).
- A BUY and B BORROW→SELL are submitted as concurrently as possible; borrow is followed immediately by a protected sell, never "borrow, wait, decide" (§14).
- Protected sell = aggressive IOC/FOK limit with a computed worst acceptable price (§15).
- Every operation has a max execution/recovery time; on timeout → stop normal flow → reconcile → recover. Never wait indefinitely (§37).

**Uncertainty & idempotency (§35, §36, §38)**
- An API error/timeout does **not** mean the action failed. Query order status / balance / loan, reconcile, *then* decide.
- Every order, borrow and repay uses a deterministic client-order-id derived from `(trade_id, leg, attempt)` and is recorded **before** the request is sent. No duplicate buys, sells, borrows or repayments, ever.
- Partial fills: use actual filled quantity, recompute remaining qty/liquidity/profit/loan/hedge. Never assume the intended quantity filled.

**Recovery (§17–§27)**
- Failed B sell ⇒ immediately: stop retrying that order; read actual B coin balance, loan, accrued interest, and A's coin; sell A's coin for USDT with a protected order; buy **only the interest amount** of coin on B from the client's 5% reserve; repay principal + interest; verify the exchange reports loan = 0.
- **Never mark recovery complete unless the API reports outstanding liability = 0** (§22).
- Do not retry the original arbitrage after a B-sell failure unless a fresh independent profitability calculation passes (§26).
- No A→B transfer just to pay interest (§23).

**Inventory & transfers (§28–§31, §47–§54)**
- Rebalancing restores *operational inventory*; it is **not** 50/50 equalization and **not** "send back what was sent". `Required = Target − Current`; skip if transfer fee/min makes it not worth it or a future trade would rebalance naturally.
- Settlement/recovery transfer and rebalancing transfer are **separate operations**, computed independently.
- Automatic transfer ≠ unlimited withdrawal authority: whitelisted destination addresses only, approved asset/network allowlist, per-transfer and per-day caps, amount computed by the engine, never user- or API-supplied.
- Transfer mode (auto/manual) can change **only when the account is idle** — locked during ACTIVE, RECOVERY, PENDING_TRANSFER, RECONCILING (§54).
- Pause: stop new opportunities, let active work complete or recover, reach loan = 0 and no pending orders/transfers, then PAUSED (§55). Resume requires fresh balance/API/margin/borrow/inventory/transfer checks (§56).

**Ledger & ROI (§32, §33, §58)**
- Internal ledger is **append-only, double-entry, actuals only**. Client balances are updated from realized exchange figures, never estimates. Losses and recovery costs are always recorded.
- Realized ROI = Net Realized Profit ÷ Capital Used × 100, computed only after a trade completes with all costs deducted.
- The published ROI feed shows **only positive realized ROI from successfully completed trades**; never estimated ROI; never failed/cancelled/recovery operations. This is a *view* over the full ledger — it must never be implemented by deleting or not recording losses. (See Open Question OQ-9 before shipping this feed.)
- After every trade: exchange state → API reconciliation → internal ledger → inventory. Any mismatch triggers reconciliation and blocks further trading for that client until resolved (§39).

## Safety rules for you (the coding agent)

- **Never** put real API keys in code, tests, fixtures, logs or commits. Tests use the in-repo exchange simulator or exchange testnets only.
- Default `ENGINE_MODE=paper`. Modes: `paper` (no orders), `shadow` (compute + log what it would do), `live`. Live requires an explicit env var **and** a per-client allow-flag. Do not change defaults.
- Never log secrets, API keys, signatures or full account identifiers. Credentials are encrypted at rest (envelope encryption; KMS in prod, local key in dev) and decrypted only in the execution process.
- Do not add withdrawal capability in any adapter until Phase 7, and then only behind the address allowlist + caps above.
- A global **kill switch** (halt new trades, keep recovery running) must exist from Phase 5 onward and be tested.
- Don't "fix" a failing safety test by loosening it. Ask or log it in OPEN_QUESTIONS.

## Tech stack (default — change only via an ADR in `docs/adr/`)

- Python 3.12, `asyncio`, `httpx`, `websockets`, `pydantic` v2, `decimal`.
- PostgreSQL 16 (SQLAlchemy 2 + Alembic) — ledger, trades, accounts, configs. Redis — market-data cache, liquidity budget, rotation queue, locks.
- FastAPI (REST + WebSocket) for the app API. Next.js + TypeScript + Tailwind for the dashboard (`web/`).
- `pytest`, `pytest-asyncio`, `hypothesis`, `ruff`, `mypy --strict` (on `core/`, `engine/`, `ledger/`).
- Docker Compose for local dev. GitHub Actions CI: lint, type-check, tests, migration check.
- **Exchanges:** launch with **Binance** and **Bitget**, but the engine is exchange-agnostic. "A" and "B" are *roles per trade*, not fixed exchanges: any registered exchange can be the buy side or the borrow-and-sell side, and both directions are evaluated (§4). So every adapter must support spot trading **and** margin borrow/repay.
- Adding an exchange = one new package under `exchanges/<name>/` implementing `ExchangeAdapter` + a `capabilities` declaration + passing the shared contract-test suite. **No exchange name may appear outside `exchanges/`** (no `if exchange == "binance"` in engine, math, inventory or ledger). Exchange quirks (symbol format, margin mode, IOC/FOK support, borrow-repay flow, interest accrual, withdrawal networks, rate limits) live in the adapter and surface through `capabilities` and normalized models.
- Client connections are per exchange pair: `(client, exchange_x, exchange_y)` from a registry, not hardcoded "A"/"B" columns.
- Do not rely on remembered API details for Binance or Bitget; read the current official API docs when implementing each endpoint and record doc links in the adapter's README.

## Repository layout

```
oddtrue/
  CLAUDE.md
  docs/            SPEC.md, IMPLEMENTATION_PLAN.md, PROGRESS.md, OPEN_QUESTIONS.md, adr/
  src/oddtrue/
    core/          money.py (Decimal helpers), config.py, clock.py, errors.py, ids.py
    exchanges/     base.py (ExchangeAdapter protocol + Capabilities), models.py, registry.py, binance/, bitget/, simulator/, contract_tests/
    marketdata/    orderbook cache, instrument rules, fee/borrow-rate feeds
    math/          pure functions only: orderbook walk, vwap, liquidity, allocation, lotsize, profit, triangular
    engine/        scanner, rotation, prechecks, revalidation, executor, recovery, state machines
    inventory/     targets, rebalance planner, transfer service (auto/manual)
    ledger/        double-entry ledger, reconciliation, ROI/reporting views
    accounts/      onboarding, credential vault, readiness checks, account state machine
    api/           FastAPI routers (auth, exchanges, account, dashboard, transfers)
    workers/       long-running processes (scanner, executor, reconciler, transfer monitor)
  web/             Next.js dashboard
  tests/           unit/, property/, integration/, failure_injection/
  scripts/  infra/  migrations/
```

Rules: `math/` has **no I/O and no imports from `engine/`, `exchanges/` or `ledger/`**. `engine/` never calls an exchange SDK directly — only `ExchangeAdapter`. All side effects go through the executor, which writes intent to the DB first.

## State machines (implement explicitly; illegal transitions raise)

- **Account:** `PENDING_SETUP → ACTION_REQUIRED ⇄ READY → ACTIVE → (RECOVERY | PENDING_TRANSFER | RECONCILING) → READY`, plus `PAUSED`. (§46, §54–§56)
- **Trade:** `DETECTED → ALLOCATED → PRECHECKED → REVALIDATED → EXECUTING → {SETTLING → COMPLETED | RECOVERING → RECOVERED | CANCELLED}`; any unexpected state → `NEEDS_MANUAL_REVIEW` (halts that client).
- **Transfer (§59):** `NO_TRANSFER_REQUIRED, TRANSFER_REQUIRED, AWAITING_USER_TRANSFER, TRANSFER_INITIATED, TRANSFER_CONFIRMING, TRANSFER_RECEIVED, RECONCILING, REBALANCED, READY`.

## Conventions

- Type everything; `mypy --strict` clean in core packages. No bare `except`. No `time.sleep` in async code.
- Time via `core.clock` (injectable) so timeouts and accrual are testable. Store UTC.
- Config via typed settings (env + DB per-client overrides). Every threshold in the spec (95, 5, 90, max slippage, min net ROI, max exec time, rotation policy) is **config, not a literal** — defaults 95/5/90.
- Structured JSON logs with `trade_id`, `client_id`, `leg`, `exchange`. Metrics for latency, rejects-by-reason, recovery count, reconciliation mismatches.
- Every rejection reason is an enum recorded with the opportunity (so "why didn't we trade?" is answerable).
- Tests: names describe the rule (`test_does_not_borrow_when_b_sell_liquidity_insufficient`). Every spec worked example (§2, §6, §9, §20–21, §25) becomes a unit test with the spec's exact numbers.

## Commands (fill in as Phase 1 lands)

```
make up            # docker compose: postgres, redis
make test          # pytest (unit + property)
make test-int      # integration against simulator
make lint          # ruff + mypy
make migrate       # alembic upgrade head
make sim           # run exchange simulator with scenario file
```

## Definition of done (every phase)

Tests green · lint/type clean · migrations apply and roll back · docs updated · spec sections listed in PR · no new open safety question left unrecorded · `docs/PROGRESS.md` updated.
