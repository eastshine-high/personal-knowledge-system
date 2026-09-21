import type { Book, ChatResponse, Conversation, Message, NoteResponse, PdfFile, SessionResponse } from "./types";

const BASE = "http://localhost:8000";

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body?.detail ?? res.statusText);
  }
  return res.json() as Promise<T>;
}

export function createSession(params: {
  pdf_path: string;
  page_start: number;
  page_end: number;
  topic: string;
  guideline?: string;
  note_count?: number;
  user_preferred_guideline?: string;
}): Promise<SessionResponse> {
  return request("/sessions", { method: "POST", body: JSON.stringify(params) });
}

export function getNotes(sessionId: string): Promise<NoteResponse[]> {
  return request(`/sessions/${sessionId}/notes`);
}

export function refineSession(
  sessionId: string,
  instruction: string,
  noteId?: string,
): Promise<SessionResponse> {
  return request(`/sessions/${sessionId}/refine`, {
    method: "POST",
    body: JSON.stringify({ instruction, note_id: noteId ?? null }),
  });
}

export function editNote(
  sessionId: string,
  noteId: string,
  body: string,
  title?: string,
): Promise<NoteResponse> {
  return request(`/sessions/${sessionId}/notes/${noteId}/edit`, {
    method: "POST",
    body: JSON.stringify({ body, title: title ?? null }),
  });
}

export function undoSession(sessionId: string): Promise<SessionResponse> {
  return request(`/sessions/${sessionId}/undo`, { method: "POST" });
}

/** <img src={pageImageUrl(...)} /> 방식으로 사용 — fetch 불필요. */
export function pageImageUrl(sessionId: string, pageNum: number): string {
  return `${BASE}/sessions/${sessionId}/pages/${pageNum}`;
}

/** <a href={exportUrl(...)} download> 방식으로 사용 — fetch 불필요. */
export function exportUrl(sessionId: string): string {
  return `${BASE}/sessions/${sessionId}/export`;
}

/** <img src={figureUrl(...)} /> 방식으로 사용 — fetch 불필요. */
export function figureUrl(sessionId: string, embedName: string): string {
  return `${BASE}/sessions/${sessionId}/figures/${embedName}`;
}

// --- 서재 -------------------------------------------------------------------

export function getBooks(): Promise<Book[]> {
  return request("/books");
}

export function createBook(title: string): Promise<Book> {
  return request("/books", { method: "POST", body: JSON.stringify({ title }) });
}

export function addPdf(bookId: string, label: string, pdf_path: string): Promise<PdfFile> {
  return request(`/books/${bookId}/pdfs`, {
    method: "POST",
    body: JSON.stringify({ label, pdf_path }),
  });
}

export function deletePdf(bookId: string, pdfId: string): Promise<void> {
  return request(`/books/${bookId}/pdfs/${pdfId}`, { method: "DELETE" });
}

// --- 자유 대화 ---------------------------------------------------------------

export function getConversations(bookId: string): Promise<Conversation[]> {
  return request(`/books/${bookId}/conversations`);
}

export function createConversation(
  bookId: string,
  pdf_file_id: string,
  pages_str: string,
): Promise<Conversation> {
  return request(`/books/${bookId}/conversations`, {
    method: "POST",
    body: JSON.stringify({ pdf_file_id, pages_str }),
  });
}

export function getMessages(convId: string): Promise<Message[]> {
  return request(`/conversations/${convId}/messages`);
}

export function sendMessage(convId: string, content: string): Promise<ChatResponse> {
  return request(`/conversations/${convId}/messages`, {
    method: "POST",
    body: JSON.stringify({ content }),
  });
}
