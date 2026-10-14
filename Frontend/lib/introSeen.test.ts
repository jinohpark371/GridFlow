import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  vi.restoreAllMocks();
  vi.resetModules();
  window.localStorage.clear();
});

describe("introSeen", () => {
  it("처음엔 안 본 상태이고, 표시하면 localStorage에 남는다", async () => {
    const { hasSeenIntro, markIntroSeen } = await import("./introSeen");

    expect(hasSeenIntro()).toBe(false);
    markIntroSeen();
    expect(hasSeenIntro()).toBe(true);
    expect(window.localStorage.getItem("gridflow:intro-seen")).toBe("1");
  });

  it("localStorage가 막혀 있어도 이번 방문 동안은 본 것으로 기억한다", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    const { hasSeenIntro, markIntroSeen } = await import("./introSeen");

    expect(hasSeenIntro()).toBe(false);
    markIntroSeen();
    expect(hasSeenIntro()).toBe(true);
  });

  it("표시하면 구독자에게 알린다", async () => {
    const { markIntroSeen, subscribeIntroSeen } = await import("./introSeen");
    const listener = vi.fn();
    subscribeIntroSeen(listener);

    markIntroSeen();

    expect(listener).toHaveBeenCalledTimes(1);
  });
});
