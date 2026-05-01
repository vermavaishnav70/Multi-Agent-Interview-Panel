"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { SessionConfig } from "@/lib/types";
import styles from "./page.module.css";

export default function NewSessionPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [mode, setMode] = useState<"voice" | "chat">("voice");
  const [config, setConfig] = useState<SessionConfig>({
    job_role: "",
    job_description: "",
    difficulty: "medium",
    voice_mode: true,
    max_turns: 9,
  });
  const [resumeFile, setResumeFile] = useState<File | null>(null);

  const handleResumeChange = (file: File | null) => {
    if (file && !file.name.toLowerCase().endsWith(".pdf")) {
      setError("Please upload a PDF file.");
      return;
    }

    setResumeFile(file);
    setError("");
  };

  const handleSubmit = async () => {
    if (!config.job_role.trim()) {
      setError("Job role is required.");
      return;
    }

    if (!config.job_description.trim() || config.job_description.trim().length < 10) {
      setError("Please provide a meaningful job description.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const formData = new FormData();
      formData.append("job_role", config.job_role);
      formData.append("job_description", config.job_description);
      formData.append("difficulty", config.difficulty);
      formData.append("voice_mode", String(mode === "voice"));
      formData.append("max_turns", String(config.max_turns));

      if (resumeFile) {
        formData.append("resume", resumeFile);
      }

      const response = await fetch("/api/sessions", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || "Failed to create session");
      }

      const { session_id } = await response.json();
      router.push(`/session/${session_id}`);
    } catch (submitError) {
      setError(
        submitError instanceof Error ? submitError.message : "Failed to create session"
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.page}>
      <div className="app-shell">
        <div className={styles.header}>
          <div>
            <p className="eyebrow">Session setup</p>
            <h1>Start a new interview workspace</h1>
            <p>
              This route keeps the marketing landing clean while still giving
              you the full live product flow today.
            </p>
          </div>
        </div>

        <div className={styles.layout}>
          <section className={`${styles.formCard} surface-card`}>
            <div className={styles.modeSwitcher}>
              <button
                className={mode === "voice" ? styles.modeActive : styles.modeButton}
                onClick={() => setMode("voice")}
                type="button"
              >
                Live Voice
              </button>
              <button
                className={mode === "chat" ? styles.modeActive : styles.modeButton}
                onClick={() => setMode("chat")}
                type="button"
              >
                Chat Interview
              </button>
            </div>

            <div className={styles.fieldGroup}>
              <label className="field-label" htmlFor="job-role">
                Target role
              </label>
              <input
                id="job-role"
                className="field-input"
                placeholder="Senior Frontend Engineer"
                value={config.job_role}
                onChange={(event) =>
                  setConfig((current) => ({ ...current, job_role: event.target.value }))
                }
              />
            </div>

            <div className={styles.fieldGroup}>
              <label className="field-label" htmlFor="job-description">
                Job description
              </label>
              <textarea
                id="job-description"
                className="field-textarea"
                placeholder="Paste the role description you want to practice against."
                value={config.job_description}
                onChange={(event) =>
                  setConfig((current) => ({
                    ...current,
                    job_description: event.target.value,
                  }))
                }
              />
            </div>

            <div className={styles.inlineFields}>
              <div>
                <label className="field-label" htmlFor="difficulty">
                  Difficulty
                </label>
                <select
                  id="difficulty"
                  className="field-select"
                  value={config.difficulty}
                  onChange={(event) =>
                    setConfig((current) => ({
                      ...current,
                      difficulty: event.target.value as SessionConfig["difficulty"],
                    }))
                  }
                >
                  <option value="easy">Easy</option>
                  <option value="medium">Medium</option>
                  <option value="hard">Hard</option>
                </select>
              </div>

              <div>
                <label className="field-label" htmlFor="turns">
                  Questions
                </label>
                <input
                  id="turns"
                  className="field-input"
                  type="number"
                  min={3}
                  max={15}
                  value={config.max_turns}
                  onChange={(event) =>
                    setConfig((current) => ({
                      ...current,
                      max_turns: Number(event.target.value),
                    }))
                  }
                />
              </div>
            </div>

            <div className={styles.fieldGroup}>
              <label className="field-label" htmlFor="resume-upload">
                Resume
              </label>
              <label className={styles.uploadCard} htmlFor="resume-upload">
                <input
                  id="resume-upload"
                  type="file"
                  accept=".pdf"
                  className={styles.hiddenInput}
                  onChange={(event) =>
                    handleResumeChange(event.target.files?.[0] || null)
                  }
                />
                <span className={styles.uploadTitle}>
                  {resumeFile ? resumeFile.name : "Upload a PDF resume"}
                </span>
                <span className={styles.uploadHint}>
                  Optional, but recommended for better context and scorecards.
                </span>
              </label>
            </div>

            {error ? <p className={styles.error}>{error}</p> : null}

            <div className={styles.actions}>
              <button
                type="button"
                className="btn btn-primary"
                disabled={loading}
                onClick={handleSubmit}
              >
                {loading ? "Creating session..." : "Launch Session"}
              </button>
            </div>
          </section>

          <aside className={`${styles.preview} soft-card`}>
            <p className={styles.previewEyebrow}>What happens next</p>
            <h2>{mode === "voice" ? "Live voice interview flow" : "Chat interview flow"}</h2>
            <ul>
              <li>AI starts the interview and adapts follow-up questions.</li>
              <li>
                {mode === "voice"
                  ? "You answer with microphone input, TTS playback, and transcript support."
                  : "You answer in chat with the same structured panel evaluation."}
              </li>
              <li>After the session, you land on a completion summary and scorecard.</li>
            </ul>
          </aside>
        </div>
      </div>
    </div>
  );
}
