"use client";

import { useState } from "react";
import type { Post } from "@/lib/state";
import { getTheme } from "@/lib/themes";
import { CarouselStrip } from "./CarouselStrip";
import styles from "./PostSheet.module.css";

interface Props {
  post: Post;
  onClose: () => void;
  onDelete: (postId: string) => void;
}

export function PostSheet({ post, onClose, onDelete }: Props) {
  const [confirming, setConfirming] = useState(false);

  return (
    <div className={styles.backdrop} onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label="게시물 상세"
        className={styles.sheet}
        onClick={(event) => event.stopPropagation()}
      >
        <div className={styles.handle} aria-hidden="true" />
        <p className={styles.meta}>
          {getTheme(post.themeId).label} 테마 · 사진 {post.photos.length}장
        </p>
        <CarouselStrip photos={post.photos} label="캐러셀 순서" />
        {confirming ? (
          <div className={styles.actions}>
            <p className={styles.confirmText}>이 게시물을 그리드에서 지울까요?</p>
            <button type="button" className={styles.danger} onClick={() => onDelete(post.id)}>
              삭제할게요
            </button>
            <button type="button" className={styles.secondary} onClick={() => setConfirming(false)}>
              취소
            </button>
          </div>
        ) : (
          <div className={styles.actions}>
            <button type="button" className={styles.secondary} onClick={() => setConfirming(true)}>
              삭제
            </button>
            <button type="button" className={styles.primary} onClick={onClose}>
              닫기
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
