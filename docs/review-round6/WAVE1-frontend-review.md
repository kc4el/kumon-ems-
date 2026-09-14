# WAVE1 Frontend Review — Agent D validation (read-only)

Branch: `chore/standard-format` (HEAD `ca7a4f6`). Served template `core/templates/core/index.html` (4046 lines), `static/js/dashboard.js` (1732 lines).

## Automated checks
- `uv run python manage.py check` → **System check identified no issues (0 silenced).**
- `node --check static/js/dashboard.js` → **OK.**
- `curl :8000` → **unreachable (000)** — D started no server; port free; none started per rule.

## Click-through checklist
| # | Check | Verdict | Evidence |
|---|-------|---------|----------|
| 1 | onboarding-docs multipart POST | FAIL | No `/api/onboarding-docs*` route in `api/urls.py`; `handleOnboarding` (`static/js/dashboard.js:589-633`) sends JSON to `/api/employees/` only, no `FormData`/file input; 5 upload buttons toast-only (`core:3936,3946,3957,3967,3978` per `05-frontend.md` §1 #13-18). Suggested patch for integrator: add `OnboardingDocument` model + `MultiPartParser` view at `POST /api/onboarding-documents/`, switch wizard to `FormData`. |
| 2 | advances endpoint wired | FAIL | No `/api/advances*` route; `handleRequestAdvance` (`dashboard.js:960-964`) only `closeAdvanceModal()` + toast. Suggest: `Advance` model + `POST /api/advances/` or honest disabled state. |
| 3 | claim decision wired | PASS | `claim-statuses/` route (`api/urls.py:169-173`) + `ClaimStatusListCreateView.create` upsert (`core/views.py:832-852`) + `loadClaimStatuses/saveClaimStatus/handleClaimAction` (`dashboard.js:899-931`) all wired. |
| 4 | grievance key (`conversation_key`) | FAIL | `Message.conversation_key` exists (`core/models.py:242`) and chat POST sends it (`dashboard.js:1190-1198`), but `handleGrievanceSubmit` (`dashboard.js:636-639`) never POSTs anywhere — toast-only, no key passed. Suggest: `POST /api/messages/` with `conversation_key='grievance'` or dedicated endpoint. |
| 5 | pager wiring | FAIL | Audit pager (`core/index.html:3639-3641`) buttons fire `showToast('Loading page…')` only; `auditPaginationInfo` hardcodes `1,482`. `StandardResultsSetPagination` (`core/pagination.py:4-7`, page_size 10) exists server-side but unused by pager. |
| 6 | file size / MIME rejects | FAIL | `MessageSerializer.attachment` (`core/serializers.py:284`) is unconstrained `FileField`; `handleChatFileSelected` (`dashboard.js:1216-1219`) toasts filename with no size/MIME check; pickers (`core:3269-3270`) have no `max-size`/`accept` (except `image/*` on image picker). Suggest: client `file.size` + allowlist guard + server `validate_attachment`. |
| 7 | batch count live | FAIL | `+ Batch Approve (0)` hardcoded (`core:2448`), never updated after `loadClaimStatuses`; `batchApproveClaims` (`dashboard.js:933-945`) fires success toast even on zero pending (false success on no-op). Suggest: recompute count from `.claims-status-pill.pending` after load + each decision; toast `No pending claims` on empty. |
| 8 | design consistency (no new visual language) | PASS w/ minor | Advance modal reuses `.modal-backdrop/.modal-card/.modal-head/.modal-foot/.btn/.btn-navy-cta` (`core:3739-3777`); chat/tour modals reuse `.modal-card/.btn-black-sm` (`dashboard.js:379-406`). Minor: onboarding wizard introduces one-off `modal-dialog-wizard/modal-wizard-*` classes (`core:3789+`) — visually consistent but new tokens; consider reusing `.modal-card`. |

## Minor issues
- `sender_name='Marcus Williams'` hardcoded (`dashboard.js:1192`) though server overwrites from `request.user` (`core/views.py:825-830`) — display-only inconsistency.
- `showToast(msg,'error')` type arg dead (single-arg definition, `dashboard.js:841`) — error toasts unstyled.
- `pages/dashboard*.html` stale mirrors still double-load `dashboard.js`.
