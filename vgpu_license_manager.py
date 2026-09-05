#!/usr/bin/env python3
"""
vGPU License Manager — GUI for NVIDIA Local Trusted Store (nvlts)
=================================================================
Manages vGPU licenses via the `nvlts` utility:
  https://git.collinwebdesigns.de/vgpu/nvlts

What it does
------------
* Shows all license editions (vWS / vPC / vApps / vCS / vGaming + Legacy)
  with ProductName / FeatureName / FeatureVersion.
* Checks current NVIDIA vGPU license status via `nvidia-smi -q`,
  filtering lines containing "License" (equivalent of
  Linux `nvidia-smi -q | grep "License"` and
  Windows `& 'nvidia-smi' -q | Select-String "License"`).
  OS is auto-detected so the right command/paths are used.
* Issues a PERMANENT license by running:
      nvlts -g -c <config.json> [-r] [-debug]
  The expiry is hard-coded in nvlts to 3000-12-31, so every
  license this tool issues is permanent — no extra flag needed.

README vs CODE — discrepancies found & handled
----------------------------------------------
1. DEFAULT BUILD IS PERMANENT (no `net` tag). `.goreleaser.yml` builds
   with plain `go build`, i.e. `schema_node_locked.go` (`//go:build !net`).
   That path writes an EMPTY `nvlts.lic` + a trusted store whose lease
   `expires = "3000-12-31T23:59:59.069621"`. The `net`-tagged build
   (`schema_net.go`, JWT ClientConfigToken, expiry 2099,
   CONCURRENT_COUNTED_SINGLE) is NOT in the releases. This tool targets
   the release build (permanent / node-locked). README never mentions tags.
2. `generate()` NEVER creates TS_DIRECTORY. `encrypt()` calls
   `os.MkdirAll(TS_DIRECTORY)` but `generate()` does not, so a fresh
   machine fails to write. -> This tool pre-creates the directory.
3. Default `-c config.json` DOES NOT EXIST. Releases only ship
   `configs/*.json`. You must always pass `-c`. -> This tool always
   passes an explicit `-c` (writes a temp config from the GUI fields).
4. `-r` is OS-specific, README only names Windows. Linux runs
   `systemctl restart nvidia-gridd`; Windows runs
   `Restart-Service NVDisplay.ContainerLocalSystem`. Handled by OS check.
5. `TrustedStore.Expires` is never populated from JSON (Config struct has
   no such field), so expiry is ALWAYS the permanent 3000 date. README
   doesn't document this — surfaced in the GUI as "Permanent".
6. Fingerprinting: MAC list + machine-id (Linux `/sys/class/dmi/id/
   product_uuid`, Windows `HKLM\\SOFTWARE\\Microsoft\\Cryptography\\
   MachineGuid`) + IPs/hostname/GPU/CPU/hypervisor. Changing NICs
   invalidates the license — warned in the GUI.

Requirements
------------
* Python 3.8+ with tkinter (stdlib, no pip packages needed).
* `nvlts` binary (auto-detected from ./source/ releases, /opt/nvlts,
  PATH, or pick manually) + `nvidia-smi` guest driver installed.
* Run as Administrator (Windows) / root (Linux) to write the trusted
  store and restart the service.

Tested logic against nvlts v1.0.3 source.
"""

import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
import traceback
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

APP_TITLE = "vGPU License Manager  (nvlts GUI)"
APP_VERSION = "1.1.0"
PERMANENT_EXPIRY_LABEL = "3000-12-31  (permanent)"
NVLTS_UPSTREAM = "https://git.collinwebdesigns.de/vgpu/nvlts"

IS_WINDOWS = platform.system().lower() == "windows"
IS_LINUX = platform.system().lower() == "linux"
OS_LABEL = platform.system() or "Unknown"

# Trusted-store + sidecar locations mirror main_linux.go / main_windows.go
# and node_locked_license/config_*.go + client_configuration_token/config_*.go
if IS_WINDOWS:
    TS_DIRECTORY = Path(r"C:/Program Files/NVIDIA Corporation/vGPU Licensing/TrustedStorage")
    TS_ENCRYPTED_FILE = TS_DIRECTORY / "NGUgNGMgNTMgMzEgMmUgMzA"
    TS_TAG_FILE = TS_DIRECTORY / "DataStore.bin"
    NLL_FILE = Path(r"C:/Program Files/NVIDIA Corporation/vGPU Licensing/License/nvlts.lic")
    CCT_FILE = Path(r"C:/Program Files/NVIDIA Corporation/vGPU Licensing/ClientConfigToken/client_configuration_token_nvlts.tok")
    RESTART_HINT = "Restart-Service NVDisplay.ContainerLocalSystem"
else:
    TS_DIRECTORY = Path("/var/lib/nvidia/vGPULicensing")
    TS_ENCRYPTED_FILE = TS_DIRECTORY / "NGUgNGMgNTMgMzEgMmUgMzA"
    TS_TAG_FILE = TS_DIRECTORY / "DataStore.bin"
    NLL_FILE = Path("/etc/nvidia/vGPULicense/nvlts.lic")
    CCT_FILE = Path("/etc/nvidia/ClientConfigToken/client_configuration_token_nvlts.tok")
    RESTART_HINT = "systemctl restart nvidia-gridd"

# License catalog — mirrors configs/*.json from nvlts v1.0.3.
# ProductName + FeatureName MUST match the driver; FeatureVersion ships
# as-is. Guest/Host driver versions are editable in the GUI.
LICENSE_CATALOG = {
    "vWS (Recommended)": {
        "file": "vWS.json",
        "product": "NVIDIA RTX Virtual Workstation",
        "feature": "Quadro-Virtual-DWS",
        "version": "5.0",
        "desc": "Full workstation: CUDA, OpenGL, ISV apps. The one most homelab / vGPU users want.",
        "badge": "MOST POPULAR",
    },
    "vPC": {
        "file": "vPC.json",
        "product": "NVIDIA Virtual PC",
        "feature": "GRID-Virtual-PC",
        "version": "2.0",
        "desc": "Virtual desktops with standard PC graphics and productivity apps.",
        "badge": "",
    },
    "vApps": {
        "file": "vApps.json",
        "product": "NVIDIA Virtual Applications",
        "feature": "GRID-Virtual-Apps",
        "version": "3.0",
        "desc": "Application remoting / session-host (RDSH) deployments.",
        "badge": "",
    },
    "vCS": {
        "file": "vCS.json",
        "product": "NVIDIA Virtual Compute Server",
        "feature": "NVIDIA-vComputeServer",
        "version": "9.0",
        "desc": "Headless compute (no graphics): AI/ML, HPC batch workers.",
        "badge": "",
    },
    "vGaming": {
        "file": "vGaming.json",
        "product": "NVIDIA vGaming",
        "feature": "GRID-vGaming",
        "version": "8.0",
        "desc": "Cloud-gaming profiles with game-optimized scheduling.",
        "badge": "",
    },
    "Legacy Quadro vDWS": {
        "file": "Legacy_Quadro_vDWS.json",
        "product": "Quadro Virtual Data Center Workstation",
        "feature": "Quadro-Virtual-DWS",
        "version": "5.0",
        "desc": "Legacy name for vWS on older (pre-Ampere-era) guest drivers.",
        "badge": "LEGACY",
    },
    "Legacy GRID vWS": {
        "file": "Legacy_GRID_vWS.json",
        "product": "GRID Virtual Workstation",
        "feature": "GRID-Virtual-WS",
        "version": "2.0",
        "desc": "Legacy workstation naming for old GRID drivers.",
        "badge": "LEGACY",
    },
    "Legacy GRID vPC": {
        "file": "Legacy_GRID_vPC.json",
        "product": "GRID Virtual PC",
        "feature": "GRID-Virtual-PC",
        "version": "2.0",
        "desc": "Legacy PC naming for old GRID drivers.",
        "badge": "LEGACY",
    },
    "Legacy GRID vApps": {
        "file": "Legacy_GRID_vApps.json",
        "product": "GRID Virtual Applications",
        "feature": "GRID-Virtual-Apps",
        "version": "3.0",
        "desc": "Legacy app-remoting naming for old GRID drivers.",
        "badge": "LEGACY",
    },
    "Legacy GRID vGaming": {
        "file": "Legacy_GRID_vGaming.json",
        "product": "GRID vGaming",
        "feature": "GRID-vGaming",
        "version": "8.0",
        "desc": "Legacy gaming naming for old GRID drivers.",
        "badge": "LEGACY",
    },
}

DEFAULT_GUEST_DRIVER = "572.83"
DEFAULT_HOST_DRIVER = "570.133.10"

NVIDIA_GREEN = "#76B900"
NEON_GREEN = "#9dff3f"
GLOW_CYAN = "#59d6ff"
GLOW_VIOLET = "#9b7bff"

# Glassmorphism palette — deep indigo night + frosted-glass cards.
# (tkinter has no real blur, so frosted glass is simulated with layered
# translucent-look panels, luminous borders, and ambient glow blobs.)
DARK_BG = "#0e1030"        # night gradient base
DARK_BG_DEEP = "#080a22"   # gradient shadow end
DARK_PANEL = "#232a52"     # frosted glass card
DARK_CARD = "#1b2145"      # frosted glass inset / inputs
GLASS_EDGE = "#8f96ff"     # luminous card border
GLASS_EDGE_DIM = "#4a5290" # dim border for nested widgets
LIGHT_FG = "#f2f4ff"
MUTED_FG = "#a9b0d8"
HEADER_GRAD_TOP = "#2b3370"
HEADER_GRAD_BOT = "#141943"


# ---------------------------------------------------------------------------
# OS / environment helpers
# ---------------------------------------------------------------------------

def script_dir() -> Path:
    try:
        return Path(__file__).resolve().parent
    except NameError:
        return Path.cwd()


def is_admin() -> bool:
    """True if we can write the trusted store (admin / root)."""
    try:
        if IS_WINDOWS:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        return os.geteuid() == 0
    except Exception:
        return False


def find_nvidia_smi() -> Path | None:
    found = shutil.which("nvidia-smi")
    if found:
        return Path(found)
    candidates = []
    if IS_WINDOWS:
        candidates = [
            Path(r"C:\Windows\System32\nvidia-smi.exe"),
            Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
            / "NVIDIA Corporation" / "NVSMI" / "nvidia-smi.exe",
        ]
    else:
        candidates = [
            Path("/usr/bin/nvidia-smi"),
            Path("/usr/local/bin/nvidia-smi"),
        ]
    for c in candidates:
        if c.exists():
            return c
    return None


def find_nvlts_binary() -> Path | None:
    """Search PATH + well-known locations incl. bundled ./source/ releases."""
    found = shutil.which("nvlts") or shutil.which("nvlts.exe")
    if found:
        return Path(found)
    base = script_dir()
    candidates = [
        base / ("nvlts.exe" if IS_WINDOWS else "nvlts"),
        base / "source" / "nvlts_1.0.3_windows_amd64" / "nvlts.exe",
        base / "source" / "nvlts-v1.0.3" / ("nvlts.exe" if IS_WINDOWS else "nvlts"),
        base / "source" / "nvlts" / ("nvlts.exe" if IS_WINDOWS else "nvlts"),
        Path("/opt/nvlts/nvlts"),
        Path("/usr/local/bin/nvlts"),
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return c
    return None


def find_configs_dir() -> Path | None:
    base = script_dir()
    candidates = [
        base / "configs",
        base / "source" / "nvlts-v1.0.3" / "configs",
        base / "source" / "nvlts_1.0.3_windows_amd64" / "configs",
        Path("/opt/nvlts/configs"),
    ]
    for c in candidates:
        if c.is_dir() and any(c.glob("*.json")):
            return c
    return None


def load_config_file(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def run_cmd(cmd: list[str], timeout: int = 60) -> tuple[int, str, str]:
    """Run a command, return (returncode, stdout, stderr) without shell."""
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            errors="replace",
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except FileNotFoundError as exc:
        return 127, "", str(exc)
    except subprocess.TimeoutExpired:
        return 124, "", f"Timed out after {timeout}s: {' '.join(cmd)}"
    except Exception as exc:  # noqa: BLE001
        return 1, "", str(exc)


def query_license_status(timeout: int = 30) -> tuple[bool, str]:
    """Mirror `nvidia-smi -q | grep License` / `| Select-String License`.

    Returns (ok, report). Filtering is done in Python so both OSes behave
    identically; the equivalent native commands are shown in the report.
    """
    smi = find_nvidia_smi()
    native = (
        "& 'nvidia-smi' -q | Select-String \"License\"" if IS_WINDOWS
        else "nvidia-smi -q | grep \"License\""
    )
    if smi is None:
        return False, (
            "nvidia-smi NOT FOUND on PATH.\n"
            f"Equivalent command would be: {native}\n"
            "Install the NVIDIA vGPU guest driver first, then retry."
        )
    rc, out, err = run_cmd([str(smi), "-q"], timeout=timeout)
    if rc != 0 or not out.strip():
        detail = (err or out).strip() or f"exit code {rc}"
        return False, f"nvidia-smi -q failed ({smi}):\n{detail}"
    lines = out.splitlines()
    hits = [ln for ln in lines if "License" in ln]  # same as grep/Select-String
    header = (
        f"OS: {OS_LABEL}  |  nvidia-smi: {smi}\n"
        f"Filter (= {native}): {len(hits)} matching line(s)\n"
        + "-" * 64
    )
    if not hits:
        return True, header + "\n(No lines containing 'License' — driver may be unlicensed / too old.)\n"
    # Highlight the most useful line if present
    body = "\n".join(hits)
    full = header + "\n" + body
    # Append a small interpretation hint
    lowered = body.lower()
    if "licensed" in lowered and "unlicensed" not in lowered:
        full += "\n" + "-" * 64 + "\nHint: output mentions 'Licensed' — check expiry/product lines above."
    elif "unlicensed" in lowered:
        full += "\n" + "-" * 64 + "\nHint: guest reports UNLICENSED — apply a permanent license below."
    return True, full


def query_driver_version(timeout: int = 20) -> str:
    smi = find_nvidia_smi()
    if smi is None:
        return ""
    rc, out, _ = run_cmd(
        [str(smi), "--query-gpu=driver_version", "--format=csv,noheader"],
        timeout=timeout,
    )
    if rc == 0 and out.strip():
        return out.strip().splitlines()[0].strip()
    return ""


def fingerprint_info() -> str:
    """Best-effort NIC/host fingerprint (what nvlts binds the license to)."""
    import socket
    import uuid
    lines: list[str] = []
    try:
        lines.append(f"Hostname: {socket.gethostname()}")
    except Exception:
        pass
    try:
        mac = ":".join(f"{(uuid.getnode() >> i) & 0xFF:02x}" for i in range(40, -8, -8))
        lines.append(f"Primary MAC (uuid.getnode): {mac}")
    except Exception:
        pass
    # Machine ID per platform (mirrors utils_linux.go / utils_windows.go)
    try:
        if IS_WINDOWS:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography"
            ) as key:
                guid, _ = winreg.QueryValueEx(key, "MachineGuid")
                lines.append(f"MachineGuid (registry): {guid}")
        else:
            for p in ("/sys/class/dmi/id/product_uuid", "/etc/machine-id"):
                if os.path.exists(p):
                    try:
                        lines.append(f"{p}: {Path(p).read_text().strip()}")
                    except Exception:
                        pass
    except Exception as exc:  # noqa: BLE001
        lines.append(f"Machine ID read failed: {exc}")
    try:
        import ipaddress  # noqa: F401  (documents intent; stdlib only)
        hostname = socket.gethostname()
        _, _, addrs = socket.gethostbyname_ex(hostname)
        if addrs:
            lines.append("IP(s): " + ", ".join(addrs))
    except Exception:
        pass
    lines.append("")
    lines.append("WARNING: changing/adding/removing NICs (incl. VPN TAP adapters)")
    lines.append("invalidates the nvlts credential — re-apply after NIC changes.")
    return "\n".join(lines)


def ensure_writable_dirs() -> tuple[bool, str]:
    """Workaround for nvlts generate() missing MkdirAll (see docstring #2)."""
    notes: list[str] = []
    try:
        TS_DIRECTORY.mkdir(parents=True, exist_ok=True)
        notes.append(f"OK: {TS_DIRECTORY}")
    except Exception as exc:  # noqa: BLE001
        return False, f"Cannot create {TS_DIRECTORY}: {exc} (run as admin/root)"
    for sidecar in (NLL_FILE, CCT_FILE):
        try:
            sidecar.parent.mkdir(parents=True, exist_ok=True)
            notes.append(f"OK: {sidecar.parent}")
        except Exception as exc:  # noqa: BLE001
            return False, f"Cannot create {sidecar.parent}: {exc} (run as admin/root)"
    return True, "\n".join(notes)


def build_config_json(product: str, feature: str, version: str,
                      guest: str, host: str, gpu: str) -> dict:
    gpu_list = [g.strip() for g in (gpu or "").split(",") if g.strip()]
    if not gpu_list:
        gpu_list = [""]  # ships as [""] in every example config
    return {
        "GuestDriverVersion": guest.strip() or DEFAULT_GUEST_DRIVER,
        "HostDriverVersion": host.strip() or DEFAULT_HOST_DRIVER,
        "ProductName": product.strip(),
        "FeatureName": feature.strip(),
        "FeatureVersion": version.strip(),
        "GPU": gpu_list,
    }


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

class VgpuManagerApp:
    def __init__(self, root):
        import tkinter as tk
        from tkinter import ttk
        self.tk = tk
        self.ttk = ttk
        self.root = root
        root.title(f"{APP_TITLE}  v{APP_VERSION}")
        root.geometry("1080x760")
        root.minsize(960, 660)

        self._style()
        self.selected_key = tk.StringVar(value="vWS (Recommended)")
        self.nvlts_path = tk.StringVar(value=str(find_nvlts_binary() or ""))
        self.guest_var = tk.StringVar(value=DEFAULT_GUEST_DRIVER)
        self.host_var = tk.StringVar(value=DEFAULT_HOST_DRIVER)
        self.gpu_var = tk.StringVar(value="")
        self.restart_var = tk.BooleanVar(value=True)
        self.debug_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value=f"OS: {OS_LABEL}  •  detecting tools…")

        self.configs_dir = find_configs_dir()
        self._build_layout()
        self.log(f"{APP_TITLE} v{APP_VERSION}")
        self.log(f"OS detected: {OS_LABEL} ({platform.platform()})")
        self.log(f"Trusted store dir: {TS_DIRECTORY}")
        self.log(f"Node-locked file : {NLL_FILE}")
        self.log(f"Restart method   : {RESTART_HINT}")
        self.log("Permanent expiry hard-coded by nvlts: " + PERMANENT_EXPIRY_LABEL)
        if not is_admin():
            self.log("WARNING: not running as Administrator/root — writes + service restart will fail.")
        self.refresh_tool_status()
        self.on_select_license()
        # Auto-detect guest driver version in background (fast, non-blocking)
        threading.Thread(target=self._autofill_driver, daemon=True).start()

    # -- styling (glassmorphism) ---------------------------------------
    def _style(self):
        from tkinter import ttk
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(".", background=DARK_BG, foreground=LIGHT_FG,
                        fieldbackground=DARK_CARD, font=("Segoe UI", 10),
                        bordercolor=GLASS_EDGE_DIM, lightcolor=GLASS_EDGE,
                        darkcolor=DARK_BG_DEEP)
        style.configure("TFrame", background=DARK_BG)
        style.configure("Glass.TFrame", background=DARK_PANEL, relief="flat",
                        borderwidth=1)
        # legacy alias kept so older layout code still resolves
        style.configure("Card.TFrame", background=DARK_PANEL, relief="flat",
                        borderwidth=1)
        style.configure("TLabel", background=DARK_BG, foreground=LIGHT_FG)
        style.configure("Card.TLabel", background=DARK_PANEL, foreground=LIGHT_FG)
        style.configure("Glass.TLabel", background=DARK_PANEL, foreground=LIGHT_FG)
        style.configure("Muted.TLabel", background=DARK_BG, foreground=MUTED_FG)
        style.configure("CardMuted.TLabel", background=DARK_PANEL,
                        foreground=MUTED_FG)
        style.configure("Hero.TLabel", background=HEADER_GRAD_BOT,
                        foreground="white", font=("Segoe UI", 17, "bold"))
        style.configure("HeroSub.TLabel", background=HEADER_GRAD_BOT,
                        foreground="#c9cff5", font=("Segoe UI", 10))
        style.configure("Title.TLabel", background=DARK_BG, foreground="white",
                        font=("Segoe UI", 15, "bold"))
        style.configure("Section.TLabel", background=DARK_PANEL,
                        foreground="white", font=("Segoe UI", 11, "bold"))
        style.configure("Accent.TButton", background=NVIDIA_GREEN, foreground="#0b0e1a",
                        font=("Segoe UI", 10, "bold"), padding=8,
                        borderwidth=0, relief="flat")
        style.map("Accent.TButton",
                  background=[("active", NEON_GREEN), ("pressed", "#5da300")])
        style.configure("Glass.TButton", background="#313a6e", foreground="white",
                        font=("Segoe UI", 9), padding=6,
                        borderwidth=1, relief="flat")
        style.map("Glass.TButton",
                  background=[("active", "#3f4a8c"), ("pressed", "#2a3170")],
                  bordercolor=[("active", GLASS_EDGE)])
        style.configure("TButton", background="#313a6e", foreground="white",
                        padding=6, borderwidth=1, relief="flat")
        style.map("TButton",
                  background=[("active", "#3f4a8c"), ("pressed", "#2a3170")])
        style.configure("TEntry", fieldbackground=DARK_CARD, foreground="white",
                        bordercolor=GLASS_EDGE_DIM, insertcolor="white",
                        padding=4)
        style.map("TEntry", bordercolor=[("focus", GLASS_EDGE)])
        style.configure("TCheckbutton", background=DARK_PANEL, foreground=LIGHT_FG)
        style.map("TCheckbutton", background=[("active", DARK_PANEL)])
        style.configure("TPanedwindow", background=DARK_BG)
        style.configure("Sash", background=GLASS_EDGE_DIM, borderwidth=2,
                        sashthickness=4)
        self.root.configure(bg=DARK_BG)

    def _glass_border(self, widget):
        """Luminous hairline around a frosted card (flat = glass edge)."""
        try:
            widget.configure(highlightthickness=1,
                             highlightbackground=GLASS_EDGE_DIM,
                             highlightcolor=GLASS_EDGE)
        except Exception:
            pass

    def _paint_glow_blobs(self, canvas, w, h):
        """Ambient aurora blobs behind the hero banner (static, stdlib-only)."""
        canvas.delete("blob")
        blobs = [
            (-70, -90, 260, 130, "#2f9e5f"),    # nvidia green aura
            (w * 0.45, -110, w * 0.45 + 340, 120, "#4a3fa3"),  # violet aura
            (w - 260, -80, w + 90, 140, "#1f6f9e"),  # cyan aura
        ]
        for x0, y0, x1, y1, color in blobs:
            canvas.create_oval(x0, y0, x1, y1, fill=color, outline="",
                               stipple="gray50", tags="blob")
        # glass shine sweep
        canvas.create_rectangle(0, 0, w, 2, fill=GLASS_EDGE, outline="",
                                tags="blob")

    # -- layout ----------------------------------------------------------
    def _build_layout(self):
        tk = self.tk
        ttk = self.ttk
        from tkinter import scrolledtext

        # ---- glass hero banner (gradient + aurora blobs + pills) ----
        hero_h = 96
        hero = tk.Canvas(self.root, height=hero_h, highlightthickness=0,
                         bg=HEADER_GRAD_TOP)
        hero.pack(fill="x")

        def _draw_hero(_evt=None):
            w = hero.winfo_width()
            if w < 20:
                return
            hero.delete("all")
            top = tuple(int(HEADER_GRAD_TOP[i:i + 2], 16) for i in (1, 3, 5))
            bot = tuple(int(HEADER_GRAD_BOT[i:i + 2], 16) for i in (1, 3, 5))
            for y in range(hero_h):
                t = y / hero_h
                r = int(top[0] + (bot[0] - top[0]) * t)
                g = int(top[1] + (bot[1] - top[1]) * t)
                b = int(top[2] + (bot[2] - top[2]) * t)
                hero.create_line(0, y, w, y,
                                 fill=f"#{r:02x}{g:02x}{b:02x}", tags="bg")
            self._paint_glow_blobs(hero, w, hero_h)
            hero.create_text(22, 30, anchor="w", tags="fg",
                             text="◈  vGPU License Manager",
                             fill="white", font=("Segoe UI", 17, "bold"))
            hero.create_text(24, 58, anchor="w", tags="fg",
                             text="nvlts GUI  •  permanent local trusted store",
                             fill="#c9cff5", font=("Segoe UI", 10))
            hero.create_text(24, 78, anchor="w", tags="fg",
                             text="pick an edition  →  check status  →  apply permanent license",
                             fill="#8f97c9", font=("Segoe UI", 8))
            # pills (right side)
            pills = [f"OS · {OS_LABEL}", "✦ PERMANENT · 3000-12-31"]
            px = w - 18
            hero.create_text(px, 78, anchor="e", tags="fg",
                             text="glass edition  v" + APP_VERSION,
                             fill="#8f97c9", font=("Segoe UI", 8, "italic"))
            for pill in reversed(pills):
                fw = max(120, len(pill) * 8 + 28)
                hero.create_rectangle(px - fw, 22, px, 48, tags="fg",
                                      fill="#0e1330", outline=GLASS_EDGE, width=1)
                hero.create_text(px - fw / 2, 35, anchor="center", tags="fg",
                                 text=pill, fill=NEON_GREEN,
                                 font=("Segoe UI", 9, "bold"))
                px -= fw + 10

        hero.bind("<Configure>", _draw_hero)
        self.root.after(60, _draw_hero)

        strip = tk.Frame(self.root, height=2, bg=NVIDIA_GREEN)
        strip.pack(fill="x")

        body = ttk.Frame(self.root, padding=(14, 6, 14, 6))
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=4)
        body.rowconfigure(0, weight=1)

        # ---- left: license catalog (frosted card) ----
        left = ttk.Frame(body, style="Card.TFrame", padding=10)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self._glass_border(left)
        ttk.Label(left, text="1 · Choose license edition", style="Section.TLabel").pack(anchor="w")
        ttk.Label(left, text="ProductName + FeatureName must match the driver.",
                  style="CardMuted.TLabel").pack(anchor="w", pady=(0, 6))

        self.edition_list = tk.Listbox(left, height=12, exportselection=False,
                                       bg="#141943", fg="white",
                                       selectbackground=NVIDIA_GREEN,
                                       selectforeground="#0b0e1a",
                                       font=("Segoe UI", 10), relief="flat",
                                       highlightthickness=1,
                                       highlightbackground=GLASS_EDGE_DIM,
                                       highlightcolor=GLASS_EDGE,
                                       activestyle="none")
        for key in LICENSE_CATALOG:
            marker = " ★" if "Recommended" in key else ""
            self.edition_list.insert("end", key + marker)
        self.edition_list.pack(fill="both", expand=True)
        self.edition_list.bind("<<ListboxSelect>>", lambda _e: self.on_select_license())
        self.edition_list.select_set(0)

        self.detail = tk.Text(left, height=9, wrap="word", bg="#141943", fg="#e8ebff",
                              relief="flat", font=("Segoe UI", 9),
                              highlightthickness=1,
                              highlightbackground=GLASS_EDGE_DIM,
                              highlightcolor=GLASS_EDGE,
                              selectbackground="#3f4a8c")
        self.detail.pack(fill="x", pady=(8, 0))
        self.detail.configure(state="disabled")

        # ---- right: config + actions ----
        right = ttk.Frame(body, padding=(4, 0, 0, 0))
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)

        cfg = ttk.Frame(right, style="Card.TFrame", padding=10)
        cfg.pack(fill="x")
        self._glass_border(cfg)
        ttk.Label(cfg, text="2 · Configuration  (temp config.json for nvlts -g -c)",
                  style="Section.TLabel").pack(anchor="w")

        grid = ttk.Frame(cfg, style="Card.TFrame")
        grid.pack(fill="x", pady=6)
        for c in (0, 1, 2, 3):
            grid.columnconfigure(c, weight=1 if c % 2 == 1 else 0)

        def rowlabel(r, text):
            ttk.Label(grid, text=text, style="Card.TLabel", foreground=MUTED_FG).grid(
                row=r, column=0, sticky="w", padx=(0, 6), pady=3)

        def rowentry(r, var, width=22):
            e = ttk.Entry(grid, textvariable=var, width=width)
            e.grid(row=r, column=1, sticky="ew", pady=3)
            return e

        rowlabel(0, "Product:")
        self.product_var = tk.StringVar()
        rowentry(0, self.product_var)
        rowlabel(1, "Feature:")
        self.feature_var = tk.StringVar()
        rowentry(1, self.feature_var)
        ttk.Label(grid, text="Version:", background=DARK_PANEL, foreground=MUTED_FG).grid(
            row=0, column=2, sticky="w", padx=(12, 6))
        self.version_var = tk.StringVar()
        ttk.Entry(grid, textvariable=self.version_var, width=10).grid(row=0, column=3, sticky="ew")
        ttk.Label(grid, text="GPU(s):", background=DARK_PANEL, foreground=MUTED_FG).grid(
            row=1, column=2, sticky="w", padx=(12, 6))
        ttk.Entry(grid, textvariable=self.gpu_var, width=14).grid(row=1, column=3, sticky="ew")
        rowlabel(2, "Guest driver:")
        rowentry(2, self.guest_var)
        rowlabel(3, "Host driver:")
        rowentry(3, self.host_var)
        ttk.Button(grid, text="Auto-detect guest", command=self.autodetect_guest).grid(
            row=2, column=2, columnspan=2, sticky="ew", padx=(12, 0))
        ttk.Label(grid, text="comma-separated; blank = [\"\"] like stock configs",
                  background=DARK_PANEL, foreground=MUTED_FG, font=("Segoe UI", 8)).grid(
            row=3, column=2, columnspan=2, sticky="w", padx=(12, 0))

        src = "embedded catalog" if self.configs_dir is None else str(self.configs_dir)
        ttk.Label(cfg, text=f"Config source on disk: {src}",
                  background=DARK_PANEL, foreground=MUTED_FG,
                  font=("Segoe UI", 8)).pack(anchor="w")
        ttk.Label(cfg, text=f"License expiry: {PERMANENT_EXPIRY_LABEL} — hard-coded in nvlts, always permanent.",
                  background=DARK_PANEL, foreground=NVIDIA_GREEN,
                  font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(4, 0))

        tools = ttk.Frame(right, style="Card.TFrame", padding=10)
        tools.pack(fill="x", pady=8)
        self._glass_border(tools)
        ttk.Label(tools, text="3 · Tools & target", style="Section.TLabel").pack(anchor="w")
        nrow = ttk.Frame(tools, style="Card.TFrame")
        nrow.pack(fill="x", pady=4)
        ttk.Label(nrow, text="nvlts binary:", style="Card.TLabel").pack(side="left")
        ttk.Entry(nrow, textvariable=self.nvlts_path).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(nrow, text="Browse…", command=self.browse_nvlts).pack(side="left")
        ttk.Button(nrow, text="Auto-find", command=self.refresh_tool_status).pack(side="left", padx=(6, 0))

        opts = ttk.Frame(tools, style="Card.TFrame")
        opts.pack(fill="x")
        ttk.Checkbutton(opts, text="Auto-restart service (-r)", variable=self.restart_var).pack(side="left")
        ttk.Checkbutton(opts, text="Debug output (-debug)", variable=self.debug_var).pack(side="left", padx=(14, 0))

        btns = ttk.Frame(right)
        btns.pack(fill="x", pady=2)
        ttk.Button(btns, text="✔ Check license status", command=self.do_check_status).pack(
            side="left", fill="x", expand=True)
        ttk.Button(btns, text="★ Apply PERMANENT license", style="Accent.TButton",
                   command=self.do_apply).pack(side="left", fill="x", expand=True, padx=(8, 0))

        btns2 = ttk.Frame(right)
        btns2.pack(fill="x", pady=(6, 0))
        ttk.Button(btns2, text="Decrypt store (-d)", command=self.do_decrypt).pack(side="left", fill="x", expand=True)
        ttk.Button(btns2, text="Backup store", command=self.do_backup).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(btns2, text="Fingerprint", command=self.do_fingerprint).pack(side="left", fill="x", expand=True)
        ttk.Button(btns2, text="Restart service", command=self.do_restart).pack(side="left", fill="x", expand=True, padx=(6, 0))

        # ---- bottom: status + log ----
        bottom = ttk.Frame(self.root, padding=(14, 0, 14, 10))
        bottom.pack(fill="both", expand=True)
        ttk.Label(bottom, textvariable=self.status_var, style="Muted.TLabel").pack(anchor="w")

        panes = ttk.PanedWindow(bottom, orient="horizontal")
        panes.pack(fill="both", expand=True, pady=4)

        status_frame = ttk.Frame(panes, style="Card.TFrame", padding=8)
        self._glass_border(status_frame)
        ttk.Label(status_frame, text="❖  license status  ·  nvidia-smi -q  |  License",
                  style="Section.TLabel", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.status_box = scrolledtext.ScrolledText(status_frame, height=10, wrap="word",
                                                    bg="#0b0e28", fg="#c8ffb0",
                                                    insertbackground="white",
                                                    font=("Consolas", 9), relief="flat",
                                                    highlightthickness=1,
                                                    highlightbackground=GLASS_EDGE_DIM,
                                                    highlightcolor=GLASS_EDGE,
                                                    selectbackground="#3f4a8c")
        self.status_box.pack(fill="both", expand=True, pady=(6, 0))
        panes.add(status_frame, weight=1)

        log_frame = ttk.Frame(panes, style="Card.TFrame", padding=8)
        self._glass_border(log_frame)
        ttk.Label(log_frame, text="❖  operation log  ·  exact nvlts commands",
                  style="Section.TLabel", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.log_box = scrolledtext.ScrolledText(log_frame, height=10, wrap="word",
                                                 bg="#0b0e28", fg=LIGHT_FG,
                                                 insertbackground="white",
                                                 font=("Consolas", 9), relief="flat",
                                                 highlightthickness=1,
                                                 highlightbackground=GLASS_EDGE_DIM,
                                                 highlightcolor=GLASS_EDGE,
                                                 selectbackground="#3f4a8c")
        self.log_box.pack(fill="both", expand=True, pady=(6, 0))
        panes.add(log_frame, weight=1)

        footer = ttk.Label(
            self.root,
            text=("Do NOT change/add/remove NICs afterwards (even VPN TAP) — it invalidates the credential.  •  "
                  f"Docs: {NVLTS_UPSTREAM}"),
            style="Muted.TLabel", font=("Segoe UI", 8), padding=(14, 0, 14, 8))
        footer.pack(fill="x")

    # -- small workers ---------------------------------------------------
    def log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_box.insert("end", f"[{ts}] {msg}\n")
        self.log_box.see("end")

    def set_status_box(self, text: str):
        self.status_box.delete("1.0", "end")
        self.status_box.insert("1.0", text)

    def current_edition(self) -> tuple[str, dict]:
        idx = self.edition_list.curselection()
        raw = self.edition_list.get(idx[0] if idx else 0)
        key = raw.replace(" ★", "")
        return key, LICENSE_CATALOG[key]

    def on_select_license(self):
        key, info = self.current_edition()
        self.selected_key.set(key)
        # Prefer values from the on-disk JSON if present (driver revs move on)
        disk_vals = None
        if self.configs_dir is not None:
            disk_vals = load_config_file(self.configs_dir / info["file"])
        product = (disk_vals or {}).get("ProductName", info["product"])
        feature = (disk_vals or {}).get("FeatureName", info["feature"])
        version = (disk_vals or {}).get("FeatureVersion", info["version"])
        self.product_var.set(product)
        self.feature_var.set(feature)
        self.version_var.set(version)
        badge = f"  [{info['badge']}]" if info.get("badge") else ""
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("end",
                           f"{key}{badge}\n"
                           f"Product : {product}\n"
                           f"Feature : {feature}\n"
                           f"Version : {version}\n\n"
                           f"{info['desc']}\n\n"
                           f"File: {info['file']}")
        self.detail.configure(state="disabled")

    def refresh_tool_status(self):
        smi = find_nvidia_smi()
        nvlts = Path(self.nvlts_path.get()) if self.nvlts_path.get() else find_nvlts_binary()
        if nvlts and nvlts.exists():
            self.nvlts_path.set(str(nvlts))
            nvlts_txt = f"nvlts: {nvlts}"
        else:
            nvlts_txt = "nvlts: NOT FOUND — Browse to nvlts(.exe) from the release zip"
            auto = find_nvlts_binary()
            if auto:
                self.nvlts_path.set(str(auto))
                nvlts_txt = f"nvlts: {auto}"
        smi_txt = f"nvidia-smi: {smi}" if smi else "nvidia-smi: NOT FOUND (install guest driver)"
        admin_txt = "admin/root: YES" if is_admin() else "admin/root: NO — relaunch elevated!"
        self.status_var.set(f"OS: {OS_LABEL}   •   {smi_txt}   •   {nvlts_txt}   •   {admin_txt}")
        self.log(f"Tool check — {smi_txt} | {nvlts_txt} | {admin_txt}")

    def _autofill_driver(self):
        ver = query_driver_version()
        if ver:
            try:
                self.root.after(0, lambda: (self.guest_var.set(ver), self.log(f"Detected guest driver: {ver}")))
            except (RuntimeError, self.tk.TclError):
                pass  # window closed before driver probe finished

    def autodetect_guest(self):
        def work():
            ver = query_driver_version()
            try:
                if ver:
                    self.root.after(0, lambda: self.guest_var.set(ver))
                    self.root.after(0, lambda: self.log(f"Detected guest driver: {ver}"))
                else:
                    self.root.after(0, lambda: self.log("Could not detect driver version (is nvidia-smi present?)"))
            except (RuntimeError, self.tk.TclError):
                pass  # window closed while probing
        threading.Thread(target=work, daemon=True).start()

    def browse_nvlts(self):
        from tkinter import filedialog
        initial = str(Path(self.nvlts_path.get()).parent) if self.nvlts_path.get() else str(script_dir())
        exe = filedialog.askopenfilename(
            title="Select nvlts binary",
            initialdir=initial,
            filetypes=[("nvlts", "nvlts* nvlts.exe*"), ("All files", "*.*")],
        )
        if exe:
            self.nvlts_path.set(exe)
            self.refresh_tool_status()

    # -- actions (threaded) ----------------------------------------------
    def _run_thread(self, fn):
        threading.Thread(target=fn, daemon=True).start()

    def do_check_status(self):
        self.set_status_box("Querying nvidia-smi -q …")
        self.log("Checking license status (nvidia-smi -q filtered for 'License')…")
        def work():
            try:
                ok, report = query_license_status()
                self.root.after(0, lambda: self.set_status_box(report))
                self.root.after(0, lambda: self.log("Status check " + ("OK." if ok else "FAILED — see left panel.")))
            except Exception:  # noqa: BLE001
                err = traceback.format_exc()
                self.root.after(0, lambda: self.log(f"Status check crashed:\n{err}"))
        self._run_thread(work)

    def _validated_nvlts(self) -> Path | None:
        p = Path(self.nvlts_path.get().strip())
        if not self.nvlts_path.get().strip() or not p.exists():
            auto = find_nvlts_binary()
            if auto:
                self.nvlts_path.set(str(auto))
                return auto
            self.log("ERROR: nvlts binary not set. Unzip the release in ./source/ and Browse to nvlts(.exe).")
            return None
        return p

    def do_apply(self):
        key, info = self.current_edition()
        self._run_thread(lambda: self._apply(key, info))

    def _apply(self, key: str, info: dict):
        from tkinter import messagebox
        nvlts = self.root.after(0, lambda: None)  # keep UI alive; real work below
        nvlts_bin = self._validated_nvlts()
        if nvlts_bin is None:
            return
        if not is_admin():
            self.log("WARNING: not elevated — write/restart will likely fail. Continuing anyway…")
        ok, prep = ensure_writable_dirs()
        self.log("Preparing directories (workaround for generate() missing MkdirAll):\n" + prep)
        if not ok:
            self.log("ERROR: cannot prepare directories. Relaunch as Administrator/root.")
            return
        cfg = build_config_json(
            self.product_var.get(), self.feature_var.get(), self.version_var.get(),
            self.guest_var.get(), self.host_var.get(), self.gpu_var.get(),
        )
        if not cfg["ProductName"] or not cfg["FeatureName"]:
            self.log("ERROR: ProductName and FeatureName must not be empty (driver requires exact match).")
            return
        tmp = Path(tempfile.gettempdir()) / f"nvlts_{info['file']}"
        try:
            tmp.write_text(json.dumps(cfg, indent=4), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            self.log(f"ERROR: cannot write temp config {tmp}: {exc}")
            return
        cmd = [str(nvlts_bin), "-g", "-c", str(tmp)]
        if self.restart_var.get():
            cmd.append("-r")
        if self.debug_var.get():
            cmd.append("-debug")
        # NOTE: readme order is `-g -r -c file`; Go flags accept any order.
        self.log(f"Applying PERMANENT '{key}' license (expires {PERMANENT_EXPIRY_LABEL}):")
        self.log("  $ " + " ".join(f'"{c}"' if " " in c else c for c in cmd))
        self.log(f"  config: {json.dumps(cfg)}")
        rc, out, err = run_cmd(cmd, timeout=120)
        if out.strip():
            self.log("--- nvlts stdout ---\n" + out.strip())
        if err.strip():
            self.log("--- nvlts stderr ---\n" + err.strip())
        if rc == 0:
            self.log(f"SUCCESS: '{key}' trusted store written. Permanent until NIC/machine-id changes.")
            try:
                self.root.after(0, lambda: messagebox.showinfo(
                    "License applied",
                    f"'{key}' permanent license written.\n\n"
                    f"Expiry: {PERMANENT_EXPIRY_LABEL}\n"
                    "Do NOT change NICs afterwards.\n\n"
                    "Re-check status to confirm 'Licensed'."))
            except Exception:
                pass
            ok2, report = query_license_status()
            self.root.after(0, lambda: self.set_status_box(report))
        else:
            self.log(f"FAILED (exit {rc}). Check nvlts output above; verify admin rights + driver installed.")
            try:
                self.root.after(0, lambda rc=rc: messagebox.showerror(
                    "Apply failed", f"nvlts exited with code {rc}.\nSee operation log for details."))
            except Exception:
                pass

    def do_decrypt(self):
        self._run_thread(self._decrypt)

    def _decrypt(self):
        nvlts_bin = self._validated_nvlts()
        if nvlts_bin is None:
            return
        out_file = Path(tempfile.gettempdir()) / "trusted_store_decrypted.json"
        # nvlts -d [-f file]; default trusted_store.json in CWD — use explicit temp path
        cmd = [str(nvlts_bin), "-d", "-f", str(out_file)]
        if self.debug_var.get():
            cmd.append("-debug")
        self.log("$ " + " ".join(cmd))
        rc, out, err = run_cmd(cmd, timeout=60)
        if out.strip():
            self.log("--- stdout ---\n" + out.strip())
        if err.strip():
            self.log("--- stderr ---\n" + err.strip())
        if rc == 0 and out_file.exists():
            try:
                preview = out_file.read_text(encoding="utf-8", errors="replace")[:3000]
                self.log(f"Decrypted {out_file} ({out_file.stat().st_size} bytes). Preview:\n{preview}")
                if IS_WINDOWS:
                    os.startfile(str(out_file))  # noqa: S606  (local temp file by design)
                self.log(f"Saved decrypted store to {out_file}")
            except Exception as exc:  # noqa: BLE001
                self.log(f"Decrypt OK but preview failed: {exc}")
        else:
            self.log(f"Decrypt FAILED (exit {rc}). Store may not exist yet — apply a license first.")

    def do_backup(self):
        self._run_thread(self._backup)

    def _backup(self):
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest_dir = script_dir() / f"trustedstore_backup_{stamp}"
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            copied = []
            for src in (TS_ENCRYPTED_FILE, TS_TAG_FILE, NLL_FILE, CCT_FILE):
                if src.exists():
                    dst = dest_dir / src.name
                    dst.write_bytes(src.read_bytes())
                    copied.append(f"{src} -> {dst}")
            if copied:
                self.log(f"Backup complete in {dest_dir}:\n" + "\n".join(copied))
            else:
                self.log(f"Nothing to back up (no store files found under {TS_DIRECTORY}). Apply a license first.")
        except Exception as exc:  # noqa: BLE001
            self.log(f"Backup FAILED: {exc}")

    def do_fingerprint(self):
        self.set_status_box("Collecting fingerprint (MAC / IP / machine-id) …")
        def work():
            try:
                report = f"OS: {OS_LABEL} ({platform.platform()})\n\n" + fingerprint_info()
                self.root.after(0, lambda: self.set_status_box(report))
                self.root.after(0, lambda: self.log("Fingerprint collected (see left panel)."))
            except Exception:  # noqa: BLE001
                err = traceback.format_exc()
                self.root.after(0, lambda: self.log(f"Fingerprint failed:\n{err}"))
        self._run_thread(work)

    def do_restart(self):
        def work():
            if IS_WINDOWS:
                cmd = ["powershell.exe", "-NoProfile", "-Command",
                       "Restart-Service NVDisplay.ContainerLocalSystem -PassThru"]
                self.log("$ " + " ".join(cmd) + f"   (nvlts -r equivalent)")
            else:
                cmd = ["systemctl", "restart", "nvidia-gridd"]
                self.log("$ " + " ".join(cmd) + "   (nvlts -r equivalent)")
            rc, out, err = run_cmd(cmd, timeout=120)
            if out.strip():
                self.log("--- stdout ---\n" + out.strip())
            if err.strip():
                self.log("--- stderr ---\n" + err.strip())
            self.log("Restart " + ("OK." if rc == 0 else f"FAILED (exit {rc}) — need admin/root?"))
        self._run_thread(work)


def main() -> int:
    try:
        import tkinter as tk
    except ImportError:
        print("ERROR: tkinter is not installed.", file=sys.stderr)
        if IS_LINUX:
            print("Install it with: sudo apt install python3-tk   (or python3-tkinter)", file=sys.stderr)
        return 2
    root = tk.Tk()
    try:
        VgpuManagerApp(root)
    except Exception:
        traceback.print_exc()
        return 1
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
