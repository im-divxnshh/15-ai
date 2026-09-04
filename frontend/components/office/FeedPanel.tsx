"use client";

import type { OfficeEvent } from "@/lib/types";

const EVENT_STYLE: Record<string, { icon: string; color: string; label: string }> = {
  TaskCreated: { icon: "📌", color: "text-amber-300", label: "Task" },
  TaskCompleted: { icon: "✅", color: "text-emerald-300", label: "Done" },
  TaskFailed: { icon: "❌", color: "text-red-300", label: "Failed" },
  AgentStarted: { icon: "⚡", color: "text-cyan-300", label: "Start" },
  AgentFinished: { icon: "🏁", color: "text-sky-300", label: "Finish" },
  AgentThinking: { icon: "💭", color: "text-violet-300", label: "Think" },
  MemorySaved: { icon: "🧠", color: "text-fuchsia-300", label: "Memory" },
  ChatMessage: { icon: "💬", color: "text-slate-300", label: "Chat" },
  SystemEvent: { icon: "🛰️", color: "text-slate-400", label: "System" },
};

export default function FeedPanel({ events }: { events: OfficeEvent[] }) {
  return (
    <div className="hud-panel flex h-full flex-col overflow-hidden">
      <div className="border-b border-slate-700/40 px-4 py-3">
        <div className="hud-title">🛰️ Mission Control</div>
        <div className="mt-0.5 text-[10px] text-slate-500">live office activity</div>
      </div>
      <div className="thin-scroll flex-1 space-y-1.5 overflow-y-auto p-3">
        {events.length === 0 && (
          <p className="px-1 py-4 text-center text-[11px] text-slate-500">
            Sab shaant hai... koi kaam bolo 😄
          </p>
        )}
        {events.map((e, i) => {
          const style = EVENT_STYLE[e.event] ?? EVENT_STYLE.SystemEvent;
          const agent = (e.data?.agent as string) ?? "";
          const detail =
            (e.data?.detail as string) ??
            (e.data?.title as string) ??
            (e.data?.type as string) ??
            "";
          return (
            <div
              key={`${e.ts}-${i}`}
              className="feed-row flex items-start gap-2 rounded-lg border border-slate-800/60 bg-slate-900/40 px-2.5 py-1.5"
            >
              <span className="text-xs leading-5">{style.icon}</span>
              <div className="min-w-0 flex-1">
                <span className={`text-[10px] font-bold uppercase tracking-wider ${style.color}`}>
                  {style.label}
                  {agent && <span className="ml-1 text-slate-500">@{agent}</span>}
                </span>
                {detail && (
                  <p className="truncate text-[11px] text-slate-400">{String(detail).slice(0, 60)}</p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
