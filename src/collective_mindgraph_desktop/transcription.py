"""Transcription adapters for recorded audio files."""

from __future__ import annotations

from collections.abc import Callable
import mimetypes
import os
from dataclasses import asdict
from dataclasses import dataclass
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from uuid import uuid4

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError, NoRegionError

DIRECT_AUDIO_UPLOAD_LIMIT_BYTES = 25 * 1024 * 1024
DEFAULT_MODEL_ID = "us.amazon.nova-2-lite-v1:0"
DEFAULT_REALTIME_BACKEND_URL = "http://127.0.0.1:8080"
DEFAULT_REALTIME_TIMEOUT_SECONDS = 240
DEFAULT_TRANSCRIPTION_PROMPT = (
    "Transcribe this audio recording exactly. Return only the transcript text. "
    "Do not summarize, explain, or add markdown."
)

_AUDIO_FORMATS_BY_SUFFIX = {
    ".aac": "aac",
    ".flac": "flac",
    ".m4a": "m4a",
    ".mka": "mka",
    ".mkv": "mkv",
    ".mp3": "mp3",
    ".mp4": "mp4",
    ".mpa": "mpeg",
    ".mpeg": "mpeg",
    ".mpga": "mpga",
    ".ogg": "ogg",
    ".opus": "opus",
    ".pcm": "pcm",
    ".wav": "wav",
    ".webm": "webm",
    ".xaac": "x-aac",
}


@dataclass(frozen=True, slots=True)
class TranscriptionResult:
    text: str
    model_id: str
    audio_path: str
    conversation_id: str | None = None
    raw_text_output: str | None = None
    corrected_text_output: str | None = None
    speaker_count: int | None = None


@dataclass(frozen=True, slots=True)
class RealtimeBackendTranscriptionConfig:
    base_url: str = DEFAULT_REALTIME_BACKEND_URL
    language: str | None = None
    request_timeout_seconds: int = DEFAULT_REALTIME_TIMEOUT_SECONDS

    @classmethod
    def from_env(cls) -> "RealtimeBackendTranscriptionConfig":
        timeout_raw = os.getenv("CMG_TRANSCRIPTION_TIMEOUT_SECONDS")
        timeout_seconds = int(timeout_raw) if timeout_raw else DEFAULT_REALTIME_TIMEOUT_SECONDS
        return cls(
            base_url=(
                os.getenv("CMG_TRANSCRIPTION_BACKEND_URL")
                or os.getenv("CMG_RT_BACKEND_URL")
                or DEFAULT_REALTIME_BACKEND_URL
            ).rstrip("/"),
            language=(os.getenv("CMG_TRANSCRIPTION_LANGUAGE") or "").strip() or None,
            request_timeout_seconds=timeout_seconds,
        )

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "RealtimeBackendTranscriptionConfig":
        base = cls.from_env()
        base_url = str(payload.get("base_url") or payload.get("backend_url") or base.base_url).strip().rstrip("/")
        language_value = payload.get("language")
        timeout_value = payload.get("request_timeout_seconds")
        return cls(
            base_url=base_url or base.base_url,
            language=str(language_value).strip() or None if language_value is not None else base.language,
            request_timeout_seconds=(
                int(timeout_value) if timeout_value is not None else base.request_timeout_seconds
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class RealtimeBackendTranscriptionSettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = (path or Path.cwd() / "transcription_settings.json").resolve()

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> RealtimeBackendTranscriptionConfig:
        if not self._path.exists():
            return RealtimeBackendTranscriptionConfig.from_env()

        payload = json.loads(self._path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Transcription settings file is invalid.")
        return RealtimeBackendTranscriptionConfig.from_dict(payload)

    def save(self, config: RealtimeBackendTranscriptionConfig) -> Path:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(config.to_dict(), indent=2), encoding="utf-8")
        return self._path


class RealtimeBackendTranscriptionService:
    def __init__(
        self,
        config: RealtimeBackendTranscriptionConfig | None = None,
        request_opener: Callable[..., object] | None = None,
    ) -> None:
        self._config = config or RealtimeBackendTranscriptionConfig.from_env()
        self._request_opener = request_opener or urlopen

    def transcribe_file(self, audio_path: str | Path) -> TranscriptionResult:
        path = Path(audio_path).expanduser().resolve()
        if not path.exists():
            raise ValueError(f"Audio file was not found: {path}")

        file_size = path.stat().st_size
        if file_size <= 0:
            raise ValueError("Audio file is empty.")

        payload, content_type = self._build_multipart_payload(path)
        request = Request(
            urljoin(f"{self._config.base_url}/", "transcribe/file"),
            data=payload,
            method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": content_type,
            },
        )
        try:
            with self._request_opener(request, timeout=self._config.request_timeout_seconds) as response:
                response_body = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace").strip()
            raise ValueError(
                f"Realtime transcription backend request failed: {detail or exc.reason or exc.code}"
            ) from exc
        except URLError as exc:
            raise ValueError(
                "Realtime transcription backend is not reachable. "
                f"Start `realtime_backend` at {self._config.base_url} and try again."
            ) from exc
        except TimeoutError as exc:
            raise ValueError("Realtime transcription backend request timed out.") from exc

        try:
            response_payload = json.loads(response_body)
        except json.JSONDecodeError as exc:
            raise ValueError("Realtime transcription backend returned an invalid JSON response.") from exc

        transcript_text = self._extract_text(response_payload)
        if not transcript_text:
            raise ValueError("Realtime transcription backend returned an empty transcript.")

        transcript_payload = response_payload.get("transcript")
        if not isinstance(transcript_payload, dict):
            transcript_payload = {}

        speaker_stats = response_payload.get("speaker_stats")
        speaker_count = len(speaker_stats) if isinstance(speaker_stats, list) else None
        return TranscriptionResult(
            text=transcript_text,
            model_id="realtime_backend",
            audio_path=str(path),
            conversation_id=self._extract_string(transcript_payload, "conversation_id"),
            raw_text_output=self._extract_string(response_payload, "raw_text_output"),
            corrected_text_output=self._extract_string(response_payload, "corrected_text_output"),
            speaker_count=speaker_count,
        )

    def _build_multipart_payload(self, audio_path: Path) -> tuple[bytes, str]:
        boundary = f"----CollectiveMindGraphBoundary{uuid4().hex}"
        chunks: list[bytes] = []

        def append_text_field(name: str, value: str) -> None:
            chunks.append(f"--{boundary}\r\n".encode("utf-8"))
            chunks.append(
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8")
            )
            chunks.append(value.encode("utf-8"))
            chunks.append(b"\r\n")

        def append_file_field(name: str, path: Path) -> None:
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            chunks.append(f"--{boundary}\r\n".encode("utf-8"))
            chunks.append(
                (
                    f'Content-Disposition: form-data; name="{name}"; filename="{path.name}"\r\n'
                    f"Content-Type: {content_type}\r\n\r\n"
                ).encode("utf-8")
            )
            chunks.append(path.read_bytes())
            chunks.append(b"\r\n")

        append_file_field("upload", audio_path)
        if self._config.language:
            append_text_field("language", self._config.language)
        chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
        return b"".join(chunks), f"multipart/form-data; boundary={boundary}"

    @staticmethod
    def _extract_text(payload: dict[str, object]) -> str:
        transcript_payload = payload.get("transcript")
        if isinstance(transcript_payload, dict):
            segments = transcript_payload.get("segments")
            if isinstance(segments, list):
                lines: list[str] = []
                for item in segments:
                    if not isinstance(item, dict):
                        continue
                    text = str(item.get("corrected_text") or item.get("raw_text") or "").strip()
                    if not text:
                        continue
                    speaker = str(item.get("speaker") or "").strip()
                    lines.append(f"{speaker}: {text}" if speaker else text)
                if lines:
                    return "\n".join(lines)

        for key in ("corrected_text_output", "text_output", "raw_text_output"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    @staticmethod
    def _extract_string(payload: dict[str, object], key: str) -> str | None:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None


@dataclass(frozen=True, slots=True)
class AmazonNovaTranscriptionConfig:
    model_id: str = DEFAULT_MODEL_ID
    region_name: str | None = None
    max_tokens: int = 4000
    temperature: float = 0.0
    top_p: float = 0.1
    prompt_text: str = DEFAULT_TRANSCRIPTION_PROMPT

    @classmethod
    def from_env(cls) -> "AmazonNovaTranscriptionConfig":
        region_name = os.getenv("CMG_AWS_REGION") or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
        model_id = os.getenv("CMG_BEDROCK_MODEL_ID") or DEFAULT_MODEL_ID
        prompt_text = os.getenv("CMG_TRANSCRIPTION_PROMPT") or DEFAULT_TRANSCRIPTION_PROMPT
        return cls(
            model_id=model_id,
            region_name=region_name,
            prompt_text=prompt_text,
        )

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "AmazonNovaTranscriptionConfig":
        base = cls.from_env()
        return cls(
            model_id=str(payload.get("model_id") or base.model_id),
            region_name=str(payload["region_name"]).strip() if payload.get("region_name") else base.region_name,
            max_tokens=int(payload.get("max_tokens") or base.max_tokens),
            temperature=float(payload.get("temperature") if payload.get("temperature") is not None else base.temperature),
            top_p=float(payload.get("top_p") if payload.get("top_p") is not None else base.top_p),
            prompt_text=str(payload.get("prompt_text") or base.prompt_text),
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class AmazonNovaTranscriptionSettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = (path or Path.cwd() / "transcription_settings.json").resolve()

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> AmazonNovaTranscriptionConfig:
        if not self._path.exists():
            return AmazonNovaTranscriptionConfig.from_env()

        payload = json.loads(self._path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Transcription settings file is invalid.")
        return AmazonNovaTranscriptionConfig.from_dict(payload)

    def save(self, config: AmazonNovaTranscriptionConfig) -> Path:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(config.to_dict(), indent=2), encoding="utf-8")
        return self._path


class AmazonNovaTranscriptionService:
    def __init__(
        self,
        config: AmazonNovaTranscriptionConfig | None = None,
        client: object | None = None,
    ) -> None:
        self._config = config or AmazonNovaTranscriptionConfig.from_env()
        self._client = client

    def transcribe_file(self, audio_path: str | Path) -> TranscriptionResult:
        path = Path(audio_path).expanduser().resolve()
        if not path.exists():
            raise ValueError(f"Audio file was not found: {path}")

        file_size = path.stat().st_size
        if file_size <= 0:
            raise ValueError("Audio file is empty.")
        if file_size > DIRECT_AUDIO_UPLOAD_LIMIT_BYTES:
            raise ValueError(
                "Audio file exceeds Amazon Nova's 25 MB direct upload limit. "
                "S3-based upload is not implemented in this app yet."
            )

        audio_format = self._detect_audio_format(path)
        audio_bytes = path.read_bytes()

        try:
            response = self._bedrock_client().converse(
                modelId=self._config.model_id,
                system=[{"text": "You are a speech-to-text transcription engine."}],
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "audio": {
                                    "format": audio_format,
                                    "source": {"bytes": audio_bytes},
                                }
                            },
                            {
                                "text": self._config.prompt_text,
                            },
                        ],
                    }
                ],
                inferenceConfig={
                    "maxTokens": self._config.max_tokens,
                    "temperature": self._config.temperature,
                    "topP": self._config.top_p,
                },
            )
        except NoRegionError as exc:
            raise ValueError(
                "AWS region is not configured. Set CMG_AWS_REGION, AWS_REGION, or AWS_DEFAULT_REGION."
            ) from exc
        except NoCredentialsError as exc:
            raise ValueError(
                "AWS credentials were not found. Configure an AWS profile or access keys before using Amazon Nova transcription."
            ) from exc
        except ClientError as exc:
            message = exc.response.get("Error", {}).get("Message", str(exc))
            raise ValueError(f"Amazon Nova request failed: {message}") from exc
        except BotoCoreError as exc:
            raise ValueError(f"Amazon Nova request failed: {exc}") from exc

        transcript_text = self._extract_text(response)
        if not transcript_text:
            raise ValueError("Amazon Nova returned an empty transcription response.")

        return TranscriptionResult(
            text=transcript_text,
            model_id=self._config.model_id,
            audio_path=str(path),
        )

    def _bedrock_client(self):
        if self._client is None:
            session = boto3.Session(region_name=self._config.region_name)
            self._client = session.client(
                "bedrock-runtime",
                config=Config(
                    connect_timeout=3600,
                    read_timeout=3600,
                    retries={"max_attempts": 1},
                ),
            )
        return self._client

    @staticmethod
    def _detect_audio_format(path: Path) -> str:
        format_name = _AUDIO_FORMATS_BY_SUFFIX.get(path.suffix.lower())
        if format_name is None:
            supported = ", ".join(sorted(_AUDIO_FORMATS_BY_SUFFIX))
            raise ValueError(f"Unsupported audio format '{path.suffix}'. Supported formats: {supported}")
        return format_name

    @staticmethod
    def _extract_text(response: dict[str, object]) -> str:
        output = response.get("output")
        if not isinstance(output, dict):
            return ""

        message = output.get("message")
        if not isinstance(message, dict):
            return ""

        content = message.get("content")
        if not isinstance(content, list):
            return ""

        text_blocks = [item.get("text", "").strip() for item in content if isinstance(item, dict) and item.get("text")]
        return "\n".join(block for block in text_blocks if block).strip()
