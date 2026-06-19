# Department Source Repository Drop Zone

부서별 업무 소스코드는 이 디렉토리 아래에 올린다.

권장 구조:

```text
source_repositories/<department_code>/
  frontend/   # Vue, React, JSP, HTML 등 화면 코드
  backend/    # Java Controller, Service 등 서버 코드
  mapper/     # MyBatis XML, SQL mapper
  docs/       # 테이블 정의서, 오류코드, 장애 이력, 업무 규칙 문서
```

지원 확장자:

```text
.vue, .ts, .tsx, .js, .jsx, .jsp, .html, .java, .xml, .sql, .md, .csv, .xlsx
```

규칙:

- 파일은 UTF-8 텍스트 기준으로 관리한다. `.xlsx`는 파일 자체는 보관하지만 현재 파서는 시트 내용을 깊게 읽지 않는다.
- `.env`, key, pem, p12, pfx, credentials, secrets 파일은 올리지 않는다.
- 파일을 추가하거나 삭제한 뒤 `./scripts/sync_sources.sh --source-dir source_repositories/<department_code> --department <department_code>`를 실행한다.
- 삭제 반영은 전체 재색인 방식으로 처리한다. 현재 폴더에 없는 파일은 Azure AI Search 검색 대상에서도 빠진다.
