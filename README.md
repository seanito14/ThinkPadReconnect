# ⚡ ThinkPad Reconnect

A lightweight macOS dock utility that monitors and reconnects services between two machines — specifically designed for a **Barrier** (keyboard/mouse sharing), **SSH tunnel**, and **SMB file access** setup.

Zero external dependencies. Uses only Python standard library.

## Screenshot

Dark-themed web dashboard with animated status indicators, per-service reconnect buttons, and auto-refresh.

## Quick Start

```bash
# Configure for your setup
export TPR_REMOTE_HOST="192.168.1.100"
export TPR_REMOTE_USER="youruser"

# Launch
python3 reconnect.py
```

A browser tab opens automatically with the status dashboard.

## Configuration

All settings are configured via **environment variables**:

| Variable | Default | Description |
|---|---|---|
| `TPR_REMOTE_HOST` | `192.168.1.100` | IP address of the remote machine |
| `TPR_REMOTE_USER` | `user` | SSH username on the remote machine |
| `TPR_BARRIER_PORT` | `24800` | Barrier server port |
| `TPR_BARRIER_AGENT` | `com.github.barrier.server` | macOS LaunchAgent label for Barrier server |
| `TPR_REMOTE_KM_SERVICE` | `input-leap-client.service` | systemd user service for keyboard/mouse client on remote |
| `TPR_SSH_LOCAL_FWD` | `11436:127.0.0.1:11434` | SSH local port forward (`-L` flag) |
| `TPR_SSH_REMOTE_FWD` | `18796:127.0.0.1:18789` | SSH remote port forward (`-R` flag) |

### Example `.env` setup (add to `~/.zshrc` or `~/.bashrc`)

```bash
export TPR_REMOTE_HOST="192.168.2.50"
export TPR_REMOTE_USER="john"
export TPR_BARRIER_PORT="24800"
export TPR_SSH_LOCAL_FWD="8080:127.0.0.1:8080"
export TPR_SSH_REMOTE_FWD="9090:127.0.0.1:9090"
```

## macOS Dock App

A `.app` bundle is included for Dock integration:

```bash
# Double-click ThinkPadReconnect.app, or:
open ThinkPadReconnect.app
```

Drag `ThinkPadReconnect.app` to your Dock for one-click access.

## Services Managed

### 1. Barrier (Keyboard & Mouse Sharing)

- **Checks**: `netstat` for ESTABLISHED connections on the configured port
- **Reconnects**: Restarts the macOS LaunchAgent server + SSH-restarts the remote systemd client service

### 2. SSH Tunnel

- **Checks**: Process grep for active tunnel + SSH reachability test
- **Reconnects**: Kills stale tunnel process, re-establishes with configured port forwards

### 3. File Access (SMB)

- **Checks**: `mount` output for active SMB mounts from the remote host
- **Reconnects**: Opens `smb://user@host` in Finder

## Architecture

```
reconnect.py              ← Single-file app (Python stdlib only)
├── http.server            ← Localhost web server on random port
├── Embedded HTML/CSS/JS   ← Dark-themed dashboard UI
├── GET  /api/status       ← JSON status for all 3 services
└── POST /api/reconnect/*  ← Trigger reconnect per service
```

## Prerequisites

- **macOS** with `/usr/bin/python3` (ships with macOS)
- **Passwordless SSH** to the remote machine (key-based auth)
- **Barrier** server configured as a LaunchAgent on macOS
- **Barrier/Input Leap** client configured as a systemd user service on the remote machine

## License

MIT
