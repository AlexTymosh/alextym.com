import { useState } from "react";
import { INTERVIEW_GUIDES, type GuideName, type GuidePosition } from "./interview";
import styles from "./workforce-scaffold.module.css";

export function InterviewGuide({ guide, onStart, onStep, onExit }: {
  guide: GuidePosition | null;
  onStart: (name: GuideName) => void;
  onStep: (name: GuideName, index: number) => void;
  onExit: () => void;
}) {
  const [choice, setChoice] = useState<GuideName>("quick");
  if (!guide) return (
    <form className={`${styles.filterBar} ${styles.guidePicker}`} aria-label="Interview walkthrough"
      onSubmit={(event) => { event.preventDefault(); onStart(choice); }}>
      <label>Guided demo
        <select value={choice} onChange={(event) => setChoice(event.currentTarget.value === "extended" ? "extended" : "quick")}>
          <option value="quick">{INTERVIEW_GUIDES.quick.label}</option>
          <option value="extended">{INTERVIEW_GUIDES.extended.label}</option>
        </select>
      </label>
      <button type="submit" className={styles.secondaryButton}>Run interview scenario</button>
    </form>
  );
  const walkthrough = INTERVIEW_GUIDES[guide.name];
  const isLast = guide.index === walkthrough.steps.length - 1;
  return (
    <aside className={styles.guide} aria-label="Active interview guide">
      <div aria-live="polite">
        <p className={styles.guideProgress}>{walkthrough.label} · Step {guide.index + 1} of {walkthrough.steps.length}</p>
        <h2>{guide.step.title}</h2><p>{guide.step.instruction}</p>
      </div>
      <div className={styles.guideActions}>
        <button type="button" className={styles.secondaryButton} onClick={onExit}>Exit guide</button>
        <button type="button" className={styles.secondaryButton} disabled={guide.index === 0}
          onClick={() => onStep(guide.name, guide.index - 1)}>Previous step</button>
        <button type="button" className={styles.primaryButton}
          onClick={() => isLast ? onExit() : onStep(guide.name, guide.index + 1)}>
          {isLast ? "Finish walkthrough" : "Next step"}
        </button>
      </div>
    </aside>
  );
}
