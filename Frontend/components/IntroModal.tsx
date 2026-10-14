"use client";

import { useState } from "react";
import styles from "./IntroModal.module.css";

const SLIDES = [
  { title: "사진을 고르면", body: "한 게시물에 넣을 사진을 최대 20장까지 골라 주세요." },
  { title: "테마에 안 맞는 사진을 골라내고", body: "흑백 · 비비드 · 골든아워 중 고른 테마와 어울리지 않는 사진을 알려 드려요." },
  { title: "넘겨 볼 순서를 추천해요", body: "색감이 자연스럽게 이어지도록 캐러셀 순서를 정해 드려요." },
] as const;

export function IntroModal({ onClose }: { onClose: () => void }) {
  const [index, setIndex] = useState(0);
  const isLast = index === SLIDES.length - 1;
  const slide = SLIDES[index];

  return (
    <div className={styles.backdrop}>
      <div role="dialog" aria-modal="true" aria-labelledby="intro-title" className={styles.modal}>
        <p className={styles.step}>
          {index + 1} / {SLIDES.length}
        </p>
        <h2 id="intro-title" className={styles.title}>
          {slide.title}
        </h2>
        <p className={styles.body}>{slide.body}</p>
        <div className={styles.dots} aria-hidden="true">
          {SLIDES.map((s, i) => (
            <span key={s.title} data-active={i === index} />
          ))}
        </div>
        <div className={styles.actions}>
          {!isLast && (
            <button type="button" className={styles.skip} onClick={onClose}>
              건너뛰기
            </button>
          )}
          <button type="button" className={styles.primary} onClick={() => (isLast ? onClose() : setIndex(index + 1))}>
            {isLast ? "시작하기" : "다음"}
          </button>
        </div>
      </div>
    </div>
  );
}
