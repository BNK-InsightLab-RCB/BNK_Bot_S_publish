import { ChangeEvent, DragEvent, useRef, useState } from "react";
import { RotateCw, UploadCloud } from "lucide-react";
import type { AdminStorageEvent, StorageUploadItem } from "../api";

interface AdminPanelProps {
  ingesting: boolean;
  ingestStatus: string;
  onIngest: () => Promise<void>;
  uploading: boolean;
  uploadStatus: string;
  lastUploaded: StorageUploadItem[];
  recentStorageEvents: AdminStorageEvent[];
  onStorageUpload: (files: File[]) => Promise<void>;
}

export function AdminPanel({
  ingesting,
  ingestStatus,
  onIngest,
  uploading,
  uploadStatus,
  lastUploaded,
  recentStorageEvents,
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
          <h2>소스 업로드 / 자동 동기화</h2>
          <p>{ingestStatus || "지식문서 색인과 Azure AI Search 반영까지 자동으로 진행합니다."}</p>
        </div>
        <div className="admin-button-group">
          <button
            type="button"
            onClick={() => void onIngest()}
            disabled={ingesting}
            title="지식문서 색인 및 Azure Search 자동 반영"
          >
            {ingesting ? <RotateCw size={18} aria-hidden="true" /> : <UploadCloud size={18} aria-hidden="true" />}
            <span>{ingesting ? "업로드 중" : "업로드"}</span>
          </button>
        </div>
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
          <strong>{uploading ? "업로드 중" : "JSON/PDF/소스 업로드"}</strong>
          <p>{uploadStatus || "파일을 놓으면 로컬 테스트 문서 폴더와 Azure Blob Storage에 함께 저장됩니다."}</p>
        </div>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".json,.pdf,.md,.csv,.xlsx,.txt,.java,.xml,.vue,.sql"
          onChange={handleFileChange}
        />
      </div>
      <div className="upload-event-list">
        {(lastUploaded.length > 0 ? lastUploaded : recentStorageEvents[0]?.files.map((file, index) => ({
          file_name: file,
          blob_name: recentStorageEvents[0]?.blob_names[index] ?? "",
          url: "",
          size: 0,
          local_path: recentStorageEvents[0]?.local_paths[index] ?? "",
        })) ?? []).slice(0, 4).map((item) => (
          <article key={`${item.file_name}-${item.blob_name}`}>
            <strong>{item.file_name}</strong>
            <span>{item.local_path || "local 저장 대기"}</span>
            <small>{item.blob_name || "Azure Blob 기록 대기"}</small>
          </article>
        ))}
      </div>
    </section>
  );
}
