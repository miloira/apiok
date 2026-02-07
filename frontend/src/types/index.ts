// API Types for API Testing Tool

export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH' | 'HEAD' | 'OPTIONS';
export type BodyType = 'json' | 'form' | 'raw' | null;

export interface Request {
  id: number;
  name: string;
  method: HttpMethod;
  url: string;
  headers: Record<string, string>;
  query_params: Record<string, string>;
  body_type: BodyType;
  body: string | null;
  folder_id: number | null;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface RequestCreate {
  name: string;
  method: HttpMethod;
  url: string;
  headers?: Record<string, string>;
  query_params?: Record<string, string>;
  body_type?: BodyType;
  body?: string;
  folder_id?: number;
}

export interface Folder {
  id: number;
  name: string;
  parent_folder_id: number | null;
  sort_order: number;
  children: Folder[];
  requests: Request[];
  created_at: string;
  updated_at: string;
}

export interface Environment {
  id: number;
  name: string;
  base_url: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  variables: Variable[];
}

export interface Variable {
  id: number;
  environment_id: number;
  key: string;
  value: string;
}

export interface ExecuteResponse {
  status_code: number;
  status_text: string;
  headers: Record<string, string>;
  body: string | null;
  body_json: unknown;
  response_time_ms: number;
  response_size: number;
  warnings: string[];
}

export interface History {
  id: number;
  request_id: number | null;
  method: string;
  url: string;
  request_headers: Record<string, string>;
  request_body: string | null;
  status_code: number;
  status_text: string;
  response_headers: Record<string, string>;
  response_body: string | null;
  response_time_ms: number;
  response_size: number;
  executed_at: string;
}

// Drag and Drop Types

export type DragItemType = 'request' | 'folder';

export interface DragData {
  type: DragItemType;
  id: number;
  folderId?: number | null;
}

export interface DropTarget {
  type: 'gap' | 'folder';
  position?: 'before' | 'after';
  refId?: number;
  refType?: DragItemType;
  targetFolderId?: number;
}
