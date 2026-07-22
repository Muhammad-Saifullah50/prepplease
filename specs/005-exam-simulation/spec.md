# Feature Specification: Exam Simulation Service

**Feature Branch**: `005-exam-simulation`
**Created**: 2026-07-22
**Status**: Draft
**Input**: User description: "Exam Simulation Service (Feature 15): a service that turns a stored generated mock exam into a live, timed, monitored exam attempt, then hands finished answers to the existing evaluation pipeline for grading. Also includes extracting a real exam duration from past papers and threading it through the blueprint and generation steps so simulated exams use an authentic time limit."

## Clarifications

### Session 2026-07-22

- Q: FR-014/015 reference a "configurable" focus-violation limit before lockout. What should the default limit be (used when a course has no override)? → A: 3 violations
- Q: FR-021 requires a "reasonable default" time limit when no duration can be extracted for an exam. What should that default be? → A: 120 minutes
- Q: FR-005 says the system must "continuously accept and save" in-progress answers. How should answer-saving be triggered from the client? → A: Debounced on change (save shortly after an answer edit stops changing)
- Q: For focus-violation tracking (US2), should rapid/flickering focus-loss events be coalesced, or does every reported event count separately? → A: Every reported event counts separately, no coalescing
- Q: FR-004/FR-014 require the client to see remaining time and focus-violation warnings as they occur. How should this be delivered to the client? → A: Client polling (periodic REST requests for attempt state)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Take a timed mock exam (Priority: P1)

A student starts a mock exam that was generated for their course. The system presents the exam questions, starts an authoritative countdown based on the real time limit those exams are normally given, and keeps the student's answers saved as they work — even if their browser refreshes or their connection blips. When time runs out, the exam is automatically finished and sent off for grading.

**Why this priority**: This is the core value of the feature — without a live, timed attempt, a generated exam is just static content. Nothing else in this feature matters if a student can't actually sit the exam under realistic conditions.

**Independent Test**: Start an exam attempt from a generated exam; confirm the questions and a countdown appear; save some answers, reload, and confirm the answers and remaining time are still there; let the countdown reach zero and confirm the attempt is automatically finished and queued for grading.

**Acceptance Scenarios**:

1. **Given** a student has a generated mock exam available for their course, **When** they start an attempt, **Then** the system creates a live attempt, shows the questions, and reports a countdown based on the exam's real time limit.
2. **Given** a student is partway through an attempt, **When** they answer questions over time, **Then** their answers are continuously saved so no work is lost if their session is interrupted.
3. **Given** a student's browser reloads or reconnects mid-attempt, **When** they return to the exam, **Then** they see their previously saved answers and the correct remaining time (not a reset timer).
4. **Given** a student's countdown reaches zero, **When** the deadline passes, **Then** the attempt is automatically finished with whatever answers were saved, and grading begins without further action from the student.
5. **Given** a student finishes early, **When** they submit their attempt manually, **Then** the attempt is finished immediately, grading begins, and the student receives prompt confirmation that grading is underway (not the final grade itself).

---

### User Story 2 - Exam integrity: focus-violation lockout (Priority: P1)

While taking a timed exam, a student who repeatedly switches away from the exam (e.g., to another browser tab or application) is warned, and after enough violations, their attempt is locked out and automatically finished — preserving whatever answers they had saved at that point.

**Why this priority**: A mock exam that can be trivially cheated on (open answers in another tab) loses most of its value as practice for the real thing. Integrity monitoring is what makes the timed attempt trustworthy, so it ships alongside the core attempt flow.

**Independent Test**: Start an attempt and report focus-loss events one at a time; confirm the student receives a warning for each violation under the limit, and confirm that crossing the limit locks the attempt, ends it, and starts grading.

**Acceptance Scenarios**:

1. **Given** a student is mid-attempt, **When** they briefly lose focus on the exam (e.g., switch tabs) one time, **Then** the system records a warning and the attempt continues normally.
2. **Given** a student has accumulated fewer violations than the allowed limit, **When** they check their attempt status, **Then** they can see how many warnings they have received and how many remain before lockout.
3. **Given** a student crosses the allowed number of focus violations, **When** the limit is exceeded, **Then** the attempt is immediately and permanently locked out, finished with the answers saved so far, and sent for grading — the student cannot resume it.

---

### User Story 3 - Exam duration reflects real exam conditions (Priority: P2)

When a mock exam is generated for a course, the time limit given to students matches what that professor's real exams actually allow (e.g., "3 hours"), rather than an arbitrary guess — so timed practice is realistic.

**Why this priority**: This is what makes the timer in User Story 1 meaningful rather than arbitrary. It depends on upstream extraction and blueprint work, so it is scoped as a supporting story rather than the primary flow.

**Independent Test**: Ingest a set of past papers that each state a time limit; confirm the resulting course blueprint reflects a duration consistent with those papers, and confirm a mock exam generated from that blueprint carries that duration through to a live attempt.

**Acceptance Scenarios**:

1. **Given** a past paper states a time limit (e.g., "Time allowed: 3 hours"), **When** the paper is processed, **Then** the extracted time limit is captured alongside the paper's other structural details.
2. **Given** a course's blueprint is built from multiple past papers with different stated time limits, **When** the blueprint is produced, **Then** it reflects the longest stated time limit among those papers (never shorter than any real exam of that type).
3. **Given** a mock exam is generated from a blueprint that has a known time limit, **When** a student starts an attempt on that exam, **Then** the attempt's countdown is set to that time limit.
4. **Given** a mock exam has no discoverable time limit (no source paper stated one), **When** a student starts an attempt, **Then** the attempt still gets a reasonable default time limit rather than failing to start.

---

### Edge Cases

- A student tries to start a second exam attempt while one is already in progress — rejected, with a pointer to the existing in-progress attempt.
- A student's saved answers include a question that no longer exists on the exam (shouldn't normally happen, but the buffer is defensive) — extra answers are ignored at grading time.
- Two different requests to finish the same attempt arrive at nearly the same time (e.g., manual submit and deadline expiry overlap) — the attempt is finished exactly once; the second request receives the already-finished result state, not an error or duplicate grading.
- A student's countdown has already reached zero, but they submit manually anyway — treated as a normal expiry, not a manual submission, since the deadline already passed.
- A student attempts to view or act on another student's exam attempt — rejected.
- A student's attempt is interrupted long enough that the live saved-answer state could be lost (e.g., an extended outage) — the student cannot resume answering, but no exam attempt is left in limbo indefinitely; the last durably known state stands.
- A past paper states a time limit in an unusual format (e.g., "90 min" vs "1.5 hours" vs "Time: 3hrs") — extraction normalizes reasonable formats to a single unit; if it cannot confidently parse a limit, it is treated as no stated limit for that paper rather than a wrong guess.
- Grading fails or errors out after an attempt is finished — the attempt still shows as finished/submitted to the student; the failure is handled by the grading process, not surfaced as an exam-taking error.

## Requirements *(mandatory)*

### Functional Requirements

**Attempt lifecycle**

- **FR-001**: System MUST allow a student to start a live attempt from a generated mock exam, presenting the exam's questions without exposing grading/rubric information.
- **FR-002**: System MUST prevent a student from having more than one active attempt at a time; a request to start a new attempt while one is active MUST be rejected with a reference to the existing active attempt.
- **FR-003**: System MUST track, per attempt, an authoritative countdown deadline that the student cannot alter from the client side.
- **FR-004**: System MUST allow a student to retrieve the current state of their active attempt (questions, saved answers, remaining time, status, and any focus warnings) via client polling, so an interrupted session can resume without data loss.
- **FR-005**: System MUST continuously accept and save a student's in-progress answers throughout an attempt, with the client saving each answer a short debounce interval after the student stops editing it (rather than on every keystroke or only at explicit save points).
- **FR-006**: System MUST allow a student to manually finish (submit) an active attempt at any time before the deadline.
- **FR-007**: System MUST automatically finish an attempt the moment its deadline passes, using whatever answers were saved, even without an explicit action from the student.
- **FR-008**: System MUST treat a manual submission that arrives after the deadline has already passed as an automatic (deadline) completion, not a manual one.
- **FR-009**: System MUST ensure an attempt can only be finished once; concurrent or repeated finish requests MUST resolve to the same single finished outcome rather than duplicating the result.
- **FR-010**: System MUST begin grading automatically whenever an attempt finishes (manually, by deadline, or by lockout), without requiring further student action.
- **FR-011**: System MUST respond promptly to a finish request confirming the attempt is finished and grading has begun, without making the student wait for grading to complete.
- **FR-012**: System MUST make the final grade available to the student through the existing course results/dashboard experience once grading completes, rather than through the exam attempt itself.

**Exam integrity**

- **FR-013**: System MUST accept reports of focus-loss events (e.g., switching away from the exam) during an active attempt.
- **FR-014**: System MUST track a running count of focus violations per attempt and communicate the count (and warnings) back to the student via client polling as they occur, up to a configurable limit (default: 3 violations before lockout). Every reported focus-loss event counts as a separate violation; events are not coalesced or debounced.
- **FR-015**: System MUST permanently lock out and finish an attempt once its focus violations reach the configured limit, using whatever answers were saved at that point, and MUST NOT allow the attempt to resume afterward.

**Access control**

- **FR-016**: System MUST ensure a student can only start, view, or act on their own exam attempts; requests targeting another student's attempt MUST be rejected.

**Exam duration extraction**

- **FR-017**: System MUST extract a stated time limit from a past paper's content when one is present, normalizing common formats to a single unit of time.
- **FR-018**: System MUST treat a past paper with no confidently recognizable time limit as having no stated time limit, rather than guessing an incorrect value.
- **FR-019**: When a course blueprint is built from multiple past papers with differing stated time limits, system MUST use the longest stated time limit among them as the blueprint's time limit.
- **FR-020**: System MUST carry a blueprint's known time limit through to any mock exam generated from that blueprint.
- **FR-021**: System MUST apply a reasonable default time limit of 120 minutes to a live attempt when the generated exam has no known time limit, so an attempt can still start.

### Key Entities *(include if feature involves data)*

- **Exam Attempt**: One student's live, timed run at a specific generated mock exam. Tracks who is taking it, which exam and course it belongs to, the questions being presented, the student's in-progress and final answers, its status (active, finished by submission, finished by expiry, or finished by lockout), when it started and ended, and how many focus violations it has accumulated. Relates to a Generated Mock Exam (source) and a Student (owner).
- **Generated Mock Exam**: An existing original exam produced for a course, including its questions, grading rubric, and (per this feature) a known or unknown time limit. Existing entity; this feature adds a time-limit attribute and is otherwise a read-only source for starting attempts.
- **Course Blueprint**: An existing structural fingerprint of how a professor's exams are put together, built from multiple past papers. This feature adds a derived time-limit attribute, computed from the time limits found on its source papers.
- **Past Paper**: An existing ingested source document. This feature adds an extracted, optional time-limit attribute captured during processing.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A student can go from "start attempt" to seeing exam questions and a running countdown in under 3 seconds.
- **SC-002**: No attempt loses previously saved answers across a page reload or brief connectivity interruption — resumed attempts always reflect the last successfully saved answers.
- **SC-003**: 100% of attempts that reach their deadline are automatically finished and queued for grading within a few seconds of expiry, with no attempt left indefinitely "active" past its deadline.
- **SC-004**: 100% of attempts that cross the focus-violation limit are locked out and queued for grading, and no locked-out attempt can subsequently be resumed.
- **SC-005**: A manual submission is acknowledged to the student in under 2 seconds, independent of how long grading itself takes.
- **SC-006**: For courses with past papers stating a time limit, at least 95% of newly generated mock exams carry a real (non-default) extracted time limit rather than falling back to the default.
- **SC-007**: No two overlapping finish requests for the same attempt (manual submit racing deadline expiry, etc.) ever produce two different grading outcomes for one attempt.
