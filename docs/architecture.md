# ShareHarvest Architecture Overview

## System Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Frontend      │────▶│   Backend       │────▶│   Database      │
│   (React)       │     │   (Django REST  │     │   (SQLite/      │
│                 │◀────│   Framework)    │◀────│   PostgreSQL)   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                       │                       │
        │                       │                       │
        ▼                       ▼                       ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Browser       │     │   Authentication│     │   Migrations    │
│   (User)        │     │   & Authorization     │   & Schema      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

## Component Interaction

### Frontend (React + Vite)
- **Technology**: React 18, Vite, React Router, Axios
- **Responsibilities**:
  - User interface rendering
  - Client-side routing
  - API communication via Axios
  - State management (React Context + hooks)
  - Form validation and user feedback

### Backend (Django REST Framework)
- **Technology**: Python, Django 4.2+, DRF, django-cors-headers
- **Responsibilities**:
  - REST API endpoints
  - Authentication & authorization
  - Business logic enforcement
  - Data validation
  - Database transactions
  - Audit logging

### Database
- **Development**: SQLite (zero-config, file-based)
- **Production**: PostgreSQL (planned)
- **ORM**: Django ORM with migrations

### External Users
- **Donors**: Restaurants, hotels, supermarkets, malls, caterers, event organizers
- **Recipients**: NGOs, charities, trusts, community organizations
- **Volunteers**: Delivery partners, pickup coordinators
- **Administrators**: Platform managers

## Three-Layer Authorization Model

```
┌─────────────────────────────────────────────────────────────┐
│  LAYER 1: Platform Role (User.role)                         │
│  - donor, recipient, volunteer, admin                       │
│  - Determines WHAT KIND of actions user can initiate        │
│  - Global permissions: e.g., only 'donor' can create        │
│    donations, only 'recipient' can create requests          │
├─────────────────────────────────────────────────────────────┤
│  LAYER 2: Organization Membership (Membership.role)         │
│  - owner, admin, member, volunteer                          │
│  - Determines SCOPE within an organization                  │
│  - Organization-scoped permissions: e.g., 'owner'/'admin'   │
│    can verify organization, manage members, approve requests│
│  - 'volunteer' role here = pickup duties within org only    │
├─────────────────────────────────────────────────────────────┤
│  LAYER 3: Organization Verification Status (Organization.status) │
│  - pending, verified, rejected                              │
│  - Gates access to certain operations                       │
│  - Only 'verified' orgs can publish donations / create requests │
└─────────────────────────────────────────────────────────────┘
```

**Key Distinction**: `User.role` (platform identity) and `Membership.role` (org-scoped duties) are separate authorization sources. Do not make them contradictory. A user with `User.role = 'donor'` can have `Membership.role = 'volunteer'` in a recipient organization - these grant different permissions at different layers.

## Security Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Security Layers                         │
├─────────────────────────────────────────────────────────────┤
│  Frontend: Route protection (UX only, not security)        │
│  Backend: Authentication (Session + CSRF)                   │
│  Backend: Permission classes (IsAuthenticated, custom)      │
│  Backend: Object-level permissions (organization isolation) │
│  Database: Row-level constraints, foreign keys              │
│  Audit: All critical actions logged                         │
└─────────────────────────────────────────────────────────────┘
```

## Django App Structure

| App | Responsibility |
|-----|----------------|
| `accounts` | Custom user model, authentication, registration |
| `organizations` | Organization profiles, memberships, verification |
| `donations` | Food donation CRUD, availability, expiry, allocation tracking |
| `donation_requests` | Recipient requests, approval, partial allocation (renamed from `requests`) |
| `pickups` | Pickup scheduling, status tracking, coordination |
| `notifications` | In-app notifications |
| `impact` | Statistics, reports, analytics |
| `audit` | Action history for compliance |
| `core` | Health checks, shared utilities |

## Data Flow Example: Donation Creation to Pickup

```
1. Donor (authenticated) POST /api/donations/
   → Validation → Save Donation (status: draft)
   
2. Donor POST /api/donations/{id}/publish/
   → Status: published → Notify nearby recipients

3. Recipient GET /api/donations/ (filters)
   → List available donations

4. Recipient POST /api/donation-requests/
   → Create DonationRequest (status: pending)

5. Donor/Org Admin GET /api/donation-requests/?donation={id}
   → Review requests

6. Donor POST /api/donation-requests/{id}/approve/ {approved_quantity, approved_unit}
   → Lock donation and request rows in an atomic transaction
   → Compare dimension-compatible quantities against request and donation remainder
   → Append DonationAllocation and transition request status

7. Volunteer/Driver GET /api/pickups/
   → Accept pickup → Update status

8. Pickup completed → Update Donation status
   → Generate Impact statistics
   → Audit log entries created
```

## Concurrency Control for Allocation

Approvals lock the shared `Donation` row first and the target `DonationRequest` row second, then sum immutable allocation records and revalidate both remaining quantities before inserting. The common donation lock serializes approvals made against different requests for the same donation. An over-allocation returns HTTP 409 and leaves the transaction unchanged.

This uses `select_for_update()` inside `transaction.atomic()`, which provides row locking on databases that support it (such as PostgreSQL). SQLite ignores `select_for_update`; the local SQLite setup does not provide the same concurrency guarantee and the threaded locking test is skipped there. Production allocation concurrency must be validated against PostgreSQL.

Quantity comparisons use grams for mass, milliliters for volume, and the exact same unit for each count unit (`units`, `boxes`, or `trays`). Existing `*_quantity_kg` fields are not used for these checks because the current model stores volume/count values in those fields as if they were kilograms. Reporting normalization remains future work.

## Deployment Architecture (Future)

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Nginx     │────▶│   Gunicorn  │────▶│   Django    │
│   (Static,  │     │   (WSGI)    │     │   App       │
│   Proxy)    │     │             │     │             │
└─────────────┘     └─────────────┘     └─────────────┘
                           │                    │
                           ▼                    ▼
                    ┌─────────────┐     ┌─────────────┐
                    │  PostgreSQL │     │   Redis     │
                    │  (Primary)  │     │  (Cache,    │
                    │             │     │   Celery)   │
                    └─────────────┘     └─────────────┘
```

## Development Workflow

1. **Local Development**: SQLite, runserver, Vite dev server
2. **Testing**: pytest (backend), Vitest/Jest (frontend)
3. **CI/CD**: GitHub Actions → Docker → Deploy
4. **Production**: PostgreSQL, Nginx, Gunicorn, Docker Compose/Kubernetes
