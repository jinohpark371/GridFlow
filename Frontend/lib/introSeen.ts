const KEY = "gridflow:intro-seen";
const listeners = new Set<() => void>();
/** localStorage가 막힌 환경(사파리 시크릿 모드 등)에서도 이번 방문 동안은 다시 띄우지 않기 위한 메모리 기억 */
let seenThisVisit = false;

export function hasSeenIntro(): boolean {
  if (seenThisVisit) return true;
  try {
    return window.localStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
}

export function markIntroSeen(): void {
  seenThisVisit = true;
  try {
    window.localStorage.setItem(KEY, "1");
  } catch {
    // 저장이 막혀 있으면 다음 방문 때 한 번 더 보여주면 된다
  }
  listeners.forEach((listener) => listener());
}

export function subscribeIntroSeen(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
