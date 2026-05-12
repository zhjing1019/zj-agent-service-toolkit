import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import {
  fetchChatHistory,
  fetchSessionList,
  streamChat,
  uploadChatImage,
  withApiKey,
  type HistoryRow,
  type ReferencedImage,
  type SessionSummary,
} from "./api/agent";
import styles from "./App.module.css";

const SESSION_STORAGE_KEY = "zj-agent-session-id";

type Msg = {
  role: "user" | "agent";
  text: string;
  uploadImageIds?: string[];
  referencedImages?: ReferencedImage[];
};

function rowsToMessages(rows: HistoryRow[]): Msg[] {
  return rows.map((r) => ({
    role: r.role === "user" ? "user" : "agent",
    text: r.content ?? "",
    uploadImageIds: r.attachments?.upload_image_ids,
    referencedImages: r.attachments?.referenced_images,
  }));
}

function chatUploadImgSrc(imageId: string): string {
  const q = new URLSearchParams({ image_id: imageId });
  return withApiKey(`/api/agent/chat-upload?${q.toString()}`);
}

function formatSessionTime(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function App() {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingSession, setLoadingSession] = useState(false);
  const [hydrating, setHydrating] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const sidLabel = useMemo(
    () => sessionId ?? "（新对话在首次发送后创建）",
    [sessionId],
  );

  const refreshSessions = useCallback(async () => {
    try {
      const list = await fetchSessionList();
      setSessions(list);
    } catch {
      setSessions([]);
    }
  }, []);

  useEffect(() => {
    let cancel = false;
    (async () => {
      try {
        const list = await fetchSessionList();
        if (cancel) return;
        setSessions(list);
        const saved = sessionStorage.getItem(SESSION_STORAGE_KEY);
        if (saved) {
          setSessionId(saved);
          const rows = await fetchChatHistory(saved);
          if (cancel) return;
          setMessages(rowsToMessages(rows));
        }
      } catch {
        if (!cancel) {
          setSessions([]);
        }
      } finally {
        if (!cancel) setHydrating(false);
      }
    })();
    return () => {
      cancel = true;
    };
  }, []);

  const scrollToBottom = useCallback(() => {
    requestAnimationFrame(() => {
      const el = listRef.current;
      if (el) el.scrollTop = el.scrollHeight;
    });
  }, []);

  const startNewChat = useCallback(() => {
    if (loading || loadingSession) return;
    sessionStorage.removeItem(SESSION_STORAGE_KEY);
    setSessionId(null);
    setMessages([]);
    setError(null);
    setInput("");
    setPendingFiles([]);
  }, [loading, loadingSession]);

  const openSession = useCallback(
    async (id: string) => {
      if (loading || id === sessionId) return;
      setLoadingSession(true);
      setError(null);
      try {
        const rows = await fetchChatHistory(id);
        setSessionId(id);
        sessionStorage.setItem(SESSION_STORAGE_KEY, id);
        setMessages(rowsToMessages(rows));
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        setError(msg);
      } finally {
        setLoadingSession(false);
        scrollToBottom();
      }
    },
    [loading, sessionId, scrollToBottom],
  );

  const onPickFiles = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []).filter((f) =>
      f.type.startsWith("image/"),
    );
    if (!files.length) return;
    setPendingFiles((prev) => [...prev, ...files].slice(0, 4));
    e.target.value = "";
  };

  const removePending = (idx: number) => {
    setPendingFiles((prev) => prev.filter((_, i) => i !== idx));
  };

  const onSend = useCallback(async () => {
    const task = input.trim();
    const files = [...pendingFiles];
    if ((!task && !files.length) || loading || loadingSession) return;

    setError(null);
    setInput("");
    setPendingFiles([]);
    setLoading(true);
    scrollToBottom();

    let imageIds: string[] = [];
    try {
      for (const f of files) {
        imageIds.push(await uploadChatImage(f));
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      setLoading(false);
      setPendingFiles(files);
      if (task) setInput(task);
      return;
    }

    const userText = task || (imageIds.length ? "（仅附图）" : "");
    setMessages((m) => [
      ...m,
      {
        role: "user",
        text: userText,
        uploadImageIds: imageIds.length ? imageIds : undefined,
      },
      { role: "agent", text: "" },
    ]);
    scrollToBottom();

    try {
      await streamChat(task, sessionId, (ev) => {
        if (ev.event === "session") {
          setSessionId(ev.session_id);
          sessionStorage.setItem(SESSION_STORAGE_KEY, ev.session_id);
        }
        if (ev.event === "refs") {
          setMessages((m) => {
            const next = [...m];
            const last = next[next.length - 1];
            if (last?.role === "agent") {
              next[next.length - 1] = {
                role: "agent",
                text: last.text,
                referencedImages: ev.referenced_images,
              };
            }
            return next;
          });
          scrollToBottom();
        }
        if (ev.event === "delta") {
          setMessages((m) => {
            const next = [...m];
            const last = next[next.length - 1];
            if (last?.role === "agent") {
              next[next.length - 1] = {
                role: "agent",
                text: last.text + ev.text,
                referencedImages: last.referencedImages,
              };
            }
            return next;
          });
          scrollToBottom();
        }
        if (ev.event === "error") {
          setError(ev.message);
        }
      }, { imageIds: imageIds.length ? imageIds : undefined });
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
    } finally {
      setLoading(false);
      scrollToBottom();
      void refreshSessions();
    }
  }, [
    input,
    loading,
    loadingSession,
    pendingFiles,
    sessionId,
    scrollToBottom,
    refreshSessions,
  ]);

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void onSend();
    }
  };

  const busy = loading || loadingSession;
  const canSend =
    !busy && !hydrating && (!!input.trim() || pendingFiles.length > 0);

  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar} aria-label="会话列表">
        <div className={styles.sidebarHeader}>
          <span className={styles.sidebarTitle}>会话</span>
          <div className={styles.sidebarActions}>
            <button
              type="button"
              className={styles.btnMini}
              disabled={busy}
              onClick={() => void refreshSessions()}
              title="刷新列表"
            >
              刷新
            </button>
            <button
              type="button"
              className={styles.btnMiniPrimary}
              disabled={busy}
              onClick={startNewChat}
            >
              新对话
            </button>
          </div>
        </div>
        <div className={styles.sessionList}>
          {hydrating && (
            <p className={styles.sidebarHint}>加载中…</p>
          )}
          {!hydrating && sessions.length === 0 && (
            <p className={styles.sidebarHint}>暂无会话，开始新对话后会出现。</p>
          )}
          {sessions.map((s) => (
            <button
              key={s.session_id}
              type="button"
              className={
                s.session_id === sessionId
                  ? styles.sessionItemActive
                  : styles.sessionItem
              }
              onClick={() => void openSession(s.session_id)}
              disabled={busy}
            >
              <span className={styles.sessionPreview}>{s.preview}</span>
              <span className={styles.sessionMeta}>
                {formatSessionTime(s.updated_at)} · {s.msg_count} 条
              </span>
              <span className={styles.sessionIdSmall}>{s.session_id}</span>
            </button>
          ))}
        </div>
      </aside>

      <div className={styles.content}>
        <header className={styles.header}>
          <h1 className={styles.title}>多轮对话</h1>
          <p className={styles.meta}>
            当前会话：
            <span className={styles.mono}>{sidLabel}</span>
          </p>
        </header>

        <main className={styles.main}>
          <div ref={listRef} className={styles.messages} role="log">
            {loadingSession && (
              <p className={styles.hint}>正在加载会话…</p>
            )}
            {!hydrating &&
              !loadingSession &&
              messages.length === 0 && (
                <p className={styles.hint}>
                  从左侧选择会话，或输入消息后发送。支持附加图片（CLIP
                  与知识库图片联合检索）。左侧列表实时反映服务端全部会话。
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
                {msg.uploadImageIds && msg.uploadImageIds.length > 0 && (
                  <div className={styles.thumbRow}>
                    {msg.uploadImageIds.map((id) => (
                      <a
                        key={id}
                        href={chatUploadImgSrc(id)}
                        target="_blank"
                        rel="noreferrer"
                        className={styles.thumbLink}
                      >
                        <img
                          className={styles.thumbImg}
                          src={chatUploadImgSrc(id)}
                          alt="上传附图"
                        />
                      </a>
                    ))}
                  </div>
                )}
                {msg.referencedImages && msg.referencedImages.length > 0 && (
                  <div className={styles.refBlock}>
                    <span className={styles.refLabel}>知识库命中图片</span>
                    <div className={styles.thumbRow}>
                      {msg.referencedImages.map((r) => (
                        <a
                          key={r.rel + r.score}
                          href={withApiKey(r.url)}
                          target="_blank"
                          rel="noreferrer"
                          className={styles.thumbLink}
                          title={r.caption || r.rel}
                        >
                          <img
                            className={styles.thumbImg}
                            src={withApiKey(r.url)}
                            alt={r.rel}
                          />
                        </a>
                      ))}
                    </div>
                  </div>
                )}
                <pre className={styles.text}>
                  {msg.text ||
                    (loading && i === messages.length - 1 ? "…" : "")}
                </pre>
              </div>
            ))}
          </div>

          {error && <div className={styles.error}>{error}</div>}

          <div className={styles.composer}>
            <div className={styles.composerMain}>
              {pendingFiles.length > 0 && (
                <div className={styles.pendingRow}>
                  {pendingFiles.map((f, idx) => (
                    <div key={`${f.name}-${idx}`} className={styles.pendingChip}>
                      <span className={styles.pendingName}>{f.name}</span>
                      <button
                        type="button"
                        className={styles.pendingRemove}
                        onClick={() => removePending(idx)}
                        aria-label="移除"
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>
              )}
              <textarea
                className={styles.input}
                rows={3}
                placeholder="输入问题，Enter 发送；可点「附图」选图（与文字一起参与检索）"
                value={input}
                disabled={busy || hydrating}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={onKeyDown}
              />
            </div>
            <div className={styles.composerActions}>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp,image/gif"
                multiple
                className={styles.fileInputHidden}
                onChange={onPickFiles}
              />
              <button
                type="button"
                className={styles.attachBtn}
                disabled={busy || hydrating}
                onClick={() => fileInputRef.current?.click()}
                title="附加图片"
              >
                附图
              </button>
              <button
                type="button"
                className={styles.send}
                disabled={!canSend}
                onClick={() => void onSend()}
              >
                发送
              </button>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
