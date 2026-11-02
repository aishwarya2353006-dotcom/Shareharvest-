# ShareHarvest API Design

## API Conventions

### Base URL
- Development: `http://localhost:8000/api/`
- Production: `https://api.shareharvest.org/api/`

### Authentication
- Session-based authentication (Django default)
- CSRF protection for state-changing operations
- `Authorization` header not used; relies on session cookies
- Frontend must send `X-CSRFToken` header for POST/PUT/PATCH/DELETE

### Response Format

#### Success
```json
{
  "data": { ... },
  "meta": { ... }
}
```

#### List Response
```json
{
  "data": [...],
  "meta": {
    "pagination": {
      "count": 100,
      "next": "http://localhost:8000/api/donations/?page=2",
      "previous": null,
      "page_size": 20,
      "current_page": 1,
      "total_pages": 5
    }
  }
}
```

#### Error
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Validation failed",
    "details": {
      "field_name": ["Error message"]
    }
  }
}
```

### HTTP Status Codes
- `200` - OK
- `201` - Created
- `204` - No Content
- `400` - Bad Request (validation error)
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `409` - Conflict (e.g., duplicate, concurrency)
- `500` - Internal Server Error

### Pagination
- Page-based pagination (default 20 items)
- Query params: `page`, `page_size` (max 100)

### Filtering & Search
- Filter: `?field=value` (exact), `?field__gte=value` (range)
- Search: `?search=query` (full-text on configured fields)
- Ordering: `?ordering=-created_at,field_name`

## API Endpoints

### Core

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health/` | Health check (public) |

### Authentication (accounts)

| Method | Endpoint | Description | Permissions |
|--------|----------|-------------|-------------|
| POST | `/api/accounts/register/` | Register new user | AllowAny |
| POST | `/api/accounts/login/` | Login (session) | AllowAny |
| POST | `/api/accounts/logout/` | Logout | IsAuthenticated |
| GET | `/api/accounts/me/` | Current user profile | IsAuthenticated |
| PUT/PATCH | `/api/accounts/me/` | Update profile | IsAuthenticated |
| PUT | `/api/accounts/me/password/` | Change password | IsAuthenticated |

### Organizations

| Method | Endpoint | Description | Permissions |
|--------|----------|-------------|-------------|
| GET | `/api/organizations/` | List organizations (user's) | IsAuthenticated |
| POST | `/api/organizations/` | Create organization | IsAuthenticated |
| GET | `/api/organizations/{id}/` | Get organization | IsAuthenticated (member) |
| PUT/PATCH | `/api/organizations/{id}/` | Update organization | IsAuthenticated (owner/admin) |
| DELETE | `/api/organizations/{id}/` | Delete organization | IsAuthenticated (owner) |
| POST | `/api/organizations/{id}/verify/` | Verify organization | IsAuthenticated (admin) |
| GET | `/api/organizations/{id}/members/` | List members | IsAuthenticated (member) |
| POST | `/api/organizations/{id}/members/` | Add member | IsAuthenticated (owner/admin) |
| DELETE | `/api/organizations/{id}/members/{user_id}/` | Remove member | IsAuthenticated (owner/admin) |
| PUT | `/api/organizations/{id}/members/{user_id}/` | Update member role | IsAuthenticated (owner/admin) |

### Donations

| Method | Endpoint | Description | Permissions |
|--------|----------|-------------|-------------|
| GET | `/api/donations/` | List donations (with filters) | IsAuthenticated |
| POST | `/api/donations/` | Create donation | IsAuthenticated (donor) |
| GET | `/api/donations/{id}/` | Get donation detail | IsAuthenticated (donor/org member/recipient if published) |
| PUT/PATCH | `/api/donations/{id}/` | Update donation | IsAuthenticated (donor, draft only) |
| DELETE | `/api/donations/{id}/` | Delete donation | IsAuthenticated (donor, draft only) |
| POST | `/api/donations/{id}/publish/` | Publish donation | IsAuthenticated (donor) |
| POST | `/api/donations/{id}/cancel/` | Cancel donation | IsAuthenticated (donor) |
| GET | `/api/donations/{id}/requests/` | List requests for donation | IsAuthenticated (donor/org member) |

#### Donation Filters
- `status` - draft, published, reserved, completed, expired, cancelled
- `food_category` - prepared, produce, dairy, bakery, packaged, beverages, other
- `available_from__gte` - available after date
- `available_until__lte` - available before date
- `organization` - organization ID
- `search` - title, description

### Requests (donation-requests)

| Method | Endpoint | Description | Permissions |
|--------|----------|-------------|-------------|
| GET | `/api/donation-requests/` | List requests visible to the current user | IsAuthenticated (participant/member/admin) |
| POST | `/api/donation-requests/` | Create a request | IsAuthenticated (recipient user active in a verified recipient organization) |
| GET | `/api/donation-requests/{id}/` | Get request detail | IsAuthenticated (participant/member/admin) |
| PATCH | `/api/donation-requests/{id}/` | Edit request details | IsAuthenticated (submitting recipient, pending only) |
| POST | `/api/donation-requests/{id}/cancel/` | Cancel request | IsAuthenticated (requester or recipient org owner/admin, pending only) |
| POST | `/api/donation-requests/{id}/approve/` | Add a full or partial allocation | IsAuthenticated (donation creator, donor org owner/admin, or platform admin) |
| POST | `/api/donation-requests/{id}/reject/` | Reject an unallocated request | IsAuthenticated (donation creator, donor org owner/admin, or platform admin) |

#### Approve Request Body
```json
{
  "approved_quantity": "50.00",
  "approved_unit": "kg",
  "notes": "Partial allocation; remainder remains requested"
}
```

`approved_unit` must be compatible with both the donation and request units. Each POST appends one immutable allocation. Multiple partial approvals are supported until the request is fully approved. Over-request and over-donation approvals return HTTP 409. Allocation records cannot be created, changed, or deleted directly.

Every approval must include an `Idempotency-Key` header (1–64 characters). The key is unique per request. Retrying the same key and payload returns the current request without creating another allocation; reusing a key with different payload or approver returns HTTP 409. A different key represents a distinct allocation operation.

Request transitions are `pending -> partially_approved -> approved`, `pending -> rejected`, and `pending -> cancelled`. Rejection or cancellation after any allocation is not supported; allocations are never withdrawn by this API.

### Allocations

| Method | Endpoint | Description | Permissions |
|--------|----------|-------------|-------------|
| GET | `/api/allocations/` | List allocations visible to the current user | IsAuthenticated (participant/member/admin) |
| GET | `/api/allocations/{id}/` | Get allocation detail | IsAuthenticated (participant/member/admin) |

Request detail responses include `allocations`, `approved_quantity`, and `remaining_quantity`. Lists use standard Django REST Framework pagination (`count`, `next`, `previous`, `results`).

### Pickups

| Method | Endpoint | Description | Permissions |
|--------|----------|-------------|-------------|
| GET | `/api/pickups/` | List pickups visible to the current user | IsAuthenticated (active donor/recipient organization members, assigned eligible volunteer, or platform admin) |
| GET | `/api/pickups/{id}/` | Get an authorized pickup | Same scope as list |
| POST | `/api/pickups/` | Schedule a pickup for an allocation | Active donor-organization or recipient-organization member, or platform admin |
| PATCH | `/api/pickups/{id}/` | Edit scheduling details or reschedule | Authorized organization member; scheduled pickups only |
| GET | `/api/pickups/eligible-allocations/` | List approved allocations without pickups | Authorized donor/recipient organization members, or platform admin |
| GET | `/api/pickups/available-volunteers/?allocation={id}` | List eligible organization volunteers for an allocation | Authorized donor/recipient organization member, or platform admin |
| POST | `/api/pickups/{id}/assign-volunteer/` | Assign or remove a volunteer (`{"volunteer": id}` or `null`) | Authorized organization member; scheduled pickups only |
| POST | `/api/pickups/{id}/start/` | Start a scheduled pickup | Authorized organization member or assigned eligible volunteer |
| POST | `/api/pickups/{id}/complete/` | Complete an in-progress pickup and record actual quantity/unit | Authorized organization member or assigned eligible volunteer |
| POST | `/api/pickups/{id}/fail/` | Mark an in-progress pickup failed with a reason | Authorized organization member or assigned eligible volunteer |
| POST | `/api/pickups/{id}/no-show/` | Mark a scheduled pickup missed after its time | Authorized organization member or assigned eligible volunteer |
| POST | `/api/pickups/{id}/cancel/` | Cancel a pickup before it starts | Authorized organization member or platform admin |

Pickup creation accepts an `allocation` ID and scheduling/contact fields. The server derives donation and request from that allocation; client-supplied status, volunteer, request, donation, and actual quantity are not writable. Each approved allocation can have one pickup, enforced by a database uniqueness constraint. Volunteer assignment is optional and requires an active `User.role=volunteer` account with an active `Membership.role=volunteer` in either participating organization.

Allowed state transitions are `scheduled -> in_progress -> completed|failed`, `scheduled -> cancelled`, and `scheduled -> no_show`. Starting and no-show actions are unavailable before the scheduled time. Rescheduling and editing scheduling details are allowed only while scheduled; terminal states cannot be reopened. Completing requires a positive actual quantity and compatible unit no greater than the approved allocation. Partial/short collection is recorded as completed with the actual amount; neither completion nor failure/cancellation/no-show changes allocation or donation stock. A missed pickup before progress starts is `no_show`; a pickup that cannot be completed after it starts is `failed` and requires a reason. Neither state records actual quantity or releases the allocation.

### Notifications

| Method | Endpoint | Description | Permissions |
|--------|----------|-------------|-------------|
| GET | `/api/notifications/` | List notifications | IsAuthenticated |
| GET | `/api/notifications/{id}/` | Get notification | IsAuthenticated (recipient) |
| PATCH | `/api/notifications/{id}/read/` | Mark as read | IsAuthenticated (recipient) |
| POST | `/api/notifications/read-all/` | Mark all as read | IsAuthenticated |

### Impact

| Method | Endpoint | Description | Permissions |
|--------|----------|-------------|-------------|
| GET | `/api/impact/reports/` | List impact reports | IsAuthenticated (org member) |
| POST | `/api/impact/reports/` | Generate report | IsAuthenticated (org admin) |
| GET | `/api/impact/reports/{id}/` | Get report detail | IsAuthenticated (org member) |
| GET | `/api/impact/statistics/` | Get statistics | IsAuthenticated (org member) |
| GET | `/api/impact/dashboard/` | Dashboard summary | IsAuthenticated |

### Audit

| Method | Endpoint | Description | Permissions |
|--------|----------|-------------|-------------|
| GET | `/api/audit/logs/` | List audit logs | IsAuthenticated (admin) |
| GET | `/api/audit/logs/{id}/` | Get audit log | IsAuthenticated (admin) |

## Request/Response Examples

### Register User
```bash
POST /api/accounts/register/
Content-Type: application/json

{
  "username": "john_donor",
  "email": "john@restaurant.com",
  "password": "securepass123",
  "password_confirm": "securepass123",
  "first_name": "John",
  "last_name": "Doe",
  "role": "donor",
  "phone": "+919876543210"
}
```

**Response 201:**
```json
{
  "data": {
    "id": 1,
    "username": "john_donor",
    "email": "john@restaurant.com",
    "first_name": "John",
    "last_name": "Doe",
    "role": "donor",
    "phone": "+919876543210",
    "is_verified": false,
    "created_at": "2026-01-15T10:30:00Z"
  }
}
```

### Create Donation
```bash
POST /api/donations/
Content-Type: application/json
X-CSRFToken: <csrf_token>

{
  "organization": 1,
  "title": "Fresh Vegetables from Daily Market",
  "description": "Assorted fresh vegetables harvested this morning",
  "food_category": "produce",
  "quantity": "25.50",
  "unit": "kg",
  "available_from": "2026-01-15T08:00:00Z",
  "available_until": "2026-01-15T20:00:00Z",
  "pickup_address": "123 Market Street, Bangalore",
  "pickup_instructions": "Back entrance, loading dock B"
}
```

### Create Request
```bash
POST /api/donation-requests/
Content-Type: application/json
X-CSRFToken: <csrf_token>

{
  "organization": 2,
  "donation": 1,
  "requested_quantity": "10.00",
  "requested_unit": "kg",
  "notes": "Need for community kitchen serving 50 people"
}
```

### Approve Request (with partial allocation)
```bash
POST /api/donation-requests/1/approve/
Content-Type: application/json
X-CSRFToken: <csrf_token>

{
  "approved_quantity": "8.00",
  "approved_unit": "kg",
  "notes": "Partial approval - limited storage capacity"
}
```

**Response 200:**
```json
{
  "data": {
    "id": 1,
    "status": "partially_approved",
    "requested_quantity": "10.00",
    "requested_unit": "kg",
    "approved_quantity": "8.00",
    "approved_unit": "kg",
    "allocations": [
      {
        "id": 1,
        "approved_quantity": "8.00",
        "approved_unit": "kg",
        "approved_quantity_kg": "8.000",
        "approved_by": "john_donor",
        "created_at": "2026-01-15T11:00:00Z"
      }
    ],
    "donation": {
      "id": 1,
      "title": "Fresh Vegetables",
      "quantity": "25.50",
      "unit": "kg"
    }
  }
}
```

### Create Pickup
```bash
POST /api/pickups/
Content-Type: application/json
X-CSRFToken: <csrf_token>

{
  "allocation": 1,
  "pickup_type": "volunteer",
  "scheduled_at": "2026-01-16T10:00:00Z",
  "pickup_address": "123 Market Street, Bangalore",
  "contact_person": "John Doe",
  "contact_phone": "+919876543210",
  "notes": "Call when arriving"
}
```

To complete a pickup, send the collected amount in a unit compatible with the approved allocation:

```json
{
  "actual_quantity": "4.25",
  "actual_unit": "kg"
}
```

## Validation Rules

### Donation
- `quantity` > 0
- `available_from` < `available_until`
- `available_from` >= now (can schedule future)
- `food_category` must be valid choice
- `unit` must be valid choice
- Donor must be member of organization with active membership (role: owner, admin, or member)

### Request
- `requested_quantity` > 0
- Requested quantity must not exceed currently unallocated donation stock at submission time.
- User must have role `recipient` and active membership in a verified recipient organization (`ngo`, `trust`, or `community`).
- Donation must be `published`, available now (`available_from <= now`), and not expired (`available_until > now`).
- Cannot request own organization's donation
- One open (`pending` or `partially_approved`) request per recipient organization and donation.
- Mass units convert between kg/g; volume units convert between l/ml. Count units (`units`, `boxes`, `trays`) are only compatible with the exact same count unit.

### Allocation (Approval)
- `approved_quantity` > 0
- `approved_unit` must be compatible with both request and donation units.
- Sum of allocations must not exceed either the remaining requested amount or remaining donation amount.
- Each approval creates a `DonationAllocation` record
- `DonationRequest.status` becomes `approved` when fulfilled or `partially_approved` while some requested amount remains.
- A fully allocated donation changes to `reserved`.

### Partial Allocation
- Donation and request rows are locked and stock is rechecked inside an atomic transaction.
- Database row locks serialize approvals on databases that support `SELECT ... FOR UPDATE` (for example PostgreSQL). SQLite ignores row-level locks; concurrency has not been verified on SQLite.
- Legacy `quantity_kg`, `requested_quantity_kg`, and `approved_quantity_kg` fields are retained, but the current model conversion stores volume/count values as if they were kilograms. Workflow validation uses dimension-specific base units in code and does not rely on those fields. A normalization migration is still needed for reporting and impact totals.

## Error Codes

| Code | HTTP | Description |
|------|------|-------------|
| `VALIDATION_ERROR` | 400 | Request data invalid |
| `AUTHENTICATION_REQUIRED` | 401 | User not authenticated |
| `PERMISSION_DENIED` | 403 | User lacks permission |
| `NOT_FOUND` | 404 | Resource not found |
| `CONFLICT` | 409 | Resource conflict (e.g., over-allocation) |
| `INVALID_STATE` | 400 | Operation invalid for current state |
| `RATE_LIMITED` | 429 | Too many requests |

## Versioning
- URL path versioning: `/api/v1/...` (future)
- Current: v1 implicit at `/api/`

## Rate Limiting (Future)
- Anonymous: 60 req/min
- Authenticated: 300 req/min
- Burst: 10 req/sec
