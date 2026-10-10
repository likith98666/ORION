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
        self.console_errors = []
        self.network_responses = []
        self.external_requests = []

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
                    if p.get("type") in ("error", "assert"):
                        args = p.get("args", [])
                        text = " ".join(str(a.get("value", a.get("description", ""))) for a in args)
                        self.console_errors.append(text)
                elif method == "Log.entryAdded":
                    entry = msg.get("params", {}).get("entry", {})
                    if entry.get("level") == "error":
                        self.console_errors.append(f"[{entry.get('source')}] {entry.get('text')}")
                elif method == "Network.requestWillBeSent":
                    url = msg.get("params", {}).get("request", {}).get("url", "")
                    if not (
                        url.startswith("http://127.0.0.1:8000")
                        or url.startswith("http://localhost:8000")
                        or url.startswith("data:")
                    ):
                        self.external_requests.append(url)
                elif method == "Network.responseReceived":
                    resp = msg.get("params", {}).get("response", {})
                    self.network_responses.append(
                        {
                            "url": resp.get("url"),
                            "status": resp.get("status"),
                            "mimeType": resp.get("mimeType"),
                            "headers": resp.get("headers", {}),
                        }
                    )
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
    chrome_port = 9227
    cmd = [
        CHROME_PATH,
        "--headless=new",
        f"--remote-debugging-port={chrome_port}",
        "--no-first-run",
        "--disable-gpu",
        "--window-size=1440,900",
        "about:blank",
    ]
    proc = subprocess.Popen(cmd)
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

            print(f"Navigating to {BASE_URL}...")
            client.call("Page.navigate", {"url": BASE_URL})

            time.sleep(2.0)
            client.drain(2.0)

            # Check document.fonts
            font_status_js = """
            (async () => {
                await document.fonts.ready;
                const loaded = [];
                for (const f of document.fonts) {
                    loaded.push({ family: f.family, weight: f.weight, status: f.status });
                }
                const hasOrbitron = loaded.some(
                    f => f.family.includes('Orbitron') && f.status === 'loaded'
                );
                const hasJetBrains = loaded.some(
                    f => f.family.includes('JetBrains Mono') && f.status === 'loaded'
                );
                return {
                    ready: true,
                    hasOrbitronLoaded: hasOrbitron,
                    hasJetBrainsLoaded: hasJetBrains,
                    loadedCount: loaded.length,
                    fonts: loaded
                };
            })()
            """
            font_status = client.eval_js(font_status_js)
            print("Document Fonts Status:", json.dumps(font_status, indent=2))

            # Inspect font responses in network traffic
            font_responses = [r for r in client.network_responses if ".woff2" in r["url"]]
            print(f"Font network responses count: {len(font_responses)}")
            for fr in font_responses:
                print(f"- {fr['url']} -> {fr['status']} (MIME: {fr['mimeType']})")

            # Verify requirements
            all_fonts_200 = all(fr["status"] == 200 for fr in font_responses)
            orbitron_loaded = bool(font_status and font_status.get("hasOrbitronLoaded"))
            jetbrains_loaded = bool(font_status and font_status.get("hasJetBrainsLoaded"))
            assert jetbrains_loaded, "JetBrains Mono not loaded"
            console_errors = client.console_errors
            external_requests = client.external_requests

            # Capture screenshot
            ss_size = client.capture_screenshot(OUTPUT_DIR / "theme_step1.png")
            print(f"Saved ui_snapshot/theme_step1.png ({ss_size} bytes)")

            report = {
                "font_responses_count": len(font_responses),
                "all_fonts_200": all_fonts_200,
                "orbitron_loaded": orbitron_loaded,
                "console_errors_count": len(console_errors),
                "console_errors": console_errors,
                "external_requests_count": len(external_requests),
                "external_requests": external_requests,
                "screenshot_bytes": ss_size,
            }
            print("\n=== STEP 1 VERIFICATION REPORT ===")
            print(json.dumps(report, indent=2))

            assert len(font_responses) > 0, "No font files were requested by browser!"
            assert all_fonts_200, f"Some fonts did not return 200: {font_responses}"
            assert orbitron_loaded, "Orbitron was not reported as loaded by document.fonts!"
            assert len(console_errors) == 0, f"Console errors found: {console_errors}"
            assert len(external_requests) == 0, f"External requests found: {external_requests}"
            print("\nSTEP 1 VERIFICATION PASSED COMPLETELY.")

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
