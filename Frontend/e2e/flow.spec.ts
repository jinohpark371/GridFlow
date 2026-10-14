import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

const SAMPLES = path.resolve(__dirname, "../../samples");
const sample = (name: string) => path.join(SAMPLES, name);

const okResponse = {
  removed_candidates: [{ photo_id: "2.jpg", score: 0.21 }],
  skipped: [],
  groups: [{ order: ["1.jpg", "0.jpg"], adjacency_costs: [["1.jpg", "0.jpg", 0.1]] }],
};

async function dismissIntro(page: Page) {
  await page.getByRole("button", { name: "다음" }).click();
  await page.getByRole("button", { name: "다음" }).click();
  await page.getByRole("button", { name: "시작하기" }).click();
}

async function pickThreePhotos(page: Page) {
  await page.getByRole("button", { name: "+ 새 게시물" }).click();
  await page.getByRole("button", { name: /골든아워/ }).click();
  await page.locator('input[type="file"]').setInputFiles([sample("photo1.JPG"), sample("photo2.JPG"), sample("photo10.JPG")]);
  await expect(page.getByText("3 / 20")).toBeVisible();
}

test("게시물 하나를 만들어 그리드에 쌓고 지운다", async ({ page }) => {
  await page.route("**/arrange", (route) => route.fulfill({ json: okResponse }));
  await page.goto("/");
  await dismissIntro(page);

  await pickThreePhotos(page);

  // 4032x3024 원본이 512px 이하로 줄었는지 — 썸네일은 리사이즈한 Blob으로 그린다
  const sizes = await page
    .getByRole("list", { name: "고른 사진" })
    .locator("img")
    .evaluateAll((imgs) => imgs.map((img) => Math.max((img as HTMLImageElement).naturalWidth, (img as HTMLImageElement).naturalHeight)));
  expect(sizes).toHaveLength(3);
  for (const size of sizes) expect(size).toBeLessThanOrEqual(512);

  await page.getByRole("button", { name: "분석하기" }).click();

  const order = page.getByRole("list", { name: "추천 캐러셀 순서" }).locator("img");
  await expect(order).toHaveCount(2);
  expect(await order.evaluateAll((imgs) => imgs.map((img) => img.getAttribute("data-photo-id")))).toEqual(["1.jpg", "0.jpg"]);
  await expect(page.getByRole("list", { name: "빼는 걸 추천하는 사진" })).toContainText("점수 0.21");

  await page.getByRole("button", { name: "그리드에 추가" }).click();
  const tiles = page.getByRole("button", { name: /게시물 열기/ });
  await expect(tiles).toHaveCount(1);

  await tiles.first().click();
  await page.getByRole("button", { name: "삭제", exact: true }).click();
  await page.getByRole("button", { name: "삭제할게요" }).click();
  await expect(page.getByText("아직 게시물이 없어요")).toBeVisible();
});

test("소개 모달은 처음 방문 때만 뜨고 ?로 다시 볼 수 있다", async ({ page }) => {
  await page.goto("/");
  await dismissIntro(page);
  await page.reload();

  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByRole("button", { name: "사용법 보기" }).click();
  await expect(page.getByRole("heading", { name: "사진을 고르면" })).toBeVisible();
});

test("휴대폰 뒤로가기는 앱 안에서 이전 단계로 간다", async ({ page }) => {
  await page.goto("/");
  await dismissIntro(page);
  await pickThreePhotos(page);

  await page.goBack();
  await expect(page.getByRole("heading", { name: "테마 고르기" })).toBeVisible();
  await page.goBack();
  await expect(page.getByText("아직 게시물이 없어요")).toBeVisible();
});

test("분석 중 뒤로가기는 요청을 취소하고 사진 고르기로 돌아간다", async ({ page }) => {
  await page.route("**/arrange", () => {
    // 응답하지 않아 분석 중 상태로 둔다
  });
  await page.goto("/");
  await dismissIntro(page);
  await pickThreePhotos(page);
  await page.getByRole("button", { name: "분석하기" }).click();
  await expect(page.getByText("사진을 분석하고 있어요")).toBeVisible();

  await page.goBack();

  await expect(page.getByText("3 / 20")).toBeVisible();
});

test("서버 오류 후 다시 시도하면 결과가 나온다", async ({ page }) => {
  let calls = 0;
  await page.route("**/arrange", (route) => {
    calls += 1;
    return calls === 1 ? route.fulfill({ status: 500, body: "" }) : route.fulfill({ json: okResponse });
  });
  await page.goto("/");
  await dismissIntro(page);
  await pickThreePhotos(page);
  await page.getByRole("button", { name: "분석하기" }).click();

  // Next.js가 화면 낭독기용 경로 안내(__next-route-announcer__)를 role="alert"로 넣어 두므로 우리 문구로 좁힌다
  await expect(page.getByRole("alert").filter({ hasText: "잠시 문제가 생겼어요" })).toBeVisible();
  await page.getByRole("button", { name: "다시 시도" }).click();

  await expect(page.getByRole("list", { name: "추천 캐러셀 순서" })).toBeVisible();
});
