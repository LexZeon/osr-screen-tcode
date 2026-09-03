from __future__ import annotations

import asyncio
import json
import threading
import webbrowser
from importlib.resources import files
from pathlib import Path

from .config import APP_DIR


class PreviewBridge:
    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._server = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._clients: set[object] = set()
        self._error: BaseException | None = None
        self.port = 0
        self.url = ""

    @property
    def is_running(self) -> bool:
        return self._loop is not None and self._loop.is_running() and self._server is not None

    def start(self) -> None:
        if self.is_running:
            return
        self._ready.clear()
        self._error = None
        self._thread = threading.Thread(target=self._run, name="osr-preview-bridge", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=3):
            raise RuntimeError("预览服务启动超时")
        if self._error is not None:
            raise RuntimeError(f"预览服务启动失败: {self._error}") from self._error

    def stop(self) -> None:
        if self._loop is None:
            return
        loop = self._loop
        if loop.is_running():
            future = asyncio.run_coroutine_threadsafe(self._shutdown(), loop)
            try:
                future.result(timeout=3)
                loop.call_soon_threadsafe(loop.stop)
            except Exception:
                loop.call_soon_threadsafe(loop.stop)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        self._thread = None
        self._loop = None
        self._server = None
        self._clients.clear()
        self.port = 0
        self.url = ""

    def open_window(self) -> Path:
        if not self.url:
            raise RuntimeError("预览服务还没有启动")
        source = files("osr_screen_tcode.assets").joinpath("osr_emu_standalone.html")
        html = source.read_text(encoding="utf-8")
        html = html.replace("ws://localhost:8080/ofs", self.url)
        html = html.replace("ws://localhost:9090", self.url)
        APP_DIR.mkdir(parents=True, exist_ok=True)
        preview_path = APP_DIR / "osr6_3d_preview.html"
        preview_path.write_text(html, encoding="utf-8")
        webbrowser.open(preview_path.as_uri())
        return preview_path

    def broadcast_tcode(self, command: str) -> None:
        if not self.is_running or self._loop is None:
            return
        text = command.strip()
        if not text:
            return
        payload = json.dumps(
            {"type": "event", "name": "tcode", "data": {"cmd": text}},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        self._loop.call_soon_threadsafe(lambda: asyncio.create_task(self._broadcast(payload)))

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._start_server())
            self._ready.set()
            loop.run_forever()
        except BaseException as exc:
            self._error = exc
            self._ready.set()
        finally:
            try:
                if self._server is not None:
                    self._server.close()
                    loop.run_until_complete(self._server.wait_closed())
                for client in list(self._clients):
                    loop.run_until_complete(client.close())
                loop.run_until_complete(loop.shutdown_asyncgens())
            finally:
                loop.close()

    async def _start_server(self) -> None:
        import websockets

        async def handler(websocket, *_args) -> None:
            self._clients.add(websocket)
            try:
                async for message in websocket:
                    await self._handle_message(websocket, message)
            finally:
                self._clients.discard(websocket)

        for port in [9090, *range(8765, 8786)]:
            try:
                self._server = await websockets.serve(handler, "127.0.0.1", port)
                self.port = port
                self.url = f"ws://127.0.0.1:{port}/osr-preview"
                return
            except OSError:
                continue
        raise OSError("没有可用的本地预览端口")

    async def _handle_message(self, websocket, message: str) -> None:
        try:
            data = json.loads(message)
        except (TypeError, json.JSONDecodeError):
            return
        if data.get("type") == "ping":
            await websocket.send(json.dumps({"type": "pong"}, separators=(",", ":")))

    async def _broadcast(self, payload: str) -> None:
        dead = []
        for client in list(self._clients):
            try:
                await client.send(payload)
            except Exception:
                dead.append(client)
        for client in dead:
            self._clients.discard(client)

    async def _shutdown(self) -> None:
        for client in list(self._clients):
            try:
                await client.close()
            except Exception:
                pass
        self._clients.clear()
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
