"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAudioPlayer } from "@/hooks/useAudioPlayer";
import { useSSE } from "@/hooks/useSSE";
import { useVoiceRecorder } from "@/hooks/useVoiceRecorder";
import { AGENT_CONFIG, type AgentRole, type SSEEvent } from "@/lib/types";
import styles from "./page.module.css";

interface ChatMessage {
  id: string;
  role: "user" | "agent";
  agent_name?: string;
  content: string;
  timestamp?: string;
  isStreaming?: boolean;
}

function formatElapsed(createdAt: string | null, now: number) {
  if (!createdAt) return "0:00 elapsed";

  const diffSeconds = Math.max(
    0,
    Math.floor((now - new Date(createdAt).getTime()) / 1000)
  );
  const minutes = Math.floor(diffSeconds / 60);
  const seconds = diffSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")} elapsed`;
}

function formatTimestamp(timestamp?: string) {
  if (!timestamp) return "Now";
  return new Date(timestamp).toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
  });
}

export default function InterviewPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.id as string;

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState("");
  const [currentAgent, setCurrentAgent] = useState<string | null>(null);
  const [turnCount, setTurnCount] = useState(0);
  const [maxTurns, setMaxTurns] = useState(9);
  const [isThinking, setIsThinking] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [sessionComplete, setSessionComplete] = useState(false);
  const [voiceMode, setVoiceMode] = useState(false);
  const [jobRole, setJobRole] = useState("");
  const [error, setError] = useState("");
  const [initialLoading, setInitialLoading] = useState(true);
  const [providerStatus, setProviderStatus] = useState("");
  const [createdAt, setCreatedAt] = useState<string | null>(null);
  const [clock, setClock] = useState(Date.now());

  const streamingMsgRef = useRef("");
  const chatEndRef = useRef<HTMLDivElement>(null);
  const openingTurnStartedRef = useRef(false);

  const { isRecording, startRecording, stopRecording } = useVoiceRecorder();
  const { playAudioUrl, stop: stopAudio } = useAudioPlayer();

  useEffect(() => {
    const timer = window.setInterval(() => setClock(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  const handleSSEEvent = useCallback(
    (event: SSEEvent) => {
      switch (event.type) {
        case "thinking":
          setIsThinking(true);
          setProviderStatus("AI is analyzing your latest response.");
          break;

        case "provider_switch":
          setProviderStatus(
            event.to_provider
              ? `Switched model provider to ${event.to_provider}`
              : "Switched model provider"
          );
          break;

        case "agent_info":
          setIsThinking(false);
          setCurrentAgent(event.agent || null);
          if (event.turn_count !== undefined) setTurnCount(event.turn_count);
          if (event.max_turns !== undefined) setMaxTurns(event.max_turns);
          streamingMsgRef.current = "";
          setMessages((previous) => [
            ...previous,
            {
              id: `agent-${Date.now()}`,
              role: "agent",
              agent_name: event.agent,
              content: "",
              timestamp: new Date().toISOString(),
              isStreaming: true,
            },
          ]);
          break;

        case "token":
          streamingMsgRef.current += event.content || "";
          setMessages((previous) => {
            const next = [...previous];
            const last = next[next.length - 1];

            if (last?.isStreaming) {
              next[next.length - 1] = {
                ...last,
                content: streamingMsgRef.current,
              };
            }

            return next;
          });
          break;

        case "tts_ready":
          if (event.audio_url) {
            playAudioUrl(event.audio_url);
          }
          break;

        case "agent_done":
          setProviderStatus("");
          setMessages((previous) => {
            const next = [...previous];
            const last = next[next.length - 1];

            if (last?.isStreaming) {
              next[next.length - 1] = { ...last, isStreaming: false };
            }

            return next;
          });
          setIsSubmitting(false);
          setIsThinking(false);
          break;

        case "session_complete":
          setSessionComplete(true);
          setCurrentAgent("synthesizer");
          setProviderStatus("Interview completed. Your summary is ready.");
          setMessages((previous) => {
            const next = [...previous];
            const last = next[next.length - 1];

            if (last?.isStreaming) {
              next[next.length - 1] = { ...last, isStreaming: false };
            }

            return next;
          });
          setIsSubmitting(false);
          setIsThinking(false);
          break;

        case "error":
          setError(event.message || "Stream error");
          setIsSubmitting(false);
          setIsThinking(false);
          setProviderStatus("");
          break;
      }
    },
    [playAudioUrl]
  );

  const { startStream } = useSSE({
    onEvent: handleSSEEvent,
    onError: (message) => {
      setError(message);
      setIsSubmitting(false);
    },
  });

  useEffect(() => {
    const fetchSession = async () => {
      try {
        const sessionResponse = await fetch(`/api/sessions/${sessionId}`);
        if (!sessionResponse.ok) throw new Error("Session not found");
        const sessionData = await sessionResponse.json();

        setMaxTurns(sessionData.max_turns);
        setVoiceMode(sessionData.voice_mode);
        setJobRole(sessionData.job_role);
        setCreatedAt(sessionData.created_at);
        setSessionComplete(sessionData.status === "completed");

        const messageResponse = await fetch(`/api/sessions/${sessionId}/messages`);
        if (messageResponse.ok) {
          const sessionMessages = await messageResponse.json();
          setMessages(
            sessionMessages.map((message: ChatMessage) => ({
              ...message,
              isStreaming: false,
            }))
          );
          setTurnCount(
            sessionMessages.filter((message: ChatMessage) => message.role === "user")
              .length
          );
        }
      } catch {
        setError("Failed to load session.");
      } finally {
        setInitialLoading(false);
      }
    };

    fetchSession();
  }, [sessionId]);

  const startTurn = useCallback(
    async (text: string, transcribedText?: string) => {
      setIsSubmitting(true);
      setError("");
      await startStream(`/api/sessions/${sessionId}/turn`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          content: text,
          transcribed_text: transcribedText,
          idempotency_key:
            typeof crypto !== "undefined" && crypto.randomUUID
              ? crypto.randomUUID()
              : `turn-${Date.now()}`,
        }),
      });
    },
    [sessionId, startStream]
  );

  useEffect(() => {
    if (
      !openingTurnStartedRef.current &&
      !initialLoading &&
      messages.length === 0 &&
      !sessionComplete
    ) {
      openingTurnStartedRef.current = true;
      startTurn("");
    }
  }, [initialLoading, messages.length, sessionComplete, startTurn]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isThinking]);

  const submitAnswer = async (text: string) => {
    if (!text.trim() || isSubmitting) return;

    setInputText("");
    setMessages((previous) => [
      ...previous,
      {
        id: `user-${Date.now()}`,
        role: "user",
        content: text.trim(),
        timestamp: new Date().toISOString(),
      },
    ]);

    try {
      await startTurn(text.trim());
    } catch (submitError) {
      setError(
        submitError instanceof Error ? submitError.message : "Failed to submit response."
      );
      setIsSubmitting(false);
    }
  };

  const handleVoiceRecord = async () => {
    if (isRecording) {
      const blob = await stopRecording();
      if (!blob) return;

      setIsTranscribing(true);

      try {
        const formData = new FormData();
        formData.append("audio", blob, "recording.wav");
        const response = await fetch(`/api/sessions/${sessionId}/transcribe`, {
          method: "POST",
          body: formData,
        });
        if (!response.ok) throw new Error("Transcription failed");
        const { transcript } = await response.json();
        await submitAnswer(transcript);
      } catch (recordError) {
        setError(
          recordError instanceof Error
            ? recordError.message
            : "Voice transcription failed."
        );
      } finally {
        setIsTranscribing(false);
      }
    } else {
      stopAudio();
      await startRecording();
    }
  };

  const latestAgentMessage = [...messages]
    .reverse()
    .find((message) => message.role === "agent" && message.content.trim());
  const latestUserMessage = [...messages]
    .reverse()
    .find((message) => message.role === "user" && message.content.trim());
  const currentQuestion = Math.min(maxTurns || 1, Math.max(turnCount + 1, 1));
  const elapsed = formatElapsed(createdAt, clock);
  const progress = maxTurns > 0 ? Math.min((turnCount / maxTurns) * 100, 100) : 0;
  const transcriptMessages = messages.slice(-10);
  const liveMetrics = [
    { label: "Clarity", value: `${Math.min(98, 68 + turnCount * 3)}%` },
    { label: "Confidence", value: voiceMode ? "Voice active" : "Chat mode" },
    { label: "Technical depth", value: currentAgent ? "Tracking" : "Starting" },
    { label: "Communication", value: `${messages.filter((msg) => msg.role === "user").length} responses` },
  ];

  if (initialLoading) {
    return (
      <div className={styles.loadingPage}>
        <div className={styles.spinner} />
        <p>Preparing your interview workspace...</p>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <header className={styles.topbar}>
        <div className="app-shell">
          <div className={styles.topbarInner}>
            <button className={styles.brandButton} onClick={() => router.push("/")}>
              Cognitive Gallery
            </button>

            <div className={styles.topbarMeta}>
              <span className="pill">
                <span className={styles.liveDot} />
                {sessionComplete ? "Completed" : "Live"}
              </span>
              <span className="pill">{voiceMode ? "Voice mode" : "Chat mode"}</span>
            </div>

            <button
              className="btn btn-ghost"
              onClick={() =>
                sessionComplete
                  ? router.push(`/session/${sessionId}/complete`)
                  : router.push("/new")
              }
            >
              {sessionComplete ? "View summary" : "End session"}
            </button>
          </div>
        </div>
      </header>

      <main className={`app-shell ${styles.main}`}>
        <section className={styles.primaryColumn}>
          <div className={styles.sessionHeader}>
            <div>
              <p className={styles.sessionEyebrow}>{jobRole || "Interview session"}</p>
              <h1>Alex Rivera</h1>
            </div>

            <div className={styles.headerPills}>
              <span className="pill">{elapsed}</span>
              <span className="pill">Q{currentQuestion} of {maxTurns}</span>
            </div>
          </div>

          <section className={`${styles.conversationPanel} surface-card`}>
            <div className={styles.voiceOrb}>
              <div className={styles.voiceOrbInner}>
                {currentAgent ? AGENT_CONFIG[currentAgent as AgentRole]?.name?.slice(0, 2) || "AI" : "AI"}
              </div>
            </div>

            <p className={styles.agentRole}>
              {currentAgent
                ? AGENT_CONFIG[currentAgent as AgentRole]?.name || currentAgent
                : "Technical Interviewer"}
            </p>

            <p className={styles.promptText}>
              {latestAgentMessage?.content ||
                "Your interviewer will appear here once the session starts."}
            </p>

            <div className={styles.panelActions}>
              <button className="btn btn-ghost" onClick={() => stopAudio()}>
                Mute AI
              </button>
              <button
                className="btn btn-ghost"
                onClick={() => setError("Prompt replay will be wired to cached TTS audio next.")}
              >
                Replay prompt
              </button>
              <button className="btn btn-ghost" onClick={() => setError("Pause support is not wired yet.")}>
                Pause
              </button>
            </div>
          </section>

          <section className={`${styles.responsePanel} surface-card`}>
            <div className={styles.responseHeader}>
              <div>
                <p className={styles.cardLabel}>Candidate response</p>
                <h2>Record, retry, or switch to keyboard</h2>
              </div>
              <div className={styles.connection}>
                <span className={styles.connectionDot} />
                Audio connected
              </div>
            </div>

            <div className={styles.recorderRow}>
              {voiceMode ? (
                <button
                  className={`${styles.recordButton} ${
                    isRecording ? styles.recording : ""
                  }`}
                  disabled={isSubmitting || isTranscribing}
                  onClick={handleVoiceRecord}
                >
                  {isTranscribing ? "…" : isRecording ? "Stop" : "Record"}
                </button>
              ) : null}

              <div className={styles.responseActions}>
                <button
                  className="btn btn-secondary"
                  disabled={!isRecording}
                  onClick={handleVoiceRecord}
                >
                  Stop
                </button>
                <button
                  className="btn btn-ghost"
                  onClick={() => {
                    setInputText("");
                    setError("");
                  }}
                >
                  Retry
                </button>
                <button
                  className="btn btn-ghost"
                  onClick={() => setVoiceMode((current) => !current)}
                >
                  {voiceMode ? "Switch to keyboard" : "Switch to voice"}
                </button>
              </div>
            </div>

            <div className={styles.textComposer}>
              <textarea
                className="field-textarea"
                placeholder={
                  isSubmitting
                    ? "Waiting for the next question..."
                    : "Type your answer or use voice input above."
                }
                value={inputText}
                disabled={isSubmitting}
                onChange={(event) => setInputText(event.target.value)}
              />

              <div className={styles.composeActions}>
                <button
                  className="btn btn-primary"
                  disabled={!inputText.trim() || isSubmitting}
                  onClick={() => submitAnswer(inputText)}
                >
                  Send response
                </button>
                <button
                  className="btn btn-ghost"
                  onClick={() => setInputText(latestUserMessage?.content || "")}
                >
                  Reuse last answer
                </button>
              </div>
            </div>

            <div className={styles.transcriptPreview}>
              <p className={styles.cardLabel}>Live transcript preview</p>
              <p>
                {isRecording
                  ? "Listening for your response..."
                  : inputText || latestUserMessage?.content || "Your latest response will appear here."}
              </p>
            </div>
          </section>

          <section className={`${styles.utilityRow} soft-card`}>
            <div>
              <p className={styles.cardLabel}>Session utility</p>
              <strong>{providerStatus || (sessionComplete ? "Interview completed." : "Connection stable.")}</strong>
            </div>

            <div className={styles.utilityActions}>
              <button className="btn btn-ghost" onClick={() => setError("Progress is already persisted automatically.")}>
                Save progress
              </button>
              {sessionComplete && (
                <button
                  className="btn btn-primary"
                  onClick={() => router.push(`/session/${sessionId}/complete`)}
                >
                  Open summary
                </button>
              )}
            </div>
          </section>
        </section>

        <aside className={styles.sidebar}>
          <section className={`${styles.sidebarCard} surface-card`}>
            <div className={styles.sidebarHeader}>
              <div>
                <p className={styles.cardLabel}>Live transcript</p>
                <h2>Recent turns</h2>
              </div>
              <span className="pill">{transcriptMessages.length} items</span>
            </div>

            <div className={styles.transcriptList}>
              {transcriptMessages.map((message) => (
                <article
                  key={message.id}
                  className={
                    message.role === "agent"
                      ? styles.agentMessage
                      : styles.userMessage
                  }
                >
                  <div className={styles.messageMeta}>
                    <strong>
                      {message.role === "agent"
                        ? AGENT_CONFIG[message.agent_name as AgentRole]?.name ||
                          message.agent_name ||
                          "AI interviewer"
                        : "Candidate"}
                    </strong>
                    <span>{formatTimestamp(message.timestamp)}</span>
                  </div>
                  <p>
                    {message.content}
                    {message.isStreaming ? <span className={styles.cursor}>▊</span> : null}
                  </p>
                </article>
              ))}

              {isThinking ? (
                <div className={styles.thinkingCard}>AI is preparing the next follow-up.</div>
              ) : null}
              <div ref={chatEndRef} />
            </div>
          </section>

          <section className={`${styles.sidebarCard} soft-card`}>
            <div className={styles.sidebarHeader}>
              <div>
                <p className={styles.cardLabel}>Evaluation snapshot</p>
                <h2>Live indicators</h2>
              </div>
            </div>

            {!sessionComplete ? (
              <p style={{ marginTop: '1rem', color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
                Scores will be available after the interview is completed.
              </p>
            ) : (
              <div className={styles.metricsList}>
                {liveMetrics.map((metric) => (
                  <div key={metric.label} className={styles.metricRow}>
                    <span>{metric.label}</span>
                    <strong>{metric.value}</strong>
                  </div>
                ))}
              </div>
            )}

            <div className={styles.progressBlock}>
              <div className={styles.progressMeta}>
                <span>Interview progress</span>
                <strong>{Math.round(progress)}%</strong>
              </div>
              <div className={styles.progressTrack}>
                <div className={styles.progressFill} style={{ width: `${progress}%` }} />
              </div>
            </div>
          </section>
        </aside>
      </main>

      {error ? (
        <div className={styles.errorBar}>
          <span>{error}</span>
          <button onClick={() => setError("")}>Dismiss</button>
        </div>
      ) : null}
    </div>
  );
}
