export type MessageRole = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  createdAt: string;
}

export type DbConnectionStatus = "connected" | "empty" | "unavailable";

export interface DbContextResult {
  context: string;
  status: DbConnectionStatus;
  available: boolean;
  connected: boolean;
  message?: string | null;
  checked_at?: string | null;
}
