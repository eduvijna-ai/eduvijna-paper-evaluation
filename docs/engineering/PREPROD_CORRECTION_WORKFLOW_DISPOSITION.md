# Preprod disposition: OCR / mapping correction workflow

**Status:** OUT OF SCOPE for live production / B6 HTTP path  
**Related:** FCR-004 (`docs/engineering/FRONTEND_CONTRACT_REQUESTS.md`), B6 evaluation report

## Decision

`OCR_TRANSCRIPTION_ERROR` and `MAPPING_ERROR` teacher actions are **not** unfinished live features. They are explicitly deferred / out of production scope for the live evaluation HTTP adapter.

## Frontend behavior

| Mode | Behavior |
|------|----------|
| **live** (`liveMode`) | Correction action buttons are **hidden** (no disabled stubs, no “not live yet” copy). |
| **mock** | Full action list remains available for mock E2E. |

HTTP guard `CORRECTION_NOT_LIVE` remains in `apps/web/src/lib/api/http/evaluation.ts` so accidental live calls fail clearly. Operators should use Change score / Escalate, or return to transcription / mapping workspaces.

## Do not treat as a P0 production gap

Showing disabled “Correction workflow not live yet” stubs implied incomplete required work. Hiding the actions and documenting this disposition closes that misleading UI without expanding B6 scope.
