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
  message?: string | null;
}
