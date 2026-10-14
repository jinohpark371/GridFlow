"use client";

import { useRef } from "react";
import { MAX_PHOTOS } from "@/lib/limits";
import type { DraftPhoto } from "@/lib/state";
import buttons from "./buttons.module.css";
import styles from "./PhotoPicker.module.css";
import { StepHeader } from "./StepHeader";

interface Props {
  photos: DraftPhoto[];
  notice: string | null;
  adding: boolean;
  onAdd: (files: File[]) => void;
  onRemove: (id: string) => void;
  onAnalyze: () => void;
  onBack: () => void;
}

export function PhotoPicker({ photos, notice, adding, onAdd, onRemove, onAnalyze, onBack }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const full = photos.length >= MAX_PHOTOS;

  return (
    <section>
      <StepHeader title="사진 고르기" onBack={onBack} />
      <p className={styles.count} aria-live="polite">
        {photos.length} / {MAX_PHOTOS}
      </p>
      {notice && (
        <p role="status" className={styles.notice}>
          {notice}
        </p>
      )}

      <ul className={styles.grid} aria-label="고른 사진">
        {photos.map((photo) => (
          <li key={photo.id} className={styles.item}>
            <img src={photo.url} alt="고른 사진" data-photo-id={photo.id} />
            <button type="button" className={styles.remove} aria-label="이 사진 빼기" onClick={() => onRemove(photo.id)}>
              ×
            </button>
          </li>
        ))}
      </ul>

      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        multiple
        hidden
        onChange={(event) => {
          const files = Array.from(event.target.files ?? []);
          event.target.value = ""; // 같은 사진을 다시 골라도 change가 일어나게
          if (files.length > 0) onAdd(files);
        }}
      />

      <div className={buttons.actions}>
        <button type="button" className={buttons.secondary} disabled={full || adding} onClick={() => inputRef.current?.click()}>
          {adding ? "사진 준비 중…" : "갤러리에서 선택"}
        </button>
        <button type="button" className={buttons.primary} disabled={photos.length === 0 || adding} onClick={onAnalyze}>
          분석하기
        </button>
      </div>
    </section>
  );
}
