"""Frontend parser for Vue, TS/JS, JSX/TSX, JSP, and HTML files."""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Tuple

from backend.app.parsers.base import BaseParser, KnowledgeDocument, SourceFile
from backend.app.utils.text import normalize_ws, unique_keep_order


API_PATTERNS = [
    re.compile(r"axios\.(get|post|put|patch|delete)\s*\(\s*['\"]([^'\"]+)['\"]", re.IGNORECASE),
    re.compile(r"fetch\s*\(\s*['\"]([^'\"]+)['\"]", re.IGNORECASE),
    re.compile(r"\$\.ajax\s*\(\s*\{[^}]*url\s*:\s*['\"]([^'\"]+)['\"]", re.IGNORECASE | re.DOTALL),
]
MESSAGE_RE = re.compile(
    r"(?:alert|confirm)\s*\(\s*['\"]([^'\"]+)['\"]|(?:toast|notify)\.[A-Za-z_]+\s*\(\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)
SCREEN_ID_RE = re.compile(r"(?:screenId|SCREEN_ID|data-screen-id)\s*[:=]\s*['\"]([A-Z0-9_/-]+)['\"]")
MENU_ID_RE = re.compile(r"(?:menuId|MENU_ID|data-menu-id)\s*[:=]\s*['\"]([A-Z0-9_/-]+)['\"]")
SCREEN_NAME_RE = re.compile(r"(?:screenName|SCREEN_NAME|title)\s*[:=]\s*['\"]([^'\"]+)['\"]")
BUTTON_RE = re.compile(
    r"<button[^>]*(?:@click|v-on:click|onClick)\s*=\s*['\"]([^'\"]+)['\"][^>]*>(.*?)</button>",
    re.IGNORECASE | re.DOTALL,
)
LABEL_INPUT_RE = re.compile(
    r"<label[^>]*>(?P<label>.*?)<input[^>]*(?:v-model(?:\.[\w.]+)?|name)\s*=\s*['\"](?P<field>[^'\"]+)['\"][^>]*>",
    re.IGNORECASE | re.DOTALL,
)
V_MODEL_RE = re.compile(r"v-model(?:\.[\w.]+)?\s*=\s*['\"]([^'\"]+)['\"]", re.IGNORECASE)
FORM_FIELD_RE = re.compile(r"\bform\.([A-Za-z_][\w]*)")


def _line_no(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _find_matching_brace(text: str, open_index: int) -> int:
    depth = 0
    quote: Optional[str] = None
    escaped = False
    for index in range(open_index, len(text)):
        char = text[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in {"'", '"', "`"}:
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
    return len(text) - 1


def _iter_functions(text: str) -> Iterable[Tuple[str, str, int, int]]:
    patterns = [
        re.compile(r"\bfunction\s+([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{"),
        re.compile(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>\s*\{"),
        re.compile(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?function\s*\([^)]*\)\s*\{"),
        re.compile(r"\b([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{"),
    ]
    seen = set()
    covered_ranges: List[Tuple[int, int]] = []
    for pattern in patterns:
        for match in pattern.finditer(text):
            name = match.group(1)
            if name in {"if", "for", "while", "switch", "catch", "function"}:
                continue
            if any(start <= match.start() <= end for start, end in covered_ranges):
                continue
            open_index = text.find("{", match.start())
            close_index = _find_matching_brace(text, open_index)
            key = (name, match.start(), close_index)
            if key in seen:
                continue
            seen.add(key)
            covered_ranges.append((match.start(), close_index))
            yield name, text[match.start() : close_index + 1], match.start(), close_index


def _extract_api_calls(body: str) -> List[Dict[str, str]]:
    calls: List[Dict[str, str]] = []
    for pattern in API_PATTERNS:
        for match in pattern.finditer(body):
            if pattern.pattern.startswith("axios"):
                calls.append({"http_method": match.group(1).upper(), "api_path": match.group(2)})
            else:
                calls.append({"http_method": "GET", "api_path": match.group(1)})
    unique: Dict[Tuple[str, str], Dict[str, str]] = {}
    for call in calls:
        unique[(call["http_method"], call["api_path"])] = call
    return list(unique.values())


def _extract_messages(body: str) -> List[str]:
    return unique_keep_order(first or second for first, second in MESSAGE_RE.findall(body))


def _extract_if_conditions(body: str) -> List[str]:
    return unique_keep_order(match.group(1).strip() for match in re.finditer(r"\bif\s*\((.*?)\)", body, re.DOTALL))


def _extract_buttons(text: str) -> Dict[str, str]:
    buttons: Dict[str, str] = {}
    for handler, label_html in BUTTON_RE.findall(text):
        handler_name = re.sub(r"\(.*\)$", "", handler.strip())
        label = normalize_ws(re.sub(r"<[^>]+>", "", label_html))
        if handler_name and label:
            buttons[handler_name] = label
    return buttons


def _extract_input_fields(text: str) -> List[str]:
    fields: List[str] = []
    for match in LABEL_INPUT_RE.finditer(text):
        label = normalize_ws(re.sub(r"<[^>]+>", "", match.group("label")))
        field = match.group("field").strip()
        if label and field:
            fields.append(f"{label}({field})")
        elif field:
            fields.append(field)
    for field in V_MODEL_RE.findall(text):
        fields.append(field.strip())
    return unique_keep_order(fields)


def _extract_form_fields(body: str) -> List[str]:
    return unique_keep_order(FORM_FIELD_RE.findall(body))


def _api_description(function_name: str, button_name: Optional[str], api_calls: List[Dict[str, str]]) -> str:
    action = f"{button_name} 버튼" if button_name else f"{function_name} 이벤트"
    if not api_calls:
        return f"{action}에서 화면 입력값을 검증한다."
    calls = ", ".join(f"{call['http_method']} {call['api_path']}" for call in api_calls)
    return f"{action}에서 화면 입력값을 검증한 뒤 {calls} 업무 API를 호출한다."


class FrontendParser(BaseParser):
    """Extract screen metadata, button events, API calls, and user messages."""

    supported_extensions = [".vue", ".ts", ".tsx", ".js", ".jsx", ".jsp", ".html"]

    def parse(self, source: SourceFile) -> List[KnowledgeDocument]:
        text = source.text
        screen_id = _first(SCREEN_ID_RE.findall(text))
        menu_id = _first(MENU_ID_RE.findall(text))
        screen_name = _first(SCREEN_NAME_RE.findall(text)) or _extract_heading(text)
        buttons = _extract_buttons(text)
        input_fields = _extract_input_fields(text)
        docs: List[KnowledgeDocument] = []

        if screen_id or screen_name or menu_id:
            docs.append(
                KnowledgeDocument(
                    doc_type="frontend_screen",
                    title=screen_name or source.path.stem,
                    business_name=screen_name or source.path.stem,
                    summary=f"{screen_name or source.path.stem} 화면 정의",
                    source_path=str(source.path),
                    screen_id=screen_id,
                    screen_name=screen_name,
                    screen_info={
                        "screen_id": screen_id,
                        "screen_name": screen_name,
                        "menu_id": menu_id,
                        "input_fields": input_fields,
                        "buttons": list(buttons.values()),
                    },
                    menu_id=menu_id,
                    input_fields=input_fields,
                    code_text=text[:4000],
                    end_line=max(1, text.count("\n") + 1),
                )
            )

        for function_name, body, start, end in _iter_functions(text):
            api_calls = _extract_api_calls(body)
            messages = _extract_messages(body)
            conditions = _extract_if_conditions(body)
            if not api_calls and not messages and function_name not in buttons:
                continue
            button_name = buttons.get(function_name)
            validation_rules = _validation_rules(conditions, messages)
            form_fields = _extract_form_fields(body)
            event_input_fields = [
                field for field in input_fields if not form_fields or any(name in field for name in form_fields)
            ]
            summary_parts = []
            if button_name:
                summary_parts.append(f"{button_name} 버튼 처리")
            if api_calls:
                summary_parts.append(
                    ", ".join(f"{call['http_method']} {call['api_path']}" for call in api_calls)
                    + " 호출"
                )
            if messages:
                summary_parts.append("사용자 메시지: " + ", ".join(messages))
            docs.append(
                KnowledgeDocument(
                    doc_type="frontend_event",
                    title=f"{source.path.name} > {function_name}",
                    business_name=screen_name or source.path.stem,
                    summary="; ".join(summary_parts) or f"{function_name} 이벤트 처리",
                    source_path=str(source.path),
                    screen_id=screen_id,
                    screen_name=screen_name,
                    screen_info={
                        "screen_id": screen_id,
                        "screen_name": screen_name,
                        "menu_id": menu_id,
                        "button_name": button_name,
                        "input_fields": event_input_fields,
                    },
                    menu_id=menu_id,
                    api_path=api_calls[0]["api_path"] if api_calls else None,
                    http_method=api_calls[0]["http_method"] if api_calls else None,
                    api_description=_api_description(function_name, button_name, api_calls),
                    method_name=function_name,
                    input_fields=event_input_fields,
                    dto_names=["form"] if api_calls and form_fields else [],
                    dto_fields=form_fields,
                    validation_conditions=conditions,
                    call_chain=[f"{call['http_method']} {call['api_path']}" for call in api_calls],
                    error_messages=messages,
                    business_rules=validation_rules,
                    branch_guide=_branch_guide(messages),
                    it_guide=(
                        f"{function_name}에서 "
                        + ", ".join(f"{call['http_method']} {call['api_path']}" for call in api_calls)
                    ).strip(),
                    code_text=body,
                    start_line=_line_no(text, start),
                    end_line=_line_no(text, end),
                    metadata={
                        "button_name": button_name,
                        "api_calls": api_calls,
                        "validation_conditions": conditions,
                        "user_messages": messages,
                    },
                )
            )
        return docs


def _first(values: List[str]) -> Optional[str]:
    return values[0] if values else None


def _extract_heading(text: str) -> Optional[str]:
    match = re.search(r"<h1[^>]*>(.*?)</h1>", text, re.IGNORECASE | re.DOTALL)
    if match:
        return normalize_ws(re.sub(r"<[^>]+>", "", match.group(1)))
    return None


def _validation_rules(conditions: List[str], messages: List[str]) -> List[str]:
    rules: List[str] = []
    for index, condition in enumerate(conditions):
        if index < len(messages):
            rules.append(f"{condition} 조건이면 '{messages[index]}' 메시지를 표시하고 처리를 중단한다.")
        else:
            rules.append(f"{condition} 조건을 확인한다.")
    return rules


def _branch_guide(messages: List[str]) -> str:
    if not messages:
        return ""
    return "화면 메시지를 확인하고 입력값 또는 처리 상태를 먼저 점검해야 합니다: " + ", ".join(messages)
