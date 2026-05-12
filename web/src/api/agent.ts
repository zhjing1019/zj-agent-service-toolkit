const CHAT_STREAM_URL = "/api/agent/chat/stream";
const CHAT_HISTORY_URL = "/api/agent/chat/history";
const SESSIONS_URL = "/api/agent/sessions";
const UPLOAD_IMAGE_URL = "/api/agent/chat/upload-image";

const API_KEY = (import.meta.env.VITE_API_KEY as string | undefined)?.trim();

function withAuth(headersInit?: HeadersInit): Headers {
  const h = new Headers(headersInit);
  if (API_KEY) {
    h.set("X-API-Key", API_KEY);
  }
  return h;
}

/** 为需鉴权的图片 URL 追加 api_key（与 SSE 一致，便于 <img src>） */
export function withApiKey(url: string): string {
  const k = API_KEY?.trim();
  if (!k) return url;
  const sep = url.includes("?") ? "&" : "?";
  return `${url}${sep}api_key=${encodeURIComponent(k)}`;
}

export type SessionSummary = {
  session_id: string;
  updated_at: string | null;
  msg_count: number;
  preview: string;
};

export async function fetchSessionList(
  limit = 80,
): Promise<SessionSummary[]> {
  const res = await fetch(`${SESSIONS_URL}?limit=${limit}`, {
    headers: withAuth(),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `拉取会话列表失败: ${res.status}`);
  }
  const j = (await res.json()) as { data?: SessionSummary[] };
  return j.data ?? [];
}

export type ChatAttachments = {
  upload_image_ids?: string[];
  referenced_images?: ReferencedImage[];
};

export type ReferencedImage = {
  rel: string;
  score: number;
  caption: string;
  url: string;
};

export type HistoryRow = {
  role: string;
  content: string;
  attachments?: ChatAttachments | null;
};

export async function fetchChatHistory(
  sessionId: string,
): Promise<HistoryRow[]> {
  const q = new URLSearchParams({ session_id: sessionId });
  const res = await fetch(`${CHAT_HISTORY_URL}?${q.toString()}`, {
    headers: withAuth(),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `拉取历史失败: ${res.status}`);
  }
  const j = (await res.json()) as { data?: HistoryRow[] };
  return j.data ?? [];
}

export async function uploadChatImage(file: File): Promise<string> {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(UPLOAD_IMAGE_URL, {
    method: "POST",
    headers: withAuth(),
    body: fd,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `上传图片失败: ${res.status}`);
  }
  const j = (await res.json()) as { data?: { image_id?: string } };
  const id = j.data?.image_id;
  if (!id) throw new Error("上传响应缺少 image_id");
  return id;
}

export type StreamEvent =
  | { event: "session"; session_id: string }
  | { event: "refs"; referenced_images: ReferencedImage[] }
  | { event: "delta"; text: string }
  | { event: "done" }
  | { event: "error"; message: string };

function parseSseBlocks(buffer: string, onLine: (dataJson: string) => void): string {
  const parts = buffer.split("\n\n");
  const rest = parts.pop() ?? "";
  for (const block of parts) {
    const line = block.trim();
    if (line.startsWith("data: ")) {
      onLine(line.slice(6));
    }
  }
  return rest;
}

/** POST + SSE：对话流式输出（与 EventSource 不同，可带 JSON body） */
export async function streamChat(
  task: string,
  sessionId: string | null,
  onEvent: (ev: StreamEvent) => void,
  options?: { signal?: AbortSignal; imageIds?: string[] },
): Promise<void> {
  const image_ids = options?.imageIds?.length ? options.imageIds : undefined;
  const res = await fetch(CHAT_STREAM_URL, {
    method: "POST",
    headers: withAuth({
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    }),
    body: JSON.stringify({
      task: task ?? "",
      session_id: sessionId || null,
      image_ids,
    }),
    signal: options?.signal,
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `请求失败: ${res.status}`);
  }

  const reader = res.body?.getReader();
  if (!reader) {
    throw new Error("无法读取响应流");
  }

  const decoder = new TextDecoder();
  let buf = "";

  const handlePayload = (payload: string) => {
    try {
      const obj = JSON.parse(payload) as Record<string, unknown>;
      const ev = obj.event as string;
      if (ev === "session") {
        onEvent({
          event: "session",
          session_id: String(obj.session_id ?? ""),
        });
      } else if (ev === "refs") {
        const raw = obj.referenced_images;
        const referenced_images = Array.isArray(raw)
          ? (raw as ReferencedImage[])
          : [];
        onEvent({ event: "refs", referenced_images });
      } else if (ev === "delta") {
        onEvent({ event: "delta", text: String(obj.text ?? "") });
      } else if (ev === "done") {
        onEvent({ event: "done" });
      } else if (ev === "error") {
        onEvent({
          event: "error",
          message: String(obj.message ?? "未知错误"),
        });
      }
    } catch {
      /* 忽略损坏行 */
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    buf = parseSseBlocks(buf, handlePayload);
  }
  buf = parseSseBlocks(buf + "\n\n", handlePayload);
}
