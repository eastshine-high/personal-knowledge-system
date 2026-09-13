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
