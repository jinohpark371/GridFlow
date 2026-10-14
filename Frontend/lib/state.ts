import type { ArrangeError, ArrangeResult } from "./api";
import { MAX_PHOTOS } from "./limits";
import type { ThemeId } from "./themes";

export type Step = "home" | "theme" | "pick" | "analyzing" | "result";

export interface DraftPhoto {
  /** 서버에 보내는 이름(0.jpg, 1.jpg, …) */
  id: string;
  /** 512px로 줄인 JPEG */
  blob: Blob;
  /** 썸네일용 objectURL — 쓰지 않게 되면 호출 측에서 URL.revokeObjectURL */
  url: string;
}

export interface Post {
  id: string;
  themeId: ThemeId;
  /** 추천 캐러셀 순서, 1장 이상 */
  photos: DraftPhoto[];
}

export interface AppState {
  step: Step;
  /** 최신이 앞 — 그대로 그리면 그리드 왼쪽 위가 최신 */
  posts: Post[];
  themeId: ThemeId | null;
  draft: DraftPhoto[];
  nextPhotoSeq: number;
  nextPostSeq: number;
  result: ArrangeResult | null;
  error: ArrangeError | null;
  openPostId: string | null;
}

export const initialState: AppState = {
  step: "home",
  posts: [],
  themeId: null,
  draft: [],
  nextPhotoSeq: 0,
  nextPostSeq: 0,
  result: null,
  error: null,
  openPostId: null,
};

export type Action =
  | { type: "START_NEW" }
  | { type: "SELECT_THEME"; themeId: ThemeId }
  | { type: "ADD_PHOTOS"; photos: { blob: Blob; url: string }[] }
  | { type: "REMOVE_PHOTO"; id: string }
  | { type: "ANALYZE_START" }
  | { type: "ANALYZE_SUCCESS"; result: ArrangeResult }
  | { type: "ANALYZE_FAILURE"; error: ArrangeError }
  | { type: "ADD_POST" }
  | { type: "DELETE_POST"; postId: string }
  | { type: "OPEN_POST"; postId: string }
  | { type: "CLOSE_POST" }
  | { type: "NAVIGATE"; step: Step };

/** 휴대폰 뒤로가기·화면의 ← 버튼이 가는 곳 */
export const PREVIOUS_STEP: Record<Step, Step> = {
  home: "home",
  theme: "home",
  pick: "theme",
  analyzing: "pick",
  result: "pick",
};

export function reducer(state: AppState, action: Action): AppState {
  switch (action.type) {
    case "START_NEW":
      return { ...state, step: "theme", themeId: null, draft: [], result: null, error: null };
    case "SELECT_THEME":
      return { ...state, step: "pick", themeId: action.themeId };
    case "ADD_PHOTOS": {
      const room = Math.max(MAX_PHOTOS - state.draft.length, 0);
      const accepted = action.photos.slice(0, room).map((photo, i) => ({ ...photo, id: `${state.nextPhotoSeq + i}.jpg` }));
      return { ...state, draft: [...state.draft, ...accepted], nextPhotoSeq: state.nextPhotoSeq + accepted.length };
    }
    case "REMOVE_PHOTO":
      return { ...state, draft: state.draft.filter((p) => p.id !== action.id) };
    case "ANALYZE_START":
      if (state.draft.length === 0) return state;
      return { ...state, step: "analyzing", result: null, error: null };
    case "ANALYZE_SUCCESS":
      if (state.step !== "analyzing") return state; // 취소된 요청의 늦은 응답
      return { ...state, step: "result", result: action.result };
    case "ANALYZE_FAILURE":
      if (state.step !== "analyzing") return state;
      return { ...state, error: action.error };
    case "ADD_POST": {
      if (state.step !== "result" || !state.themeId) return state;
      const { ordered } = selectResultView(state);
      if (ordered.length === 0) return state;
      const post: Post = { id: `post-${state.nextPostSeq}`, themeId: state.themeId, photos: ordered };
      return {
        ...state,
        step: "home",
        posts: [post, ...state.posts],
        nextPostSeq: state.nextPostSeq + 1,
        themeId: null,
        draft: [],
        result: null,
      };
    }
    case "DELETE_POST":
      return { ...state, posts: state.posts.filter((p) => p.id !== action.postId), openPostId: null };
    case "OPEN_POST":
      return { ...state, openPostId: action.postId };
    case "CLOSE_POST":
      return { ...state, openPostId: null };
    case "NAVIGATE":
      return { ...state, step: action.step, error: null };
  }
}

export interface ResultView {
  ordered: DraftPhoto[];
  removed: { photo: DraftPhoto; score: number }[];
  skipped: { id: string; reason: string; photo: DraftPhoto | null }[];
}

/** 서버 응답의 id를 초안 사진으로 바꾼다. 서버가 모르는 id를 돌려줘도 화면이 깨지지 않게 걸러낸다 */
export function selectResultView(state: Pick<AppState, "draft" | "result">): ResultView {
  if (!state.result) return { ordered: [], removed: [], skipped: [] };
  const byId = new Map(state.draft.map((p) => [p.id, p]));
  return {
    ordered: state.result.order.flatMap((id) => {
      const photo = byId.get(id);
      return photo ? [photo] : [];
    }),
    removed: state.result.removed.flatMap(({ id, score }) => {
      const photo = byId.get(id);
      return photo ? [{ photo, score }] : [];
    }),
    skipped: state.result.skipped.map(({ id, reason }) => ({ id, reason, photo: byId.get(id) ?? null })),
  };
}

export function urlsReleasedByAddPost(state: AppState): string[] {
  const kept = new Set(selectResultView(state).ordered.map((p) => p.id));
  return state.draft.filter((p) => !kept.has(p.id)).map((p) => p.url);
}
