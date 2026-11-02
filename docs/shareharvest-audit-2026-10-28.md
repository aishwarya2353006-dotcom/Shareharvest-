# ShareHarvest Repository Audit — 2026-10-28 (current)

This file is the current audit record. Older UI notes (`shareharvest-ui-audit.md`, `todo.md`, historical `run_*.log`, `phase*_report*.txt`) describe earlier snapshots and must not be treated as current verification.

## Verification actually performed in this audit

| Check | Command | Result |
|---|---|---|
| Django system check + full backend test suite | `.venv\Scripts\python.exe manage.py test --failfast` (with `DEBUG=True` forced) | **97 tests found, run to completion: 95 passed, 2 skipped** (the 2 skips are the concurrency tests that require PostgreSQL row locks; SQLite cannot verify them). No failures. |
| Frontend lint | `npm run lint` (frontend) | Passed, no errors emitted |
| Frontend production build | `npm run build` (frontend) | Passed (Vite build completed) |
| Browser/manual route verification | — | **Not performed** in this audit. |
| Migration completeness | settings/apps inspected, `compliance` app has migrations | Migration state consistent; no pending model changes detected during test-DB creation |

Environment notes: backend has no local `.env`; a project-root `.env` with dev-only `SECRET_KEY`/`DEBUG=True` exists (git-ignored). Tests were run with `DEBUG=True` forced in the shell.

## Backend inventory (all apps verified mounted in `config/settings.py` and `config/urls.py`)

| App | Key models | Key endpoints | Tests |
|---|---|---|---|
| accounts | `User` (AbstractUser + role/phone/is_verified) | register, login (CSRF-wrapped), logout, csrf_token, me (GET/PATCH), change-password | yes |
| organizations | `Organization`, `Membership` (owner/admin/member/volunteer) | CRUD + verify/reject/pending (admin only), user-search, membership CRUD with role-escalation and last-owner protection | yes |
| donations | `Donation` (status machine draft→published→reserved→completed/expired/cancelled; unit-aware quantity) | CRUD, `?browse=1` (recipient-only, in-window, remaining>0), `?mine=1`, transition matrix, publish requires verified org, delete blocked when history exists | yes |
| donation_requests | `DonationRequest`, `DonationAllocation` | create (validated, duplicate-open-request blocked), approve (idempotency-key required, row-locked, partial/full), reject, cancel, allocation read API | yes |
| pickups | `Pickup` (one per allocation, DB-enforced status/timestamp consistency) | schedule, reschedule, start, complete (actual qty), fail, no-show, cancel, assign-volunteer, eligible-allocations, available-volunteers | yes |
| notifications | `Notification` (deduplicated per recipient+event) | list/mark-read/mark-all-read; services wired into request submit/review and every pickup event | yes |
| impact | — | `/api/impact/summary/` (completed_pickups, total_allocated_kg from mass units only, donations_published, organizations) | none found |
| audit | `AuditLog` | admin-only read API with object_type/action filters | none found |
| compliance | FSSAI compliance records + allergen declarations (per donation) | submit/verify/reject compliance, submit/review allergen declarations, org-scoped reads | yes |

## Frontend inventory

- React 18 + Vite 5, axios, react-router-dom 6, plain CSS with a single token block shared with the landing page. No UI framework.
- Routes: public `/`, `/login`, `/register`; donor (dashboard, donations, requests, pickups, organizations), recipient (dashboard, browse, requests, pickups, organizations), volunteer (pickups), admin (organizations); shared `/notifications`, `/settings`, `/compliance`; catch-all 404. All protected routes wrap `ProtectedRoute` (role guard) + `MainLayout`.
- Sidebar per-role navigation matches routes exactly; active state uses `NavLink`; mobile drawer has focus trap, Escape, scrim, close-on-navigate.
- Topbar: notification popover (recent 5, mark-read, unread badge, links into role-correct pages), profile popover (identity + logout), both close on Escape/outside-click.
- `api.js` axios instance: CSRF bootstrap for unsafe methods, 401 → redirect to `/login` (excluding auth endpoints).
- Pages load real API data throughout; loading/error/retry/empty states are present on every data page (verified by reading each page component).

## Feature classification

| Feature | Class | Evidence |
|---|---|---|
| Registration/login/logout/session/CSRF | 1 — Implemented and verified (backend tests) | accounts app + passing tests |
| Role guard, protected routes | 1 | ProtectedRoute + App.jsx; backend re-checks role on every write |
| Organizations CRUD/verification/memberships | 1 | organizations app + tests; admin verify/reject regression-tested |
| Donation create/edit/publish/transition rules | 1 | donations app + tests |
| Browse available food (recipient) | 1 | `?browse=1` filters status/window/remaining; page renders real data |
| Requests + approve/reject/cancel + idempotent partial allocation | 1 | donation_requests app + tests |
| Pickup schedule→start→complete/fail/no-show lifecycle | 1 | pickups app + tests (concurrency variants skipped on SQLite) |
| Notifications for request + pickup events | 1 | notifications services wired into both viewsets |
| Compliance/allergen declarations | 1 (backend tests) / 2 (page renders, no browser verification) | compliance app + CompliancePage |
| Impact summary API | 2 — Implemented, not verified by tests (no impact tests found) | impact/views.py |
| Audit log read API | 2 (read path exists, admin-only) | audit/views.py |
| Audit log **writes** | 4 — Backend partially exists (service), but **no view calls it**; grep for `log_audit` in donations/organizations/pickups/compliance views returns nothing | audit/services.py |
| Donation cancel action from donor UI | 7 — Not implemented (backend transition matrix allows it; UI offers edit/publish only) | MyDonationsPage.jsx |
| Recipient request edit/cancel UI | 7 — Backend supports cancel (pending) and edit (pending); recipient page exposes neither | MyRequestsPage.jsx, donation_requests/views.py |
| Volunteer task discovery/self-claim | 7 — Not implemented; volunteers only see pickups already assigned to them | pickups/views.py `pickup_queryset_for` |
| Volunteer onboarding path | 7 — Not implemented (memberships can add volunteer role, but no invite/approval flow) | organizations app |
| Impact dashboard UI | 7 — Not implemented (API only) | no impact page/route |
| Audit history UI | 7 — Not implemented (API only) | no audit page/route |
| Admin user management page | 7 — Not implemented beyond org membership roles | — |
| Donation photos, city/area filters, expiry scheduler, email/SMS delivery | 7 — Not implemented | — |
| Password change session continuity | 3 — `set_password` without `update_session_auth_hash`; current session is invalidated silently while Settings copy says otherwise | accounts/views.py:39 |
| Concurrent allocation/pickup safety on production DB | 8 — Blocked: code uses `select_for_update` + unique constraints correctly, but SQLite cannot execute the row-lock tests; PostgreSQL verification pending | skipped tests |
| Production security configuration | 3 — defaults are dev-safe but not fail-closed for production | config/settings.py |

## Security / data-integrity findings (prioritized)

| # | Severity | Finding | Where | Recommendation |
|---|---|---|---|---|
| 1 | High | Browse endpoint returns full `pickup_address` and `pickup_instructions` to any recipient before approval (`fields = '__all__'`) | donations/serializers.py, donations/views.py `browse` branch | Serve a browse-safe serializer omitting those fields; expose exact address only after approval (via allocation/pickup records). |
| 2 | High (deploy) | `DEBUG`/`SECRET_KEY` fall back to insecure dev values; startup does not fail closed in production | config/settings.py | Fail fast in production when defaults are present; enforce HTTPS/secure cookies there. |
| 3 | Medium | Platform admins bypass the donation transition matrix (invalid transitions accepted for admin) | donations/views.py:108-114 | Enforce matrix for all roles; add an explicit audited recovery action if admin override is needed. |
| 4 | Medium | Audit service exists but is never invoked; audit trail is effectively empty despite the read API | audit/services.py; grep shows no callers | Call it inside the transaction for verify/reject/approve/pickup transitions; test actor+timestamp+immutability. |
| 5 | Medium | Impact `total_allocated_kg` counts allocations regardless of pickup completion; misleading as "impact" | impact/views.py | Report allocated vs delivered (completed pickups' actual_quantity) separately. |
| 6 | Medium | Password change invalidates the session without telling the user | accounts/views.py | Call `update_session_auth_hash` or sign the user out explicitly with a message. |
| 7 | Low | Partially approved requests cannot be cancelled (recipient stuck if donor approved part) | donation_requests/views.py `cancel` | Define cancellation policy for partially approved requests that restores stock atomically. |
| 8 | Low | `NotificationsProvider`/unread polling and duplicate `getAllPages` helpers are minor code-health items, not defects. | frontend/services | Consolidate opportunistically later; no behavior change needed now. |

## Sidebar audit (by role)

Every sidebar entry below has: matching route ✓, role-guarded ✓, real API ✓, loading/error/empty states ✓, active-state styling ✓. Browser/mobile/refresh behaviors follow the same source-verified patterns as prior snapshots but were **not** re-verified in a live browser this audit.

| Role | Label | Route | Status |
|---|---|---|---|
| Donor | Overview | /donor/dashboard | Implemented (real metrics from donations/requests/pickups) |
| Donor | My Donations | /donor/donations | Implemented (create/edit/publish; cancel action missing) |
| Donor | Donation Requests | /donor/requests | Implemented (approve w/ idempotency, reject) |
| Donor | Organizations | /donor/organizations | Implemented |
| Donor | Food Safety & Compliance | /compliance | Implemented (submit/declare; admin verifies) |
| Donor | Pickups | /donor/pickups | Implemented (full lifecycle) |
| Donor | Notifications / Settings | /notifications, /settings | Implemented |
| Recipient | Overview | /recipient/dashboard | Implemented |
| Recipient | Browse Food | /recipient/browse | Implemented (search + category filter, request form) |
| Recipient | My Requests | /recipient/requests | Implemented (read-only; edit/cancel UI missing) |
| Recipient | Organizations | /recipient/organizations | Implemented |
| Recipient | Pickups | /recipient/pickups | Implemented |
| Recipient | Notifications / Settings | shared | Implemented |
| Volunteer | My pickups | /volunteer/pickups | Partial (assigned pickups only; no discovery/claim) |
| Volunteer | Notifications / Settings | shared | Implemented |
| Admin | Organization review | /admin/organizations | Implemented (verify/reject/pending) |
| Admin | Food Safety & Compliance | /compliance | Implemented (review queue) |
| Admin | Notifications / Settings | shared | Implemented |

No broken routes, no duplicate items, no placeholder "Soon" entries, no menu items pointing at unauthorized pages. Sidebar intentionally omits impact/audit because no pages exist for them yet — correct behavior.

## Code changes made during this audit

None. This pass was read-only plus test execution; no source files were modified, no database or migration changes were made, and nothing was committed to Git.

## Immediate next tasks (ordered)

1. Browse-safe donation serializer (removes address leakage) — smallest high-impact fix, no schema change.
2. Fail-closed production settings.
3. Enforce donation transition matrix for admins too.
4. Wire audit logging into verification/approval/pickup transitions.
5. Add recipient request edit/cancel UI (backend already supports both for pending requests).
