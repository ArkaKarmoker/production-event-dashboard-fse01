# CSI Smart Tech LTD | FSE 01 - Production Event Processing Dashboard

**Full Stack Engineering Practical Assessment**  
**Candidate Name:** Arka Karmoker  
**Candidate ID:** 12  
**System:** Real-Time Production Event Processing Dashboard + MQTT Device Integration  
**Customer Scenario:** NorthBridge Garments (Garment Factory IoT Counting & Exception Management)

---

## 1. System Overview

This system provides an end-to-end event-processing backend and real-time supervisor dashboard designed for NorthBridge Garments. It solves critical factory floor challenges:
- **Zero Double-Counting:** Idempotent event processing with deterministic SHA-256 payload hashing distinguishes identical replays (`DUPLICATE`) from conflicting edits (`CONFLICT`).
- **Out-of-Order VOID Resolution:** Sensor or network delays can deliver a `VOID` reversal **before** the matching `COUNT` event. Unmatched `VOID` events are durably stored as `PENDING_REFERENCE` and resolve automatically when the target arrives.
- **Unified Logic:** REST APIs and the MQTT device worker call the **exact same** business service (`EventService.process_batch`). No logic is duplicated.
- **Durable PostgreSQL State:** 100% of event ledgers, raw attempts, and simulator challenges persist across server restarts.
- **Modern Responsive Dashboard:** Single-page dashboard built with Next.js, TypeScript, and Tailwind CSS showing 6 live KPI metrics, event simulator presets, supervisor acknowledgement workflow, and real-time MQTT connectivity status.

---

## 2. Architecture: Function-Based Modular Monolith

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
                     |  - COUNT Addition                               |
                     |  - VOID Reversal & Pending Resolution           |
                     |  - Idempotency & Conflict Guard                 |
                     +-------------------+-----------------------------+
                                         |
                                         v (ACID Transactions & Row Locks)
                     +-------------------------------------------------+
                     |            PostgreSQL Database (Port 5435)      |
                     |  - production_sources                           |
                     |  - production_events (composite unique key)     |
                     |  - submission_attempts (immutable audit trail)  |
                     |  - mqtt_challenges (idempotent replay cache)    |
                     +-------------------+-----------------------------+
                                         |
                                         v
                     +-------------------------------------------------+
                     |          Next.js Supervisor Dashboard           |
                     |  - 6 KPI Indicators (Net Total, Pending, etc.)  |
                     |  - Event Ingestion Terminal (Demo Presets)      |
                     |  - Multi-select Supervisor ACK Table            |
                     |  - Exceptions & Conflicts Audit View            |
                     |  - Live MQTT Broker & Challenge Monitor         |
                     +-------------------------------------------------+
```

### Module Layout:
```text
production-event-dashboard-fse01/
├── backend/
│   ├── core/                        # Django configuration package (settings, urls, wsgi)
│   ├── modules/
│   │   ├── events/                  # Core Event models, validation, repository, service, views
│   │   ├── state/                   # State aggregation, summary, pending, exceptions
│   │   ├── ack/                     # Idempotent acknowledgement service and view
│   │   ├── mqtt_worker/             # Paho-MQTT client, protocol validator, heartbeat, challenges
│   │   └── shared/                  # Contracts, constants, domain events
│   ├── tests/                       # 7 automated test suites (pytest & Django test runner)
│   ├── requirements.txt             # Pinned top-level dependencies
│   └── pytest.ini                   # Pytest configuration
├── frontend/
│   ├── src/
│   │   ├── app/                     # Next.js App Router (page.tsx, layout.tsx, globals.css)
│   │   └── lib/                     # Typed API client (api.ts)
│   ├── package.json                 # Next.js, React 19, Tailwind CSS, Lucide icons
│   └── tsconfig.json
├── docker-compose.yml               # PostgreSQL 16 container definition
├── .env.example                     # Sample environment variables
├── TECHNICAL_EXPLANATION.md         # Comprehensive architectural explanation
└── AI_USAGE.md                      # AI assistance disclosure record
```

---

## 3. Quick Start & Setup Guide

### Prerequisites
- Python 3.11+ / 3.12
- Node.js 18+ / 20+
- Docker & Docker Compose (or existing PostgreSQL)

---

### Step 1: Start PostgreSQL via Docker Compose
A lightweight PostgreSQL 16 container mapped to port `5435` (to prevent port 5432 host conflicts) is configured:
```bash
docker compose up -d postgres
```

---

### Step 2: Configure Environment Variables
Copy the provided `.env.example` to `.env` in the root and backend folders:
```bash
cp .env.example .env
cp .env.example backend/.env
```

---

### Step 3: Setup & Run Backend (Django + DRF)
```bash
cd backend

# 1. Create and activate virtual environment
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
# source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Apply database migrations
python manage.py migrate

# 4. Run Django development server (Port 8000)
python manage.py runserver 8000
```
> **Note:** The MQTT worker connects automatically in the background upon server launch. If you wish to run the MQTT worker as an isolated standalone daemon, execute:
> ```bash
> python manage.py run_mqtt_worker
> ```

---

### Step 4: Setup & Run Frontend (Next.js)
In a separate terminal:
```bash
cd frontend

# Install frontend dependencies
npm install

# Start Next.js development server (Port 3000)
npm run dev
```
Open **[http://localhost:3000](http://localhost:3000)** in your browser to access the supervisor dashboard.

---

## 4. Running Automated Tests

7 automated tests verify all 5 mandatory requirements plus edge-case reliability:

### Run via Django Test Runner:
```bash
cd backend
python manage.py test tests
```

### Run via Pytest:
```bash
cd backend
pytest
```

### Test Coverage Summary:
| Test Name | Scenario Tested |
| :--- | :--- |
| `test_1_count_and_total` | New `COUNT +5` event increases `net_total` and sets status `ACCEPTED`. |
| `test_2_identical_duplicate` | Same event resubmitted returns `DUPLICATE` with zero double-counting. |
| `test_3_void_before_count_resolution` | `VOID` arriving before `COUNT` is stored as `PENDING_REFERENCE` and auto-resolves when `COUNT` arrives. |
| `test_4_repeated_acknowledgement` | `POST /api/ack` is idempotent; first is `ACKED`, second is `ALREADY_ACKED`. |
| `test_5_repeated_mqtt_challenge` | Replay challenge with same ID returns cached response without reprocessing; conflict returns `CHALLENGE_CONFLICT`. |
| `test_6_batch_processing_and_isolation` | Mixed batch: valid events commit successfully even if another item is `REJECTED`. |
| `test_7_conflict_detection` | Same event ID with altered payload returns `CONFLICT` and records exception. |

---

## 5. REST API Documentation & Curl Examples

### 1. `POST /api/events`
Accepts a single event JSON object or a JSON array.

#### Submit a Single COUNT Event:
```bash
curl -X POST http://localhost:8000/api/events \
  -H "Content-Type: application/json" \
  -d '{
    "source_id": "LINE-01",
    "event_id": "EV-101",
    "type": "COUNT",
    "quantity": 5,
    "target_event_id": null,
    "event_time": "2026-10-09T10:30:00Z"
  }'
```
**Response (HTTP 200):**
```json
{
  "results": [
    {
      "event_id": "EV-101",
      "status": "ACCEPTED",
      "message": "Event processed"
    }
  ]
}
```

#### Submit a VOID Reversal:
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

### 2. `GET /api/state`
Query parameters: `view` (`summary` | `pending` | `exceptions`), optional `source_id`.

#### Get Summary State:
```bash
curl -X GET "http://localhost:8000/api/state?view=summary"
```
**Response (HTTP 200):**
```json
{
  "net_total": 5,
  "processed_events": 1,
  "pending_ack": 1,
  "unresolved": 0,
  "duplicates": 0,
  "conflicts": 0
}
```

#### Get Pending Events (Awaiting Supervisor ACK):
```bash
curl -X GET "http://localhost:8000/api/state?view=pending&source_id=LINE-01"
```

#### Get Exceptions & Conflicts:
```bash
curl -X GET "http://localhost:8000/api/state?view=exceptions"
```

---

### 3. `POST /api/ack`
Acknowledge processed events by ID.

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
| **Port** | `1883` (Plain MQTT) |
| **Candidate ID** | `12` |
| **Client ID** | `fse01-12-{suffix}` |
| **QoS / Retain** | QoS 1, Retain `false` |
| **Subscribe Topic** | `fse-01/12/challenge` |
| **Publish Response** | `fse-01/12/response` |
| **Publish Status** | `fse-01/12/status` (`ONLINE`, `HEARTBEAT`, `OFFLINE` via LWT) |

---

## 7. Examiner Live Demo Walkthrough

The dashboard at `http://localhost:3000` includes one-click **Quick Presets** to demonstrate all evaluation criteria in under 2 minutes:

1. **Step 1 (Open Dashboard):** Open `http://localhost:3000`. The top bar displays candidate identity, connection status, and 6 KPI indicators.
2. **Step 2 (COUNT +5):** Click `COUNT +5` preset, then click `Submit Event(s)`. Notice Net Total increments to `5`, Pending ACK becomes `1`, and the event appears in the Pending table.
3. **Step 3 (Duplicate Replay):** Click `Duplicate EV-101` preset and submit again. Result is `DUPLICATE`. Net total stays `5`, and Duplicates indicator increments to `1`.
4. **Step 4 (VOID before COUNT):**
   - Click `VOID Before COUNT` preset (reverses `EV-201` before it exists). Result is `PENDING_REFERENCE`. Unresolved counter increments to `1`.
   - Click `Matching COUNT` preset (`EV-201`, qty `8`). Result is `ACCEPTED`. The system automatically matches and applies the pending void! Net total reflects verified production, and Unresolved drops back to `0`.
5. **Step 5 (Supervisor ACK):** In the Pending Review table, check the box for `EV-101` and click `Acknowledge Selected (1)`. The item is acknowledged and removed from Pending.
6. **Step 6 (MQTT Live Status):** Observe the MQTT Device Simulator strip confirming broker connection, candidate ID isolation (`fse-01/12/*`), and heartbeat transmission every 30 seconds.
