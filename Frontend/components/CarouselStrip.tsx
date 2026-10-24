import type { DraftPhoto } from "@/lib/state";
import styles from "./CarouselStrip.module.css";

export function CarouselStrip({ photos, label }: { photos: DraftPhoto[]; label: string }) {
  return (
    <ol className={styles.strip} aria-label={label}>
      {photos.map((photo, i) => (
        <li key={photo.id} className={styles.item}>
          <span className={styles.index}>{i + 1}</span>
          <img src={photo.url} alt={`${i + 1}번째 사진`} data-photo-id={photo.id} />
        </li>
      ))}
    </ol>
  );
}
