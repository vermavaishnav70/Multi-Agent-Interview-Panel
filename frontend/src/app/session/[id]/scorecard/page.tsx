"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import type { Message, Scorecard, SessionResponse } from "@/lib/types";
import styles from "./page.module.css";

type QuestionReview = {
  question: string;
  answer: string;
};

const recommendationLabels: Record<string, string> = {
  strong_yes: "Strong yes",
  yes: "Yes",
  borderline: "Borderline",
  no: "Needs more practice",
};

function toTitleCase(value: string) {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function buildQuestionReview(messages: Message[]) {
  const pairs: QuestionReview[] = [];
  let pendingQuestion: string | null = null;

  for (const message of messages) {
    if (message.role === "agent" && message.content.trim()) {
      pendingQuestion = message.content;
      continue;
    }

    if (message.role === "user" && pendingQuestion) {
      pairs.push({
        question: pendingQuestion,
        answer: message.content,
      });
      pendingQuestion = null;
    }
  }

  return pairs.slice(0, 5);
}

export default function ScorecardPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.id as string;

  const [scorecard, setScorecard] = useState<Scorecard | null>(null);
  const [session, setSession] = useState<SessionResponse | null>(null);
  const [reviews, setReviews] = useState<QuestionReview[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        const [scorecardResponse, sessionResponse, messageResponse] =
          await Promise.all([
            fetch(`/api/sessions/${sessionId}/scorecard`),
            fetch(`/api/sessions/${sessionId}`),
            fetch(`/api/sessions/${sessionId}/messages`),
          ]);

        if (!scorecardResponse.ok || !sessionResponse.ok) {
          throw new Error("Failed to load the scorecard.");
        }

        setScorecard(await scorecardResponse.json());
        const sessionData = await sessionResponse.json();
        
        if (sessionData.status !== "completed") {
          router.push(`/session/${sessionId}`);
          return;
        }
        
        setSession(sessionData);

        if (messageResponse.ok) {
          const transcript = await messageResponse.json();
          setReviews(buildQuestionReview(transcript));
        }
      } catch (loadError) {
        setError(
          loadError instanceof Error ? loadError.message : "Failed to load the scorecard."
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
        <p>Preparing your scorecard...</p>
      </div>
    );
  }

  if (error || !scorecard || !session) {
    return (
      <div className={styles.loadingPage}>
        <p>{error || "Scorecard unavailable."}</p>
        <button className="btn btn-primary" onClick={() => router.push("/")}>
          Back to home
        </button>
      </div>
    );
  }

  const scoreEntries = Object.entries(scorecard.per_dimension_scores);

  return (
    <div className={styles.page}>
      <main className={`app-shell ${styles.main}`}>
        <header className={styles.header}>
          <div>
            <div className={styles.headerMeta}>
              <span className="pill">{session.voice_mode ? "Live Voice" : "Chat"}</span>
              <span className="pill">{session.job_role}</span>
            </div>
            <h1>Candidate Scorecard</h1>
            <p>{scorecard.summary}</p>
          </div>

          <div className={styles.headerActions}>
            <button className="btn btn-secondary" onClick={() => router.push(`/session/${sessionId}/complete`)}>
              Back to Summary
            </button>
            <button className="btn btn-primary" onClick={() => router.push("/new")}>
              Practice Again
            </button>
          </div>
        </header>

        <section className={styles.layout}>
          <div className={styles.mainColumn}>
            <section className={`${styles.overviewCard} surface-card`}>
              <div className={styles.overviewScore}>
                <span>Overall score</span>
                <strong>{scorecard.final_score}%</strong>
                <p>{recommendationLabels[scorecard.hire_recommendation] || "Keep practicing"}</p>
              </div>

              <div className={styles.overviewDetails}>
                <div>
                  <span>Difficulty</span>
                  <strong>{session.difficulty}</strong>
                </div>
                <div>
                  <span>Mode</span>
                  <strong>{session.voice_mode ? "Live Voice" : "Chat"}</strong>
                </div>
                <div>
                  <span>Transcript</span>
                  <strong>Available</strong>
                </div>
              </div>
            </section>

            <section className={`${styles.sectionCard} surface-card`}>
              <div className={styles.sectionHeader}>
                <p className={styles.cardLabel}>Category breakdown</p>
                <h2>Detailed scoring</h2>
              </div>

              <div className={styles.scoreRows}>
                {scoreEntries.map(([key, value]) => (
                  <div key={key} className={styles.scoreRow}>
                    <div>
                      <strong>{toTitleCase(key)}</strong>
                      <p>
                        {value >= 8
                          ? "Strong signal across the session."
                          : value >= 6
                            ? "Solid, with room to tighten the response."
                            : "Needs more focused repetition."}
                      </p>
                    </div>
                    <div className={styles.scoreBarWrap}>
                      <span>{value}/10</span>
                      <div className={styles.scoreTrack}>
                        <div className={styles.scoreFill} style={{ width: `${value * 10}%` }} />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </section>

            <section className={styles.twoColumn}>
              <article className={`${styles.sectionCard} surface-card`}>
                <div className={styles.sectionHeader}>
                  <p className={styles.cardLabel}>Strengths</p>
                  <h2>What went well</h2>
                </div>
                <ul className={styles.feedbackList}>
                  {scorecard.strengths.map((strength) => (
                    <li key={strength}>{strength}</li>
                  ))}
                </ul>
              </article>

              <article className={`${styles.sectionCard} surface-card`}>
                <div className={styles.sectionHeader}>
                  <p className={styles.cardLabel}>Improvement areas</p>
                  <h2>Where to focus next</h2>
                </div>
                <ul className={styles.feedbackList}>
                  {scorecard.improvement_areas.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </article>
            </section>

            <section className={`${styles.sectionCard} surface-card`}>
              <div className={styles.sectionHeader}>
                <p className={styles.cardLabel}>Question review</p>
                <h2>Response-by-response notes</h2>
              </div>

              <div className={styles.reviewList}>
                {reviews.length > 0 ? (
                  reviews.map((review, index) => (
                    <article key={`${review.question}-${index}`} className={styles.reviewCard}>
                      <div>
                        <p className={styles.reviewLabel}>Question {index + 1}</p>
                        <h3>{review.question}</h3>
                      </div>
                      <p>{review.answer}</p>
                    </article>
                  ))
                ) : (
                  <p className={styles.emptyState}>
                    Full question review will appear here once the transcript is
                    available.
                  </p>
                )}
              </div>
            </section>
          </div>

          <aside className={styles.sideColumn}>
            <section className={`${styles.sideCard} soft-card`}>
              <p className={styles.cardLabel}>Quick summary</p>
              <div className={styles.summaryItem}>
                <span>Overall</span>
                <strong>{scorecard.final_score}%</strong>
              </div>
              <div className={styles.summaryItem}>
                <span>Status</span>
                <strong>Completed</strong>
              </div>
              <div className={styles.summaryItem}>
                <span>Mode</span>
                <strong>{session.voice_mode ? "Live Voice" : "Chat"}</strong>
              </div>
              <div className={styles.summaryItem}>
                <span>Transcript</span>
                <strong>Available</strong>
              </div>
            </section>

            <section className={`${styles.sideCard} soft-card`}>
              <p className={styles.cardLabel}>Recommendation</p>
              <h2>{recommendationLabels[scorecard.hire_recommendation] || "Keep practicing"}</h2>
              <p className={styles.sideCopy}>
                Focus next on the lowest-scoring dimensions, then rerun the
                interview to compare how the scorecard changes.
              </p>
              <button className="btn btn-primary" onClick={() => router.push(`/session/${sessionId}`)}>
                View transcript
              </button>
            </section>
          </aside>
        </section>
      </main>
    </div>
  );
}
