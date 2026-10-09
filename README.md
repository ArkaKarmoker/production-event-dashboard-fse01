# CSI Smart Tech Ltd | FSE 01 - Production Event Processing Dashboard

**Full Stack Engineering Practical Assessment + Change Request**  
- **Candidate Name:** Arka Karmoker  
- **Candidate ID:** 12  
- **Client Scenario:** NorthBridge Garments (Garment Factory IoT Event Processing & Supervisor Console)  
- **Tech Stack:** Python 3.12, Django 6.0, Django REST Framework, PostgreSQL 16, Paho-MQTT 2.1, Next.js 16 (React 19), TypeScript, Tailwind CSS, Docker Compose  

---

## 1. System Overview

A durable, function-based modular monolith event-processing system with an interactive Next.js supervisor dashboard and outbound MQTT device worker.

- **Zero Double-Counting:** Deterministic SHA-256 payload normalization distinguishes identical resubmissions (`DUPLICATE`) from altered payloads (`CONFLICT`).
- **Out-of-Order VOID Resolution:** `VOID` arriving prior to its target `COUNT` is safely recorded as `PENDING_REFERENCE` and resolves automatically upon target arrival ("First stored valid VOID wins").
- **Quantity Range Validation (CR-01):** Single `COUNT` events are strictly validated to `1 <= quantity <= 500`. Excess quantities return `REJECTED` and are audited without increasing production totals.
- **7-Metric Summary Projection (CR-02 & CR-04):** Durable PostgreSQL calculation providing `net_total`, `processed_events`, `pending_ack`, `unresolved`, `duplicates`, `conflicts`, and `rejected_submissions`.
- **Production Source Filter (CR-03):** Dashboard toolbar allows live filtering by production line (e.g., `LINE-01`) across Summary, Pending Review, and Exceptions views.
- **Unified Processing:** REST API (`POST /api/events`) and MQTT worker invoke the exact same service (`EventService.process_batch`). Zero logic duplication.

---

## 2. Architecture & Modular Boundaries

```text
                       +-------------------------------------------------+
                       |                 Ingestion Layer                 |
                       |     [REST API]                 [MQTT Worker]    |
                       +-------------------+-----------------------------+
                                           |
                                           v
                       +-------------------------------------------------+
                       |             Core Event Engine                   |
                       |  validate_event() -> process_event()            |
                       |  - COUNT Validation (1 to 500, CR-01)           |
                       |  - VOID Reversal & Pending Reference Matching   |
                       |  - SHA-256 Idempotency & Conflict Guard         |
                       +-------------------+-----------------------------+
                                           |
                                           v (ACID Transactions & Row Locks)
                       +-------------------------------------------------+
                       |            PostgreSQL Database (Port 5435)      |
                       |  - production_sources                           |
                       |  - production_events (composite unique key)     |
                       |  - submission_attempts (immutable audit trail)  |
                       |  - mqtt_challenges (replay cache & ledger)      |
                       +-------------------+-----------------------------+
                                           |
                                           v
                       +-------------------------------------------------+
                       |          Next.js Supervisor Dashboard           |
                       |  - Source Filter Bar (CR-03: Line-01, Line-02)  |
                       |  - 7 KPI Indicators (including Rejected, CR-04) |
                       |  - Event Ingestion Terminal (Demo Presets)      |
                       |  - Multi-select Supervisor ACK Table            |
                       |  - Exceptions & Conflicts Table (REJECTED tag)  |
                       |  - Live MQTT Broker & Challenge Monitor         |
                       +-------------------------------------------------+
```

### Repository Structure:
```text
production-event-dashboard-fse01/
├── backend/
│   ├── core/                        # Django configuration (settings, urls, wsgi)
│   ├── modules/
│   │   ├── events/                  # Models, validation (Qty <= 500), service, repository, views
│   │   ├── state/                   # State aggregation (7 indicators), queries, views
│   │   ├── ack/                     # Acknowledgement service and view
│   │   ├── mqtt_worker/             # Paho-MQTT client, protocol validator, heartbeat, worker
│   │   └── shared/                  # Contracts, constants, domain events
│   ├── tests/                       # 9 automated tests (100% pass)
│   ├── Dockerfile                   # Python 3.12 backend container definition
│   └── requirements.txt             # Pinned backend dependencies
├── frontend/
│   ├── src/
│   │   ├── app/                     # Next.js App Router (page.tsx, layout.tsx, globals.css)
│   │   └── lib/                     # Typed API client (api.ts)
│   ├── Dockerfile                   # Next.js frontend container definition
│   └── package.json
├── docker-compose.yml               # PostgreSQL 16, Django backend, Next.js frontend
├── .env.example                     # Environment template without secrets
├── TECHNICAL_EXPLANATION.md         # Comprehensive architectural documentation
├── REQUIREMENT_DECISIONS.md         # Clarification questions & architectural trade-offs
├── AI_USAGE.md                      # AI assistance disclosure record
└── change_request_document.md       # Assessment Change Request specifications
```

---

## 3. Quick Start & Execution

### Option A: One-Command Docker Compose (Recommended)

Start the entire stack (PostgreSQL 16, Django Backend + MQTT Worker, Next.js Frontend):
```bash
docker compose up -d
```
- **Frontend Dashboard:** [http://localhost:3000](http://localhost:3000)
- **Backend REST API:** [http://localhost:8000](http://localhost:8000)
- **PostgreSQL Database:** `localhost:5435` (mapped to avoid local 5432 conflicts)

Stop the stack:
```bash
docker compose down
```

---

### Option B: Local Manual Setup

#### 1. Start PostgreSQL
```bash
docker compose up -d postgres
```

#### 2. Setup & Run Backend
```bash
cd backend
python -m venv venv

# Windows:
venv\Scripts\activate
# Linux/macOS:
# source venv/bin/activate

pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 8000
```
*(The background MQTT worker automatically launches with Django.)*

#### 3. Setup & Run Frontend
```bash
cd frontend
npm install
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## 4. Automated Test Suite

The test suite contains **9 automated tests** covering all mandatory scenarios and change request specifications:

### Run Tests:
```bash
cd backend
python manage.py test tests
```
*Or via pytest:*
```bash
pytest
```

### Test Scenarios:
| # | Test Method | Covered Requirement |
| :---: | :--- | :--- |
| **1** | `test_1_count_and_total` | `COUNT` increments net total; returns `ACCEPTED`. |
| **2** | `test_2_identical_duplicate_without_double_counting` | Identical duplicate returns `DUPLICATE`; zero double-counting. |
| **3** | `test_3_void_before_count_resolution` | Out-of-order `VOID` becomes `PENDING_REFERENCE`; auto-resolves when `COUNT` arrives. |
| **4** | `test_4_repeated_acknowledgement` | Safe repeated ACK: first is `ACKED`, second is `ALREADY_ACKED`. |
| **5** | `test_5_repeated_mqtt_challenge_idempotency` | Identical MQTT challenge returns cached response; conflict returns `CHALLENGE_CONFLICT`. |
| **6** | `test_6_batch_processing_and_isolation` | Mixed batch: valid events commit even if another item is `REJECTED`. |
| **7** | `test_7_conflict_detection` | Same event ID with different payload returns `CONFLICT`. |
| **8** | `test_8_count_quantity_max_500_validation` | **CR-01:** `COUNT 450` ➔ `ACCEPTED`; `COUNT 501` ➔ `REJECTED`. Total does not increment. |
| **9** | `test_9_rejected_submissions_in_summary_and_source_filter` | **CR-02 & CR-03:** `rejected_submissions` in `/api/state` & `/api/stats`, source filter, and MQTT state. |

---

## 5. REST API Reference & Curl Examples

### 1. `POST /api/events`
Accepts a single event JSON object or an array of event objects.

#### Submit Valid COUNT (`quantity <= 500`):
```bash
curl -X POST http://localhost:8000/api/events \
  -H "Content-Type: application/json" \
  -d '{
    "source_id": "LINE-01",
    "event_id": "EV-101",
    "type": "COUNT",
    "quantity": 450,
    "target_event_id": null,
    "event_time": "2026-10-09T10:30:00Z"
  }'
```
**Response (HTTP 200):**
```json
{
  "results": [
    { "event_id": "EV-101", "status": "ACCEPTED", "message": "Event processed" }
  ]
}
```

#### Submit Invalid COUNT (`quantity > 500` - CR-01):
```bash
curl -X POST http://localhost:8000/api/events \
  -H "Content-Type: application/json" \
  -d '{
    "source_id": "LINE-01",
    "event_id": "EV-501",
    "type": "COUNT",
    "quantity": 501,
    "event_time": "2026-10-09T10:30:00Z"
  }'
```
**Response (HTTP 200):**
```json
{
  "results": [
    { "event_id": "EV-501", "status": "REJECTED", "message": "quantity: COUNT quantity must be an integer between 1 and 500 (received: 501)." }
  ]
}
```

#### Submit VOID Event (Reversal):
```bash
curl -X POST http://localhost:8000/api/events \
  -H "Content-Type: application/json" \
  -d '{
    "source_id": "LINE-01",
    "event_id": "VOID-101",
    "type": "VOID",
    "quantity": null,
    "target_event_id": "EV-101",
    "event_time": "2026-10-09T10:35:00Z"
  }'
```

---

### 2. `GET /api/state` (or `/api/stats`)
Query parameters: `view` (`summary` | `pending` | `exceptions`), optional `source_id`.

#### Summary View (All 7 Indicators):
```bash
curl -X GET "http://localhost:8000/api/state?view=summary"
```
**Response (HTTP 200):**
```json
{
  "net_total": 450,
  "processed_events": 1,
  "pending_ack": 1,
  "unresolved": 0,
  "duplicates": 0,
  "conflicts": 0,
  "rejected_submissions": 1
}
```

#### Filtered Summary by Production Line (CR-03):
```bash
curl -X GET "http://localhost:8000/api/state?view=summary&source_id=LINE-01"
```

#### Pending Review View (COUNTs awaiting supervisor sign-off):
```bash
curl -X GET "http://localhost:8000/api/state?view=pending&source_id=LINE-01"
```

#### Exceptions View (Unresolved references, conflicts, and rejected attempts):
```bash
curl -X GET "http://localhost:8000/api/state?view=exceptions"
```

---

### 3. `POST /api/ack`
Acknowledges reviewed events by ID. Repeated requests are idempotent.

```bash
curl -X POST http://localhost:8000/api/ack \
  -H "Content-Type: application/json" \
  -d '{
    "event_ids": ["EV-101", "NON-EXISTENT"]
  }'
```
**Response (HTTP 200):**
```json
[
  { "event_id": "EV-101", "status": "ACKED" },
  { "event_id": "NON-EXISTENT", "status": "NOT_FOUND" }
]
```

---

## 6. MQTT Device Simulator Integration

| Setting | Value |
| :--- | :--- |
| **Broker Host** | `152.42.238.142` |
| **Broker Port** | `1883` (Plain MQTT) |
| **Candidate ID** | `12` |
| **Client ID** | `fse01-12-{suffix}` |
| **QoS / Retain** | QoS 1, Retain `false` |
| **Subscribe Topic** | `fse-01/12/challenge` |
| **Publish Response** | `fse-01/12/response` |
| **Publish Status** | `fse-01/12/status` (`ONLINE`, `HEARTBEAT`, `OFFLINE` via LWT) |
| **Heartbeat Interval**| 30 seconds |

- **Replay Protection:** Identical challenge (`challenge_id` + same payload hash) immediately returns cached `COMPLETED` response without reprocessing events. Same ID with altered body returns `FAILED` with code `CHALLENGE_CONFLICT`.
- **Envelope Validation:** Validates `protocol_version`, `candidate_id`, `challenge_id`, and `expires_at`.

---

## 7. Examiner Live Demo Walkthrough

The supervisor dashboard at [http://localhost:3000](http://localhost:3000) features one-click demo presets:

1. **Production Source Filter (CR-03):** Use the top filter bar to switch between `All Sources`, `LINE-01`, and `LINE-02`. Notice KPI cards, Pending Review, and Exceptions update synchronously.
2. **Accepted COUNT (CR-01):** Click `COUNT 450 (Valid)` preset and submit. `net_total` increments by 450, status is `ACCEPTED`, and row appears in Pending Review.
3. **Rejected COUNT (CR-01 & CR-04):** Click `COUNT 501 (Rejected)` preset and submit. Status is `REJECTED`, `net_total` does not increase, 7th KPI `Rejected Submissions` increments, and event appears in Exceptions with a red `REJECTED` badge.
4. **Duplicate Replay:** Click `Duplicate EV-101` and submit. Returns `DUPLICATE`; total is unchanged.
5. **Out-of-Order VOID Resolution:** Click `VOID Before COUNT` (`PENDING_REFERENCE`), then click `Matching COUNT` (`ACCEPTED`). Unresolved count auto-clears back to 0.
6. **Supervisor Acknowledgement:** Select pending rows and click `Acknowledge Selected`. Status transitions to `ACKED`.
7. **MQTT Device Monitoring:** Check the live MQTT panel displaying real-time connection status, candidate ID `12`, 30s heartbeat timestamps, and last response status.
