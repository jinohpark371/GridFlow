import { describe, expect, it } from "vitest";
import { ArrangeError, type ArrangeResult } from "./api";
import { MAX_PHOTOS } from "./limits";
import { initialState, reducer, selectResultView, urlsReleasedByAddPost, type Action, type AppState } from "./state";

function photos(count: number) {
  return Array.from({ length: count }, (_, i) => ({ blob: new Blob([String(i)]), url: `blob:${i}` }));
}

function run(actions: Action[], from: AppState = initialState): AppState {
  return actions.reduce(reducer, from);
}

const result: ArrangeResult = {
  order: ["2.jpg", "0.jpg"],
  removed: [{ id: "1.jpg", score: 0.2 }],
  skipped: [],
};

function stateAtResult(): AppState {
  return run([
    { type: "START_NEW" },
    { type: "SELECT_THEME", themeId: "golden" },
    { type: "ADD_PHOTOS", photos: photos(3) },
    { type: "ANALYZE_START" },
    { type: "ANALYZE_SUCCESS", result },
  ]);
}

describe("reducer", () => {
  it("새 게시물 → 테마 → 사진 고르기 순서로 단계가 바뀐다", () => {
    const state = run([{ type: "START_NEW" }, { type: "SELECT_THEME", themeId: "mono" }]);

    expect(state.step).toBe("pick");
    expect(state.themeId).toBe("mono");
  });

  it("사진 id는 0.jpg부터 증가하고, 빼고 다시 넣어도 겹치지 않는다", () => {
    const state = run([
      { type: "ADD_PHOTOS", photos: photos(2) },
      { type: "REMOVE_PHOTO", id: "1.jpg" },
      { type: "ADD_PHOTOS", photos: photos(1) },
    ]);

    expect(state.draft.map((p) => p.id)).toEqual(["0.jpg", "2.jpg"]);
  });

  it("여러 번 나눠 골라도 최대 장수를 넘기지 않는다", () => {
    const state = run([
      { type: "ADD_PHOTOS", photos: photos(15) },
      { type: "ADD_PHOTOS", photos: photos(10) },
    ]);

    expect(state.draft).toHaveLength(MAX_PHOTOS);
  });

  it("사진이 없으면 분석을 시작하지 않는다", () => {
    const state = run([{ type: "START_NEW" }, { type: "SELECT_THEME", themeId: "mono" }, { type: "ANALYZE_START" }]);

    expect(state.step).toBe("pick");
  });

  it("분석 성공 시 결과 단계로 간다", () => {
    expect(stateAtResult().step).toBe("result");
  });

  it("분석 실패 시 analyzing에 머물며 에러를 담는다", () => {
    const state = run([
      { type: "ADD_PHOTOS", photos: photos(1) },
      { type: "ANALYZE_START" },
      { type: "ANALYZE_FAILURE", error: new ArrangeError("server", "x") },
    ]);

    expect(state.step).toBe("analyzing");
    expect(state.error?.kind).toBe("server");
  });

  it("뒤로가기로 analyzing을 떠난 뒤 늦게 온 응답은 무시한다", () => {
    const state = run([
      { type: "ADD_PHOTOS", photos: photos(1) },
      { type: "ANALYZE_START" },
      { type: "NAVIGATE", step: "pick" },
      { type: "ANALYZE_SUCCESS", result },
      { type: "ANALYZE_FAILURE", error: new ArrangeError("server", "x") },
    ]);

    expect(state.step).toBe("pick");
    expect(state.result).toBeNull();
    expect(state.error).toBeNull();
  });

  it("그리드에 추가하면 추천 순서대로 맨 앞에 쌓이고 홈으로 간다", () => {
    const first = run([{ type: "ADD_POST" }], stateAtResult());
    const second = run(
      [
        { type: "START_NEW" },
        { type: "SELECT_THEME", themeId: "vivid" },
        { type: "ADD_PHOTOS", photos: photos(1) },
        { type: "ANALYZE_START" },
        { type: "ANALYZE_SUCCESS", result: { order: ["3.jpg"], removed: [], skipped: [] } },
        { type: "ADD_POST" },
      ],
      first,
    );

    expect(first.step).toBe("home");
    expect(first.posts[0].photos.map((p) => p.id)).toEqual(["2.jpg", "0.jpg"]);
    expect(second.posts.map((p) => p.themeId)).toEqual(["vivid", "golden"]);
    expect(second.draft).toEqual([]);
  });

  it("추천 순서가 비어 있으면(전부 제거 후보) 그리드에 추가하지 않는다", () => {
    const empty = run([
      { type: "ADD_PHOTOS", photos: photos(1) },
      { type: "SELECT_THEME", themeId: "mono" },
      { type: "ANALYZE_START" },
      { type: "ANALYZE_SUCCESS", result: { order: [], removed: [{ id: "0.jpg", score: 0.1 }], skipped: [] } },
      { type: "ADD_POST" },
    ]);

    expect(empty.posts).toEqual([]);
    expect(empty.step).toBe("result");
  });

  it("게시물을 삭제하면 그리드에서 빠지고 시트가 닫힌다", () => {
    const added = run([{ type: "ADD_POST" }], stateAtResult());
    const postId = added.posts[0].id;
    const state = run([{ type: "OPEN_POST", postId }, { type: "DELETE_POST", postId }], added);

    expect(state.posts).toEqual([]);
    expect(state.openPostId).toBeNull();
  });
});

describe("selectResultView", () => {
  it("응답 id를 초안 사진으로 바꾸고, 모르는 id는 걸러낸다", () => {
    const state = run(
      [
        {
          type: "ANALYZE_SUCCESS",
          result: {
            order: ["2.jpg", "99.jpg", "0.jpg"],
            removed: [{ id: "1.jpg", score: 0.2 }, { id: "77.jpg", score: 0.1 }],
            skipped: [{ id: "88.jpg", reason: "용량 초과(5MB 제한)" }],
          },
        },
      ],
      { ...run([{ type: "ADD_PHOTOS", photos: photos(3) }]), step: "analyzing" },
    );

    const view = selectResultView(state);

    expect(view.ordered.map((p) => p.id)).toEqual(["2.jpg", "0.jpg"]);
    expect(view.removed.map((r) => r.photo.id)).toEqual(["1.jpg"]);
    expect(view.skipped).toEqual([{ id: "88.jpg", reason: "용량 초과(5MB 제한)", photo: null }]);
  });
});

describe("urlsReleasedByAddPost", () => {
  it("그리드에 남지 않는 사진(제거 후보)의 URL만 돌려준다", () => {
    expect(urlsReleasedByAddPost(stateAtResult())).toEqual(["blob:1"]);
  });
});
