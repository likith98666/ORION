import base64
import json
import os
import select
import socket
import struct
import subprocess
import time
from pathlib import Path
from urllib.request import Request, urlopen

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BASE_URL = "http://127.0.0.1:8000/"
OUTPUT_DIR = Path("ui_snapshot")
OUTPUT_DIR.mkdir(exist_ok=True)


class CDPClient:
    def __init__(self, ws_url: str):
        parts = ws_url.replace("ws://", "").split("/", 1)
        host, port_str = parts[0].split(":")
        path = "/" + parts[1]
        self._sock = socket.create_connection((host, int(port_str)), timeout=10)
        self._sock.setblocking(True)
        self._next_id = 1
        self.console_messages = []
        self.console_errors = []
        self.requests_sent = {}
        self.responses_received = {}
        self.requests_failed = {}
        self.external_requests = []

        # WebSocket Handshake
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        handshake = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}:{port_str}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self._sock.sendall(handshake.encode("utf-8"))
        resp = self._sock.recv(2048)
        if b"101 " not in resp:
            raise ConnectionError(f"WebSocket handshake failed: {resp.decode('utf-8', 'ignore')}")

    def close(self):
        try:
            self._sock.close()
        except Exception:
            pass

    def _send_cmd(self, method: str, params: dict | None = None) -> int:
        cmd_id = self._next_id
        self._next_id += 1
        payload = {"id": cmd_id, "method": method, "params": params or {}}
        raw = json.dumps(payload).encode("utf-8")
        mask = os.urandom(4)
        length = len(raw)

        if length < 126:
            hdr = bytearray([0x81, 0x80 | length])
        elif length < 65536:
            hdr = bytearray([0x81, 0x80 | 126]) + struct.pack("!H", length)
        else:
            hdr = bytearray([0x81, 0x80 | 127]) + struct.pack("!Q", length)

        hdr.extend(mask)
        masked = bytearray(raw[i] ^ mask[i % 4] for i in range(length))
        self._sock.sendall(hdr + masked)
        return cmd_id

    def _read_frame(self, timeout: float = 0.1) -> dict | None:
        r, _, _ = select.select([self._sock], [], [], timeout)
        if not r:
            return None
        hdr = self._sock.recv(2)
        if len(hdr) < 2:
            return None
        length = hdr[1] & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._sock.recv(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._sock.recv(8))[0]

        data = bytearray()
        while len(data) < length:
            chunk = self._sock.recv(length - len(data))
            if not chunk:
                break
            data.extend(chunk)

        try:
            msg = json.loads(data.decode("utf-8"))
            if isinstance(msg, dict):
                method = msg.get("method", "")
                if method == "Runtime.consoleAPICalled":
                    p = msg.get("params", {})
                    msg_type = p.get("type")
                    args = p.get("args", [])
                    text = " ".join(str(a.get("value", a.get("description", ""))) for a in args)
                    self.console_messages.append({"type": msg_type, "text": text})
                    if msg_type in ("error", "assert"):
                        self.console_errors.append(text)
                elif method == "Log.entryAdded":
                    entry = msg.get("params", {}).get("entry", {})
                    if entry.get("level") == "error":
                        self.console_errors.append(f"[{entry.get('source')}] {entry.get('text')}")
                elif method == "Network.requestWillBeSent":
                    p = msg.get("params", {})
                    req_id = p.get("requestId")
                    url = p.get("request", {}).get("url", "")
                    self.requests_sent[req_id] = url
                    if not (
                        url.startswith("http://127.0.0.1:8000")
                        or url.startswith("http://localhost:8000")
                        or url.startswith("data:")
                    ):
                        self.external_requests.append(url)
                elif method == "Network.responseReceived":
                    p = msg.get("params", {})
                    req_id = p.get("requestId")
                    resp = p.get("response", {})
                    self.responses_received[req_id] = {
                        "url": resp.get("url"),
                        "status": resp.get("status"),
                        "mimeType": resp.get("mimeType"),
                    }
                elif method == "Network.loadingFailed":
                    p = msg.get("params", {})
                    req_id = p.get("requestId")
                    err_text = p.get("errorText", "")
                    url = self.requests_sent.get(req_id, "unknown")
                    if not p.get("canceled", False):
                        self.requests_failed[req_id] = {"url": url, "error": err_text}
            return msg
        except Exception:
            return None

    def drain(self, duration: float = 1.0):
        start = time.time()
        while time.time() - start < duration:
            msg = self._read_frame(timeout=0.05)
            if not msg:
                time.sleep(0.02)

    def call(self, method: str, params: dict | None = None, timeout: float = 8.0) -> dict | None:
        target_id = self._send_cmd(method, params)
        start = time.time()
        while time.time() - start < timeout:
            msg = self._read_frame(timeout=0.5)
            if msg and msg.get("id") == target_id:
                if "error" in msg:
                    raise RuntimeError(f"CDP error: {msg['error']}")
                return msg.get("result")
        return None

    def eval_js(self, expression: str) -> any:
        res = self.call(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True,
            },
        )
        if res and "result" in res:
            return res["result"].get("value")
        return None

    def capture_screenshot(self, out_path: Path):
        res = self.call("Page.captureScreenshot", {"format": "png"})
        if res and "data" in res:
            png_bytes = base64.b64decode(res["data"])
            out_path.write_bytes(png_bytes)
            return len(png_bytes)
        raise RuntimeError("Failed to capture screenshot")


def main():
    chrome_port = 9226
    chrome_cmd = [
        CHROME_PATH,
        "--headless=new",
        f"--remote-debugging-port={chrome_port}",
        "--no-first-run",
        "--disable-gpu",
        "--window-size=1440,900",
        "about:blank",
    ]
    proc = subprocess.Popen(chrome_cmd)
    time.sleep(1.5)

    try:
        req = Request(f"http://127.0.0.1:{chrome_port}/json/new", method="PUT")
        with urlopen(req) as r:
            page_info = json.loads(r.read().decode("utf-8"))
        ws_url = page_info["webSocketDebuggerUrl"]

        client = CDPClient(ws_url)
        try:
            client.call("Page.enable")
            client.call("Runtime.enable")
            client.call("Network.enable")
            client.call("Log.enable")

            # Navigate
            print(f"Navigating to {BASE_URL}...")
            client.call("Page.navigate", {"url": BASE_URL})

            # Wait for load event and let network settle
            time.sleep(2.0)
            client.drain(2.0)

            ready_state = client.eval_js("document.readyState")
            title = client.eval_js("document.title")
            print(f"Page Title: {title}")
            print(f"Document readyState: {ready_state}")

            # Network inventory
            all_requests = []
            for req_id, url in client.requests_sent.items():
                resp = client.responses_received.get(req_id)
                failed = client.requests_failed.get(req_id)
                status = (
                    resp["status"]
                    if resp
                    else (
                        "FAILED"
                        if failed
                        else ("OPEN_SSE" if url.endswith("/events") else "PENDING")
                    )
                )
                all_requests.append(
                    {
                        "url": url,
                        "status": status,
                        "mime": resp.get("mimeType") if resp else None,
                    }
                )

            pending_requests = [r for r in all_requests if r["status"] == "PENDING"]
            failed_requests = [r for r in all_requests if r["status"] == "FAILED"]
            external_requests = list(client.external_requests)
            console_errors = list(client.console_errors)

            # Overview screenshot
            print("Capturing Overview view screenshot...")
            overview_size = client.capture_screenshot(OUTPUT_DIR / "overview_view.png")
            print(f"Saved ui_snapshot/overview_view.png ({overview_size} bytes)")

            # Switch to Landing view
            print("Switching to Landing view...")
            client.eval_js("document.getElementById('navLanding').click()")
            time.sleep(0.8)
            client.drain(0.8)
            landing_active = client.eval_js(
                "document.getElementById('viewLanding').classList.contains('active')"
            )
            print(f"Landing view active: {landing_active}")

            # Landing screenshot
            print("Capturing Landing view screenshot...")
            landing_size = client.capture_screenshot(OUTPUT_DIR / "landing_view.png")
            print(f"Saved ui_snapshot/landing_view.png ({landing_size} bytes)")

            # Document Fonts verification (Part C)
            print("Verifying document.fonts loading status...")
            fonts_info = client.eval_js("""
                Promise.all(Array.from(document.fonts).map(f => f.load())).then(() => {
                    const list = [];
                    document.fonts.forEach(f => {
                        list.push({
                            family: f.family,
                            weight: f.weight,
                            style: f.style,
                            status: f.status
                        });
                    });
                    return {
                        status: document.fonts.status,
                        count: document.fonts.size,
                        all_loaded: list.every(f => f.status === 'loaded'),
                        orbitron_check: document.fonts.check("16px Orbitron"),
                        jetbrains_check: document.fonts.check("14px 'JetBrains Mono'"),
                        space_grotesk_check: document.fonts.check("14px 'Space Grotesk'"),
                        fonts: list
                    };
                })
            """)
            f_status = fonts_info.get("status")
            f_count = fonts_info.get("count")
            print(f"document.fonts status: {f_status}, count: {f_count}")
            print(f"Orbitron font check: {fonts_info.get('orbitron_check')}")
            print(f"JetBrains Mono font check: {fonts_info.get('jetbrains_check')}")
            print(f"Space Grotesk font check: {fonts_info.get('space_grotesk_check')}")
            print(f"All declared fonts loaded: {fonts_info.get('all_loaded')}")
            for f in fonts_info.get("fonts", []):
                fam, wt = f.get("family"), f.get("weight")
                st, stat = f.get("style"), f.get("status")
                print(f"  - {fam} (weight {wt}, {st}): {stat}")

            # Strict Part C assertions
            assert fonts_info.get("all_loaded") is True, (
                f"All declared fonts must be loaded, got: {fonts_info}"
            )
            assert fonts_info.get("orbitron_check") is True, (
                "Orbitron font must be loaded in document.fonts"
            )
            assert fonts_info.get("jetbrains_check") is True, (
                "JetBrains Mono font must be loaded in document.fonts"
            )
            assert fonts_info.get("space_grotesk_check") is True, (
                "Space Grotesk font must be loaded in document.fonts"
            )
            assert len(external_requests) == 0, f"Found external requests: {external_requests}"
            assert len(console_errors) == 0, f"Found console errors: {console_errors}"

            summary = {
                "page_finished_loading": ready_state == "complete",
                "title": title,
                "document_fonts": fonts_info,
                "console_errors_count": len(console_errors),
                "console_errors": console_errors,
                "total_network_requests": len(all_requests),
                "network_requests": all_requests,
                "pending_requests_count": len(pending_requests),
                "pending_requests": pending_requests,
                "failed_requests_count": len(failed_requests),
                "failed_requests": failed_requests,
                "external_requests_count": len(external_requests),
                "external_requests": external_requests,
                "overview_snapshot_bytes": overview_size,
                "landing_snapshot_bytes": landing_size,
            }
            print("\n=== VERIFICATION RESULTS JSON ===")
            print(json.dumps(summary, indent=2))

        finally:
            client.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    main()
