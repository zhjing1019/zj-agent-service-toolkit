import {
  useCallback,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import { sendChatMessage } from "./api/agent";
import styles from "./App.module.css";

type Msg = { role: "user" | "agent"; text: string };

export default function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Msg[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const sidLabel = useMemo(
    () => sessionId ?? "（首次发送后由服务端分配）",
    [sessionId],
  );

  const scrollToBottom = useCallback(() => {
    requestAnimationFrame(() => {
      const el = listRef.current;
      if (el) el.scrollTop = el.scrollHeight;
    });
  }, []);

  const onSend = useCallback(async () => {
    const task = input.trim();
    if (!task || loading) return;

    setError(null);
    setInput("");
    setMessages((m) => [...m, { role: "user", text: task }]);
    setLoading(true);
    scrollToBottom();

    try {
      const res = await sendChatMessage(task, sessionId);
      setSessionId(res.session_id);
      setMessages((m) => [...m, { role: "agent", text: res.data }]);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
    } finally {
      setLoading(false);
      scrollToBottom();
    }
  }, [input, loading, sessionId, scrollToBottom]);

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void onSend();
    }
  };

  return (
    <div className={styles.layout}>
      <header className={styles.header}>
        <h1 className={styles.title}>Agent 对话</h1>
        <p className={styles.meta}>
          会话 ID：<span className={styles.mono}>{sidLabel}</span>
        </p>
      </header>

      <main className={styles.main}>
        <div ref={listRef} className={styles.messages} role="log">
          {messages.length === 0 && (
            <p className={styles.hint}>
              向智能体提问，支持多轮会话（历史由后端 SQLite 持久化）。
            </p>
          )}
          {messages.map((msg, i) => (
            <div
              key={`${i}-${msg.role}`}
              className={
                msg.role === "user" ? styles.bubbleUser : styles.bubbleAgent
              }
            >
              <span className={styles.role}>
                {msg.role === "user" ? "你" : "Agent"}
              </span>
              <pre className={styles.text}>{msg.text}</pre>
            </div>
          ))}
          {loading && <div className={styles.pending}>思考中…</div>}
        </div>

        {error && <div className={styles.error}>{error}</div>}

        <div className={styles.composer}>
          <textarea
            className={styles.input}
            rows={3}
            placeholder="输入问题，Enter 发送，Shift+Enter 换行"
            value={input}
            disabled={loading}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
          />
          <button
            type="button"
            className={styles.send}
            disabled={loading || !input.trim()}
            onClick={() => void onSend()}
          >
            发送
          </button>
        </div>
      </main>
    </div>
  );
}
