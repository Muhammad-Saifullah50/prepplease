# Exam Attempt API Contracts

Base path: `/api/v1/exam-attempts`

---

## POST /api/v1/exam-attempts

Start a new exam attempt from a generated mock exam.

**Request**:
```json
{
  "generated_exam_id": "uuid",
  "course_id": "uuid"
}
```

**Response 201**:
```json
{
  "id": "uuid",
  "status": "active",
  "started_at": "2026-07-22T10:00:00Z",
  "deadline": "2026-07-22T13:00:00Z",
  "time_limit_minutes": 180,
  "questions": [
    {"number": 1, "text": "...", "marks": 10},
    {"number": 2, "text": "...", "marks": 15}
  ]
}
```

**Errors**:
- `409 Conflict`: Student already has an active attempt. Body includes `existing_attempt_id`.
- `404 Not Found`: Generated exam not found or not available.
- `422 Unprocessable`: Validation failure.

**Idempotency**: Not idempotent. A second request while one is active returns 409.

---

## GET /api/v1/exam-attempts/{attempt_id}/state

Poll current attempt state (questions, answers, remaining time, focus violations).

**Response 200**:
```json
{
  "id": "uuid",
  "status": "active",
  "questions": [
    {"number": 1, "text": "...", "marks": 10},
    {"number": 2, "text": "...", "marks": 15}
  ],
  "answers": {"1": "answer text", "2": ""},
  "remaining_seconds": 10750,
  "focus_violations": 1,
  "focus_violations_limit": 3,
  "deadline": "2026-07-22T13:00:00Z"
}
```

For terminal states, `remaining_seconds` is `0`, no questions/answers returned.

**Errors**:
- `403 Forbidden`: Attempt belongs to another user.
- `404 Not Found`: Attempt not found.

---

## PUT /api/v1/exam-attempts/{attempt_id}/answers

Save in-progress answers (partial update, upsert per question).

**Request**:
```json
{
  "answers": {"1": "updated answer", "3": "new answer for q3"}
}
```

**Response 200**:
```json
{
  "status": "saved",
  "saved_at": "2026-07-22T11:30:00Z"
}
```

**Errors**:
- `400 Bad Request`: Attempt is not active (already finished/locked/expired).
- `403 Forbidden`: Attempt belongs to another user.
- `404 Not Found`: Attempt not found.

---

## POST /api/v1/exam-attempts/{attempt_id}/finish

Manually submit an active attempt.

**Response 200** (if attempt was active and is now finished):
```json
{
  "status": "submitted",
  "finished_by": "manual",
  "ended_at": "2026-07-22T12:30:00Z",
  "grading_status": "queued"
}
```

**Response 200** (if attempt was already finished — idempotent):
```json
{
  "status": "submitted",
  "finished_by": "deadline",
  "ended_at": "2026-07-22T12:30:00Z",
  "grading_status": "queued"
}
```

No 409 — concurrent finishes resolve to the same outcome (FR-009).

**Errors**:
- `403 Forbidden`: Attempt belongs to another user.
- `404 Not Found`: Attempt not found.
