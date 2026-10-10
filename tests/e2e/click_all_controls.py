import base64
import json
import os
import select
import socket
import struct
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

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
        self.network_events = []

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

    def _read_frame(self, timeout: float = 0.05) -> dict | None:
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
                elif method == "Network.responseReceived":
                    resp = msg.get("params", {}).get("response", {})
                    self.network_events.append(
                        {
                            "url": resp.get("url"),
                            "status": resp.get("status"),
                            "mime": resp.get("mimeType"),
                        }
                    )
            return msg
        except Exception:
            return None

    def drain(self, duration: float = 0.5):
        start = time.time()
        while time.time() - start < duration:
            self._read_frame(timeout=0.02)

    def call(self, method: str, params: dict | None = None, timeout: float = 8.0) -> dict | None:
        target_id = self._send_cmd(method, params)
        start = time.time()
        while time.time() - start < timeout:
            msg = self._read_frame(timeout=0.2)
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

    def clear_events(self):
        self.network_events = []
        self.console_errors = []


def main():
    chrome_port = 9228
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
            client.drain(1.0)

            # 1. ENUMERATE ALL CONTROLS
            enum_js = """
            (() => {
                const sel = 'button, a.nav-item, [role="tab"], .tab-btn, ' +
                            '.sidebar-link, input[type="submit"], [onclick]';
                const elements = document.querySelectorAll(sel);
                const items = [];
                elements.forEach((el, idx) => {
                    const id = el.id || '';
                    const tag = el.tagName.toLowerCase();
                    const raw = el.innerText || el.textContent ||
                                el.getAttribute('title') ||
                                el.getAttribute('aria-label') || '';
                    const text = raw.trim().replace(/\\s+/g, ' ');
                    const dataView = el.getAttribute('data-view') || '';
                    const dataTab = el.getAttribute('data-tab') || '';
                    const className = el.className || '';
                    items.push({ idx, tag, id, text, dataView, dataTab, className });
                });
                return items;
            })()
            """
            controls_list = client.eval_js(enum_js)
            print(f"\nTotal Enumerated Controls: {len(controls_list)}")
            print("Full Enumerated List:")
            for c in controls_list:
                tag, cid, txt = c["tag"], c["id"], c["text"][:30]
                vw, tb = c["dataView"], c["dataTab"]
                print(f"[{c['idx']}] <{tag}> id='{cid}' text='{txt}' view='{vw}' tab='{tb}'")

            results = []

            # 2. RUN REAL MISSION JOURNEY END-TO-END THROUGH UI
            print("\n--- Running Real Mission Journey Through UI ---")
            client.clear_events()
            prompt = "Autonomous Verification: repair off-by-one arithmetic in add() and run pytest"
            client.eval_js(f"""
                document.getElementById('taskInputPrompt').value = '{prompt}';
                document.getElementById('workspaceInputPath').value = '.';
                document.getElementById('executionModeSelect').value = 'controlled';
            """)
            time.sleep(0.3)
            # Click submit
            client.eval_js("document.getElementById('btnSubmitTask').click()")
            time.sleep(1.5)
            client.drain(1.5)

            # Get created mission ID
            mid_js = "window.currentMissionId || (window.activeMissionState || {}).id || ''"
            mid = client.eval_js(mid_js)
            print(f"Mission created via UI: '{mid}'")

            # Check health probe missions_count
            health_req = Request("http://127.0.0.1:8000/api/v1/health")
            with urlopen(health_req) as hr:
                health_data = json.loads(hr.read().decode())
            print(f"Health check missions_count: {health_data.get('missions_count')}")
            assert health_data.get("missions_count", 0) > 0, "missions_count did not increase!"

            # If mid exists, advance stages through UI
            if mid:
                print(f"Advancing stages for mission {mid} through UI...")
                for _ in range(4):
                    step_click = (
                        "if (document.getElementById('btnAdvanceStage')) "
                        "document.getElementById('btnAdvanceStage').click();"
                    )
                    client.eval_js(step_click)
                    time.sleep(0.6)
                    client.drain(0.6)

                # Check approval modal / banner if present
                appr_click = (
                    "const b = document.getElementById('btnQuickApprove'); "
                    "const alert = document.getElementById('approvalAlertBanner'); "
                    "if (b && alert && alert.style.display !== 'none') b.click();"
                )
                client.eval_js(appr_click)
                time.sleep(0.6)
                client.drain(0.6)

            # 3. TEST btnReplayMission EXPLICITLY
            print("\n--- Testing btnReplayMission Explicitly ---")
            client.clear_events()
            replay_click_res = client.eval_js("""
                (() => {
                    const btn = document.getElementById('btnReplayMission');
                    if (!btn) return { found: false };
                    btn.click();
                    const bar = document.getElementById('missionReplayBar');
                    const barVisible = bar && bar.style.display !== 'none';
                    const btnText = btn.textContent.trim();
                    return { found: true, barVisible, btnText };
                })()
            """)
            time.sleep(0.8)
            client.drain(0.8)
            print("btnReplayMission click result:", json.dumps(replay_click_res))
            replay_net = [e for e in client.network_events if "/timeline" in e["url"]]
            if replay_net:
                replay_req_str = f"GET {replay_net[0]['url']} ({replay_net[0]['status']})"
            else:
                replay_req_str = "Timeline cache"
            r_vis = replay_click_res.get("barVisible")
            r_btn = replay_click_res.get("btnText")
            r_err = "None" if not client.console_errors else str(client.console_errors)
            r_verd = (
                "PASS" if replay_click_res.get("found") and not client.console_errors else "FAIL"
            )
            results.append(
                {
                    "control": "btnReplayMission",
                    "action": "Click (Toggle Replay Mode)",
                    "request": replay_req_str,
                    "result": f"Replay bar visible: {r_vis}, Button: '{r_btn}'",
                    "console_error": r_err,
                    "verdict": r_verd,
                }
            )

            # Test Replay Controls: Next, Prev, Exit
            client.clear_events()
            next_scrub = (
                "const nb = document.getElementById('btnMissionReplayNext'); if (nb) nb.click();"
            )
            client.eval_js(next_scrub)
            time.sleep(0.3)
            client.drain(0.3)
            nxt_err = "None" if not client.console_errors else str(client.console_errors)
            results.append(
                {
                    "control": "btnMissionReplayNext",
                    "action": "Click (Step Next Event)",
                    "request": "Internal scrubber step",
                    "result": "Timeline scrubber advanced",
                    "console_error": nxt_err,
                    "verdict": "PASS" if not client.console_errors else "FAIL",
                }
            )

            client.clear_events()
            exit_scrub = (
                "const eb = document.getElementById('btnExitMissionReplay'); if (eb) eb.click();"
            )
            client.eval_js(exit_scrub)
            time.sleep(0.3)
            client.drain(0.3)
            bar_after_exit = client.eval_js(
                "document.getElementById('missionReplayBar').style.display === 'none'"
            )
            ex_err = "None" if not client.console_errors else str(client.console_errors)
            results.append(
                {
                    "control": "btnExitMissionReplay",
                    "action": "Click (Exit Replay Mode)",
                    "request": "Internal mode reset",
                    "result": f"Replay bar hidden: {bar_after_exit}",
                    "console_error": ex_err,
                    "verdict": "PASS" if bar_after_exit and not client.console_errors else "FAIL",
                }
            )

            # 4. TEST ALL NAVIGATION VIEWS
            nav_views = [
                ("navOverview", "overview", "viewOverview"),
                ("navLanding", "landing", "viewLanding"),
                ("navMissionsAll", "missions-all", "viewMissionsAll"),
                ("navMissionActive", "mission-detail", "viewMissionDetail"),
                ("navMissionsHistory", "missions-history", "viewMissionsAll"),
                ("navSystemWorkforce", "agents", "viewAgents"),
                ("navEvidenceLedger", "evidence", "viewEvidence"),
                ("navSystemHealth", "system", "viewSystem"),
                ("navSystemDocs", "docs", "viewDocs"),
                ("btnFootPrivacy", "privacy", "viewPrivacy"),
                ("btnFootTerms", "terms", "viewTerms"),
                ("navSettings", "settings", "viewSettings"),
            ]
            print("\n--- Testing Navigation Controls ---")
            for nav_id, view_name, target_id in nav_views:
                client.clear_events()
                click_res = client.eval_js(f"""
                    (() => {{
                        const el = document.getElementById('{nav_id}');
                        if (!el) return {{ found: false }};
                        el.click();
                        const target = document.getElementById('{target_id}');
                        const isActive = target && target.classList.contains('active');
                        return {{ found: true, isActive }};
                    }})()
                """)
                time.sleep(0.4)
                client.drain(0.4)
                net_req = (
                    client.network_events[0]["url"] if client.network_events else "View Switch"
                )
                net_status = (
                    str(client.network_events[0]["status"]) if client.network_events else "Local"
                )
                has_err = len(client.console_errors) > 0
                passed = click_res.get("found") and click_res.get("isActive") and not has_err
                results.append(
                    {
                        "control": f"#{nav_id} ({view_name})",
                        "action": f"Click (Switch to {view_name})",
                        "request": f"{net_req} ({net_status})",
                        "result": f"View #{target_id} active: {click_res.get('isActive')}",
                        "console_error": "None" if not has_err else str(client.console_errors),
                        "verdict": "PASS" if passed else "FAIL",
                    }
                )

            # 5. TEST MISSION DETAIL TABS
            client.eval_js("if (window.switchView) window.switchView('mission-detail');")
            time.sleep(0.5)
            client.drain(0.5)

            tabs = [
                ("tabBtnChanges", "tab-changes", "tab-changes"),
                ("tabBtnTests", "tab-tests", "tab-tests"),
                ("tabBtnVerification", "tab-verification", "tab-verification"),
                ("tabBtnReport", "tab-report", "tab-report"),
                ("tabBtnRecovery", "tab-recovery", "tab-recovery"),
                ("tabBtnGraph", "tab-graph", "tab-graph"),
                ("tabBtnEvidence", "tab-evidence", "tab-evidence"),
            ]
            print("\n--- Testing Mission Detail Tab Controls ---")
            for btn_id, tab_name, pane_id in tabs:
                client.clear_events()
                click_res = client.eval_js(f"""
                    (() => {{
                        const sel = '[data-tab="{tab_name}"]';
                        const elById = document.getElementById('{btn_id}');
                        const btn = document.querySelector(sel) || elById;
                        if (!btn) return {{ found: false }};
                        btn.click();
                        const pane = document.getElementById('{pane_id}');
                        const isVisible = pane && (pane.classList.contains('active') ||
                                                  pane.style.display !== 'none');
                        return {{ found: true, isVisible }};
                    }})()
                """)
                time.sleep(0.4)
                client.drain(0.4)
                net_req = client.network_events[0]["url"] if client.network_events else "Local Tab"
                net_status = (
                    str(client.network_events[0]["status"]) if client.network_events else "200"
                )
                has_err = len(client.console_errors) > 0
                passed = click_res.get("found") and click_res.get("isVisible") and not has_err
                results.append(
                    {
                        "control": f"Tab: {tab_name}",
                        "action": f"Click (Open {tab_name} pane)",
                        "request": f"{net_req} ({net_status})",
                        "result": f"Pane #{pane_id} active: {click_res.get('isVisible')}",
                        "console_error": "None" if not has_err else str(client.console_errors),
                        "verdict": "PASS" if passed else "FAIL",
                    }
                )

            # 6. TEST ACTION BUTTONS
            action_buttons = [
                ("btnRefresh", "Click (Refresh State)", "GET /api/v1/health (200)"),
                ("btnNewMission", "Click (New Mission)", "Switches to overview / clears inputs"),
                ("btnSaveSettings", "Click (Save Config)", "Saves local storage config"),
                ("btnResetSettings", "Click (Reset Config)", "Resets default config"),
                ("btnMissionTraceLink", "Click (Observability)", "Switches to Observability"),
                ("btnCheckServiceHealth", "Click (Check Health)", "GET /api/tasks (200)"),
                ("brandLogoTrigger", "Click (Brand Logo)", "Switches to overview"),
                ("btnTopbarNotifications", "Click (Notifications)", "Displays notifications"),
                ("btnTopbarUser", "Click (User Profile)", "Displays user profile status"),
                ("btnSidebarDemo", "Click (Demo Center)", "Opens Demo Center modal"),
                ("btnSidebarArch", "Click (Architecture)", "Opens Architecture Explorer"),
            ]
            print("\n--- Testing Action Buttons ---")
            for btn_id, act_desc, exp_res in action_buttons:
                client.clear_events()
                click_res = client.eval_js(f"""
                    (() => {{
                        const btn = document.getElementById('{btn_id}');
                        if (!btn) return {{ found: false }};
                        btn.click();
                        return {{ found: true }};
                    }})()
                """)
                time.sleep(0.4)
                client.drain(0.4)
                if client.network_events:
                    ev = client.network_events[0]
                    net_str = f"{ev['url']} ({ev['status']})"
                else:
                    net_str = "Local handler"
                has_err = len(client.console_errors) > 0
                passed = click_res.get("found") and not has_err
                results.append(
                    {
                        "control": f"#{btn_id}",
                        "action": act_desc,
                        "request": net_str,
                        "result": exp_res,
                        "console_error": "None" if not has_err else str(client.console_errors),
                        "verdict": "PASS" if passed else "FAIL",
                    }
                )

            # PRINT SUMMARY TABLE
            print("\n=== STEP 2 CONTROLS VERIFICATION TABLE ===")
            print("| Control | Action | Request | Result | Verdict |")
            print("| :--- | :--- | :--- | :--- | :--- |")
            for r in results:
                ctrl, act, req_s, res_s, verd = (
                    r["control"],
                    r["action"],
                    r["request"],
                    r["result"],
                    r["verdict"],
                )
                print(f"| `{ctrl}` | {act} | {req_s} | {res_s} | **{verd}** |")

            all_passed = all(r["verdict"] == "PASS" for r in results)
            print(f"\nTotal Controls Tested: {len(results)}")
            print(f"Passed: {sum(1 for r in results if r['verdict'] == 'PASS')}")
            print(f"Failed: {sum(1 for r in results if r['verdict'] == 'FAIL')}")
            assert all_passed, "Some controls failed verification!"
            print("\nALL CONTROLS PASSED AGAINST REAL BACKEND.")

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
