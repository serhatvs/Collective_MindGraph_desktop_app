"""Stream microphone PCM audio to the realtime backend websocket."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import sys
import threading
from dataclasses import dataclass
from typing import Any

import sounddevice as sd
import websockets


@dataclass(slots=True)
class StreamClientConfig:
    url: str
    language: str | None
    sample_rate: int
    channels: int
    block_duration_ms: int
    flush_interval_seconds: float
    device: int | None


async def run_stream(config: StreamClientConfig) -> None:
    queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    loop = asyncio.get_running_loop()
    stop_capture = threading.Event()
    final_event = asyncio.Event()

    def audio_callback(indata: bytes, _frames: int, _time: Any, status: sd.CallbackFlags) -> None:
        if status:
            print(f"[microphone] {status}", file=sys.stderr)
        if stop_capture.is_set():
            return
        loop.call_soon_threadsafe(queue.put_nowait, bytes(indata))

    websocket_url = config.url
    if config.language:
        separator = "&" if "?" in websocket_url else "?"
        websocket_url = f"{websocket_url}{separator}language={config.language}"

    async with websockets.connect(websocket_url, max_size=32 * 1024 * 1024) as websocket:
        ready_message = json.loads(await websocket.recv())
        if ready_message.get("event") != "ready":
            raise RuntimeError(f"Unexpected first websocket event: {ready_message}")
        _validate_server_audio_format(ready_message, config)

        sender = asyncio.create_task(_send_audio(websocket, queue, stop_capture, config.flush_interval_seconds))
        receiver = asyncio.create_task(_receive_events(websocket, final_event))

        stream = sd.RawInputStream(
            samplerate=config.sample_rate,
            channels=config.channels,
            dtype="int16",
            blocksize=max(1, int(config.sample_rate * config.block_duration_ms / 1000)),
            callback=audio_callback,
            device=config.device,
        )
        with stream:
            print("Microphone stream started. Press Enter to stop and finalize.")
            await asyncio.to_thread(input)
            stop_capture.set()
            await queue.put(None)
            await sender
            await websocket.send(json.dumps({"event": "finalize"}))
            await final_event.wait()
            receiver.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await receiver


async def _send_audio(
    websocket: websockets.ClientConnection,
    queue: asyncio.Queue[bytes | None],
    stop_capture: threading.Event,
    flush_interval_seconds: float,
) -> None:
    async def periodic_flush() -> None:
        while not stop_capture.is_set():
            await asyncio.sleep(flush_interval_seconds)
            if stop_capture.is_set():
                return
            await websocket.send(json.dumps({"event": "flush"}))

    flush_task = asyncio.create_task(periodic_flush())
    try:
        while True:
            chunk = await queue.get()
            if chunk is None:
                return
            await websocket.send(chunk)
    finally:
        flush_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await flush_task


async def _receive_events(
    websocket: websockets.ClientConnection,
    final_event: asyncio.Event,
) -> None:
    async for message in websocket:
        payload = json.loads(message)
        event = payload.get("event")
        if event == "partial_transcript":
            segments = payload.get("segments", [])
            if segments:
                latest = segments[-1]
                print(
                    f"[partial] {latest['speaker']} "
                    f"{latest['start']:.2f}-{latest['end']:.2f}: {latest['corrected_text']}"
                )
            continue
        if event == "final_transcript":
            print("\nFinal transcript:\n")
            print(payload.get("text_output", ""))
            if payload.get("summary"):
                print("\nSummary:\n")
                print(payload["summary"])
            final_event.set()
            return
        if event == "ready":
            continue
        print(f"[event] {payload}")


def _validate_server_audio_format(payload: dict[str, Any], config: StreamClientConfig) -> None:
    audio_format = payload.get("audio_format", {})
    sample_rate = audio_format.get("sample_rate")
    channels = audio_format.get("channels")
    encoding = audio_format.get("encoding")
    if sample_rate != config.sample_rate or channels != config.channels or encoding != "pcm_s16le":
        raise RuntimeError(
            "Server requested incompatible audio format: "
            f"{audio_format}. Expected pcm_s16le/{config.sample_rate}Hz/{config.channels}ch."
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stream microphone audio to the realtime backend.")
    parser.add_argument("--url", default="ws://127.0.0.1:8080/transcribe/stream")
    parser.add_argument("--language", default=None)
    parser.add_argument("--sample-rate", type=int, default=16000)
    parser.add_argument("--channels", type=int, default=1)
    parser.add_argument("--block-ms", type=int, default=100)
    parser.add_argument("--flush-seconds", type=float, default=6.0)
    parser.add_argument("--device", type=int, default=None)
    parser.add_argument("--list-devices", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.list_devices:
        print(sd.query_devices())
        return 0

    config = StreamClientConfig(
        url=args.url,
        language=args.language,
        sample_rate=args.sample_rate,
        channels=args.channels,
        block_duration_ms=args.block_ms,
        flush_interval_seconds=args.flush_seconds,
        device=args.device,
    )
    try:
        asyncio.run(run_stream(config))
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
