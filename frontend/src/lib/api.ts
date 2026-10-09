/**
 * API client for CSI Smart Tech FSE 01 Backend
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface SummaryState {
  net_total: number;
  processed_events: number;
  pending_ack: number;
  unresolved: number;
  duplicates: number;
  conflicts: number;
  rejected_submissions: number;
}

export interface PendingEvent {
  event_id: string;
  source_id: string;
  type: string;
  quantity: number | null;
  target_event_id: string | null;
  event_time: string | null;
  received_at: string | null;
  status: string;
  is_voided: boolean;
  acknowledged_at: string | null;
}

export interface ExceptionItem {
  category: string;
  event_id: string;
  source_id: string;
  target_event_id?: string | null;
  reason: string;
  timestamp: string | null;
  raw_payload?: Record<string, unknown>;
}

export interface MqttStatus {
  is_connected: boolean;
  broker_host: string;
  broker_port: number;
  candidate_id: string;
  client_id: string;
  connected_at: string | null;
  last_heartbeat_at: string | null;
  last_challenge_id: string | null;
  last_challenge_time: string | null;
  last_response_status: string | null;
  total_challenges_received: number;
  last_error: string | null;
}

export interface SubmissionResult {
  event_id: string;
  status: "ACCEPTED" | "DUPLICATE" | "CONFLICT" | "PENDING_REFERENCE" | "REJECTED";
  message: string;
}

export interface AckResult {
  event_id: string;
  status: "ACKED" | "ALREADY_ACKED" | "NOT_READY" | "NOT_FOUND";
}

export async function fetchSummary(sourceId?: string): Promise<SummaryState> {
  const url = new URL(`${API_BASE_URL}/api/state`);
  url.searchParams.set("view", "summary");
  if (sourceId) url.searchParams.set("source_id", sourceId);

  const res = await fetch(url.toString(), { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch summary: ${res.statusText}`);
  return res.json();
}

export async function fetchPending(sourceId?: string): Promise<PendingEvent[]> {
  const url = new URL(`${API_BASE_URL}/api/state`);
  url.searchParams.set("view", "pending");
  if (sourceId) url.searchParams.set("source_id", sourceId);

  const res = await fetch(url.toString(), { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch pending: ${res.statusText}`);
  return res.json();
}

export async function fetchExceptions(sourceId?: string): Promise<ExceptionItem[]> {
  const url = new URL(`${API_BASE_URL}/api/state`);
  url.searchParams.set("view", "exceptions");
  if (sourceId) url.searchParams.set("source_id", sourceId);

  const res = await fetch(url.toString(), { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch exceptions: ${res.statusText}`);
  return res.json();
}

export async function submitEvents(payload: unknown): Promise<{ results: SubmissionResult[] }> {
  const res = await fetch(`${API_BASE_URL}/api/events`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok && res.status !== 200) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.error || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function submitAck(eventIds: string[]): Promise<AckResult[]> {
  const res = await fetch(`${API_BASE_URL}/api/ack`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ event_ids: eventIds }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchMqttStatus(): Promise<MqttStatus> {
  const res = await fetch(`${API_BASE_URL}/api/mqtt/status`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch MQTT status: ${res.statusText}`);
  return res.json();
}
