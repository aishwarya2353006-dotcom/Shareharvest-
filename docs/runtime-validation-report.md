# Runtime Validation Report

**Generated**: 2026-10-23  
**Target**: `D:\share_harvest`

## Summary

| Step | Status | Exit Code | Details |
|------|--------|-----------|---------|
| Startup | PASS | n/a | Isolated Django backend on port 8002 and Vite frontend on port 5176 started; frontend returned HTTP 200. |
| Integration Tests | PASS | 0 | Django suite: 75 tests, 73 passed, 2 skipped; skips are row-lock concurrency tests unavailable on SQLite. |
| Frontend Build and Lint | PASS | 0 | `npm run build` and `npm run lint` completed successfully. |
| Browser E2E | PARTIAL | n/a | Core scheduling, volunteer progress/failure, recipient refresh, and completion flows passed; rescheduling/cancellation/no-show and mobile viewport were not tested. |

**Overall**: NEEDS_SIGNOFF — PostgreSQL row-lock concurrency remains unverified.

## Defect Found and Fixed

The first browser scheduling attempt returned HTTP 500 because pickup creation invoked the out-of-scope Notifications subsystem, whose model expected a database column absent from its migrations. Pickup actions were decoupled from Notifications, and regression coverage now verifies pickup scheduling succeeds without creating notification records. No Notifications migration or unrelated feature work was added.

## Environment

- Docker: unavailable (`docker` command not found).
- Node.js: available, `v24.11.1`.
- Browser: integrated Playwright browser tool available and used against the running application.
- Database: isolated SQLite QA database at `C:\Users\Academytraining\.copilot\session-state\48c051ac-8a77-4923-b394-58d1b5e2e5c8\files\shareharvest-phase3-qa.sqlite3`; it is separate from `backend\db.sqlite3`.
- Backend Django system check: passed.
- Pickup migration drift check: passed (`No changes detected in app 'pickups'`).

## Browser Evidence

| Check | Result | Evidence |
|---|---|---|
| Donor login/logout and recipient login with separate accounts | PASS | Both auth requests returned HTTP 200. |
| Schedule a pickup | PASS | API response through browser: HTTP 201. |
| Assign volunteer and start pickup | PASS | Requests returned HTTP 200. |
| Report failed pickup and refresh recipient view | PASS | Failure returned HTTP 200; status and reason remained visible after re-login/navigation. |
| Completed pickup and actual quantity | PASS | Earlier browser flow completed 4.25 kg against a 5 kg allocation. |
| Persisted failed pickup relationships and quantities | PASS | One pickup linked to the expected allocation/request/donation; approved quantity 4 kg, actual quantity unset, allocation and donation quantities unchanged. |
| Rescheduling, cancellation, and no-show controls | NOT TESTED | No browser execution evidence for these actions. |
| Browser viewport at mobile size | NOT TESTED | No mobile viewport evidence recorded. |
| Browser console/network for final flow | PASS, LIMITED | React Router future-flag warnings only; no app runtime errors observed. A comprehensive failed-network-request audit was not recorded. |

## Integration and Integrity Evidence

- Full backend test command: `python manage.py test` — exit code 0; 75 tests, 73 passed, 2 skipped.
- Focused pickup and notification-boundary command: `python manage.py test notifications.tests.NotificationApiAndEventsTests.test_pickup_create_api_does_not_create_out_of_scope_notifications pickups` — exit code 0; 17 tests, 16 passed, 1 skipped.
- Frontend commands: `npm run build` and `npm run lint` — both exit code 0.
- SQLite cannot verify PostgreSQL row-lock behavior. The pickup scheduling concurrency test and an existing donation-request concurrency test were skipped because this database does not support `select_for_update`.

## Authorization and Boundary Evidence

- Backend pickup tests exercised scoped list/detail access, scheduling authorization, volunteer assignment eligibility, and lifecycle permissions; the full backend test suite passed.
- No separate browser execution was recorded for unrelated-user access, rescheduling/cancellation/no-show authorization, malformed quantities, or concurrent API submissions. These are not claimed as browser-tested in this report.
- The database uniqueness constraint and application checks cover one pickup per allocation. PostgreSQL behavior under simultaneous requests remains unverified in this environment.

## Files Changed

- Backend pickup implementation and coverage: `backend/pickups/models.py`, `serializers.py`, `views.py`, `urls.py`, `tests.py`, and migrations `0002_pickup_integrity.py` and `0003_remove_pickup_pickup_status_timestamp_consistency_and_more.py`.
- Notifications test: `backend/notifications/tests.py` now asserts pickup creation does not create out-of-scope notifications.
- Frontend: `frontend/src/services/pickupApi.js`, `frontend/src/pages/pickups/PickupsPage.jsx`, `frontend/src/App.jsx`, `frontend/src/components/Sidebar.jsx`, `frontend/src/layouts/MainLayout.jsx`, `frontend/src/pages/auth/LoginPage.jsx`, `frontend/src/pages/recipient/MyRequestsPage.jsx`, and `frontend/src/styles/main.css`.
- Documentation: `README.md`, `docs/api-design.md`, `docs/data-models.md`, and this report.

## Gaps and Follow-up

- Run the row-lock concurrency tests against PostgreSQL before claiming production concurrency verification.
- Browser verification covered the successful completion and failure paths; rescheduling, cancellation, and no-show actions were not separately exercised in the browser.
- Notifications and Impact Reporting remain out of scope. Pickup creation intentionally does not invoke the existing Notifications subsystem.

## Verdict

```text
environment:
  docker: UNAVAILABLE — docker command not found
  node: AVAILABLE — v24.11.1
  playwright: AVAILABLE — integrated browser tool executed the application workflows
  infra-tier: FALLBACK(embedded/in-memory) — isolated SQLite; Docker unavailable
  browser-tier: PRIMARY(Playwright) — browser rendering and interactions exercised
startup: PASS — isolated Django and Vite servers; UI loaded and authenticated API requests succeeded; startup time not recorded
integration: PASS — exit_code: 0, passed: 73, failed: 0, skipped: 2; full Django suite; PostgreSQL row-lock semantics not covered
e2e: PARTIAL — browser tool flows succeeded; donor schedule, volunteer assignment/start/failure, recipient status refresh, and completed pickup flow; rescheduling/cancellation/no-show and mobile viewport not tested
overall: NEEDS_SIGNOFF — PostgreSQL row-lock concurrency remains unverified
```
