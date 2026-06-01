"""KylinClaw GUI Launcher"""

import tkinter as tk
from tkinter import scrolledtext, messagebox, ttk
import subprocess
import threading
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PYTHON = os.path.join(ROOT, "python", "python.exe")
if not os.path.exists(PYTHON):
    PYTHON = sys.executable  # fallback to system Python

EXAMPLES = [
    ("基础 Agent + 工具调用", "examples/basic_agent.py"),
    ("多 Agent：Chain & Crew", "examples/multi_agent.py"),
    ("RAG 检索增强生成",       "examples/rag_example.py"),
]

BG      = "#1e1e2e"
PANEL   = "#2a2a3e"
ACCENT  = "#7c6af7"
FG      = "#cdd6f4"
FG2     = "#a6adc8"
GREEN   = "#a6e3a1"
RED     = "#f38ba8"
YELLOW  = "#f9e2af"
MONO    = ("Consolas", 10)
SANS    = ("Segoe UI", 10)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("KylinClaw")
        self.geometry("860x580")
        self.minsize(700, 480)
        self.configure(bg=BG)
        self._proc = None
        self._build()

    def _build(self):
        # ── Header ──────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=PANEL, height=52)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="KylinClaw", font=("Segoe UI", 16, "bold"),
                 bg=PANEL, fg=ACCENT).pack(side="left", padx=18, pady=10)
        tk.Label(hdr, text="轻量级 Python LLM Agent 框架", font=("Segoe UI", 9),
                 bg=PANEL, fg=FG2).pack(side="left", pady=10)
        tk.Label(hdr, text="v0.1.0", font=("Segoe UI", 9),
                 bg=PANEL, fg=FG2).pack(side="right", padx=18)

        # ── Body ─────────────────────────────────────────────────────
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=14, pady=10)

        # Left: controls
        left = tk.Frame(body, bg=PANEL, width=210)
        left.pack(side="left", fill="y", padx=(0, 10))
        left.pack_propagate(False)

        tk.Label(left, text="API 配置", font=("Segoe UI", 9, "bold"),
                 bg=PANEL, fg=FG2).pack(anchor="w", padx=12, pady=(14, 2))

        tk.Label(left, text="API Key", font=SANS, bg=PANEL, fg=FG2).pack(anchor="w", padx=12)
        self.api_key = tk.Entry(left, font=MONO, bg=BG, fg=FG,
                                insertbackground=FG, relief="flat", show="*")
        self.api_key.pack(fill="x", padx=12, pady=(2, 8))
        self.api_key.insert(0, os.environ.get("OPENAI_API_KEY", ""))

        tk.Label(left, text="Base URL", font=SANS, bg=PANEL, fg=FG2).pack(anchor="w", padx=12)
        self.base_url = tk.Entry(left, font=MONO, bg=BG, fg=FG,
                                 insertbackground=FG, relief="flat")
        self.base_url.pack(fill="x", padx=12, pady=(2, 8))
        self.base_url.insert(0, "https://api.deepseek.com/v1")

        tk.Label(left, text="Model", font=SANS, bg=PANEL, fg=FG2).pack(anchor="w", padx=12)
        self.model = tk.Entry(left, font=MONO, bg=BG, fg=FG,
                              insertbackground=FG, relief="flat")
        self.model.pack(fill="x", padx=12, pady=(2, 16))
        self.model.insert(0, "deepseek-chat")

        ttk.Separator(left, orient="horizontal").pack(fill="x", padx=12, pady=4)

        tk.Label(left, text="运行示例", font=("Segoe UI", 9, "bold"),
                 bg=PANEL, fg=FG2).pack(anchor="w", padx=12, pady=(8, 4))

        for label, script in EXAMPLES:
            btn = tk.Button(left, text=label, font=SANS, bg=BG, fg=FG,
                            activebackground=ACCENT, activeforeground="#fff",
                            relief="flat", cursor="hand2", anchor="w", padx=10,
                            command=lambda s=script: self._run(s))
            btn.pack(fill="x", padx=12, pady=2)

        ttk.Separator(left, orient="horizontal").pack(fill="x", padx=12, pady=10)

        self.stop_btn = tk.Button(left, text="停止运行", font=SANS,
                                  bg="#3a1a1a", fg=RED,
                                  activebackground=RED, activeforeground="#fff",
                                  relief="flat", cursor="hand2",
                                  command=self._stop)
        self.stop_btn.pack(fill="x", padx=12, pady=2)

        tk.Button(left, text="清空输出", font=SANS, bg=BG, fg=FG2,
                  activebackground=PANEL, relief="flat", cursor="hand2",
                  command=self._clear).pack(fill="x", padx=12, pady=2)

        # Right: console output
        right = tk.Frame(body, bg=BG)
        right.pack(side="left", fill="both", expand=True)

        tk.Label(right, text="输出", font=("Segoe UI", 9, "bold"),
                 bg=BG, fg=FG2).pack(anchor="w")

        self.console = scrolledtext.ScrolledText(
            right, font=MONO, bg="#11111b", fg=FG,
            insertbackground=FG, relief="flat",
            wrap="word", state="disabled"
        )
        self.console.pack(fill="both", expand=True)
        self.console.tag_config("ok",  foreground=GREEN)
        self.console.tag_config("err", foreground=RED)
        self.console.tag_config("hdr", foreground=YELLOW)

        # Status bar
        self.status = tk.Label(self, text="就绪", font=("Segoe UI", 8),
                               bg=PANEL, fg=FG2, anchor="w")
        self.status.pack(fill="x", side="bottom")

        self._log("欢迎使用 KylinClaw\n填写 API Key 后点击示例运行，或直接 import kylinclaw 使用。\n", "hdr")

    # ── Helpers ───────────────────────────────────────────────────────

    def _log(self, text, tag=None):
        self.console.configure(state="normal")
        self.console.insert("end", text, tag or "")
        self.console.see("end")
        self.console.configure(state="disabled")

    def _clear(self):
        self.console.configure(state="normal")
        self.console.delete("1.0", "end")
        self.console.configure(state="disabled")

    def _stop(self):
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            self._log("\n[已停止]\n", "err")
            self.status.config(text="已停止")

    def _run(self, script):
        if self._proc and self._proc.poll() is None:
            messagebox.showwarning("运行中", "请先等待当前脚本结束，或点击「停止运行」。")
            return

        script_path = os.path.join(ROOT, script)
        if not os.path.exists(script_path):
            self._log(f"[错误] 找不到文件: {script}\n", "err")
            return

        env = os.environ.copy()
        env["OPENAI_API_KEY"]  = self.api_key.get().strip()
        env["OPENAI_BASE_URL"] = self.base_url.get().strip()
        env["OPENAI_MODEL"]    = self.model.get().strip()
        env["PYTHONPATH"]      = ROOT

        self._log(f"\n{'─'*50}\n运行: {script}\n{'─'*50}\n", "hdr")
        self.status.config(text=f"运行中: {script}")

        self._proc = subprocess.Popen(
            [PYTHON, script_path],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            env=env, text=True, encoding="utf-8", errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        threading.Thread(target=self._stream, daemon=True).start()

    def _stream(self):
        for line in self._proc.stdout:
            self._log(line)
        self._proc.wait()
        rc = self._proc.returncode
        if rc == 0:
            self._log("\n[完成]\n", "ok")
            self.status.config(text="完成")
        else:
            self._log(f"\n[退出码 {rc}]\n", "err")
            self.status.config(text=f"错误 (退出码 {rc})")


if __name__ == "__main__":
    app = App()
    app.mainloop()
