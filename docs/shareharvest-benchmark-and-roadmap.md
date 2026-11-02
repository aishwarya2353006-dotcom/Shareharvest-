# ShareHarvest Platform Comparison and Development Roadmap

**Prepared:** 2026-10-26  
**Companion evidence report:** [ShareHarvest Project Audit](./shareharvest-project-audit.md)

This is a product/workflow comparison, not a feature-by-feature teardown of competitors’ authenticated applications. It uses public official pages and only claims what those pages describe. No competitor code, assets, branding, or proprietary copy should be reused.

## Platform comparison

| Platform | Publicly described workflow | Relevant ShareHarvest capability | Gap / product opportunity |
|---|---|---|---|
| [Food Rescue US](https://foodrescue.us/volunteer) | Its public volunteer story describes volunteers opening the app, seeing rescues scheduled for a future time, and choosing one they can pick up; volunteers deliver rescued food to a community agency. The exact complete donor/agency permission flow was not publicly verified here. | ShareHarvest can create and schedule pickups, assign volunteers, and let an already-assigned volunteer update progress. | Volunteers cannot browse or claim unassigned pickups; the current registration flow does not onboard volunteers. Add controlled self-claim or explicit assignment, with capacity/eligibility and pickup-claim concurrency rules. |
| [OLIO](https://olioapp.com/en/) | Its public homepage describes a Food Waste Hero volunteering to collect surplus food from local businesses and share it with nearby people; it also describes neighbor-to-neighbor free sharing. Detailed in-app assignment, safety training, and allergen flows were not independently verified from this public page. | ShareHarvest has organization-based donations, recipient requests, allocation, and pickup coordination. | ShareHarvest is currently a structured organization-to-organization workflow, not an open neighborhood-sharing marketplace. Choose and clearly communicate that scope before adding consumer-to-consumer listings. Add location-aware discovery and food-safety/allergen details before widening access. |
| [MealConnect](https://mealconnect.org/how-it-works) | Its official workflow says donors post a donation with a photo, basic information, and preferred pickup time; the donation is sent to a trusted nonprofit for review/acceptance; the local pantry/program schedules pickup and provides a volunteer. The page also points to food-safety guidance and describes vetting/audits for nonprofit partners. | ShareHarvest has donation availability windows, verified organizations, recipient requests/approvals, allocations, assigned pickups, and actual pickup quantities. | Add photos and safety information; clarify whether the donor, receiving agency, or volunteer schedules pickup; improve verified-partner trust cues; provide a complete city/area discovery flow. Do not expose a donor’s exact address before the appropriate handoff. |
| IFSA (named in the audit brief) | A reliable public official product page and donor-registration workflow could not be independently confirmed during this review. A prior public-page review described a structured food-sharing initiative and registration of surplus-food distribution agencies, but the donor registration page exposed too little detail to verify the steps. | ShareHarvest supports organization registration, organization membership, and platform-admin verification. | Treat the comparison as unverified, not as a feature specification. Confirm the exact IFSA organization/URL and its current public or partner onboarding flow before using it as a product benchmark. |

### What the comparison implies

1. Establish ShareHarvest’s first-release audience as verified organizations and their staff, rather than trying to combine a nonprofit donation network and an unrestricted neighborhood marketplace.
2. Make the chain of custody explicit: donor post → verified recipient review/request → allocation → named pickup owner → completion with actual quantity.
3. Use privacy-safe local discovery. City/area can support matching; exact pickup details should be limited to authorized participants at the right workflow stage.
4. Treat safe handling, allergens, storage conditions, collection deadlines, and traceability as operational requirements—not decorative listing enhancements.
5. Keep assignment, cancellation, and partial-fulfillment behavior transparent and auditable. Avoid reporting requested or allocated food as delivered impact.

## Existing implementation baseline

The current product already has real donor and recipient API flows, organization verification, requests/allocations, pickup management, and request/pickup notifications. It has session/CSRF authentication and role-specific route guards. The main gaps are not a lack of all functionality; they are address privacy, production-safe defaults, incomplete lifecycle policy, absent volunteer discovery/onboarding, food-safety/discovery data, and missing impact/audit UI.

Do not treat the roadmap as authorization to replace the existing frontend or rewrite the backend. Each phase should preserve working API contracts where practical and add focused tests before expanding the workflow. The audit’s findings and verification limits are in [shareharvest-project-audit.md](./shareharvest-project-audit.md).

## Prioritized phased roadmap

Effort is relative (`S` = a few focused days, `M` = several days to roughly two weeks, `L` = multiple weeks or an infrastructure/product decision); it is not a delivery estimate.

| Phase / priority | Outcome and scope | Main dependencies | Acceptance criteria | Effort |
|---|---|---|---|---|
| **0 — Evidence and baseline (complete)** | Record actual routes, APIs, roles, data states, tests, known risks, and explicit unknowns. Keep the existing SQLite database and migrations intact. | None | Audit and this roadmap match inspected code; no unperformed browser checks are reported as passing; the existing rejection defect has a regression test. | Complete |
| **1 — Privacy and production security (P0)** | Split public browse fields from authorized pickup details; make production configuration fail closed; enforce the donation transition matrix for admins; align password-change/session behavior; set a documented CSRF/CORS/HTTPS/cookie policy. | Phase 0 | API tests prove precise address/instructions are absent from general browse and available only at the authorized workflow stage; no role can perform invalid transitions; production settings reject a missing/default secret and debug mode; password-change behavior matches UI. | M |
| **2 — Auditable end-to-end fulfillment (P0)** | Specify request cancellation/partial approval, allocation reversal, pickup failure/no-show/retry, and donation closure rules. Record actor/timestamp changes for organization, donation, request/allocation, and pickup transitions. Ensure completion and quantity accounting agree. | Phase 1 | State-transition and permission matrix is covered by API tests; history is persisted atomically and cannot be changed through ordinary APIs; completed pickup actual quantity is authoritative; failed/cancelled pickup does not count as delivered; reopen/override policy is explicit and audited. | M–L |
| **3 — Safe local discovery (P1)** | Add server-side city/area filters, clear availability windows, listing photo support, and minimum food-safety fields (food type/condition, use-by or collection deadline, storage/temperature notes as applicable, allergens/handling notes). | Phases 1–2; final safety policy decision | Search is server-filtered and pagination-safe; a recipient can distinguish location area from exact address; required safety fields validate; image type/size are constrained; stale/unavailable offers cannot be requested; tests cover privacy, validation, and expired listings. | M–L |
| **4 — Volunteer onboarding and pickup ownership (P1)** | Add a safe invitation/approval path for volunteer accounts, and explicit assignment or eligible open-task claim. Avoid public self-registration as a privileged volunteer unless an approval policy is selected. | Phases 1–2; task eligibility and claim policy | Volunteer can only see eligible nearby/scheduled tasks; claim is atomic and cannot double-assign under concurrent requests on the production database; only assigned volunteer/authorized organization can update progress; onboarding does not grant admin permissions. | M |
| **5 — Role dashboards and truthful impact (P1)** | Build a recipient/volunteer/admin operations overview and connect the existing impact API to a UI only after semantics are corrected. Separate published, requested, allocated, picked-up, and delivered totals; label units and date range. | Phases 2–4 | Each metric is derived from the corresponding state and unit; delivered totals include completed pickups only; dashboard permissions and empty/error/loading states are tested; the audit/operations page exposes only authorized fields. | M |
| **6 — Consistent, accessible application UI (P2)** | Consolidate internal typography, spacing, focus, contrast, status/action patterns, and responsive navigation using the existing tokens and shared components. Remove misleading links and align labels with real actions; avoid a blanket re-theme. | Phases 1–5 stabilize interactions | Keyboard-only flow can complete the main donor, recipient, volunteer, and admin journeys; focus is visible and trapped/released correctly where needed; text/controls meet the chosen accessibility contrast and sizing baseline; direct URLs and mobile menu are manually tested. | M |
| **7 — Notifications and operational automation (P2)** | Add organization verification outcomes, request decision, pickup reminder, reassignment, failure, and completion notifications; configure a managed scheduler for donation expiry and reminders; provide delivery/retry observability. | Phases 2–4; deployment environment and email/SMS decision | Each event has one documented recipient policy; retries do not duplicate user-visible events; expired items stop appearing; task/scheduler health is observable; no message leaks the exact address to an unauthorized recipient. | M |
| **8 — Release, deployment, and resilience (P0 release gate)** | Choose production database/host, secure environment and secrets, backups/retention, static/media storage, monitoring, rate limits, deployment checks, and recovery process. Add frontend/API integration and browser coverage. | Phases 1–7; deployment decisions | CI runs backend tests on the production database engine and frontend lint/build; browser smoke tests cover login, primary role journeys, denied permissions, session expiry, and mobile navigation; migration/backup restore are rehearsed; deployment has HTTPS, secure cookies, no dev secret/debug, and tested rollback. | L |

Phases 1 and 2 are the first engineering batch. Phase 3 and volunteer self-service (Phase 4) can be sequenced based on the launch market and operations policy, but neither should weaken Phase 1’s privacy boundary. UI polish is intentionally after core behavior so that the design standardizes real actions rather than mock screens.

## Smallest safe MVP

**MVP audience:** verified donor and recipient organizations, their authorized members, one platform administrator, and explicitly invited/assigned volunteers. Do not include an open consumer-to-consumer marketplace in this MVP.

The minimum end-to-end scenario is:

1. A donor organization creates a listing with accurate quantity/unit, availability, collection deadline, city/area, and required safety/allergen notes.
2. A verified recipient organization browses only currently available local listings. It cannot see the exact pickup address or private instructions yet.
3. A recipient submits a quantity-bounded request; the donor approves or rejects it. Duplicate and concurrent approvals cannot over-allocate stock.
4. The authorized organization assigns an invited volunteer or schedules a named pickup owner. Exact collection details become visible only to authorized participants.
5. The pickup owner records a completed quantity or a failure/no-show. The allocation, listing availability, notifications, audit event, and delivered-impact total remain consistent.
6. The organization/admin can inspect the complete history and correct only through an explicit, audited recovery action.

**MVP release gate:** Phase 1 privacy/configuration fixes and Phase 2 lifecycle/audit rules are required; Phase 3’s minimum safety/area fields and Phase 4’s safe volunteer assignment/onboarding are required if volunteers participate. Phase 5 needs only a small truthful delivered-quantity view, not a full analytics suite. Phase 6 needs accessibility and responsive checks for the core flows, not a complete visual redesign. Phase 7 reminders and Phase 8 deployment/recovery gates are required before a public production release.

**Defer:** route optimization, live maps/GPS, recurring donations, automated matching/AI, payments/monetization, social feeds, consumer-to-consumer sharing, native mobile applications, external food-bank integrations, and advanced impact exports.

## Exact next development task

**Add a browse-safe donation serializer that omits `pickup_address` and `pickup_instructions` from recipient browse responses.** Add focused API tests proving (a) a recipient cannot obtain either field from general browse/list or detail endpoints before authorization, and (b) the donor and the authorized participants in the approved pickup workflow retain the information they need. Do not change the SQLite database or migrations for this task.

This is the smallest high-impact step because it closes a concrete privacy exposure without requiring product-policy decisions or a broad workflow rewrite. After it passes, continue Phase 1 with production fail-closed settings and admin transition enforcement.
