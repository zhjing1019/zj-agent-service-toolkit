import {
  useCallback,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import { streamChat } from "./api/agent";
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
    setMessages((m) => [
      ...m,
      { role: "user", text: task },
      { role: "agent", text: "" },
    ]);
    setLoading(true);
    scrollToBottom();

    try {
      await streamChat(task, sessionId, (ev) => {
        if (ev.event === "session") {
          setSessionId(ev.session_id);
        }
        if (ev.event === "delta") {
          setMessages((m) => {
            const next = [...m];
            const last = next[next.length - 1];
            if (last?.role === "agent") {
              next[next.length - 1] = {
                role: "agent",
                text: last.text + ev.text,
              };
            }
            return next;
          });
          scrollToBottom();
        }
        if (ev.event === "error") {
          setError(ev.message);
        }
      });
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
        <h1 className={styles.title}>Agent 对话（SSE）</h1>
        <p className={styles.meta}>
          会话 ID：<span className={styles.mono}>{sidLabel}</span>
        </p>
      </header>

      <main className={styles.main}>
        <div ref={listRef} className={styles.messages} role="log">
          {messages.length === 0 && (
            <p className={styles.hint}>
              流式输出最终汇总；规划 / 工具 / RAG 阶段仍会在后台完整执行后再开始打字。
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
              <pre className={styles.text}>
                {msg.text || (loading && i === messages.length - 1 ? "…" : "")}
              </pre>
            </div>
          ))}
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
