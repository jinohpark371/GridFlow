"use client";

import { useEffect, useReducer, useRef, useState, useSyncExternalStore } from "react";
import { arrange, ArrangeError } from "@/lib/api";
import { hasSeenIntro, markIntroSeen, subscribeIntroSeen } from "@/lib/introSeen";
import { MAX_PHOTOS } from "@/lib/limits";
import { resizeImage } from "@/lib/resize";
import { initialState, PREVIOUS_STEP, reducer, selectResultView, urlsReleasedByAddPost, type Step } from "@/lib/state";
import { getTheme } from "@/lib/themes";
import { AnalyzingView } from "./AnalyzingView";
import { FeedGrid } from "./FeedGrid";
import { IntroModal } from "./IntroModal";
import { PhotoPicker } from "./PhotoPicker";
import { PostSheet } from "./PostSheet";
import { ResultView } from "./ResultView";
import { ThemePicker } from "./ThemePicker";

export function GridFlowApp() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const [notice, setNotice] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [introForced, setIntroForced] = useState(false);
  // 정적 빌드(서버)에서는 모달을 그리지 않고, 브라우저에서 저장 여부를 읽은 뒤 띄운다
  const introSeen = useSyncExternalStore(subscribeIntroSeen, hasSeenIntro, () => true);

  const stepRef = useRef<Step>(state.step);
  const draftCountRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    stepRef.current = state.step;
    draftCountRef.current = state.draft.length;
  }, [state.step, state.draft.length]);

  useEffect(() => {
    const onPopState = () => {
      const current = stepRef.current;
      if (current === "home") return;
      if (current === "analyzing") abortRef.current?.abort();
      const previous = PREVIOUS_STEP[current];
      dispatch({ type: "NAVIGATE", step: previous });
      if (previous !== "home") window.history.pushState({ gridflow: true }, "");
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const goBack = () => window.history.back();

  const handleNewPost = () => {
    state.draft.forEach((photo) => URL.revokeObjectURL(photo.url)); // 지난번에 그만둔 초안
    setNotice(null);
    dispatch({ type: "START_NEW" });
    if (!window.history.state?.gridflow) window.history.pushState({ gridflow: true }, "");
  };

  const handleAddFiles = async (files: File[]) => {
    const room = Math.max(MAX_PHOTOS - draftCountRef.current, 0);
    const targets = files.slice(0, room);
    setAdding(true);
    const ready: { blob: Blob; url: string }[] = [];
    let failed = 0;
    for (const file of targets) {
      try {
        const blob = await resizeImage(file);
        ready.push({ blob, url: URL.createObjectURL(blob) });
      } catch {
        failed += 1; // 브라우저가 못 여는 형식(일부 안드로이드 HEIC 등)
      }
    }
    setAdding(false);
    dispatch({ type: "ADD_PHOTOS", photos: ready });
    const messages: string[] = [];
    if (files.length > targets.length) messages.push(`최대 ${MAX_PHOTOS}장까지 고를 수 있어요`);
    if (failed > 0) messages.push(`열 수 없는 사진 ${failed}장을 뺐어요`);
    setNotice(messages.length > 0 ? messages.join(" · ") : null);
  };

  const handleRemovePhoto = (id: string) => {
    const photo = state.draft.find((p) => p.id === id);
    if (photo) URL.revokeObjectURL(photo.url);
    dispatch({ type: "REMOVE_PHOTO", id });
  };

  const runAnalyze = async () => {
    if (!state.themeId || state.draft.length === 0) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    dispatch({ type: "ANALYZE_START" });
    setAttempt((n) => n + 1);
    try {
      const result = await arrange(
        getTheme(state.themeId).prompt,
        state.draft.map((p) => ({ id: p.id, blob: p.blob })),
        { signal: controller.signal },
      );
      dispatch({ type: "ANALYZE_SUCCESS", result });
    } catch (error) {
      if (controller.signal.aborted) return; // 뒤로가기로 취소한 요청
      dispatch({
        type: "ANALYZE_FAILURE",
        error: error instanceof ArrangeError ? error : new ArrangeError("server", String(error)),
      });
    }
  };

  const handleAddToGrid = () => {
    urlsReleasedByAddPost(state).forEach((url) => URL.revokeObjectURL(url));
    dispatch({ type: "ADD_POST" });
    window.history.replaceState(null, "");
  };

  const handleDeletePost = (postId: string) => {
    state.posts.find((p) => p.id === postId)?.photos.forEach((photo) => URL.revokeObjectURL(photo.url));
    dispatch({ type: "DELETE_POST", postId });
  };

  const closeIntro = () => {
    markIntroSeen();
    setIntroForced(false);
  };

  const openPost = state.posts.find((p) => p.id === state.openPostId) ?? null;

  return (
    <main className="app">
      {state.step === "home" && (
        <FeedGrid
          posts={state.posts}
          onOpenPost={(postId) => dispatch({ type: "OPEN_POST", postId })}
          onNewPost={handleNewPost}
          onShowIntro={() => setIntroForced(true)}
        />
      )}
      {state.step === "theme" && <ThemePicker onSelect={(themeId) => dispatch({ type: "SELECT_THEME", themeId })} onBack={goBack} />}
      {state.step === "pick" && (
        <PhotoPicker
          photos={state.draft}
          notice={notice}
          adding={adding}
          onAdd={handleAddFiles}
          onRemove={handleRemovePhoto}
          onAnalyze={runAnalyze}
          onBack={goBack}
        />
      )}
      {state.step === "analyzing" && (
        <AnalyzingView key={attempt} error={state.error} onRetry={runAnalyze} onRepick={() => dispatch({ type: "NAVIGATE", step: "pick" })} />
      )}
      {state.step === "result" && state.themeId && (
        <ResultView
          themeLabel={getTheme(state.themeId).label}
          view={selectResultView(state)}
          onAddToGrid={handleAddToGrid}
          onRepick={() => dispatch({ type: "NAVIGATE", step: "pick" })}
          onChangeTheme={() => dispatch({ type: "NAVIGATE", step: "theme" })}
        />
      )}
      {openPost && <PostSheet post={openPost} onClose={() => dispatch({ type: "CLOSE_POST" })} onDelete={handleDeletePost} />}
      {(!introSeen || introForced) && <IntroModal onClose={closeIntro} />}
    </main>
  );
}
