import { FormEvent, useState } from "react";
import { Send } from "lucide-react";
import type { ChatResponse, UserRole } from "../api";
import { AnswerView } from "./AnswerView";
import { ChatDogeAvatar } from "./ChatDogeAvatar";

interface ChatPanelProps {
  loading: boolean;
  onAsk: (question: string, userRole: UserRole) => Promise<void>;
  userRole: UserRole;
  title: string;
  description: string;
  response?: ChatResponse | null;
  activeQuestion?: string;
  samples?: string[];
  submitLabel?: string;
  showSamples?: boolean;
  hideEvidenceSections?: boolean;
  hideTechnicalSummary?: boolean;
  hideInternalSections?: boolean;
}

const defaultSamples = [
  "자동이체 등록 화면에서 출금계좌가 만료되었거나 사용 불가 상태라고 나와요. 납부자번호는 입력했습니다.",
  "고객조회 화면에서 저장이 안돼요.",
  "저장 권한이 없다고 나오는데 어떻게 해야 하나요?",
];

export function ChatPanel({
  loading,
  onAsk,
  userRole,
  title,
  description,
  response = null,
  activeQuestion = "",
  samples = defaultSamples,
  submitLabel = "전송",
  showSamples = true,
  hideEvidenceSections = false,
  hideTechnicalSummary = false,
  hideInternalSections = false,
}: ChatPanelProps) {
  const [question, setQuestion] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    const nextQuestion = question.trim();
    if (!nextQuestion || loading) return;
    setQuestion("");
    await onAsk(nextQuestion, userRole);
  }

  return (
    <section className="chat-panel chat-shell">
      <div className="chat-panel-head">
        <ChatDogeAvatar />
        <div>
          <h2>{title}</h2>
          <p>{description}</p>
        </div>
      </div>

      <div className="chat-thread" aria-live="polite">
        <AnswerView
          response={response}
          loading={loading}
          question={activeQuestion}
          hideEvidenceSections={hideEvidenceSections}
          hideTechnicalSummary={hideTechnicalSummary}
          hideInternalSections={hideInternalSections}
        />
      </div>

      {showSamples && samples.length > 0 && (
        <div className="sample-row">
          {samples.map((sample) => (
            <button key={sample} type="button" onClick={() => setQuestion(sample)}>
              {sample}
            </button>
          ))}
        </div>
      )}

      <form onSubmit={submit} className="ask-form chat-composer">
        <textarea
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          rows={2}
          placeholder="문의 내용을 입력하세요"
        />
        <div className="form-row">
          <span className="role-chip">{roleLabel(userRole)}</span>
          <button type="submit" disabled={loading || !question.trim()} title="질문 보내기">
            <Send size={18} aria-hidden="true" />
            <span>{loading ? "답변 생성 중" : submitLabel}</span>
          </button>
        </div>
      </form>
    </section>
  );
}

function roleLabel(role: UserRole) {
  if (role === "admin") return "관리자";
  if (role === "it") return "IT 직원";
  return "영업점 직원";
}
