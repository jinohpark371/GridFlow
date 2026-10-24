import { THEMES, type ThemeId } from "@/lib/themes";
import { StepHeader } from "./StepHeader";
import styles from "./ThemePicker.module.css";

export function ThemePicker({ onSelect, onBack }: { onSelect: (themeId: ThemeId) => void; onBack: () => void }) {
  return (
    <section>
      <StepHeader title="테마 고르기" onBack={onBack} />
      <p className={styles.lead}>어떤 분위기의 게시물인가요?</p>
      <ul className={styles.list}>
        {THEMES.map((theme) => (
          <li key={theme.id}>
            <button type="button" className={styles.card} onClick={() => onSelect(theme.id)}>
              <span className={styles.swatch} aria-hidden="true">
                {theme.swatch.map((color) => (
                  <span key={color} style={{ background: color }} />
                ))}
              </span>
              <span className={styles.text}>
                <span className={styles.label}>{theme.label}</span>
                <span className={styles.description}>{theme.description}</span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
