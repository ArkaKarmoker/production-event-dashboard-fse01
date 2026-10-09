"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  fetchSummary,
  fetchPending,
  fetchExceptions,
  fetchMqttStatus,
  submitEvents,
  submitAck,
  SummaryState,
  PendingEvent,
  ExceptionItem,
  MqttStatus,
  SubmissionResult,
} from "@/lib/api";
import {
  Activity,
  Layers,
  Clock,
  AlertCircle,
  Copy,
  AlertTriangle,
  RefreshCw,
  Send,
  CheckCircle2,
  Radio,
  FileText,
  ChevronRight,
  Filter,
  CheckSquare,
  Square,
  ShieldCheck,
  Server,
  Zap,
} from "lucide-react";

export default function DashboardPage() {
  // State variables
  const [sourceId, setSourceId] = useState<string>("");
  const [summary, setSummary] = useState<SummaryState>({
    net_total: 0,
    processed_events: 0,
    pending_ack: 0,
    unresolved: 0,
    duplicates: 0,
    conflicts: 0,
  });
  const [pendingEvents, setPendingEvents] = useState<PendingEvent[]>([]);
  const [exceptions, setExceptions] = useState<ExceptionItem[]>([]);
  const [mqttStatus, setMqttStatus] = useState<MqttStatus | null>(null);

  const [activeTab, setActiveTab] = useState<"pending" | "exceptions">("pending");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [isSubmittingAck, setIsSubmittingAck] = useState(false);
  const [ackNotice, setAckNotice] = useState<string | null>(null);

  // Ingestion Simulator State
  const [inputPayload, setInputPayload] = useState<string>(
    JSON.stringify(
      {
        source_id: "LINE-01",
        event_id: "EV-101",
        type: "COUNT",
        quantity: 5,
        target_event_id: null,
        event_time: "2026-10-09T10:30:00Z",
      },
      null,
      2
    )
  );
  const [isSubmittingEvent, setIsSubmittingEvent] = useState(false);
  const [submissionResults, setSubmissionResults] = useState<SubmissionResult[] | null>(null);
  const [submissionError, setSubmissionError] = useState<string | null>(null);

  const [isLoading, setIsLoading] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);

  // Load all dashboard data
  const loadData = useCallback(async () => {
    try {
      setIsLoading(true);
      const [sum, pend, exc, mqtt] = await Promise.all([
        fetchSummary(sourceId || undefined),
        fetchPending(sourceId || undefined),
        fetchExceptions(sourceId || undefined),
        fetchMqttStatus().catch(() => null),
      ]);
      setSummary(sum);
      setPendingEvents(pend);
      setExceptions(exc);
      if (mqtt) setMqttStatus(mqtt);
    } catch (err) {
      console.error("Dashboard refresh error:", err);
    } finally {
      setIsLoading(false);
    }
  }, [sourceId]);

  useEffect(() => {
    loadData();
    if (!autoRefresh) return;
    const interval = setInterval(loadData, 3500);
    return () => clearInterval(interval);
  }, [loadData, autoRefresh]);

  // Preset payload helpers for examiner demo
  const loadPreset = (type: string) => {
    const nowIso = new Date().toISOString();
    switch (type) {
      case "count-5":
        setInputPayload(
          JSON.stringify(
            {
              source_id: "LINE-01",
              event_id: "EV-101",
              type: "COUNT",
              quantity: 5,
              target_event_id: null,
              event_time: nowIso,
            },
            null,
            2
          )
        );
        break;
      case "duplicate":
        setInputPayload(
          JSON.stringify(
            {
              source_id: "LINE-01",
              event_id: "EV-101",
              type: "COUNT",
              quantity: 5,
              target_event_id: null,
              event_time: nowIso,
            },
            null,
            2
          )
        );
        break;
      case "void-before-count":
        setInputPayload(
          JSON.stringify(
            {
              source_id: "LINE-01",
              event_id: "VOID-201",
              type: "VOID",
              quantity: null,
              target_event_id: "EV-201",
              event_time: nowIso,
            },
            null,
            2
          )
        );
        break;
      case "matching-count":
        setInputPayload(
          JSON.stringify(
            {
              source_id: "LINE-01",
              event_id: "EV-201",
              type: "COUNT",
              quantity: 8,
              target_event_id: null,
              event_time: nowIso,
            },
            null,
            2
          )
        );
        break;
      case "batch":
        setInputPayload(
          JSON.stringify(
            [
              {
                source_id: "LINE-01",
                event_id: "EV-BATCH-1",
                type: "COUNT",
                quantity: 12,
                event_time: nowIso,
              },
              {
                source_id: "LINE-01",
                event_id: "EV-BATCH-2",
                type: "COUNT",
                quantity: -10, // Invalid item
                event_time: nowIso,
              },
              {
                source_id: "LINE-01",
                event_id: "EV-BATCH-3",
                type: "COUNT",
                quantity: 15,
                event_time: nowIso,
              },
            ],
            null,
            2
          )
        );
        break;
    }
  };

  // Handle Event Submission
  const handleEventSubmit = async () => {
    setSubmissionError(null);
    setSubmissionResults(null);
    setIsSubmittingEvent(true);
    try {
      const parsed = JSON.parse(inputPayload);
      const res = await submitEvents(parsed);
      setSubmissionResults(res.results);
      await loadData();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setSubmissionError(err.message);
      } else {
        setSubmissionError("Invalid JSON or server error");
      }
    } finally {
      setIsSubmittingEvent(false);
    }
  };

  // Handle Select All Checkbox
  const toggleSelectAll = () => {
    if (selectedIds.length === pendingEvents.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(pendingEvents.map((p) => p.event_id));
    }
  };

  const toggleSelectRow = (id: string) => {
    if (selectedIds.includes(id)) {
      setSelectedIds(selectedIds.filter((x) => x !== id));
    } else {
      setSelectedIds([...selectedIds, id]);
    }
  };

  // Handle Supervisor Acknowledgment Submission
  const handleAcknowledge = async () => {
    if (selectedIds.length === 0) return;
    setIsSubmittingAck(true);
    setAckNotice(null);
    try {
      const results = await submitAck(selectedIds);
      const ackedCount = results.filter((r) => r.status === "ACKED").length;
      const alreadyAcked = results.filter((r) => r.status === "ALREADY_ACKED").length;
      setAckNotice(`Acknowledged ${ackedCount} event(s) successfully${alreadyAcked > 0 ? ` (${alreadyAcked} were already acknowledged)` : ""}.`);
      setSelectedIds([]);
      await loadData();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setAckNotice(`ACK Error: ${err.message}`);
      }
    } finally {
      setIsSubmittingAck(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Top Header */}
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-30 px-4 lg:px-8 py-3.5">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-400 flex items-center justify-center shadow-lg shadow-emerald-500/20">
              <Zap className="w-5 h-5 text-slate-950 font-bold" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-bold tracking-tight text-white">
                  CSI SMART TECH
                </h1>
                <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 font-medium border border-emerald-500/20">
                  FSE 01 Live
                </span>
              </div>
              <p className="text-xs text-slate-400">
                NorthBridge Garments • Production Event & MQTT Supervisor Console
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3 w-full sm:w-auto justify-between sm:justify-end">
            {/* Candidate Badge */}
            <div className="flex items-center gap-2 text-xs bg-slate-800/80 border border-slate-700/60 px-3 py-1.5 rounded-lg">
              <span className="text-slate-400">Candidate:</span>
              <span className="font-semibold text-slate-200">Arka Karmoker</span>
              <span className="px-1.5 py-0.2 rounded bg-indigo-500/20 text-indigo-300 font-mono text-[11px]">
                ID: 12
              </span>
            </div>

            {/* Line Filter */}
            <div className="flex items-center gap-1.5 bg-slate-800/80 border border-slate-700/60 px-2.5 py-1.5 rounded-lg text-xs">
              <Filter className="w-3.5 h-3.5 text-slate-400" />
              <input
                type="text"
                placeholder="Filter Source (e.g. LINE-01)"
                value={sourceId}
                onChange={(e) => setSourceId(e.target.value.trim())}
                className="bg-transparent text-slate-200 placeholder-slate-500 outline-none w-36 text-xs"
              />
              {sourceId && (
                <button
                  onClick={() => setSourceId("")}
                  className="text-slate-400 hover:text-white text-[11px]"
                >
                  ✕
                </button>
              )}
            </div>

            {/* Refresh Controls */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => setAutoRefresh(!autoRefresh)}
                className={`text-xs px-2.5 py-1.5 rounded-lg border transition ${
                  autoRefresh
                    ? "bg-emerald-950/40 text-emerald-300 border-emerald-800/50"
                    : "bg-slate-800 text-slate-400 border-slate-700"
                }`}
                title="Toggle Live Auto-refresh"
              >
                Auto {autoRefresh ? "ON" : "OFF"}
              </button>

              <button
                onClick={loadData}
                disabled={isLoading}
                className="flex items-center gap-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold px-3 py-1.5 rounded-lg transition shadow disabled:opacity-50"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
                <span>Refresh</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 lg:p-8 space-y-6">
        {/* KPI 6 Indicator Cards */}
        <section className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3.5">
          {/* 1. Net Total */}
          <div className="bg-slate-900/90 border border-emerald-500/30 rounded-xl p-4 shadow-sm relative overflow-hidden group">
            <div className="absolute top-0 right-0 w-20 h-20 bg-emerald-500/10 rounded-full blur-xl pointer-events-none group-hover:bg-emerald-500/20 transition" />
            <div className="flex items-center justify-between text-slate-400 text-xs mb-2">
              <span>Net Total Pieces</span>
              <Activity className="w-4 h-4 text-emerald-400" />
            </div>
            <div className="text-2xl lg:text-3xl font-extrabold text-emerald-400 tracking-tight">
              {summary.net_total.toLocaleString()}
            </div>
            <div className="text-[11px] text-slate-400 mt-1 flex items-center gap-1">
              <CheckCircle2 className="w-3 h-3 text-emerald-500" />
              <span>Verified production</span>
            </div>
          </div>

          {/* 2. Processed Events */}
          <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 shadow-sm">
            <div className="flex items-center justify-between text-slate-400 text-xs mb-2">
              <span>Processed</span>
              <Layers className="w-4 h-4 text-blue-400" />
            </div>
            <div className="text-2xl lg:text-3xl font-extrabold text-blue-400 tracking-tight">
              {summary.processed_events.toLocaleString()}
            </div>
            <div className="text-[11px] text-slate-400 mt-1">Completed COUNT & VOID</div>
          </div>

          {/* 3. Pending Ack */}
          <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 shadow-sm">
            <div className="flex items-center justify-between text-slate-400 text-xs mb-2">
              <span>Pending ACK</span>
              <Clock className="w-4 h-4 text-amber-400" />
            </div>
            <div className="text-2xl lg:text-3xl font-extrabold text-amber-400 tracking-tight">
              {summary.pending_ack.toLocaleString()}
            </div>
            <div className="text-[11px] text-slate-400 mt-1">Awaiting review</div>
          </div>

          {/* 4. Unresolved */}
          <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 shadow-sm">
            <div className="flex items-center justify-between text-slate-400 text-xs mb-2">
              <span>Unresolved</span>
              <AlertCircle className="w-4 h-4 text-purple-400" />
            </div>
            <div className="text-2xl lg:text-3xl font-extrabold text-purple-400 tracking-tight">
              {summary.unresolved.toLocaleString()}
            </div>
            <div className="text-[11px] text-slate-400 mt-1">Pending VOID references</div>
          </div>

          {/* 5. Duplicates */}
          <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 shadow-sm">
            <div className="flex items-center justify-between text-slate-400 text-xs mb-2">
              <span>Duplicates</span>
              <Copy className="w-4 h-4 text-slate-400" />
            </div>
            <div className="text-2xl lg:text-3xl font-extrabold text-slate-300 tracking-tight">
              {summary.duplicates.toLocaleString()}
            </div>
            <div className="text-[11px] text-slate-400 mt-1">Safe replays prevented</div>
          </div>

          {/* 6. Conflicts */}
          <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 shadow-sm">
            <div className="flex items-center justify-between text-slate-400 text-xs mb-2">
              <span>Conflicts</span>
              <AlertTriangle className="w-4 h-4 text-rose-400" />
            </div>
            <div className="text-2xl lg:text-3xl font-extrabold text-rose-400 tracking-tight">
              {summary.conflicts.toLocaleString()}
            </div>
            <div className="text-[11px] text-slate-400 mt-1">Payload mismatches</div>
          </div>
        </section>

        {/* MQTT Live Integration Banner */}
        <section className="bg-slate-900/70 border border-slate-800/90 rounded-xl p-4 text-xs">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <span className="relative flex h-3 w-3">
                  <span
                    className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                      mqttStatus?.is_connected ? "bg-emerald-400" : "bg-rose-400"
                    }`}
                  ></span>
                  <span
                    className={`relative inline-flex rounded-full h-3 w-3 ${
                      mqttStatus?.is_connected ? "bg-emerald-500" : "bg-rose-500"
                    }`}
                  ></span>
                </span>
                <span className="font-semibold uppercase tracking-wider text-slate-200">
                  MQTT Device Simulator:
                </span>
              </div>
              <span
                className={`px-2 py-0.5 rounded font-mono font-bold text-[11px] ${
                  mqttStatus?.is_connected
                    ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                    : "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                }`}
              >
                {mqttStatus?.is_connected ? "CONNECTED (ONLINE)" : "DISCONNECTED / CONNECTING"}
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-slate-300 text-[11px]">
              <div>
                <span className="text-slate-500 block">Broker:</span>
                <span className="font-mono text-slate-200">
                  {mqttStatus?.broker_host || "152.42.238.142"}:{mqttStatus?.broker_port || 1883}
                </span>
              </div>
              <div>
                <span className="text-slate-500 block">Topic Base:</span>
                <span className="font-mono text-indigo-300">
                  fse-01/{mqttStatus?.candidate_id || "12"}/*
                </span>
              </div>
              <div>
                <span className="text-slate-500 block">Challenges Handled:</span>
                <span className="font-bold text-slate-200">
                  {mqttStatus?.total_challenges_received ?? 0}
                </span>
              </div>
              <div>
                <span className="text-slate-500 block">Last Response:</span>
                <span
                  className={`font-mono font-medium ${
                    mqttStatus?.last_response_status === "COMPLETED"
                      ? "text-emerald-400"
                      : "text-slate-400"
                  }`}
                >
                  {mqttStatus?.last_response_status || "IDLE"}
                </span>
              </div>
            </div>
          </div>
        </section>

        {/* Lower Main Grid: Left Ingestion Simulator, Right Supervisor Review */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* LEFT: Event Ingestion Terminal (5 Cols) */}
          <section className="lg:col-span-5 bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Radio className="w-4 h-4 text-emerald-400" />
                <h2 className="font-bold text-sm text-white">Event Ingestion Terminal</h2>
              </div>
              <span className="text-[11px] font-mono text-slate-400">POST /api/events</span>
            </div>

            {/* Quick-fill preset buttons */}
            <div>
              <div className="text-[11px] text-slate-400 mb-1.5 font-medium">
                Examiner Demo Quick Presets:
              </div>
              <div className="flex flex-wrap gap-1.5">
                <button
                  type="button"
                  onClick={() => loadPreset("count-5")}
                  className="text-[11px] bg-slate-800 hover:bg-slate-700 text-slate-200 px-2.5 py-1 rounded border border-slate-700 transition"
                >
                  COUNT +5
                </button>
                <button
                  type="button"
                  onClick={() => loadPreset("duplicate")}
                  className="text-[11px] bg-slate-800 hover:bg-slate-700 text-slate-200 px-2.5 py-1 rounded border border-slate-700 transition"
                >
                  Duplicate EV-101
                </button>
                <button
                  type="button"
                  onClick={() => loadPreset("void-before-count")}
                  className="text-[11px] bg-slate-800 hover:bg-slate-700 text-purple-300 px-2.5 py-1 rounded border border-purple-800/50 transition"
                >
                  VOID Before COUNT
                </button>
                <button
                  type="button"
                  onClick={() => loadPreset("matching-count")}
                  className="text-[11px] bg-slate-800 hover:bg-slate-700 text-emerald-300 px-2.5 py-1 rounded border border-emerald-800/50 transition"
                >
                  Matching COUNT
                </button>
                <button
                  type="button"
                  onClick={() => loadPreset("batch")}
                  className="text-[11px] bg-slate-800 hover:bg-slate-700 text-amber-300 px-2.5 py-1 rounded border border-amber-800/50 transition"
                >
                  Batch (Mixed)
                </button>
              </div>
            </div>

            {/* JSON Code Input */}
            <div>
              <textarea
                value={inputPayload}
                onChange={(e) => setInputPayload(e.target.value)}
                rows={10}
                className="w-full bg-slate-950 font-mono text-xs text-emerald-400 p-3 rounded-lg border border-slate-800 focus:border-emerald-500 focus:outline-none resize-none leading-relaxed"
                placeholder="Enter event JSON object or array..."
              />
            </div>

            {/* Submit Button */}
            <button
              onClick={handleEventSubmit}
              disabled={isSubmittingEvent}
              className="w-full bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-bold text-xs py-2.5 rounded-lg flex items-center justify-center gap-2 transition disabled:opacity-50 shadow-md shadow-emerald-600/10"
            >
              <Send className="w-3.5 h-3.5" />
              <span>{isSubmittingEvent ? "Processing..." : "Submit Event(s)"}</span>
            </button>

            {/* Results / Error View */}
            {submissionError && (
              <div className="bg-rose-950/40 border border-rose-800/50 rounded-lg p-3 text-xs text-rose-300 flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                <div>
                  <div className="font-semibold">Submission Failed</div>
                  <div className="text-[11px] mt-0.5 text-rose-400">{submissionError}</div>
                </div>
              </div>
            )}

            {submissionResults && (
              <div className="bg-slate-950 border border-slate-800 rounded-lg p-3 space-y-2">
                <div className="text-xs font-semibold text-slate-300 flex items-center justify-between">
                  <span>Response Results</span>
                  <span className="text-[11px] font-mono text-slate-500">
                    {submissionResults.length} item(s)
                  </span>
                </div>
                <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                  {submissionResults.map((res, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between bg-slate-900 px-2.5 py-1.5 rounded border border-slate-800/80 text-xs"
                    >
                      <span className="font-mono font-medium text-slate-200">
                        {res.event_id}
                      </span>
                      <div className="flex items-center gap-2">
                        <span
                          className={`text-[10px] font-bold px-2 py-0.5 rounded font-mono ${
                            res.status === "ACCEPTED"
                              ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                              : res.status === "DUPLICATE"
                              ? "bg-slate-500/20 text-slate-300 border border-slate-500/30"
                              : res.status === "PENDING_REFERENCE"
                              ? "bg-purple-500/20 text-purple-300 border border-purple-500/30"
                              : res.status === "CONFLICT"
                              ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                              : "bg-rose-500/20 text-rose-400 border border-rose-500/30"
                          }`}
                        >
                          {res.status}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </section>

          {/* RIGHT: Supervisor Operations (7 Cols) */}
          <section className="lg:col-span-7 bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
            {/* Header Tabs */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setActiveTab("pending")}
                  className={`text-xs font-bold px-3 py-1.5 rounded-lg transition flex items-center gap-1.5 ${
                    activeTab === "pending"
                      ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  <ShieldCheck className="w-3.5 h-3.5" />
                  <span>Pending Review ({pendingEvents.length})</span>
                </button>

                <button
                  type="button"
                  onClick={() => setActiveTab("exceptions")}
                  className={`text-xs font-bold px-3 py-1.5 rounded-lg transition flex items-center gap-1.5 ${
                    activeTab === "exceptions"
                      ? "bg-purple-500/20 text-purple-300 border border-purple-500/30"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  <AlertCircle className="w-3.5 h-3.5" />
                  <span>Exceptions & Conflicts ({exceptions.length})</span>
                </button>
              </div>

              {activeTab === "pending" && (
                <button
                  onClick={handleAcknowledge}
                  disabled={selectedIds.length === 0 || isSubmittingAck}
                  className="bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-bold text-xs px-3.5 py-1.5 rounded-lg transition disabled:opacity-40 flex items-center gap-1.5 shadow"
                >
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>Acknowledge Selected ({selectedIds.length})</span>
                </button>
              )}
            </div>

            {/* Notice Banner */}
            {ackNotice && (
              <div className="bg-emerald-950/40 border border-emerald-800/40 rounded-lg p-2.5 text-xs text-emerald-300 flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>{ackNotice}</span>
              </div>
            )}

            {/* TAB 1: Pending Table */}
            {activeTab === "pending" && (
              <div className="overflow-x-auto rounded-lg border border-slate-800">
                <table className="w-full text-left text-xs text-slate-300">
                  <thead className="bg-slate-950 text-slate-400 font-semibold border-b border-slate-800">
                    <tr>
                      <th className="p-3 w-10 text-center">
                        <button
                          type="button"
                          onClick={toggleSelectAll}
                          className="text-slate-400 hover:text-white"
                        >
                          {pendingEvents.length > 0 &&
                          selectedIds.length === pendingEvents.length ? (
                            <CheckSquare className="w-4 h-4 text-emerald-400" />
                          ) : (
                            <Square className="w-4 h-4" />
                          )}
                        </button>
                      </th>
                      <th className="p-3">Event ID</th>
                      <th className="p-3">Line</th>
                      <th className="p-3">Type</th>
                      <th className="p-3">Qty</th>
                      <th className="p-3">Event Time</th>
                      <th className="p-3">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/70">
                    {pendingEvents.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="p-8 text-center text-slate-500">
                          <CheckCircle2 className="w-8 h-8 mx-auto mb-2 text-slate-600" />
                          <div>No pending events waiting for supervisor review.</div>
                          <div className="text-[11px] text-slate-600 mt-1">
                            Send a COUNT event from the simulator to see it here.
                          </div>
                        </td>
                      </tr>
                    ) : (
                      pendingEvents.map((evt) => {
                        const isSelected = selectedIds.includes(evt.event_id);
                        return (
                          <tr
                            key={evt.event_id}
                            onClick={() => toggleSelectRow(evt.event_id)}
                            className={`cursor-pointer transition hover:bg-slate-800/50 ${
                              isSelected ? "bg-emerald-950/20" : ""
                            }`}
                          >
                            <td className="p-3 text-center">
                              {isSelected ? (
                                <CheckSquare className="w-4 h-4 text-emerald-400" />
                              ) : (
                                <Square className="w-4 h-4 text-slate-500" />
                              )}
                            </td>
                            <td className="p-3 font-mono font-medium text-white">
                              {evt.event_id}
                            </td>
                            <td className="p-3 font-mono text-slate-400">{evt.source_id}</td>
                            <td className="p-3">
                              <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-blue-500/20 text-blue-300 border border-blue-500/30">
                                {evt.type}
                              </span>
                            </td>
                            <td className="p-3 font-extrabold text-emerald-400 font-mono">
                              +{evt.quantity}
                            </td>
                            <td className="p-3 text-slate-400 text-[11px]">
                              {evt.event_time ? new Date(evt.event_time).toLocaleTimeString() : "-"}
                            </td>
                            <td className="p-3">
                              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                                READY_FOR_ACK
                              </span>
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            )}

            {/* TAB 2: Exceptions Table */}
            {activeTab === "exceptions" && (
              <div className="overflow-x-auto rounded-lg border border-slate-800">
                <table className="w-full text-left text-xs text-slate-300">
                  <thead className="bg-slate-950 text-slate-400 font-semibold border-b border-slate-800">
                    <tr>
                      <th className="p-3">Category</th>
                      <th className="p-3">Event ID</th>
                      <th className="p-3">Line</th>
                      <th className="p-3">Reason / Details</th>
                      <th className="p-3">Timestamp</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/70">
                    {exceptions.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="p-8 text-center text-slate-500">
                          <CheckCircle2 className="w-8 h-8 mx-auto mb-2 text-slate-600" />
                          <div>No active exceptions, unresolved voids, or conflicts found.</div>
                        </td>
                      </tr>
                    ) : (
                      exceptions.map((ex, idx) => (
                        <tr key={idx} className="hover:bg-slate-800/40 transition">
                          <td className="p-3">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-bold font-mono ${
                                ex.category === "UNRESOLVED_REFERENCE"
                                  ? "bg-purple-500/20 text-purple-300 border border-purple-500/30"
                                  : ex.category === "CONFLICT"
                                  ? "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                                  : "bg-slate-600/20 text-slate-300 border border-slate-600/30"
                              }`}
                            >
                              {ex.category}
                            </span>
                          </td>
                          <td className="p-3 font-mono font-medium text-white">
                            {ex.event_id}
                          </td>
                          <td className="p-3 font-mono text-slate-400">{ex.source_id}</td>
                          <td className="p-3 text-slate-300 text-[11px] max-w-xs truncate">
                            {ex.reason}
                          </td>
                          <td className="p-3 text-slate-500 text-[11px]">
                            {ex.timestamp ? new Date(ex.timestamp).toLocaleTimeString() : "-"}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            )}

            {/* Supervisor Workflow Note Footer */}
            <div className="text-[11px] text-slate-500 border-t border-slate-800/60 pt-3">
              <span className="font-semibold text-slate-400">Garment Workflow Rule:</span> VOID
              correction events are automatically acknowledged upon successful reversal. Only
              completed COUNT events requiring supervisor sign-off appear in the Pending Review
              table.
            </div>
          </section>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-900 bg-slate-950 px-4 lg:px-8 py-3 text-center text-xs text-slate-600">
        CSI Smart Tech Ltd • FSE 01 Practical Assessment • Candidate Arka Karmoker (ID: 12) •
        PostgreSQL 16 & MQTT 3.1.1/5.0
      </footer>
    </div>
  );
}
