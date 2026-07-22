# Feature Specification: Foundation Services

**Feature Branch**: `004-foundation-services`
**Created**: 2026-07-21
**Status**: Draft
**Input**: User description: "Phase 3a: Course Core Service + Ingestion Pipeline Service — FastAPI CRUD for courses, dashboard telemetry, user profiles, performance history; file upload to S3 streaming, chunking, semantic tokenization, and DB storage"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Upload a past paper and track its processing (Priority: P1)

A student uploads a past exam PDF or lecture slide deck for a course. The system accepts the file, stores it securely, and processes it in the background — extracting text, identifying the instructor, building or updating the exam blueprint, and making the content searchable. The student can check processing status at any time.

**Why this priority**: This is the primary data ingestion path. Without it, no content enters the system for blueprint extraction or exam generation. It wraps the existing ingestion pipeline with a user-facing API.

**Independent Test**: Upload a past-paper PDF via the upload endpoint; poll the status endpoint until it reads "completed"; verify the course's blueprint count has increased and the paper appears in the course's paper list.

**Acceptance Scenarios**:

1. **Given** a logged-in user enrolled in a course, **When** they upload a PDF past paper, **Then** the system accepts the file, returns a tracking identifier immediately, and begins background processing.
2. **Given** a submitted paper whose processing completes successfully, **When** the user checks its status, **Then** the status reads "completed" and the course's blueprint has been created or updated.
3. **Given** a submitted paper whose processing fails (corrupt file, parsing failure), **When** the user checks its status, **Then** the status reads "failed" with a human-readable reason and no partial data is persisted.
4. **Given** a submitted paper whose processing is in progress, **When** the user checks its status, **Then** the status reads "processing" with an approximate elapsed time.
5. **Given** a user uploads the same file twice, **When** the second upload completes, **Then** the system detects the duplicate and returns the existing tracking identifier without re-processing (idempotent).

---

### User Story 2 - View course dashboard with performance analytics (Priority: P1)

A student opens their course dashboard and sees an overview: their recent exam results, per-topic strength and weakness breakdowns, their course's extracted blueprint (showing the exam structure the professor follows), and a list of past papers and available mock exams.

**Why this priority**: The dashboard is the student's home base. It surfaces the value of everything the system has built — blueprints, past ingestions, and exam history — in one place.

**Independent Test**: With a course that has an uploaded paper, a blueprint, and at least one graded exam result, call the dashboard summary endpoint; verify it returns an aggregate score, a list of weak topics derived from results, and a reference to the latest blueprint.

**Acceptance Scenarios**:

1. **Given** a user with access to multiple courses, **When** they view their dashboard, **Then** they see a list of their courses with each course's latest blueprint summary, number of past papers ingested, and number of completed exams.
2. **Given** a course with graded exam results, **When** the user views the course's performance view, **Then** they see an aggregate score (average percentage across all results), a per-topic breakdown showing strongest and weakest areas, and the trend over time.
3. **Given** a course with an extracted blueprint, **When** the user views the blueprint, **Then** they see the exam structure (sections, question types, marks distribution, topic weight matrix) in a readable summary format.
4. **Given** a course with no exam results yet, **When** the user views performance, **Then** they see a clear message that no exams have been completed, rather than empty or broken data.

---

### User Story 3 - Manage courses and browse blueprints (Priority: P2)

A student creates a new course (e.g., "CS301 - Data Structures"), sets the instructor, and links it to their account. They can rename or archive courses, browse their list of past papers, and view the extracted blueprints for each course.

**Why this priority**: Course management is foundational but less urgent than ingestion and dashboard — a user can use the system with a pre-seeded course.

**Independent Test**: Create a course via the API, verify it appears in the course list, then update its name and verify the change is reflected.

**Acceptance Scenarios**:

1. **Given** a registered user, **When** they create a new course with a name and optional instructor, **Then** the course is created and appears in their course list with a "no blueprint yet" status.
2. **Given** a course with an existing blueprint, **When** the user views the course's blueprint history, **Then** they see all versions of the blueprint with their version numbers, creation dates, and confidence scores.
3. **Given** a course the user owns, **When** they rename it or archive it, **Then** the change is persisted immediately and reflected in all subsequent views.
4. **Given** a course the user does not own (no access), **When** they attempt to view or modify it, **Then** the system rejects the request.

---

### User Story 4 - Register account and manage profile (Priority: P2)

A new user signs up via Clerk (external authentication provider). On first API call, the system creates a local user record synced to their Clerk identity. The user can update their display name and preferences.

**Why this priority**: Authentication gates all other functionality. Using an external provider (Clerk) avoids building auth from scratch. Webhook sync ensures user records stay consistent.

**Independent Test**: Simulate a Clerk webhook for a new user; verify a local user record is created. Then call the profile endpoint and verify the user data matches.

**Acceptance Scenarios**:

1. **Given** a new Clerk user record is created, **When** the Clerk webhook fires, **Then** the system creates a local user record with the Clerk user ID and default preferences.
2. **Given** a Clerk user record is updated (name change), **When** the Clerk webhook fires, **Then** the local user record is updated to match.
3. **Given** a Clerk user record is deleted, **When** the Clerk webhook fires, **Then** the local user record is marked inactive (not hard-deleted, to preserve data integrity).
4. **Given** an unauthenticated request to any protected endpoint, **When** the request arrives, **Then** the system rejects it with an authentication error.
5. **Given** a valid Clerk JWT for an existing user, **When** they call a protected endpoint, **Then** the request is authorized and the user's identity is available to downstream logic.
6. **Given** a valid Clerk JWT for a user who does not yet have a local record, **When** they call a protected endpoint, **Then** the system creates the local user record lazily and proceeds.

---

### Edge Cases

- Upload of an unsupported file type (not PDF or PPTX) — rejected before any processing with a clear error message.
- Upload of a file exceeding size limit (e.g., >50MB) — rejected with a size-limit error.
- Concurrent upload of the same file by two users — both trigger processing; the second one detects the existing file via content hash and returns the existing tracking ID (idempotent).
- Course has no blueprint (no papers ingested yet) — dashboard shows "no blueprint available" rather than empty or error state.
- User has no courses — dashboard shows an empty state with a prompt to create or join a course.
- Clerk webhook arrives after the user has already been created lazily via their first API call — webhook is a no-op (upsert).
- Ingestion pipeline takes longer than expected (>10 minutes) — status continues to read "processing"; no timeout that deletes the paper.
- Multiple papers being processed simultaneously for the same course — serialized per course to prevent blueprint conflicts; one runs at a time, others queue.
- Past paper with no discernible instructor name — ingestion completes but the blueprint is flagged with "low confidence" due to missing instructor attribution.
- User attempts to DELETE a course that has papers and results — cascade is rejected; course is soft-archived instead (data preservation).
- Clerk JWT verification fails (expired token, invalid signature) — endpoint returns a clear authentication error, not an internal server error.
- Clerk webhook secret validation fails — webhook endpoint returns 401 and does not process the event.

## Requirements *(mandatory)*

### Functional Requirements

**User authentication and profile**

- **FR-001**: The system MUST integrate with Clerk as the sole authentication provider. All protected endpoints MUST validate Clerk-issued JWTs before processing requests. Clerk integration will be set up using Clerk's own tools and SDK.
- **FR-002**: The system MUST listen for Clerk webhooks (`user.created`, `user.updated`, `user.deleted`) using Clerk's webhook signing secret for verification. Deletion MUST soft-mark rather than hard-delete.
- **FR-003**: On receiving an authenticated request from a Clerk user ID not yet in the local database, the system MUST create the local record lazily before processing the request.
- **FR-004**: Users MUST be able to view and update their display name and notification preferences.

**Course management**

- **FR-005**: Users MUST be able to create, read, update, and soft-delete (archive) courses. Each course has a name and optionally links to an instructor.
- **FR-006**: Courses MUST be scoped to a single user. A user MUST NOT see or modify courses they do not own.
- **FR-007**: When a course is soft-deleted, all associated data (papers, blueprints, results) MUST remain intact for future unarchive.

**File upload and ingestion**

- **FR-008**: The system MUST accept file uploads (PDF, PPTX) via a multipart endpoint, stream the file to secure object storage, create a processing record with status "pending", and return a tracking identifier immediately.
- **FR-009**: The system MUST reject uploads of unsupported file types before any storage or processing occurs, with a clear error message.
- **FR-010**: The system MUST detect duplicate uploads (by content hash) and return the existing tracking identifier without re-processing.
- **FR-011**: File processing (text extraction, instructor alignment, chunking, embedding, blueprint extraction) MUST run asynchronously after upload. The upload endpoint MUST NOT block until processing completes.
- **FR-012**: The system MUST expose a status endpoint for each uploaded file: pending, processing, completed, or failed with a human-readable reason.
- **FR-013**: Processing of papers within the same course MUST be serialized — at most one blueprint-modifying run per course at a time. Subsequent uploads for the same course queue behind the active run.

**Dashboard and analytics**

- **FR-014**: The system MUST expose a dashboard summary endpoint that, for the authenticated user, returns per-course aggregates: paper count, blueprint version (or "none"), number of completed exams, and average score.
- **FR-015**: The system MUST expose a per-course performance endpoint that returns: aggregate score across all results, per-topic strength/weakness breakdown derived from evaluation data, and recent exam history.
- **FR-016**: The system MUST expose a per-course blueprint view endpoint that returns the latest blueprint's section layout, question types, marks distribution, topic weights, and confidence score in a readable format.
- **FR-017**: The system MUST expose an endpoint to list all past papers for a course with their processing status and timestamps.

**Data integrity and security**

- **FR-018**: The system MUST NOT expose raw LLM prompts, raw document text, or student answers in any API response. Dashboard analytics use aggregate/computed values only.
- **FR-019**: The system MUST validate all input data at API boundaries using schema validation, rejecting malformed input with descriptive errors.
- **FR-020**: Changes to course data (rename, archive) MUST be persisted durably and be immediately visible on subsequent reads.
- **FR-021**: Clerk webhook endpoints MUST validate the `svix` signed payload before processing to prevent unauthorized webhook calls.

**Performance**

- **FR-022**: Dashboard summary endpoints MUST respond in under 2 seconds for users with up to 10 courses and 100 total results.
- **FR-023**: Status polling endpoints MUST respond in under 500ms regardless of processing state.

### Key Entities

- **User**: A person using the platform. Has a Clerk identity (external), a local record with display name and preferences. Owns courses and results.
- **Course**: A named academic course (e.g., "CS301 - Data Structures"). Belongs to exactly one user. May link to one instructor. Has a collection of past papers, blueprints, and results.
- **Past Paper**: A file (PDF/PPTX) uploaded for a course. Tracks processing status (pending → processing → completed/failed) and the resulting document chunks. Links to a course.
- **Exam Blueprint**: A versioned structural fingerprint of how a course's instructor writes exams. Captures sections, question types, marks distribution, topic weights, and phrasing style. Updated when new papers are ingested.
- **Result**: The outcome of grading a completed exam session. Contains per-question scores and feedback, aggregate score, and weak-topic list. Scoped to a course and user.
- **Instructor**: A resolved professor identity. Courses may link to exactly one. Keyed by normalized name.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can upload a 10-page PDF past paper and see it reach "completed" status within 5 minutes without manual intervention.
- **SC-002**: A user can view their course dashboard and see all of: course list, blueprint summary (or "none"), paper count, and aggregate exam score within 2 seconds of requesting the page.
- **SC-003**: Duplicate file uploads are detected and rejected with the existing tracking ID in under 1 second, with no duplicate processing.
- **SC-004**: Unsupported file types and files exceeding the size limit are rejected with clear error messages before any storage occurs.
- **SC-005**: A user can create a course, rename it, and archive it with all changes immediately reflected on subsequent reads.
- **SC-006**: Clerk webhook events (user.created, user.updated, user.deleted) are processed within 5 seconds of receipt, keeping local user records consistent.
- **SC-007**: Every protected endpoint rejects unauthenticated requests; every authorized request resolves the correct user identity.
- **SC-008**: No API response ever contains raw LLM prompts, full document text, or student answers — only computed analytics and metadata are exposed.
- **SC-009**: The full test suite for both services runs without network access (excluding Clerk webhook integration tests, which require a live webhook target).
- **SC-010**: A user with 10 courses and 100 exam results can load their dashboard summary in under 2 seconds.

## Assumptions

- Clerk handles all frontend authentication UI (sign-up, sign-in, password reset, MFA). The services in this phase only validate Clerk-issued JWTs and handle webhooks for user sync.
- Clerk's Svix-based webhook signing is used for webhook endpoint security.
- The existing `ingest_course_file()`, `generate_exam()`, and `evaluate_submission()` pipelines from the agents library are complete and ready to be wired into service endpoints.
- File storage uses S3-compatible object storage with pre-signed URLs for secure file access.
- Async background processing uses lightweight in-process background tasks (no external task queue). For production, this can be upgraded to a dedicated queue.
- The Clerk secret key and webhook signing secret are provided via environment configuration, following the existing project approach to secrets management.

## Out of Scope

- Real-time exam session management (timer, auto-save, focus lockout) — deferred to Phase 3b.
- Clerk frontend components (sign-in UI, user management UI) — handled by Clerk's hosted pages or pre-built components.
- Admin/user management dashboard (user search, role management, analytics across all users).
- Batch upload of multiple files.
- Direct file download or streaming endpoints (files are processed server-side only).
- Webhook retry or dead-letter queue for failed Clerk webhooks.
