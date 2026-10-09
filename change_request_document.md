CSI SMART TECH LTD. / ENGINEERING ASSESSMENT

# CHANGE REQUEST
**FSE-01 | Backend & Frontend Modification Requirements**

> **IMPORTANT** These requirements extend your existing FSE-01 application. Do not rebuild the project. Modify the current implementation and preserve all previously required functionality.

---

## 01 Production Quantity Validation
**BACKEND**

The factory management has introduced a new production validation rule.
*   A single **COUNT** event cannot contain a quantity greater than **500**.
*   Valid COUNT quantities are integers from **1 to 500**, inclusive.
*   If quantity exceeds 500, return **REJECTED** with a clear reason.
*   Record the rejected submission in PostgreSQL.
*   Rejected events must not increase production totals.
*   Apply validation consistently for REST API submissions and MQTT challenges.
*   Preserve existing VOID and duplicate/conflict processing rules.

**COUNT 450 ➔ ACCEPTED | COUNT 501 ➔ REJECTED**

---

## 02 Rejected Submissions in Summary
**BACKEND**

Add `rejected_submissions` to the existing `GET /api/stats?view=summary` response.
*   Count stored submission attempts with status **REJECTED**.
*   Support the existing optional **source_id** filter.
*   Exclude **DUPLICATE**, **CONFLICT** and **PENDING_REFERENCE** attempts.
*   Return **0** when there are no rejected submissions.
*   Calculate from persistent PostgreSQL data, not hardcoded or memory-only values.
*   Include the field in the MQTT challenge response's **state** object when the shared state-query service returns the production summary.
*   Keep all six existing summary fields unchanged.

---

## 03 Production Source Filter
**FRONTEND**

The factory manager must be able to view production information for a specific production line.
*   Add a Production Source filter to the dashboard.
*   Provide a source ID input, e.g. **LINE-01**.
*   Allow selection of one source or clearing the filter to see all sources.
*   Apply the selected source to Summary, Pending and Exceptions views.
*   Use the backend API's existing **source_id** filtering.
*   Show appropriate loading, empty and error states.
*   Do not hardcode production results.

---

## 04 Rejected Submissions Indicator
**FRONTEND**

The dashboard currently has six production summary indicators. Add a seventh: Rejected Submissions.
*   Display **rejected_submissions** returned by the backend.
*   Update the indicator whenever the dashboard refreshes.
*   Apply the current Production Source filter.
*   Display **0** when there are no rejected submissions.
*   Visually distinguish it from successfully processed production metrics.
*   Keep the dashboard responsive on desktop and mobile screens.

---

## FINAL TECHNICAL REQUIREMENTS

**01** Maintain the existing function-based modular monolith architecture.
**02** Do not duplicate business rules in REST and MQTT handlers.
**03** Do not introduce unnecessary new APIs or separate microservices.
**04** Preserve PostgreSQL transaction safety and existing business rules.
**05** Demonstrate at least one accepted and one rejected COUNT.
**06** Demonstrate the updated dashboard, source filtering and rejected submission count.
**07** Ensure all previously required functionality continues working.
**08** Commit the modifications to the existing GitHub repository.

**TECHNICAL REVIEW** Be prepared to identify the functions and modules changed and explain why the application did not require a complete rewrite.

---
CSI SMART TECH LTD. • ENGINEERING ASSESSMENT TEAM