# ShareHarvest — Frontend UI Improvement Audit

**Date:** 2026-10-26
**Scope:** `frontend/` only (React 18 + Vite 5, plain CSS, axios). No code changes were made in this task; no browser testing was performed, so all runtime/layout claims below are **source-verified** and items requiring visual confirmation are explicitly marked **SUSPECTED**.
**Sources inspected:** all 34 files under `frontend/src/`, `frontend/package.json`, route map in `App.jsx`, full `main.css` (1,326 lines).

> **Current-source notice:** This is a historical frontend-only review. Current route, workflow, backend, and verification findings are in [shareharvest-project-audit.md](./shareharvest-project-audit.md); the current product comparison and roadmap are in [shareharvest-benchmark-and-roadmap.md](./shareharvest-benchmark-and-roadmap.md). Treat the findings below as observations from the date and source snapshot stated here, not as current runtime verification.

---

## 0. Environment facts (verified)

### package.json capabilities
| Category | Status |
|---|---|
| Styling libraries | **None** — one hand-rolled stylesheet (`src/styles/main.css`), no Tailwind/CSS-modules/styled-components |
| Animation libraries | **None** — all animation is CSS keyframes/transitions (`sh-wave-drift`, `sh-mesh-pulse`, `spinner-border`) |
| Icon libraries | **None** — inline SVGs + Unicode glyphs (`⌂ ▤ ↗ ▣ ◉ ⌕ ◌`) |
| Testing libraries | **None** — no vitest/jest/react-testing-library; `lint` script exists, no `test` script |
| Runtime deps | react 18.2, react-dom 18.2, react-router-dom 6.22, axios 1.6 |

### Route map (must remain functional — verified in `App.jsx`)
- Public: `/`, `/login`, `/register`, catch-all `*` → inline 404
- Donor: `/donor/dashboard`, `/donor/donations`, `/donor/requests`, `/donor/pickups`, `/donor/organizations`
- Recipient: `/recipient/dashboard`, `/recipient/browse`, `/recipient/requests`, `/recipient/pickups`, `/recipient/organizations`
- Volunteer: `/volunteer/pickups`; Admin: `/admin/organizations`; All roles: `/notifications`

### Shared components actually used by pages
| Component | Used by | Note |
|---|---|---|
| `Loading.jsx` | all data pages | only shared component in active use besides layout pieces |
| `Button.jsx` | **LandingPage only** | uses `me-2` Bootstrap class that has no CSS definition |
| `Card.jsx` | **unused** (0 imports) | styles `.card` exist but pages never use it |
| `Input.jsx` | **unused** (0 imports) | pages hand-roll `<label className="donor-field">` |
| `ErrorMessage.jsx` | **unused** (0 imports) | pages use `donor-inline-error`/`donor-form-error` divs |
| `Sidebar.jsx`, `Topbar.jsx`, `MainLayout.jsx`, `ProtectedRoute.jsx` | all authenticated routes | solid, keyboard-trap-safe mobile drawer |

### API integration surface (must not break)
- `services/api.js`: axios instance `baseURL: '/api'`, `withCredentials: true`, CSRF interceptor fetching `/accounts/csrf_token/` for unsafe methods.
- `donorApi.js` / `recipientApi.js` / `organizationApi.js` each contain a **duplicated private `getAllPages()` paginator** (identical logic, 3 copies).
- Notification APIs are separate (`notificationApi.js`) with a `NotificationsContext` providing `unreadCount`.
- Quantity-unit math (`QUANTITY_UNITS`, base-unit conversion) lives in `donorApi.js` and is imported cross-role by `BrowseFoodPage.jsx` — a hidden donor↔recipient coupling.

---

## 1. Confirmed issues

> "Confirmed" = directly observable in source (unused/missing selectors, duplicated code, wrong class names, literal placeholders). Rendering consequences are still labeled below.

### UI-001 — Two conflicting design systems in one stylesheet (Critical)
- **File:** `frontend/src/styles/main.css` (entire file; pivotal points: lines 1–55 vs 936–965)
- **Status:** Resolved — token definitions are consolidated into one `:root` block using the dark emerald values.
- **Current behavior:** The application uses a dark emerald theme (`color-scheme: dark`, dark canvas/surfaces, light text, emerald accents). Earlier light-theme token values conflicted with a later dark emerald `:root` block; the duplicate block has been removed and its canonical values are now defined once at the top of the stylesheet. Component-level declarations and phase overrides remain outside this token-only change.
- **Impact:** The duplicate token source of truth and conflicting light/dark token aliases are resolved. This does not consolidate unrelated component styles or phase overrides.
- **Verification:** `frontend/src/styles/main.css` contains one `:root` token block; lint and production build pass. Visual verification was not performed.
- **Priority:** Critical
- **Dependencies:** none (do first; everything else builds on it)
- **Verification:** `grep -c ':root' main.css` = 1; visually re-check Landing, Login, Donor dashboard against current screenshots.

### UI-002 — Heading hierarchy is inconsistent and semantically wrong (High)
- **Files:** `DonorOverviewPage.jsx` (lines 75, 82, 93: `h2` inside sections whose page `h1` comes from `MainLayout.jsx:99`), `MyDonationsPage.jsx` (intro uses `h2` at line 163 while `MainLayout` already renders `h1`), `DonationRequestsPage.jsx` (same pattern, line 134), `BrowseFoodPage.jsx` (line 126), `MyRequestsPage.jsx` (line 43), `PickupsPage.jsx` (line 382), `OrganizationsPage.jsx` (line 218), `RecipientOverviewPage.jsx` (h2 only, line 7), `NotificationsPage.jsx` (h2 only, line 68)
- **Current behavior:** `MainLayout` renders the page `h1` from a route table, then each page repeats an eyebrow + `h2` intro block ("DONOR WORKSPACE / My Donations") that duplicates the topbar/page title. Card titles inside lists are sometimes `h3`, sometimes `h2` (`recipient-food-head h2` in `BrowseFoodPage` vs `donor-donation-title-row h3` in `MyDonationsPage` for the same kind of item). `RecipientOverviewPage` and `NotificationsPage` have **no h1** of their own (the layout's h1 serves, but the card headings skip levels: h2 inside a section, then h3 in cards).
- **Impact:** screen-reader users get a jumbled outline; two visible "page titles" appear back-to-back (layout h1 + page h2), which reads as duplicated headers.
- **Recommended improvement:** Remove the per-page intro `h2` (or demote the layout's block to breadcrumb-only) and standardize card titles to `h3`. Keep the visual design identical via CSS.
- **Priority:** High
- **Dependencies:** after UI-001 (CSS consolidation) to avoid fighting overrides.
- **Verification:** run an outline audit (e.g., axe DevTools / HTML5 outline) on each route; confirm exactly one `h1` and consistent card level.

### UI-003 — Duplicated page-intro markup pattern across 6 pages (Medium)
- **Files:** `MyDonationsPage.jsx:163`, `DonationRequestsPage.jsx:134`, `BrowseFoodPage.jsx:126`, `MyRequestsPage.jsx:43`, `PickupsPage.jsx:379-388`, `OrganizationsPage.jsx:218`
- **Current behavior:** identical `donor-page-intro` + `donor-eyebrow` + refresh-button block copy-pasted; even recipient pages import "donor-" prefixed classes.
- **Recommended improvement:** extract a `PageIntro` component (`eyebrow`, `title`, `description`, `action` props) and rename donor-prefixed shared classes to neutral names (`app-*`) in CSS.
- **Priority:** Medium | **Dependencies:** UI-001. **Verification:** grep `donor-page-intro` in JSX = 1 (the component).

### UI-004 — "Donor-" CSS classes used across recipient/volunteer/admin pages (Medium)
- **Files:** every recipient page, `PickupsPage.jsx` (volunteer route), `OrganizationsPage.jsx` (admin route), plus `main.css` blocks `donor-*` (lines 738–856)
- **Current behavior:** buttons (`donor-button`), fields (`donor-field`), empty panels (`donor-empty-panel`), status pills (`donor-status-*`) are shared by all roles but carry donor naming. `PickupCard` reuses `donor-request-card donor-request-facts` classes (lines 240–263).
- **Recommended improvement:** rename shared classes to role-neutral names (`app-button`, `app-field`, `status-badge`); keep old names as aliases during transition or do a single coordinated rename (all call sites are known).
- **Priority:** Medium | **Dependencies:** UI-001, UI-003. **Verification:** global grep — zero `donor-` class references outside donor pages.

### UI-005 — Dead/unused shared components and a missing CSS class (Medium)
- **Files:** `components/Button.jsx:30` (`spinner-border-sm me-2` — `me-2` has **no CSS definition** anywhere; `spinner-border-sm` also undefined, so loading buttons render a full-size spinner with no gap), `components/Card.jsx`, `components/Input.jsx`, `components/ErrorMessage.jsx` (0 imports project-wide), `main.css` `.card` block (lines 109–114) unused by pages, `.donor-donation-card-main` (referenced in `MyDonationsPage.jsx:101`) and `.pickup-list` (referenced in `PickupsPage.jsx:404`) **have no CSS rules** — they rely entirely on the parent `.donor-donation-card` / `.donor-request-list` styles, which happens to work but is accidental.
- **Recommended improvement:** either adopt Card/Input/ErrorMessage in the refactor (they are a good start) or remove them; fix Button's spinner classes to match real CSS; add explicit (or remove the phantom) `donor-donation-card-main` / `pickup-list` rules.
- **Priority:** Medium | **Dependencies:** none. **Verification:** grep each class in `main.css` after change.

### UI-006 — Status badge system is donor-named, fragmented, and incomplete (Medium)
- **Files:** `main.css` lines 771–779 + 1067–1079 (`.donor-status-*`); `PickupsPage.jsx:1228–1230` adds a second family `.pickup-status-*`; `BrowseFoodPage.jsx:54` hard-codes `donor-status-published` with the literal text "Available" regardless of actual donation state; org cards use `donor-status-${status}` where `status` can be `unknown`.
- **Current behavior:** three visually similar badge families (`donor-status-*`, `pickup-status-*`, plus ad-hoc inline classes); no styling for `draft`/`verified`/`unknown` in the light-theme block, only in the Phase-4 dark block (e.g., `.donor-status-draft` only at line 1071). Every badge has `text-transform: capitalize` + `replaceAll('_', ' ')` logic duplicated inline in each page (`MyDonationsPage:102`, `DonationRequestsPage:70`, `MyRequestsPage:8`, `PickupsPage:36`, `OrganizationsPage:93`).
- **Recommended improvement:** one `StatusBadge` component + one `status-*` CSS family with tokens for approved/pending/rejected/in-progress/unknown; delete per-page `replaceAll` duplicates.
- **Priority:** Medium | **Dependencies:** UI-001. **Verification:** render each known status (donation/request/pickup/org) in a test page or storybook-less harness; check contrast.

### UI-007 — Loading/empty/error states are functional but styled three different ways (Medium)
- **Files:** `Loading.jsx` (`.loading` full-viewport grid) wrapped by pages in `donor-panel`/`notification-state`/plain `<p role="status">` (Topbar.jsx:55); error UI: `donor-state-panel`, `donor-inline-error`, `donor-form-error`, `app-alert`, `error-message`, `notification-error` (6 variants); empty states: `donor-empty-panel`, `notification-empty`, plain paragraphs (`DonorOverviewPage:83`).
- **Recommended improvement:** consolidate to `Loading`, `ErrorState` (with retry callback), and `EmptyState` shared components; keep existing CSS hooks.
- **Priority:** Medium | **Dependencies:** UI-005 (decide component fate). **Verification:** throttle network in devtools; every page shows consistent skeleton/loading + retry.

### UI-008 — Accessibility gaps in Topbar popovers and icon buttons (Medium)
- **Files:** `Topbar.jsx` lines 43–68
- **Current behavior (source-verified):** popovers open on click but (a) **no outside-click / Escape handling** to close notification or profile popovers; (b) notification and profile popovers do not trap or return focus; (c) the notification bell button lacks `aria-haspopup`; (d) the unread count badge uses `<span aria-hidden>` (good) but the count is only in the bell's `aria-label`, not announced when it changes (no `aria-live` on the count region); (e) profile-popover has no id/`aria-controls`.
- **Also confirmed:** `Sidebar.jsx:40` correctly uses `role="dialog"` + `aria-modal` when open, and `MainLayout.jsx:34–76` implements a proper focus trap with Escape — this part is good and must be preserved.
- **Recommended improvement:** add Escape/outside-click close, `aria-haspopup="dialog"`, focus return, `aria-live="polite"` on the unread badge container.
- **Priority:** Medium | **Dependencies:** none. **Verification:** keyboard-only walkthrough: Tab into bell → open → Tab cycles → Escape closes and focus returns.

### UI-009 — Color-only / glyph-only semantics (Low–Medium)
- **Files:** `Sidebar.jsx` icons are Unicode text glyphs (`⌂ ▤ ↗ ▣ ◉`) rendered via `aria-hidden` — acceptable since labels are text, but glyph rendering varies by OS font and can look broken on Linux/Android; `BrowseFoodPage` availability is conveyed **only** by the badge; form required markers are `<b aria-hidden="true">*</b>` with no `aria-required`/visually-hidden "required" text in most fields (`MyDonationsPage:83–91`, `OrganizationsPage:222–232`); `LandingPage.jsx:91` uses `role="img"` on a decorative `div` collage — should be `aria-hidden` instead (it is pure decoration).
- **Recommended improvement:** replace text glyphs with the inline-SVG icon set already used in Topbar; add accessible required-field text; fix the hero `role="img"`.
- **Priority:** Low | **Dependencies:** none. **Verification:** screen-reader pass; contrast check of status pills (WCAG AA on dark surfaces).

### UI-010 — Typography scale is ad hoc (Low)
- **File:** `main.css` throughout (e.g., body copy at 9–12px: `.donor-metric-hint` 9px, `.donor-donation-facts span` 10px, `.app-footer` 10px, `.footer-bottom` 9px on mobile)
- **Current behavior:** no type scale; many sub-12px sizes below comfortable readability, especially fact labels (`b` at 8px, letter-spaced uppercase). Headings use a few `clamp()` rules (good) but body text does not scale at all.
- **Recommended improvement:** define `--sh-text-xs/sm/md/lg` tokens, raise sub-10px text to ≥11px, and add responsive body scaling.
- **Priority:** Low | **Dependencies:** UI-001. **Verification:** visual diff at 360px, 768px, 1280px.

### UI-011 — Buttons: three parallel button systems (Medium)
- **Files:** `main.css` `.btn` family (lines 93–104, used only by Landing/Login/Register), `.donor-button` family (752–758, 1179–1189, used by all app pages), and raw `<button>` styling in `pickup-*`/`org-*` contexts; `Button.jsx` component only used by LandingPage.
- **Current behavior:** same action ("Refresh", "Try again", "Save") can render via `.btn-secondary`, `.donor-button-secondary`, or a bare button depending on page. Hover lift (`translateY(-1px)`) exists on `donor-button`/`btn` but nothing standardizes focus/active states.
- **Recommended improvement:** converge on the `Button.jsx` component (add `variant="secondary"|"danger"`, neutral class names) and delete `.donor-button` duplication.
- **Priority:** Medium | **Dependencies:** UI-001, UI-004. **Verification:** grep shows all submit/action buttons render through `Button`.

### UI-012 — Triplicated `getAllPages` helper and hidden cross-service imports (Medium)
- **Files:** `donorApi.js:3–22`, `recipientApi.js:3–19`, `organizationApi.js:3–19` (identical function ×3); `BrowseFoodPage.jsx:3` imports unit math from `donorApi`.
- **Current behavior:** risk of drift between paginators; cross-domain imports make refactors fragile.
- **Recommended improvement:** move `getAllPages` to `services/api.js` (or `utils/pagination.js`); move unit math to `utils/units.js`; re-export for compatibility so pages keep working.
- **Priority:** Medium (code health, not visual) | **Dependencies:** none. **Verification:** `npm run build` + manual flow test of browse→request→approve.

### UI-013 — Form validation is imperative, per-page, and inconsistent (Medium)
- **Files:** `MyDonationsPage.jsx:43–74` (manual `reportValidity` + custom checks), `BrowseFoodPage.jsx:24–48` (string-based errors), `PickupsPage.jsx` (HTML5 required only), `OrganizationsPage.jsx:221–234` (HTML5 only), auth pages (uninspected in depth for this audit's UI scope but same pattern visible in CSS).
- **Current behavior:** no shared field-error component; errors render as page-level blocks (`donor-form-error`) rather than per-field; `Input.jsx` has the right `aria-invalid`/`aria-describedby` pattern but is unused.
- **Recommended improvement:** adopt/extend `Input.jsx` (add select/textarea variants) and wire per-field errors with the aria pattern it already implements.
- **Priority:** Medium | **Dependencies:** UI-005. **Verification:** submit each form empty → per-field errors announced (aria-live) and focus moves to first invalid field.

### UI-014 — Repeated 9–10px "fact list" markup pattern (Low)
- **Files:** `donor-donation-facts` / `donor-request-facts` / `recipient-food-facts` / `recipient-request-facts` / `org-facts` / `pickup-location` — six near-identical `<span><b>LABEL</b>value</span>` grids (CSS lines 799–801, 870–872, 896–898, 1226–1227).
- **Recommended improvement:** single `FactList`/`FactItem` component and one CSS rule.
- **Priority:** Low | **Dependencies:** UI-001. **Verification:** CSS dedup — one `.fact-list` rule replaces six.

### UI-015 — Dashboard metric card as `<Link>` has no focus/hover affordance parity (Low)
- **File:** `DonorOverviewPage.jsx:19`, CSS `main.css:743–744`
- **Current behavior:** metric cards are whole-card links (good for click) but hover/focus styling only changes border/transform — no visible focus outline on the card itself in some browsers because the `:focus-visible` rule targets the `a` element with `outline-offset: 3px` that can clip under `overflow: hidden` parents. **SUSPECTED** — needs browser check.
- **Priority:** Low. **Verification:** Tab through dashboard, screenshot focus ring.

### UI-016 — Unfinished features that are intentional, not defects (informational)
- **Files:** `Sidebar.jsx:12,21` ("Impact" nav item with `is-unavailable` + "Soon" chip — deliberate placeholder); `DonorOverviewPage.jsx:71` ("Upcoming pickups" metric card rendered with `unavailable` state — deliberate); `MainLayout.jsx:100` static subtitle "Good food, shared with purpose." on every page (could become per-page copy later); `LandingPage.jsx:182–186` "Developer diagnostic: API health" `<details>` block visible on the public homepage (looks like a debug leftover — confirm whether it should ship).
- **Do not "fix" these as UI bugs** without product confirmation; the report flags the API diagnostic block as the one most likely to be mistaken for a defect.

### UI-017 — Responsive behavior is broadly handled; two gaps remain (Low)
- **Files:** `main.css` media queries at 1000/760/440px (public) and 900/720/380px (app shell), 620/420px (donor/recipient/org), 520px (pickup/notification)
- **Confirmed gaps:** (a) no print styles; (b) `@media (max-width: 720px)` hides `.profile-copy` (good) but the mobile drawer breakpoint differs from the public site's 760px — two mobile nav patterns exist side by side; (c) **SUSPECTED:** very long unbroken strings in `org-facts`/`donor-donation-facts` use `overflow-wrap: anywhere` (present) — likely fine, needs visual check at 320px.
- **Priority:** Low. **Verification:** 320/375/768/1024/1440 screenshot sweep.

### UI-018 — Animations/transitions exist and are reduced-motion-safe (informational + one gap)
- **Files:** `main.css` 106, 474–476, 1014–1022, keyframes 534–541; hover transitions on cards/buttons/nav.
- **Confirmed gap:** cards fade/animate on hover but there is **no entrance/loading transition** (lists pop in abruptly after fetch) and no page-transition. Reduced-motion is correctly respected (both blocks disable animations). Any new animation work should follow the existing `--sh-duration-*`/`--sh-ease-out` tokens.
- **Priority:** Low. **Verification:** Lighthouse + manual.

### UI-019 — API layer has no 401 handling (High — correctness adjacent to UI)
- **File:** `services/api.js:29–39`
- **Current behavior:** the response interceptor is an empty stub with a TODO comment; on session expiry every page just shows its generic error panel instead of redirecting to `/login`. Users see "We couldn't load your donations" when the real problem is an expired session.
- **Recommended improvement:** on 401 (excluding the CSRF/login endpoints), clear auth state and redirect to login. This is behavior, not styling — implement carefully so `ProtectedRoute`'s own `checkSession` flow isn't double-triggered.
- **Priority:** High | **Dependencies:** coordinate with `AuthContext` (not read in full here — verify its logout shape first). **Verification:** expire session manually, confirm redirect + no error spam.

### UI-020 — No tests exist at all (High — enables everything else)
- **Files:** `frontend/package.json` (no `test` script, no test deps)
- **Recommended improvement:** add Vitest + React Testing Library before the refactor so the consolidation in UI-001/UI-004/UI-011 has a safety net (smoke render of each route + one interaction per page).
- **Priority:** High | **Dependencies:** do early, before UI-001.

---

## 2. SUSPECTED issues (require browser verification — not performed)

| ID | Suspicion | How to verify |
|---|---|---|
| SUS-01 | `MainLayout` page-title fallback (line 32) shows "Donor overview" as title on `/notifications` for donors because `/notifications` is in the map — actually mapped, but for any future route the fallback is role-guessed; also `access-denied` (role-mismatch) renders inside `<main>` **without** the sidebar, producing a bare page. | Log in as donor, manually type `/volunteer/pickups`. |
| SUS-02 | Dark-theme `input-input` inside the light-background `auth-page` gradient: `color-scheme: dark` inputs on dark card should be fine, but native date pickers inside `donor-field` inputs on the Phase-4 dark cards may render dark-on-dark icons. | Open donation form; inspect datetime pickers in Chrome/Edge. |
| SUS-03 | `.app-content` uses `padding: 32px max(24px, calc((100vw - 1160px) / 2))` (line 355) while width is `min(1180px, 100%)` (line 702) — 1180 vs 1160 mismatch may cause slight off-center content on ultra-wide screens. | Measure at 1920px width. |
| SUS-04 | Popover `right: -52px` on ≤520px (line 1324) may push the notifications popover off-screen on 320px devices. | Open bell popover at 320px. |
| SUS-05 | `DonationRequestsPage` fact grid has 5 items in a 3-column grid → orphan item layout; `.donor-request-facts` set to 3 columns (line 822) vs donation facts at 2 — visual inconsistency between the two card types. | Screenshot a populated request card. |
| SUS-06 | `Topbar` popover opens without focus being moved into it; screen readers may not announce the opened list. | NVDA/JAWS pass. |
| SUS-07 | Status pill contrast: `--sh-color-text-subtle` (#91a69b) on `rgba(145,166,155,.1)` background may fail 4.5:1 for the 9px badge text. | Contrast analyzer on rendered badges. |
| SUS-08 | Long emails/usernames in `org-user-result` and `profile-copy` rely on `overflow-wrap: anywhere`/ellipsis — verify no layout blowout with a 60-char email. | Seed nothing; use a long-named test account in a **non-production** manner (or mock). |
| SUS-09 | Landing hero decorative `role="img"` (LandingPage.jsx:91) may be announced as a giant unlabeled image; also the `aria-label` is long. | Screen-reader smoke test. |

---

## 3. Implementation risks (Step 3 summary)

1. **Shared components at risk:** `Loading` (used everywhere), `Sidebar`/`Topbar`/`MainLayout` (whole app shell), `ProtectedRoute` (auth gate). Changes here affect every route — test all 12 authenticated routes after any edit.
2. **Styles to preserve:** the mobile drawer focus-trap behavior (`MainLayout`), reduced-motion overrides, `sr-only` utility, `color-scheme: dark` inputs, the CSRF cookie flow, `getAllPages` pagination semantics (pages depend on arrays, not paginators).
3. **Routes that must remain:** the full map in §0. Especially `/donor/pickups`, `/recipient/pickups`, `/volunteer/pickups` — one `PickupsPage` serves three roles with role-conditional UI; refactor must keep role branching intact.
4. **API contracts not to break:** `mine=true` / `browse=true` query params, approve endpoint's `Idempotency-Key` header, `organization` filter on memberships, `user-search` endpoint, `/accounts/csrf_token/` bootstrap, `/health/` diagnostic.
5. **Unfinished features (not defects):** "Impact" sidebar entries, unavailable pickup metric, static page subtitle, homepage API diagnostic block (UI-016).
6. **Coupling to watch:** unit-math in `donorApi.js` used by recipient page (UI-012); `PickupsPage` imports error helper from `donorApi` despite being cross-role.

---

## 4. Safe implementation order (Step 5)

| Phase | Scope | Rationale |
|---|---|---|
| **0** | Add Vitest + RTL, smoke-render all routes (UI-020) | safety net before touching shared code |
| **1** | Consolidate design tokens (UI-001): single `:root`, delete dead layers, keep class names | everything downstream inherits correct tokens |
| **2** | Shared primitives: finish `Button.jsx`, adopt `Card`/`Input`/`ErrorMessage` or delete them (UI-005, UI-011, UI-013) | removes duplication before page refactors |
| **3** | Shared navigation/shell polish: Topbar popover a11y (UI-008), neutral class renames (UI-004) | app-wide, low page-level risk |
| **4** | Shared patterns: `StatusBadge` (UI-006), `PageIntro` (UI-003), `FactList` (UI-014), unified loading/error/empty (UI-007) | mechanical, page-by-page migration |
| **5** | Dashboards first (Donor overview, Recipient overview), then workflow pages (donations, requests, browse, pickups, organizations, notifications) | dashboards have most bespoke CSS; validate pattern reuse there |
| **6** | Typography scale (UI-010), animations/entrance transitions (UI-018), responsive sweep (UI-017) | polish after structure is stable |
| **7** | API robustness (UI-019) + accessibility verification pass (UI-009, SUS items) | final correctness + a11y gate |

Each phase should end with: `npm run lint`, `npm run build`, manual click-through of all 12 authenticated routes + landing/login/register, and a fresh screenshot set for comparison.

---

## 5. Issue index (quick reference)

| ID | Area | Priority | Status |
|---|---|---|---|
| UI-001 | Dual/conflicting token systems | Critical | Confirmed |
| UI-002 | Heading hierarchy | High | Confirmed |
| UI-019 | No 401 handling | High | Confirmed |
| UI-020 | No tests | High | Confirmed |
| UI-003 | Duplicated page intro | Medium | Confirmed |
| UI-004 | donor- classes everywhere | Medium | Confirmed |
| UI-005 | Dead components / missing CSS | Medium | Confirmed |
| UI-006 | Fragmented status badges | Medium | Confirmed |
| UI-007 | Inconsistent state UI | Medium | Confirmed |
| UI-008 | Topbar popover a11y | Medium | Confirmed |
| UI-011 | Three button systems | Medium | Confirmed |
| UI-012 | Triplicated API helper | Medium | Confirmed |
| UI-013 | Form validation inconsistency | Medium | Confirmed |
| UI-009 | Glyph icons / aria details | Low | Confirmed |
| UI-010 | Ad-hoc type scale | Low | Confirmed |
| UI-014 | Fact-list duplication | Low | Confirmed |
| UI-015 | Metric card focus ring | Low | Suspected |
| UI-016 | Intentional placeholders | Info | Confirmed |
| UI-017 | Responsive gaps | Low | Mixed |
| UI-018 | Animation polish | Low | Confirmed |
| SUS-01…09 | Runtime/layout suspicions | Varies | **Requires browser verification** |

*No application source files were modified in producing this report.*
