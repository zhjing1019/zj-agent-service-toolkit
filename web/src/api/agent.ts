const CHAT_URL = "/api/agent/chat";

export type ChatResponse = {
  code: number;
  session_id: string;
  data: string;
};

export async function sendChatMessage(
  task: string,
  sessionId: string | null,
): Promise<ChatResponse> {
  const res = await fetch(CHAT_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      task,
      session_id: sessionId || null,
    }),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `请求失败: ${res.status}`);
  }

  return res.json() as Promise<ChatResponse>;
}
