"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { CommandPod, PodRings, WorkStation } from "@/components/office/AgentDesk";
import ChatPanel from "@/components/office/ChatPanel";
import FeedPanel from "@/components/office/FeedPanel";
import { api } from "@/lib/api";
import { getSocket } from "@/lib/socket";
import type { AgentInfo, Analytics, ChatMessage, HealthInfo, OfficeEvent } from "@/lib/types";

const TILE = 88;
const GRID = 9;

let msgCounter = 0;
const nextMsgId = () => `m${++msgCounter}`;

export default function Office() {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [events, setEvents] = useState<OfficeEvent[]>([]);
  const [thinking, setThinking] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [health, setHealth] = useState<HealthInfo | null>(null);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [zoom, setZoom] = useState(1);
  const [connected, setConnected] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showToast = useCallback((msg: string) => {
    setToast(msg);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 3500);
  }, []);

  const patchAgent = useCallback((id: string, patch: Partial<AgentInfo>) => {
    setAgents((prev) => prev.map((a) => (a.id === id ? { ...a, ...patch } : a)));
  }, []);

  const refreshAgents = useCallback(async () => {
    try {
      const { agents: list } = await api.agents();
      setAgents(list);
    } catch {
      /* backend offline — keep last state */
    }
  }, []);

  // ---- initial load + periodic refresh --------------------------------
  useEffect(() => {
    const tick = () => {
      refreshAgents();
      api.health().then(setHealth).catch(() => setHealth(null));
      api.analytics().then(setAnalytics).catch(() => {});
    };
    const first = setTimeout(tick, 0); // async — avoids sync setState in effect body
    const interval = setInterval(tick, 15000);
    return () => {
      clearTimeout(first);
      clearInterval(interval);
    };
  }, [refreshAgents]);

  // ---- socket.io live events -------------------------------------------
  useEffect(() => {
    const socket = getSocket();

    const onConnect = () => setConnected(true);
    const onDisconnect = () => setConnected(false);

    const onOfficeEvent = (envelope: OfficeEvent) => {
      setEvents((prev) => [envelope, ...prev].slice(0, 60));

      const d = envelope.data ?? {};
      switch (envelope.event) {
        case "AgentStarted":
          if (d.agent)
            patchAgent(String(d.agent), {
              state: "working",
              current_action: (d.action as string) ?? "working...",
            });
          break;
        case "AgentThinking":
          if (d.agent) patchAgent(String(d.agent), { state: "thinking" });
          break;
        case "AgentFinished":
          if (d.agent)
            patchAgent(String(d.agent), { state: "idle", current_action: null });
          break;
        case "TaskCompleted":
        case "TaskFailed":
          refreshAgents(); // pick up tasks_done counters
          break;
        case "ChatMessage":
          if (d.role === "jarvis" && d.text) {
            setMessages((prev) => [
              ...prev,
              { id: nextMsgId(), role: "jarvis", text: String(d.text), ts: Date.now() },
            ]);
            setThinking(false);
          }
          break;
      }
    };

    socket.on("connect", onConnect);
    socket.on("disconnect", onDisconnect);
    socket.on("office_event", onOfficeEvent);
    return () => {
      socket.off("connect", onConnect);
      socket.off("disconnect", onDisconnect);
      socket.off("office_event", onOfficeEvent);
    };
  }, [patchAgent, refreshAgents]);

  // ---- actions ----------------------------------------------------------
  const selectedAgent = agents.find((a) => a.id === selectedId) ?? null;

  const sendChat = useCallback(
    async (text: string, agentId?: string | null) => {
      setMessages((prev) => [
        ...prev,
        { id: nextMsgId(), role: "user", text, ts: Date.now() },
      ]);
      setThinking(true);
      try {
        const res = await api.chat(text, agentId ?? undefined);
        // ChatMessage socket event may have already added the reply — dedupe by text
        setMessages((prev) => {
          if (prev.some((m) => m.role === "jarvis" && m.text === res.reply)) return prev;
          return [
            ...prev,
            { id: nextMsgId(), role: "jarvis", agent: res.agent, text: res.reply, ts: Date.now() },
          ];
        });
      } catch {
        setMessages((prev) => [
          ...prev,
          {
            id: nextMsgId(),
            role: "jarvis",
            text: "Backend se connect nahi ho paya... 😓 Backend chalu hai na? (uvicorn main:app --reload)",
            ts: Date.now(),
          },
        ]);
      } finally {
        setThinking(false);
      }
    },
    []
  );

  const onVoice = useCallback(
    async (blob: Blob) => {
      showToast("🎤 Sun raha hoon...");
      try {
        const res = await api.voiceStt(blob);
        if (res.text) {
          sendChat(res.text, selectedId);
        } else {
          showToast(res.message ?? "Voice samajh nahi aaya, dobara bolo 🙏");
        }
      } catch {
        showToast("Voice server se connect nahi hua 😓");
      }
    },
    [sendChat, selectedId, showToast]
  );

  const onFile = useCallback(
    async (file: File) => {
      showToast(`📎 ${file.name} upload ho raha hai...`);
      try {
        const res = await api.uploadFile(file);
        showToast(
          `✅ ${file.name} memory mein save ho gaya (${res.chunks_indexed} chunks indexed) — ab pucho kuch bhi iske baare mein!`
        );
      } catch {
        showToast("❌ File upload fail — backend check karo");
      }
    },
    [showToast]
  );

  const jarvis = agents.find((a) => a.id === "jarvis");
  const workers = agents.filter((a) => a.id !== "jarvis");
  const workingCount = agents.filter((a) => a.state === "working" || a.state === "thinking").length;

  return (
    <div className="flex h-dvh w-full flex-col bg-[#05070d] text-slate-200">
      {/* ===== top bar ===== */}
      <header className="z-30 flex items-center gap-4 border-b border-slate-800/60 bg-[#070a12]/90 px-5 py-2.5 backdrop-blur">
        <div className="flex items-center gap-2.5">
          <span className="text-xl">🧠</span>
          <div>
            <div className="pixel-font text-[10px] tracking-widest text-cyan-300 neon-text">
              15-AI · JARVIS OFFICE
            </div>
            <div className="pixel-font mt-1 text-[7px] tracking-wider text-slate-500">
              build for comfort · 15 agents · ek mission
            </div>
          </div>
        </div>

        <div className="ml-auto flex items-center gap-2 text-[10px]">
          <span
            className={`rounded-full border px-2.5 py-1 font-semibold tracking-wide ${
              connected
                ? "border-emerald-400/40 bg-emerald-400/10 text-emerald-300"
                : "border-red-400/40 bg-red-400/10 text-red-300"
            }`}
          >
            ● {connected ? "LIVE" : "OFFLINE"}
          </span>
          <span className="rounded-full border border-slate-700/60 bg-slate-800/50 px-2.5 py-1 text-slate-400">
            👷 {workingCount}/{agents.length || 15} active
          </span>
          {health && (
            <span
              className={`rounded-full border px-2.5 py-1 ${
                health.llm === "ready"
                  ? "border-cyan-400/40 bg-cyan-400/10 text-cyan-300"
                  : "border-amber-400/40 bg-amber-400/10 text-amber-300"
              }`}
              title="GLM brain status"
            >
              🧠 {health.llm === "ready" ? "GLM" : "no key"}
            </span>
          )}
          {analytics && (
            <span className="hidden rounded-full border border-slate-700/60 bg-slate-800/50 px-2.5 py-1 text-slate-400 md:inline">
              📌 {analytics.user_tasks.total} tasks · 🗄️ {analytics.memory.vector_memories} memories
            </span>
          )}
        </div>
      </header>

      {/* ===== main area ===== */}
      <div className="relative flex min-h-0 flex-1">
        {/* left: mission control */}
        <aside className="z-20 hidden w-64 shrink-0 p-3 lg:block">
          <FeedPanel events={events} />
        </aside>

        {/* center: the pixel office */}
        <main className="office-stage relative min-w-0 flex-1">
          <div className="office-aurora" />
          <div className="scene-center">
            <div
              className="floor-pixel"
              style={{
                width: TILE * GRID,
                height: TILE * GRID,
                transform: `scale(${zoom})`,
                transition: "transform 0.25s steps(6)",
              }}
            >
              {/* rainbow pixel floor tiles */}
              {Array.from({ length: GRID }, (_, gx) =>
                Array.from({ length: GRID }, (_, gy) => (
                  <div
                    key={`t-${gx}-${gy}`}
                    className={`tile-pixel${(gx + gy) % 2 ? " alt" : ""}`}
                    style={{
                      width: TILE,
                      height: TILE,
                      left: gx * TILE,
                      top: gy * TILE,
                      ["--hue" as string]: ((gx * 40 + gy * 25) % 360),
                    }}
                  />
                ))
              )}

              {/* corner lamps */}
              {[
                [0, 0],
                [GRID - 1, 0],
                [0, GRID - 1],
                [GRID - 1, GRID - 1],
              ].map(([gx, gy], i) => (
                <div
                  key={`lamp-${i}`}
                  className="px-lamp"
                  style={{
                    left: gx * TILE + TILE / 2,
                    top: gy * TILE + TILE / 2,
                    ["--hue" as string]: i * 90,
                  }}
                />
              ))}

              {/* JARVIS command pod */}
              {jarvis && <PodRings gx={jarvis.desk[0]} gy={jarvis.desk[1]} />}
              {jarvis && <CommandPod agent={jarvis} onClick={() => setSelectedId(null)} />}

              {/* agent workstations */}
              {workers.map((a) => (
                <WorkStation
                  key={a.id}
                  agent={a}
                  selected={selectedId === a.id}
                  onClick={(agent) => setSelectedId(agent.id)}
                />
              ))}
            </div>
          </div>

          {/* zoom controls */}
          <div className="absolute bottom-4 left-1/2 z-20 flex -translate-x-1/2 items-center gap-1.5 rounded-full border border-slate-700/60 bg-[#070a12]/90 px-2 py-1.5 backdrop-blur">
            <button
              onClick={() => setZoom((z) => Math.max(0.5, +(z - 0.15).toFixed(2)))}
              className="h-7 w-7 rounded-full text-slate-400 transition hover:bg-slate-800 hover:text-cyan-300"
            >
              −
            </button>
            <span className="w-10 text-center text-[10px] text-slate-500">{Math.round(zoom * 100)}%</span>
            <button
              onClick={() => setZoom((z) => Math.min(2, +(z + 0.15).toFixed(2)))}
              className="h-7 w-7 rounded-full text-slate-400 transition hover:bg-slate-800 hover:text-cyan-300"
            >
              +
            </button>
          </div>

          {/* toast */}
          {toast && (
            <div className="msg-in absolute left-1/2 top-4 z-30 max-w-md -translate-x-1/2 rounded-xl border border-cyan-400/40 bg-[#070a12]/95 px-4 py-2.5 text-xs text-cyan-100 shadow-lg backdrop-blur">
              {toast}
            </div>
          )}

          {/* selected agent chip */}
          {selectedAgent && (
            <div className="absolute left-4 top-4 z-20 flex items-center gap-2 rounded-xl border border-slate-700/60 bg-[#070a12]/90 px-3 py-2 backdrop-blur">
              <span className="text-lg">{selectedAgent.emoji}</span>
              <div>
                <div className="text-xs font-bold" style={{ color: selectedAgent.accent }}>
                  {selectedAgent.name} · {selectedAgent.role}
                </div>
                <div className="text-[10px] text-slate-500">
                  {selectedAgent.tasks_done} tasks done · direct chat open
                </div>
              </div>
              <button
                onClick={() => setSelectedId(null)}
                className="ml-2 text-slate-500 transition hover:text-slate-300"
              >
                ✕
              </button>
            </div>
          )}
        </main>

        {/* right: chat */}
        <aside className="z-20 w-full max-w-[400px] shrink-0 p-3 md:w-[380px]">
          <ChatPanel
            messages={messages}
            thinking={thinking}
            selectedAgent={selectedAgent}
            onSend={(text) => sendChat(text, selectedId)}
            onVoice={onVoice}
            onFile={onFile}
          />
        </aside>
      </div>
    </div>
  );
}
