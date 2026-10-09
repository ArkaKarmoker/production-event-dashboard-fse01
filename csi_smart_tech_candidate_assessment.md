**CSI SMART TECH LTD | FSE 01 | CANDIDATE ASSESSMENT**

# Full Stack Engineering Practical Assessment

**Production Event Processing Dashboard + MQTT Device Integration**

| Assessment | Total time | Marks | Submission |
| :--- | :--- | :--- | :--- |
| FSE 01 | 1 hour 45 minutes | 100 | Working full-stack system |

| Candidate Name | Candidate ID |
| :--- | :--- |
| Arka Karmoker | 12 |

The aim: Understand a real business problem, ask useful questions, design a clear solution, and show a working frontend. Fast code without understanding is not the goal.

### 1 The customer story: why are we building this?

A small garment factory, NorthBridge Garments (fictional), operates several production lines. Each line has a counter device that reports how many finished pieces were produced. Today, the supervisor collects numbers from different screens and handwritten notes. Some messages arrive late; sometimes the same message is sent twice after a network reconnect. A faulty sensor can also report pieces that were never made.

The factory manager wants one dashboard for current operations and, later, for each work shift. The dashboard must show the true total, events waiting for review, mistakes that need attention, and whether connected devices are responding. A supervisor must be able to review completed events and acknowledge them. If an earlier count was wrong, a correction should reverse it without deleting history.

**Your job:** Build the small first version that CSI Smart Tech could demonstrate to this customer. It must work now and be easy to change when the customer adds more lines, business rules or devices later.

| End user | What they need |
| :--- | :--- |
| Production supervisor | See reliable totals, inspect exceptions, and acknowledge reviewed events. |
| Factory floor operator | Submit a count or correction when a device or report needs manual attention. |
| Support/engineering team | Check device connection, see the last challenge, and trace errors without losing history. |

### 2 Understand the entities (simple examples)

An entity is a real thing or business record your software must recognize and store. A function is an action the software performs on those records. An event says that something happened.

| Entity | Simple meaning and example |
| :--- | :--- |
| Production source | A line or machine sending counts, such as LINE-01. |
| Production event | One action: COUNT +5 (EV-101), or VOID a wrong earlier count. |
| Submission attempt | Every received request, including the second copy of EV-101 or an invalid request. |
| Acknowledgement | A review marker saying a successfully processed event has been checked. |
| MQTT challenge | A device-simulator request identified by challenge_id that needs a matching response. |

Example: LINE-01 reports COUNT 5. The total becomes 5. The same message arrives again: the total must stay 5. Later a valid VOID of that COUNT arrives: the total becomes 0. Every step remains traceable.

CSI Smart Tech • CANDIDATE ASSESSMENT | Page 1

---

**CSI SMART TECH LTD | FSE 01 | CANDIDATE ASSESSMENT**

### 3 Candidate instructions and working time

| Stage | Time | Rule |
| :--- | :--- | :--- |
| Read the full brief | 10 minutes | Do not code. Identify actors, entities, business rules, unclear points and expected outputs. |
| Clarify with examiner | 10 minutes | Ask up to seven meaningful questions. No AI or search in these first two stages. |
| Build, test and demo | 85 minutes | AI is allowed, but you must explain and change any generated code. |

*   Open the provided Google Form first; follow its delivery and deadline instructions.
*   Use PostgreSQL as the required persistent database. SQLite and in-memory databases are not acceptable for the submitted solution.
*   Use any suitable language or framework. The architecture and working behavior matter more than a framework name.
*   Initialize Git; make at least three genuine progress commits and push a runnable repository to GitHub.
*   Submit AI_USAGE.md and the relevant AI conversation record. Never include .env secrets, passwords, build caches, node_modules or virtual environments.
*   If two statements seem unclear or inconsistent, raise the question. If unanswered, record your chosen assumption in TECHNICAL_EXPLANATION.md.

### 4 Required architecture: a function-based modular monolith

Build ONE backend application, with ONE deployment and ONE PostgreSQL database. Organize it into small modules that act like independent services inside the same application. Do not create separate deployed microservices for this assessment.

**In simple English:** The events module decides whether a count is valid. The acknowledgement module handles review. The state module calculates totals. The MQTT module receives a device message and calls the same event-processing function used by the REST API.

```text
REST input ----\
                --> validate_event() --> process_event() --> PostgreSQL
MQTT input ----/                         |
                                         business event / callback
                                         |
                                         state / acknowledgement / audit
```

*   Use small functions with clear inputs and outputs. Examples: validate_event(), process_count(), process_void(), resolve_pending_voids(), acknowledge_event(), get_summary(), handle_mqtt_challenge().
*   Keep controllers/routes thin. Place business rules in services and database commands in repositories/data-access modules.
*   Each module owns its responsibility. Changing a rule in one function should not require editing every route or unrelated module.
*   Use internal event notifications or callbacks where useful (for example, EVENT_ACCEPTED, VOID_RESOLVED or EVENT_ACKNOWLEDGED). Trigger notifications only after successful database work.
*   Keep data contracts and module boundaries clear so a module could later become its own microservice and the internal notifications could later use a message broker.
*   Do not duplicate COUNT or VOID logic in REST routes, MQTT handlers, frontend code or multiple services.

**Not required today:** Kafka, RabbitMQ, multiple deployments, distributed databases, Kubernetes or a real microservices platform. Explain a credible future migration path instead.

One possible folder layout (change names to suit your framework):

CSI Smart Tech • CANDIDATE ASSESSMENT | Page 2

---

**CSI SMART TECH LTD | FSE 01 | CANDIDATE ASSESSMENT**

```text
src/
  modules/events/(routes,validation,service,repository)
  modules/ack/(routes,service,repository)
  modules/state/(routes,service,queries)
  modules/mqtt/(worker,protocol,service)
  modules/audit/(service,repository)
  shared/(db,contracts,domain_events)
frontend/ migrations/ tests/
```

### 5 Production events and business rules

#### 5.1 Event JSON
```json
{
  "source_id": "LINE-01", "event_id": "EV-101", "type": "COUNT",
  "quantity": 5, "target_event_id": null,
  "event_time": "2026-10-09T10:30:00Z"
}
```

| Field | Required behavior |
| :--- | :--- |
| source_id | Required non-empty production source name. |
| event_id | Required non-empty string. An event ID is globally unique across all production sources. |
| type | Exactly COUNT or VOID. |
| quantity | COUNT: positive integer. VOID: null or omitted. |
| target_event_id | COUNT: null or omitted. VOID: ID of the COUNT being reversed. |
| event_time | Required ISO 8601 timestamp with timezone; keep the event time separate from server receipt time. |

#### 5.2 Processing, retries and corrections
*   COUNT adds its quantity only once after successful processing.
*   VOID reverses one accepted COUNT; the COUNT and VOID must have the same source_id. One COUNT can be reversed only once.
*   If VOID arrives before COUNT, store it as PENDING_REFERENCE. Resolve automatically when the matching COUNT arrives.
*   If several pending VOID events target one COUNT, the first stored valid VOID wins. Reject the others with clear reasons.
*   Process items of a batch in submitted order. Preserve the same item order in the response.
*   An invalid item is REJECTED and recorded, but valid items in the same batch still succeed.
*   Keep every rejected submission, duplicate attempt and conflict attempt in persistent storage.
*   Use PostgreSQL constraints and transactions to prevent double counting under repeated or concurrent requests.

| Incoming case | Item status | Business effect |
| :--- | :--- | :--- |
| New valid COUNT or applicable VOID | ACCEPTED | Process once and store. |
| Valid VOID missing its COUNT | PENDING_REFERENCE | Store, wait for matching COUNT. |
| Same event ID, same normalized data | DUPLICATE | Record attempt; never process twice. |
| Same event ID, different data | CONFLICT | Record attempt; preserve original event. |
| Invalid event | REJECTED | Store reason; continue other batch items. |

CSI Smart Tech • CANDIDATE ASSESSMENT | Page 3

---

**CSI SMART TECH LTD | FSE 01 | CANDIDATE ASSESSMENT**

### 6 Three REST APIs (JSON)

#### 6.1 POST /api/events
Accept one event object or a JSON array. Return one item result per submitted item, in the original order. Allowed statuses: ACCEPTED, DUPLICATE, CONFLICT, PENDING_REFERENCE and REJECTED.

```json
{ "results": [ { "event_id": "EV-101", "status": "ACCEPTED",
                 "message": "Event processed" } ] }
```

*   Return HTTP 200 when the top-level JSON is an event or event array, even if some items are REJECTED.
*   Return HTTP 400 when the top-level request cannot be interpreted as an event or event array.
*   Do not undo valid items because a different item in the batch is invalid.

#### 6.2 GET /api/state
Example: `GET /api/state?source_id=LINE-01&view=summary`. `source_id` is optional. `view` must be one of summary, pending or exceptions.

| View | Return |
| :--- | :--- |
| summary | net_total, processed_events, pending_ack, unresolved, duplicates, conflicts |
| pending | Successfully processed COUNT/VOID events that are ready for acknowledgement and are not yet acknowledged |
| exceptions | Unresolved references, rejected submissions and conflict attempts, with reasons |

| Summary value | Meaning |
| :--- | :--- |
| net_total | Sum of accepted COUNT quantities minus successfully applied VOID quantities. |
| processed_events | Distinct completed COUNT and VOID events; unresolved VOID joins after resolution. |
| pending_ack | Successfully processed or resolved events not yet acknowledged. |
| unresolved | Valid VOID events still waiting for target COUNT. |
| duplicates | Number of stored identical duplicate submission attempts. |
| conflicts | Number of stored conflicting submission attempts. |

With `source_id`, filter original events by stored source. Duplicate/conflict attempts use the `source_id` in that attempt. Invalid submissions without a useful `source_id` appear only in unfiltered exceptions.

#### 6.3 POST /api/ack
```json
{ "event_ids": ["EV-101", "EV-102"] }
```
Return one result for every requested ID, in order. ACKED means newly acknowledged; ALREADY_ACKED means it was acknowledged earlier; NOT_READY means it is unresolved, rejected or not successfully processed; NOT_FOUND means there is no original logical event with that ID.

*   Repeated acknowledgements must be safe. The second copy of an ID in one request becomes ALREADY_ACKED if the first was ACKED.
*   Acknowledgement never deletes history or prevents a later valid VOID from reversing a COUNT.
*   Both completed COUNT and completed VOID events can be acknowledged through this API.

### 7 PostgreSQL, history and reliability
Store logical production events, all submission attempts, original payload/normalized values, processing status, failure reason, event time, receipt time, acknowledgement information and MQTT challenge responses. Data must survive server restart.

CSI Smart Tech • CANDIDATE ASSESSMENT | Page 4

---

**CSI SMART TECH LTD | FSE 01 | CANDIDATE ASSESSMENT**

| Suggested entity/table | Typical columns or responsibility |
| :--- | :--- |
| production_sources | source_id, display name (other fields at your discretion). |
| production_events | event_id, source_id, type, quantity, target_event_id, event_time, status, acknowledged_at. |
| submission_attempts | raw payload, source_id (if present), event_id (if present), classification, error, received_at. |
| mqtt_challenges | challenge_id, request digest/body, serialized result, timestamps, status. |

*   Database modelling note: use a composite unique key on (source_id, event_id), allowing different production lines to use the same event ID.
*   For a batch import, treat the batch as one database transaction: commit the whole batch together or roll it back if any event fails validation.
*   Protect competing COUNT/VOID updates and acknowledgement state with appropriate transactions, constraints and database locks where necessary.
*   Read summary totals from durable evidence (or from a reliably updated transactional projection), not from process memory.
*   Never expose SQL credentials, stack traces or internal secrets in API errors. Provide a migration/initialization command and .env.example.

### 8 MQTT simulator integration

The examiner simulator acts like a remote factory device. Connect as an outbound MQTT client, receive a challenge, send its events through the same processing functions as REST, read state through the same query functions, and publish a matching response. *MQTT topic isolation uses the assigned Candidate ID.*

| Setting | Required value |
| :--- | :--- |
| Broker | 152.42.238.142 | port 1883 | MQTT 3.1.1 or 5.0 |
| Security | Plain MQTT for this synthetic assessment only |
| QoS / retain | QoS 1, retain false for challenge, response and status |
| Candidate ID | Assigned by examiner; use only your own topic paths |
| Client ID | fse01-{candidate_id}-{short_random_suffix} |

| Direction | Topic |
| :--- | :--- |
| Subscribe | fse-01/{candidate_id}/challenge |
| Publish response | fse-01/{candidate_id}/response |
| Publish status | fse-01/{candidate_id}/status |

#### 8.1 Challenge shape
```json
{
  "protocol_version":"1.0", "candidate_id":"CAND-017",
  "challenge_id":"CH-7e1c4a42", "command":"PROCESS_EVENTS",
  "sent_at":"2026-10-09T10:45:00Z",
  "expires_at":"2026-10-09T10:45:15Z",
  "events":[{"source_id":"LINE-01", "event_id":"EV-101",
             "type":"COUNT", "quantity":5, "target_event_id":null,
             "event_time":"2026-10-09T10:30:00Z" }]
}
```

CSI Smart Tech • CANDIDATE ASSESSMENT | Page 5

---

**CSI SMART TECH LTD | FSE 01 | CANDIDATE ASSESSMENT**

#### 8.2 Must-do behavior
1.  Validate protocol_version, candidate_id, challenge_id, PROCESS_EVENTS command, expiry and events collection. Reject expired/mismatched challenges before processing events.
2.  Use one shared event service and PostgreSQL data model for MQTT and REST. MQTT candidate_id is envelope metadata, not part of event identity.
3.  Publish a COMPLETED response with ordered event results and the current six-field state. An invalid item may be REJECTED while challenge status is COMPLETED.
4.  Persist each challenge_id and response. Same ID + same challenge body returns the original response without processing again. Same ID + changed body returns FAILED / CHALLENGE_CONFLICT.
5.  Publish before expires_at; use stable failure codes such as VALIDATION_ERROR, CANDIDATE_MISMATCH, UNSUPPORTED_PROTOCOL, CHALLENGE_EXPIRED, CHALLENGE_CONFLICT, INTERNAL_ERROR.
6.  Publish ONLINE after subscription, HEARTBEAT at least every 30 seconds, and OFFLINE as MQTT last will where supported. Reconnect with backoff and resubscribe after a disconnect.

#### 8.3 Response example
```json
{
  "protocol_version":"1.0", "candidate_id":"CAND-017",
  "challenge_id":"CH-7e1c4a42", "status":"COMPLETED",
  "processed_at":"2026-10-09T10:45:02Z",
  "results":[{"event_id":"EV-101", "status":"ACCEPTED"}],
  "state":{"net_total":5,"processed_events":1,"pending_ack":1,
           "unresolved":0,"duplicates":0,"conflicts":0}
}
```
A challenge-level failure uses status FAILED plus error_code and message. A PUBACK only confirms transport delivery; the simulator must receive a correct response with a matching challenge ID and state.

### 9 Frontend: show the working product

Build one responsive dashboard page connected to the real backend. The examiner must be able to see how a factory user would use it, not just inspect your APIs in Postman.
*   Allow input of one JSON event or a JSON event array, submission and result messages.
*   Show six indicators: net total, processed events, pending acknowledgement, unresolved references, duplicates and conflicts.
*   Include a Pending / Exceptions table switch with useful event fields, status and reason.
*   Allow selecting one or multiple pending events, submitting acknowledgement and refreshing visible data.
*   Show MQTT connectivity, assigned candidate ID, last challenge ID/time, last response status, challenge counts and last error.
*   Handle loading, success, empty, invalid input and API failure states; use real backend values only.
*   Keep the page usable on a typical laptop and a narrow mobile viewport.

Factory workflow note: VOID messages are correction records and should be automatically marked acknowledged when they complete. The Pending table should show COUNT events for supervisor review, not VOID events.

#### 9.1 Minimum examiner demo
1.  Open the dashboard and explain who uses it and why.
2.  Send COUNT +5 to LINE-01; show the updated state from PostgreSQL.
3.  Send the same event again; show duplicate evidence without extra production.
4.  Send a VOID before its target, then the target COUNT; show automatic resolution.
5.  Choose pending rows, acknowledge them, and show the updated pending state.
6.  Show a real MQTT challenge and correlated response on the dashboard; show an error or exception state.

CSI Smart Tech • CANDIDATE ASSESSMENT | Page 6

---

**CSI SMART TECH LTD | FSE 01 | CANDIDATE ASSESSMENT**

### 10 Automated tests and review

Write at least five runnable automated tests: COUNT and total; identical duplicate without double counting; VOID-before-COUNT resolution; repeated acknowledgement; and repeated MQTT challenge without repeated event processing. Extra reliability credit is available for conflict handling, concurrent requests, mixed batches, restart recovery and reconnect.

In review, explain: What is your entity model? Which function owns a COUNT? Why do REST and MQTT call the same service? Where are database transactions used? What changes to split the MQTT, event and query modules into services later? Trace one challenge from reception to stored state and published response.

The examiner may ask you to change one rule in one function and demonstrate that the other modules still work. A correct explanation and a working change are more valuable than complicated code you cannot explain.

### 11 Submission and documentation

*   Runnable backend and frontend, required migrations for PostgreSQL, three REST APIs and a working MQTT worker.
*   At least five automated tests and a GitHub repository with at least three meaningful commits.
*   README.md with exact setup, PostgreSQL initialization, run commands, tests, all REST request examples, MQTT topics and sample flow.
*   TECHNICAL_EXPLANATION.md with entity model, module/function boundaries, transaction and duplicate strategy, pending VOID resolution, restart behavior, future microservice migration and known assumptions.
*   AI_USAGE.md plus the required AI conversation record; .env.example without real secrets.
*   Screenshots of the working dashboard, REST API tests and successful MQTT challenge; clean source ZIP without dependencies, caches or credentials.
*   Submit everything through the provided Google Form on time.

### 12 Assessment criteria

| Area | Marks | Evidence |
| :--- | :--- | :--- |
| Understanding and clarification | 10 | Useful questions, customer context, entities, correct assumptions |
| Backend and REST APIs | 20 | Three endpoints, validation and consistent behavior |
| PostgreSQL and business logic | 18 | Persistent data, transactions, COUNT/VOID correctness |
| MQTT integration | 17 | Topics, correlation, shared logic, replay safety and response |
| Frontend integration | 12 | Working dashboard, ACK flow and MQTT visibility |
| Reliability and edge cases | 10 | Concurrent delivery, retries, pending resolution and restart |
| Automated tests | 5 | Five required tests with meaningful assertions |
| Git and documentation | 4 | Commits, README and reproducible commands |
| Code ownership and architecture | 4 | Modular functions, explanation and live walkthrough |
| TOTAL | 100 | |

### 13 Optional bonus / final check

After all mandatory items work, you may add a .proto contract and demonstrate Protocol Buffers serialization for up to three bonus marks. Existing JSON contracts must continue working. Explain field numbering and compatibility.

**Before submission:** Can another engineer run your README, open the frontend, send REST and MQTT events, restart the server, and still see accurate PostgreSQL-backed state? Can you explain every important function?

END OF CANDIDATE ASSESSMENT

CSI Smart Tech • CANDIDATE ASSESSMENT | Page 7