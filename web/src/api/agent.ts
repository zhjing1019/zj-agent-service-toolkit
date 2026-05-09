const CHAT_STREAM_URL = "/api/agent/chat/stream";

export type StreamEvent =
  | { event: "session"; session_id: string }
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
  options?: { signal?: AbortSignal },
): Promise<void> {
  const res = await fetch(CHAT_STREAM_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify({
      task,
      session_id: sessionId || null,
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
