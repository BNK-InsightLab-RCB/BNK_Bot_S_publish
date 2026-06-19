import { AlertCircle, CheckCircle2, ClipboardList, Wrench } from "lucide-react";
import type { ChatResponse } from "../api";

interface AnswerViewProps {
  response: ChatResponse | null;
  loading: boolean;
  question: string;
}

const sectionIcons: Record<string, JSX.Element> = {
  "[가능한 원인]": <AlertCircle size={18} aria-hidden="true" />,
  "[먼저 확인할 사항]": <CheckCircle2 size={18} aria-hidden="true" />,
  "[계속 오류가 발생하는 경우]": <ClipboardList size={18} aria-hidden="true" />,
  "[IT부서 전달용 정보]": <Wrench size={18} aria-hidden="true" />,
};

export function AnswerView({ response, loading, question }: AnswerViewProps) {
  if (!response && !loading && !question) {
    return (
      <section className="answer-view answer-empty">
        <div className="bot-message">
          <div className="assistant-avatar" aria-hidden="true">
            AI
          </div>
          <div>
            <h2>질문을 기다리고 있습니다</h2>
            <p>오류 문구, 화면명, 입력값 상황을 함께 적으면 더 정확하게 찾습니다.</p>
          </div>
        </div>
      </section>
    );
  }

  const sections = response ? splitSections(response.answer) : [];

  return (
    <section className="answer-view">
      {question && (
        <div className="user-message">
          <span>질문</span>
          <p>{question}</p>
        </div>
      )}
      <div className="bot-message">
        <div className="assistant-avatar" aria-hidden="true">
          AI
        </div>
        <div className="bot-message-body">
          <h2>{loading ? "답변 생성 중" : "답변"}</h2>
          {loading ? (
            <div className="loading-lines" aria-label="답변 생성 중">
              <span />
              <span />
              <span />
            </div>
          ) : (
            <div className="sections">
              {sections.map((section) => (
                <article key={section.title} className="answer-section">
                  <h3>
                    {sectionIcons[section.title] ?? null}
                    <span>{section.title.replace("[", "").replace("]", "")}</span>
                  </h3>
                  <p>{section.body}</p>
                </article>
              ))}
            </div>
          )}
        </div>
      </div>
      {response && Object.keys(response.it_summary).length > 0 && (
        <div className="it-summary">
          <h3>IT 요약</h3>
          <dl>
            {Object.entries(response.it_summary).map(([key, value]) => (
              <div key={key}>
                <dt>{key}</dt>
                <dd>{Array.isArray(value) ? value.join(", ") : String(value ?? "-")}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}
      {response?.metadata && (
        <div className="response-meta">
          <span>{String(response.metadata.rag_provider ?? "local")}</span>
          <span>{String(response.metadata.answer_backend ?? "local")}</span>
        </div>
      )}
    </section>
  );
}

function splitSections(answer: string) {
  const matches = answer.split(/(?=\[[^\]]+\])/g).filter(Boolean);
  return matches.map((chunk) => {
    const firstLine = chunk.split("\n")[0].trim();
    return {
      title: firstLine,
      body: chunk.replace(firstLine, "").trim(),
    };
  });
}
