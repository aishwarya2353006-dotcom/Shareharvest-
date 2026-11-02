# ShareHarvest Project Audit

**Audit date:** 2026-10-26  
**Scope:** Current workspace source, configuration names, documentation, tests, and routes.  
**Method:** Direct inspection of the React/Vite frontend and Django/DRF backend; source-level workflow and permission review; backend checks/tests and frontend lint/build. The app was not launched in a browser during this audit, so rendered behavior, viewport behavior, direct-refresh behavior, and live API integration are not claimed as browser-verified.

This audit describes code in the workspace, not a clean Git baseline: `git ls-files` returned no tracked files and the working tree lists the repository contents as untracked. The development SQLite database was not read or modified. Django tests used a temporary test database. `.env` and credential/cookie capture values were not opened; only variable names and filenames were checked.

## Executive summary

ShareHarvest is an implemented Django/DRF + React application, not a blank scaffold. Its strongest area is the authenticated donation-to-allocation-to-pickup workflow: server-side organization scoping, quantity checks, idempotent allocation approvals, pickup state validation, notification delivery, and relevant API tests are present. Donor and recipient pages consume real API responses and provide loading/error/empty states.

It is not yet a release-ready multi-role SaaS. Highest-priority gaps are (1) the authenticated browse endpoint serializes exact donor pickup addresses before a recipient has an approved request, (2) production safety depends on overriding `DEBUG=True` and a known development `SECRET_KEY` fallback, (3) platform administrators bypass the donation state-transition matrix, (4) audit and impact functions do not yet provide trustworthy end-to-end operational reporting, and (5) volunteers cannot discover or claim tasks and cannot self-register through the public registration flow. Food safety/allergen fields, donation photos, city-based discovery, and admin user management are also absent.

One narrow defect was fixed during the audit: the platform-admin organization rejection action referenced `timezone` without importing it. A regression test now covers an authorized rejection and rejection denial for a non-admin.

## Repository inventory

| Area | Observed implementation | Current confidence |
|---|---|---|
| Frontend | React 18, Vite 5, React Router 6, Axios, one shared CSS file; 39 files under `frontend/src` | Source inspected; production build/lint passed |
| Backend | Django 4.2-compatible dependency range, DRF, session authentication, CSRF, custom `accounts.User`; domain apps for accounts, organizations, donations, donation requests, pickups, notifications, impact, audit, and core | Source inspected; Django checks and tests run |
| Database | SQLite development database at `backend/db.sqlite3`; app migrations exist, including integrity migrations for allocations/notifications/pickups | Database contents not inspected; `makemigrations --check --dry-run` reported no drift |
| Tests | Backend app tests and `backend/qa_tests`; no frontend test script/framework in `frontend/package.json` | Backend tests run; no browser/E2E run |
| Environment | Settings read `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, and `CORS_ALLOWED_ORIGINS`; local `.env` and cookie/CSRF artifacts exist but their values were not inspected | Deployment configuration not verified |
| Documentation | Architecture, API, data model, UI audit, and benchmark/roadmap documents exist | Current source takes precedence where older docs conflict |

Primary entry points: [frontend/src/App.jsx](../frontend/src/App.jsx), [frontend/src/main.jsx](../frontend/src/main.jsx), [backend/config/urls.py](../backend/config/urls.py), [backend/config/settings.py](../backend/config/settings.py).

## Feature inventory

Statuses use the requested categories: **implemented and verified**, **implemented but not verified**, **partially implemented**, **UI exists but backend integration is missing**, **backend exists but the UI is missing**, **placeholder or non-functional**, **not implemented**, and **blocked**.

| Feature | Status | Evidence and limits |
|---|---|---|
| Public landing page | Implemented but not verified | Real React page and responsive public navigation are in [LandingPage.jsx](../frontend/src/pages/LandingPage.jsx); visual rendering was not browser-checked. The impact section is explanatory copy, not live impact data. |
| Registration, login, logout, session restore, profile and password change | Implemented and verified | Session/CSRF flow in [AuthContext.jsx](../frontend/src/context/AuthContext.jsx), [accounts/views.py](../backend/accounts/views.py), and account tests. Public registration permits donor/recipient only. Password change changes the password but does not refresh the Django session hash; this conflicts with the Settings UI statement that the user stays signed in. |
| Volunteer/admin onboarding and user administration | Partially implemented / blocked | User roles exist, but registration allows only donor and recipient and there is no user-management API or admin UI. Volunteer/admin provisioning therefore requires out-of-band setup. |
| Protected frontend routes | Implemented but not fully verified | Role guards cover all configured application paths in [App.jsx](../frontend/src/App.jsx) and [ProtectedRoute.jsx](../frontend/src/components/ProtectedRoute.jsx). Route behavior was source-reviewed, not browser-tested. |
| Organization create, member list, profile, membership role management, verification | Implemented and verified | Scoped organization/membership viewsets and tests exist. Owners are added at creation; manager search/add/reactivation and last-owner protections are implemented. The rejection endpoint import defect was corrected and regression-tested in this audit. |
| Organization status notifications | Partially implemented | A notification type exists, but verification/rejection actions do not call a notification service. |
| Donation create, edit, publish, browse, expiry | Implemented and verified with limits | Donor create/edit/publish form and recipient browse/request form use real APIs. Publishing requires verified organizations. An expiry command exists, but no scheduler configuration was found. The donor UI does not expose a cancel/close action. |
| Donation details, media, food safety and allergens | Not implemented | Donation has text/category/quantity/windows/address/instructions only. No image upload, allergen declaration, storage/temperature/use-by guidance, safety checklist, or recipient-facing safety record was found. |
| Donation discovery by city | Partially implemented | Organizations store city/state/country and donations store pickup address. Browse returns all currently published offers and applies search/category filters in the browser; it has no server-side city/geo filter. |
| Donation requests, edits, review, rejection, cancellation, allocations | Implemented and verified with UI gaps | Server validates recipient role, organization status/type and membership, availability, compatible units, stock, and duplicate open requests. Allocation approval is transactional and idempotent. Recipient UI tracks requests but does not expose backend pending-request edit/cancel actions. Only pending requests can be cancelled; partially approved requests cannot. |
| Over-allocation and duplicate pickup controls | Implemented, tested with SQLite caveat | Row locks, database uniqueness/idempotency constraints, and boundary/concurrency tests exist. SQLite does not provide production-grade row-level `SELECT FOR UPDATE` semantics; concurrent behavior on the intended production database remains to be verified. |
| Pickup schedule, assignment, progress, completion, failure, no-show and cancellation | Implemented and verified with role gap | API/state constraints and donor/recipient/assigned-volunteer controls exist. A volunteer can only see pickups already assigned to them; no open-task discovery or volunteer self-claim flow exists. Pickup completion records actual quantity but does not automatically close the donation when all deliveries finish. |
| Notifications | Implemented and verified for request/pickup events | User-scoped list, unread count, single/all read actions and request/pickup triggers exist and are tested. Organization verification notifications and scheduled reminders are absent. |
| Impact reporting | Backend exists but UI is missing; reporting is only partial | Authenticated `/api/impact/summary/` aggregates organization-linked pickups, allocations, published listings, and organizations. There is no frontend route or dashboard consumer. `total_allocated_kg` means allocated mass, not delivered mass; it sums allocations without requiring completed pickups. `donations_published` counts status, not whether the availability window is current. |
| Audit history | Partially implemented | Admin-only read API and model exist, but `log_audit()` has no call sites in the backend. Its broad exception handler silently discards failures. Sensitive workflow actions are therefore not demonstrably recorded. |
| Admin operations | Partially implemented | Admin UI supports organization verification/rejection/status reset. There is no UI for user management, operational workflow monitoring, impact reports, or audit history. Django admin protects organization deletion and makes membership records read-only, but no custom user admin was found. |
| Application-wide loading/error/empty states | Implemented with source evidence | Data pages generally show loading, retry/error, and empty states. This was not verified in a live browser. |
| Frontend automated tests | Not implemented | `frontend/package.json` contains `lint` and `build` scripts but no test script or frontend test framework. |

### Backend correctness and security findings

| Severity | Finding | Evidence | Recommended correction |
|---|---|---|---|
| **High — privacy** | Exact donor pickup address and pickup instructions are included in the browse response for every authenticated recipient. `DonationSerializer` exposes `fields = '__all__'`; browse intentionally returns offers from all donor organizations. | [donations/serializers.py](../backend/donations/serializers.py), [donations/views.py](../backend/donations/views.py) | Use a browse-specific serializer that omits precise address/instructions (return city/area only), and reveal pickup details only to parties after an authorized allocation/pickup step. Add API tests for both pre- and post-allocation visibility. |
| **High — deployment configuration, conditional** | Settings default to `DEBUG=True` and `SECRET_KEY='django-insecure-dev-key-change-in-production'`. If production starts without overriding these, debugging exposure and a publicly known signing key are possible. | [config/settings.py](../backend/config/settings.py) | Make production startup fail closed on missing/default secret; require `DEBUG=False`, explicit hosts/origins, HTTPS, and secure session/CSRF cookie settings in deployment configuration. Do not copy secret values into reports. |
| **High — lifecycle integrity** | Platform admins bypass the donation transition matrix: the view only rejects an invalid transition for non-admins. A valid status can therefore reopen a completed or cancelled donation. | [donations/views.py](../backend/donations/views.py) | Enforce the transition matrix for all roles; if a platform-admin override is required, define a narrow audited override action and test terminal-state protection. |
| **Medium — auditability** | The audit model/read API are present, but no business view calls `log_audit()`. The service catches every exception and silently passes. | [audit/services.py](../backend/audit/services.py), [audit/views.py](../backend/audit/views.py) | Wire audit writes into verification, membership, donation, allocation and pickup transitions within their transaction boundary; surface failures using the project’s logging/error policy; test actor, timestamps, and immutable history. |
| **Medium — metric truthfulness** | Impact summary labels allocation mass as `total_allocated_kg`, but the calculation is not constrained to completed pickups. Donation model fields named `quantity_kg` also store volume/count values using mass-like conversions; impact currently filters non-mass units, but exposed fields remain ambiguous. | [impact/views.py](../backend/impact/views.py), [donations/models.py](../backend/donations/models.py), [donation_requests/models.py](../backend/donation_requests/models.py) | Report separate requested, allocated, and completed quantities. Compute delivered mass from completed pickups’ actual quantities in mass units. Stop calling volume/count totals kilograms; use dimensioned totals or keep them separate. |
| **Medium — lifecycle/notification completeness** | A pending request can be cancelled, but a partially approved request cannot be cancelled; the recipient UI offers neither edit nor cancel. Completed pickup does not update donation status. Organization verification has no event notification. | [donation_requests/views.py](../backend/donation_requests/views.py), [pickups/views.py](../backend/pickups/views.py), corresponding recipient pages | Define post-allocation cancellation/reversal rules without deleting history, expose supported request actions, and make notification/status transitions reflect that policy. |
| **Medium — session behavior** | Password-change UI says the session remains active; `change_password` calls `set_password()` without `update_session_auth_hash()`, so Django invalidates the current session on a later request. | [accounts/views.py](../backend/accounts/views.py), [SettingsPage.jsx](../frontend/src/pages/settings/SettingsPage.jsx) | Either update the session auth hash after changing the password or change the UX to explicitly sign out and require login. Add a subsequent authenticated-request test. |
| **Low — auth UX** | API response interceptor redirects on HTTP 401 only. DRF SessionAuthentication can return 403 for unauthenticated requests, so already-loaded pages may show a local API error after session expiry rather than a consistent re-auth flow. | [frontend/src/services/api.js](../frontend/src/services/api.js), [config/settings.py](../backend/config/settings.py) | Align frontend expired-session handling with the actual DRF response behavior and test it without redirect loops. |

### UI and visual consistency

- The landing implementation is the intended design reference. `main.css` defines typography, spacing, emerald/focus tokens and motion; the landing page includes light cream sections and internal pages use dashboard-specific cards, forms and tables.
- Authenticated pages use shared layouts and some shared primitives (`PageIntro`, `FactList`, `StatusBadge`, `Loading`), but much of the internal CSS and class vocabulary is donor-prefixed even on recipient, volunteer and admin screens. Some internal labels/facts/buttons use very small 8–11px text; raise the readable minimum and check contrast.
- The same CSS file contains both token-driven colors and many literal light-panel/text values. The landing/dashboards should be compared at real viewport sizes before changing those values; do not make a blanket theme rewrite.
- The notification/profile popovers close on outside click and Escape. The mobile app drawer includes a focus loop, Escape handling, scrim, and close-on-navigation. The public page uses a native `<details>` mobile menu. These are source-observed behaviors, not keyboard/browser test results.
- No production hosting rewrite configuration was found in the Vite config; it only configures the development proxy. SPA deep-link refresh must be checked against the eventual host.
- No competitor branding, layouts, proprietary content, or code are proposed for reuse.

## Route and sidebar audit

All paths below are explicitly configured in [App.jsx](../frontend/src/App.jsx); all sidebar destinations have a matching route. Every protected route has a role guard and shared layout. API existence and data use are source-verified; render, accessibility, mobile, and refresh checks are **not browser-verified**.

| Role | Sidebar label | Destination | Page/API and actual actions | Page states and authorization | Nav/refresh/mobile | Status |
|---|---|---|---|---|---|---|
| Donor | Overview | `/donor/dashboard` | Real donor donations, per-donation requests, pickups; computed metrics and links | Loading/error/retry/empty; donor-only route | `NavLink` exact match; direct refresh/mobile not tested | Implemented; source verified |
| Donor | My Donations | `/donor/donations` | Real donor/org data; create draft, edit, publish | Loading, errors and empty states; backend donor/org permissions | Same; not browser-tested | Implemented; cancel/close action absent |
| Donor | Donation Requests | `/donor/requests` | Real requests; idempotent approval and rejection | Loading/error/empty; backend limits requests to parties/managers | Same; not browser-tested | Implemented |
| Donor | Organizations | `/donor/organizations` | Real memberships/orgs; create org, manage member roles | Loading/error/empty; organization scopes enforced in API | Same; not browser-tested | Implemented |
| Donor | Pickups | `/donor/pickups` | Schedule/edit/assign/cancel, start, complete, fail/no-show as allowed | API enforces party membership and state; UI has loading/error/empty | Same; not browser-tested | Implemented |
| Donor | Notifications | `/notifications` | Paginated real notifications; read one/all | Loading/error/empty; user-scoped API | Same; not browser-tested | Implemented |
| Donor | Settings | `/settings` | Profile update, password change, links to notifications/orgs | Profile load/save and field errors; `/me` is self-scoped | Same; not browser-tested | Implemented; password/session message mismatch |
| Recipient | Overview | `/recipient/dashboard` | Real available donations, own requests and pickups | Loading/error; real API data | Same; not browser-tested | Implemented |
| Recipient | Browse Food | `/recipient/browse` | Real current published offers; client-side search/category; request form | Loading/error/empty/no matches; backend revalidates role/org/stock | Same; not browser-tested | Implemented; address exposure risk |
| Recipient | My Requests | `/recipient/requests` | Real requests and allocations | Loading/error/empty; queryset scoped to recipient | Same; not browser-tested | Implemented; no edit/cancel controls |
| Recipient | Organizations | `/recipient/organizations` | Real memberships; create/manage where permitted | Loading/error/empty; API scope enforced | Same; not browser-tested | Implemented |
| Recipient | Pickups | `/recipient/pickups` | Schedule/edit/assign/progress actions for eligible allocation | API authorizes party membership and state | Same; not browser-tested | Implemented |
| Recipient | Notifications | `/notifications` | Same shared real notification history | User-scoped API | Same; not browser-tested | Implemented |
| Recipient | Settings | `/settings` | Self-profile/password; notifications/org links | Same as donor | Same; not browser-tested | Implemented; password/session message mismatch |
| Volunteer | My pickups | `/volunteer/pickups` | Real pickups already assigned to eligible volunteer; start/complete/fail/no-show | Assigned volunteer is scoped and authorized; loading/error/empty | Same; not browser-tested | Partial: no task discovery or self-claim |
| Volunteer | Notifications | `/notifications` | Shared real notification history | User-scoped API | Same; not browser-tested | Implemented |
| Volunteer | Settings | `/settings` | Self-profile/password/notifications; no organization page link | API self-scope | Same; not browser-tested | Implemented; onboarding out-of-band |
| Admin | Organization review | `/admin/organizations` | Real organization list; verify/reject/reset status | Admin-only mutations; rejection fixed and regression-tested | Same; not browser-tested | Implemented; narrow scope |
| Admin | Notifications | `/notifications` | Shared real notification history | User-scoped API | Same; not browser-tested | Implemented |
| Admin | Settings | `/settings` | Self-profile/password; admin organization link | API self-scope | Same; not browser-tested | Implemented; password/session message mismatch |

Public routes are `/`, `/login`, and `/register`; unknown URLs render an inline 404. The topbar notification popover loads recent notifications, links to history and supports mark-read; the profile popover displays identity and logs out. There are no nested sidebar menus or placeholder “Soon” entries. The sidebars currently omit entry points to backend-only impact/audit APIs and admin user-management/operations because corresponding pages are not implemented; do not add links until those pages exist.

## Verification actually performed

| Check | Result |
|---|---|
| Django `manage.py check` | Passed; no issues reported |
| Django `makemigrations --check --dry-run` | Passed; no model changes detected |
| Focused organization verification test before fix | Passed, but did not exercise rejection |
| New focused admin-rejection regression test | Passed |
| Backend domain + authorization suite (`manage.py test accounts organizations donations donation_requests pickups notifications qa_tests --noinput`) | Passed: 97 tests run, 2 skipped, 0 failures. The skipped concurrent-allocation and concurrent-pickup tests require database row-lock support (`select_for_update`), which SQLite does not provide. |
| Frontend `npm run lint` | Passed |
| Frontend `npm run build` | Passed (Vite production build) |
| Browser/manual route and responsive verification | Not run; no browser page was shared and no app session was launched |
| Frontend automated unit/E2E tests | Not available in the package scripts |

## Immediate priorities

1. Stop disclosing full donor pickup addresses during broad browse; test field visibility before/after approval.
2. Make production security settings fail closed rather than relying on local defaults.
3. Enforce donation transitions for admins as well as other users, with audited exceptional recovery if needed.
4. Record sensitive workflow events reliably and replace allocation-only impact with completed-quantity reporting.
5. Add volunteer onboarding and an authorized pickup-discovery/claim path, or explicitly scope volunteers out of the first release.

The consolidated comparison and phase-by-phase plan are in [shareharvest-benchmark-and-roadmap.md](./shareharvest-benchmark-and-roadmap.md). This audit is the current evidence source; older UI notes should not override it.
