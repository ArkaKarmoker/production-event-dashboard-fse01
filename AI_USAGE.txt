# AI Usage Disclosure & Engineering Conversation Record

**Assessment:** CSI Smart Tech Ltd | FSE 01  
**Candidate Name:** Arka Karmoker  
**Candidate ID:** 12  
**Date:** 2026-10-09  
**System:** Production Event Processing Dashboard + MQTT Device Integration (Garment Factory IoT)  

---

## 1. Overview & Tooling Disclosure

In accordance with Stage 3 instructions (*"Build, test and demo: AI is allowed, but you must explain and change any generated code. Submit AI_USAGE.md and the required AI conversation record"*), this document records the complete chronological pair-programming interaction log between the candidate and the AI assistant (**Google Antigravity IDE / Gemini 3.8 Flash**).

The AI served strictly as an interactive pair-programmer. All architectural decisions, transactional constraints, domain models, edge-case assumptions, and code verifications were directed, reviewed, and finalized by the candidate.

---

## 2. Chronological Prompt & Engineering Conversation Log

### Phase 1: Problem Understanding, Domain Modeling & Architecture

#### Prompt 1.1 (Candidate Directive):
> *"We need to build the NorthBridge Garments Production Event Processing Dashboard for CSI Smart Tech FSE 01. The factory has counter devices reporting piece counts, late arrivals, duplicate transmissions, and sensor errors. The solution must follow a function-based modular monolith with PostgreSQL 16 persistence, 3 REST APIs (`POST /api/events`, `GET /api/state`, `POST /api/ack`), an outbound Paho-MQTT device worker, and a Next.js supervisor dashboard. Review `csi_smart_tech_candidate_assessment.md` and outline the architectural boundaries."*

**AI Response & Action:**  
Analyzed the customer scenario and entities. Proposed a Django 6 + Django REST Framework modular monolith architecture under `backend/modules/` (`events`, `state`, `ack`, `mqtt_worker`, `shared`) to guarantee strict encapsulation and ensure zero logic duplication between REST controllers and MQTT subscribers.

#### Prompt 1.2 (Candidate Directive):
> *"Let's design the relational data model in PostgreSQL. We need tables for sources, canonical production events, immutable submission attempts, and MQTT challenges. Note the brief requirement: use a composite unique constraint on `(source_id, event_id)` so separate factory lines can isolate event namespaces. Ensure timestamps distinguish sensor `event_time` from server `received_at`."*

**AI Response & Action:**  
Implemented Django ORM models in `backend/modules/events/models.py`:
- `ProductionSource`: `source_id` primary key, line display name.
- `ProductionEvent`: `(source_id, event_id)` composite unique constraint, status (`ACCEPTED`, `PENDING_REFERENCE`), `normalized_payload_hash`, `is_voided`, and `acknowledged_at`.
- `SubmissionAttempt`: Immutable audit log capturing all raw payloads, classifications (`DUPLICATE`, `CONFLICT`, `REJECTED`), and arrival timestamps.
- `MqttChallenge`: Challenge ledger tracking request digests, responses, and execution statuses.

---

### Phase 2: Transaction Safety, Idempotency & Out-of-Order VOID Resolution

#### Prompt 2.1 (Candidate Directive):
> *"Explain how we will handle idempotency and concurrency. If an identical event arrives twice, it must be marked `DUPLICATE` and never double-count. If the payload is modified under the same event ID, it must be flagged as `CONFLICT`. Furthermore, use PostgreSQL row-level locks to prevent race conditions during high-volume or concurrent submissions."*

**AI Response & Action:**  
Implemented deterministic SHA-256 payload normalization (`compute_payload_hash`) in `backend/modules/events/models.py`. In `EventService.process_single_event`, wrapped ingestion in `transaction.atomic()` with `select_for_update()`:
- Matching hash ➔ Recorded as `DUPLICATE` in attempts; total does not increment.
- Differing hash ➔ Recorded as `CONFLICT` in attempts; original event remains untouched.

#### Prompt 2.2 (Candidate Directive):
> *"Now implement the out-of-order VOID resolution rule. In IoT networks, a `VOID` reversal might arrive before the matching `COUNT`. It must be saved as `PENDING_REFERENCE`. When the target `COUNT` arrives later, it must automatically resolve the pending VOID, reversing the count. Also, if multiple pending VOIDs target the same COUNT, enforce the rule: 'The first stored valid VOID wins; reject the others with clear reasons'."*

**AI Response & Action:**  
Implemented `resolve_pending_voids()` in `EventService`. When a `COUNT` event is inserted:
1. Queries pending VOIDs for `(source_id, target_event_id)` with `select_for_update()`.
2. Transitions the earliest valid VOID to `ACCEPTED` and auto-acknowledges it.
3. Marks the target COUNT `is_voided = True`.
4. Updates any secondary redundant pending VOIDs to `REJECTED` with message `"Target COUNT already voided"`.

#### Prompt 2.3 (Candidate Directive):
> *"Implement the supervisor acknowledgement API `POST /api/ack`. Remember: VOID events are system corrections and should be auto-acknowledged upon completion. The supervisor acknowledgement API should safely acknowledge unreviewed COUNT events. Repeated requests for the same ID must return `ALREADY_ACKED` without failing."*

**AI Response & Action:**  
Built `AckService.acknowledge_events` in `backend/modules/ack/service.py`. Enforced safe idempotency returning ordered results: `ACKED`, `ALREADY_ACKED`, `NOT_READY`, and `NOT_FOUND`.

---

### Phase 3: Paho-MQTT Worker Integration & Replay Protection

#### Prompt 3.1 (Candidate Directive):
> *"Set up the outbound MQTT worker connecting to the examiner simulator at `152.42.238.142:1883`. Topic isolation must use candidate ID `12`: subscribe to `fse-01/12/challenge`, publish responses to `fse-01/12/response`, and send status to `fse-01/12/status`. Crucially, ensure the worker reuses the exact same `EventService.process_batch` and `StateService.get_summary` functions as the REST API."*

**AI Response & Action:**  
Built `backend/modules/mqtt_worker/`:
- `worker.py`: Paho-MQTT 2.1 client with automatic exponential backoff reconnection, 30-second heartbeat thread, and Last Will & Testament (`OFFLINE`).
- `service.py`: `MqttChallengeService` delegates event processing directly to `EventService.process_batch()` and queries state via `StateService.get_summary()`.

#### Prompt 3.2 (Candidate Directive):
> *"Add challenge envelope validation and replay caching. Reject expired challenges or mismatched candidate IDs. If the simulator sends an identical challenge repeatedly, return the saved response without double-processing events. If the payload differs under the same challenge ID, return `FAILED` with `CHALLENGE_CONFLICT`."*

**AI Response & Action:**  
Built `ChallengeValidator` and `compute_request_hash` in `backend/modules/mqtt_worker/protocol.py`. Integrated database persistence in `MqttChallenge` table to verify request digests before event execution.

---

### Phase 4: Frontend Supervisor Dashboard Development

#### Prompt 4.1 (Candidate Directive):
> *"Build a single-page supervisor dashboard using Next.js 16, TypeScript, and Tailwind CSS. Display the 6 required indicators: Net Total, Processed, Pending ACK, Unresolved, Duplicates, and Conflicts. Include an Event Ingestion Terminal with demo presets, a Pending Review table with bulk acknowledgement checkboxes, an Exceptions/Conflicts table, and a live MQTT connectivity badge."*

**AI Response & Action:**  
Constructed responsive dashboard in `frontend/src/app/page.tsx` with:
- 6 KPI cards with live polling.
- Ingestion terminal supporting raw JSON or one-click preset buttons (`COUNT +5`, `Duplicate EV-101`, `VOID Before COUNT`, `Matching COUNT`, `Batch Mixed`).
- Review table with multi-select checkboxes and batch acknowledgement dispatch.
- Real-time MQTT monitoring showing broker IP, candidate ID, heartbeat timestamps, and last response status.

---

### Phase 5: Automated Testing & Browser Validation

#### Prompt 5.1 (Candidate Directive):
> *"Write automated tests in `backend/tests/test_assessment.py` covering all 5 mandatory scenarios: 1) COUNT addition and total, 2) identical duplicate without double counting, 3) VOID-before-COUNT resolution, 4) repeated acknowledgement idempotency, and 5) repeated MQTT challenge replay cache. Add extra reliability tests for mixed batches and conflict attempts."*

**AI Response & Action:**  
Created 7 comprehensive test methods. Executed via `python manage.py test tests` and `pytest`: 7/7 tests passed with 100% success rate.

#### Prompt 5.2 (Candidate Directive):
> *"Open a browser subagent and perform end-to-end testing of every user story on the live dashboard: verify KPI updates on COUNT, duplicate prevention, out-of-order VOID resolution, bulk supervisor ACK, and MQTT connection status."*

**AI Response & Action:**  
Launched browser subagent to interactively execute all steps on `http://localhost:3000/`. Captured screenshots and WebP execution recordings verifying accurate state updates and UI responsiveness.

---

### Phase 6: Docker Orchestration, Environment Consolidation & Gitignore Debugging

#### Prompt 6.1 (Candidate Directive):
> *"Set up Docker Compose to run PostgreSQL 16, Django backend, and Next.js frontend with a single command. Map PostgreSQL to port 5435 to prevent conflicts with local instances. Consolidate environment variables into a single root `.env` and provide a clean `.env.example`."*

**AI Response & Action:**  
Authored `backend/Dockerfile`, `frontend/Dockerfile`, and `docker-compose.yml`. Configured unified `.env` loading and committed `.env.example`.

#### Prompt 6.2 (Candidate Directive):
> *"Audit `.gitignore` across root and frontend. Is there any clash where backend/root rules prevent important frontend files from being tracked, or vice-versa? Perform a deep scan of every file with `git check-ignore`."*

**AI Response & Action:**  
Executed script testing all files. Discovered that a generic Python rule `lib/` in root `.gitignore` was accidentally ignoring `frontend/src/lib/api.ts`. Fixed immediately by scoping to `/lib/` and adding `!frontend/src/lib/`. Confirmed all source code files tracked cleanly while keeping `.env` and node_modules ignored.

---

### Phase 7: Change Request Rapid Extension (CR-01 to CR-04)

#### Prompt 7.1 (Candidate Directive):
> *"The examiner has issued a Change Request (`change_request_document.md`):*
> *1. Quantity Validation: Single COUNT cannot exceed 500 (`1 <= quantity <= 500`). COUNT 450 is ACCEPTED; COUNT 501 is REJECTED without increasing production.*
> *2. Add `rejected_submissions` to `GET /api/state?view=summary` (and `/api/stats` alias), supporting `source_id` filter and MQTT challenge response.*
> *3. Frontend: Add a Production Source filter toolbar (e.g., `LINE-01`).*
> *4. Frontend: Add a 7th KPI indicator for Rejected Submissions.*
> *Implement these modifications cleanly while preserving our modular architecture and existing functionality."*

**AI Response & Action:**  
Executed modifications across the modular monolith:
1. **Backend Validation (`modules/events/validation.py`):** Added `1 <= quantity <= 500` validation in `EventSerializer`. Shared by REST and MQTT.
2. **Backend Query (`modules/state/queries.py`):** Extended `StateQueries.get_summary()` to count `submission_attempts.filter(classification='REJECTED')`. Added `/api/stats` alias in `backend/core/urls.py`.
3. **Frontend API Client (`frontend/src/lib/api.ts`):** Added `rejected_submissions` to `SummaryState`.
4. **Frontend UI (`frontend/src/app/page.tsx`):**
   - Added Production Source Filter toolbar with quick pills (`All Sources`, `LINE-01`, `LINE-02`, `LINE-03`), custom text input, active badge, and clear button.
   - Added 7th KPI Card ("Rejected Submissions") styled in distinct red with `Ban` icon.
   - Added demo presets: `COUNT 450 (Valid)` and `COUNT 501 (Rejected)`.
   - Styled `REJECTED` category in Exceptions table with a distinct red badge.

#### Prompt 7.2 (Candidate Directive):
> *"Update the automated test suite with tests for the Change Request requirements and verify everything locally and in the browser."*

**AI Response & Action:**  
Added `test_8_count_quantity_max_500_validation` and `test_9_rejected_submissions_in_summary_and_source_filter` to `backend/tests/test_assessment.py`. Ran test suite: all 9 tests passed in 0.428s.  
Launched browser subagent on `http://localhost:3000/`: submitted `COUNT 501`, verified rejection message, verified 7th KPI incremented, verified Exceptions table entry, and tested `LINE-01` source filtering.

---

## 3. Human Architecture Decisions & Code Verification Summary

| Area | Candidate Decision & Verification |
| :--- | :--- |
| **Monolith Architecture** | Enforced function-based modular monolith with strict module boundaries. Prohibited code duplication between REST routes and MQTT handlers. |
| **Transaction Safety** | Selected PostgreSQL row-level locks (`select_for_update`) to guarantee ACID transaction boundaries under concurrent loads. |
| **Idempotency Strategy** | Designed deterministic canonical JSON SHA-256 hashing to differentiate `DUPLICATE` from `CONFLICT`. |
| **Out-of-Order VOID** | Formulated "First stored valid VOID wins" policy; secondary VOIDs rejected with clear reasoning. |
| **Change Request Integration** | Extended existing validation and query layers without rewriting application structure, demonstrating architecture extensibility. |
| **Test Verification** | Authored and confirmed 9 automated tests passing with 100% success rate. |

---

## 4. Verification Check
- All code runs locally against persistent PostgreSQL 16.
- All 9 automated tests pass with 100% success rate (`pytest` & `python manage.py test tests`).
- Codebase is clean, well-documented, and ready for examiner live walkthrough and modification.
