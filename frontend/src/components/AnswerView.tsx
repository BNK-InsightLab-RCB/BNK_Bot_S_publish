import { AlertCircle, CheckCircle2, ClipboardList, Wrench } from "lucide-react";
import type { ChatResponse } from "../api";
import { ChatDogeAvatar } from "./ChatDogeAvatar";

interface AnswerViewProps {
  response: ChatResponse | null;
  loading: boolean;
  question: string;
  hideEvidenceSections?: boolean;
  hideTechnicalSummary?: boolean;
}

const sectionIcons: Record<string, JSX.Element> = {
  "[가능한 원인]": <AlertCircle size={18} aria-hidden="true" />,
  "[먼저 확인할 사항]": <CheckCircle2 size={18} aria-hidden="true" />,
  "[계속 오류가 발생하는 경우]": <ClipboardList size={18} aria-hidden="true" />,
  "[IT부서 전달용 정보]": <Wrench size={18} aria-hidden="true" />,
};

const hiddenEvidenceTitles = new Set(["근거", "답변 근거", "답변근거", "출처", "sources"]);

export function AnswerView({
  response,
  loading,
  question,
  hideEvidenceSections = false,
  hideTechnicalSummary = false,
}: AnswerViewProps) {
  if (!response && !loading && !question) {
    return (
      <section className="answer-view answer-empty">
        <div className="bot-message">
          <ChatDogeAvatar />
          <div>
            <h2>질문을 기다리고 있습니다</h2>
            <p>오류 문구, 화면명, 입력값 상황을 함께 적으면 더 정확하게 찾습니다.</p>
          </div>
        </div>
      </section>
    );
  }

  const sections = response
    ? splitSections(response.answer).filter(
        (section) => !hideEvidenceSections || !hiddenEvidenceTitles.has(normalizeSectionTitle(section.title)),
      )
    : [];

  return (
    <section className="answer-view">
      {question && (
        <div className="user-message">
          <span>질문</span>
          <p>{question}</p>
        </div>
      )}
      <div className="bot-message">
        <ChatDogeAvatar />
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
                  <AnswerBody text={section.body} />
                </article>
              ))}
            </div>
          )}
        </div>
      </div>
      {!hideTechnicalSummary && response && Object.keys(response.it_summary).length > 0 && (
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
      {!hideTechnicalSummary && response?.metadata && (
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

function AnswerBody({ text }: { text: string }) {
  const lines = text.split("\n").map((line) => line.trimEnd());
  const blocks: JSX.Element[] = [];
  let listItems: JSX.Element[] = [];

  function flushList() {
    if (listItems.length === 0) return;
    blocks.push(<ul key={`list-${blocks.length}`}>{listItems}</ul>);
    listItems = [];
  }

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      flushList();
      continue;
    }
    const bullet = trimmed.match(/^[-•]\s+(.+)$/);
    if (bullet) {
      listItems.push(<li key={`item-${blocks.length}-${listItems.length}`}>{renderInline(bullet[1])}</li>);
      continue;
    }
    flushList();
    const numbered = trimmed.match(/^(\d+\.)\s+(.+)$/);
    if (numbered) {
      blocks.push(
        <p key={`p-${blocks.length}`} className="answer-step">
          <span>{numbered[1]}</span>
          <span>{renderInline(numbered[2])}</span>
        </p>,
      );
      continue;
    }
    blocks.push(<p key={`p-${blocks.length}`}>{renderInline(trimmed)}</p>);
  }
  flushList();
  return <div className="answer-body">{blocks}</div>;
}

function normalizeSectionTitle(title: string) {
  return title.replace(/^\[/, "").replace(/\]$/, "").trim().toLowerCase();
}

function renderInline(text: string) {
  const parts = text.split(/(`[^`]+`)/g);
  return parts.map((part, index) => {
    if (part.startsWith("`") && part.endsWith("`")) {
      return <code key={`${part}-${index}`}>{part.slice(1, -1)}</code>;
    }
    return <span key={`${part}-${index}`}>{part}</span>;
  });
}
