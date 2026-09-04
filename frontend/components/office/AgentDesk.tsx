"use client";

import type { AgentInfo } from "@/lib/types";

const TILE = 78;
const OFFSET = 1; // grid → world: (gx + OFFSET) * TILE

export function gridToWorld(gx: number, gy: number): { left: number; top: number } {
  return { left: (gx + OFFSET) * TILE, top: (gy + OFFSET) * TILE };
}

interface AgentDeskProps {
  agent: AgentInfo;
  selected: boolean;
  onClick: (agent: AgentInfo) => void;
}

export default function AgentDesk({ agent, selected, onClick }: AgentDeskProps) {
  const { left, top } = gridToWorld(agent.desk[0], agent.desk[1]);
  const working = agent.state === "working" || agent.state === "thinking";

  return (
    <div
      className="desk"
      style={{ left, top, ["--accent" as string]: agent.accent }}
      onClick={() => onClick(agent)}
      title={`${agent.name} — ${agent.role}`}
    >
      {/* glow ring when active */}
      {working && <div className="pulse-ring" style={{ width: 110, height: 110 }} />}

      {/* colored aura pad on the floor */}
      <div className="aura" style={{ width: 130, height: 130, opacity: selected ? 0.75 : 0.4 }} />

      {/* the desk (lies flat in the iso plane) */}
      <div
        className="desk-top"
        style={{
          width: selected ? 104 : 92,
          height: selected ? 76 : 68,
        }}
      />

      {/* desk side (fake thickness) */}
      <div
        className="desk-side"
        style={{ width: 92, height: 10, left: 0, top: 34, transform: "translate(-50%, 0)" }}
      />

      {/* the worker (upright billboard) */}
      <div className="sprite">
        {(working || selected) && (
          <div className="bubble">
            {agent.state === "thinking" ? "💭 soch raha hoon..." : `⚡ ${agent.current_action?.slice(0, 26) ?? "working..."}`}
          </div>
        )}
        <div className="agent-emoji">
          {agent.emoji}
          {working && <span className="typing-dots" style={{ position: "absolute", right: -14, bottom: 4 }} />}
        </div>
        <div className="agent-plate">{agent.name}</div>
      </div>
    </div>
  );
}

export function CommandPod({ agent, onClick }: { agent: AgentInfo; onClick: () => void }) {  const { left, top } = gridToWorld(agent.desk[0], agent.desk[1]);
  return (
    <div
      className="desk"
      style={{ left, top, ["--accent" as string]: agent.accent, cursor: "pointer" }}
      onClick={onClick}
      title="JARVIS — Master Orchestrator"
    >
      <div className="pod-rings" style={{ width: 190, height: 190, transform: "translate(-50%, -50%)" }} />
      <div className="pod-rings reverse" style={{ width: 150, height: 150, transform: "translate(-50%, -50%)" }} />
      <div className="pod-platform" style={{ width: 130, height: 130 }} />
      <div className="sprite">
        {(agent.state === "working" || agent.state === "thinking") && (
          <div className="bubble">
            {agent.state === "thinking" ? "💭 thinking..." : `⚡ ${agent.current_action?.slice(0, 26) ?? "orchestrating..."}`}
          </div>
        )}
        <div className="jarvis-core">🧠</div>
        <div className="agent-plate" style={{ fontSize: 11 }}>JARVIS · COMMAND</div>
      </div>
    </div>
  );
}
