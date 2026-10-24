import styles from "./StepHeader.module.css";

export function StepHeader({ title, onBack }: { title: string; onBack: () => void }) {
  return (
    <header className={styles.header}>
      <button type="button" className={styles.back} onClick={onBack} aria-label="뒤로">
        ←
      </button>
      <h1 className={styles.title}>{title}</h1>
    </header>
  );
}
