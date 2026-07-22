# Focus Violation API Contract

Base path: `/api/v1/exam-attempts`

---

## POST /api/v1/exam-attempts/{attempt_id}/focus-violations

Report a focus-loss event.

**Request** (no body needed):
```json
{}
```

**Response 200** (violation recorded, under limit):
```json
{
  "focus_violations": 2,
  "focus_violations_limit": 3,
  "violations_remaining": 1,
  "status": "active"
}
```

**Response 200** (violation crossed the limit — attempt locked):
```json
{
  "focus_violations": 3,
  "focus_violations_limit": 3,
  "violations_remaining": 0,
  "status": "locked_out",
  "finished_by": "lockout",
  "ended_at": "2026-07-22T11:45:00Z"
}
```

**Errors**:
- `400 Bad Request`: Attempt is not active (already locked/finished/expired).
- `403 Forbidden`: Attempt belongs to another user.
- `404 Not Found`: Attempt not found.
