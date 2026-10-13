import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { getTheme, THEMES } from "./themes";

// new URL("…", import.meta.url) 형태는 Vite가 자산 주소(http://…/@fs/…)로 바꿔 버려서 경로를 직접 계산한다
const COLLECT_SCRIPT = resolve(dirname(fileURLToPath(import.meta.url)), "../../Ai/collect_unsplash_data.py");

function trainedThemePrompts(): string[] {
  const source = readFileSync(COLLECT_SCRIPT, "utf8");
  const block = source.match(/^THEMES = \[([\s\S]*?)\]/m);
  if (!block) throw new Error("Ai/collect_unsplash_data.py에서 THEMES를 찾지 못함");
  return [...block[1].matchAll(/"([^"]+)"/g)].map((m) => m[1]);
}

describe("THEMES", () => {
  it("영어 문장이 ScoringMLP 학습 테마와 글자 하나까지 같다", () => {
    expect(THEMES.map((t) => t.prompt).sort()).toEqual(trainedThemePrompts().sort());
  });

  it("한글 이름 3개를 가진다", () => {
    expect(THEMES.map((t) => t.label)).toEqual(["흑백", "비비드", "골든아워"]);
  });

  it("getTheme으로 id에 맞는 테마를 찾는다", () => {
    expect(getTheme("golden").prompt).toBe("warm golden hour sunset photography");
  });
});
