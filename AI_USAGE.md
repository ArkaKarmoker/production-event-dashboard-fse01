# AI Usage Disclosure & Verification Record

**Assessment:** CSI Smart Tech Ltd | FSE 01  
**Candidate Name:** Arka Karmoker  
**Candidate ID:** 12  
**Date:** 2026-10-09  

---

## 1. Overview of AI Assistance
In accordance with Stage 3 assessment rules ("Build, test and demo: AI is allowed, but you must explain and change any generated code"), an AI assistant (Google Antigravity / Gemini) was utilized during the implementation phase.

## 2. Tools & Models Used
- **Assistant:** Google Antigravity IDE (Gemini 3.8 Flash High)
- **Role:** Pair-programming assistant for rapid scaffolding, database modeling, test harness setup, and Next.js frontend dashboard layout.

## 3. Human Architecture Decisions & Code Verification
All architectural boundaries, design decisions, and business rule enforcement were reviewed and confirmed:
- **Decision 1 (Modular Monolith):** Chose Django 5 + Django REST Framework with strict module boundaries (`events`, `state`, `ack`, `mqtt_worker`, `shared`) to guarantee zero duplicate business logic between REST and MQTT handlers.
- **Decision 2 (ACID Transactions & Row-level Locks):** Verified PostgreSQL transactions using `select_for_update()` to enforce the "First stored valid VOID wins" rule and prevent concurrent double-counting.
- **Decision 3 (MQTT Protocol & Worker Lifecycle):** Configured `paho-mqtt` with auto-reconnect backoff, 30-second heartbeat thread, LWT, and SHA-256 challenge deduplication for replay safety.
- **Decision 4 (Test Suite):** Designed 7 comprehensive automated tests verifying all five mandatory scenarios (COUNT additions, duplicate idempotency, VOID-before-COUNT resolution, repeated ACK, and MQTT challenge replay cache).

## 4. Verification Check
- All code runs locally against persistent PostgreSQL 16.
- All automated tests pass with 100% success rate (`pytest` & `python manage.py test`).
- Codebase is clean, well-documented, and ready for examiner live walkthrough and modification.
