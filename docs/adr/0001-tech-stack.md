# ADR-0001: Tech stack

Status: Accepted (default from CLAUDE.md; client confirmation tracked as OQ-10)

## Decision

- Python 3.12, asyncio, httpx, websockets, pydantic v2, `decimal.Decimal` for all money.
- PostgreSQL 16 (SQLAlchemy 2 + Alembic) for ledger, trades, accounts, config; Redis for
  market-data cache, shared liquidity budget, rotation queue, locks.
- FastAPI for the app API; Next.js + TypeScript + Tailwind for `web/`.
- Tooling: uv, pytest, pytest-asyncio, hypothesis, ruff, `mypy --strict` on `core/`, `engine/`,
  `ledger/`. Docker Compose for local dev; GitHub Actions for CI.
- Launch exchanges: Binance and Bitget behind a registry; no exchange name outside `exchanges/`.

## Consequences

- SQLAlchemy/Alembic/psycopg and FastAPI dependencies are added in the phase that first needs
  them (Phase 1 and Phase 8), not in the skeleton.
- Changing any item requires a new ADR.
