# MasterMobile Engineering Principles

## Code Quality
- Target Python **3.12+** with FastAPI as the core web framework.
- Enforce **strict typing**; `mypy` must pass with `--strict` settings.
- Run `ruff` with autofix disabled in CI and commit hooks; violations block merges.
- Maintain **≥95% unit-test coverage** on core modules; surface coverage dashboards in PRs.
- Keep pre-commit hooks mandatory for linting, typing, formatting, and security scans.

## Testing Strategy
- Follow the **testing pyramid**: unit ≫ integration ≫ end-to-end.
- Use `pytest` with `httpx.AsyncClient` for API layers; isolate FastAPI dependencies via fixtures.
- Provide stubs/mocks for Telegram Bot API and Bitrix24 integrations to keep tests deterministic.
- Maintain golden-file tests for conversational prompts and message templates.
- Require regression suites to run in CI before every release tag.

## Security & Compliance
- Store configuration in `.env`; never commit secrets to the repo.
- Manage runtime secrets through GitHub Actions OIDC + repository secrets.
- Align with **OWASP ASVS Level 1**; log and track remediation tasks for gaps.
- Emit immutable **audit logs** for administrative actions and data exports.
- Minimize collection of PII; document retention windows and anonymization rules.

## UX Consistency
- Prioritize **Telegram-first flows**; ensure equivalent capabilities in Bitrix admin panels.
- Default user-facing copy to **Russian locale**, with fallbacks documented.
- Keep error messages concise, actionable, and consistent with the error catalog.
- Sync UX updates with docs/one-pagers before code merges.

## Performance & Scalability
- Guarantee **P95 API latency < 250 ms** under nominal load; document load baselines.
- Prefer streaming responses for long-running operations (transcriptions, exports).
- Use async I/O and connection pooling for all network and database calls.
- Implement caching layers (Redis) with explicit TTLs and cache-invalidation strategy.
- Support idempotency keys for all write paths; enforce conflict detection on mismatched payloads.

## Observability
- Produce structured JSON logs with request context and correlation IDs.
- Propagate `X-Request-ID` across services and into external integrations.
- Expose `/healthz` for readiness/liveness and `/metrics` for Prometheus scraping.
- Collect domain-specific events (e.g., sync batches, transcript jobs) for dashboards and alerts.

## Documentation as Code
- Operate **spec-first**: update PRD, one-pagers, and ADRs before implementation.
- Keep ADRs current; mark superseded decisions with status updates.
- Use docs-driven acceptance criteria; link PRs to the authoritative documents in `docs/`.
- Automate doc linting and link checks in CI.

## CI/CD Expectations
- GitHub Actions pipeline must run `ruff`, `mypy`, and `pytest` on every push and PR.
- Build Docker images on CI, tagging semantic versions on merges to `main`.
- Block releases on failing quality gates or coverage regressions.
- Publish changelog entries and version metadata alongside releases.
