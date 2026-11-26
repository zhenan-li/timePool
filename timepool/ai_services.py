from __future__ import annotations

from .i18n import tr

import json
import mimetypes
import ssl
import threading
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class AIServiceError(RuntimeError):
    pass


@dataclass(slots=True)
class ExtractedTimeEntry:
    date: date
    title: str
    description: str
    minutes: int


@dataclass(slots=True)
class ExtractionResult:
    entries: list[ExtractedTimeEntry]
    warnings: list[str]
    raw_response: str


def _endpoint(base_url: str, path: str) -> str:
    return base_url.rstrip("/") + path


def _read_error(error: HTTPError) -> str:
    try:
        return error.read().decode("utf-8", errors="replace")
    except Exception:
        return str(error)


def _headers(api_key: str | None, extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if extra:
        headers.update(extra)
    return headers


def post_json(url: str, payload: dict[str, Any], api_key: str, timeout: int) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = _headers(api_key, {"Content-Type": "application/json"})
    request = Request(url, data=body, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise AIServiceError(f"HTTP {exc.code}: {_read_error(exc)}") from exc
    except URLError as exc:
        raise AIServiceError(f"Connection failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise AIServiceError("Request timed out") from exc


def _multipart_body(fields: dict[str, str], file_field: str, file_path: Path) -> tuple[bytes, str]:
    boundary = f"----timepool-{uuid.uuid4().hex}"
    lines: list[bytes] = []
    for name, value in fields.items():
        lines.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                str(value).encode("utf-8"),
                b"\r\n",
            ]
        )

    mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    lines.extend(
        [
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{file_field}"; filename="{file_path.name}"\r\n'.encode(),
            f"Content-Type: {mime_type}\r\n\r\n".encode(),
            file_path.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    return b"".join(lines), f"multipart/form-data; boundary={boundary}"


def post_multipart(
    url: str,
    fields: dict[str, str],
    file_field: str,
    file_path: Path,
    api_key: str,
    timeout: int,
) -> dict[str, Any]:
    body, content_type = _multipart_body(fields, file_field, file_path)
    headers = _headers(api_key, {"Content-Type": content_type})
    request = Request(url, data=body, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise AIServiceError(f"HTTP {exc.code}: {_read_error(exc)}") from exc
    except URLError as exc:
        raise AIServiceError(f"Connection failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise AIServiceError("Request timed out") from exc


def extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        for index, char in enumerate(text):
            if char != "{":
                continue
            try:
                parsed, _end = decoder.raw_decode(text[index:])
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue
    raise AIServiceError("LLM did not return a JSON object")


class LLMTimeParser:
    def __init__(self, settings: dict[str, Any], api_key: str):
        self.settings = settings
        self.api_key = api_key

    def extract(
        self,
        text: str,
        *,
        default_date: date,
        start_date: date,
        today: date,
    ) -> ExtractionResult:
        payload = self._payload(text, default_date=default_date, start_date=start_date, today=today)
        url = _endpoint(str(self.settings.get("base_url", "")), "/chat/completions")
        timeout = int(self.settings.get("timeout_seconds", 60))
        response = post_json(url, payload, self.api_key, timeout)
        raw_content = self._message_content(response)
        parsed = extract_json_object(raw_content)
        entries, warnings = self._normalize(parsed, default_date=default_date, start_date=start_date, today=today)
        return ExtractionResult(entries=entries, warnings=warnings, raw_response=raw_content)

    def _payload(self, text: str, *, default_date: date, start_date: date, today: date) -> dict[str, Any]:
        system = (
            "You extract time-use records from natural language. Return JSON only. "
            "Each entry must have date, title, description, minutes. "
            "Use minutes as an integer. If date is omitted, use default_date. "
            "Do not include unallocated time."
        )
        user = (
            f"software_start_date: {start_date.isoformat()}\n"
            f"today: {today.isoformat()}\n"
            f"default_date: {default_date.isoformat()}\n"
            "Allowed JSON schema:\n"
            '{"entries":[{"date":"YYYY-MM-DD","title":"string","description":"string","minutes":120}],'
            '"warnings":["string"]}\n'
            "Input:\n"
            f"{text}"
        )
        payload: dict[str, Any] = {
            "model": str(self.settings.get("model", "gpt-4o-mini")),
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
        }
        if bool(self.settings.get("use_response_format", True)):
            payload["response_format"] = {"type": "json_object"}
        return payload

    def _message_content(self, response: dict[str, Any]) -> str:
        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIServiceError("LLM response did not contain choices[0].message.content") from exc
        if isinstance(content, list):
            return "\n".join(str(part.get("text", "")) if isinstance(part, dict) else str(part) for part in content)
        return str(content)

    def _normalize(
        self,
        parsed: dict[str, Any],
        *,
        default_date: date,
        start_date: date,
        today: date,
    ) -> tuple[list[ExtractedTimeEntry], list[str]]:
        entries: list[ExtractedTimeEntry] = []
        warnings = [str(item) for item in parsed.get("warnings", []) if str(item).strip()]
        raw_entries = parsed.get("entries", [])
        if not isinstance(raw_entries, list):
            raise AIServiceError("LLM JSON field 'entries' must be a list")

        for index, raw in enumerate(raw_entries, start=1):
            if not isinstance(raw, dict):
                warnings.append(f"entry {index} ignored: not an object")
                continue
            try:
                entry_date = date.fromisoformat(str(raw.get("date") or default_date.isoformat()))
            except ValueError:
                warnings.append(f"entry {index} ignored: invalid date")
                continue
            if entry_date < start_date or entry_date > today:
                warnings.append(f"entry {index} ignored: date out of allowed range")
                continue

            title = str(raw.get("title", "")).strip()
            description = str(raw.get("description", "")).strip() or "\u672a\u547d\u540d\u5c0f\u7c7b"
            if not title:
                warnings.append(f"entry {index} ignored: title is empty")
                continue
            try:
                minutes = int(round(float(raw.get("minutes", 0))))
            except (TypeError, ValueError):
                warnings.append(f"entry {index} ignored: minutes is invalid")
                continue
            if minutes <= 0:
                warnings.append(f"entry {index} ignored: minutes must be positive")
                continue
            entries.append(ExtractedTimeEntry(entry_date, title, description, minutes))

        return entries, warnings


class STTClient:
    def __init__(self, settings: dict[str, Any], api_key: str):
        self.settings = settings
        self.api_key = api_key

    def transcribe_file(self, file_path: Path) -> str:
        if not file_path.exists():
            raise AIServiceError("Audio file does not exist")
        fields = {
            "model": str(self.settings.get("model", "whisper-1")),
            "response_format": "json",
        }
        language = str(self.settings.get("language", "")).strip()
        if language:
            fields["language"] = language
        url = _endpoint(str(self.settings.get("base_url", "")), "/audio/transcriptions")
        response = post_multipart(
            url,
            fields,
            "file",
            file_path,
            self.api_key,
            int(self.settings.get("timeout_seconds", 120)),
        )
        for key in ("text", "transcript", "content"):
            value = response.get(key)
            if value:
                return str(value)
        raise AIServiceError("STT response did not contain text")


class RealtimeSTTClient:
    def __init__(self, settings: dict[str, Any], api_key: str):
        self.settings = settings
        self.api_key = api_key

    def listen(self, on_text: Callable[[str], None], stop_event: threading.Event) -> None:
        try:
            import websocket
        except ImportError as exc:
            raise AIServiceError("websocket-client is required for realtime STT") from exc

        url = str(self.settings.get("realtime_url", "")).strip()
        if not url:
            raise AIServiceError("Realtime STT URL is empty")

        headers = []
        if self.api_key:
            headers.append(f"Authorization: Bearer {self.api_key}")
        try:
            ws = websocket.create_connection(url, header=headers, timeout=5, sslopt={"cert_reqs": ssl.CERT_NONE})
        except ConnectionRefusedError as exc:
            raise AIServiceError(
                tr("The service refused the connection. Check its settings, or use Record locally.")
            ) from exc
        try:
            while not stop_event.is_set():
                raw = ws.recv()
                text = self._extract_text(raw)
                if text:
                    on_text(text)
        finally:
            ws.close()

    def _extract_text(self, raw: str | bytes) -> str:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")
        stripped = raw.strip()
        if not stripped:
            return ""
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            return stripped
        for key in ("text", "delta", "transcript", "content"):
            value = payload.get(key)
            if value:
                return str(value)
        return ""
