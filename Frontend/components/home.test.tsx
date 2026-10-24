import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { Post } from "@/lib/state";
import { FeedGrid } from "./FeedGrid";
import { IntroModal } from "./IntroModal";
import { PostSheet } from "./PostSheet";

function post(id: string, count: number): Post {
  return {
    id,
    themeId: "golden",
    photos: Array.from({ length: count }, (_, i) => ({ id: `${i}.jpg`, blob: new Blob(), url: `blob:${id}-${i}` })),
  };
}

describe("FeedGrid", () => {
  it("게시물이 없으면 빈 상태 안내를 보여준다", () => {
    render(<FeedGrid posts={[]} onOpenPost={vi.fn()} onNewPost={vi.fn()} onShowIntro={vi.fn()} />);

    expect(screen.getByText("아직 게시물이 없어요")).toBeInTheDocument();
  });

  it("게시물마다 칸 하나, 대표 사진은 첫 번째 사진, 2장 이상이면 캐러셀 표시", async () => {
    const onOpenPost = vi.fn();
    const { container } = render(
      <FeedGrid posts={[post("post-1", 3), post("post-0", 1)]} onOpenPost={onOpenPost} onNewPost={vi.fn()} onShowIntro={vi.fn()} />,
    );

    const tiles = screen.getAllByRole("button", { name: /게시물 열기/ });
    expect(tiles).toHaveLength(2);
    expect(tiles[0].querySelector("img")).toHaveAttribute("src", "blob:post-1-0");
    expect(container.querySelectorAll("[data-carousel]")).toHaveLength(1);

    await userEvent.click(tiles[0]);
    expect(onOpenPost).toHaveBeenCalledWith("post-1");
  });
});

describe("PostSheet", () => {
  it("삭제는 한 번 더 확인한 뒤에만 실행한다", async () => {
    const onDelete = vi.fn();
    render(<PostSheet post={post("post-0", 2)} onClose={vi.fn()} onDelete={onDelete} />);

    await userEvent.click(screen.getByRole("button", { name: "삭제" }));
    expect(onDelete).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: "삭제할게요" }));
    expect(onDelete).toHaveBeenCalledWith("post-0");
  });

  it("캐러셀 순서를 번호와 함께 보여준다", () => {
    render(<PostSheet post={post("post-0", 2)} onClose={vi.fn()} onDelete={vi.fn()} />);

    const order = screen.getByRole("list", { name: "캐러셀 순서" });
    expect([...order.querySelectorAll("img")].map((img) => img.getAttribute("data-photo-id"))).toEqual(["0.jpg", "1.jpg"]);
  });
});

describe("IntroModal", () => {
  it("슬라이드 3장을 넘긴 뒤 시작하기로 닫는다", async () => {
    const onClose = vi.fn();
    render(<IntroModal onClose={onClose} />);

    expect(screen.getByRole("heading", { name: "사진을 고르면" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "다음" }));
    await userEvent.click(screen.getByRole("button", { name: "다음" }));
    await userEvent.click(screen.getByRole("button", { name: "시작하기" }));

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("건너뛰기로 바로 닫을 수 있다", async () => {
    const onClose = vi.fn();
    render(<IntroModal onClose={onClose} />);

    await userEvent.click(screen.getByRole("button", { name: "건너뛰기" }));

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
