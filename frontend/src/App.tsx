import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  ArrowRight,
  Bot,
  Building2,
  Cloud,
  Code2,
  Database,
  LogOut,
  MessageSquarePlus,
  MonitorCog,
  Search,
  Shield,
  Users,
} from "lucide-react";
import {
  askQuestion,
  createSupportTicket,
  getHealth,
  getRuntimeLogs,
  getSupportTickets,
  ingestSample,
  searchKnowledge,
  uploadFilesToStorage,
  type ChatResponse,
  type HealthResponse,
  type RuntimeLog,
  type SearchResult,
  type SupportTicket,
  type UserRole,
} from "./api";
import { AdminPanel } from "./components/AdminPanel";
import { AnswerView } from "./components/AnswerView";
import { ChatPanel } from "./components/ChatPanel";
import { SourceList } from "./components/SourceList";
import "./styles.css";

type SessionUser = {
  role: UserRole;
  name: string;
};

const userProfiles: SessionUser[] = [
  { role: "branch", name: "영업점 행원" },
  { role: "it", name: "IT 직원" },
  { role: "admin", name: "관리자" },
];

const itSamples = [
  "자동이체 등록 화면 오류의 API, 서비스, SQL 근거를 요약해줘.",
  "카드 재발급에서 월 재발급 횟수 초과 오류가 어디서 나는지 확인해줘.",
  "잔액증명서 발급 제한 조건을 코드 근거와 함께 정리해줘.",
];

export default function App() {
  const [session, setSession] = useState<SessionUser | null>(() => {
    const saved = localStorage.getItem("ops-rag-session");
    return saved ? (JSON.parse(saved) as SessionUser) : null;
  });
  const [response, setResponse] = useState<ChatResponse | null>(null);
  const [activeQuestion, setActiveQuestion] = useState("");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [backendOnline, setBackendOnline] = useState(false);
  const [loading, setLoading] = useState(false);
  const [ingesting, setIngesting] = useState(false);
  const [ingestStatus, setIngestStatus] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState("");
  const [ticketStatus, setTicketStatus] = useState("");
  const [logs, setLogs] = useState<RuntimeLog[]>([]);
  const [tickets, setTickets] = useState<SupportTicket[]>([]);
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    refreshHealth();
    refreshRuntime();
  }, []);

  function login(profile: SessionUser) {
    setSession(profile);
    setResponse(null);
    setActiveQuestion("");
    setError("");
    localStorage.setItem("ops-rag-session", JSON.stringify(profile));
  }

  function logout() {
    setSession(null);
    setResponse(null);
    setActiveQuestion("");
    localStorage.removeItem("ops-rag-session");
  }

  async function refreshHealth() {
    try {
      const result = await getHealth();
      setHealth(result);
      setBackendOnline(true);
    } catch (event) {
      setBackendOnline(false);
      setError(event instanceof Error ? event.message : "백엔드 상태 확인에 실패했습니다.");
    }
  }

  async function refreshRuntime() {
    const [nextLogs, nextTickets] = await Promise.all([
      getRuntimeLogs().catch(() => []),
      getSupportTickets().catch(() => []),
    ]);
    setLogs(nextLogs);
    setTickets(nextTickets);
  }

  async function handleAsk(question: string, userRole: UserRole) {
    setLoading(true);
    setError("");
    setTicketStatus("");
    setActiveQuestion(question);
    setResponse(null);
    try {
      const result = await askQuestion(question, userRole);
      setResponse(result);
      setBackendOnline(true);
      await refreshRuntime();
    } catch (event) {
      setError(event instanceof Error ? event.message : "chat failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleIngest() {
    setIngesting(true);
    setError("");
    try {
      const result = await ingestSample();
      setIngestStatus(`${result.status} / ${result.indexed_count} docs`);
      setBackendOnline(true);
      await refreshRuntime();
    } catch (event) {
      setError(event instanceof Error ? event.message : "ingest failed");
    } finally {
      setIngesting(false);
    }
  }

  async function handleStorageUpload(files: File[]) {
    setUploading(true);
    setError("");
    try {
      const result = await uploadFilesToStorage(files);
      const uploadedSize = result.uploaded.reduce((total, item) => total + item.size, 0);
      setUploadStatus(`${result.uploaded.length} files / ${(uploadedSize / 1024).toFixed(1)} KiB`);
      await refreshRuntime();
    } catch (event) {
      setError(event instanceof Error ? event.message : "storage upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function handleTicket() {
    if (!response || !activeQuestion) return;
    setTicketStatus("전송 중");
    const metadata = response.metadata ?? {};
    try {
      const ticket = await createSupportTicket({
        question: activeQuestion,
        summary: response.branch_guide.it_contact_summary || response.answer.slice(0, 240),
        priority: response.confidence < 0.55 ? "high" : "normal",
        answer_backend: String(metadata.answer_backend ?? ""),
        rag_provider: String(metadata.rag_provider ?? ""),
        retrieval_backend: sourceBackends(response).join(", "),
        confidence: response.confidence,
        source_count: response.sources.length,
      });
      setTicketStatus(`${ticket.id} 접수`);
      await refreshRuntime();
    } catch (event) {
      setTicketStatus("");
      setError(event instanceof Error ? event.message : "IT 쪽지 생성에 실패했습니다.");
    }
  }

  async function handleSearch(query: string) {
    if (!query.trim()) return;
    setSearching(true);
    setError("");
    try {
      const result = await searchKnowledge(query.trim(), "it");
      setSearchResults(result);
    } catch (event) {
      setError(event instanceof Error ? event.message : "검색에 실패했습니다.");
    } finally {
      setSearching(false);
    }
  }

  const route = useMemo(() => routeSummary(response, health), [response, health]);

  if (!session) {
    return <LoginView backendOnline={backendOnline} health={health} onLogin={login} />;
  }

  return (
    <main className="app-shell">
      <WorkspaceHeader
        session={session}
        backendOnline={backendOnline}
        health={health}
        response={response}
        onLogout={logout}
      />
      {error && <div className="error-banner app-error">{error}</div>}
      {session.role === "branch" && (
        <BranchWorkspace
          response={response}
          loading={loading}
          activeQuestion={activeQuestion}
          route={route}
          ticketStatus={ticketStatus}
          onAsk={handleAsk}
          onTicket={handleTicket}
        />
      )}
      {session.role === "it" && (
        <ITWorkspace
          response={response}
          loading={loading}
          activeQuestion={activeQuestion}
          tickets={tickets}
          searchResults={searchResults}
          searching={searching}
          onAsk={handleAsk}
          onSearch={handleSearch}
          onRefresh={refreshRuntime}
        />
      )}
      {session.role === "admin" && (
        <AdminWorkspace
          response={response}
          loading={loading}
          activeQuestion={activeQuestion}
          logs={logs}
          tickets={tickets}
          ingesting={ingesting}
          ingestStatus={ingestStatus}
          uploading={uploading}
          uploadStatus={uploadStatus}
          onAsk={handleAsk}
          onIngest={handleIngest}
          onStorageUpload={handleStorageUpload}
          onRefresh={refreshRuntime}
        />
      )}
    </main>
  );
}

function LoginView({
  backendOnline,
  health,
  onLogin,
}: {
  backendOnline: boolean;
  health: HealthResponse | null;
  onLogin: (profile: SessionUser) => void;
}) {
  return (
    <main className="login-shell">
      <section className="login-panel">
        <div>
          <span className="eyebrow">Source-Aware Ops RAG</span>
          <h1>영업점 운영지원</h1>
        </div>
        <div className="login-grid">
          {userProfiles.map((profile) => (
            <button key={profile.role} type="button" onClick={() => onLogin(profile)}>
              {profile.role === "branch" && <Building2 size={24} aria-hidden="true" />}
              {profile.role === "it" && <MonitorCog size={24} aria-hidden="true" />}
              {profile.role === "admin" && <Shield size={24} aria-hidden="true" />}
              <span>{profile.name}</span>
              <ArrowRight size={18} aria-hidden="true" />
            </button>
          ))}
        </div>
        <div className="login-status">
          <StatusPill online={backendOnline} label={backendOnline ? "Backend online" : "Backend offline"} />
          <span>{health?.rag_provider ?? "multi_agent"}</span>
        </div>
      </section>
    </main>
  );
}

function WorkspaceHeader({
  session,
  backendOnline,
  health,
  response,
  onLogout,
}: {
  session: SessionUser;
  backendOnline: boolean;
  health: HealthResponse | null;
  response: ChatResponse | null;
  onLogout: () => void;
}) {
  return (
    <header className="app-header">
      <div>
        <span className="eyebrow">Source-Aware Ops RAG</span>
        <h1>{session.name} 워크스페이스</h1>
      </div>
      <div className="status-cluster" aria-label="서비스 상태">
        <StatusPill online={backendOnline} label={backendOnline ? "Backend online" : "Backend offline"} />
        <span className="status-pill">{health?.rag_provider ?? "multi_agent"}</span>
        <span className="status-pill">{String(response?.metadata?.answer_backend ?? "standby")}</span>
        <button className="icon-button" type="button" onClick={onLogout} title="로그아웃">
          <LogOut size={18} aria-hidden="true" />
        </button>
      </div>
    </header>
  );
}

function BranchWorkspace({
  response,
  loading,
  activeQuestion,
  route,
  ticketStatus,
  onAsk,
  onTicket,
}: {
  response: ChatResponse | null;
  loading: boolean;
  activeQuestion: string;
  route: RouteSummary;
  ticketStatus: string;
  onAsk: (question: string, userRole: UserRole) => Promise<void>;
  onTicket: () => Promise<void>;
}) {
  return (
    <div className="workspace branch-layout">
      <section className="chat-workspace">
        <RoutePanel route={route} />
        <ChatPanel
          loading={loading}
          onAsk={onAsk}
          lastResponse={response}
          userRole="branch"
          title="업무 오류 문의"
          description="화면명, 오류 문구, 입력 상황을 남겨주세요."
        />
        <AnswerView response={response} loading={loading} question={activeQuestion} />
      </section>
      <aside className="ops-rail">
        <BranchGuide response={response} onTicket={onTicket} ticketStatus={ticketStatus} />
      </aside>
    </div>
  );
}

function ITWorkspace({
  response,
  loading,
  activeQuestion,
  tickets,
  searchResults,
  searching,
  onAsk,
  onSearch,
  onRefresh,
}: {
  response: ChatResponse | null;
  loading: boolean;
  activeQuestion: string;
  tickets: SupportTicket[];
  searchResults: SearchResult[];
  searching: boolean;
  onAsk: (question: string, userRole: UserRole) => Promise<void>;
  onSearch: (query: string) => Promise<void>;
  onRefresh: () => Promise<void>;
}) {
  return (
    <div className="workspace it-layout">
      <section className="chat-workspace">
        <ChatPanel
          loading={loading}
          onAsk={onAsk}
          lastResponse={response}
          userRole="it"
          title="장애 원인 분석"
          description="검색 근거와 코드 단서를 함께 확인합니다."
          samples={itSamples}
        />
        <AnswerView response={response} loading={loading} question={activeQuestion} />
        <SourceList sources={response?.sources ?? []} />
      </section>
      <aside className="ops-rail">
        <ITSearchPanel
          response={response}
          searchResults={searchResults}
          searching={searching}
          onSearch={onSearch}
        />
        <TicketList tickets={tickets} onRefresh={onRefresh} />
      </aside>
    </div>
  );
}

function AdminWorkspace({
  response,
  loading,
  activeQuestion,
  logs,
  tickets,
  ingesting,
  ingestStatus,
  uploading,
  uploadStatus,
  onAsk,
  onIngest,
  onStorageUpload,
  onRefresh,
}: {
  response: ChatResponse | null;
  loading: boolean;
  activeQuestion: string;
  logs: RuntimeLog[];
  tickets: SupportTicket[];
  ingesting: boolean;
  ingestStatus: string;
  uploading: boolean;
  uploadStatus: string;
  onAsk: (question: string, userRole: UserRole) => Promise<void>;
  onIngest: () => Promise<void>;
  onStorageUpload: (files: File[]) => Promise<void>;
  onRefresh: () => Promise<void>;
}) {
  return (
    <div className="workspace admin-layout">
      <section className="chat-workspace">
        <AdminPanel
          ingesting={ingesting}
          ingestStatus={ingestStatus}
          onIngest={onIngest}
          uploading={uploading}
          uploadStatus={uploadStatus}
          onStorageUpload={onStorageUpload}
        />
        <LogPanel logs={logs} onRefresh={onRefresh} />
      </section>
      <aside className="ops-rail">
        <ChatPanel
          loading={loading}
          onAsk={onAsk}
          lastResponse={response}
          userRole="admin"
          title="관리자 검증"
          description="색인 상태와 응답 경로를 확인합니다."
          samples={itSamples}
        />
        <AnswerView response={response} loading={loading} question={activeQuestion} />
        <TicketList tickets={tickets} onRefresh={onRefresh} />
      </aside>
    </div>
  );
}

function RoutePanel({ route }: { route: RouteSummary }) {
  return (
    <section className="panel route-panel">
      <div>
        <h2>응답 경로</h2>
        <p>{route.description}</p>
      </div>
      <div className="route-badges">
        <span>
          {route.isCloud ? <Cloud size={16} aria-hidden="true" /> : <Database size={16} aria-hidden="true" />}
          {route.answer}
        </span>
        <span>
          <Search size={16} aria-hidden="true" />
          {route.retrieval}
        </span>
      </div>
    </section>
  );
}

function BranchGuide({
  response,
  ticketStatus,
  onTicket,
}: {
  response: ChatResponse | null;
  ticketStatus: string;
  onTicket: () => Promise<void>;
}) {
  const checklist = response?.branch_guide.checklist ?? [];
  return (
    <section className="panel branch-guide-panel">
      <div className="panel-title">
        <Bot size={19} aria-hidden="true" />
        <h2>가이드</h2>
      </div>
      {checklist.length === 0 ? (
        <p>답변 후 확인 항목이 표시됩니다.</p>
      ) : (
        <ol>
          {checklist.slice(0, 6).map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ol>
      )}
      <button type="button" onClick={onTicket} disabled={!response} title="IT 쪽지 보내기">
        <MessageSquarePlus size={18} aria-hidden="true" />
        <span>{ticketStatus || "IT 쪽지 보내기"}</span>
      </button>
    </section>
  );
}

function ITSearchPanel({
  response,
  searchResults,
  searching,
  onSearch,
}: {
  response: ChatResponse | null;
  searchResults: SearchResult[];
  searching: boolean;
  onSearch: (query: string) => Promise<void>;
}) {
  const [query, setQuery] = useState("자동이체 출금계좌 만료 납부자번호");
  const generatedQuery = buildGeneratedQuery(response);

  return (
    <section className="panel it-tools">
      <div className="panel-title">
        <Code2 size={19} aria-hidden="true" />
        <h2>쿼리 생성</h2>
      </div>
      <div className="query-box">
        <span>{generatedQuery || "답변 후 검색어가 생성됩니다."}</span>
      </div>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void onSearch(query);
        }}
      >
        <input value={query} onChange={(event) => setQuery(event.target.value)} />
        <button type="submit" disabled={searching}>
          <Search size={18} aria-hidden="true" />
        </button>
      </form>
      <div className="search-results">
        {searchResults.slice(0, 5).map((result) => (
          <article key={result.document.doc_id}>
            <strong>{result.document.title}</strong>
            <span>{result.retrieval_backend}</span>
            <p>{result.summary}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function LogPanel({ logs, onRefresh }: { logs: RuntimeLog[]; onRefresh: () => Promise<void> }) {
  return (
    <section className="panel log-panel">
      <div className="table-head">
        <div className="panel-title">
          <Activity size={19} aria-hidden="true" />
          <h2>실행 로그</h2>
        </div>
        <button type="button" onClick={() => void onRefresh()}>
          새로고침
        </button>
      </div>
      <div className="log-table">
        <div className="log-row log-row-head">
          <span>시간</span>
          <span>역할</span>
          <span>응답</span>
          <span>검색</span>
          <span>상태</span>
        </div>
        {logs.slice(0, 12).map((log) => (
          <div className="log-row" key={log.id}>
            <span>{formatTime(log.timestamp)}</span>
            <span>{roleLabel(log.user_role as UserRole)}</span>
            <span>{routeLabel(log.answer_backend)}</span>
            <span>{log.retrieval_backend || "-"}</span>
            <span>{log.status}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function TicketList({ tickets, onRefresh }: { tickets: SupportTicket[]; onRefresh: () => Promise<void> }) {
  return (
    <section className="panel ticket-list">
      <div className="table-head">
        <div className="panel-title">
          <Users size={19} aria-hidden="true" />
          <h2>IT 쪽지</h2>
        </div>
        <button type="button" onClick={() => void onRefresh()}>
          새로고침
        </button>
      </div>
      {tickets.length === 0 ? (
        <p>접수된 쪽지가 없습니다.</p>
      ) : (
        <ul>
          {tickets.slice(0, 8).map((ticket) => (
            <li key={ticket.id}>
              <strong>{ticket.question}</strong>
              <span>
                {ticket.priority} · {routeLabel(ticket.answer_backend)} · {ticket.retrieval_backend || "-"}
              </span>
              <p>{ticket.summary}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function StatusPill({ online, label }: { online: boolean; label: string }) {
  return <span className={`status-pill ${online ? "is-online" : "is-offline"}`}>{label}</span>;
}

type RouteSummary = {
  answer: string;
  retrieval: string;
  description: string;
  isCloud: boolean;
};

function routeSummary(response: ChatResponse | null, health: HealthResponse | null): RouteSummary {
  const answerBackend = String(response?.metadata?.answer_backend ?? "");
  const ragProvider = String(response?.metadata?.rag_provider ?? health?.rag_provider ?? "multi_agent");
  const retrieval = sourceBackends(response).join(", ") || (ragProvider === "local" ? "local_json" : "azure_ai_search");
  const isCloud = answerBackend === "foundry" || retrieval.includes("azure_ai_search");
  const answer =
    answerBackend === "foundry"
      ? "MS Foundry gpt-5.4"
      : answerBackend === "safety"
        ? "보안 차단"
        : answerBackend === "local"
          ? "Local/Qwen"
          : "대기";
  return {
    answer,
    retrieval,
    isCloud,
    description: isCloud
      ? "Microsoft Foundry와 Azure AI Search 경로"
      : "로컬 Qwen 또는 Docker Elasticsearch 경로",
  };
}

function sourceBackends(response: ChatResponse | null): string[] {
  if (!response) return [];
  return Array.from(
    new Set(response.sources.map((source) => source.retrieval_backend).filter(Boolean) as string[]),
  );
}

function buildGeneratedQuery(response: ChatResponse | null) {
  if (!response) return "";
  const source = response.sources[0];
  const terms = [
    source?.title,
    source?.api_path,
    source?.class_name,
    source?.method_name,
    ...(source?.tables ?? []),
  ].filter(Boolean);
  return terms.join(" ");
}

function roleLabel(role: UserRole | string) {
  if (role === "admin") return "관리자";
  if (role === "it") return "IT";
  return "영업점";
}

function routeLabel(answerBackend: string) {
  if (answerBackend === "foundry") return "MS Foundry";
  if (answerBackend === "local") return "Local";
  if (answerBackend === "safety") return "Safety";
  return answerBackend || "-";
}

function formatTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" });
}
