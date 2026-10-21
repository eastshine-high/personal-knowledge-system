// --- 서재 -------------------------------------------------------------------

export interface PdfFile {
  id: string;
  book_id: string;
  label: string;
  pdf_path: string;
  created_at: string;
}

export interface Book {
  id: string;
  title: string;
  created_at: string;
  pdf_files: PdfFile[];
}

// --- 자유 대화 ---------------------------------------------------------------

export interface LLMUsage {
  model: string;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number | null;
}

export interface ExtractionStats {
  page_count: number;
  elapsed_s: number;
  backend: string;
  cost_usd: number | null;
}

export interface Conversation {
  id: string;
  book_id: string;
  pdf_file_id: string;
  pages: number[];
  pages_display: string;
  title: string | null;
  topic: string | null;
  created_at: string;
  extraction_stats?: ExtractionStats | null;
}

export interface Extraction {
  id: string;
  pdf_file_id: string;
  topic: string;
  pages: number[];
  pages_display: string;
  created_at: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface ChatResponse {
  conversation: Conversation;
  message: Message;
  usage?: LLMUsage | null;
}

// --- 노트 -------------------------------------------------------------------

export interface FigureResponse {
  embed_name: string;
  caption: string;
}

export interface NoteResponse {
  id: string;
  title: string;
  source: string;
  pages: number[];
  topic: string;
  created: string;
  body: string;
  tags: string[];
  figures: FigureResponse[];
  markdown: string;
}

export interface EventResponse {
  seq: number;
  author: string;
  action: string;
  content: string;
}

export interface SessionResponse {
  session_id: string;
  notes: NoteResponse[];
  events: EventResponse[];
}
