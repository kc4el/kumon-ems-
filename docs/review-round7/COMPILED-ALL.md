# Review Round 7 — Compiled: UX test + 4 system reviews

Branch `feat/settings-view` @ `2571004` (+ workdir T1–T6 uncommitted). Suite: 280 tests, 8 pre-existing reds (untouched). Method: adversarial persona (Linda, 54, center admin) via code+curl (browser tool blocks localhost, no screenshots/click-through), plus 4 read-only subagent reviews with disjoint scopes. Parent verified every HIGH with grep; MEDIUM/LOW accepted as reported with file:line. Merged duplicates noted inline.

## Part A — UX tickets (Linda)

- **UX-1 = FE-1 (merged): Fake forgot-password toast.** `login.html:62` shows "dispatched" with no request. HIGH. Fix: wire real reset or honest "contact HR/IT" copy.
- **UX-2 = FE-5 (merged): Dual-door login, no guidance.** Employee vs HR door; wrong pick = bare 403. MEDIUM. Fix: one-line door guidance + links both ways; checkin page needs a "which login" link.
- **UX-3: No first-run empty state.** Dashboard with 0 employees offers no "add your first employee" path. MEDIUM. Fix: empty-state card.
- **UX-4: 8.5px sidebar text** (`main.css:158`). HIGH (a11y). Fix: min 11px, audit sub-10px sizes.
- **UX-5: Morning clock-in widget.** Dashboard has no one-tap in/out; staff queue at 8am. GREEN/feature. Fix: small who's-in + in/out widget.
- **UX-6 (catch-all): Copy pass.** "onboarded" → "new staff"; "Conflict"/"Authentication required" → plain words; link kiosk page from Attendance view. YELLOW.

## Part B — System reviews

### SEC (security-auth) — 2 HIGH verified, rest as reported
1. **SEC-H1 (verified): Self-promotion via settings role field.** `MUTABLE_PROFILE_FIELDS` (`serializers.py:530`) includes `role`; `_is_hr_user` (`views.py:138-148`) grants HR on `"hr" in role`. Any employee PATCHes `profile.role` → HR gate passes. Fix: drop `role` (+`email`) from self-service set.
2. **SEC-H2 (verified): Password change wipes ALL sessions.** `views.py:1432-1434` deletes unfiltered by user; under token auth (`session_key=None`) deletes literally everything. Fix: scope to `_auth_user_id == user`.
3. **SEC-M1:** ChangePasswordView skips `validate_password` (accepts common/numeric). Fix: call validators.
4. **SEC-M2:** Password change never revokes DRF tokens nor Supabase password. Fix: delete/rotate tokens + sync Supabase.
5. **SEC-M3:** SessionLoginView 403s oracle account/HR status (vs generic 401). Fix: uniform 401.
6. **SEC-M4:** HrSessionLoginView admits staff with inactive/missing Employee row. Fix: require active linked profile.
7. **SEC-L1:** No Secure/HSTS/session-age flags in `settings.py`. Fix: set for production.
8. **SEC-L2 = DATA-M6 (merged): Unbounded workbook parse** (`views_import.py`). Fix: size + row caps, 400/413.
9. **SEC-L3:** SiteSettings PATCH allowlist missing (any staff key persists). Fix: restrict to `SITE_SETTING_DEFAULTS` + approved extras.
10. **SEC-L4:** `IsOwnerOrStaff`/`OwnerQuerysetMixin` fail open for anonymous (safe today via `IsAuthenticated` everywhere; one future view slips). Fix: deny/scope anonymous.

### DATA (data-integrity) — 4 HIGH (3 verified pattern, 1 reported)
1. **DATA-H1:** `SiteSetting.value` free text, no constraint; corrupt values persist, readers silently fall back. Fix: model `clean()` + log on fallback.
2. **DATA-H2:** Purge `--days 0` allowed, bypasses 1–365 floor (`purge_resigned.py`); fractional truncation via `int(float())`. Fix: reject `<1`, reject non-integers.
3. **DATA-H3:** Purge deletes Supabase user BEFORE local row; local failure after = orphan upstream; broad `except` mislabels. Fix: local-first or reconcile pass.
4. **DATA-H4 (verified pattern): Import Supabase-first leaves orphans.** `views_import.py` creates auth users before `bulk_create`; bulk/DataError paths roll back none. Purge only covers resigned, never these. Fix: local-first + reconcile, or compensate per row.
5. **DATA-M1 = API-M4 (merged): page_size unenforced below serializer.** No model/DB range; stored >100 bypasses `max_page_size` clamp (`pagination.py:15`). Fix: clamp in `get_page_size` + model validators.
6. **DATA-M2:** Silent `_site_val`/`_site_decimal` fallbacks mask DB death + corruption. Fix: log + distinguish unset vs invalid.
7. **DATA-M3:** OT `hours` omittable in serializer, required in model → 500 not 400; no non-negative check. Fix: `required=True` + `MinValueValidator(0)`.
8. **DATA-M4:** Multiplier checked against hour-semantics settings (24h → 24x); silent lo>hi reset. Fix: separate multiplier bounds or error loudly.
9. **DATA-M5:** Uniqueness pre-checks race; no IntegrityError→409 mapping at serializer layer. Fix: catch + 409.
10. **DATA-M6:** = SEC-L2 (merged above).
11. **DATA-M7:** Import `bulk_create` skips `full_clean`; overlong cells → uncaught DataError → whole batch 500. Fix: pre-validate lengths, catch DataError per row.
12. **DATA-L1:** Migration 0029 seeds no `SiteSetting` rows; fresh installs run on phantom defaults. Fix: data migration with 4 seeds.

### FE (frontend, settings/auth/a11y) — 3 HIGH (2 verified, 1 reported)
1. **FE-H1 = UX-1** (above).
2. **FE-H2 (verified): Hardcoded live credentials in signup form.** `login.html:103-124`: `EMP-10482`, `employee@kumon-ems.com`, `SecurePass2026!`, policy box pre-checked; demo-copy claims prefill that doesn't exist on login. Fix: strip values + checkbox default; fix or drop copy.
3. **FE-H3 (verified): Three dead company inputs.** `setAttGrace/setLeaveQuota/setPayAdvanceMax` (`index.html:3726-3741`) never loaded/saved by `renderSettingsSite`/`saveSettingsSite` — edits silently discarded. Fix: wire or remove.
4. **FE-M1 (verified, upgraded): Import card bypasses the import endpoint.** Card parses client-side and POSTs row-by-row to `/api/employees/` (`dashboard.js:2525-2550`); `settings/import-employees/` (dry-run, bulk, per-row errors) is never called; `accept=".xlsx,.xls,.csv"` but parser is comma-split with silent 50-row cap. Fix: call the real endpoint for xlsx, keep row-POST only for csv — or restrict accept to `.csv`.
5. **FE-M2 = UX-2** (above).
6. **FE-M3:** `setReadOnlyNet` stuck on "Loading…" for non-staff; Company tab vanishes silently. Fix: error/empty states + "contact HR admin" note.
7. **FE-M4:** Settings load failure leaves stale live-looking form. Fix: disable saves + error state.
8. **FE-M5:** Settings pills lack tab semantics/keyboard/aria. Fix: `role=tablist/tab/tabpanel` + arrow keys.
9. **FE-M6:** Bare `<label>`s, selects lack names. Fix: `for`/`aria-label` throughout.
10. **FE-M7:** Confirm modal not a dialog (no role/focus trap/Esc). Fix: mirror leaveModal pattern.
11. **FE-M8:** Toasts color-only, never announced. Fix: `aria-live` + error prefix.
12. **FE-M9:** Checkin label says email, code sends name; footer contradicts. Fix: one identifier end to end.
13. **FE-M10:** Login label/hint/checkbox disagree on email-vs-ID. Fix: single identifier wording.
14. **FE-M11:** A11y tail is 3 rules only; no `:focus-visible`, no OS `prefers-*` fallbacks, contrast map partial. Fix: focus rings + media queries.
15. **FE-L1:** Inline-style sprawl in settings markup vs tokens. Fix: extract classes.
16. **FE-L2:** apiFetch throws bare `'auth'`/`'load failed'`/`'save failed'`. Fix: actionable copy.
17. **FE-L3:** Show-password toggles expose no state. Fix: `aria-pressed` + Hide swap.

### API (api-contract) — 1 HIGH verified, rest as reported
1. **API-H1 (verified): `complaints/<int:pk>/` vs UUID pk.** Detail route unreachable (`urls.py:84`; `models.py:285`). Fix: `<uuid:pk>`.
2. **API-M1:** `claims/<str:pk>/decision/` returns `{id}` vs `{claim_id}` per branch. Fix: one envelope.
3. **API-M2:** `leave-requests/` alias lacks detail counterpart. Fix: add or drop alias.
4. **API-M3:** = DATA-M1 (merged above).
5. **API-M4:** `ClaimStatusListCreateView.create` returns 200 not 201. Fix: 201.
6. **API-M5:** SiteSettings GET/PATCH shape mismatch (read-only keys in GET, dropped in PATCH). Fix: same envelope or 400 on keys.
7. **API-M6:** Import always-200 + dry-run/commit envelope mismatch. Fix: non-2xx on total failure + uniform row errors + counts.
8. **API-M7:** `auth-token/` failure uses `{non_field_errors}` not `{error}`. Fix: wrap to envelope.
9. **API-L1:** `claims/` alias lacks detail route; non-UUID codes have none. Fix: add or document.

## Fix order (suggested, not started)
1. SEC-H1 + SEC-H2 (privilege escalation + global logout — both one-spot fixes).
2. FE-H2 (live password in HTML — strip now).
3. DATA-H2/H3/H4 + API-H1 (purge/import safety + dead route).
4. UX-1/UX-4 + FE-H3/FE-M1 (fake toast, font size, dead inputs, import wiring).
5. Everything MEDIUM in one pass; LOWs opportunistically.

Counts: 6 UX + 10 SEC + 13 DATA + 17 FE + 9 API − 6 merges = **49 unique items** (5 HIGH-verified, 4 HIGH-reported).
