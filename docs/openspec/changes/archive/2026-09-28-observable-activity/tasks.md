## Implementation
- [x] Add behavior tests and additive journal migration with chain verification.
- [x] Integrate stable lifecycle identities, history checkpoints and read-only API.
- [x] Implement durable OTLP export and an optional Collector configuration.
- [x] Build and inspect the live animated dashboard.
- [x] Document commands, actual guarantees and limitations.
- [x] Pass repository checks, strict specifications and container CI; archive change.

## Verification
- `make check`: 33 passed, 5 container checks skipped locally; Ruff and Compose valid.
- `make spec-check`: strict requirements validation passed.
- GitHub Actions run 36404766007: all 5 container integration checks passed on Linux,
  including Postgres mutation rejection and real Collector delivery.
- Chrome: a real fixture worker animated, workflow reached human review, loss of
  connectivity stopped live animation, reconnection restored the feed, credentials
  were absent from local/session storage, and no JavaScript errors occurred.
- Desktop 1536px and mobile 390px layouts inspected with no page-level overflow.
- Original local history retained; 87 events verified against an exported checkpoint
  after restarting the gateway. The checkpoint is local, not an independent anchor.
