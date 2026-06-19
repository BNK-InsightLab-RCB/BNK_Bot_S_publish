import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  Activity,
  Bot,
  Cloud,
  Code2,
  Database,
  IdCard,
  Inbox,
  LockKeyhole,
  LogOut,
  Mail,
  MessageSquarePlus,
  Reply,
  Search,
  Shield,
  UserPlus,
  Users,
} from "lucide-react";
import {
  askQuestion,
  createSupportTicket,
  getHealth,
  getRuntimeLogs,
  getSupportTickets,
  ingestSample,
  loginUser,
  replySupportTicket,
  signupUser,
  uploadFilesToStorage,
  type AuthUser,
  type ChatResponse,
  type HealthResponse,
  type RoleCode,
  type RuntimeLog,
  type SourceCitation,
  type SupportTicket,
  type UserRole,
} from "./api";
import { AdminPanel } from "./components/AdminPanel";
import { AnswerView } from "./components/AnswerView";
import { ChatPanel } from "./components/ChatPanel";
import "./styles.css";

const roleOptions: Array<{ code: RoleCode; role: UserRole; label: string }> = [
  { code: "01", role: "branch", label: "영업점 직원" },
  { code: "02", role: "it", label: "IT 개발직원" },
  { code: "03", role: "admin", label: "관리자" },
];

const branchSamples = [
  "자동이체 등록: 출금계좌 사용 불가",
  "고객조회 저장: 권한 없음 문구 표시",
  "전표승인: 승인 후 오류 반복",
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
          <span className="eyebrow">Source-Aware Ops RAG</span>
          <h1>영업점 운영지원 로그인</h1>
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
                <input value={realName} onChange={(event) => setRealName(event.target.value)} />
              </span>
            </label>
          )}
          <label>
            행번
            <span>
              <IdCard size={17} aria-hidden="true" />
              <input value={employeeId} onChange={(event) => setEmployeeId(event.target.value)} />
            </span>
          </label>
          <label>
            비밀번호
            <span>
              <LockKeyhole size={17} aria-hidden="true" />
              <input
                type="password"
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
          <button type="submit" disabled={submitting || !employeeId || !password}>
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
          lastResponse={response}
          userRole="branch"
          title="영업점 업무 문의"
          description="화면명, 오류 문구, 처리 상황을 함께 남겨주세요."
          samples={branchSamples}
        />
        {(response || loading || activeQuestion) && (
          <AnswerView response={response} loading={loading} question={activeQuestion} />
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
          lastResponse={response}
          userRole="it"
          title="IT 개발자 분석 챗봇"
          description="파일, API, 서비스, SQL, 테이블 단서까지 함께 확인합니다."
          samples={itSamples}
        />
        {(response || loading || activeQuestion) && (
          <AnswerView response={response} loading={loading} question={activeQuestion} />
        )}
      </section>
    </div>
  );
}

function AdminWorkspace({
  session,
  logs,
  tickets,
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
  ingesting: boolean;
  ingestStatus: string;
  uploading: boolean;
  uploadStatus: string;
  onIngest: () => Promise<void>;
  onStorageUpload: (files: File[]) => Promise<void>;
  onRefresh: () => Promise<void>;
}) {
  return (
    <div className="workspace admin-layout">
      <section className="chat-workspace">
        <section className="panel admin-placeholder">
          <div className="panel-title">
            <Shield size={19} aria-hidden="true" />
            <h2>관리자 콘솔</h2>
          </div>
          <dl>
            <div>
              <dt>사용자</dt>
              <dd>{session.real_name}</dd>
            </div>
            <div>
              <dt>권한코드</dt>
              <dd>{session.role_code}</dd>
            </div>
            <div>
              <dt>접수 쪽지</dt>
              <dd>{tickets.length}</dd>
            </div>
          </dl>
        </section>
        <AdminPanel
          ingesting={ingesting}
          ingestStatus={ingestStatus}
          onIngest={onIngest}
          uploading={uploading}
          uploadStatus={uploadStatus}
          onStorageUpload={onStorageUpload}
        />
      </section>
      <aside className="ops-rail">
        <LogPanel logs={logs} onRefresh={onRefresh} />
      </aside>
    </div>
  );
}

function QuestionGuide() {
  const examples = [
    {
      label: "화면",
      title: "업무명/화면명",
      body: "자동이체 등록, 카드 재발급처럼 실제 화면 이름",
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
      label: "입력",
      title: "입력 상황",
      body: "계좌는 뒤 4자리만, 납부자번호/전표번호는 필요한 범위만",
    },
    {
      label: "범위",
      title: "발생 범위",
      body: "특정 고객, 특정 계좌, 모든 직원 공통 여부",
    },
    {
      label: "재시도",
      title: "재시도 결과",
      body: "새로고침, 재로그인, 정상 건 비교 여부",
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
    const key = [
      source.source_path || "",
      source.api_path || "",
      source.title || "",
      source.business_name || "",
      source.screen_id || "",
    ].join("|");
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
  const isCloud = answerBackend === "foundry" || retrieval.includes("azure_ai_search");
  const answer =
    answerBackend === "foundry"
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
