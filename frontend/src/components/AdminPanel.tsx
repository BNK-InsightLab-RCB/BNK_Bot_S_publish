import { ChangeEvent, DragEvent, useRef, useState } from "react";
import { DatabaseZap, RotateCw, UploadCloud } from "lucide-react";

interface AdminPanelProps {
  ingesting: boolean;
  ingestStatus: string;
  onIngest: () => Promise<void>;
  uploading: boolean;
  uploadStatus: string;
  onStorageUpload: (files: File[]) => Promise<void>;
}

export function AdminPanel({
  ingesting,
  ingestStatus,
  onIngest,
  uploading,
  uploadStatus,
  onStorageUpload,
}: AdminPanelProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [dragging, setDragging] = useState(false);

  function submitFiles(fileList: FileList | null) {
    const files = Array.from(fileList ?? []);
    if (files.length > 0 && !uploading) {
      void onStorageUpload(files);
    }
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    submitFiles(event.dataTransfer.files);
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    submitFiles(event.target.files);
    event.target.value = "";
  }

  return (
    <section className="panel admin-panel">
      <div className="admin-row">
        <div>
          <h2>소스 색인</h2>
          <p>{ingestStatus || "대기 중"}</p>
        </div>
        <button type="button" onClick={onIngest} disabled={ingesting} title="샘플 색인 실행">
          {ingesting ? <RotateCw size={18} aria-hidden="true" /> : <DatabaseZap size={18} aria-hidden="true" />}
          <span>{ingesting ? "실행 중" : "샘플 색인"}</span>
        </button>
      </div>
      <div
        className={`storage-drop${dragging ? " is-dragging" : ""}`}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        role="button"
        tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            inputRef.current?.click();
          }
        }}
      >
        <UploadCloud size={20} aria-hidden="true" />
        <div>
          <strong>{uploading ? "업로드 중" : "소스/PDF 업로드"}</strong>
          <p>{uploadStatus || "파일을 놓거나 선택"}</p>
        </div>
        <input ref={inputRef} type="file" multiple onChange={handleFileChange} />
      </div>
    </section>
  );
}
