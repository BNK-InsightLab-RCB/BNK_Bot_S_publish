import { FormEvent, useState } from "react";
import { Send } from "lucide-react";
import type { UserRole } from "../api";

interface ChatPanelProps {
  loading: boolean;
  onAsk: (question: string, userRole: UserRole) => Promise<void>;
  userRole: UserRole;
  title: string;
  description: string;
  samples?: string[];
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
  samples = defaultSamples,
}: ChatPanelProps) {
  const [question, setQuestion] = useState(samples[0]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!question.trim() || loading) return;
    await onAsk(question.trim(), userRole);
  }

  return (
    <section className="chat-panel">
      <div className="chat-panel-head">
        <div className="assistant-avatar" aria-hidden="true">
          AI
        </div>
        <div>
          <h2>{title}</h2>
          <p>{description}</p>
        </div>
      </div>

      <form onSubmit={submit} className="ask-form">
        <textarea
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          rows={5}
          placeholder="문의 내용을 입력하세요"
        />
        <div className="form-row">
          <span className="role-chip">{roleLabel(userRole)}</span>
          <button type="submit" disabled={loading || !question.trim()} title="질문 보내기">
            <Send size={18} aria-hidden="true" />
            <span>{loading ? "답변 생성 중" : "전송"}</span>
          </button>
        </div>
      </form>

      <div className="sample-row">
        {samples.map((sample) => (
          <button key={sample} type="button" onClick={() => setQuestion(sample)}>
            {sample}
          </button>
        ))}
      </div>
    </section>
  );
}

function roleLabel(role: UserRole) {
  if (role === "admin") return "관리자";
  if (role === "it") return "IT 직원";
  return "영업점 직원";
}
