import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ArrangeError } from "@/lib/api";
import type { DraftPhoto } from "@/lib/state";
import { AnalyzingView } from "./AnalyzingView";
import { PhotoPicker } from "./PhotoPicker";
import { ResultView } from "./ResultView";
import { ThemePicker } from "./ThemePicker";

function photo(id: string): DraftPhoto {
  return { id, blob: new Blob(), url: `blob:${id}` };
}

describe("ThemePicker", () => {
  it("테마 카드를 누르면 그 테마 id로 알린다", async () => {
    const onSelect = vi.fn();
    render(<ThemePicker onSelect={onSelect} onBack={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: /골든아워/ }));

    expect(onSelect).toHaveBeenCalledWith("golden");
  });
});

describe("PhotoPicker", () => {
  const base = { notice: null, adding: false, onAdd: vi.fn(), onRemove: vi.fn(), onAnalyze: vi.fn(), onBack: vi.fn() };

  it("사진이 없으면 분석하기를 누를 수 없다", () => {
    render(<PhotoPicker {...base} photos={[]} />);

    expect(screen.getByRole("button", { name: "분석하기" })).toBeDisabled();
    expect(screen.getByText("0 / 20")).toBeInTheDocument();
  });

  it("고른 장수와 안내 문구를 보여주고, 사진을 뺄 수 있다", async () => {
    const onRemove = vi.fn();
    render(<PhotoPicker {...base} onRemove={onRemove} notice="최대 20장까지 고를 수 있어요" photos={[photo("0.jpg"), photo("1.jpg")]} />);

    expect(screen.getByText("2 / 20")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("최대 20장까지 고를 수 있어요");
    await userEvent.click(screen.getAllByRole("button", { name: "이 사진 빼기" })[1]);
    expect(onRemove).toHaveBeenCalledWith("1.jpg");
  });

  it("20장이 차면 더 고를 수 없다", () => {
    const full = Array.from({ length: 20 }, (_, i) => photo(`${i}.jpg`));
    render(<PhotoPicker {...base} photos={full} />);

    expect(screen.getByRole("button", { name: "갤러리에서 선택" })).toBeDisabled();
  });
});

describe("AnalyzingView", () => {
  it("10초가 지나면 서버를 깨우는 중일 수 있다고 안내한다", () => {
    vi.useFakeTimers();
    render(<AnalyzingView error={null} onRetry={vi.fn()} onRepick={vi.fn()} />);

    expect(screen.getByText("사진을 분석하고 있어요")).toBeInTheDocument();
    expect(screen.queryByText(/서버를 깨우는 중/)).not.toBeInTheDocument();
    act(() => {
      vi.advanceTimersByTime(10_000);
    });
    expect(screen.getByText(/서버를 깨우는 중/)).toBeInTheDocument();
    vi.useRealTimers();
  });

  it.each([
    ["network", "서버에 연결할 수 없어요"],
    ["timeout", "분석이 너무 오래 걸려요. 사진 수를 줄여 보세요"],
    ["server", "잠시 문제가 생겼어요"],
  ] as const)("%s 에러는 '%s'와 다시 시도 버튼", async (kind, message) => {
    const onRetry = vi.fn();
    render(<AnalyzingView error={new ArrangeError(kind, "x")} onRetry={onRetry} onRepick={vi.fn()} />);

    expect(screen.getByRole("alert")).toHaveTextContent(message);
    await userEvent.click(screen.getByRole("button", { name: "다시 시도" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("bad_request는 서버 메시지를 보여주고 다시 시도 없이 사진 다시 고르기만", () => {
    render(<AnalyzingView error={new ArrangeError("bad_request", "사진은 최대 20장까지 보낼 수 있음")} onRetry={vi.fn()} onRepick={vi.fn()} />);

    expect(screen.getByRole("alert")).toHaveTextContent("사진은 최대 20장까지 보낼 수 있음");
    expect(screen.queryByRole("button", { name: "다시 시도" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "사진 다시 고르기" })).toBeInTheDocument();
  });
});

describe("ResultView", () => {
  const handlers = { onAddToGrid: vi.fn(), onRepick: vi.fn(), onChangeTheme: vi.fn() };

  it("추천 순서·빼는 걸 추천·분석 못 한 사진을 보여준다", () => {
    render(
      <ResultView
        themeLabel="골든아워"
        view={{
          ordered: [photo("2.jpg"), photo("0.jpg")],
          removed: [{ photo: photo("1.jpg"), score: 0.214 }],
          skipped: [{ id: "3.jpg", reason: "용량 초과(5MB 제한)", photo: photo("3.jpg") }],
        }}
        {...handlers}
      />,
    );

    const order = screen.getByRole("list", { name: "추천 캐러셀 순서" });
    expect([...order.querySelectorAll("img")].map((img) => img.getAttribute("data-photo-id"))).toEqual(["2.jpg", "0.jpg"]);
    expect(screen.getByRole("list", { name: "빼는 걸 추천하는 사진" })).toHaveTextContent("점수 0.21");
    expect(screen.getByText("분석하지 못한 사진 1장")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "그리드에 추가" })).toBeInTheDocument();
  });

  it("전부 제거 후보면 안내와 다른 테마 버튼을 보여주고 그리드 추가는 숨긴다", async () => {
    const onChangeTheme = vi.fn();
    render(
      <ResultView
        themeLabel="흑백"
        view={{ ordered: [], removed: [{ photo: photo("0.jpg"), score: 0.1 }], skipped: [] }}
        {...handlers}
        onChangeTheme={onChangeTheme}
      />,
    );

    expect(screen.getByText("이 테마와 어울리는 사진이 없어요")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "그리드에 추가" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "다른 테마로 해보기" }));
    expect(onChangeTheme).toHaveBeenCalledTimes(1);
  });
});
