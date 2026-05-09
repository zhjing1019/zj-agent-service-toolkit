import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import { fetchChatHistory, streamChat } from "./api/agent";
import styles from "./App.module.css";

const SESSION_STORAGE_KEY = "zj-agent-session-id";

type Msg = { role: "user" | "agent"; text: string };

function rowsToMessages(
  rows: { role: string; content: string }[],
): Msg[] {
  return rows.map((r) => ({
    role: r.role === "user" ? "user" : "agent",
    text: r.content ?? "",
  }));
}

export default function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Msg[]>([]);
  const [loading, setLoading] = useState(false);
  const [hydrating, setHydrating] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const sidLabel = useMemo(
    () => sessionId ?? "（首轮发送后分配，可刷新页面保留）",
    [sessionId],
  );

  useEffect(() => {
    const saved = sessionStorage.getItem(SESSION_STORAGE_KEY);
    if (!saved) {
      setHydrating(false);
      return;
    }
    setSessionId(saved);
    fetchChatHistory(saved)
      .then((rows) => {
        setMessages(rowsToMessages(rows));
      })
      .catch(() => {
        sessionStorage.removeItem(SESSION_STORAGE_KEY);
        setSessionId(null);
      })
      .finally(() => setHydrating(false));
  }, []);

  const scrollToBottom = useCallback(() => {
    requestAnimationFrame(() => {
      const el = listRef.current;
      if (el) el.scrollTop = el.scrollHeight;
    });
  }, []);

  const startNewChat = useCallback(() => {
    if (loading) return;
    sessionStorage.removeItem(SESSION_STORAGE_KEY);
    setSessionId(null);
    setMessages([]);
    setError(null);
    setInput("");
  }, [loading]);

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
          sessionStorage.setItem(SESSION_STORAGE_KEY, ev.session_id);
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
        <div className={styles.headerRow}>
          <div>
            <h1 className={styles.title}>多轮对话</h1>
            <p className={styles.meta}>
              会话 ID：
              <span className={styles.mono}>{sidLabel}</span>
            </p>
          </div>
          <button
            type="button"
            className={styles.btnGhost}
            disabled={loading}
            onClick={startNewChat}
          >
            新对话
          </button>
        </div>
      </header>

      <main className={styles.main}>
        <div ref={listRef} className={styles.messages} role="log">
          {hydrating && (
            <p className={styles.hint}>正在恢复会话…</p>
          )}
          {!hydrating && messages.length === 0 && (
            <p className={styles.hint}>
              同一浏览器标签内会自动记住会话；可多轮追问。汇总阶段为 SSE
              流式输出。
            </p>
          )}
          {messages.map((msg, i) => (
            <div
              key={`${sessionId ?? "new"}-${i}-${msg.role}`}
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
            disabled={loading || hydrating}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
          />
          <button
            type="button"
            className={styles.send}
            disabled={loading || hydrating || !input.trim()}
            onClick={() => void onSend()}
          >
            发送
          </button>
        </div>
      </main>
    </div>
  );
}
