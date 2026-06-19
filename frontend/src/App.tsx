import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  Activity,
  BarChart3,
  Bot,
  Cloud,
  Code2,
  Database,
  Gauge,
  IdCard,
  Inbox,
  LockKeyhole,
  LogOut,
  Mail,
  MessageSquarePlus,
  Reply,
  Search,
  UploadCloud,
  UserPlus,
  Users,
} from "lucide-react";
import {
  askQuestion,
  createSupportTicket,
  getAdminDashboard,
  getHealth,
  getRuntimeLogs,
  getSupportTickets,
  ingestSample,
  loginUser,
  replySupportTicket,
  signupUser,
  uploadFilesToStorage,
  type AdminDashboard,
  type AuthUser,
  type ChatResponse,
  type HealthResponse,
  type RoleCode,
  type RuntimeLog,
  type StorageUploadItem,
  type SourceCitation,
  type SupportTicket,
  type UserRole,
} from "./api";
import { AdminPanel } from "./components/AdminPanel";
import { AnswerView } from "./components/AnswerView";
import { ChatPanel } from "./components/ChatPanel";
import { ChatDogeAvatar } from "./components/ChatDogeAvatar";
import "./styles.css";

const roleOptions: Array<{ code: RoleCode; role: UserRole; label: string }> = [
  { code: "01", role: "branch", label: "영업점 직원" },
  { code: "02", role: "it", label: "IT 개발직원" },
  { code: "03", role: "admin", label: "관리자" },
];

const branchSamples = [
  "업무명: 자동이체 등록 / 화면번호 또는 대표 문구: 자동이체 등록 / 오류문구: 출금계좌 사용 불가 / 수행작업: 등록 버튼 클릭 / 입력상황: 납부자번호 입력, 출금계좌 뒤 4자리 1234",
  "업무명: 고객조회 저장 / 화면번호 또는 대표 문구: 고객조회 상세 / 오류문구: 저장 권한이 없습니다 / 수행작업: 저장 버튼 클릭 / 입력상황: 고객번호 조회 후 주소 변경",
  "업무명: 전표승인 / 화면번호 또는 대표 문구: 전표승인 / 오류문구: 승인 처리 중 오류가 발생했습니다 / 수행작업: 승인 버튼 클릭 / 입력상황: 전표번호 입력 후 승인",
];

const itSamples = [
  "자동이체 등록 화면 오류의 API, 서비스, SQL 근거를 요약해줘.",
  "카드 재발급에서 월 재발급 횟수 초과 오류가 어디서 나는지 확인해줘.",
  "잔액증명서 발급 제한 조건을 코드 근거와 함께 정리해줘.",
];

export default function App() {
  const [session, setSession] = useState<AuthUser | null>(() => {
    const saved = localStorage.getItem("ops-rag-session");
    return saved ? (JSON.parse(saved) as AuthUser) : null;
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
  const [adminDashboard, setAdminDashboard] = useState<AdminDashboard | null>(null);
  const [lastUploaded, setLastUploaded] = useState<StorageUploadItem[]>([]);
  const [selectedTicketId, setSelectedTicketId] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    refreshHealth();
    refreshRuntime();
  }, []);

  function setAuthenticated(user: AuthUser) {
    setSession(user);
    setResponse(null);
    setActiveQuestion("");
    setTicketStatus("");
    setError("");
    localStorage.setItem("ops-rag-session", JSON.stringify(user));
  }

  function logout() {
    setSession(null);
    setResponse(null);
    setActiveQuestion("");
    setTicketStatus("");
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
    const [nextLogs, nextTickets, nextDashboard] = await Promise.all([
      getRuntimeLogs().catch(() => []),
      getSupportTickets().catch(() => []),
      getAdminDashboard().catch(() => null),
    ]);
    setLogs(nextLogs);
    setTickets(nextTickets);
    setAdminDashboard(nextDashboard);
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
      setIngestStatus(`${result.status} / ${result.indexed_count} docs / Azure Search`);
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
      setUploadStatus(
        `로컬 저장 + Azure Blob 동기화 완료 · ${result.uploaded.length} files / ${(uploadedSize / 1024).toFixed(1)} KiB`,
      );
      setLastUploaded(result.uploaded);
      await refreshRuntime();
    } catch (event) {
      setError(event instanceof Error ? event.message : "storage upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function handleTicket() {
    if (!response || !activeQuestion || !session) return;
    setTicketStatus("전송 중");
    const metadata = response.metadata ?? {};
    try {
      const ticket = await createSupportTicket({
        question: activeQuestion,
        summary: buildTicketSummary(response),
        priority: response.confidence < 0.55 ? "high" : "normal",
        sender_name: session.real_name,
        sender_employee_id: session.employee_id,
        sender_role: session.role,
        sender_role_code: session.role_code,
        answer_backend: String(metadata.answer_backend ?? ""),
        rag_provider: String(metadata.rag_provider ?? ""),
        retrieval_backend: sourceBackends(response).join(", "),
        confidence: response.confidence,
        source_count: response.sources.length,
        sources: response.sources,
      });
      setSelectedTicketId(ticket.id);
      setTicketStatus(`${ticket.id} 접수`);
      await refreshRuntime();
    } catch (event) {
      setTicketStatus("");
      setError(event instanceof Error ? event.message : "IT 쪽지 생성에 실패했습니다.");
    }
  }

  async function handleReply(ticketId: string, body: string) {
    if (!session) return;
    setError("");
    try {
      const ticket = await replySupportTicket(ticketId, {
        body,
        author_name: session.real_name,
        author_employee_id: session.employee_id,
        author_role: session.role,
        author_role_code: session.role_code,
      });
      setSelectedTicketId(ticket.id);
      await refreshRuntime();
    } catch (event) {
      setError(event instanceof Error ? event.message : "쪽지 답장에 실패했습니다.");
    }
  }

  const route = useMemo(() => routeSummary(response, health), [response, health]);

  if (!session) {
    return (
      <LoginView
        backendOnline={backendOnline}
        health={health}
        onLogin={setAuthenticated}
        onError={setError}
        error={error}
      />
    );
  }

  const selectedTicket =
    tickets.find((ticket) => ticket.id === selectedTicketId) ?? tickets[0] ?? null;
  const assignedTickets = session
    ? tickets.filter(
        (ticket) =>
          !ticket.recipient_employee_id || ticket.recipient_employee_id === session.employee_id,
      )
    : tickets;
  const assignedSelectedTicket =
    assignedTickets.find((ticket) => ticket.id === selectedTicketId) ?? assignedTickets[0] ?? null;

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
          session={session}
          response={response}
          loading={loading}
          activeQuestion={activeQuestion}
          route={route}
          ticketStatus={ticketStatus}
          tickets={tickets}
          selectedTicket={selectedTicket}
          onAsk={handleAsk}
          onTicket={handleTicket}
          onSelectTicket={setSelectedTicketId}
        />
      )}
      {session.role === "it" && (
        <ITWorkspace
          session={session}
          response={response}
          loading={loading}
          activeQuestion={activeQuestion}
          tickets={assignedTickets}
          selectedTicket={assignedSelectedTicket}
          onAsk={handleAsk}
          onReply={handleReply}
          onRefresh={refreshRuntime}
          onSelectTicket={setSelectedTicketId}
        />
      )}
      {session.role === "admin" && (
        <AdminWorkspace
          session={session}
          logs={logs}
          tickets={tickets}
          dashboard={adminDashboard}
          lastUploaded={lastUploaded}
          ingesting={ingesting}
          ingestStatus={ingestStatus}
          uploading={uploading}
          uploadStatus={uploadStatus}
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
  onError,
  error,
}: {
  backendOnline: boolean;
  health: HealthResponse | null;
  onLogin: (profile: AuthUser) => void;
  onError: (message: string) => void;
  error: string;
}) {
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [realName, setRealName] = useState("");
  const [employeeId, setEmployeeId] = useState("");
  const [password, setPassword] = useState("");
  const [roleCode, setRoleCode] = useState<RoleCode>("01");
  const [submitting, setSubmitting] = useState(false);
  const signupMissingName = mode === "signup" && !realName.trim();

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    onError("");
    try {
      const user =
        mode === "signup"
          ? await signupUser({
              real_name: realName,
              employee_id: employeeId,
              password,
              role_code: roleCode,
            })
          : await loginUser({ employee_id: employeeId, password });
      onLogin(user);
    } catch (submitError) {
      onError(submitError instanceof Error ? submitError.message : "인증에 실패했습니다.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="login-shell">
      <section className="login-panel auth-panel">
        <div className="auth-copy">
          <div className="auth-brand">
            <ChatDogeAvatar />
            <div>
              <span className="eyebrow">Source-Aware Ops RAG</span>
              <h1>챗도지</h1>
            </div>
          </div>
          <p>{mode === "signup" ? "챗도지 계정 만들기" : "영업점 운영지원 로그인"}</p>
        </div>
        <div className="auth-tabs" role="tablist" aria-label="인증 방식">
          <button
            type="button"
            className={mode === "login" ? "is-active" : ""}
            onClick={() => setMode("login")}
          >
            <LockKeyhole size={17} aria-hidden="true" />
            로그인
          </button>
          <button
            type="button"
            className={mode === "signup" ? "is-active" : ""}
            onClick={() => setMode("signup")}
          >
            <UserPlus size={17} aria-hidden="true" />
            회원가입
          </button>
        </div>
        <form className="auth-form" onSubmit={submit}>
          {mode === "signup" && (
            <label>
              실명
              <span>
                <Users size={17} aria-hidden="true" />
                <input
                  required
                  placeholder="실명 입력"
                  value={realName}
                  onChange={(event) => setRealName(event.target.value)}
                />
              </span>
            </label>
          )}
          <label>
            행번
            <span>
              <IdCard size={17} aria-hidden="true" />
              <input
                required
                placeholder="행번 입력"
                value={employeeId}
                onChange={(event) => setEmployeeId(event.target.value)}
              />
            </span>
          </label>
          <label>
            비밀번호
            <span>
              <LockKeyhole size={17} aria-hidden="true" />
              <input
                required
                minLength={mode === "signup" ? 4 : 1}
                type="password"
                placeholder="비밀번호 입력"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </span>
          </label>
          {mode === "signup" && (
            <label>
              권한
              <select value={roleCode} onChange={(event) => setRoleCode(event.target.value as RoleCode)}>
                {roleOptions.map((option) => (
                  <option key={option.code} value={option.code}>
                    {option.code} · {option.label}
                  </option>
                ))}
              </select>
            </label>
          )}
          <button type="submit" disabled={submitting || signupMissingName || !employeeId || !password}>
            {mode === "signup" ? <UserPlus size={18} aria-hidden="true" /> : <LockKeyhole size={18} aria-hidden="true" />}
            <span>{submitting ? "처리 중" : mode === "signup" ? "가입하기" : "로그인"}</span>
          </button>
        </form>
        {error && <div className="error-banner auth-error">{error}</div>}
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
  session: AuthUser;
  backendOnline: boolean;
  health: HealthResponse | null;
  response: ChatResponse | null;
  onLogout: () => void;
}) {
  return (
    <header className="app-header">
      <div>
        <span className="eyebrow">Source-Aware Ops RAG</span>
        <h1>{workspaceTitle(session.role)}</h1>
      </div>
      <div className="status-cluster" aria-label="서비스 상태">
        <span className="status-pill">
          {session.real_name} · {session.employee_id} · {session.role_code}
        </span>
        <StatusPill online={backendOnline} label={backendOnline ? "Backend online" : "Backend offline"} />
        <span className="status-pill">{health?.rag_provider ?? "multi_agent"}</span>
        <span className="status-pill">{routeStatusLabel(response, health)}</span>
        <button className="icon-button" type="button" onClick={onLogout} title="로그아웃">
          <LogOut size={18} aria-hidden="true" />
        </button>
      </div>
    </header>
  );
}

function BranchWorkspace({
  session,
  response,
  loading,
  activeQuestion,
  route,
  ticketStatus,
  tickets,
  selectedTicket,
  onAsk,
  onTicket,
  onSelectTicket,
}: {
  session: AuthUser;
  response: ChatResponse | null;
  loading: boolean;
  activeQuestion: string;
  route: RouteSummary;
  ticketStatus: string;
  tickets: SupportTicket[];
  selectedTicket: SupportTicket | null;
  onAsk: (question: string, userRole: UserRole) => Promise<void>;
  onTicket: () => Promise<void>;
  onSelectTicket: (ticketId: string) => void;
}) {
  const myTickets = tickets.filter((ticket) => ticket.sender_employee_id === session.employee_id);
  const selected = selectedTicket?.sender_employee_id === session.employee_id ? selectedTicket : myTickets[0] ?? null;
  return (
    <div className="workspace branch-layout">
      <aside className="ops-rail left-rail">
        <QuestionGuide />
      </aside>
      <section className="chat-workspace center-chat">
        <RoutePanel route={route} />
        <ChatPanel
          loading={loading}
          onAsk={onAsk}
          userRole="branch"
          title="영업점 업무 문의"
          description="화면명, 오류 문구, 처리 상황을 함께 남겨주세요."
          samples={branchSamples}
        />
        {(response || loading || activeQuestion) && (
          <AnswerView
            response={response}
            loading={loading}
            question={activeQuestion}
            hideEvidenceSections
            hideTechnicalSummary
          />
        )}
      </section>
      <aside className="ops-rail right-rail">
        <BranchMailbox
          response={response}
          tickets={myTickets}
          selectedTicket={selected}
          ticketStatus={ticketStatus}
          onTicket={onTicket}
          onSelectTicket={onSelectTicket}
        />
      </aside>
    </div>
  );
}

function ITWorkspace({
  session,
  response,
  loading,
  activeQuestion,
  tickets,
  selectedTicket,
  onAsk,
  onReply,
  onRefresh,
  onSelectTicket,
}: {
  session: AuthUser;
  response: ChatResponse | null;
  loading: boolean;
  activeQuestion: string;
  tickets: SupportTicket[];
  selectedTicket: SupportTicket | null;
  onAsk: (question: string, userRole: UserRole) => Promise<void>;
  onReply: (ticketId: string, body: string) => Promise<void>;
  onRefresh: () => Promise<void>;
  onSelectTicket: (ticketId: string) => void;
}) {
  return (
    <div className="workspace it-layout">
      <aside className="ops-rail mail-rail">
        <ITMailbox
          tickets={tickets}
          selectedTicket={selectedTicket}
          onRefresh={onRefresh}
          onSelectTicket={onSelectTicket}
        />
      </aside>
      <section className="ticket-detail-rail">
        <ITTicketDetail session={session} ticket={selectedTicket} onReply={onReply} />
      </section>
      <section className="developer-chat-rail">
        <ChatPanel
          loading={loading}
          onAsk={onAsk}
          userRole="it"
          title="IT 개발자 분석 챗봇"
          description="파일, API, 서비스, SQL, 테이블 단서까지 함께 확인합니다."
          samples={itSamples}
        />
        {(response || loading || activeQuestion) && (
          <AnswerView
            response={response}
            loading={loading}
            question={activeQuestion}
            hideEvidenceSections
            hideTechnicalSummary
          />
        )}
      </section>
    </div>
  );
}

function AdminWorkspace({
  session,
  logs,
  tickets,
  dashboard,
  lastUploaded,
  ingesting,
  ingestStatus,
  uploading,
  uploadStatus,
  onIngest,
  onStorageUpload,
  onRefresh,
}: {
  session: AuthUser;
  logs: RuntimeLog[];
  tickets: SupportTicket[];
  dashboard: AdminDashboard | null;
  lastUploaded: StorageUploadItem[];
  ingesting: boolean;
  ingestStatus: string;
  uploading: boolean;
  uploadStatus: string;
  onIngest: () => Promise<void>;
  onStorageUpload: (files: File[]) => Promise<void>;
  onRefresh: () => Promise<void>;
}) {
  const totals = dashboard?.totals;
  return (
    <div className="workspace admin-layout">
      <section className="admin-dashboard">
        <AdminPanel
          ingesting={ingesting}
          ingestStatus={ingestStatus}
          onIngest={onIngest}
          uploading={uploading}
          uploadStatus={uploadStatus}
          lastUploaded={lastUploaded}
          recentStorageEvents={dashboard?.recent_storage_events ?? []}
          onStorageUpload={onStorageUpload}
        />
        <section className="panel admin-command">
          <div>
            <span className="eyebrow">Admin Control Plane</span>
            <h2>운영 모니터링 대시보드</h2>
            <p>
              로컬 Qwen 경로와 Microsoft Foundry/Azure 경로를 같은 기준으로 기록하고,
              업로드·색인·쪽지 처리 상태를 한 화면에서 확인합니다.
            </p>
          </div>
          <div className="admin-command-actions">
            <span className="status-pill">{session.real_name} · {session.role_code}</span>
            <button type="button" onClick={() => void onRefresh()} title="대시보드 새로고침">
              새로고침
            </button>
          </div>
        </section>
        <section className="admin-kpi-strip" aria-label="관리자 KPI">
          <MetricTile icon={<Bot size={18} />} label="총 답변" value={String(totals?.chat_count ?? 0)} />
          <MetricTile
            icon={<Cloud size={18} />}
            label="MS 클라우드"
            value={String(totals?.cloud_answer_count ?? 0)}
          />
          <MetricTile
            icon={<Database size={18} />}
            label="로컬 답변"
            value={String(totals?.local_answer_count ?? 0)}
          />
          <MetricTile
            icon={<Gauge size={18} />}
            label="평균 응답"
            value={`${Math.round(totals?.avg_duration_ms ?? 0)}ms`}
          />
          <MetricTile
            icon={<Mail size={18} />}
            label="미해결 쪽지"
            value={String(totals?.open_ticket_count ?? tickets.length)}
          />
          <MetricTile
            icon={<UploadCloud size={18} />}
            label="업로드"
            value={formatBytes(totals?.storage_uploaded_bytes ?? 0)}
          />
        </section>
        <AdminProviderBoards dashboard={dashboard} />
        <div className="admin-content-grid">
          <div className="admin-stack">
            <AdminEvaluationPanel />
          </div>
          <div className="admin-stack">
            <LogPanel logs={logs} onRefresh={onRefresh} />
          </div>
        </div>
      </section>
    </div>
  );
}

function MetricTile({
  icon,
  label,
  value,
}: {
  icon: JSX.Element;
  label: string;
  value: string;
}) {
  return (
    <article className="metric-tile">
      <span aria-hidden="true">{icon}</span>
      <div>
        <small>{label}</small>
        <strong>{value}</strong>
      </div>
    </article>
  );
}

function AdminProviderBoards({ dashboard }: { dashboard: AdminDashboard | null }) {
  const azure = dashboard?.azure;
  const local = dashboard?.local;
  const totals = dashboard?.totals;
  const routeCounts = dashboard?.route_counts ?? [];
  const retrievalCounts = dashboard?.retrieval_counts ?? [];
  const monitor = azure?.monitor;
  const monitorConnected = monitor?.status === "connected";
  const monitorConfigured = Boolean(monitor?.configured);
  const azureOps = {
    model: azure?.foundry_model || "gpt-5.4",
    usedTokens: monitorConnected ? monitor?.tokens_used ?? 0 : 128_420,
    tokenLimit: monitor?.token_limit || 1_000_000,
    requestCount: monitorConnected ? monitor?.request_count ?? 0 : totals?.cloud_answer_count ?? 14,
    latencyP95: monitorConnected ? Math.round(monitor?.latency_ms ?? 0) : 820,
    modelLoad: monitorConnected ? monitor?.model_load_percent ?? 0 : 34,
    searchLoad: 46,
    queueDepth: monitorConnected ? monitor?.throttled_count ?? 0 : 2,
    errorCount: monitorConnected ? monitor?.error_count ?? 0 : 0,
  };
  const localOps = {
    cpuLoad: 37,
    memoryLoad: 58,
    qwenLoad: local?.llm_chat_enabled ? 44 : 18,
    queueDepth: 1,
    latencyP95: 410,
    requestCount: totals?.local_answer_count ?? 3,
  };
  const usedPercent = Math.round((azureOps.usedTokens / azureOps.tokenLimit) * 100);
  const azureLoadPercent = Math.round((azureOps.modelLoad + azureOps.searchLoad) / 2);
  return (
    <section className="provider-board-grid" aria-label="응답 경로 대시보드">
      <article className="panel provider-card is-azure">
        <header>
          <div>
            <span className="provider-icon">
              <Cloud size={22} aria-hidden="true" />
            </span>
            <div>
              <span className="eyebrow">Microsoft Cloud Route</span>
              <h2>MS Azure / Foundry</h2>
            </div>
          </div>
          <strong>{totals?.cloud_answer_count ?? 0}</strong>
        </header>
        <p>Foundry 답변 생성, Azure AI Search 검색, Blob Storage 업로드 상태를 함께 봅니다.</p>
        <dl>
          <div>
            <dt>Foundry 모델</dt>
            <dd>{azure?.foundry_configured ? azure.foundry_model : "미설정"}</dd>
          </div>
          <div>
            <dt>AI Search</dt>
            <dd>{azure?.azure_search_configured ? azure.search_index : "미설정"}</dd>
          </div>
          <div>
            <dt>Storage</dt>
            <dd>{azure?.storage_configured ? azure.storage_container : "미설정"}</dd>
          </div>
          <div>
            <dt>클라우드 경로</dt>
            <dd>{azure?.route ?? "-"}</dd>
          </div>
        </dl>
        <div className="provider-chip-row">
          {routeCounts
            .filter((item) => item.label === "foundry")
            .map((item) => (
              <span key={item.label}>{routeLabel(item.label)} {item.count}</span>
            ))}
          {retrievalCounts
            .filter((item) => item.label.includes("azure") || item.label === "foundry")
            .map((item) => (
              <span key={item.label}>{item.label} {item.count}</span>
            ))}
        </div>
        <div className="provider-ops-grid">
          <div className="provider-metric-grid" aria-label="Azure 모델 사용량 데모">
            <article>
              <span>모델 사용량</span>
              <strong>{usedPercent}%</strong>
              <small>{azureOps.usedTokens.toLocaleString()} / {azureOps.tokenLimit.toLocaleString()} tokens</small>
              <div className="usage-meter" aria-hidden="true">
                <span style={{ width: `${usedPercent}%` }} />
              </div>
            </article>
            <article>
              <span>현재 부하</span>
              <strong>{azureLoadPercent}%</strong>
              <small>model {azureOps.modelLoad}% · search {azureOps.searchLoad}% · throttle {azureOps.queueDepth}</small>
              <div className="usage-meter is-load" aria-hidden="true">
                <span style={{ width: `${azureLoadPercent}%` }} />
              </div>
            </article>
          </div>
          <div className="observability-agent" aria-label="Azure Observability 대화형 에이전트 데모">
            <header>
              <div>
                <span className="eyebrow">Observability Agent</span>
                <strong>대화로 원인 · 참조 · 부하 확인</strong>
                <small>
                  {azureOps.requestCount} {monitorConnected ? "Azure Monitor calls" : "demo calls"} · P95 {azureOps.latencyP95}ms
                </small>
              </div>
              <button
                type="button"
                disabled
                title={monitorConfigured ? monitor?.message : "AZURE_MONITOR_RESOURCE_ID 설정 후 실제 지표를 표시합니다."}
              >
                {monitorConnected ? "Live" : monitorConfigured ? "대기" : "Demo"}
              </button>
            </header>
            <div className="agent-chat-window">
              <p className="is-system"><span>agent</span> Foundry 모델, AI Search, 토큰, 지연시간 로그를 함께 봅니다.</p>
              <p><span>admin</span> 자동이체 오류 답변의 참조와 현재 부하를 보여줘.</p>
              <p>
                <span>agent</span> AI Search 부하 {azureOps.searchLoad}%, 모델 부하 {azureOps.modelLoad}%,
                오류 {azureOps.errorCount}건, 참조 6건입니다.
              </p>
            </div>
            <div className="agent-input-row" aria-disabled="true">
              <input type="text" disabled placeholder="Observability 에이전트에게 질문하기" />
              <button type="button" disabled>전송</button>
            </div>
          </div>
        </div>
      </article>
      <article className="panel provider-card is-local">
        <header>
          <div>
            <span className="provider-icon">
              <Database size={22} aria-hidden="true" />
            </span>
            <div>
              <span className="eyebrow">Local Runtime Route</span>
              <h2>Local Qwen</h2>
            </div>
          </div>
          <strong>{totals?.local_answer_count ?? 0}</strong>
        </header>
        <p>로컬 Qwen, 로컬 JSON/Elasticsearch 지식문서, 업로드된 테스트 문서 경로를 봅니다.</p>
        <dl>
          <div>
            <dt>모델</dt>
            <dd>{local?.llm_model ?? "Qwen/Qwen3-14B-MLX-4bit"}</dd>
          </div>
          <div>
            <dt>지식문서</dt>
            <dd>{local?.local_index_count ?? 0} docs</dd>
          </div>
          <div>
            <dt>로컬 인덱스</dt>
            <dd>{local?.local_index_path ?? "-"}</dd>
          </div>
          <div>
            <dt>업로드 폴더</dt>
            <dd>{local?.upload_dir ?? "-"}</dd>
          </div>
        </dl>
        <div className="provider-chip-row">
          {retrievalCounts
            .filter((item) => item.label.includes("local"))
            .map((item) => (
              <span key={item.label}>{item.label} {item.count}</span>
            ))}
          <span>Qwen chat {local?.llm_chat_enabled ? "on" : "fallback"}</span>
        </div>
        <div className="provider-ops-grid is-local-ops">
          <div className="provider-metric-grid" aria-label="Local Qwen 백엔드 사용량 데모">
            <article>
              <span>백엔드 CPU</span>
              <strong>{localOps.cpuLoad}%</strong>
              <small>uvicorn worker 1 · queue {localOps.queueDepth}</small>
              <div className="usage-meter" aria-hidden="true">
                <span style={{ width: `${localOps.cpuLoad}%` }} />
              </div>
            </article>
            <article>
              <span>메모리 / Qwen</span>
              <strong>{localOps.memoryLoad}%</strong>
              <small>qwen load {localOps.qwenLoad}% · P95 {localOps.latencyP95}ms</small>
              <div className="usage-meter is-local" aria-hidden="true">
                <span style={{ width: `${localOps.memoryLoad}%` }} />
              </div>
            </article>
          </div>
          <div className="local-runtime-panel" aria-label="Local Qwen 런타임 상태 데모">
            <header>
              <div>
                <span className="eyebrow">Backend Runtime</span>
                <strong>서버 부하 · 인덱스 · 큐 상태</strong>
                <small>{localOps.requestCount} local calls · demo metrics</small>
              </div>
            </header>
            <dl>
              <div>
                <dt>Qwen 서버</dt>
                <dd>{local?.llm_chat_enabled ? "online" : "fallback"}</dd>
              </div>
              <div>
                <dt>검색 큐</dt>
                <dd>{localOps.queueDepth} waiting</dd>
              </div>
              <div>
                <dt>지식문서</dt>
                <dd>{local?.local_index_count ?? 0} docs</dd>
              </div>
              <div>
                <dt>런타임</dt>
                <dd>FastAPI · Qwen local</dd>
              </div>
            </dl>
          </div>
        </div>
      </article>
    </section>
  );
}

function AdminEvaluationPanel() {
  const evaluationSummary = [
    { label: "Groundedness", value: 88, note: "검색 근거와 답변 일치" },
    { label: "Task Adherence", value: 91, note: "지침서 준수" },
    { label: "Tool Success", value: 97, note: "AI Search 호출 성공" },
  ];
  const evaluatorGroups = [
    {
      name: "답변 품질",
      items: ["Groundedness", "Fluency", "Coherence", "Relevance", "IntentResolution"],
      score: 89,
    },
    {
      name: "도구 활용",
      items: ["ToolSelection", "ToolOutputUtilization", "ToolInputAccuracy", "ToolCallAccuracy"],
      score: 92,
    },
    {
      name: "업무 완결",
      items: ["TaskCompletion", "TaskAdherence", "CustomerSatisfaction"],
      score: 86,
    },
    {
      name: "안전성",
      items: ["Violence", "SelfHarm", "IndirectAttack", "ProtectedMaterial", "CodeVulnerability"],
      score: 99,
    },
  ];
  return (
    <section className="panel evaluation-panel">
      <div className="panel-title">
        <BarChart3 size={19} aria-hidden="true" />
        <h2>Foundry 평가 보드</h2>
      </div>
      <div className="evaluation-run-card">
        <div>
          <span className="eyebrow">Evaluation group</span>
          <strong>eval-65o0x3cb</strong>
          <small>test-agent: 3 · dataset test_agent_9q8qbq50hq</small>
        </div>
        <span className="run-status">In progress</span>
      </div>
      <div className="evaluation-score-grid">
        {evaluationSummary.map((item) => (
          <article key={item.label}>
            <span>{item.label}</span>
            <strong>{item.value}</strong>
            <small>{item.note}</small>
            <div className="usage-meter" aria-hidden="true">
              <span style={{ width: `${item.value}%` }} />
            </div>
          </article>
        ))}
      </div>
      <div className="evaluator-group-list">
        {evaluatorGroups.map((group) => (
          <article key={group.name}>
            <header>
              <strong>{group.name}</strong>
              <span>{group.score}</span>
            </header>
            <div>
              {group.items.map((item) => (
                <small key={item}>{item}</small>
              ))}
            </div>
          </article>
        ))}
      </div>
      <div className="evaluation-insight-card">
        <Activity size={18} aria-hidden="true" />
        <p>
          실패 테스트는 Groundedness, ToolOutputUtilization, ToolCallAccuracy를 먼저 보고
          AI Search 근거 누락인지, 도구 호출은 됐지만 답변에 반영되지 않은 문제인지 나눠 확인합니다.
        </p>
      </div>
    </section>
  );
}

function QuestionGuide() {
  const examples = [
    {
      label: "번호",
      title: "화면번호 또는 대표 문구",
      body: "화면번호를 모르면 화면 상단 제목이나 크게 보이는 문구",
    },
    {
      label: "문구",
      title: "오류 문구",
      body: "화면에 나온 문장을 줄이지 말고 그대로",
    },
    {
      label: "작업",
      title: "수행 작업",
      body: "조회, 등록, 승인, 발급 등 누른 버튼과 직전 단계",
    },
    {
      label: "업무",
      title: "업무명",
      body: "자동이체 등록, 고객조회 저장, 전표승인처럼 업무 이름",
    },
    {
      label: "입력",
      title: "입력 상황",
      body: "계좌는 뒤 4자리만, 납부자번호/전표번호는 필요한 범위만",
    },
  ];
  return (
    <section className="panel question-guide">
      <div className="panel-title">
        <Bot size={19} aria-hidden="true" />
        <h2>질문 가이드</h2>
      </div>
      <div className="guide-list">
        {examples.map((item) => (
          <article key={item.label}>
            <span>{item.label}</span>
            <div>
              <strong>{item.title}</strong>
              <p>{item.body}</p>
            </div>
          </article>
        ))}
      </div>
      <div className="guide-note">
        주민번호, 전체 계좌번호, 비밀번호, 인증번호는 입력하지 마세요.
      </div>
    </section>
  );
}

function BranchMailbox({
  response,
  tickets,
  selectedTicket,
  ticketStatus,
  onTicket,
  onSelectTicket,
}: {
  response: ChatResponse | null;
  tickets: SupportTicket[];
  selectedTicket: SupportTicket | null;
  ticketStatus: string;
  onTicket: () => Promise<void>;
  onSelectTicket: (ticketId: string) => void;
}) {
  return (
    <section className="panel mailbox">
      <div className="panel-title">
        <Mail size={19} aria-hidden="true" />
        <h2>IT 쪽지함</h2>
      </div>
      <button type="button" onClick={onTicket} disabled={!response} title="현재 답변 정리해서 보내기">
        <MessageSquarePlus size={18} aria-hidden="true" />
        <span>{ticketStatus || "현재 상황 보내기"}</span>
      </button>
      {tickets.length > 0 ? (
        <>
          <TicketList
            tickets={tickets}
            selectedTicketId={selectedTicket?.id ?? ""}
            emptyText="보낸 쪽지가 없습니다."
            onSelectTicket={onSelectTicket}
          />
          <TicketThread ticket={selectedTicket} compact />
        </>
      ) : (
        <div className="mailbox-empty-card">
          <strong>아직 보낸 쪽지가 없습니다</strong>
          <p>챗봇 답변이 나온 뒤 현재 상황을 IT 담당자에게 보낼 수 있습니다.</p>
        </div>
      )}
    </section>
  );
}

function ITMailbox({
  tickets,
  selectedTicket,
  onRefresh,
  onSelectTicket,
}: {
  tickets: SupportTicket[];
  selectedTicket: SupportTicket | null;
  onRefresh: () => Promise<void>;
  onSelectTicket: (ticketId: string) => void;
}) {
  return (
    <section className="panel mailbox it-mailbox">
      <div className="table-head">
        <div className="panel-title">
          <Inbox size={19} aria-hidden="true" />
          <h2>영업점 쪽지</h2>
        </div>
        <button type="button" onClick={() => void onRefresh()}>
          새로고침
        </button>
      </div>
      <TicketList
        tickets={tickets}
        selectedTicketId={selectedTicket?.id ?? ""}
        emptyText="접수된 쪽지가 없습니다."
        onSelectTicket={onSelectTicket}
      />
    </section>
  );
}

function ITTicketDetail({
  session,
  ticket,
  onReply,
}: {
  session: AuthUser;
  ticket: SupportTicket | null;
  onReply: (ticketId: string, body: string) => Promise<void>;
}) {
  const [replyText, setReplyText] = useState("");

  async function submitReply(event: FormEvent) {
    event.preventDefault();
    if (!ticket || !replyText.trim()) return;
    await onReply(ticket.id, replyText.trim());
    setReplyText("");
  }

  return (
    <section className="panel ticket-detail-panel">
      <div className="panel-title">
        <Mail size={19} aria-hidden="true" />
        <h2>문의 상세</h2>
      </div>
      <TicketThread ticket={ticket} />
      <EvidenceList key={ticket?.id ?? "empty-evidence"} sources={ticket?.sources ?? []} />
      <form className="reply-form" onSubmit={submitReply}>
        <textarea
          value={replyText}
          onChange={(event) => setReplyText(event.target.value)}
          placeholder={ticket ? `${session.real_name} 답장 입력` : "메일을 선택하면 답장할 수 있습니다."}
          rows={5}
          disabled={!ticket}
        />
        <button type="submit" disabled={!ticket || !replyText.trim()}>
          <Reply size={18} aria-hidden="true" />
          <span>답장 보내기</span>
        </button>
      </form>
    </section>
  );
}

function TicketList({
  tickets,
  selectedTicketId,
  emptyText,
  onSelectTicket,
}: {
  tickets: SupportTicket[];
  selectedTicketId: string;
  emptyText: string;
  onSelectTicket: (ticketId: string) => void;
}) {
  if (tickets.length === 0) {
    return <p className="empty-text">{emptyText}</p>;
  }
  return (
    <div className="mail-list">
      {tickets.slice(0, 12).map((ticket) => (
        <button
          key={ticket.id}
          type="button"
          className={ticket.id === selectedTicketId ? "is-selected" : ""}
          onClick={() => onSelectTicket(ticket.id)}
        >
          <span>{ticket.sender_name || "영업점"}</span>
          <strong>{ticket.question}</strong>
          <small>
            {ticket.status} · {formatTime(ticket.updated_at || ticket.timestamp)}
          </small>
        </button>
      ))}
    </div>
  );
}

function TicketThread({ ticket, compact = false }: { ticket: SupportTicket | null; compact?: boolean }) {
  if (!ticket) {
    return (
      <div className="ticket-thread">
        <p>선택된 쪽지가 없습니다.</p>
      </div>
    );
  }
  return (
    <div className={`ticket-thread${compact ? " is-compact" : ""}`}>
      <div className="ticket-head">
        <span>{ticket.priority}</span>
        <strong>{ticket.question}</strong>
        <small>
          {ticket.sender_name || "영업점"} · {ticket.sender_employee_id || "-"}
        </small>
      </div>
      <div className="mail-body">
        <p>{ticket.summary}</p>
        <small>
          {routeLabel(ticket.answer_backend)} · {ticket.retrieval_backend || "-"} · 근거 {ticket.source_count}
        </small>
      </div>
      <div className="reply-stack">
        {(ticket.replies ?? []).map((reply) => (
          <article key={reply.id} className={reply.author_role === "branch" ? "from-branch" : "from-it"}>
            <strong>
              {reply.author_name || roleLabel(reply.author_role)} · {roleLabel(reply.author_role)}
            </strong>
            <p>{reply.body}</p>
            <small>{formatTime(reply.timestamp)}</small>
          </article>
        ))}
      </div>
    </div>
  );
}

function EvidenceList({ sources }: { sources: SourceCitation[] }) {
  const evidenceItems = mergeEvidenceSources(sources);

  return (
    <div className="evidence-list">
      <div className="evidence-head">
        <div className="panel-title">
          <Code2 size={18} aria-hidden="true" />
          <h3>답변 근거</h3>
        </div>
        {evidenceItems.length > 0 && <span>{evidenceItems.length}건</span>}
      </div>
      {sources.length === 0 ? (
        <p>저장된 근거가 없습니다. 필요하면 오른쪽 개발자 챗봇에서 다시 분석해 주세요.</p>
      ) : (
        <ul>
          {evidenceItems.slice(0, 8).map((source, index) => (
            <li key={`${source.doc_id}-${index}`}>
              <div className="evidence-index">{index + 1}</div>
              <article className="evidence-card">
                <header>
                  <strong>{source.title}</strong>
                  <div className="evidence-meta">
                    {source.business_name && <span>{source.business_name}</span>}
                    {source.screen_id && <span>{source.screen_id}</span>}
                    {source.screen_name && <span>{source.screen_name}</span>}
                    {source.retrieval_backend && <span>{source.retrieval_backend}</span>}
                  </div>
                </header>
                <p title={source.reason}>{evidenceSummary(source)}</p>
                <dl className="evidence-facts">
                  {source.source_path && (
                    <div>
                      <dt>위치</dt>
                      <dd>
                        {source.source_path}:{source.line_range}
                      </dd>
                    </div>
                  )}
                  {source.api_path && (
                    <div>
                      <dt>API</dt>
                      <dd>
                        {source.http_method ? `${source.http_method} ` : ""}
                        {source.api_path}
                      </dd>
                    </div>
                  )}
                  {source.error_codes && source.error_codes.length > 0 && (
                    <div>
                      <dt>Error</dt>
                      <dd>{source.error_codes.slice(0, 5).join(", ")}</dd>
                    </div>
                  )}
                  {source.exception_types && source.exception_types.length > 0 && (
                    <div>
                      <dt>Exception</dt>
                      <dd>{source.exception_types.join(", ")}</dd>
                    </div>
                  )}
                  {source.dto_names && source.dto_names.length > 0 && (
                    <div>
                      <dt>DTO</dt>
                      <dd>{source.dto_names.join(", ")}</dd>
                    </div>
                  )}
                  {source.dto_fields && source.dto_fields.length > 0 && (
                    <div>
                      <dt>Fields</dt>
                      <dd>{source.dto_fields.slice(0, 6).join(", ")}</dd>
                    </div>
                  )}
                  {source.input_fields && source.input_fields.length > 0 && (
                    <div>
                      <dt>입력</dt>
                      <dd>{source.input_fields.slice(0, 4).join(", ")}</dd>
                    </div>
                  )}
                  {source.validation_conditions && source.validation_conditions.length > 0 && (
                    <div>
                      <dt>검증</dt>
                      <dd>{source.validation_conditions.slice(0, 2).join(" / ")}</dd>
                    </div>
                  )}
                  {source.tables && source.tables.length > 0 && (
                    <div>
                      <dt>테이블</dt>
                      <dd>{source.tables.slice(0, 4).join(", ")}</dd>
                    </div>
                  )}
                </dl>
              </article>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function mergeEvidenceSources(sources: SourceCitation[]) {
  const grouped = new Map<string, SourceCitation>();
  for (const source of sources) {
    const key = evidenceGroupKey(source);
    const existing = grouped.get(key);
    if (!existing) {
      grouped.set(key, {
        ...source,
        error_codes: [...(source.error_codes ?? [])],
        exception_types: [...(source.exception_types ?? [])],
        dto_names: [...(source.dto_names ?? [])],
        dto_fields: [...(source.dto_fields ?? [])],
        input_fields: [...(source.input_fields ?? [])],
        validation_conditions: [...(source.validation_conditions ?? [])],
        tables: [...(source.tables ?? [])],
      });
      continue;
    }
    existing.reason = joinUnique([existing.reason, source.reason]).join(" / ");
    existing.api_description = existing.api_description || source.api_description;
    existing.error_codes = joinUnique([...(existing.error_codes ?? []), ...(source.error_codes ?? [])]);
    existing.exception_types = joinUnique([
      ...(existing.exception_types ?? []),
      ...(source.exception_types ?? []),
    ]);
    existing.dto_names = joinUnique([...(existing.dto_names ?? []), ...(source.dto_names ?? [])]);
    existing.dto_fields = joinUnique([...(existing.dto_fields ?? []), ...(source.dto_fields ?? [])]);
    existing.input_fields = joinUnique([...(existing.input_fields ?? []), ...(source.input_fields ?? [])]);
    existing.validation_conditions = joinUnique([
      ...(existing.validation_conditions ?? []),
      ...(source.validation_conditions ?? []),
    ]);
    existing.tables = joinUnique([...(existing.tables ?? []), ...(source.tables ?? [])]);
  }
  return Array.from(grouped.values());
}

function evidenceGroupKey(source: SourceCitation) {
  if (source.source_path || source.api_path || source.sql_id) {
    return [
      "technical",
      source.source_path || "",
      source.api_path || "",
      source.sql_id || "",
      source.title || "",
    ].join("|");
  }
  const title = source.title || "";
  const isBusinessRule = title.includes("업무 규칙") || !source.source_path;
  if (isBusinessRule) {
    return [
      "business-rule",
      title,
      source.screen_name || source.screen_id || "",
      source.retrieval_backend || "",
    ].join("|");
  }
  return ["summary", title, source.business_name || "", source.screen_id || ""].join("|");
}

function evidenceSummary(source: SourceCitation) {
  const text = source.api_description || source.reason || "저장된 근거 요약이 없습니다.";
  const compact = text.replace(/\s+/g, " ").trim();
  if (compact.length <= 180) return compact;
  return `${compact.slice(0, 180).trim()}...`;
}

function joinUnique(values: Array<string | null | undefined>) {
  const seen = new Set<string>();
  return values
    .map((value) => String(value || "").trim())
    .filter((value) => {
      if (!value || seen.has(value)) return false;
      seen.add(value);
      return true;
    });
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
  const isCloud = answerBackend === "foundry" || answerBackend === "foundry_sql_generator" || retrieval.includes("azure_ai_search");
  const answer =
    answerBackend === "foundry_sql_generator"
      ? "SQLGenerator-Agent"
      : answerBackend === "foundry"
      ? "MS Foundry gpt-5.4"
      : answerBackend === "safety"
        ? "보안 차단"
        : answerBackend === "scope_guard"
          ? "업무 범위 확인"
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

function routeStatusLabel(response: ChatResponse | null, health: HealthResponse | null) {
  const answerBackend = String(response?.metadata?.answer_backend ?? "");
  if (answerBackend === "foundry_sql_generator") return "SQLGenerator-Agent";
  if (answerBackend === "foundry") return "MS Foundry connected";
  if (answerBackend) return answerBackend;
  if (health?.ms_route === "foundry_search_tool") return "Foundry Search ready";
  if (health?.ms_route === "azure_search_then_foundry_context") return "Azure Search + Foundry ready";
  if (health?.ms_route === "azure_search_local_answer") return "Azure Search ready";
  return "standby";
}

function sourceBackends(response: ChatResponse | null): string[] {
  if (!response) return [];
  return Array.from(
    new Set(response.sources.map((source) => source.retrieval_backend).filter(Boolean) as string[]),
  );
}

function buildTicketSummary(response: ChatResponse) {
  const causes = response.branch_guide.possible_causes?.join(", ");
  const checklist = response.branch_guide.checklist?.slice(0, 5).join(" / ");
  return [
    causes ? `가능 원인: ${causes}` : "",
    checklist ? `확인 항목: ${checklist}` : "",
    `챗봇 답변 요약: ${response.answer.slice(0, 280)}`,
  ]
    .filter(Boolean)
    .join("\n");
}

function workspaceTitle(role: UserRole) {
  if (role === "admin") return "관리자 워크스페이스";
  if (role === "it") return "IT 개발자 워크스페이스";
  return "영업점 직원 워크스페이스";
}

function roleLabel(role: UserRole | string) {
  if (role === "admin") return "관리자";
  if (role === "it") return "IT 개발";
  return "영업점";
}

function routeLabel(answerBackend: string) {
  if (answerBackend === "foundry_sql_generator") return "SQL Generator";
  if (answerBackend === "foundry") return "MS Foundry";
  if (answerBackend === "local") return "Local";
  if (answerBackend === "safety") return "Safety";
  if (answerBackend === "scope_guard") return "Scope";
  return answerBackend || "-";
}

function formatTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" });
}

function formatBytes(value: number) {
  if (!value) return "0 B";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KiB`;
  return `${(value / 1024 / 1024).toFixed(1)} MiB`;
}
