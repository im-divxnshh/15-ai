"use client";

import type { AgentInfo } from "@/lib/types";

const TILE = 88;

function tileCenter(gx: number, gy: number): { left: number; top: number } {
  return { left: gx * TILE + TILE / 2, top: gy * TILE + TILE / 2 };
}

function StatusBubble({ agent }: { agent: AgentInfo }) {
  if (agent.state === "idle") return null;
  const text =
    agent.state === "thinking"
      ? "soch raha hoon..."
      : agent.current_action?.slice(0, 28) ?? "working...";
  return (
    <div className="bubble">
      {agent.state === "thinking" ? "💭" : "⚡"} {text}
    </div>
  );
}

/** A LEGO-minifig-style worker built from pure CSS blocks. */
function Minifig({ hat }: { hat: string }) {
  return (
    <div className="minifig">
      <div className="mf-hat">{hat}</div>
      <div className="mf-stud" />
      <div className="mf-head">
        <div className="mf-face" />
      </div>
      <div className="mf-torso">
        <div className="mf-arm mf-arm-l" />
        <div className="mf-arm mf-arm-r" />
      </div>
      <div className="mf-legs">
        <div className="mf-leg" />
        <div className="mf-leg" />
      </div>
    </div>
  );
}

interface WorkStationProps {
  agent: AgentInfo;
  selected: boolean;
  onClick: (agent: AgentInfo) => void;
}

export default function WorkStation({ agent, selected, onClick }: WorkStationProps) {
  const { left, top } = tileCenter(agent.desk[0], agent.desk[1]);
  const working = agent.state === "working" || agent.state === "thinking";

  return (
    <div
      className={`workstation${working ? " working" : ""}${selected ? " selected" : ""}`}
      style={{ left, top, ["--accent" as string]: agent.accent }}
      onClick={() => onClick(agent)}
      title={`${agent.name} — ${agent.role}`}
    >
      <StatusBubble agent={agent} />
      <Minifig hat={agent.emoji} />
      <div className="px-desk" />
      <div className="agent-plate">{agent.name}</div>
      {agent.tasks_done > 0 && <div className="task-badge">×{agent.tasks_done}</div>}
    </div>
  );
}

export function CommandPod({ agent, onClick }: { agent: AgentInfo; onClick: () => void }) {
  const { left, top } = tileCenter(agent.desk[0], agent.desk[1]);
  const working = agent.state === "working" || agent.state === "thinking";

  return (
    <div
      className={`workstation jarvis${working ? " working" : ""}`}
      style={{ left, top, ["--accent" as string]: "#fbbf24" }}
      onClick={onClick}
      title="JARVIS — Master Orchestrator"
    >
      <StatusBubble agent={agent} />
      <Minifig hat="🧠" />
      <div className="px-desk" />
      <div className="agent-plate">JARVIS CMD</div>
      {agent.tasks_done > 0 && <div className="task-badge">×{agent.tasks_done}</div>}
    </div>
  );
}

export function PodRings({ gx, gy }: { gx: number; gy: number }) {
  const { left, top } = tileCenter(gx, gy);
  return (
    <>
      <div className="pod-pixel" style={{ left, top, width: 200, height: 200 }} />
      <div className="pod-pixel r2" style={{ left, top, width: 160, height: 160 }} />
      <div className="pod-pixel r3" style={{ left, top, width: 120, height: 120 }} />
    </>
  );
}

export { WorkStation };

