export interface AgentInfo {
  id: string;
  name: string;
  role: string;
  layer: string;
  emoji: string;
  accent: string;
  desk: [number, number];
  tools: string[];
  state: "idle" | "working" | "thinking" | "finished";
  current_action: string | null;
  tasks_done: number;
}

export interface ChatMessage {
  id: string;
  role: "user" | "jarvis";
  agent?: string;
  text: string;
  ts: number;
}

export interface OfficeEvent {
  event: string;
  data: Record<string, unknown> & { agent?: string; detail?: string };
  ts: string;
}

export interface Analytics {
  user_tasks: { total: number; done: number };
  agent_tasks: { total: number; by_state: Record<string, number> };
  agents: { count: number; working: number };
  memory: { vector_memories: number; conversation_turns: number; facts: number };
  queue: { lanes: Record<string, number>; workers: number };
  audit_entries: number;
}

export interface HealthInfo {
  status: string;
  llm: string;
  firebase: string;
  neon: string;
  r2: string;
  search: string;
  stt: string;
}

export const LAYER_LABELS: Record<string, string> = {
  supreme: "Supreme Control",
  intelligence: "Intelligence Layer",
  execution: "Execution Layer",
  optimization: "Human Optimization",
  communication: "Communication",
  lifestyle: "Lifestyle",
};
