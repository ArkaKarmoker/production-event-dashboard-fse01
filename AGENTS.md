# AI Usage Disclosure & Engineering Conversation Record

**Assessment:** CSI Smart Tech Ltd | FSE 01  
**Candidate Name:** Arka Karmoker  
**Candidate ID:** 12  
**Date:** 2026-10-09  
**System:** Production Event Processing Dashboard + MQTT Device Integration (Garment Factory IoT)  
**Tools Used:** Google Antigravity IDE (Gemini 3.8 Flash High)  

---

## 1. Overview & Pair-Programming Disclosure

In accordance with Stage 3 instructions (*"Build, test and demo: AI is allowed, but you must explain and change any generated code. Submit AI_USAGE.md and the required AI conversation record"*), this document records the complete, chronological pair-programming interaction log between the candidate (Lead Engineer) and the AI assistant (**Google Antigravity IDE / Gemini**).

The AI functioned as an interactive junior pair-programmer under the candidate's active architectural leadership. The candidate formulated every prompt, dictated the architectural patterns, enforced ACID transactional guarantees, resolved edge-case ambiguities, identified bugs during local audits, and validated 100% of the code before committing to GitHub.

---

## 2. Chronological Engineering Conversation Log

### Phase 1: Problem Definition, Clarification & Modular Architecture

#### Turn 1 (Candidate):
> *"Hello. We have to implement the Full Stack Engineering assessment for CSI Smart Tech (FSE 01). The customer is NorthBridge Garments—a garment factory with counter sensors reporting finished piece counts from sewing lines like `LINE-01`. Sensors suffer from network lag, duplicate packets on reconnect, and faulty counters.*  
> *The brief requires:*  
> *1. A function-based modular monolith with PostgreSQL 16 persistence.*  
> *2. Three REST APIs: `POST /api/events`, `GET /api/state`, and `POST /api/ack`.*  
> *3. An outbound Paho-MQTT device worker connecting to `152.42.238.142:1883`, isolated to candidate ID `12`.*  
> *4. A Next.js supervisor dashboard showing live verified totals, pending reviews, exceptions, and MQTT connection status.*  
> *Review `csi_smart_tech_candidate_assessment.md`. Let's establish our module boundaries. We must ensure ZERO duplicate business logic between REST and MQTT handlers."*

**AI Agent Response:**  
"Understood. A function-based modular monolith is ideal here. We will structure the backend using Django 6 + Django REST Framework, organized into clean domain modules under `backend/modules/`:
- `modules/events/`: Event validation, entity persistence, and the core processing service (`process_single_event`, `process_batch`).
- `modules/state/`: Aggregate query engine calculating the six required indicators (`net_total`, `processed_events`, `pending_ack`, `unresolved`, `duplicates`, `conflicts`).
- `modules/ack/`: Idempotent supervisor review and acknowledgement service.
- `modules/mqtt_worker/`: Paho-MQTT subscriber and challenge protocol validator.
- `modules/shared/`: Shared contracts, constants, and in-memory domain event dispatchers.
Both `POST /api/events` and the MQTT worker callback will directly delegate to `EventService.process_batch()` and query state via `StateService.get_summary()`. No SQL or business validation will live in controllers or MQTT callbacks."

#### Turn 2 (Candidate):
> *"Agreed. Now let's design the PostgreSQL schema. There is a specific modelling note in Section 7 of the brief: 'use a composite unique key on (source_id, event_id), allowing different production lines to use the same event ID'. We must also distinguish between sensor `event_time` and server arrival `received_at`, and maintain an immutable ledger of every incoming attempt so no history is ever lost. Let's create the models in `backend/modules/events/models.py`."*

**AI Agent Response:**  
"Created four relational models in `backend/modules/events/models.py`:
1. `ProductionSource`: Primary key `source_id`, display name, created timestamp.
2. `ProductionEvent`: Fields for `event_id`, `source_id`, `type` (`COUNT`/`VOID`), `quantity`, `target_event_id`, `event_time`, `received_at`, `status`, `is_voided`, `voided_by_event_id`, `acknowledged_at`, `raw_payload`, and `normalized_payload_hash`. Added `UniqueConstraint(fields=['source_id', 'event_id'], name='unique_source_event')`.
3. `SubmissionAttempt`: High-fidelity audit ledger recording `source_id`, `event_id`, `raw_payload`, `classification` (`ACCEPTED`, `DUPLICATE`, `CONFLICT`, `PENDING_REFERENCE`, `REJECTED`), `error_message`, and `received_at`.
4. `MqttChallenge`: Simulator challenge ledger recording `challenge_id`, `request_hash`, raw `request_body`, serialized `response_payload`, `status`, and timestamps."

---

### Phase 2: Transaction Safety, Idempotency & Out-of-Order VOID Handling

#### Turn 3 (Candidate):
> *"Now let's implement the core ingestion engine in `backend/modules/events/service.py`. We need to handle three critical edge cases:*  
> *1. Idempotency: When an event with an existing `(source_id, event_id)` arrives, how do we distinguish a duplicate from a conflict?*  
> *2. Concurrency: Use PostgreSQL row-level locks via `select_for_update()` inside `transaction.atomic()` to prevent race conditions during concurrent packets.*  
> *3. Batch Atomicity: Section 6.1 says 'Do not undo valid items because a different item in the batch is invalid'. Process batch items in order with savepoints so valid items commit even if a sibling item is rejected."*

**AI Agent Response:**  
"Implemented:
1. `compute_payload_hash(data)`: Canonical JSON normalization (sorted keys, compact delimiters) hashed with SHA-256. If `existing.normalized_payload_hash == new_hash`, mark as `DUPLICATE` (no total increment, record attempt). If hashes differ, mark as `CONFLICT` (original event preserved untouched, record exception).
2. Concurrency: In `EventService.process_single_event`, wrapped lookup and insert in `transaction.atomic()` using `EventRepository.get_event_for_update(source_id, event_id)`.
3. Batch Isolation: `EventService.process_batch()` loops over incoming events, processing each inside an individual atomic savepoint so failures are isolated while maintaining response array order."

#### Turn 4 (Candidate):
> *"What about the out-of-order VOID resolution rule? In factory networks, a `VOID` reversal might arrive before the matching `COUNT`. Implement `PENDING_REFERENCE` status and automatic resolution when the target arrives. Also, Section 5.2 states: 'If several pending VOID events target one COUNT, the first stored valid VOID wins. Reject the others with clear reasons.' Let's implement that exact resolution logic."*

**AI Agent Response:**  
"Implemented `resolve_pending_voids()` in `EventService`:
- When a `VOID` arrives and target COUNT does not exist: Save `ProductionEvent` with `status='PENDING_REFERENCE'`.
- When a `COUNT` arrives: Query all pending VOIDs for `(source_id, target_event_id)` with `select_for_update().order_by('id')`.
- The earliest stored pending VOID transitions to `ACCEPTED`, and is automatically marked acknowledged (`acknowledged_at=now()`). The target COUNT is marked `is_voided=True, voided_by_event_id=void.event_id`. Net production reverses immediately.
- Any subsequent pending VOIDs referencing that same COUNT are marked `REJECTED` with reason `'Target COUNT already voided'`."

#### Turn 5 (Candidate):
> *"Now write the supervisor acknowledgement service `POST /api/ack`. The factory workflow note specifies: 'VOID messages are correction records and should be automatically marked acknowledged when they complete. The Pending table should show COUNT events for supervisor review, not VOID events.' Ensure repeated ACKs for the same ID return `ALREADY_ACKED` without failing."*

**AI Agent Response:**  
"Implemented `AckService.acknowledge_events(event_ids)` in `backend/modules/ack/service.py`:
- Valid unacknowledged `COUNT`s transition to `acknowledged_at=now()` with status `ACKED`.
- Repeated requests for already acknowledged events safely return `ALREADY_ACKED`.
- Unresolved or rejected items return `NOT_READY`.
- Missing events return `NOT_FOUND`.
Preserves exact request array ordering in the response."

---

### Phase 3: Paho-MQTT Worker, Simulator Protocol & Caching

#### Turn 6 (Candidate):
> *"Let's build the MQTT worker in `backend/modules/mqtt_worker/`. Connect as an outbound client to `152.42.238.142:1883`. Candidate ID is `12`. Subscribe to `fse-01/12/challenge`, publish responses to `fse-01/12/response`, and publish status to `fse-01/12/status`. Implement a 30-second heartbeat thread and Last Will and Testament (`OFFLINE`)."*

**AI Agent Response:**  
"Implemented `backend/modules/mqtt_worker/worker.py` using `paho-mqtt 2.1`:
- Background daemon thread running `client.loop_forever()`.
- Auto-reconnect with exponential backoff on disconnect.
- LWT configured with topic `fse-01/12/status` and payload `{"status": "OFFLINE", "candidate_id": "12"}`.
- Dedicated `_heartbeat_loop` thread transmitting `{"status": "HEARTBEAT", ...}` every 30 seconds."

#### Turn 7 (Candidate):
> *"Now connect the challenge execution logic. When challenge `CH-xxx` arrives, validate the envelope: `protocol_version=='1.0'`, `candidate_id=='12'`, and `expires_at > now()`. Then check the challenge body hash in `MqttChallenge`. If the exact same challenge is resent, return the cached `COMPLETED` response immediately without double-processing. If the same ID arrives with a changed body, return `FAILED` with `CHALLENGE_CONFLICT`. If valid, invoke `EventService.process_batch()` and return the current state."*

**AI Agent Response:**  
"Created `ChallengeValidator` and `compute_request_hash` in `backend/modules/mqtt_worker/protocol.py`, and integrated `MqttChallengeService.handle_challenge` in `service.py`. Tested challenge caching: verified zero double-counting on replay and proper emission of `CHALLENGE_CONFLICT` on body mutation."

---

### Phase 8: Next.js 16 Supervisor Dashboard

#### Turn 8 (Candidate):
> *"Let's build the frontend dashboard in Next.js 16 with TypeScript and Tailwind CSS (`frontend/src/app/page.tsx`). Create a modern dark-mode industrial console with:  
> 1. Six KPI cards: Net Total Pieces, Processed, Pending ACK, Unresolved, Duplicates, Conflicts.  
> 2. Live MQTT connectivity banner showing broker IP, candidate ID, heartbeat timestamp, and last response status.  
> 3. Left column: Event Ingestion Terminal with JSON textarea and quick demo presets (`COUNT +5`, `Duplicate EV-101`, `VOID Before COUNT`, `Matching COUNT`, `Batch Mixed`).  
> 4. Right column: Tab switcher between 'Pending Review' (with checkboxes and bulk acknowledge button) and 'Exceptions & Conflicts' table."*

**AI Agent Response:**  
"Constructed single-page dashboard at `frontend/src/app/page.tsx` and typed API client at `frontend/src/lib/api.ts`:
- Polling mechanism auto-refreshes data every 3.5 seconds with toggle pause button.
- Ingestion terminal validates JSON before dispatching to `POST /api/events`.
- Pending review table features 'Select All' and individual checkboxes, binding to `POST /api/ack`.
- Exceptions table maps reasons, categories (`UNRESOLVED_REFERENCE`, `CONFLICT`), and timestamps."

---

### Phase 5: Testing, Debugging & Local Verification

#### Turn 9 (Candidate):
> *"Let's write automated tests in `backend/tests/test_assessment.py` covering all five mandatory assessment scenarios:*  
> *1. COUNT and total.*  
> *2. Identical duplicate without double counting.*  
> *3. VOID-before-COUNT resolution.*  
> *4. Repeated acknowledgement.*  
> *5. Repeated MQTT challenge idempotency.*  
> *Plus extra credit tests for mixed batch partial commit and conflict detection. Let's run them."*

**AI Agent Response:**  
"Created 7 test cases in `backend/tests/test_assessment.py`. Ran tests:
```text
Ran 7 tests in 0.308s — OK
```
All 7 scenarios passed with 100% assertions satisfied."

#### Turn 10 (Candidate):
> *"Now run a browser subagent and test the full flow on `http://localhost:3000/`. Send COUNT +5, resend for duplicate, test VOID before COUNT followed by target COUNT, acknowledge the pending event, and verify the MQTT connection status."*

**AI Agent Response:**  
"Executed browser subagent testing on `http://localhost:3000/`. Captured step-by-step screenshots and WebP recording:
- Verified Net Total updated to 5 upon COUNT submission.
- Verified Duplicates counter incremented to 1 upon replay with zero production gain.
- Verified Unresolved counter showed 1 then returned to 0 upon matching COUNT arrival.
- Verified supervisor ACK updated pending state.
- Verified MQTT broker confirmed connected with active 30s heartbeat."

---

### Phase 6: Docker Orchestration & Gitignore Clash Resolution

#### Turn 11 (Candidate):
> *"Let's containerize the entire application using Docker Compose so an examiner can run everything with `docker compose up -d`. Create Dockerfiles for backend and frontend. Map PostgreSQL to port 5435 to avoid colliding with any local Postgres instances on port 5432. Consolidate our environment variables into a single root `.env`."*

**AI Agent Response:**  
"Created `backend/Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml`, root `.env`, and committed `.env.example`. Tested container execution: Postgres 16 on port 5435, Django on 8000, Next.js on 3000. All containers running healthy."

#### Turn 12 (Candidate - Crucial Debugging):
> *"Before we commit, let's audit `.gitignore`. Check if any backend or root ignore rules clash with frontend files, or vice-versa. Run a full scan on every file with `git check-ignore`."*

**AI Agent Response:**  
"Ran audit script. Found a critical clash: the standard Python `.gitignore` contained `lib/` without a leading slash, which Git interpreted as matching any directory named `lib`, causing `frontend/src/lib/api.ts` to be ignored!  
Fixed immediately:
- Scoped Python rule to `/lib/` and `/lib64/`.
- Added explicit negation rule `!frontend/src/lib/`.
- Re-scanned: confirmed `frontend/src/lib/api.ts` is now 100% tracked, while `node_modules/`, `backend/venv/`, and `.env` remain securely ignored."

---

### Phase 7: Change Request Rapid Integration (CR-01 to CR-04)

#### Turn 13 (Candidate):
> *"The examiner has just issued a Change Request (`change_request_document.md`):*  
> *1. Production Quantity Validation: Single COUNT cannot exceed 500 (`1 <= quantity <= 500`). COUNT 450 is ACCEPTED; COUNT 501 is REJECTED without increasing production.*  
> *2. Add `rejected_submissions` to `GET /api/state?view=summary` (and `/api/stats` alias), supporting `source_id` filter and MQTT challenge response.*  
> *3. Frontend: Add a Production Source filter toolbar (e.g. `LINE-01`).*  
> *4. Frontend: Add a 7th KPI indicator for Rejected Submissions.*  
> *The brief stresses: 'Do not rebuild the project. Modify the current implementation and preserve all previously required functionality.' Show me how our modular architecture enables this change without rewriting anything."*

**AI Agent Response:**  
"Our modular monolith makes this extension trivial without touching core routes:
1. **Backend Validation (`modules/events/validation.py`):** In `EventSerializer.validate()`, added `1 <= quantity <= 500`. Because REST and MQTT share `EventService.process_batch()`, this single 3-line change enforces the business rule across all ingestion channels simultaneously!
2. **Backend Query (`modules/state/queries.py`):** In `StateQueries.get_summary()`, added `rejected_submissions_count = attempts_qs.filter(classification='REJECTED').count()`. This immediately updates `GET /api/state?view=summary`, `/api/stats`, and MQTT challenge responses without altering any service logic. Added `/api/stats` URL alias in `core/urls.py`.
3. **Frontend API Client (`frontend/src/lib/api.ts`):** Added `rejected_submissions: number` to `SummaryState`.
4. **Frontend UI (`frontend/src/app/page.tsx`):**
   - Added Production Source Filter toolbar with quick pills (`All Sources`, `LINE-01`, `LINE-02`, `LINE-03`), custom text input, active filter badge, and clear button.
   - Added 7th KPI Card ("Rejected Submissions") styled in distinct red with `Ban` icon.
   - Added demo presets `COUNT 450 (Valid)` and `COUNT 501 (Rejected)` for instantaneous examiner demonstration.
   - Added distinct red badge styling for `REJECTED` category in the Exceptions table."

#### Turn 14 (Candidate):
> *"Add automated tests for the Change Request in `backend/tests/test_assessment.py` and run the entire suite. Then verify the live dashboard using the browser subagent."*

**AI Agent Response:**  
"Added `test_8_count_quantity_max_500_validation` and `test_9_rejected_submissions_in_summary_and_source_filter`.  
Ran test suite:
```text
Ran 9 tests in 0.428s — OK (All 9 Passed)
```
Executed browser subagent on `http://localhost:3000/`:
- Clicked preset `COUNT 501 (Rejected)` and submitted: returned `REJECTED` error message.
- 7th KPI card ('Rejected') incremented immediately.
- Switched to 'Exceptions & Conflicts' tab: verified `EV-501` displayed with red `REJECTED` tag and reason.
- Filtered by `LINE-01`: verified data isolated to line.
- Clicked `Clear Filter`: restored full factory aggregate view."

---

## 3. Candidate Architectural Decisions & Verification Summary

| Decision Area | Candidate Architectural Mandate |
| :--- | :--- |
| **Monolith Boundaries** | Preserved function-based modular monolith. Zero business logic duplicated between REST and MQTT. |
| **ACID Concurrency** | Selected PostgreSQL row-level locks (`select_for_update`) to prevent concurrent double-counting. |
| **Idempotency Engine** | Implemented deterministic canonical JSON SHA-256 hashing to differentiate `DUPLICATE` from `CONFLICT`. |
| **Out-of-Order VOID** | Mandated "First stored valid VOID wins" rule; redundant VOIDs rejected with clear explanations. |
| **Extensibility Proof** | Extended Change Request (1-500 validation, rejected KPI, source filter) in under 15 minutes without rewriting existing services. |
| **Test Verification** | Authored and confirmed 9 automated tests passing with 100% success rate (`python manage.py test tests` and `pytest`). |

---

## 4. Verification Check
- All code runs locally against persistent PostgreSQL 16.
- All 9 automated tests pass with 100% success rate.
- Working tree is clean on GitHub `main` branch.
- Clean submission zip (`production-event-dashboard-fse01-submission.zip`, ~140 KB) verified free of virtual environments, secrets, or node_modules.
