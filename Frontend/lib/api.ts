export type ApiErrorKind = "network" | "timeout" | "bad_request" | "server";

export class ArrangeError extends Error {
  readonly kind: ApiErrorKind;

  constructor(kind: ApiErrorKind, message: string) {
    super(message);
    this.name = "ArrangeError";
    this.kind = kind;
  }
}

export interface UploadPhoto {
  /** 서버가 사진을 구분하는 이름(0.jpg, 1.jpg, …) — 응답의 photo_id로 그대로 돌아온다 */
  id: string;
  blob: Blob;
}

export interface ArrangeResult {
  order: string[];
  removed: { id: string; score: number }[];
  skipped: { id: string; reason: string }[];
}

interface ArrangeResponseBody {
  removed_candidates: { photo_id: string; score: number }[];
  skipped: { photo_id: string; reason: string }[];
  groups: { order: string[]; adjacency_costs: [string, string, number][] }[];
}

export const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");
/** CloudFront 오리진 대기(60초)보다 살짝 길게 — 서버 쪽 504를 먼저 받을 수 있게 */
export const REQUEST_TIMEOUT_MS = 65_000;

export interface ArrangeOptions {
  signal?: AbortSignal;
  timeoutMs?: number;
  fetchImpl?: typeof fetch;
  baseUrl?: string;
}

export async function arrange(themePrompt: string, photos: UploadPhoto[], options: ArrangeOptions = {}): Promise<ArrangeResult> {
  const { signal, timeoutMs = REQUEST_TIMEOUT_MS, fetchImpl = fetch, baseUrl = API_BASE_URL } = options;

  const form = new FormData();
  form.append("theme", themePrompt);
  for (const photo of photos) {
    form.append("photos", photo.blob, photo.id);
    form.append("group_ids", "0"); // 요청 1번 = 게시물 1개
  }

  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  const forwardAbort = () => controller.abort();
  signal?.addEventListener("abort", forwardAbort);

  let response: Response;
  try {
    response = await fetchImpl(`${baseUrl}/arrange`, { method: "POST", body: form, signal: controller.signal });
  } catch (error) {
    if (timedOut) throw new ArrangeError("timeout", "요청 시간이 초과됨");
    if (signal?.aborted) throw error;
    // 브라우저는 CORS 거절도 일반 연결 실패와 똑같이 알려줘서 둘을 구분할 수 없다
    throw new ArrangeError("network", "서버에 연결하지 못함");
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", forwardAbort);
  }

  if (response.ok) return toResult((await response.json()) as ArrangeResponseBody);
  if (response.status === 504) throw new ArrangeError("timeout", "게이트웨이 시간 초과");
  if (response.status >= 400 && response.status < 500) throw new ArrangeError("bad_request", await readDetail(response));
  throw new ArrangeError("server", `서버 오류 (${response.status})`);
}

async function readDetail(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json();
    if (typeof body === "object" && body !== null && typeof (body as { detail?: unknown }).detail === "string") {
      return (body as { detail: string }).detail;
    }
  } catch {
    // 본문이 JSON이 아니면 아래 기본 문구를 쓴다
  }
  return `요청이 거절됨 (${response.status})`;
}

function toResult(body: ArrangeResponseBody): ArrangeResult {
  return {
    order: body.groups[0]?.order ?? [],
    removed: body.removed_candidates.map((c) => ({ id: c.photo_id, score: c.score })),
    skipped: body.skipped.map((s) => ({ id: s.photo_id, reason: s.reason })),
  };
}
