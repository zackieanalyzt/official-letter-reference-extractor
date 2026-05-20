# AGENTS.md

## Project Identity

OLRE (Official Letter Reference Extractor) is a Thai government document OCR and reference extraction system.

Primary goals:
- High OCR reliability
- Deterministic extraction behavior
- Runtime stability
- Operator-friendly diagnostics
- Real-world resilience for scanned Thai official documents

The system prioritizes reliability and traceability over experimental AI behavior.

---

# Architecture Rules

- Keep processing pipeline modular.
- Do not tightly couple OCR, extraction, and storage logic.
- Prefer service-layer architecture.
- Avoid hidden side effects.
- Avoid global mutable state.
- Keep extraction logic deterministic whenever possible.

---

# OCR Rules

- Thai OCR accuracy is more important than processing speed.
- Do not reduce image preprocessing quality to optimize runtime.
- Preserve existing crop heuristics unless explicitly replacing them.
- New OCR heuristics must be additive and backward compatible.
- Never silently remove existing extraction regions.

Preferred behavior:
- Fail gracefully
- Return diagnostics
- Preserve partial extraction result

---

# Extraction Rules

- Reference extraction must remain explainable.
- Regex changes must not reduce backward compatibility.
- Prefer layered fallback extraction strategy.
- Preserve support for low-quality scans and skewed documents.

Avoid:
- Hardcoded assumptions tied to one document template
- Aggressive normalization that destroys original content

---

# Storage Rules

- SQLite is supported for local runtime only.
- Do not introduce destructive migrations.
- Backup and restore compatibility is critical.
- Preserve runtime profile compatibility across versions.

Never:
- Delete user data automatically
- Modify backup structure without migration support

---

# UI Rules

- Thai language support is mandatory.
- UI should remain operator-centric.
- Prefer clarity over visual complexity.
- Diagnostics visibility is more important than aesthetic minimalism.

Avoid:
- Heavy frontend dependencies
- Large client-side frameworks unless necessary

---

# Diagnostics Rules

- All processing failures should emit structured diagnostics.
- Prefer explicit error messages over silent failures.
- Logging should help non-developer operators understand issues.

---

# Testing Rules

Before commit:
- Run extraction regression tests
- Verify runtime profile loading
- Verify backup/restore behavior
- Verify multilingual UI rendering

Do not commit:
- Untested OCR heuristics
- Experimental extraction logic without fallback path

---

# Git Rules

Preferred commit style:
- feat:
- fix:
- refactor:
- docs:
- hardening:
- diagnostics:

Keep commits focused and atomic.

---

# Forbidden Changes

Never:
- Remove runtime compatibility checks
- Remove existing OCR fallback regions without replacement
- Replace deterministic extraction with opaque AI-only extraction
- Introduce cloud dependency for core local workflow
- Hardcode machine-specific paths

---

# Preferred Workflow

When implementing features:
1. Preserve existing behavior
2. Add diagnostics
3. Add fallback handling
4. Add regression safety
5. Update documentation

When uncertain:
- Prefer conservative changes
- Avoid broad refactors
- Preserve operator workflow stability