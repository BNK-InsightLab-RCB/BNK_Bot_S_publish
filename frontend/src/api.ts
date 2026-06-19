export type UserRole = "branch" | "it" | "admin";

export type RoleCode = "01" | "02" | "03";

export interface AuthUser {
  id: string;
  real_name: string;
  employee_id: string;
  role: UserRole;
  role_code: RoleCode;
  role_label: string;
}

export interface SourceCitation {
  doc_id: string;
  title: string;
  business_name?: string;
  screen_id?: string;
  screen_name?: string;
  source_path?: string;
  line_range: string;
  reason: string;
  api_path?: string | null;
  http_method?: string | null;
  api_description?: string | null;
  class_name?: string | null;
  method_name?: string | null;
  sql_id?: string | null;
  tables?: string[];
  columns?: string[];
  dto_names?: string[];
  dto_fields?: string[];
  input_fields?: string[];
  validation_conditions?: string[];
  exception_types?: string[];
  auth_codes?: string[];
  call_chain?: string[];
  error_codes?: string[];
  error_messages?: string[];
  retrieval_backend?: string | null;
}

export interface ChatResponse {
  answer: string;
  branch_guide: {
    possible_causes?: string[];
    checklist?: string[];
    it_contact_summary?: string;
  };
  it_summary: Record<string, unknown>;
  confidence: number;
  sources: SourceCitation[];
  metadata?: Record<string, unknown>;
}

export interface HealthResponse {
  status: string;
  index_name: string;
  rag_provider: string;
  azure_search_configured?: boolean;
  foundry_configured?: boolean;
  foundry_search_tool_configured?: boolean;
  ms_route?: string;
}

export interface RuntimeLog {
  id: string;
  timestamp: string;
  kind: "chat" | "ticket" | "storage" | "ingest";
  user_role: UserRole | "unknown";
  question_preview: string;
  rag_provider: string;
  answer_backend: string;
  retrieval_backend: string;
  confidence: number;
  source_count: number;
  duration_ms?: number;
  answer_preview?: string;
  source_titles?: string[];
  status: string;
}

export interface SupportTicket {
  id: string;
  timestamp: string;
  updated_at?: string;
  status: string;
  priority: string;
  screen_name: string;
  sender_name: string;
  sender_employee_id: string;
  sender_role: UserRole;
  sender_role_code: RoleCode;
  recipient_name?: string;
  recipient_employee_id?: string;
  recipient_role?: UserRole;
  recipient_role_code?: RoleCode;
  question: string;
  summary: string;
  answer_backend: string;
  rag_provider: string;
  retrieval_backend: string;
  confidence: number;
  source_count: number;
  sources: SourceCitation[];
  replies: TicketReply[];
}

export interface TicketReply {
  id: string;
  timestamp: string;
  author_name: string;
  author_employee_id: string;
  author_role: UserRole;
  author_role_code: RoleCode;
  body: string;
}

export interface SearchResult {
  score: number;
  document: SourceCitation;
  summary: string;
  business_rules: string[];
  retrieval_backend: string;
  elastic_score?: number | null;
}

export interface StorageUploadItem {
  file_name: string;
  blob_name: string;
  url: string;
  size: number;
  local_path?: string;
}

export interface StorageUploadResponse {
  status: string;
  container: string;
  uploaded: StorageUploadItem[];
}

export interface AdminKpi {
  name: string;
  value: string;
  description: string;
  target: string;
  verification: string;
}

export interface AdminCountItem {
  label: string;
  count: number;
}

export interface AdminModelEvent {
  id: string;
  timestamp: string;
  role: string;
  question_preview: string;
  answer_preview: string;
  answer_backend: string;
  retrieval_backend: string;
  duration_ms: number;
  source_count: number;
  source_titles: string[];
  agent_trace: string[];
}

export interface AdminStorageEvent {
  id: string;
  timestamp: string;
  files: string[];
  blob_names: string[];
  local_paths: string[];
  bytes: number;
  status: string;
}

export interface AdminDashboard {
  generated_at: string;
  window_log_count: number;
  totals: {
    chat_count: number;
    ticket_count: number;
    open_ticket_count: number;
    cloud_answer_count: number;
    local_answer_count: number;
    storage_upload_count: number;
    storage_uploaded_bytes: number;
    ingest_count: number;
    avg_duration_ms: number;
    avg_source_count: number;
  };
  kpis: AdminKpi[];
  route_counts: AdminCountItem[];
  retrieval_counts: AdminCountItem[];
  role_counts: AdminCountItem[];
  recent_model_events: AdminModelEvent[];
  recent_storage_events: AdminStorageEvent[];
  azure: {
    route: string;
    azure_search_configured: boolean;
    foundry_configured: boolean;
    foundry_search_tool_configured: boolean;
    storage_configured: boolean;
    search_index: string;
    storage_container: string;
    foundry_model: string;
  };
  local: {
    index_name: string;
    local_index_path: string;
    local_index_count: number;
    upload_dir: string;
    llm_model: string;
    llm_chat_enabled: boolean;
  };
  monitoring_notes: string[];
}

export async function signupUser(input: {
  real_name: string;
  employee_id: string;
  password: string;
  role_code: RoleCode;
}): Promise<AuthUser> {
  const response = await apiFetch("/api/auth/signup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, "회원가입에 실패했습니다."));
  }
  const body = (await response.json()) as { user: AuthUser };
  return body.user;
}

export async function loginUser(input: {
  employee_id: string;
  password: string;
}): Promise<AuthUser> {
  const response = await apiFetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, "로그인에 실패했습니다."));
  }
  const body = (await response.json()) as { user: AuthUser };
  return body.user;
}

export async function askQuestion(question: string, userRole: UserRole): Promise<ChatResponse> {
  const response = await apiFetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      user_role: userRole,
      include_sources: true,
    }),
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, "답변 생성에 실패했습니다."));
  }
  return response.json();
}

export async function searchKnowledge(query: string, userRole: UserRole): Promise<SearchResult[]> {
  const response = await apiFetch("/api/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query,
      user_role: userRole,
      top_k: 8,
    }),
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, "검색에 실패했습니다."));
  }
  const body = (await response.json()) as { results: SearchResult[] };
  return body.results;
}

export async function getHealth(): Promise<HealthResponse> {
  const response = await apiFetch("/api/health");
  if (!response.ok) {
    throw new Error(await errorMessage(response, "백엔드 상태 확인에 실패했습니다."));
  }
  return response.json();
}

export async function ingestSample(
  uploadAzureSearch = false,
): Promise<{ status: string; indexed_count: number }> {
  const response = await apiFetch("/api/ingest/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      source_dir: "backend/examples/bank_sample",
      reset_index: true,
      generate_summaries: false,
      upload_azure_search: uploadAzureSearch,
    }),
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, "색인 실행에 실패했습니다."));
  }
  return response.json();
}

export async function uploadFilesToStorage(files: File[]): Promise<StorageUploadResponse> {
  const form = new FormData();
  for (const file of files) {
    form.append("files", file, file.name);
  }
  form.append("prefix", "source-drop");
  form.append("overwrite", "true");
  const response = await apiFetch("/api/storage/upload", {
    method: "POST",
    body: form,
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, "Storage 업로드에 실패했습니다."));
  }
  return response.json();
}

export async function createSupportTicket(input: {
  question: string;
  summary: string;
  screen_name?: string;
  priority?: string;
  sender_name?: string;
  sender_employee_id?: string;
  sender_role?: UserRole;
  sender_role_code?: RoleCode;
  recipient_name?: string;
  recipient_employee_id?: string;
  recipient_role?: UserRole;
  recipient_role_code?: RoleCode;
  answer_backend?: string;
  rag_provider?: string;
  retrieval_backend?: string;
  confidence?: number;
  source_count?: number;
  sources?: SourceCitation[];
}): Promise<SupportTicket> {
  const response = await apiFetch("/api/runtime/tickets", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, "IT 쪽지 생성에 실패했습니다."));
  }
  const body = (await response.json()) as { ticket: SupportTicket };
  return body.ticket;
}

export async function replySupportTicket(
  ticketId: string,
  input: {
    body: string;
    author_name?: string;
    author_employee_id?: string;
    author_role?: UserRole;
    author_role_code?: RoleCode;
  },
): Promise<SupportTicket> {
  const response = await apiFetch(`/api/runtime/tickets/${encodeURIComponent(ticketId)}/replies`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, "쪽지 답장에 실패했습니다."));
  }
  const body = (await response.json()) as { ticket: SupportTicket };
  return body.ticket;
}

export async function getSupportTickets(): Promise<SupportTicket[]> {
  const response = await apiFetch("/api/runtime/tickets");
  if (!response.ok) {
    throw new Error(await errorMessage(response, "IT 쪽지 목록을 불러오지 못했습니다."));
  }
  const body = (await response.json()) as { tickets: SupportTicket[] };
  return body.tickets;
}

export async function getRuntimeLogs(): Promise<RuntimeLog[]> {
  const response = await apiFetch("/api/runtime/logs");
  if (!response.ok) {
    throw new Error(await errorMessage(response, "실행 로그를 불러오지 못했습니다."));
  }
  const body = (await response.json()) as { logs: RuntimeLog[] };
  return body.logs;
}

export async function getAdminDashboard(): Promise<AdminDashboard> {
  const response = await apiFetch("/api/admin/dashboard");
  if (!response.ok) {
    throw new Error(await errorMessage(response, "관리자 대시보드를 불러오지 못했습니다."));
  }
  return response.json();
}

async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(path, init);
  } catch {
    throw new Error(
      "백엔드에 연결할 수 없습니다. 터미널에서 ./scripts/run_chatbot.sh를 실행한 상태로 이 화면을 새로고침하세요.",
    );
  }
}

async function errorMessage(response: Response, fallback: string): Promise<string> {
  const detail = await response.json().catch(() => ({}));
  if (detail && typeof detail.detail === "string") {
    return detail.detail;
  }
  return `${fallback} (${response.status})`;
}
