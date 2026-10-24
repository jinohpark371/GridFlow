import type { ResultView as ResultViewData } from "@/lib/state";
import buttons from "./buttons.module.css";
import { CarouselStrip } from "./CarouselStrip";
import styles from "./ResultView.module.css";
import { StepHeader } from "./StepHeader";

interface Props {
  themeLabel: string;
  view: ResultViewData;
  onAddToGrid: () => void;
  onRepick: () => void;
  onChangeTheme: () => void;
}

export function ResultView({ themeLabel, view, onAddToGrid, onRepick, onChangeTheme }: Props) {
  const { ordered, removed, skipped } = view;

  return (
    <section>
      <StepHeader title="추천 결과" onBack={onRepick} />

      {ordered.length === 0 ? (
        <div className={styles.empty} role="status">
          <p>이 테마와 어울리는 사진이 없어요</p>
          <button type="button" className={buttons.primary} onClick={onChangeTheme}>
            다른 테마로 해보기
          </button>
        </div>
      ) : (
        <>
          <h2 className={styles.heading}>이 순서로 올려 보세요</h2>
          <p className={styles.sub}>
            {themeLabel} · 사진 {ordered.length}장
          </p>
          <CarouselStrip photos={ordered} label="추천 캐러셀 순서" />
        </>
      )}

      {removed.length > 0 && (
        <div className={styles.block}>
          <h3 className={styles.blockTitle}>빼는 걸 추천해요</h3>
          <p className={styles.sub}>{themeLabel} 테마와 잘 어울리지 않아요</p>
          <ul className={styles.removed} aria-label="빼는 걸 추천하는 사진">
            {removed.map(({ photo, score }) => (
              <li key={photo.id}>
                <img src={photo.url} alt="빼는 걸 추천하는 사진" data-photo-id={photo.id} />
                <span>점수 {score.toFixed(2)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {skipped.length > 0 && (
        <p className={styles.skipped} role="status">
          분석하지 못한 사진 {skipped.length}장
        </p>
      )}

      <div className={buttons.actions}>
        {ordered.length > 0 && (
          <button type="button" className={buttons.primary} onClick={onAddToGrid}>
            그리드에 추가
          </button>
        )}
        <button type="button" className={buttons.secondary} onClick={onRepick}>
          사진 다시 고르기
        </button>
      </div>
    </section>
  );
}
