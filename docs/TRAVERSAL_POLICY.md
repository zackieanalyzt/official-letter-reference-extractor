# OLRE Traversal Policy

## Position

**OLRE traversal is not a crawler.**

Traversal policy exists to keep linked-document handling controlled, deterministic, auditable, bounded, and safe. It applies only to references that OLRE has already extracted from official-letter PDFs. It must not expand arbitrary HTML links or discover new URLs beyond extracted QR/URL references.

Phase 1 is docs-only. No traversal policy is active in runtime until a later implementation phase adds settings, services, and storage.

## Strict Defaults

Traversal must be disabled by default:

```env
TRAVERSAL_ENABLED=false
TRAVERSAL_MAX_DEPTH=1
```

Traversal must not run automatically by default. In Phase 2, any downloader must be manual, single-depth, and operator-triggered.

## Proposed Configuration

Recommended future settings:

```env
TRAVERSAL_ENABLED=false
TRAVERSAL_MAX_DEPTH=1
TRAVERSAL_MAX_DOCUMENTS_PER_BATCH=20
TRAVERSAL_ALLOWED_CONTENT_TYPES=application/pdf
TRAVERSAL_TIMEOUT_SECONDS=15
TRAVERSAL_MAX_DOWNLOAD_MB=20
TRAVERSAL_ALLOWED_DOMAINS=
TRAVERSAL_BLOCK_PRIVATE_IPS=true
TRAVERSAL_STORAGE_DIR=/app/data/runtime/linked-documents
```

| Setting | Default | Meaning |
| --- | --- | --- |
| `TRAVERSAL_ENABLED` | `false` | Master switch; traversal cannot execute when false |
| `TRAVERSAL_MAX_DEPTH` | `1` | Maximum allowed traversal depth |
| `TRAVERSAL_MAX_DOCUMENTS_PER_BATCH` | `20` | Upper bound for linked-document actions in one batch/manual operation |
| `TRAVERSAL_ALLOWED_CONTENT_TYPES` | `application/pdf` | Allowed downstream content types |
| `TRAVERSAL_TIMEOUT_SECONDS` | `15` | Maximum time for a future network operation |
| `TRAVERSAL_MAX_DOWNLOAD_MB` | `20` | Maximum linked file size |
| `TRAVERSAL_ALLOWED_DOMAINS` | empty | Optional allowlist; empty means no domain allowlist is applied |
| `TRAVERSAL_BLOCK_PRIVATE_IPS` | `true` | Blocks private/local network targets |
| `TRAVERSAL_STORAGE_DIR` | `/app/data/runtime/linked-documents` | Controlled storage area for future linked downloads |

## Policy Decisions

Future policy evaluation should produce a stable decision:

| Decision | Meaning |
| --- | --- |
| `allowed` | Candidate may proceed to the next manual traversal step |
| `blocked` | Candidate is valid in shape but rejected by policy |
| `unsupported` | Candidate is not a supported traversal target |
| `not_evaluated` | Candidate has not yet been evaluated |

Policy reasons should be stable enough for tests and operator reporting, for example:

- `traversal_disabled`
- `depth_limit_reached`
- `unsupported_scheme`
- `unsupported_target_type`
- `unsupported_content_type`
- `domain_not_allowed`
- `private_ip_blocked`
- `loopback_blocked`
- `link_local_blocked`
- `file_too_large`
- `timeout_limit_required`
- `html_expansion_not_supported`

## Target Classification Policy

| Target type | Policy |
| --- | --- |
| Direct PDF URL | Candidate may be allowed if all safety checks pass |
| Known short URL | Candidate may be planned, but Phase 2 must still apply URL resolution and safety checks before download |
| HTML page | Unsupported; no HTML link expansion |
| Image URL | Unsupported |
| Malformed URL | Unsupported |
| Unsupported scheme | Unsupported |
| Unknown target | Unsupported |

No HTML link expansion is allowed. A resolved HTML page must not be parsed for links in Phase 2.

## Security Boundary

Future traversal must enforce these guardrails before any linked document is persisted as a child document:

- block unsupported schemes
- allow only `http` and `https`
- block private IP targets
- block loopback targets
- block link-local targets
- block multicast, unspecified, and otherwise non-routable IP targets
- enforce timeout
- enforce file size cap
- enforce allowed content type
- apply optional domain allowlist when configured
- never expand HTML links
- never write linked files into the normal import inbox

Private-network protection must apply both to the original host and to the final resolved host after redirects in a later downloader phase. DNS resolution and redirect handling must be designed to avoid SSRF bypasses.

## Depth and Cycle Policy

Default maximum depth is `1`.

Depth policy:

- Original imported document depth is `0`.
- Linked document candidate from the original document is depth `1`.
- Any target beyond depth `1` is `DEPTH_LIMIT_REACHED` by default.

Cycle policy:

- Prevent `A -> B -> A`.
- Prevent repeated traversal of the same resolved URL for the same parent/reference pair.
- Use existing SHA-256 duplicate detection before creating a child document.
- A duplicate linked document must preserve provenance through the traversal row rather than creating an untraceable document.

## Provenance Policy

Every linked document candidate must trace back to exactly one `parent_document_id` and one `source_reference_id`.

Policy decisions must be recorded with the traversal candidate so operators can understand why a linked document was not followed, was blocked, or was later accepted.

No child document may exist without traversal provenance when it enters OLRE through the traversal path.

## Storage Policy

Future linked files should use:

```text
TRAVERSAL_STORAGE_DIR=/app/data/runtime/linked-documents
```

Local development may resolve this to:

```text
data/runtime/linked-documents
```

The traversal storage area is a staging area, not the normal import inbox. Files placed there must be subject to cleanup and retention rules in a later design.

## Phase 2 Downloader Rule

If Phase 2 adds a downloader, it must be:

```text
manual single-depth operator-triggered traversal
```

It must not be automatic recursive crawl behavior. It must remain disabled by default and respect `TRAVERSAL_ENABLED=false`.

## No-Internet Test Policy

Phase 2 tests must not require internet access.

Use:

- mocked HTTP clients
- local fixture files
- local test URLs with mocked responses
- deterministic content-type and content-length fixtures
- in-memory or temporary file storage

Tests must cover policy decisions without depending on external network availability, DNS, remote redirects, or live public websites.

## Phase 2 Entry Criteria

Phase 2 may start only when:

- Phase 1 docs are reviewed
- security guardrails are approved
- provenance model is approved
- policy config defaults are approved
- there is no objection to the proposed schema
- the controlled pilot branch remains stable

