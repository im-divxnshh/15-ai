"use client";

import { useEffect, useRef, useState } from "react";
import type { AgentInfo, ChatMessage } from "@/lib/types";

interface ChatPanelProps {
  messages: ChatMessage[];
  thinking: boolean;
  selectedAgent: AgentInfo | null;
  onSend: (text: string) => void;
  onVoice: (blob: Blob) => void;
  onFile: (file: File) => void;
}

/** Pick an Indian voice for TTS — Hinglish text reads best with en-IN/hi-IN. */
function speak(text: string) {
  if (typeof window === "undefined" || !window.speechSynthesis) return;
  const clean = text.replace(/[*_#`>]/g, "").replace(/\[(.*?)\]\(.*?\)/g, "$1");
  const utter = new SpeechSynthesisUtterance(clean.slice(0, 600));
  const isDevanagari = /[ऀ-ॿ]/.test(clean);
  utter.lang = isDevanagari ? "hi-IN" : "en-IN";
  const voices = window.speechSynthesis.getVoices();
  const pick =
    voices.find((v) => v.lang === utter.lang) ||
    voices.find((v) => v.lang.startsWith(isDevanagari ? "hi" : "en-IN")) ||
    voices.find((v) => v.lang.startsWith("en"));
  if (pick) utter.voice = pick;
  utter.rate = 1;
  utter.pitch = 1;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utter);
}

export default function ChatPanel({
  messages,
  thinking,
  selectedAgent,
  onSend,
  onVoice,
  onFile,
}: ChatPanelProps) {
  const [input, setInput] = useState("");
  const [tts, setTts] = useState(true);
  const [recording, setRecording] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, thinking]);

  // speak the latest jarvis reply
  useEffect(() => {
    if (!tts || messages.length === 0) return;
    const last = messages[messages.length - 1];
    if (last.role === "jarvis") speak(last.text);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages.length]);

  const send = () => {
    const text = input.trim();
    if (!text || thinking) return;
    onSend(text);
    setInput("");
  };

  const toggleRecording = async () => {
    if (recording) {
      recorderRef.current?.stop();
      setRecording(false);
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream);
      const chunks: BlobPart[] = [];
      rec.ondataavailable = (e) => chunks.push(e.data);
      rec.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        onVoice(new Blob(chunks, { type: "audio/webm" }));
      };
      rec.start();
      recorderRef.current = rec;
      setRecording(true);
    } catch {
      alert("Mic access nahi mila — browser permission check karo.");
    }
  };

  return (
    <div className="hud-panel flex h-full flex-col overflow-hidden">
      {/* header */}
      <div className="flex items-center gap-3 border-b border-slate-700/40 px-4 py-3">
        <span className="text-2xl">{selectedAgent?.emoji ?? "🧠"}</span>
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-bold text-cyan-300 neon-text">
            {selectedAgent?.name ?? "JARVIS"}
          </div>
          <div className="truncate text-[11px] text-slate-400">
            {selectedAgent?.role ?? "Master Orchestrator — sab kuch handle karta hoon"}
          </div>
        </div>
        <button
          onClick={() => setTts((v) => !v)}
          title="Voice replies on/off"
          className={`rounded-lg border px-2 py-1 text-xs transition ${
            tts
              ? "border-cyan-400/50 bg-cyan-400/10 text-cyan-300"
              : "border-slate-600/50 text-slate-500"
          }`}
        >
          {tts ? "🔊" : "🔇"}
        </button>
      </div>

      {/* messages */}
      <div ref={scrollRef} className="thin-scroll flex-1 space-y-3 overflow-y-auto px-4 py-4">
        {messages.length === 0 && (
          <div className="mt-8 text-center text-xs leading-relaxed text-slate-500">
            <div className="mb-2 text-3xl">🧠</div>
            <p className="font-semibold text-slate-400">Namaste, Boss! 🙏</p>
            <p className="mt-1">
              Main JARVIS hoon — aapka personal AI office.
              <br />
              Kuch bhi pucho, kaam bolo... ya office ke kisi worker pe click karke baat karo.
            </p>
            <p className="mt-3 text-slate-600">
              Try: &quot;mere liye ek reminder set karo&quot; · &quot;aaj ka news batao&quot; ·
              &quot;mujhe motivate karo&quot;
            </p>
          </div>
        )}
        {messages.map((m) => (
          <div key={m.id} className={`msg-in flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-3.5 py-2.5 text-[13px] leading-relaxed ${
                m.role === "user" ? "chat-bubble-user text-cyan-50" : "chat-bubble-jarvis text-slate-200"
              }`}
            >
              {m.text}
            </div>
          </div>
        ))}
        {thinking && (
          <div className="msg-in flex justify-start">
            <div className="chat-bubble-jarvis think-cursor rounded-2xl px-3.5 py-2.5 text-[13px] text-slate-300">
              {selectedAgent?.name ?? "JARVIS"} soch raha hai
            </div>
          </div>
        )}
      </div>

      {/* input */}
      <div className="border-t border-slate-700/40 p-3">
        <div className="flex items-end gap-2">
          <button
            onClick={() => fileRef.current?.click()}
            title="File upload karo — PDF/code kuch bhi"
            className="rounded-xl border border-slate-600/50 bg-slate-800/60 px-3 py-2.5 text-sm text-slate-300 transition hover:border-cyan-400/50 hover:text-cyan-300"
          >
            📎
          </button>
          <input
            ref={fileRef}
            type="file"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) onFile(f);
              e.target.value = "";
            }}
          />
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            rows={1}
            placeholder="Bolo boss... kuch bhi (Hindi/English dono chalega) 💬"
            className="thin-scroll max-h-28 min-h-[44px] flex-1 resize-none rounded-xl border border-slate-600/50 bg-slate-900/70 px-3.5 py-2.5 text-[13px] text-slate-100 placeholder:text-slate-500 focus:border-cyan-400/60 focus:outline-none"
          />
          <button
            onClick={toggleRecording}
            title="Bol ke batao (Hindi/English)"
            className={`rounded-xl border px-3 py-2.5 text-sm transition ${
              recording
                ? "mic-rec border-red-400/70 text-red-300"
                : "border-slate-600/50 bg-slate-800/60 text-slate-300 hover:border-cyan-400/50 hover:text-cyan-300"
            }`}
          >
            {recording ? "⏹️" : "🎤"}
          </button>
          <button
            onClick={send}
            disabled={thinking || !input.trim()}
            className="rounded-xl border border-cyan-400/50 bg-cyan-500/20 px-4 py-2.5 text-sm font-semibold text-cyan-200 transition hover:bg-cyan-500/30 disabled:opacity-40"
          >
            ➤
          </button>
        </div>
      </div>
    </div>
  );
}
