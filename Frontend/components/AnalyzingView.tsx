"use client";

import { useEffect, useState } from "react";
import type { ArrangeError } from "@/lib/api";
import styles from "./AnalyzingView.module.css";
import buttons from "./buttons.module.css";

const SLOW_HINT_MS = 10_000;

function errorMessage(error: ArrangeError): string {
  switch (error.kind) {
    case "network":
      return "서버에 연결할 수 없어요";
    case "timeout":
      return "분석이 너무 오래 걸려요. 사진 수를 줄여 보세요";
    case "server":
      return "잠시 문제가 생겼어요";
    case "bad_request":
      return error.message; // 정상 흐름에선 프론트가 미리 막으므로, 보인다면 버그 — 서버 문구 그대로
  }
}

export function AnalyzingView({ error, onRetry, onRepick }: { error: ArrangeError | null; onRetry: () => void; onRepick: () => void }) {
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    if (error) return;
    const timer = setTimeout(() => setSlow(true), SLOW_HINT_MS);
    return () => clearTimeout(timer);
  }, [error]);

  if (error) {
    return (
      <section className={styles.card} role="alert">
        <h2 className={styles.message}>{errorMessage(error)}</h2>
        <div className={buttons.actions}>
          {error.kind !== "bad_request" && (
            <button type="button" className={buttons.primary} onClick={onRetry}>
              다시 시도
            </button>
          )}
          <button type="button" className={buttons.secondary} onClick={onRepick}>
            사진 다시 고르기
          </button>
        </div>
      </section>
    );
  }

  return (
    <section className={styles.loading} aria-busy="true">
      <div className={styles.spinner} aria-hidden="true" />
      <p>사진을 분석하고 있어요</p>
      {slow && <p className={styles.hint}>서버를 깨우는 중일 수 있어요. 조금만 기다려 주세요</p>}
    </section>
  );
}
