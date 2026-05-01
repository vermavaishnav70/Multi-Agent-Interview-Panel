"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import type { Message, Scorecard, SessionResponse } from "@/lib/types";
import styles from "./page.module.css";

const recommendationMap: Record<string, string> = {
  strong_yes: "Strong yes",
  yes: "Yes",
  borderline: "Borderline",
  no: "Needs more practice",
};

function formatDate(value?: string) {
  if (!value) return "Saved just now";
  return new Date(value).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export default function InterviewCompletePage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.id as string;

  const [session, setSession] = useState<SessionResponse | null>(null);
  const [scorecard, setScorecard] = useState<Scorecard | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        const [sessionResponse, scorecardResponse, messagesResponse] =
          await Promise.all([
            fetch(`/api/sessions/${sessionId}`),
            fetch(`/api/sessions/${sessionId}/scorecard`),
            fetch(`/api/sessions/${sessionId}/messages`),
          ]);

        if (!sessionResponse.ok || !scorecardResponse.ok) {
          throw new Error("Unable to load the session summary.");
        }

        const sessionData = await sessionResponse.json();
        
        if (sessionData.status !== "completed") {
          router.push(`/session/${sessionId}`);
          return;
        }
        
        setSession(sessionData);
        setScorecard(await scorecardResponse.json());

        if (messagesResponse.ok) {
          setMessages(await messagesResponse.json());
        }
      } catch (loadError) {
        setError(
          loadError instanceof Error
            ? loadError.message
            : "Unable to load the session summary."
        );
      } finally {
        setLoading(false);
      }
    };

    load();
  }, [sessionId]);

  if (loading) {
    return (
      <div className={styles.loadingPage}>
        <div className={styles.spinner} />
        <p>Finalizing your interview summary...</p>
      </div>
    );
  }

  if (error || !session || !scorecard) {
    return (
      <div className={styles.loadingPage}>
        <p>{error || "Summary unavailable."}</p>
        <button className="btn btn-primary" onClick={() => router.push("/")}>
          Back to home
        </button>
      </div>
    );
  }

  const userResponses = messages.filter((message) => message.role === "user").length;
  const agentTurns = messages.filter((message) => message.role === "agent").length;
  const snapshot = [
    { label: "Overall score", value: `${scorecard.final_score}%` },
    {
      label: "Communication",
      value: `${scorecard.per_dimension_scores.communication ?? scorecard.final_score / 10}/10`,
    },
    {
      label: "Technical depth",
      value: `${scorecard.per_dimension_scores.technical_depth ?? scorecard.final_score / 10}/10`,
    },
    {
      label: "Confidence",
      value: `${scorecard.per_dimension_scores.confidence ?? scorecard.final_score / 10}/10`,
    },
  ];

  return (
    <div className={styles.page}>
      <main className={`app-shell ${styles.main}`}>
        <section className={styles.hero}>
          <div className={styles.heroIcon}>✓</div>
          <p className="eyebrow">Session saved</p>
          <h1>Interview Complete</h1>
          <p className={styles.heroCopy}>
            Your live session has been saved and the analysis is ready to
            review. Start with the scorecard or return to the dashboard to
            launch another round.
          </p>
          <div className={styles.heroActions}>
            <button
              className="btn btn-primary"
              onClick={() => router.push(`/session/${sessionId}/scorecard`)}
            >
              View Scorecard
            </button>
            <button className="btn btn-secondary" onClick={() => router.push("/new")}>
              Start New Interview
            </button>
          </div>
        </section>

        <section className={styles.grid}>
          <article className={`${styles.recapCard} surface-card`}>
            <div className={styles.recapHeader}>
              <div>
                <p className={styles.cardLabel}>Session recap</p>
                <h2>{session.job_role}</h2>
              </div>
              <span className="pill">Completed</span>
            </div>

            <div className={styles.recapMeta}>
              <div>
                <span>Mode</span>
                <strong>{session.voice_mode ? "Live Voice" : "Chat"}</strong>
              </div>
              <div>
                <span>Difficulty</span>
                <strong>{session.difficulty}</strong>
              </div>
              <div>
                <span>Duration</span>
                <strong>{messages.length ? `${userResponses + agentTurns} turns` : "Captured"}</strong>
              </div>
              <div>
                <span>Saved</span>
                <strong>{formatDate(session.created_at)}</strong>
              </div>
            </div>
          </article>

          <article className={`${styles.summaryCard} soft-card`}>
            <p className={styles.cardLabel}>Session summary</p>
            <ul>
              <li>{userResponses} questions answered</li>
              <li>{Math.max(agentTurns - 1, 0)} follow-up prompts captured</li>
              <li>Transcript available for detailed review</li>
            </ul>
          </article>
        </section>

        <section className={styles.snapshotSection}>
          {snapshot.map((item) => (
            <article key={item.label} className="surface-card">
              <p className={styles.cardLabel}>{item.label}</p>
              <strong>{item.value}</strong>
            </article>
          ))}
        </section>

        <section className={styles.detailGrid}>
          <article className="surface-card">
            <p className={styles.cardLabel}>Strengths</p>
            <ul className={styles.detailList}>
              {scorecard.strengths.slice(0, 3).map((strength) => (
                <li key={strength}>{strength}</li>
              ))}
            </ul>
          </article>

          <article className="surface-card">
            <p className={styles.cardLabel}>Improvement areas</p>
            <ul className={styles.detailList}>
              {scorecard.improvement_areas.slice(0, 3).map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </article>
        </section>

        <section className={`${styles.nextSteps} soft-card`}>
          <div>
            <p className={styles.cardLabel}>Next steps</p>
            <h2>{recommendationMap[scorecard.hire_recommendation] || "Keep practicing"}</h2>
            <p>{scorecard.summary}</p>
          </div>
          <div className={styles.nextActions}>
            <button
              className="btn btn-primary"
              onClick={() => router.push(`/session/${sessionId}/scorecard`)}
            >
              Review full scorecard
            </button>
            <button className="btn btn-ghost" onClick={() => router.push(`/session/${sessionId}`)}>
              Review transcript
            </button>
          </div>
        </section>
      </main>
    </div>
  );
}
