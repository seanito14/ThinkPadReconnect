#!/usr/bin/env python3
"""
ThinkPad Reconnect — macOS Dock Utility
A local web-based status dashboard for Barrier, SSH tunnel, and SMB.
Zero external dependencies — uses only Python stdlib.
"""

import http.server
import json
import os
import signal
import socket
import subprocess
import threading
import webbrowser
import sys

# ─── Configuration ───────────────────────────────────────────────────────────
# All settings are configurable via environment variables.
# See README.md for details.

REMOTE_HOST       = os.environ.get("TPR_REMOTE_HOST", "192.168.1.100")
REMOTE_USER       = os.environ.get("TPR_REMOTE_USER", "user")
BARRIER_PORT      = int(os.environ.get("TPR_BARRIER_PORT", "24800"))
BARRIER_AGENT     = os.environ.get("TPR_BARRIER_AGENT", "com.github.barrier.server")
REMOTE_KM_SERVICE = os.environ.get("TPR_REMOTE_KM_SERVICE", "input-leap-client.service")
SSH_LOCAL_FWD     = os.environ.get("TPR_SSH_LOCAL_FWD", "11436:127.0.0.1:11434")
SSH_REMOTE_FWD    = os.environ.get("TPR_SSH_REMOTE_FWD", "18796:127.0.0.1:18789")
SSH_TUNNEL_CMD    = [
    "ssh", "-N", "-o", "ServerAliveInterval=30", "-o", "ServerAliveCountMax=3",
    "-L", SSH_LOCAL_FWD,
    "-R", SSH_REMOTE_FWD,
    f"{REMOTE_USER}@{REMOTE_HOST}"
]
SERVER_PORT = 0  # OS picks a free port

# ─── Status Check Functions ──────────────────────────────────────────────────

def check_barrier():
    try:
        out = subprocess.check_output(
            ["netstat", "-an"], stderr=subprocess.DEVNULL, timeout=5
        ).decode()
        for line in out.splitlines():
            if str(BARRIER_PORT) in line and "ESTABLISHED" in line:
                return {"status": "connected", "detail": "Client connected"}
        for line in out.splitlines():
            if str(BARRIER_PORT) in line and "LISTEN" in line:
                return {"status": "warning", "detail": "Listening, no client"}
        return {"status": "down", "detail": "Server not running"}
    except Exception as e:
        return {"status": "down", "detail": str(e)[:60]}


def check_ssh():
    try:
        out = subprocess.check_output(
            ["pgrep", "-f", f"ssh -N.*{REMOTE_HOST}"],
            stderr=subprocess.DEVNULL, timeout=3
        ).decode().strip()
        tunnel_running = bool(out)
    except Exception:
        tunnel_running = False

    try:
        subprocess.check_call(
            ["ssh", "-o", "ConnectTimeout=3", "-o", "BatchMode=yes",
             f"{REMOTE_USER}@{REMOTE_HOST}", "echo", "ok"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=6
        )
        reachable = True
    except Exception:
        reachable = False

    if tunnel_running and reachable:
        return {"status": "connected", "detail": "Tunnel active"}
    elif reachable:
        return {"status": "warning", "detail": "SSH OK, tunnel down"}
    elif tunnel_running:
        return {"status": "warning", "detail": "Tunnel proc exists, SSH unreachable"}
    else:
        return {"status": "down", "detail": "Unreachable"}


def check_smb():
    try:
        out = subprocess.check_output(["mount"], timeout=5).decode()
        for line in out.splitlines():
            if REMOTE_HOST in line and ("smbfs" in line or "cifs" in line):
                # Extract mount point
                parts = line.split(" on ")
                mount_point = parts[1].split(" (")[0] if len(parts) > 1 else "mounted"
                return {"status": "connected", "detail": mount_point}
        return {"status": "down", "detail": "No mount found"}
    except Exception as e:
        return {"status": "down", "detail": str(e)[:60]}


# ─── Reconnect Functions ─────────────────────────────────────────────────────

def reconnect_barrier():
    uid = os.getuid()
    msgs = []
    try:
        subprocess.run(
            ["launchctl", "kickstart", "-k", f"gui/{uid}/{BARRIER_AGENT}"],
            timeout=10, capture_output=True
        )
        msgs.append("Server restarted")
    except Exception:
        subprocess.run(["pkill", "-f", "barriers"], capture_output=True)
        msgs.append("Server killed (KeepAlive will restart)")

    try:
        subprocess.run(
            ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes",
             f"{REMOTE_USER}@{REMOTE_HOST}",
             "systemctl", "--user", "restart", REMOTE_KM_SERVICE],
            timeout=15, capture_output=True
        )
        msgs.append("Client restarted")
    except Exception:
        msgs.append("Could not restart client")
    return "; ".join(msgs)


def reconnect_ssh():
    try:
        subprocess.run(
            ["pkill", "-f", f"ssh -N.*{REMOTE_HOST}"],
            capture_output=True, timeout=5
        )
    except Exception:
        pass

    import time
    time.sleep(1)

    try:
        subprocess.Popen(
            SSH_TUNNEL_CMD,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        return "Tunnel re-established"
    except Exception as e:
        return f"Failed: {e}"


def reconnect_smb():
    try:
        subprocess.Popen(
            ["open", f"smb://{REMOTE_USER}@{REMOTE_HOST}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        return "SMB share opened in Finder"
    except Exception as e:
        return f"Failed: {e}"


# ─── HTML UI ──────────────────────────────────────────────────────────────────

HTML_PAGE = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ThinkPad Reconnect</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #0d1117;
    --bg-card: #161b22;
    --bg-card-hover: #1c2333;
    --border: #30363d;
    --fg: #e6edf3;
    --fg-dim: #7d8590;
    --green: #3fb950;
    --green-bg: rgba(63,185,80,0.12);
    --red: #f85149;
    --red-bg: rgba(248,81,73,0.12);
    --yellow: #d29922;
    --yellow-bg: rgba(210,153,34,0.12);
    --accent: #58a6ff;
    --purple: #bc8cff;
    --purple-bg: rgba(188,140,255,0.15);
    --radius: 12px;
  }

  * { margin: 0; padding: 0; box-sizing: border-box; }

  body {
    font-family: 'Inter', -apple-system, sans-serif;
    background: var(--bg);
    color: var(--fg);
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 24px 20px;
    -webkit-font-smoothing: antialiased;
  }

  .header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    max-width: 440px;
    margin-bottom: 20px;
  }

  .header h1 {
    font-size: 18px;
    font-weight: 700;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .header h1 .bolt {
    font-size: 22px;
    filter: drop-shadow(0 0 6px rgba(88,166,255,0.5));
  }

  .header .target {
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    color: var(--fg-dim);
    background: var(--bg-card);
    border: 1px solid var(--border);
    padding: 4px 10px;
    border-radius: 20px;
  }

  .card-container {
    width: 100%;
    max-width: 440px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 16px 18px;
    display: flex;
    align-items: center;
    gap: 14px;
    transition: all 0.2s ease;
    cursor: default;
  }

  .card:hover {
    background: var(--bg-card-hover);
    border-color: #444c56;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
  }

  .indicator {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
    transition: all 0.3s ease;
    box-shadow: 0 0 0 0 transparent;
  }

  .indicator.connected {
    background: var(--green);
    box-shadow: 0 0 8px rgba(63,185,80,0.5);
    animation: pulse-green 2s infinite;
  }

  .indicator.warning {
    background: var(--yellow);
    box-shadow: 0 0 8px rgba(210,153,34,0.5);
  }

  .indicator.down {
    background: var(--red);
    box-shadow: 0 0 8px rgba(248,81,73,0.4);
  }

  .indicator.checking {
    background: var(--fg-dim);
    animation: pulse-check 1s infinite;
  }

  @keyframes pulse-green {
    0%, 100% { box-shadow: 0 0 8px rgba(63,185,80,0.5); }
    50% { box-shadow: 0 0 14px rgba(63,185,80,0.8); }
  }

  @keyframes pulse-check {
    0%, 100% { opacity: 0.4; }
    50% { opacity: 1; }
  }

  .info {
    flex: 1;
    min-width: 0;
  }

  .info .name {
    font-size: 14px;
    font-weight: 600;
    margin-bottom: 2px;
  }

  .info .detail {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    color: var(--fg-dim);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .info .detail.connected { color: var(--green); }
  .info .detail.warning { color: var(--yellow); }
  .info .detail.down { color: var(--red); }

  .reconnect-btn {
    background: transparent;
    border: 1px solid var(--border);
    color: var(--fg-dim);
    font-size: 16px;
    width: 36px;
    height: 36px;
    border-radius: 10px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s ease;
    flex-shrink: 0;
  }

  .reconnect-btn:hover {
    background: var(--purple-bg);
    border-color: var(--purple);
    color: var(--purple);
    transform: rotate(90deg);
  }

  .reconnect-btn:active {
    transform: rotate(180deg) scale(0.95);
  }

  .reconnect-btn.spinning {
    animation: spin 1s linear infinite;
    color: var(--accent);
    border-color: var(--accent);
    pointer-events: none;
  }

  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }

  .reconnect-all {
    margin-top: 6px;
    width: 100%;
    max-width: 440px;
    background: linear-gradient(135deg, #1f0f3a, #1a1040);
    border: 1px solid #3d2866;
    color: var(--purple);
    font-family: 'Inter', sans-serif;
    font-size: 14px;
    font-weight: 600;
    padding: 12px;
    border-radius: var(--radius);
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
  }

  .reconnect-all:hover {
    background: linear-gradient(135deg, #2a1550, #231555);
    border-color: var(--purple);
    box-shadow: 0 4px 20px rgba(188,140,255,0.2);
    transform: translateY(-1px);
  }

  .reconnect-all:active {
    transform: translateY(0);
  }

  .footer {
    margin-top: 16px;
    font-size: 11px;
    color: var(--fg-dim);
    opacity: 0.5;
    text-align: center;
  }

  .toast {
    position: fixed;
    bottom: 20px;
    left: 50%;
    transform: translateX(-50%) translateY(80px);
    background: var(--bg-card);
    border: 1px solid var(--border);
    padding: 10px 20px;
    border-radius: 10px;
    font-size: 13px;
    color: var(--fg);
    box-shadow: 0 8px 24px rgba(0,0,0,0.4);
    transition: transform 0.3s ease;
    z-index: 100;
    font-family: 'JetBrains Mono', monospace;
  }

  .toast.show {
    transform: translateX(-50%) translateY(0);
  }
</style>
</head>
<body>

<div class="header">
  <h1><span class="bolt">⚡</span> ThinkPad Reconnect</h1>
  <span class="target">→ ''' + REMOTE_HOST + '''</span>
</div>

<div class="card-container">
  <div class="card" id="barrier-card">
    <div class="indicator checking" id="barrier-dot"></div>
    <div class="info">
      <div class="name">Barrier</div>
      <div class="detail" id="barrier-detail">Checking…</div>
    </div>
    <button class="reconnect-btn" onclick="reconnect('barrier')" id="barrier-btn" title="Reconnect Barrier">↻</button>
  </div>

  <div class="card" id="ssh-card">
    <div class="indicator checking" id="ssh-dot"></div>
    <div class="info">
      <div class="name">SSH Tunnel</div>
      <div class="detail" id="ssh-detail">Checking…</div>
    </div>
    <button class="reconnect-btn" onclick="reconnect('ssh')" id="ssh-btn" title="Reconnect SSH Tunnel">↻</button>
  </div>

  <div class="card" id="smb-card">
    <div class="indicator checking" id="smb-dot"></div>
    <div class="info">
      <div class="name">File Access</div>
      <div class="detail" id="smb-detail">Checking…</div>
    </div>
    <button class="reconnect-btn" onclick="reconnect('smb')" id="smb-btn" title="Reconnect File Access">↻</button>
  </div>
</div>

<button class="reconnect-all" onclick="reconnectAll()">
  <span>⟳</span> Reconnect All
</button>

<div class="footer">Auto-refresh every 10s · Port ''' + '${PORT}' + '''</div>

<div class="toast" id="toast"></div>

<script>
  function updateService(name, data) {
    const dot = document.getElementById(name + '-dot');
    const detail = document.getElementById(name + '-detail');
    
    dot.className = 'indicator ' + data.status;
    detail.textContent = data.detail;
    detail.className = 'detail ' + data.status;
  }

  async function fetchStatus() {
    try {
      const res = await fetch('/api/status');
      const data = await res.json();
      updateService('barrier', data.barrier);
      updateService('ssh', data.ssh);
      updateService('smb', data.smb);
    } catch (e) {
      ['barrier', 'ssh', 'smb'].forEach(name => {
        updateService(name, {status: 'down', detail: 'Server unreachable'});
      });
    }
  }

  async function reconnect(service) {
    const btn = document.getElementById(service + '-btn');
    btn.classList.add('spinning');
    
    try {
      const res = await fetch('/api/reconnect/' + service, {method: 'POST'});
      const data = await res.json();
      showToast(data.message || 'Reconnecting…');
      
      // Wait a bit then refresh
      setTimeout(() => {
        fetchStatus();
        btn.classList.remove('spinning');
      }, 4000);
    } catch (e) {
      showToast('Error: ' + e.message);
      btn.classList.remove('spinning');
    }
  }

  function reconnectAll() {
    reconnect('barrier');
    reconnect('ssh');
    reconnect('smb');
  }

  function showToast(msg) {
    const toast = document.getElementById('toast');
    toast.textContent = msg;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 3000);
  }

  // Initial fetch + auto-refresh
  fetchStatus();
  setInterval(fetchStatus, 10000);
</script>

</body>
</html>'''


# ─── HTTP Server ──────────────────────────────────────────────────────────────

class ReconnectHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress logs

    def _json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _html(self, content):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(content.encode())

    def do_GET(self):
        if self.path == "/":
            page = HTML_PAGE.replace("${PORT}", str(self.server.server_address[1]))
            self._html(page)
        elif self.path == "/api/status":
            barrier = check_barrier()
            ssh = check_ssh()
            smb = check_smb()
            self._json({"barrier": barrier, "ssh": ssh, "smb": smb})
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/api/reconnect/barrier":
            msg = reconnect_barrier()
            self._json({"message": msg})
        elif self.path == "/api/reconnect/ssh":
            msg = reconnect_ssh()
            self._json({"message": msg})
        elif self.path == "/api/reconnect/smb":
            msg = reconnect_smb()
            self._json({"message": msg})
        elif self.path == "/api/reconnect/all":
            msgs = []
            msgs.append(reconnect_barrier())
            msgs.append(reconnect_ssh())
            msgs.append(reconnect_smb())
            self._json({"message": "; ".join(msgs)})
        else:
            self.send_error(404)


def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    port = find_free_port()
    server = http.server.HTTPServer(("127.0.0.1", port), ReconnectHandler)

    print(f"ThinkPad Reconnect running at http://127.0.0.1:{port}")

    # Open browser
    webbrowser.open(f"http://127.0.0.1:{port}")

    # Handle Ctrl+C gracefully
    def handle_signal(sig, frame):
        print("\nShutting down…")
        server.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
