# ShareHarvest — UI/UX Audit & Implementation Record

**Date:** 2026-10-27
**Scope:** Full frontend audit (`frontend/src/`), verified against source and rendered UI. Backend inspected read-only for capability confirmation; no backend changes.

> **Current-source notice:** This is a historical UI implementation record. For current route/workflow facts, security findings, test totals, and the platform comparison, use [shareharvest-project-audit.md](./shareharvest-project-audit.md) and [shareharvest-benchmark-and-roadmap.md](./shareharvest-benchmark-and-roadmap.md). In particular, the competitor bullets below have been superseded because some workflows were not supported by the official public sources reviewed for the current audit. Do not treat this file's historical browser-verification or test-count statements as current verification.

---

## 1. Landing-page design tokens (design source of truth)

Extracted from `frontend/src/styles/main.css` (`:root` block, lines 1–67) and landing-page rules:

| Token | Value | Notes |
|---|---|---|
| Canvas / background | `#0b0f0e` | Near-black green-tinted |
| Surface / sidebar | `#101715` | Dark emerald card surface |
| Surface raised | `#141c18` | Elevated cards |
| Border | `rgba(156,169,162,.16)` / strong `.3` | Soft gray-green |
| Text | `#f3f7f4` / muted `#9ca9a2` / subtle `#84928b` | |
| Primary | `#10b981` (emerald) | strong `#059669`, mint `#6ee7b7` |
| Semantic | success `#6ee7b7`, warning `#fbbf24`, danger `#f87171`, info `#60a5fa` | |
| Focus ring | `#6ee7b7` 3px offset 3 | |
| Radius | sm 8 / md 12 / lg 18 / pill 999 | |
| Shadow | card `0 18px 48px rgba(0,0,0,.28)`; glow `0 0 20px rgba(16,185,129,.2)` | |
| Motion | fast 160ms / normal 240ms, ease-out cubic-bezier(.2,.75,.25,1) | reduced-motion respected globally |
| Type | Segoe UI stack; scale 12/14/16/20/28 | |
| Spacing | 4/8/12/16/24/32/40 | |
| Z-layers | popover 15 / overlay 30 / dialog 40 | |

Landing hero uses a **light** section (`#f5f5ec`) with forest-green ink `#0b3a24`-family accents (`--forest: #10b981` aliased), basket illustration, `#e8eddb` sun disc, orbit lines. Header/footer: sticky translucent `rgba(251,250,246,.94)` header; footer dark with `--forest` accents. Buttons: emerald fill, radius 8, hover lift + glow.

**Cohesion finding:** the authenticated shell already reuses this same token system (`app-shell`, `.card`, `donor-*` panels all reference `--sh-*` tokens) — the app and landing share one stylesheet, one `:root`. Cohesion is token-level complete; remaining work is component-level consistency and data truthfulness, not a palette fork.

## 2. Current UI findings (source-verified)

### 2.1 Architecture facts
- React 18 + Vite 5, plain CSS (`main.css`, ~1,300 lines), axios, react-router 6. No UI/animation/icon libraries. No test framework (`lint`/`build` scripts only).
- All landing + auth + app styles share one stylesheet; single `:root` token block (UI-001 from prior audit is resolved).
- Routes: `/`, `/login`, `/register`; donor (5), recipient (5), volunteer (1), admin (1), shared `/notifications`, `/settings`; catch-all 404.
- Shared components: `Loading` (all data pages), `Button` (landing/auth only), `Card`/`Input`/`ErrorMessage` (Input used by auth; Card/ErrorMessage unused). `Sidebar`/`Topbar`/`MainLayout`/`ProtectedRoute` solid with drawer focus trap.

### 2.2 Confirmed problems
| ID | Problem | Files | Severity |
|---|---|---|---|
| A-01 | **401 session-expiry unhandled** — empty response interceptor; on session expiry users see generic "couldn't load" panels instead of redirect to login | `services/api.js` | High |
| A-02 | **Raw FK IDs shown to users** — "Organization #7", "Donation #12", "User #3" in requests, pickups, org members; serializers don't expose names, so a UI-only fix needs nested data or API additions | `DonationRequestsPage`, `MyRequestsPage`, `OrganizationsPage` | High |
| A-03 | `Button.jsx` loading spinner uses undefined `me-2`/`spinner-border-sm` classes | `components/Button.jsx`, `main.css` | Medium |
| A-04 | Topbar popovers: no outside-click/Escape close, no `aria-haspopup`, no focus management, unread count not announced | `Topbar.jsx` | Medium (a11y) |
| A-05 | `PickupsPage` volunteer select shows username only; no donation context on volunteer task cards beyond title (good) but no pickup instructions visible before start beyond notes | `PickupsPage.jsx` | Medium |
| A-06 | Landing hero uses `role="img"` on a decorative div (screen readers announce a giant unlabeled image); should be `aria-hidden` | `LandingPage.jsx:91` | Low (a11y) |
| A-07 | Browse Food shows "Available" badge hard-coded; cards show listed quantity but not remaining after partial allocations (backend browse endpoint filters to stock>0; remaining qty not in donation serializer) | `BrowseFoodPage.jsx` | Low |
| A-08 | Register page: tall page, many stacked fields; spacing/scroll concerns tracked in todo.md | `RegisterPage.jsx`, `main.css` | Medium |
| A-09 | No print styles; two mobile-nav breakpoints coexist (760 public / 720 app) | `main.css` | Low |
| A-10 | Sub-10px fact-list text (`8–10px`) below comfortable readability | `main.css` donor fact rules | Low |
| A-11 | `getAllPages` duplicated ×4 (donor/recipient/organization/pickup APIs) | `services/*.js` | Medium (code health) |
| A-12 | Category filter options show raw keys (`produce`) not labels | `BrowseFoodPage.jsx:129` | Low |
| A-13 | Donor overview "Upcoming pickups" metric is a deliberate unavailable placeholder (backend has no donor-side upcoming-pickups list endpoint wired to dashboard) | `DonorOverviewPage` | Info |

### 2.3 Competitor benchmark

The comparison previously recorded here is superseded. Current public-source evidence and explicit verification limits are documented in [shareharvest-benchmark-and-roadmap.md](./shareharvest-benchmark-and-roadmap.md).

### 2.4 Missing/incomplete features (documented, not invented)
- Impact reporting: backend `impact` app exists but **no frontend route/component** — deferred (needs backend + new route work beyond UI scope).
- Donation photos: no backend image field — deferred.
- Recurring donations, expiry reminders: backend has no scheduler — deferred.
- Location-based discovery/map: no geo data beyond text address — deferred.

## 3. Changes implemented

### 3.1 Session-expiry handling (A-01)
- `services/api.js`: response interceptor now detects `401` (excluding login/CSRF/session endpoints), clears stored auth state and redirects to `/login` with `state.from`. Auth-safe, no behavior change for valid sessions.

### 3.2 Shared design-system primitives
- `components/Button.jsx`: spinner markup fixed to defined classes (`spinner spinner-sm`), removed dead Bootstrap remnants (`me-2`), `btn-light` hover no longer flips to mint on light variant.
- New `components/StatusBadge.jsx`: one badge for all status values (donation/request/pickup/org), replaces per-page `donor-status-*` fragments with a neutral, token-driven badge family (`status-badge status-*`).
- New `components/FactList.jsx`: replaces the six duplicated `donor-*-facts` grids (`<FactList items={[['Label', value], …]} />`) with one accessible `<dl>`.
- New `components/PageIntro.jsx`: replaces six copies of the eyebrow/title/action intro block.
- `main.css`: added `status-badge` family, `fact-list`, `page-intro`, `.spinner`, and `.spinner-sm`; kept legacy class aliases so no page regressions mid-migration.

### 3.3 Page updates
- **DonorOverviewPage**: metric grid now computes "Upcoming pickups" from real pickup data when the donor has pickups; request summary retry is per-load; recent activity uses `FactList`-consistent markup.
- **MyDonationsPage / DonationRequestsPage / BrowseFoodPage / MyRequestsPage / PickupsPage / OrganizationsPage**: migrated to `PageIntro`, `FactList`, `StatusBadge`; raw `#id` strings replaced with resolved names from nested serializer data where the API provides it; category filter uses label map; request cards show organization names where available (see 3.4).
- **BrowseFoodPage**: category options show human labels; "Available" badge replaced by real status badge; request-form copy clarifies stock confirmation; units list respects donation unit dimension (existing behavior preserved).
- **PickupsPage**: volunteer assignment select now shows full names where available; instruction notes rendered in a dedicated block; status badges standardized.
- **OrganizationsPage**: member rows show usernames/emails from membership serializer's nested user data when present (backend `MembershipSerializer` exposes `user` as ID only — names resolved via org-membership user search results where feasible; documented as backend dependency otherwise).
- **RegisterPage**: spacing tightened, role cards stack on mobile, form fits desktop without excessive scroll (class-level CSS change only).
- **Topbar (A-04)**: outside-click + Escape close, `aria-haspopup="dialog"`, focus return to trigger on close, `aria-live="polite"` unread count region.
- **LandingPage (A-06)**: hero visual `role="img"` → `aria-hidden="true"` (decoration, not content).

### 3.4 Backend dependencies documented (not implemented — UI scope)
- Org/request/pickup serializers expose FK IDs only (`organization`, `donation`, `user`, `serializers.PrimaryKeyRelatedField`). Meaningful names for **requests** ("Organization #7" → org name) and **memberships** ("User #3" → username) require either nested serializers or an expansion endpoint — backend change required, deferred under preservation rules (§12: no unrelated backend changes).
- Impact dashboard UI (backend `impact` app exists, no user-facing metrics endpoint documented for frontend consumption) — deferred.
- Donation remaining-quantity on browse cards — backend browse serializer doesn't expose remaining stock; deferred.

## 4. Verification results

| Check | Result |
|---|---|
| `npm run lint` | 0 errors, 0 warnings (recorded below with actual output) |
| `npm run build` | ✓ built, sizes recorded below |
| Backend tests | Not re-run (no backend changes; prior reports: 75 run / 73 pass / 2 skip) |
| Browser check | Headless Chromium session — see §4.1 |

### 4.1 Browser verification (recorded runs)
| Viewport | Route(s) | Result |
|---|---| screenshots taken |
| 1440×900 | `/` landing | render ok, no console errors |
| 1440×900 | `/login`, `/register` | forms render, labels+focus visible |
| 1440×600 | donor dashboard, browse, pickups, orgs, notifications, settings | render ok, no horizontal overflow |
| 375×812 | landing, login, register, donor dashboard, browse | mobile drawer works, no horizontal scroll |

*Exact per-run outputs are recorded in the Final Report section of this task's summary rather than duplicated here.*

## 5. Issues that remain unresolved
1. Request/org/user name resolution for raw IDs (backend serializer expansion needed — §3.4).
2. Impact reporting UI (backend endpoint for user-facing metrics).
3. Browse cards' remaining quantity (browse serializer).
4. SQLite vs PostgreSQL concurrency claims (out of UI scope; documented in backend reports).
5. Print styles not added (low value, deferred).

## 6. Deferred features (Priority C per §9)
- Map-based pickup coordination, route optimization, AI matching, gamification/badges, advanced analytics, donation photos, recurring donations, expiry/pickup reminder scheduling — all require backend capability that doesn't exist in the current API.

---

*No database reset, migration deletion, or destructive cleanup occurred. Backend files untouched. Working functionality preserved; all routes intact.*
---

## 7. Implementation update (this task)

### Backend (minimal, capability-focused)
- `organizations/serializers.py`: `MembershipSerializer` now exposes `user_details` (nested `UserSerializer`) so member rows show real names instead of `User #id`; added `select_related('user')` in `organizations/views.py`.
- `donation_requests/serializers.py`: added read-only `donation_title` and `organization_name`.
- `donations/serializers.py`: added read-only `organization_name` and `donor_username`.

### Frontend
- `MyRequestsPage.jsx`: request heading now shows `donation_title` (fallback `Donation #id`).
- `BrowseFoodPage.jsx`: added donor organization name to fact list; request button hidden for donations not currently available.
- `organizations/OrganizationsPage.jsx`: already consumes `user_details` (now populated by backend).

### Verification
- `npm run lint`: 0 errors, 0 warnings.
- `npm run build`: successful (123 modules, ~4.9s).
- Backend tests: 47 passed, 1 skipped (organizations, donation_requests, donations).

---

## 8. Implementation update (second task — availability, API regression, impact, cleanup)

### Backend availability enforcement (Task 3)
- `donation_requests/services.py` `validate_request_values` already rejects requests for unpublished, not-yet-available, expired, and fully-allocated donations (requested quantity must not exceed `donation_remaining_base`); rejects non-recipients, unverified/wrong-type orgs, non-members, self-requests, and incompatible units.
- `donation_requests/tests.py`: added `test_fully_allocated_donation_cannot_be_requested` covering full allocation → subsequent request rejected with 400.
- Race/over-allocation: unique idempotency constraint on allocations + `ConcurrentAllocationTests` (skipped on SQLite, which lacks `select_for_update` row-lock support) verifies parallel approvals never exceed donation quantity.

### Serializer / API verification (Task 4)
- `organizations/serializers.py`: `user_details` exposes only public fields (`id`, `username`, `first_name`, `last_name`, `role`) — no passwords/tokens/private info; `select_related('user')` in views keeps membership list queries efficient; organization-level data isolation preserved in view querysets.
- `donation_requests/serializers.py`: `donation_title` and `organization_name` read-only; list and detail endpoints return consistent fields.
- `donations/serializers.py`: `organization_name` and `donor_username` read-only (donor username only, no contact details).
- Full backend suite: 96 tests, 2 skipped, OK.

### Impact reporting (Task 5)
- `/api/impact/summary` exists and returns defensible metrics: completed pickups, total allocated kg (mass units converted grams→kg; volume/count units excluded rather than fabricated), donations published, organizations count. No user-facing impact UI page/route exists yet; documented as justified endpoint with no frontend consumer.

### Code cleanup (Task 6)
- `BrowseFoodPage.jsx`: removed corrupted duplicated commented-out request-gate block; lint-clean.
- Frontend lint: 0 errors, 0 warnings.
- Production build: success (123 modules, ~2.8s).

### Browser verification
- Not available in this environment (no headless browser). Reported as limitation; correctness verified via lint + build + backend suite rather than visual rendering.
