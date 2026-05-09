# OLRE Runtime Profile Hardening Handoff

Date: `2026-05-09`

Branch: `hardening/runtime-profiles-backup-and-storage`

Tag: `v0.9.5-runtime-profile-hardening`

---

## Executive Summary

The runtime profile hardening phase was initiated because OLRE's runtime behavior had become environment-sensitive in unsafe ways, but that sensitivity was not being modeled explicitly in the application architecture.

The visible failures were operationally serious:

- local macOS runtime could fail when `.env` was missing because fallback paths pointed to `/app/data/...`
- local `uvicorn` behavior depended too heavily on an explicit `.env`
- pytest behavior changed depending on whether the developer's real `.env` existed in the workspace
- `tests/integration/test_runtime_readiness.py` was accidentally influenced by machine-specific local state
- runtime defaults and test expectations no longer represented a stable, architecture-level contract

This was not merely a small configuration mistake. It was a runtime architecture problem because the application had multiple valid execution contexts:

- local development
- Docker container runtime
- isolated test runtime
- future production deployment

Those contexts have different expectations for:

- filesystem roots
- writable directories
- default SQLite location
- startup port conventions
- whether runtime configuration should come from `.env` or from injected environment variables

Before this phase, OLRE implicitly treated Docker assumptions as universal fallback behavior. That meant Docker worked well, but local development and test isolation were unstable whenever explicit environment configuration was absent or incomplete. This phase formalized runtime profiles so OLRE can now resolve defaults predictably based on execution intent rather than accident.

---

## Previous Runtime Problems

### 1. Docker-centric fallback paths

The settings layer defaulted key runtime paths to container-style locations:

- `/app/data/input`
- `/app/data/processed`
- `/app/data/error`
- `/app/data/debug/qr`
- `/app/data/runtime/tmp`
- `/app/data/runtime/failed-retained`

The default database URL also pointed to:

```text
sqlite:////app/data/olre.sqlite3
```

This was safe inside Docker, but wrong as a universal fallback for local workstation runtime.

### 2. Implicit runtime assumptions

The system had no formal runtime profile model. Instead, it assumed:

- Docker-like filesystem layout
- Docker-like persistence root
- one default SQLite location for all environments
- one default port expectation that drifted across docs, tests, Compose, and local workflows

This meant the effective runtime model depended on incidental environmental conditions instead of an explicit architecture rule.

### 3. Local `uvicorn` startup failures

When `.env` was absent or incomplete on macOS, local startup could fall back to `/app/data/...` paths. On a local workstation, that is the wrong storage root and can lead to startup validation failures or permission errors during writable path checks.

This made OLRE appear healthy only when the developer had already hand-crafted a working `.env`, which is the opposite of predictable runtime behavior.

### 4. pytest contamination from `.env`

The settings layer used `.env` automatically via `pydantic-settings`. As a result:

- tests that intended to verify defaults were not really verifying code defaults
- the presence of a developer's real `.env` changed test behavior
- local machine state leaked into test outcomes

This is especially dangerous for readiness and configuration tests because they are supposed to validate architectural guarantees.

### 5. Non-isolated runtime readiness tests

`tests/integration/test_runtime_readiness.py::test_default_settings_match_docker_sqlite_runtime` originally depended on the runtime settings loader in a way that could still read `.env`.

That meant the test was not deterministic. It could pass or fail based on:

- the current workspace
- whether `.env` existed
- what values the developer had in `.env`

### 6. Inconsistent `DATABASE_URL` and path resolution behavior

There was also an architectural mismatch between runtime modes:

- some flows assumed local relative SQLite under `data/...`
- some flows assumed Docker absolute SQLite under `/app/data/...`
- tests and docs encoded conflicting assumptions about default port and storage roots

The result was a runtime contract that was operationally useful only when the operator already knew which assumptions were hidden inside the codebase.

---

## Runtime Profiles Introduced

This phase introduced and formalized four runtime profiles through `APP_ENV` and `ENVIRONMENT`.

### Supported Profiles

| Profile | Intended Environment | Default Database | Default Storage Root | Expected Deployment Style |
|---|---|---|---|---|
| `development` | local workstation development | `sqlite:///data/olre.sqlite3` | `data/...` under repo | local `venv` / local `uvicorn` |
| `docker` | container runtime | `sqlite:////app/data/olre.sqlite3` | `/app/data/...` | single-container SQLite-first Docker runtime |
| `testing` | pytest / isolated test runtime | `sqlite:///data/olre.sqlite3` | `data/...` under repo unless overridden by test env | test fixture-driven runtime |
| `production` | future production-style runtime | `sqlite:////app/data/olre.sqlite3` | `/app/data/...` | operational deployment with explicit env control |

### Profile Intent

#### `development`

Use for:

- local macOS/Linux development
- local `venv`
- direct `uvicorn` startup
- local Alembic migration flow

Defaults:

- `APP_PORT=7777`
- `DATABASE_URL=sqlite:///data/olre.sqlite3`
- `INPUT_DIR=data/input`
- `PROCESSED_DIR=data/processed`
- `ERROR_DIR=data/error`
- `QR_DEBUG_DIR=data/qr-debug`
- `RUNTIME_TMP_DIR=data/runtime/tmp`
- `FAILED_RETAINED_DIR=data/runtime/failed-retained`

#### `docker`

Use for:

- Docker image runtime
- `docker compose up`
- `/app/data` volume-backed persistence

Defaults:

- `APP_PORT=8000`
- `DATABASE_URL=sqlite:////app/data/olre.sqlite3`
- `INPUT_DIR=/app/data/input`
- `PROCESSED_DIR=/app/data/processed`
- `ERROR_DIR=/app/data/error`
- `QR_DEBUG_DIR=/app/data/qr-debug`
- `RUNTIME_TMP_DIR=/app/data/runtime/tmp`
- `FAILED_RETAINED_DIR=/app/data/runtime/failed-retained`

#### `testing`

Use for:

- pytest
- isolated settings construction
- controlled test fixture runtime

Defaults intentionally mirror local development paths rather than Docker paths, because test infrastructure should not depend on container layout unless explicitly requested.

#### `production`

Use for:

- future operational deployment outside local development
- deployments that should retain container-style absolute paths
- future platform-specific runtime hardening

At this stage, `production` remains operationally aligned with Docker-style absolute storage assumptions.

---

## Runtime Resolution Strategy

### New Resolution Model

OLRE now resolves runtime configuration using a clear precedence model:

1. Explicit environment variables
2. Runtime profile selected by `APP_ENV` or `ENVIRONMENT`
3. Profile-specific defaults

This is the core architectural change of the phase.

### `APP_ENV` / `ENVIRONMENT` handling

The settings layer now accepts either:

- `APP_ENV`
- `ENVIRONMENT`

Supported normalized values:

- `development`
- `docker`
- `testing`
- `production`

Common aliases are normalized internally:

- `dev` -> `development`
- `test` -> `testing`
- `prod` -> `production`

### Explicit environment variable precedence

Profile defaults are only used when a specific value is not explicitly supplied.

That means these still override profile behavior when set:

- `APP_PORT`
- `DATABASE_URL`
- `INPUT_DIR`
- `PROCESSED_DIR`
- `ERROR_DIR`
- `QR_DEBUG_DIR`
- `RUNTIME_TMP_DIR`
- `FAILED_RETAINED_DIR`

This preserves backward compatibility for:

- existing local `.env`
- Docker environment injection
- future deployment scripts
- test fixtures using `monkeypatch.setenv(...)`

### Why local development now defaults to `data/...`

Local development should not require a container-style filesystem. A developer cloning OLRE and starting a local `venv` should get repository-local storage by default:

```text
data/input
data/processed
data/error
data/qr-debug
data/runtime/tmp
data/runtime/failed-retained
```

This aligns with:

- workstation usability
- relative-path portability
- local Alembic + SQLite workflow
- predictable startup on macOS/Linux

### Why Docker still resolves to `/app/data/...`

Docker still requires an absolute, volume-backed persistence root. That behavior was preserved deliberately because it is correct for container runtime:

```text
/app/data/input
/app/data/processed
/app/data/error
/app/data/qr-debug
/app/data/runtime/tmp
/app/data/runtime/failed-retained
```

This keeps:

- Docker named volume persistence
- container restart safety
- runtime startup path validation
- `/healthz` and `/readyz` semantics

### Conceptual examples

#### Example 1: local development with no `.env`

```env
APP_ENV=development
```

Result:

- SQLite: `sqlite:///data/olre.sqlite3`
- paths: repo-local `data/...`
- local `uvicorn` can run without needing `/app/data`

#### Example 2: Docker runtime with no extra overrides

```env
APP_ENV=docker
```

Result:

- SQLite: `sqlite:////app/data/olre.sqlite3`
- paths: `/app/data/...`
- container volume layout remains valid

#### Example 3: explicit override inside Docker profile

```env
APP_ENV=docker
APP_PORT=9911
INPUT_DIR=custom/input
```

Result:

- runtime profile is still `docker`
- explicit env vars win
- the settings layer uses the overridden values

This is essential because profiles are defaults, not hard constraints.

---

## Testing Isolation Improvements

### Why tests previously failed when `.env` existed

Before hardening, the settings object read `.env` automatically, and some tests that intended to inspect defaults did not opt out of that behavior.

This caused a subtle but serious issue:

- tests were verifying whatever happened to be in `.env`
- not what the code would do in a clean environment

The readiness test became especially brittle because it was checking startup-critical runtime assumptions.

### Isolated settings construction

The hardening phase introduced explicit isolated settings construction in the runtime readiness tests:

```python
Settings(_env_file=None)
```

That disables automatic `.env` loading for those tests and makes them validate only:

- explicit environment variables supplied by the test
- profile defaults in code

### `tests/conftest.py` stabilization

The shared test fixture now explicitly sets:

```text
APP_ENV=testing
```

This improves suite-wide determinism because test runtime no longer depends on whatever ambient runtime profile might have leaked in from the developer shell or local `.env`.

### Runtime readiness tests are now deterministic

`tests/integration/test_runtime_readiness.py` now verifies:

- development profile resolves local `data/...` paths
- testing profile resolves local `data/...` paths
- docker profile resolves `/app/data/...` paths
- explicit env vars override profile defaults
- isolated settings do not accidentally read local `.env`

This makes readiness testing architecture-level validation rather than machine-level coincidence.

### Verification scenarios completed

Two critical scenarios were verified:

#### 1. pytest with `.env` present

Full suite result:

```text
73 passed
```

#### 2. pytest with `.env` absent

A temporary move-and-restore validation was performed on the real workspace:

- `.env` moved away temporarily
- full pytest executed
- `.env` restored immediately afterward

Result:

```text
73 passed
```

This is the strongest practical confirmation that test behavior no longer depends on the developer's local `.env`.

---

## Docker Runtime Alignment

Introducing runtime profiles required Docker artifacts to become explicit about using the `docker` runtime profile rather than inheriting behavior accidentally.

### `Dockerfile`

Changes:

- `APP_ENV` changed to `docker`
- default exposed port aligned to `8000`
- `QR_DEBUG_DIR` aligned to `/app/data/qr-debug`
- image bootstrap directory creation updated accordingly

Why it mattered:

- once development defaults moved to local `data/...`, Docker had to declare container behavior explicitly
- the image should identify itself as container runtime without ambiguity

### `docker-compose.yml`

Changes:

- `APP_ENV` default changed to `docker`
- container port mapping aligned to `8000:8000`
- runtime environment defaults kept under `/app/data/...`
- healthcheck URL updated to `http://127.0.0.1:8000/healthz`
- QR debug path aligned to `/app/data/qr-debug`

Why it mattered:

- Compose is the clearest expression of operational container runtime
- it should reflect the same profile model the application itself now uses

### `scripts/start-docker.sh`

Changes:

- runtime directory bootstrap updated to `/app/data/qr-debug`
- final `uvicorn` startup default port aligned to `8000`

Why it mattered:

- startup scripts are operational truth at runtime
- if they lag behind the config model, debugging becomes confusing and profile hardening is incomplete

### QR debug fallback paths

`app/batch/qr_debug.py` fallback behavior was updated from:

```text
data/debug/qr
```

to:

```text
data/qr-debug
```

Why it mattered:

- fallback behavior should be consistent with the new profile-aware path vocabulary
- QR debug artifacts are part of runtime storage behavior and should not retain legacy path assumptions

---

## macOS Local Runtime Validation

This hardening phase was driven directly by local workstation behavior, especially on macOS development flow.

### Practical validation flow on local MacBook

The intended local validation path for this phase is:

1. Install and use Python `3.11`
2. Create an isolated virtual environment
3. Activate the local `venv`
4. Use a local `.env` when explicit local overrides are desired
5. Run `python -m alembic upgrade head`
6. Start `uvicorn`
7. Verify SQLite local runtime behavior
8. Run pytest and confirm `.env` no longer destabilizes tests

Representative command flow:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m alembic upgrade head
python -m uvicorn app.main:app --host 0.0.0.0 --port 7777
python -m pytest
```

### Why this local validation mattered

The problem being solved was not abstract. The local runtime had reached a state where:

- it could work only when `.env` was manually prepared correctly
- absence of `.env` could trigger container-style fallback paths
- path validation could target the wrong filesystem root

After hardening, local runtime defaults now point to repository-local `data/...` paths, which is the correct behavior for local workstation execution.

### Important lessons learned

#### 1. Python 3.11 remains the safest current baseline

The project currently targets Python `>=3.11`, and Python `3.11` remains the most stable practical baseline for local development during this phase.

#### 2. Python 3.13 may still introduce compatibility friction

Previous runtime work documented Python `3.13` usage, but this phase reinforced that newer interpreter versions may still surface packaging or dependency-resolution edge cases faster than the application logic itself changes.

#### 3. `pydantic-core` and dependency resolution can become environment problems, not app problems

When local runtime is not isolated cleanly, dependency-resolution issues can look like application instability. In practice, some runtime failures attributed to "OLRE config" are actually:

- interpreter mismatch
- wheel resolution mismatch
- partially isolated environment state

#### 4. isolated `venv` runtime is essential

The biggest operational lesson is that runtime correctness depends on environment isolation:

- isolated virtual environment
- explicit runtime profile
- test isolation from ambient `.env`
- minimal hidden machine state

This phase reduced configuration ambiguity, but clean `venv` usage remains a critical operational discipline.

---

## Verification Results

### Final verification status

The runtime profile hardening phase completed with the following verified outcomes.

### Lint

Command:

```bash
uv run ruff check app tests migrations
```

Result:

```text
All checks passed
```

### Full pytest suite

Command:

```bash
uv run pytest
```

Result:

```text
73 passed
```

### Runtime readiness tests

`tests/integration/test_runtime_readiness.py` passed with the new deterministic profile-aware coverage.

Result:

```text
6 passed
```

Covered:

- development profile path resolution
- testing profile path resolution
- docker profile path resolution
- explicit env override behavior
- `.env` isolation behavior
- readiness endpoint runtime validation

### `.env` isolation verification

Verified scenarios:

- pytest with `.env` present
- pytest with `.env` absent

Both outcomes:

```text
73 passed
```

### Local runtime direction

The architecture now supports local `uvicorn` startup with local-repository `data/...` defaults when `APP_ENV=development` or when development is the implicit default profile.

This was the central functional objective of the phase.

### Docker compatibility preservation

Docker profile behavior remains aligned with:

- `/app/data/...`
- SQLite-first runtime
- explicit container profile semantics
- operational health/readiness endpoints

This preserves compatibility with the Docker runtime direction established in the earlier v0.9.5 packaging work.

---

## Architectural Impact

This phase matters because it changed OLRE from "works when configured correctly" to "knows which runtime it is in."

### 1. Runtime maturity improved

OLRE no longer relies on Docker defaults masquerading as universal application defaults. Runtime behavior now reflects environment intent.

### 2. Predictable environment behavior

The same codebase can now behave predictably across:

- local development
- Docker runtime
- pytest
- future production deployment

without each context having to fight container-specific fallback assumptions.

### 3. Separation of concerns is clearer

The phase established a real distinction between:

- local developer ergonomics
- container persistence layout
- test isolation
- future production operational hardening

That separation is essential for maintainability.

### 4. Production readiness improved

Production readiness is not just about Docker image availability. It also requires:

- deterministic settings resolution
- fewer hidden assumptions
- reproducible startup behavior
- predictable writable path validation

This phase advanced all of those.

### 5. Hidden assumptions were reduced

Before hardening, OLRE encoded several assumptions that were only visible when they broke. After hardening, profile intent is encoded explicitly in the configuration model itself.

That is a major architectural improvement.

---

## Known Remaining Technical Debt

This phase solved runtime profile ambiguity, but it did not complete storage hardening.

### Remaining issues

#### 1. Storage hardening is not yet implemented

Runtime profile correctness does not yet mean storage safety is fully hardened.

#### 2. Filename and path-length risks remain

Long filenames, especially deeply nested or UTF-8-heavy Thai filenames, remain a known operational risk.

#### 3. UTF-8 long filename handling is still incomplete

Observed Linux/macOS issues around very long filenames have not yet been resolved through a storage abstraction or filename normalization strategy.

#### 4. WAL-safe backup strategy is still pending

SQLite backup guidance exists, but a fully hardened, verified WAL-safe operational backup strategy is still a next-phase concern.

#### 5. Content-addressable storage is not yet implemented

This remains a recommended future direction for:

- filename safety
- deduplication clarity
- path stability
- storage abstraction

#### 6. `uv.lock` is still undecided

`uv.lock` appeared during tooling execution in this phase, but lockfile policy for this repository remains unresolved.

This is not a runtime blocker, but it is a workflow and reproducibility decision that still needs explicit team agreement.

#### 7. non-blocking SWIG warnings remain

The pytest suite still emits non-blocking warnings from third-party dependency layers:

- `SwigPyPacked`
- `SwigPyObject`
- `swigvarlink`

These are currently warnings only, not runtime failures.

---

## Recommended Next Phase

### Recommended phase name

```text
Storage Hardening
```

Runtime profile hardening should now be followed by storage hardening, because storage safety is the next major operational risk after runtime predictability.

### Suggested focus areas

#### 1. Content-addressable storage

Move toward storage identity based on content rather than original filename wherever practical.

#### 2. Filename normalization

Introduce a consistent strategy for:

- UTF-8 handling
- path-safe filenames
- collision-safe runtime naming

#### 3. Path-depth safety

Reduce operational risk from deeply nested or overlong path constructions.

#### 4. Backup and restore verification

Operationally verify backup and restore routines, not just document them.

#### 5. WAL-safe SQLite backup

Formalize the exact backup model for:

- `.sqlite3`
- `-wal`
- `-shm`

and test restore workflows end to end.

#### 6. Runtime storage abstraction

Introduce a cleaner storage abstraction so higher-level services stop caring about raw path details wherever possible.

This would reduce future coupling between:

- document lifecycle
- debug artifacts
- retention cleanup
- backup strategy

---

## Final Assessment

The runtime profile hardening phase successfully transitioned OLRE from:

```text
Docker-assumption runtime
```

to:

```text
runtime-aware operational architecture
```

That is the core architectural achievement of this phase.

OLRE no longer treats container defaults as universal truth. Instead, it now models runtime intent directly, supports deterministic test behavior, preserves Docker compatibility, and restores sane local development defaults.

This phase should be considered a meaningful maturity step in OLRE's operational evolution:

- more predictable
- more debuggable
- more portable
- more testable
- better prepared for future storage hardening and production operations

In practical terms, OLRE is now substantially safer to develop, validate, and operate across multiple environments without hidden configuration drift.
