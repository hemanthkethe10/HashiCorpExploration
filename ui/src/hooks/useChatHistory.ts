import { useCallback, useEffect, useState } from "react";

import type { ChatMessage } from "../types";

const STORAGE_KEY = "ra-agent-chat-history";

function loadHistory(): ChatMessage[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as ChatMessage[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function saveHistory(messages: ChatMessage[]): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
}

export function useChatHistory() {
  const [messages, setMessages] = useState<ChatMessage[]>(loadHistory);

  useEffect(() => {
    saveHistory(messages);
  }, [messages]);

  const appendMessage = useCallback((message: ChatMessage) => {
    setMessages((current) => [...current, message]);
  }, []);

  const clearHistory = useCallback(() => {
    setMessages([]);
    localStorage.removeItem(STORAGE_KEY);
  }, []);

  return { messages, appendMessage, clearHistory, setMessages };
}
