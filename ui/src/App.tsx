import { FormEvent, useCallback, useEffect, useRef, useState } from "react";

import { fetchDbContext, reloadDbContext, sendChat } from "./api/client";
import { useChatHistory } from "./hooks/useChatHistory";
import type { ChatMessage, DbContextResult } from "./types";

function createMessage(role: ChatMessage["role"], content: string): ChatMessage {
  return {
    id: crypto.randomUUID(),
    role,
    content,
    createdAt: new Date().toISOString(),
  };
}

export default function App() {
  const { messages, appendMessage, clearHistory } = useChatHistory();
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dbContext, setDbContext] = useState<DbContextResult | null>(null);
  const [isDbLoading, setIsDbLoading] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = useCallback(() => {
    const list = listRef.current;
    if (list) {
      list.scrollTop = list.scrollHeight;
    }
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  const loadDbContext = useCallback(async (reload = false) => {
    setIsDbLoading(true);
    setError(null);
    try {
      const result = reload ? await reloadDbContext() : await fetchDbContext();
      setDbContext(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load database context.");
    } finally {
      setIsDbLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadDbContext();
  }, [loadDbContext]);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || isSending) return;

    const userMessage = createMessage("user", trimmed);
    const nextMessages = [...messages, userMessage];

    setInput("");
    setError(null);
    setIsSending(true);
    appendMessage(userMessage);

    try {
      const reply = await sendChat(nextMessages);
      appendMessage(createMessage("assistant", reply));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send message.");
    } finally {
      setIsSending(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void handleSubmit(event);
    }
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>RA-Agent Chat</h1>
        <div className="header-actions">
          <button type="button" onClick={() => void loadDbContext(true)} disabled={isDbLoading}>
            {isDbLoading ? "Checking DB…" : "Test DB connection"}
          </button>
          <button type="button" onClick={clearHistory} disabled={messages.length === 0}>
            Clear history
          </button>
        </div>
      </header>

      <details className="db-panel" open={dbContext !== null && !dbContext.available}>
        <summary>
          Database connection
          {dbContext && (
            <span className={`db-status ${dbContext.available ? "available" : "unavailable"}`}>
              ● {dbContext.status}
            </span>
          )}
        </summary>
        {dbContext?.message && (
          <p className="db-status-detail">{dbContext.message}</p>
        )}
        {dbContext && <pre className="db-context-pre">{dbContext.context}</pre>}
      </details>

      <main className="chat-main">
        <div className="message-list" ref={listRef} role="log" aria-live="polite">
          {messages.length === 0 ? (
            <p className="empty-state">
              Ask RA-Agent-001 anything. Chat history is saved in this browser only.
            </p>
          ) : (
            messages.map((message) => (
              <article key={message.id} className={`message ${message.role}`}>
                {message.content}
              </article>
            ))
          )}
        </div>

        {error && <div className="error-banner">{error}</div>}

        <form className="composer" onSubmit={handleSubmit}>
          <textarea
            ref={inputRef}
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a message…"
            rows={2}
            disabled={isSending}
            aria-label="Message"
          />
          <button type="submit" className="primary" disabled={isSending || !input.trim()}>
            {isSending ? "Sending…" : "Send"}
          </button>
        </form>
      </main>
    </div>
  );
}
