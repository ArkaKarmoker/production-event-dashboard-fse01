# CSI Smart Tech - FSE 01 Technical Explanation

**Candidate Name:** Arka Karmoker  
**Candidate ID:** 12  
**System:** Production Event Processing Dashboard + MQTT Device Integration (Garment Factory IoT)

---

## 1. Entity Model and Relational Design

The system implements durable, relational storage backed by PostgreSQL. The primary entities are modeled to guarantee full auditability, zero data loss, and ACID transactional guarantees:

1. **`production_sources` (`ProductionSource`):**
   - Represents physical sewing or finishing lines (e.g., `LINE-01`).
   - Primary key: `source_id` (string).
   - Display name and creation timestamp.

2. **`production_events` (`ProductionEvent`):**
   - Represents the canonical logical event ledger (`COUNT` or `VOID`).
   - Fields: `event_id`, `source_id`, `type`, `quantity`, `target_event_id`, `event_time`, `received_at`, `status`, `is_voided`, `voided_by_event_id`, `acknowledged_at`, `acknowledged_by`, `raw_payload`, `normalized_payload_hash`.
   - **Composite Constraint:** `UniqueConstraint(fields=['source_id', 'event_id'])` ensures production lines can isolate event namespaces or share global uniqueness.
   - Separate timestamps: `event_time` (sensor time) vs `received_at` (server arrival time).

3. **`submission_attempts` (`SubmissionAttempt`):**
   - High-fidelity immutable audit log storing **every** incoming request (valid, duplicate, conflict, pending reference, or malformed/rejected).
   - Records `source_id`, `event_id`, `raw_payload`, `classification`, `error_message`, and `received_at`.
   - Never deletes rows; survives server restart and preserves historical attempts for compliance and debugging.

4. **`mqtt_challenges` (`MqttChallenge`):**
   - Dedicated ledger for simulator verification challenges.
   - Primary key: `challenge_id`.
   - Tracks `request_hash`, raw `request_body`, serialized `response_payload`, `status`, and timestamps (`received_at`, `processed_at`, `expires_at`).

---

## 2. Module & Function Boundaries (Modular Monolith)

The backend is organized as a function-based modular monolith where all modules reside within a single application deployment, single database, and strict boundary contracts:

```text
src/
  modules/events/        # Validation, EventService, Repository, Models
  modules/state/         # StateQueries, StateService, Views
  modules/ack/           # AckService, Views
  modules/mqtt_worker/   # Protocol, ChallengeValidator, Paho-MQTT Client, Worker
  modules/shared/        # Contracts, Constants, Domain Event Bus
```

### Shared Event Processing Function:
Crucially, **no business logic is duplicated** between REST routes and MQTT handlers:
- Both `POST /api/events` and the MQTT worker callback delegate to:
  ```python
  EventService.process_batch(events) -> EventService.process_single_event(event)
  ```
- Both query the same state calculation engine:
  ```python
  StateService.get_summary(source_id) -> StateQueries.get_summary()
  ```

---

## 3. Transaction, Concurrency & Idempotency Strategy

### 3.1 Idempotency (DUPLICATE vs CONFLICT):
When an event arrives with an `event_id` that already exists for that `source_id`:
1. The payload is deterministically normalized into a canonical JSON string (sorted keys, compact delimiters) and hashed via SHA-256.
2. If `normalized_payload_hash == existing.normalized_payload_hash`:
   - Marked **`DUPLICATE`**.
   - Recorded in `submission_attempts`.
   - Production counter is **not incremented**.
3. If hashes differ:
   - Marked **`CONFLICT`**.
   - Recorded in `submission_attempts` with details.
   - Original canonical event remains completely preserved without alteration.

### 3.2 Concurrency & Row-Level Locking:
- Competing requests on the same `(source_id, event_id)` or target COUNT are guarded by `transaction.atomic()` and PostgreSQL row-level locks via `select_for_update()`.
- Batch imports are processed with per-item atomic savepoints. An invalid or rejected item is marked `REJECTED`, but valid items in the batch are committed and succeed.

---

## 4. Pending VOID Resolution (Out-of-Order Handling)

In IoT networks, network latency or reconnects can cause a `VOID` correction to arrive **before** the target `COUNT` event:
1. When a valid `VOID` arrives and target COUNT does not exist:
   - Stored in `production_events` with status **`PENDING_REFERENCE`**.
   - Audit attempt is logged.
   - State indicator `unresolved` is incremented.
2. When the matching `COUNT` event subsequently arrives:
   - The COUNT is inserted.
   - The system queries all pending VOIDs for that `(source_id, target_event_id)` using `select_for_update()`.
   - **First Stored VOID Wins Rule:** The earliest pending VOID by ID/arrival order is transitioned to `ACCEPTED`, and automatically marked acknowledged (`acknowledged_at = now()`).
   - Target COUNT is marked `is_voided = True, voided_by_event_id = void.event_id`.
   - Net total updates immediately.
   - Any secondary/redundant pending VOIDs targeting the same COUNT are marked `REJECTED` with a clear explanation: `"Target COUNT already voided"`.

---

## 5. Supervisor Acknowledgement Workflow

- Completed `VOID` events are corrections and are automatically acknowledged upon completion.
- The **Pending Table** exclusively displays unreviewed `COUNT` events ready for supervisor inspection.
- When supervisor submits IDs via `POST /api/ack`:
  - `ACKED`: First valid acknowledgement.
  - `ALREADY_ACKED`: Repeated acknowledgement (safe & idempotent).
  - `NOT_READY`: Event is pending reference or rejected.
  - `NOT_FOUND`: Event ID does not exist.

---

## 6. MQTT Integration & Replay Protection

- **Topic Isolation:** Topics are namespaced by Candidate ID (`fse-01/12/...`).
- **Heartbeat & LWT:** Publishes `ONLINE` on connect, `HEARTBEAT` every 30 seconds, and `OFFLINE` as MQTT Last Will & Testament.
- **Challenge Deduplication:**
  - When challenge `CH-xxx` arrives, its SHA-256 body hash is checked in `mqtt_challenges`.
  - Same ID + Same Body: returns the cached `COMPLETED` response immediately without double-processing events.
  - Same ID + Different Body: publishes `FAILED` with code `CHALLENGE_CONFLICT`.

---

## 7. Future Microservices Migration Path

Because the application is built as a function-based modular monolith:
1. **Module Decoupling:** `modules/events`, `modules/state`, `modules/ack`, and `modules/mqtt_worker` communicate through explicit interfaces (`shared/contracts.py`) and internal in-memory domain events (`shared/domain_events.py`).
2. **Migration to Independent Services:**
   - The in-memory domain events (`EVENT_ACCEPTED`, `VOID_RESOLVED`) can be swapped for an external message broker (RabbitMQ / Apache Kafka / NATS) by swapping the emitter implementation.
   - `modules/mqtt_worker` can be containerized into an independent ingestion daemon running on the factory edge.
   - `modules/events` becomes the Core Event Ingestion Service with its own PostgreSQL schema.
   - `modules/state` becomes a read-optimized Projection / Query Service subscribing to domain events.
