import { describe, expect, it } from "vitest";
import { fitWithin, RESIZE_LONG_SIDE } from "./resize";

describe("fitWithin", () => {
  it("가로가 긴 사진은 가로를 512로 맞추고 비율을 유지한다", () => {
    expect(fitWithin(4032, 3024, RESIZE_LONG_SIDE)).toEqual({ width: 512, height: 384 });
  });

  it("세로가 긴 사진은 세로를 512로 맞춘다", () => {
    expect(fitWithin(3024, 4032, RESIZE_LONG_SIDE)).toEqual({ width: 384, height: 512 });
  });

  it("이미 작은 사진은 키우지 않는다", () => {
    expect(fitWithin(300, 200, RESIZE_LONG_SIDE)).toEqual({ width: 300, height: 200 });
  });

  it("아주 가는 사진도 최소 1px은 남긴다", () => {
    expect(fitWithin(10000, 5, RESIZE_LONG_SIDE)).toEqual({ width: 512, height: 1 });
  });
});
