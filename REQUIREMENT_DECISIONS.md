# CSI Smart Tech - FSE 01 Requirement Decisions & Assumptions

**Candidate Name:** Arka Karmoker  
**Candidate ID:** 12  
**System:** Production Event Processing Dashboard + MQTT Device Integration (Garment Factory IoT)  
**Date:** 2026-10-09  

---

## 1. Overview

This document records the architectural decisions, trade-offs, and requirement interpretations made during the design and implementation of the NorthBridge Garments Production Event Processing Dashboard (Assessment FSE 01).

---

## 2. Seven Clarification Questions & Chosen Assumptions

Per Stage 2 guidelines (*"Clarify with examiner: Ask up to seven meaningful questions. If unanswered, record your chosen assumption"*), the following questions and decisions were formulated:

### Q1: Out-of-Order VOID vs Multiple Conflicting VOIDs
- **Question:** If multiple `VOID` events arrive targeting a non-existent `COUNT` event, how should the conflicting pending VOIDs be handled when the target `COUNT` finally arrives?
- **Decision/Assumption:** **"First stored valid VOID wins"** rule (Assessment Section 5.2). When the matching `COUNT` event arrives, the earliest stored pending VOID in PostgreSQL (`status='PENDING_REFERENCE'`) is transitioned to `ACCEPTED`, and its quantity reverses the count. Any subsequent pending VOIDs referencing the exact same target COUNT are updated to `REJECTED` with the explanation `"Target COUNT already voided"`.

### Q2: Acknowledgement Lifecycle of VOID Events
- **Question:** Should supervisor users manually acknowledge `VOID` correction events on the dashboard, or should `VOID` events be automatically acknowledged?
- **Decision/Assumption:** Per Factory Workflow Note (Assessment Section 9): `VOID` events are system corrections and are **automatically marked acknowledged upon successful processing/resolution** (`acknowledged_at = now()`). The supervisor **Pending Review table** exclusively lists unreviewed `COUNT` events for human sign-off.

### Q3: Event ID Scope & Multi-Line Namespace
- **Question:** The brief states both *"An event ID is globally unique across all production sources"* (Sec 5.1) and *"use a composite unique key on (source_id, event_id), allowing different production lines to use the same event ID"* (Sec 7). How should this be reconciled in PostgreSQL?
- **Decision/Assumption:** Implemented a composite unique constraint in PostgreSQL:
  ```python
  UniqueConstraint(fields=['source_id', 'event_id'], name='unique_source_event')
  ```
  This satisfies the industrial multi-line reality where separate IoT sensors on `LINE-01` and `LINE-02` might reset counter hardware or use independent sequence IDs, while still ensuring complete uniqueness per production line.

### Q4: Batch Atomicity and Partial Failures
- **Question:** Section 6.1 states *"Do not undo valid items because a different item in the batch is invalid"*, while Section 7 states *"For a batch import, treat the batch as one database transaction: commit the whole batch together or roll it back if any event fails validation."*
- **Decision/Assumption:** Implemented per-item atomic savepoints within a single outer transaction:
  - If a batch item fails business validation (e.g., negative quantity, invalid type), that specific item is categorized as `REJECTED`, and recorded in `submission_attempts`.
  - Valid sibling items within the same batch proceed to be processed and committed to PostgreSQL.
  - The HTTP response preserves the exact input array ordering with corresponding item statuses (`ACCEPTED`, `REJECTED`, etc.), and returns HTTP 200 per Section 6.1.
  - If a catastrophic database-level error occurs (e.g., connection drop, serialization deadlock), the entire transaction rolls back cleanly.

### Q5: Idempotency vs Payload Mutation (DUPLICATE vs CONFLICT)
- **Question:** How strictly is payload equivalence evaluated to distinguish `DUPLICATE` from `CONFLICT`?
- **Decision/Assumption:** Canonical JSON normalization. Incoming event payloads are normalized (sorted keys, stripped insignificant whitespace) and hashed via SHA-256 (`normalized_payload_hash`).
  - If an incoming event matches an existing `(source_id, event_id)` and the SHA-256 matches: Classified as **`DUPLICATE`**. Counter does not increment. Stored in `submission_attempts`.
  - If the SHA-256 differs: Classified as **`CONFLICT`**. Original event is preserved untouched. Stored in `submission_attempts` as an exception.

### Q6: MQTT Replay & Challenge Response Caching
- **Question:** When an identical MQTT challenge is received multiple times by the worker, should events be re-evaluated?
- **Decision/Assumption:** Idempotent Challenge Caching. The MQTT challenge body is hashed (SHA-256) and recorded in `mqtt_challenges`.
  - Same `challenge_id` + same body: Returns the cached `COMPLETED` response payload immediately without re-processing events.
  - Same `challenge_id` + altered body: Emits `FAILED` response with error code `CHALLENGE_CONFLICT`.
  - Expired challenge (`now() > expires_at`): Emits `FAILED` response with error code `CHALLENGE_EXPIRED`.

### Q7: Shared Business Logic & Microservice Decoupling
- **Question:** How do we ensure zero business logic duplication between REST APIs and MQTT background worker?
- **Decision/Assumption:** Both REST endpoints and the MQTT background subscriber import and invoke the identical business service functions:
  ```python
  EventService.process_batch(events)
  StateService.get_summary(source_id)
  ```
  Neither the REST controller nor the MQTT worker contains business validation or SQL queries. All state logic resides in `modules/events` and `modules/state`.

---

## 3. Technology Stack Selection Rationale

| Layer | Selected Tech | Rationale |
| :--- | :--- | :--- |
| **Backend** | Python 3.12 / Django 6.0 / DRF | Native ACID transaction handling (`transaction.atomic()`, `select_for_update()`), robust ORM migrations, enterprise reliability, and clear modular monolith structure. |
| **Database** | PostgreSQL 16 (via Docker) | Mandatory requirement. Provides reliable row-level locking, composite constraints, and durable audit logs that survive restarts. |
| **MQTT Client** | Paho-MQTT 2.1 | Industry-standard MQTT client supporting QoS 1, KeepAlive, automatic exponential backoff reconnection, and Last Will & Testament (LWT). |
| **Frontend** | Next.js 16 / TypeScript / Tailwind CSS | Fast server-driven and client-interactive UI, type safety matching backend contracts, dark-mode modern dashboard aesthetics, and responsive layout. |
| **Containerization** | Docker Compose | Single command (`docker compose up -d`) launches PostgreSQL 16, Django backend + MQTT worker, and Next.js frontend with isolated networking. |

---

## 4. Environment & Configuration Consolidation

- **Root `.env` Strategy:** Rather than maintaining divergent `.env` files across folders, the system utilizes a centralized root `.env` loaded into Docker Compose and passed cleanly to backend and frontend containers.
- **Safety:** `.env` is strictly ignored by Git. `.env.example` is committed to version control with standard template parameters and non-secret defaults.

---

## 5. Change Request Decisions (FSE-01 Modification Requirements)

- **CR-01 (Quantity Range Validation):** Valid single COUNT quantities are integers from 1 to 500 inclusive. Enforced in `EventSerializer.validate()`. Rejections are stored in `submission_attempts` with status `REJECTED` and clear error messaging without increasing totals.
- **CR-02 (Rejected Submissions in Summary):** Added `rejected_submissions` to `StateQueries.get_summary()`. Filters `submission_attempts` by `classification="REJECTED"`, supporting optional `source_id` filtering. Aliased `/api/stats` to `/api/state`.
- **CR-03 (Production Source Filter):** Implemented an interactive toolbar on the dashboard with quick pills (`All Sources`, `LINE-01`, `LINE-02`, `LINE-03`), custom text input, active filter badge, and clear button.
- **CR-04 (Rejected Submissions KPI Indicator):** Added a 7th KPI card in distinct red styling displaying `rejected_submissions`, updating live with source filtering.

