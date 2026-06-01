"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { sendMessage } from "@/src/services/chat";

declare global {
  interface Window {
    webkitSpeechRecognition: any;
    SpeechRecognition: any;
  }
}

type Message = {
  role: "user" | "assistant";
  content: string;
};

export default function Home() {
  const [input, setInput] = useState("");
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);
  const recognitionRef = useRef<any>(null);
  const voiceRef = useRef<SpeechSynthesisVoice | null>(null);

  // Pre-load best voice once
  useEffect(() => {
    const load = () => {
      const voices = window.speechSynthesis.getVoices();
      voiceRef.current =
        voices.find((v) => v.name.includes("Google US English")) ||
        voices.find((v) => v.lang === "en-US") ||
        voices[0] ||
        null;
    };
    load();
    window.speechSynthesis.onvoiceschanged = load;
    return () => {
      window.speechSynthesis.onvoiceschanged = null;
    };
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const stopSpeaking = () => {
    window.speechSynthesis?.cancel();
    setIsSpeaking(false);
  };

 const speak = useCallback(
   (text: string) => {
     if (!voiceEnabled || !window.speechSynthesis || !text) return;

     window.speechSynthesis.cancel();

     setIsSpeaking(true);

     // Split long responses into chunks
     const chunks = text.match(/[^.!?]+[.!?]+|[^.!?]+$/g) || [text];

     let index = 0;

     const speakChunk = () => {
       if (index >= chunks.length) {
         setIsSpeaking(false);
         return;
       }

       const utterance = new SpeechSynthesisUtterance(chunks[index].trim());

       utterance.lang = "en-US";
       utterance.rate = 1;
       utterance.pitch = 1;

       if (voiceRef.current) {
         utterance.voice = voiceRef.current;
       }

       utterance.onend = () => {
         index++;
         speakChunk();
       };

       utterance.onerror = () => {
         setIsSpeaking(false);
       };

       window.speechSynthesis.speak(utterance);
     };

     speakChunk();
   },
   [voiceEnabled],
 );

  const send = useCallback(
    async (text?: string) => {
      const finalMessage = (text || input).trim();
      if (!finalMessage || loading) return;
      setMessages((prev) => [...prev, { role: "user", content: finalMessage }]);
      setInput("");
      setLoading(true);
      try {
        const response = await sendMessage(finalMessage);
        const reply =
          response.message ||
          response.response ||
          response.result ||
          "No response";
        setMessages((prev) => [...prev, { role: "assistant", content: reply }]);
        speak(reply); // ← auto-speak every Jarvis reply
      } catch {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: "Backend Error" },
        ]);
      } finally {
        setLoading(false);
      }
    },
    [input, loading, speak],
  );

const toggleListening = useCallback(() => {
  if (isListening) {
    recognitionRef.current?.stop();
    return;
  }

  const SpeechRecognition =
    window.SpeechRecognition || window.webkitSpeechRecognition;

  if (!SpeechRecognition) {
    alert("Speech Recognition not supported");
    return;
  }

  stopSpeaking();

  const recognition = new SpeechRecognition();

  recognition.lang = navigator.language || "en-US";
  recognition.continuous = true; // keep listening
  recognition.interimResults = true;
  recognition.maxAlternatives = 1;

  let finalTranscript = "";

  recognition.onstart = () => {
    setIsListening(true);
  };

  recognition.onresult = (event: any) => {
    let interimTranscript = "";

    for (let i = event.resultIndex; i < event.results.length; i++) {
      const transcript = event.results[i][0].transcript;

      if (event.results[i].isFinal) {
        finalTranscript += transcript + " ";
      } else {
        interimTranscript += transcript;
      }
    }

    setInput((finalTranscript + interimTranscript).trim());
  };

  recognition.onerror = (event: any) => {
    console.error("Speech Error:", event.error);
    setIsListening(false);
  };

  recognition.onend = () => {
    setIsListening(false);

    const text = finalTranscript.trim();

    if (text.length > 0) {
      send(text);
    }
  };

  recognition.start();
  recognitionRef.current = recognition;
}, [isListening, send]);

  return (
    <main className="min-h-screen bg-[#05050a] flex flex-col items-center justify-center p-3 sm:p-6">
      {/* Title */}
      <motion.div
        initial={{ opacity: 0, y: -16 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-4 text-center select-none"
      >
        <h1 className="text-3xl sm:text-4xl font-bold tracking-[0.3em] text-transparent bg-clip-text bg-linear-to-r from-violet-400 to-emerald-400">
          JARVIS
        </h1>
        <p className="text-[11px] tracking-widest text-[#3a3a55] mt-1 uppercase">
          AI Assistant
        </p>
      </motion.div>

      {/* Chat window */}
      <motion.div
        initial={{ opacity: 0, scale: 0.97 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ delay: 0.08 }}
        className="w-full max-w-2xl bg-[#0a0a0f] border border-[#1e1e2e] rounded-2xl flex flex-col overflow-hidden"
        style={{ height: "clamp(400px, 65vh, 580px)" }}
      >
        {/* Top bar */}
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-[#1a1a28]">
          <div className="flex items-center gap-1.5">
            <motion.div
              className="w-2 h-2 rounded-full bg-emerald-500"
              animate={{ opacity: [1, 0.3, 1] }}
              transition={{ duration: 2, repeat: Infinity }}
            />
            <span className="text-[11px] text-[#3a3a55]">Online</span>
          </div>
          <div className="flex items-center gap-3">
            {/* Speaking indicator */}
            <AnimatePresence>
              {isSpeaking && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="flex items-center gap-1.5"
                >
                  <div className="flex gap-0.5 items-end h-3">
                    {[0.4, 0.7, 1, 0.7, 0.4].map((h, i) => (
                      <motion.div
                        key={i}
                        className="w-0.5 bg-violet-500 rounded-full"
                        animate={{ scaleY: [h, 1, h] }}
                        transition={{
                          duration: 0.6,
                          repeat: Infinity,
                          delay: i * 0.1,
                        }}
                        style={{ height: "12px", transformOrigin: "bottom" }}
                      />
                    ))}
                  </div>
                  <button
                    onClick={stopSpeaking}
                    className="text-[10px] text-[#50507080] hover:text-violet-400 transition-colors ml-1"
                  >
                    stop
                  </button>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Voice toggle */}
            <button
              onClick={() => {
                setVoiceEnabled((v) => !v);
                stopSpeaking();
              }}
              className={`text-[11px] px-2 py-0.5 rounded-lg border transition-colors duration-150 ${
                voiceEnabled
                  ? "border-violet-500/40 text-violet-400 bg-violet-500/10"
                  : "border-[#2a2a40] text-[#3a3a55]"
              }`}
            >
              {voiceEnabled ? "🔊 on" : "🔇 off"}
            </button>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-4 flex flex-col gap-3">
          {messages.length === 0 && (
            <div className="flex-1 flex items-center justify-center h-full">
              <p className="text-[#2a2a40] text-sm">
                Say something to Jarvis...
              </p>
            </div>
          )}
          <AnimatePresence initial={false}>
            {messages.map((msg, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ type: "spring", stiffness: 320, damping: 30 }}
                className={`flex gap-2 items-end ${msg.role === "user" ? "flex-row-reverse" : ""}`}
              >
                <div
                  className={`w-6 h-6 rounded-full shrink-0 flex items-center justify-center text-[10px] font-bold ${
                    msg.role === "user"
                      ? "bg-[#1e1e35] text-[#7070a0]"
                      : "bg-linear-to-br from-violet-600 to-emerald-500 text-white"
                  }`}
                >
                  {msg.role === "user" ? "U" : "J"}
                </div>
                <div
                  className={`max-w-[78%] px-3.5 py-2.5 text-sm leading-relaxed rounded-2xl ${
                    msg.role === "user"
                      ? "bg-[#14142a] text-[#c0c0e0] border border-[#2a2a45] rounded-br-sm"
                      : "bg-[#0f0f1e] text-[#d0d0e8] border border-[#1a1a30] rounded-bl-sm"
                  }`}
                >
                  {msg.content}
                </div>
              </motion.div>
            ))}
          </AnimatePresence>

          {/* Typing */}
          <AnimatePresence>
            {loading && (
              <motion.div
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="flex gap-2 items-end"
              >
                <div className="w-6 h-6 rounded-full bg-linear-to-br from-violet-600 to-emerald-500 shrink-0 flex items-center justify-center text-[10px] font-bold text-white">
                  J
                </div>
                <div className="bg-[#0f0f1e] border border-[#1a1a30] rounded-2xl rounded-bl-sm px-4 py-3 flex gap-1">
                  {[0, 1, 2].map((i) => (
                    <motion.div
                      key={i}
                      className="w-1.5 h-1.5 rounded-full bg-violet-500"
                      animate={{ y: [0, -4, 0] }}
                      transition={{
                        duration: 0.6,
                        repeat: Infinity,
                        delay: i * 0.13,
                      }}
                    />
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
          <div ref={bottomRef} />
        </div>
      </motion.div>

      {/* Input row */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
        className="w-full max-w-2xl mt-3 flex gap-2 items-center"
      >
        {/* Mic */}
        <motion.button
          whileTap={{ scale: 0.88 }}
          onClick={toggleListening}
          className={`relative w-11 h-11 rounded-xl shrink-0 flex items-center justify-center text-base border transition-colors duration-150 ${
            isListening
              ? "bg-violet-600/20 border-violet-500/60 text-violet-400"
              : "bg-[#0f0f1e] border-[#2a2a40] text-[#606080]"
          }`}
          aria-label={isListening ? "Stop listening" : "Start listening"}
        >
          {isListening && (
            <motion.div
              className="absolute inset-0 rounded-xl border border-violet-500/70"
              animate={{ scale: [1, 1.18, 1], opacity: [0.8, 0, 0.8] }}
              transition={{ duration: 1.2, repeat: Infinity }}
            />
          )}
          {isListening ? "⏹" : "🎙️"}
        </motion.button>

        {/* Input */}
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send()}
          placeholder={isListening ? "Listening..." : "Ask Jarvis..."}
          disabled={loading}
          className="flex-1 bg-[#0f0f1e] border border-[#2a2a40] focus:border-violet-500/60 rounded-xl px-4 py-2.5 text-sm text-[#e0e0f0] placeholder-[#2a2a45] outline-none transition-colors duration-150 disabled:opacity-50"
        />

        {/* Send */}
        <motion.button
          whileTap={{ scale: 0.9 }}
          onClick={() => send()}
          disabled={!input.trim() || loading}
          className="w-11 h-11 rounded-xl bg-violet-600 hover:bg-violet-500 disabled:opacity-30 disabled:cursor-not-allowed shrink-0 flex items-center justify-center text-white transition-colors duration-150"
          aria-label="Send"
        >
          <svg
            width="15"
            height="15"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <line x1="22" y1="2" x2="11" y2="13" />
            <polygon points="22 2 15 22 11 13 2 9 22 2" />
          </svg>
        </motion.button>
      </motion.div>
    </main>
  );
}
