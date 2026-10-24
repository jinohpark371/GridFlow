import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { MAX_PHOTOS } from "./limits";

// new URL("…", import.meta.url) 형태는 Vite가 자산 주소(http://…/@fs/…)로 바꿔 버려서 경로를 직접 계산한다
const BACKEND_MAIN = resolve(dirname(fileURLToPath(import.meta.url)), "../../Backend/main.py");

describe("MAX_PHOTOS", () => {
  it("백엔드 Backend/main.py의 MAX_PHOTOS와 같다", () => {
    const source = readFileSync(BACKEND_MAIN, "utf8");
    const match = source.match(/^MAX_PHOTOS = (\d+)/m);

    expect(match).not.toBeNull();
    expect(MAX_PHOTOS).toBe(Number(match![1]));
  });
});
