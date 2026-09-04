const BACKEND =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export { BACKEND };

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BACKEND}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`API ${path} failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  agents: () => req<{ agents: import("./types").AgentInfo[] }>("/api/agents"),
  health: () => req<import("./types").HealthInfo>("/api/system/health"),
  analytics: () => req<import("./types").Analytics>("/api/analytics"),
  chat: (text: string, agent?: string) =>
    req<{ reply: string; agent: string; intent: string }>(
      "/api/chat",
      { method: "POST", body: JSON.stringify({ text, agent: agent ?? null }) }
    ),
  tasks: () => req<{ tasks: Array<Record<string, string>> }>("/api/tasks"),
  uploadFile: async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BACKEND}/api/files/upload`, {
      method: "POST",
      body: form,
    });
    if (!res.ok) throw new Error("upload failed");
    return res.json();
  },
  voiceStt: async (blob: Blob) => {
    const form = new FormData();
    form.append("audio", blob, "speech.webm");
    const res = await fetch(`${BACKEND}/api/voice/stt`, {
      method: "POST",
      body: form,
    });
    if (!res.ok) throw new Error("stt failed");
    return res.json() as Promise<{ text?: string; error?: string; message?: string }>;
  },
};
