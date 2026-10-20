# Oddtrue — Implementation Plan

Source spec: `docs/SPEC.md` (§1–§62). Rules for the coding agent: `CLAUDE.md`.

## 1. Strategy in one paragraph

Build the **pure math first**, then the exchange layer against a **simulator**, then the execution and recovery state machines, then inventory/transfers, then the user-facing app, and only then touch real money — through paper → shadow → tiny-capital canary. Every phase ends in something runnable and tested. Money-moving code (execution, recovery, transfers) is built *after* the simulator can reproduce every failure the spec describes, so failure paths are tested before they can cost anything.

```
P0 Decisions ─ P1 Foundations ─ P2 Exchange layer ─ P3 Math core ─ P4 Scanner+Rotation ─ P5 Execution
                                                                                              │
         P9 Hardening ─ P8 User app (can start after P2) ─ P7 Inventory+Transfers ─ P6 Recovery+Reconciliation
                │
          P10 Canary → rollout        P11 Triangular (optional, after stable live)
```

P8 (web app) is independent of P3–P7 once P2 and the ledger exist and can run in parallel if a second developer is available.

## 2. Spec gaps and risks to resolve (feeds `docs/OPEN_QUESTIONS.md`)

Raise these with the client **before or during Phase 0**. Each has a proposed default so work is not blocked.

| # | Issue | Why it matters | Proposed default |
|---|---|---|---|
| OQ-1 | ~~Which exchanges?~~ **Resolved: Binance + Bitget at launch, extensible to others.** Remaining: which is the default borrow side per pair; margin mode (cross/isolated); which coins are borrowable on each | Both must act as A or B since both directions are evaluated; borrow/repay flow, IOC/FOK, rate limits, withdrawal networks and fees differ per exchange | Adapter per exchange behind a `Capabilities` declaration and registry; direction chosen per pair by net profit |
| OQ-2 | **How is the borrowed coin repaid on a *successful* trade (§16)?** A bought coin on A, B sold borrowed coin for USDT. To repay B's loan, the coin must reach B (A→B withdrawal = "Transfer 1 — settlement", §30) or B must buy it back (which cancels the arbitrage profit). | Loan stays open and accruing interest during the transfer; exposure to withdrawal delays/fees; this is the main economic and operational risk of the strategy. | Settlement transfer A→B, with interest and fee included in net-ROI model and a max-open-loan-time limit |
| OQ-3 | Where does each client's 5% reserve live? §21 uses "B's reserved 5%", but §2 defines it as % of total capacity. | Reserve must be sitting as USDT (or collateral) on B to be usable. | Reserve held as USDT on B; U measured as A-USDT + B-collateral eligible for trading |
| OQ-4 | Rotation policy (§8) — "only clients that fit participate" but no ordering rule. | Fairness and disputes. | Least-recently-served first, then pack by size to maximize filled capacity; log every decision |
| OQ-5 | Min net ROI, max slippage, max execution/recovery time, scan interval, fee tier source | Required by §12, §13, §37 but no values given. | Config with conservative defaults; client to confirm |
| OQ-6 | Custody & legal model — pooled/managed client funds, API keys with trade+borrow(+withdraw) permission, licensing in operating jurisdictions | Automatic transfers need withdrawal permission; this is the largest security exposure. | Withdrawal only to client-whitelisted addresses on the exchange; caps; legal review before live |
| OQ-7 | Capital model: is U per client on A and B, or a single number? What's the minimum client size? (§2 uses $500; min notionals/fees may make small accounts unprofitable) | Affects eligibility and allocation. | Eligibility check includes min-viable-trade size per pair |
| OQ-8 | Cross vs isolated margin on each exchange; which coins are borrowable on Binance and on Bitget; borrow-rate accrual (hourly?) and interest-in-coin | "Hundreds of pairs" is really the intersection of A-spot ∩ B-borrowable | Universe = pairs tradable on one exchange and borrowable on the other, per direction, refreshed periodically |
| OQ-9 | **"Only positive realized ROI is published; losses are not."** (§58) | A public feed showing only wins can be misleading to current/prospective clients and may breach advertising/financial-promotion rules depending on jurisdiction. | Implement as a *filtered view*; each client's own statement shows everything; legal sign-off before launch |
| OQ-10 | Tech stack / hosting / team | Plan assumes Python + Postgres + Redis + Next.js on containers | Confirm or override via ADR |

## 3. Phases

Effort numbers assume one experienced developer working with Claude Code; treat as relative, not a quote.

---

### Phase 0 — Decisions & scaffolding (≈ 2–3 days)

**Scope:** resolve/record OQs, set up repo and tooling.
- Create repo layout from `CLAUDE.md`; `docs/` populated; ADR-0001 (stack).
- `pyproject`, ruff, mypy, pytest, hypothesis, pre-commit, Docker Compose (Postgres, Redis), CI.
- `docs/PROGRESS.md` with every phase's exit criteria as checkboxes.

**Exit criteria:** `make up && make test && make lint` pass on an empty skeleton; CI green; OPEN_QUESTIONS.md reviewed by client for OQ-1, 2, 3, 5, 6.

---

### Phase 1 — Foundations: money, config, ledger, vault (≈ 1–1.5 weeks)

**Spec:** §2, §32, §33, §44 (credential storage), §39.
- `core.money`: Decimal wrappers, quantize-down, bps/percent helpers, no float.
- Typed config (95/5/90, slippage, min ROI, timeouts) with per-client override.
- DB schema + migrations: `clients`, `exchange_connections` (encrypted), `accounts`, `opportunities`, `trades`, `orders`, `loans`, `transfers`, `ledger_entries`, `balance_snapshots`, `audit_log`, `config`.
- **Double-entry append-only ledger** with the §32 field set per trade; actual-vs-expected columns; recovery/transfer/rebalance cost categories; views for realized P/L and ROI (§33, §58).
- Credential vault: envelope encryption, key rotation hook, redaction in logs.
- Deterministic id generation (`trade_id`, `client_order_id`).

**Exit criteria:** ledger invariants tested (entries always balance; no update/delete possible; trade P/L reproduces §25 example: $500 → $498.50 ⇒ $1.50 loss + costs); secrets never appear in logs (test); migrations up/down.

---

### Phase 2 — Exchange layer, simulator, market data, onboarding (≈ 2–3 weeks)

**Spec:** §1, §3, §44–§46, §58 (balances), §59.
- `ExchangeAdapter` protocol (symbol normalization to a canonical `BASE/QUOTE`, decimals only): balances, collateral, margin health, liabilities, max-borrowable, order book (REST+WS), instrument rules (min/max qty, step, min notional, tick), fees, borrow rates, place/cancel/query order (IOC/FOK, client-order-id), borrow, repay, loan/interest query, deposit/withdraw status (withdraw stubbed until P7).
- **Exchange registry + `Capabilities`** (supports margin borrow, IOC, FOK, post-only, borrow-and-sell atomicity, WS order books, withdrawal networks, interest-accrual unit, rate-limit weights). The engine reads capabilities to decide which order types/flows are allowed per exchange.
- Concrete adapters for **Binance** and **Bitget** (read current official API docs while building; link them in each adapter README), with rate-limit manager, clock-skew handling, retries that **never** blindly retry non-idempotent calls.
- **Exchange simulator** (critical): in-memory order books, margin/borrow engine, interest accrual, fees, plus scriptable fault injection — timeouts-after-success, rejects, partial fills, borrow denied, liquidity vanishing, stale books, loan not zeroing, delayed deposits.
- Market-data service: full books for the configured universe (A-spot ∩ B-borrowable), instrument rules/fees/borrow rates cached with TTLs, staleness detection (stale data ⇒ no trade).
- Account onboarding service: permission checks, **readiness** → `READY` / `ACTION_REQUIRED` with exact per-item reasons (§46); eligibility pool (§1).

**Exit criteria:** adapters pass a shared contract-test suite against the simulator and, where the exchange offers one, a testnet (margin borrowing may not be testable on testnets — verify per exchange; if not, the simulator plus a tiny-notional live check in Phase 10 cover it); **a third dummy exchange added in under a day with zero engine changes** (proves extensibility); market data handles hundreds of pairs within rate limits; readiness check returns specific actionable failures; fault injection works.

---

### Phase 3 — Math core (pure functions) (≈ 1.5–2 weeks)

**Spec:** §5, §6, §7, §9, §11 (qty calc), §13, §34 (calc), §41.
- `walk_book(book, target_qty|target_notional, max_slippage)` → levels consumed, VWAP, executable liquidity.
- `executable_liquidity`, `market_cap = 0.90 × liquidity`.
- `client_allocation = MIN(0.95·U, market share, capital, borrowable, exchange max)`.
- `round_to_lot()` (round down to step, enforce min/max qty, min notional, tick) and **re-validate caps after rounding** (§9 example 0.123456 → 0.12345 BTC).
- Profitability: buy cost, sell proceeds, gross, fees (per-leg fee rate), interest estimate (`borrowed × rate × duration`, including **settlement-transfer duration** from OQ-2), slippage, net profit, net ROI.
- Max acceptable sell price for protected orders (§15).
- `validate_trade_constraints()` implementing the §41 master constraint with a typed rejection reason.
- Triangular route *calculation* (§34) for comparison only — no execution yet.
- Recovery math helpers: total liability `P + I`, interest-BTC → USDT required from reserve (§20–§21), failed-trade loss (§25).

**Exit criteria:** every worked example in the spec is a unit test with exact numbers (§2, §6, §9, §20, §21, §25); hypothesis properties: allocation never exceeds any cap; rounding never rounds up; VWAP between best and worst consumed price; net profit decreases monotonically with each added cost; `mypy --strict` clean.

---

### Phase 4 — Opportunity scanner, allocation, rotation (≈ 1.5–2 weeks)

**Spec:** §4, §6–§8, §10–§11 (as filters), §40 (first half of loop).
- Scanner: both directions for each pair, ranks by executable net profit; each rejection has a reason enum.
- **Shared 90% liquidity budget** across all clients per opportunity (Redis atomic reservation with expiry).
- Allocation per eligible client; **rotation queue** per OQ-4: persistent state, fairness metrics, "not executed ≠ failed" (§8).
- Pre-checks as read-only evaluators: B sell liquidity (§10), borrow capacity (§11).
- **Paper mode runner**: scanner + allocation + rotation running against live market data with no orders; writes opportunities and hypothetical trades.

**Exit criteria:** spec example ($100k demand vs $45k capacity) reproduced; no client starves in a long simulated run; the 90% cap holds under concurrent allocators (test with many clients); paper mode runs for 24 h without crashes and with a report of opportunity frequency and expected net ROI.

> **Go/no-go gate with the client:** the paper-mode report shows how often net-positive opportunities actually exist after fees, interest and settlement cost. Review before investing in Phases 5–7.

---

### Phase 5 — Execution engine (≈ 2–3 weeks)

**Spec:** §12, §14, §15, §16, §35–§38.
- Trade state machine with persisted intent-before-send and idempotent client-order-ids.
- **Final revalidation** (§12): re-query books, balances, borrowable, fees, rates, margin; recompute everything; cancel if below threshold.
- Concurrent executor: `asyncio.gather` of A-buy and B-(borrow → immediate protected IOC/FOK sell), with per-operation deadlines (§37).
- Uncertain-outcome handler: on any API error/timeout → query order/balance/loan → reconcile → decide (§35, §38). Partial-fill handler (§36).
- Success path through recording actual fills/fees/interest and handing off to settlement (repay loan + interest; transfer if required per OQ-2) — repayment/settlement completed in P6/P7, stubbed with the simulator until then.
- Kill switch, per-client and global; per-client circuit breaker after N failures; max concurrent trades per client.
- Mode gating: `paper`/`shadow`/`live`.

**Exit criteria (all run on the simulator with fault injection):** no duplicate order/borrow under timeout-after-success; B sell failure leaves the trade in `RECOVERING` (not stuck); partial fills handled; deadlines trigger reconcile+recover; kill switch halts new trades but not recovery; shadow mode logs decisions identical to what live would have sent.

---

### Phase 6 — Recovery & reconciliation (≈ 2 weeks)

**Spec:** §16–§27, §35, §37, §39.
- **Failed-B-sell recovery**: stop retrying → read B coin, loan, interest, A coin → protected sell of A coin to USDT → compute interest-coin needed → check reserve (§41: interest ≤ 5% reserve, where permitted by B margin rules) → buy only the interest coin on B (with fee/step adjustment) → repay `P + I` → verify exchange liability = 0 (§22). Retries with backoff; escalates to `NEEDS_MANUAL_REVIEW` + alert if it can't reach zero.
- Handles variants: partial B sell fill, borrow succeeded but A buy failed (unwind/repay), A-unwind slippage, reserve insufficient, loan not zero after repay.
- **Successful trade settlement**: repay + verify zero; record actual P/L (§16, §33).
- **Reconciliation service**: exchange state vs internal ledger after every trade and on a timer; mismatch ⇒ lock client from new trades until resolved (§39); reports for A and B balances/loans/interest (§27).
- Recovery cost accounting into the ledger (§25).

**Exit criteria:** §17–§27 scenario suite passes on simulator including the spec numbers ($500 → $498.50; 0.003 BTC + 0.00002 interest); recovery is idempotent if the process crashes at any step and restarts (crash-point test at every state transition); recovery never reports complete while the simulator liability ≠ 0.

---

### Phase 7 — Inventory, rebalancing, transfers (≈ 2–3 weeks)

**Spec:** §28–§31, §47–§54, §57, §59.
- Target operational inventory model (per client, per exchange, per coin/USDT) driven by expected demand; `Required = Target − Current`; fee/min-transfer/benefit gate; "will a future trade rebalance naturally?" check (§29, §31).
- Two independent planners: **settlement transfer** and **rebalancing transfer** (§30).
- Transfer service with full status machine (§59), monitoring, deposit confirmation, reconciliation after receipt.
- **Automatic mode** with safety rails (§53): address allowlist, asset/network allowlist, min withdrawal, fee check, expected-received check, balance check, deposit-availability check, per-transfer and daily caps, "would this impair future trading?" check, human-approval threshold for large amounts.
- **Manual mode**: instruction object (asset, amount, from, to, network, est. fee, reason, deadline), awaiting-user state, automatic deposit detection, confirmation + reconcile (§51–§52).
- Mode-change lock (§54), pause/resume semantics wired to account state (§55–§56). Default: Automatic ON (§61).

**Exit criteria:** no blind equalization (test); transfer-mode change rejected in ACTIVE/RECOVERY/PENDING_TRANSFER/RECONCILING; automatic transfer rejected to non-whitelisted address/network; delayed/missing deposits handled; pause drains to loan = 0 and PAUSED.

---

### Phase 8 — User app & API (≈ 3–4 weeks; parallelizable from Phase 2)

**Spec:** §43–§46, §49, §54–§62.
- Auth (email + password + 2FA), required verification flow hook (KYC provider TBD).
- Exchange Connections: A and B credential entry, encrypted storage, connectivity/permission/margin/borrow tests, readiness screen with exact fixes (§44–§46); guidance to create keys **without withdrawal permission unless automatic transfer is chosen**, IP-whitelisted.
- Transfer Mode screen (auto default, risk explanation per §61), manual-transfer instruction cards and status chips (§51, §59).
- Dashboard (§58): A and B balances, borrowed/interest/borrowable, 95%/5% split, allocated amount, rotation status, active opportunity, current P/L, transfer status/mode, realized ROI, ROI history, total realized profit.
- **ROI feed rule (§58):** realized, successful, positive only, green; never estimates; losses excluded from the *feed* but present in the client's full statement and ledger export. Gated behind legal confirmation (OQ-9).
- Pause / Resume controls; notifications (email/push) for action required, awaiting transfer, recovery events.
- Admin console: client list/status, kill switch, rotation view, recovery/needs-review queue, reconciliation mismatches.

**Exit criteria:** end-to-end onboarding on testnet; dashboard numbers equal ledger numbers (test); ROI feed contains no estimates/losses/recoveries (test); mode lock and pause behave per §54–§56 through the UI.

---

### Phase 9 — Hardening & security (≈ 2–3 weeks)

- Chaos/failure-injection suite across all phases; soak test (≥ 72 h simulator + ≥ 7 days paper/shadow on live data).
- Security: threat model, secrets in KMS, least-privilege DB roles, rate-limit and abuse protection, dependency audit, external pen-test of auth and credential vault.
- Observability: dashboards and alerts for reconciliation mismatch, loan open > threshold, recovery failures, stale data, withdrawal events, kill-switch state; runbooks for each alert.
- Disaster recovery: backups, restore drill, process-crash resumption verified in staging.
- Load: hundreds of pairs × N clients within API rate limits.

**Exit criteria:** zero unresolved P1/P2 findings; runbooks exist; restore drill passed; client sign-off on shadow-mode results.

---

### Phase 10 — Canary & rollout (≈ 2–4 weeks, calendar-bound)

1. Internal funds, 1 account, tiny notional (~minimum viable), automatic transfer OFF, human watching every trade; reconcile to the cent.
2. Add automatic transfers with tight caps.
3. 5–10 friendly clients, low caps; weekly review of expected vs actual ROI, recovery frequency, realized slippage.
4. Raise caps/clients in stages, each stage gated on clean reconciliation and recovery stats.

**Exit criteria:** N consecutive days with zero reconciliation breaks and zero loans left open; realized vs expected ROI within agreed tolerance.

---

### Phase 11 — Triangular / multi-route class (optional, ≈ 2–3 weeks)

**Spec:** §34. Execution of multi-leg routes as a separate opportunity class with its own state machine, per-leg partial-fill/unwind logic, and the comparison rule: choose by **executable net profit, liquidity, leg count, fees and execution risk**, not gross percentage. Built only after the primary strategy is stable live.

---

## 4. Test strategy (summary)

| Layer | Tooling | Focus |
|---|---|---|
| Unit / spec-example | pytest | Every spec numeric example with exact numbers |
| Property | hypothesis | Caps never exceeded; rounding down; monotonic costs; ledger balances |
| Contract | pytest | Same suite against simulator and testnets for each adapter |
| State-machine & crash-point | pytest + simulator | Kill the process at every transition; restart must converge |
| Failure injection | simulator | Timeout-after-success, partial fills, vanished liquidity, loan ≠ 0, late deposits |
| Concurrency | pytest-asyncio | Shared 90% budget, rotation, duplicate-order prevention |
| E2E | Playwright | Onboarding, transfer-mode lock, pause/resume, dashboard vs ledger |

## 5. Timeline (one developer + Claude Code, indicative)

Phases 0–4 ≈ 7–9 weeks → **go/no-go gate** → Phases 5–7 ≈ 6–8 weeks → Phase 8 in parallel (3–4 weeks) → Phase 9 ≈ 2–3 weeks → Phase 10 ≈ 2–4 weeks. Roughly **5–6 months to a controlled live launch**; two developers can bring it to ~4 months by parallelizing P8 and P2/P3.

## 6. How to drive this with Claude Code

For each phase, start a fresh session in the repo and say:

> Read CLAUDE.md and docs/IMPLEMENTATION_PLAN.md. We are starting **Phase N**. Restate the scope and the spec sections, create a task list, build it with tests, and stop when the exit criteria are met. Record any ambiguity in docs/OPEN_QUESTIONS.md instead of guessing.

Review each phase's diff and exit-criteria evidence before moving on; Phases 5–7 deserve line-by-line human review.
