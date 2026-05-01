import Link from "next/link";
import styles from "./page.module.css";

const metrics = [
  { value: "10k+", label: "Sessions Conducted" },
  { value: "92%", label: "Candidate Success" },
  { value: "24/7", label: "AI Availability" },
];

const features = [
  {
    title: "Realistic practice",
    description:
      "Simulate pressure, pacing, and follow-up depth with AI interviewers tailored to your target role.",
  },
  {
    title: "Mode flexibility",
    description:
      "Choose live voice with TTS for presence training or chat mode when you want focused, text-first rehearsal.",
  },
  {
    title: "Instant feedback",
    description:
      "Review scorecards, question breakdowns, and improvement areas right after your session ends.",
  },
];

export default function LandingPage() {
  return (
    <div className={styles.page}>
      <header className={styles.topbar}>
        <div className="app-shell">
          <div className={styles.topbarInner}>
            <Link href="/" className={styles.brand}>
              Cognitive Gallery
            </Link>

            <nav className={styles.nav}>
              <a href="#features">Features</a>
              <a href="#modes">Modes</a>
              <a href="#roadmap">Roadmap</a>
            </nav>

            <div className={styles.topbarActions}>
              <Link href="/new" className="btn btn-ghost">
                Sign in
              </Link>
              <Link href="/new" className="btn btn-primary">
                Get started
              </Link>
            </div>
          </div>
        </div>
      </header>

      <main>
        <section className={`${styles.hero} app-shell`}>
          <div className={styles.heroCopy}>
            <span className="eyebrow">AI interview prep</span>
            <h1>Master the interview with AI.</h1>
            <p>
              Practice with high-fidelity voice or chat simulations, get
              structured feedback in minutes, and build confidence before the
              real conversation.
            </p>
            <div className={styles.heroActions}>
              <Link href="/new" className="btn btn-primary">
                Get Started Free
              </Link>
              <a href="#modes" className="btn btn-secondary">
                Explore Product
              </a>
            </div>
          </div>

          <div className={`${styles.preview} surface-card`}>
            <div className={styles.previewBadge}>Session preview</div>
            <div className={styles.previewHeader}>
              <div>
                <p className={styles.previewEyebrow}>Live prep</p>
                <h2>Choose your mode</h2>
              </div>
              <span className="pill">
                <span className="status-dot" />
                Ready
              </span>
            </div>

            <div className={styles.modeCards}>
              <article className={styles.modeCard}>
                <div className={styles.modeIcon}>◉</div>
                <h3>Live Voice Interview</h3>
                <p>
                  Practice with TTS-driven interviewers, a live microphone
                  flow, and stress-reducing transcript support.
                </p>
              </article>

              <article className={styles.modeCard}>
                <div className={styles.modeIcon}>⌘</div>
                <h3>Chat-Based Interview</h3>
                <p>
                  Work through structured prompts, iterate faster, and focus on
                  reasoning without the pressure of voice.
                </p>
              </article>
            </div>
          </div>
        </section>

        <section className={styles.metricBand}>
          <div className="app-shell">
            <div className={styles.metricGrid}>
              {metrics.map((metric) => (
                <div key={metric.label} className={styles.metricCard}>
                  <strong>{metric.value}</strong>
                  <span>{metric.label}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="modes" className={`${styles.featureSection} app-shell`}>
          <div className={styles.sectionHeader}>
            <span className="eyebrow">Product preview</span>
            <h2>Built for calm, structured practice</h2>
            <p>
              The interface stays focused during live interviews, then hands you
              a clear summary and scorecard when the session ends.
            </p>
          </div>

          <div className={styles.modeShowcase}>
            <div className={`${styles.voicePanel} surface-card`}>
              <div className={styles.voiceOrb}>
                <div className={styles.voiceOrbInner}>AI</div>
              </div>
              <div>
                <p className={styles.cardEyebrow}>Live voice with TTS</p>
                <h3>Hear the prompt. Respond naturally.</h3>
                <p>
                  A dedicated live session workspace keeps the AI voice signal,
                  candidate transcript, and session controls visible without
                  clutter.
                </p>
              </div>
            </div>

            <div className={`${styles.chatPanel} soft-card`}>
              <p className={styles.cardEyebrow}>Chat interview mode</p>
              <h3>Use text when you want focused rehearsal.</h3>
              <ul className={styles.chatList}>
                <li>Switch between pressure training and deliberate practice.</li>
                <li>Review AI follow-ups and structure your responses faster.</li>
                <li>Carry the same scorecard and improvement loop across modes.</li>
              </ul>
            </div>
          </div>
        </section>

        <section id="features" className={`${styles.featureCards} app-shell`}>
          {features.map((feature) => (
            <article key={feature.title} className="surface-card">
              <p className={styles.cardEyebrow}>Feature</p>
              <h3>{feature.title}</h3>
              <p>{feature.description}</p>
            </article>
          ))}
        </section>

        <section id="roadmap" className={`${styles.roadmap} app-shell`}>
          <div className={`${styles.roadmapCard} soft-card`}>
            <div>
              <span className="eyebrow">Coming soon</span>
              <h2>More workflow tools are on the way</h2>
              <p>
                The job tracker is planned as the next workflow layer, but the
                current experience stays tightly focused on interview practice,
                live sessions, and high-quality feedback.
              </p>
            </div>
            <Link href="/new" className="btn btn-primary">
              Try the app flow
            </Link>
          </div>
        </section>
      </main>
    </div>
  );
}
