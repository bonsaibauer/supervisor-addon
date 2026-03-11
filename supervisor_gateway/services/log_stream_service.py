from __future__ import annotations

import asyncio
from asyncio.subprocess import PIPE, STDOUT
import json
from typing import Any

from fastapi import HTTPException, Request

from ..config import Settings
from .action_service import ActionService


def log_methods(channel: str) -> tuple[str, str]:
    if channel in {"stdout", "enshrouded"}:
        return "readServerStdoutLog", "tailServerStdoutLog"
    if channel == "stderr":
        return "readServerStderrLog", "tailServerStderrLog"
    if channel == "supervisor":
        raise HTTPException(
            status_code=400,
            detail="api.logs.error.supervisor_stream_only",
        )
    raise HTTPException(
        status_code=400,
        detail="api.logs.error.invalid_channel",
    )


async def read_log(
    settings: Settings,
    server_id: str,
    channel: str,
    offset: int,
    length: int,
) -> dict[str, Any]:
    read_method, _ = log_methods(channel)
    action_service = ActionService(settings)
    data = await asyncio.to_thread(
        action_service.client.call_addon, read_method, server_id, offset, length
    )
    return {
        "ok": True,
        "server_id": server_id,
        "channel": channel,
        "offset": offset,
        "length": length,
        "data": data,
    }


async def tail_log(
    settings: Settings,
    server_id: str,
    channel: str,
    offset: int,
    length: int,
) -> dict[str, Any]:
    _, tail_method = log_methods(channel)
    action_service = ActionService(settings)
    data, next_offset, overflow = await asyncio.to_thread(
        action_service.client.call_addon, tail_method, server_id, offset, length
    )
    return {
        "ok": True,
        "server_id": server_id,
        "channel": channel,
        "offset": offset,
        "next_offset": next_offset,
        "overflow": bool(overflow),
        "data": data,
    }


async def stream_events(
    request: Request,
    settings: Settings,
    server_id: str,
    channel: str,
    offset: int,
    chunk_bytes: int | None,
):
    if channel == "supervisor":
        async for event in stream_supervisor_events(request, settings, server_id):
            yield event
        return

    _, tail_method = log_methods(channel)
    action_service = ActionService(settings)
    per_chunk = chunk_bytes or settings.stream_chunk_bytes
    per_chunk = max(128, min(per_chunk, 65536))

    current_offset = offset
    while True:
        if await request.is_disconnected():
            break

        try:
            data, next_offset, overflow = await asyncio.to_thread(
                action_service.client.call_addon,
                tail_method,
                server_id,
                current_offset,
                per_chunk,
            )
        except Exception as error:  # noqa: BLE001
            payload = {"ok": False, "error": str(error)}
            yield f"event: error\ndata: {json.dumps(payload)}\n\n"
            await asyncio.sleep(settings.stream_poll_seconds)
            continue

        payload = {
            "ok": True,
            "server_id": server_id,
            "channel": channel,
            "offset": current_offset,
            "next_offset": next_offset,
            "overflow": bool(overflow),
            "data": data,
        }
        if data:
            yield f"data: {json.dumps(payload)}\n\n"
        else:
            yield ": keep-alive\n\n"

        current_offset = int(next_offset)
        await asyncio.sleep(settings.stream_poll_seconds)


async def stream_supervisor_events(
    request: Request,
    settings: Settings,
    server_id: str,
):
    while True:
        if await request.is_disconnected():
            return

        try:
            process = await asyncio.create_subprocess_exec(
                "tail",
                "-n",
                str(settings.supervisor_tail_lines),
                "-F",
                settings.supervisor_log_file,
                stdout=PIPE,
                stderr=STDOUT,
            )
        except FileNotFoundError:
            payload = {
                "ok": False,
                "error": "api.logs.error.tail_binary_missing",
            }
            yield f"event: error\ndata: {json.dumps(payload)}\n\n"
            await asyncio.sleep(settings.stream_poll_seconds)
            continue
        except Exception as error:  # noqa: BLE001
            payload = {"ok": False, "error": str(error)}
            yield f"event: error\ndata: {json.dumps(payload)}\n\n"
            await asyncio.sleep(settings.stream_poll_seconds)
            continue

        try:
            while True:
                if await request.is_disconnected():
                    process.terminate()
                    await process.wait()
                    return

                try:
                    chunk = await asyncio.wait_for(
                        process.stdout.readline() if process.stdout else asyncio.sleep(0, result=b""),
                        timeout=max(settings.stream_poll_seconds, 0.1),
                    )
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue

                if not chunk:
                    break

                payload = {
                    "ok": True,
                    "server_id": server_id,
                    "channel": "supervisor",
                    "offset": 0,
                    "next_offset": 0,
                    "overflow": False,
                    "data": chunk.decode("utf-8", errors="replace"),
                }
                yield f"data: {json.dumps(payload)}\n\n"
        finally:
            if process.returncode is None:
                process.terminate()
                await process.wait()

        await asyncio.sleep(settings.stream_poll_seconds)



