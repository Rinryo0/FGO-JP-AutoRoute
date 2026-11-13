from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk


APP_NAME = "FGO-JP-AutoRoute"
DEFAULT_DEVICE = "127.0.0.1:16416"
REFRESH_MS = 2000


def candidate_adb_paths() -> list[Path]:
    roots = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
        Path(os.environ.get("LOCALAPPDATA", "")),
    ]
    candidates: list[Path] = []
    for root in roots:
        if not str(root):
            continue
        for relative in (
            Path("Netease/MuMuPlayer-12.0/shell/adb.exe"),
            Path("Netease/MuMuPlayerGlobal-12.0/shell/adb.exe"),
            Path("MuMuPlayer-12.0/shell/adb.exe"),
            Path("Netease/MuMuPlayer-12.0/vmonitor/bin/adb.exe"),
            Path("Netease/MuMuPlayerGlobal-12.0/vmonitor/bin/adb.exe"),
        ):
            candidates.append(root / relative)

    on_path = shutil.which("adb")
    if on_path:
        candidates.insert(0, Path(on_path))

    env_path = os.environ.get("FGO_ADB_PATH")
    if env_path:
        candidates.insert(0, Path(env_path))

    unique: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path).lower()
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def find_adb() -> Path | None:
    for path in candidate_adb_paths():
        if path.is_file():
            return path
    return None


class FGODesktopApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(f"{APP_NAME} — MuMu 桌面監看")
        self.root.geometry("1180x780")
        self.root.minsize(900, 620)
        self.root.configure(bg="#0b1220")

        self.adb_path = find_adb()
        self.device_var = tk.StringVar(value=DEFAULT_DEVICE)
        self.status_var = tk.StringVar(value="尚未連線")
        self.adb_var = tk.StringVar(
            value=str(self.adb_path) if self.adb_path else "尚未找到 adb.exe"
        )
        self.auto_var = tk.BooleanVar(value=True)
        self.last_frame: Image.Image | None = None
        self.photo: ImageTk.PhotoImage | None = None
        self.last_status = ""
        self.refresh_job: str | None = None
        self.busy = False
        self.closing = False

        self._configure_style()
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._schedule_refresh(500)

    def _configure_style(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "TFrame", background="#0b1220"
        )
        style.configure(
            "Panel.TFrame", background="#142033"
        )
        style.configure(
            "TLabel", background="#0b1220", foreground="#e6edf7",
            font=("Segoe UI", 10)
        )
        style.configure(
            "Panel.TLabel", background="#142033", foreground="#e6edf7",
            font=("Segoe UI", 10)
        )
        style.configure(
            "Title.TLabel", background="#0b1220", foreground="#f4c77b",
            font=("Segoe UI", 19, "bold")
        )
        style.configure(
            "Sub.TLabel", background="#0b1220", foreground="#91a4bf",
            font=("Segoe UI", 9)
        )
        style.configure(
            "Status.TLabel", background="#142033", foreground="#9de2bb",
            font=("Segoe UI", 10, "bold")
        )
        style.configure(
            "TButton", font=("Segoe UI", 10), padding=(12, 8),
            background="#263750", foreground="#edf3ff"
        )
        style.map(
            "TButton",
            background=[("active", "#385274"), ("disabled", "#1c293c")],
            foreground=[("disabled", "#74839a")]
        )
        style.configure(
            "Accent.TButton", background="#d7a85e", foreground="#111827",
            font=("Segoe UI", 10, "bold"), padding=(14, 9)
        )
        style.map("Accent.TButton", background=[("active", "#edc47d")])
        style.configure(
            "TEntry", fieldbackground="#0e192a", foreground="#e6edf7",
            insertcolor="#e6edf7", padding=7
        )
        style.configure(
            "TCheckbutton", background="#142033", foreground="#e6edf7",
            font=("Segoe UI", 9)
        )
        style.map("TCheckbutton", background=[("active", "#142033")])

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 14))
        ttk.Label(header, text="FGO AUTO", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="日本版 FATE / GRAND ORDER　·　WINDOWS DESKTOP",
            style="Sub.TLabel"
        ).pack(anchor="w", pady=(2, 0))

        toolbar = ttk.Frame(outer, style="Panel.TFrame", padding=12)
        toolbar.pack(fill="x", pady=(0, 12))

        line1 = ttk.Frame(toolbar, style="Panel.TFrame")
        line1.pack(fill="x")
        ttk.Label(line1, text="MuMu ADB 位址", style="Panel.TLabel").pack(side="left")
        self.device_entry = ttk.Entry(line1, textvariable=self.device_var, width=24)
        self.device_entry.pack(side="left", padx=(10, 12))
        ttk.Button(
            line1, text="連接 MuMu", style="Accent.TButton",
            command=self.connect_device
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            line1, text="選擇 ADB", command=self.choose_adb
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            line1, text="立即截圖", command=self.capture_now
        ).pack(side="left")

        line2 = ttk.Frame(toolbar, style="Panel.TFrame")
        line2.pack(fill="x", pady=(10, 0))
        ttk.Label(line2, text="連線狀態：", style="Panel.TLabel").pack(side="left")
        ttk.Label(line2, textvariable=self.status_var, style="Status.TLabel").pack(side="left")
        ttk.Label(line2, text="　ADB：", style="Panel.TLabel").pack(side="left")
        ttk.Label(
            line2, textvariable=self.adb_var, style="Panel.TLabel"
        ).pack(side="left", fill="x", expand=True)
        ttk.Checkbutton(
            line2, text="每 2 秒自動更新截圖", variable=self.auto_var
        ).pack(side="right")

        content = ttk.Frame(outer)
        content.pack(fill="both", expand=True)

        preview_panel = ttk.Frame(content, style="Panel.TFrame", padding=10)
        preview_panel.pack(side="left", fill="both", expand=True, padx=(0, 12))
        ttk.Label(
            preview_panel, text="MuMu 即時畫面", style="Panel.TLabel",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", pady=(0, 8))

        self.preview = tk.Canvas(
            preview_panel, bg="#070d17", highlightthickness=0,
            width=800, height=540
        )
        self.preview.pack(fill="both", expand=True)
        self.preview.bind("<Configure>", self._redraw_preview)

        side = ttk.Frame(content, style="Panel.TFrame", padding=12, width=270)
        side.pack(side="right", fill="y")
        side.pack_propagate(False)
        ttk.Label(
            side, text="使用方式", style="Panel.TLabel",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", pady=(0, 10))
        tips = (
            "1. 開啟 MuMu 12 與日版 FGO。\n\n"
            "2. 確認 ADB 位址為模擬器目前使用的連接埠。\n\n"
            "3. 按「連接 MuMu」。\n\n"
            "4. 連線成功後，畫面會每 2 秒自動更新。\n\n"
            "5. 若找不到 adb.exe，按「選擇 ADB」指定 MuMu 安裝資料夾內的 adb.exe。"
        )
        ttk.Label(
            side, text=tips, style="Panel.TLabel",
            wraplength=238, justify="left"
        ).pack(anchor="w")

        ttk.Separator(side).pack(fill="x", pady=14)
        ttk.Label(
            side, text="執行紀錄", style="Panel.TLabel",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", pady=(0, 8))
        self.log_box = tk.Text(
            side, height=14, bg="#0b1627", fg="#b9c9df",
            insertbackground="#ffffff", relief="flat",
            font=("Consolas", 8), wrap="word", state="disabled"
        )
        self.log_box.pack(fill="both", expand=True)
        self._log("程式已啟動。請連接 MuMu。")

        footer = ttk.Label(
            outer,
            text="此版本提供桌面監看與截圖更新；遊戲內操作仍由使用者自行完成。",
            style="Sub.TLabel"
        )
        footer.pack(anchor="w", pady=(10, 0))

    def _log(self, message: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{stamp}] {message}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _set_status(self, value: str) -> None:
        self.status_var.set(value)
        if value != self.last_status:
            self._log(value)
            self.last_status = value

    def _run_adb(self, *args: str, timeout: int = 8) -> subprocess.CompletedProcess[bytes]:
        if not self.adb_path or not self.adb_path.is_file():
            raise FileNotFoundError("找不到 adb.exe，請按「選擇 ADB」。")
        return subprocess.run(
            [str(self.adb_path), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False
        )

    def choose_adb(self) -> None:
        selected = filedialog.askopenfilename(
            title="選擇 MuMu 的 adb.exe",
            filetypes=[("ADB executable", "adb.exe"), ("Executable", "*.exe")]
        )
        if selected:
            self.adb_path = Path(selected)
            self.adb_var.set(str(self.adb_path))
            self._log("已設定 ADB 路徑。")

    def connect_device(self) -> None:
        address = self.device_var.get().strip()
        if not address or ":" not in address:
            messagebox.showwarning("ADB 位址", "請輸入類似 127.0.0.1:16416 的位址。")
            return
        try:
            if not self.adb_path:
                self.adb_path = find_adb()
                if self.adb_path:
                    self.adb_var.set(str(self.adb_path))
            result = self._run_adb("connect", address, timeout=12)
            output = (result.stdout + result.stderr).decode("utf-8", "replace").strip()
            state = self._run_adb("-s", address, "get-state", timeout=8)
            if state.returncode == 0 and b"device" in state.stdout:
                self._set_status(f"已連線：{address}")
                if output:
                    self._log(output)
                self.capture_now()
            else:
                self._set_status("尚未連線，請確認 MuMu 已開啟及 ADB 位址正確")
                if output:
                    self._log(output)
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
            self._set_status(f"連線失敗：{exc}")
            messagebox.showerror("ADB 連線失敗", str(exc))

    def capture_now(self) -> None:
        if self.busy:
            return
        self.busy = True
        address = self.device_var.get().strip()
        try:
            state = self._run_adb("-s", address, "get-state", timeout=6)
            if state.returncode != 0 or b"device" not in state.stdout:
                self._set_status("MuMu 未連線")
                return
            result = self._run_adb(
                "-s", address, "exec-out", "screencap", "-p", timeout=10
            )
            if result.returncode != 0 or not result.stdout:
                error = result.stderr.decode("utf-8", "replace").strip()
                self._set_status(f"截圖失敗：{error or 'ADB 沒有回傳畫面'}")
                return
            image = Image.open(io.BytesIO(result.stdout)).convert("RGB")
            self.last_frame = image
            self._redraw_preview()
            self._set_status(f"已連線：{address}　·　畫面更新 {time.strftime('%H:%M:%S')}")
        except FileNotFoundError as exc:
            self._set_status(str(exc))
        except subprocess.TimeoutExpired:
            self._set_status("截圖逾時，請確認 MuMu 是否正常運作")
        except Exception as exc:
            self._set_status(f"讀取畫面失敗：{exc}")
        finally:
            self.busy = False

    def _redraw_preview(self, _event: object = None) -> None:
        self.preview.delete("all")
        width = max(self.preview.winfo_width(), 1)
        height = max(self.preview.winfo_height(), 1)
        if self.last_frame is None:
            self.preview.create_text(
                width // 2, height // 2,
                text="等待 MuMu 畫面…",
                fill="#7f91aa", font=("Segoe UI", 15)
            )
            return
        frame = self.last_frame.copy()
        frame.thumbnail((width - 16, height - 16), Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(frame)
        self.preview.create_image(
            width // 2, height // 2, image=self.photo, anchor="center"
        )

    def _schedule_refresh(self, delay: int = REFRESH_MS) -> None:
        if self.closing:
            return
        self.refresh_job = self.root.after(delay, self._refresh_tick)

    def _refresh_tick(self) -> None:
        self.refresh_job = None
        if self.auto_var.get():
            self.capture_now()
        self._schedule_refresh(REFRESH_MS)

    def close(self) -> None:
        self.closing = True
        if self.refresh_job:
            try:
                self.root.after_cancel(self.refresh_job)
            except tk.TclError:
                pass
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    FGODesktopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
