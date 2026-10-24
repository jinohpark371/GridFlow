import { describe, expect, it, vi } from "vitest";
import { arrange, ArrangeError, type UploadPhoto } from "./api";

const photos: UploadPhoto[] = [
  { id: "0.jpg", blob: new Blob(["a"], { type: "image/jpeg" }) },
  { id: "1.jpg", blob: new Blob(["b"], { type: "image/jpeg" }) },
];

const okBody = {
  removed_candidates: [{ photo_id: "1.jpg", score: 0.21 }],
  skipped: [{ photo_id: "2.jpg", reason: "용량 초과(5MB 제한)" }],
  groups: [{ order: ["0.jpg"], adjacency_costs: [] }],
};

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

describe("arrange", () => {
  it("테마·사진·group_ids(전부 0)를 멀티파트로 보낸다", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, okBody));

    await arrange("vibrant colorful photography", photos, { fetchImpl, baseUrl: "https://api.test" });

    const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("https://api.test/arrange");
    expect(init.method).toBe("POST");
    const form = init.body as FormData;
    expect(form.get("theme")).toBe("vibrant colorful photography");
    expect(form.getAll("group_ids")).toEqual(["0", "0"]);
    expect(form.getAll("photos").map((file) => (file as File).name)).toEqual(["0.jpg", "1.jpg"]);
  });

  it("정상 응답을 순서·제거 후보·건너뛴 사진으로 바꾼다", async () => {
    const result = await arrange("t", photos, { fetchImpl: async () => jsonResponse(200, okBody) });

    expect(result).toEqual({
      order: ["0.jpg"],
      removed: [{ id: "1.jpg", score: 0.21 }],
      skipped: [{ id: "2.jpg", reason: "용량 초과(5MB 제한)" }],
    });
  });

  it("그룹이 비어 있으면(전부 제거 후보) 순서는 빈 배열", async () => {
    const body = { ...okBody, groups: [] };
    const result = await arrange("t", photos, { fetchImpl: async () => jsonResponse(200, body) });

    expect(result.order).toEqual([]);
  });

  it("연결 실패는 network", async () => {
    const fetchImpl = async () => {
      throw new TypeError("Failed to fetch");
    };

    await expect(arrange("t", photos, { fetchImpl })).rejects.toMatchObject({ kind: "network" });
  });

  it("제한 시간을 넘기면 timeout", async () => {
    const hang: typeof fetch = (_url, init) =>
      new Promise((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
      });

    await expect(arrange("t", photos, { fetchImpl: hang, timeoutMs: 10 })).rejects.toMatchObject({ kind: "timeout" });
  });

  it("504는 timeout", async () => {
    await expect(arrange("t", photos, { fetchImpl: async () => new Response("", { status: 504 }) })).rejects.toMatchObject({
      kind: "timeout",
    });
  });

  it("400은 bad_request이고 서버의 detail 문구를 메시지로 쓴다", async () => {
    const fetchImpl = async () => jsonResponse(400, { detail: "사진은 최대 20장까지 보낼 수 있음" });

    await expect(arrange("t", photos, { fetchImpl })).rejects.toMatchObject({
      kind: "bad_request",
      message: "사진은 최대 20장까지 보낼 수 있음",
    });
  });

  it("500은 server", async () => {
    await expect(arrange("t", photos, { fetchImpl: async () => new Response("", { status: 500 }) })).rejects.toBeInstanceOf(
      ArrangeError,
    );
    await expect(arrange("t", photos, { fetchImpl: async () => new Response("", { status: 500 }) })).rejects.toMatchObject({
      kind: "server",
    });
  });

  it("바깥에서 취소하면 ArrangeError가 아니라 AbortError를 그대로 던진다", async () => {
    const controller = new AbortController();
    const hang: typeof fetch = (_url, init) =>
      new Promise((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
      });

    const pending = arrange("t", photos, { fetchImpl: hang, signal: controller.signal });
    controller.abort();

    await expect(pending).rejects.toMatchObject({ name: "AbortError" });
  });
});
