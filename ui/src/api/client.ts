import type { ChatMessage, DbContextResult } from "../types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed (${response.status})`);
  }

  return response.json() as Promise<T>;
}

export async function sendChat(messages: ChatMessage[]): Promise<string> {
  const payload = {
    messages: messages.map((message) => ({
      role: message.role,
      content: message.content,
    })),
  };

  const data = await request<{ content: string }>("/api/chat", {
    method: "POST",
    body: JSON.stringify(payload),
  });

  return data.content;
}

export async function fetchDbContext(): Promise<DbContextResult> {
  return request<DbContextResult>("/api/db-context");
}

export async function reloadDbContext(): Promise<DbContextResult> {
  return request<DbContextResult>("/api/db-context/reload", { method: "POST" });
}
