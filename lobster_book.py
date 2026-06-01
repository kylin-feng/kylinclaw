"""
龙虾写书 — AI 自主写书桌面应用
功能：① 自主写书 + 导出 PDF  ② 定时任务  ③ 广场付费阅读
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
import json
import os
import sys
import time
import datetime
import urllib.request
import urllib.error

# ── PDF ──────────────────────────────────────────────────────────────────────
try:
    from fpdf import FPDF
    HAS_PDF = True
except ImportError:
    HAS_PDF = False

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(ROOT, "lobster_data.json")

# ── Colors ────────────────────────────────────────────────────────────────────
BG      = "#0f0f17"
PANEL   = "#1a1a2e"
CARD    = "#16213e"
ACCENT  = "#e85d4a"   # lobster red
ACCENT2 = "#f4a261"   # warm orange
FG      = "#eaeaea"
FG2     = "#8888aa"
GREEN   = "#52c41a"
BORDER  = "#2a2a4a"
MONO    = ("Consolas", 10)
SANS    = ("Segoe UI", 10)
SANS_B  = ("Segoe UI", 10, "bold")
TITLE_F = ("Segoe UI", 13, "bold")

# ── Dummy plaza data ──────────────────────────────────────────────────────────
PLAZA_BOOKS = [
    {"id":1, "title":"深度学习实战指南",   "author":"张明远", "price":9.9,  "preview":"本书系统介绍深度学习核心算法，从感知机到Transformer，配合PyTorch实战代码...", "free":True},
    {"id":2, "title":"个人品牌打造手册",   "author":"李晓雨", "price":19.9, "preview":"在注意力经济时代，个人品牌是最重要的资产。本书提供可执行的7步框架...", "free":False},
    {"id":3, "title":"Python量化交易入门", "author":"王策",   "price":29.9, "preview":"从零开始学习量化交易，掌握数据获取、策略回测、实盘部署全流程...", "free":False},
    {"id":4, "title":"极简主义生活美学",   "author":"陈雅涵", "price":6.9,  "preview":"断舍离不是扔东西，而是一种与物品的关系哲学。本书带你重新审视...", "free":True},
    {"id":5, "title":"创业融资实战笔记",   "author":"赵启明", "price":39.9, "preview":"融过10轮资的创始人亲历总结，Pre-Seed到B轮的完整路径与坑点...", "free":False},
    {"id":6, "title":"AI提示词工程手册",   "author":"刘思远", "price":14.9, "preview":"系统掌握Prompt Engineering，让大模型真正为你所用。涵盖角色设定...", "free":False},
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"api_key": "", "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat", "tasks": [], "purchased": []}

def save_data(d):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

def llm_stream(api_key, base_url, model, messages, on_chunk, on_done, on_error):
    """Call LLM API and stream output via callbacks (runs in thread)."""
    url = base_url.rstrip("/") + "/chat/completions"
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "stream": True,
        "max_tokens": 4096,
    }).encode()
    req = urllib.request.Request(url, data=payload, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            for raw in r:
                line = raw.decode("utf-8").strip()
                if not line.startswith("data:"):
                    continue
                chunk = line[5:].strip()
                if chunk == "[DONE]":
                    break
                try:
                    delta = json.loads(chunk)["choices"][0]["delta"].get("content", "")
                    if delta:
                        on_chunk(delta)
                except Exception:
                    pass
        on_done()
    except Exception as e:
        on_error(str(e))


# ════════════════════════════════════════════════════════════════════
# Main App
# ════════════════════════════════════════════════════════════════════

class LobsterBookApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("龙虾写书")
        self.geometry("1000x660")
        self.minsize(800, 540)
        self.configure(bg=BG)
        self.data = load_data()
        self._book_text = ""
        self._writing = False
        self._timer_thread = None
        self._build()
        self._start_timer_worker()

    # ── Layout ───────────────────────────────────────────────────────

    def _build(self):
        self._build_header()
        self._build_nav()
        self.content = tk.Frame(self, bg=BG)
        self.content.pack(fill="both", expand=True)
        self._pages = {}
        self._build_page_write()
        self._build_page_tasks()
        self._build_page_plaza()
        self._show_page("write")

    def _build_header(self):
        hdr = tk.Frame(self, bg=PANEL, height=56)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="🦞", font=("Segoe UI Emoji", 20),
                 bg=PANEL).pack(side="left", padx=12)
        tk.Label(hdr, text="龙虾写书", font=("Segoe UI", 17, "bold"),
                 bg=PANEL, fg=ACCENT).pack(side="left")
        tk.Label(hdr, text="AI 自主创作 · 一键出版", font=("Segoe UI", 9),
                 bg=PANEL, fg=FG2).pack(side="left", padx=12, pady=16)
        # Settings button
        tk.Button(hdr, text="⚙ 设置", font=SANS, bg=PANEL, fg=FG2,
                  activebackground=BORDER, relief="flat", cursor="hand2",
                  command=self._open_settings).pack(side="right", padx=14)

    def _build_nav(self):
        nav = tk.Frame(self, bg=CARD, height=40)
        nav.pack(fill="x")
        nav.pack_propagate(False)
        self._nav_btns = {}
        for key, label in [("write", "✍ 写书"), ("tasks", "⏰ 定时任务"), ("plaza", "🏪 广场")]:
            btn = tk.Button(nav, text=label, font=SANS_B, bg=CARD, fg=FG2,
                            activebackground=BG, relief="flat", cursor="hand2",
                            padx=20, pady=8,
                            command=lambda k=key: self._show_page(k))
            btn.pack(side="left")
            self._nav_btns[key] = btn

    def _show_page(self, key):
        for k, f in self._pages.items():
            f.pack_forget()
        self._pages[key].pack(fill="both", expand=True)
        for k, btn in self._nav_btns.items():
            btn.config(bg=ACCENT if k == key else CARD,
                       fg="#fff" if k == key else FG2)

    # ── Page: Write ───────────────────────────────────────────────────

    def _build_page_write(self):
        page = tk.Frame(self.content, bg=BG)
        self._pages["write"] = page

        # Left config panel
        left = tk.Frame(page, bg=PANEL, width=240)
        left.pack(side="left", fill="y", padx=(12, 6), pady=12)
        left.pack_propagate(False)

        def lbl(parent, text):
            tk.Label(parent, text=text, font=("Segoe UI", 9),
                     bg=PANEL, fg=FG2).pack(anchor="w", padx=12, pady=(10, 1))

        lbl(left, "书名")
        self.w_title = tk.Entry(left, font=SANS, bg=BG, fg=FG,
                                insertbackground=FG, relief="flat")
        self.w_title.pack(fill="x", padx=12, pady=(0, 2))
        self.w_title.insert(0, "AI时代的个人成长")

        lbl(left, "类型")
        self.w_genre = ttk.Combobox(left, font=SANS, state="readonly",
            values=["商业/管理", "个人成长", "科技/AI", "小说/故事", "知识科普", "投资理财"])
        self.w_genre.pack(fill="x", padx=12, pady=(0, 2))
        self.w_genre.current(1)

        lbl(left, "章节数")
        self.w_chapters = tk.Scale(left, from_=3, to=12, orient="horizontal",
                                   bg=PANEL, fg=FG, troughcolor=BG,
                                   highlightthickness=0, activebackground=ACCENT)
        self.w_chapters.pack(fill="x", padx=12)
        self.w_chapters.set(5)

        lbl(left, "写作风格")
        self.w_style = ttk.Combobox(left, font=SANS, state="readonly",
            values=["专业严谨", "轻松易读", "故事驱动", "数据导向", "励志激励"])
        self.w_style.pack(fill="x", padx=12, pady=(0, 2))
        self.w_style.current(1)

        lbl(left, "简介/大纲（可选）")
        self.w_brief = tk.Text(left, font=SANS, bg=BG, fg=FG,
                               insertbackground=FG, relief="flat",
                               height=5, wrap="word")
        self.w_brief.pack(fill="x", padx=12, pady=(0, 10))

        # Progress
        self.w_progress_var = tk.DoubleVar()
        self.w_progress = ttk.Progressbar(left, variable=self.w_progress_var,
                                          maximum=100)
        self.w_progress.pack(fill="x", padx=12, pady=(4, 2))
        self.w_status_lbl = tk.Label(left, text="待机", font=("Segoe UI", 8),
                                     bg=PANEL, fg=FG2)
        self.w_status_lbl.pack(anchor="w", padx=12)

        tk.Frame(left, bg=BORDER, height=1).pack(fill="x", padx=12, pady=10)

        self.w_start_btn = tk.Button(left, text="▶  开始写书", font=SANS_B,
                                     bg=ACCENT, fg="#fff",
                                     activebackground="#c0392b",
                                     relief="flat", cursor="hand2", pady=8,
                                     command=self._start_writing)
        self.w_start_btn.pack(fill="x", padx=12, pady=2)

        self.w_export_btn = tk.Button(left, text="📄  导出 PDF", font=SANS,
                                      bg=CARD, fg=FG2,
                                      activebackground=ACCENT2,
                                      relief="flat", cursor="hand2", pady=6,
                                      state="disabled",
                                      command=self._export_pdf)
        self.w_export_btn.pack(fill="x", padx=12, pady=2)

        # Right: content preview
        right = tk.Frame(page, bg=BG)
        right.pack(side="left", fill="both", expand=True, padx=(0, 12), pady=12)

        tk.Label(right, text="内容预览", font=("Segoe UI", 9),
                 bg=BG, fg=FG2).pack(anchor="w")
        self.w_preview = scrolledtext.ScrolledText(
            right, font=MONO, bg="#0a0a14", fg=FG,
            insertbackground=FG, relief="flat", wrap="word", state="disabled"
        )
        self.w_preview.pack(fill="both", expand=True)
        self.w_preview.tag_config("chapter", foreground=ACCENT2,
                                  font=("Segoe UI", 11, "bold"))

    def _start_writing(self):
        if self._writing:
            return
        if not self.data["api_key"]:
            messagebox.showwarning("提示", "请先在「设置」中填写 API Key")
            return

        title   = self.w_title.get().strip() or "未命名书籍"
        genre   = self.w_genre.get()
        n_chap  = int(self.w_chapters.get())
        style   = self.w_style.get()
        brief   = self.w_brief.get("1.0", "end").strip()
        self._book_text = f"# {title}\n\n"
        self._writing = True
        self.w_start_btn.config(state="disabled", text="写作中...")
        self.w_export_btn.config(state="disabled")
        self._set_preview("")
        self._preview_append(f"《{title}》\n\n", "chapter")

        def run():
            system_prompt = (
                f"你是一位专业作家，擅长写{genre}类书籍，风格{style}。"
                "每章内容详实，约800-1200字，结构清晰。用中文写作。"
            )
            outline_prompt = (
                f"为书籍《{title}》设计{n_chap}章的大纲，每章给出章节名和100字摘要。"
                + (f"\n参考方向：{brief}" if brief else "")
                + "\n仅输出章节列表，格式：第N章 章节名：摘要"
            )
            # Step 1: generate outline
            self._set_status("生成大纲...")
            outline_text = []
            def on_chunk(c): outline_text.append(c)
            def on_done(): pass
            def on_error(e): self._set_status(f"错误: {e}")
            ev = threading.Event()
            def done_ev(): ev.set()
            llm_stream(
                self.data["api_key"], self.data["base_url"], self.data["model"],
                [{"role": "system", "content": system_prompt},
                 {"role": "user", "content": outline_prompt}],
                on_chunk, done_ev, on_error
            )
            # fallback sync — stream ran synchronously above
            outline = "".join(outline_text)
            self._book_text += f"## 大纲\n\n{outline}\n\n"
            self._preview_append("【大纲】\n" + outline + "\n\n", "chapter")
            self.w_progress_var.set(10)

            # Step 2: write each chapter
            chapters = [l.strip() for l in outline.split("\n") if l.strip().startswith("第") and "章" in l]
            if not chapters:
                chapters = [f"第{i+1}章" for i in range(n_chap)]

            for i, chap_line in enumerate(chapters[:n_chap]):
                chap_name = chap_line.split("：")[0].split(":")[0].strip()
                self._set_status(f"正在写 {chap_name}...")
                self._preview_append(f"\n\n{'─'*40}\n{chap_name}\n{'─'*40}\n\n", "chapter")

                chap_text = []
                ev2 = threading.Event()

                def _chunk(c, store=chap_text): store.append(c); self._preview_append(c)
                def _done(ev=ev2): ev.set()
                def _err(e): self._set_status(f"错误: {e}"); ev2.set()

                llm_stream(
                    self.data["api_key"], self.data["base_url"], self.data["model"],
                    [{"role": "system", "content": system_prompt},
                     {"role": "user", "content":
                      f"书名：《{title}》\n大纲：{outline}\n\n请完整写出「{chap_name}」的全部正文内容，约1000字，不要再列大纲。"}],
                    _chunk, _done, _err
                )
                ev2.wait()
                self._book_text += f"\n\n## {chap_name}\n\n{''.join(chap_text)}"
                progress = 10 + int(90 * (i + 1) / len(chapters[:n_chap]))
                self.w_progress_var.set(progress)
                time.sleep(0.3)

            self._writing = False
            self._set_status("写作完成 ✓")
            self.w_start_btn.config(state="normal", text="▶  开始写书")
            self.w_export_btn.config(state="normal")

        threading.Thread(target=run, daemon=True).start()

    def _set_preview(self, text):
        self.w_preview.configure(state="normal")
        self.w_preview.delete("1.0", "end")
        if text:
            self.w_preview.insert("end", text)
        self.w_preview.configure(state="disabled")

    def _preview_append(self, text, tag=None):
        self.w_preview.configure(state="normal")
        self.w_preview.insert("end", text, tag or "")
        self.w_preview.see("end")
        self.w_preview.configure(state="disabled")

    def _set_status(self, text):
        self.w_status_lbl.config(text=text)

    def _export_pdf(self):
        if not self._book_text.strip():
            messagebox.showinfo("提示", "书籍内容为空，请先完成写作。")
            return
        if not HAS_PDF:
            messagebox.showerror("错误", "PDF 导出模块未安装 (fpdf2)")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF 文件", "*.pdf")],
            initialfile=self.w_title.get().strip() or "我的书籍"
        )
        if not path:
            return
        try:
            pdf = FPDF()
            pdf.set_auto_page_break(auto=True, margin=20)
            font_path = os.path.join(ROOT, "assets", "NotoSansSC-Regular.ttf")
            if os.path.exists(font_path):
                pdf.add_font("NotoSans", "", font_path)
                font_name = "NotoSans"
            else:
                font_name = "Helvetica"

            for line in self._book_text.split("\n"):
                if line.startswith("# "):
                    pdf.add_page()
                    pdf.set_font(font_name, size=22)
                    pdf.cell(0, 14, line[2:], ln=True, align="C")
                    pdf.ln(6)
                elif line.startswith("## "):
                    pdf.add_page()
                    pdf.set_font(font_name, size=16)
                    pdf.cell(0, 10, line[3:], ln=True)
                    pdf.ln(4)
                else:
                    pdf.set_font(font_name, size=11)
                    if line.strip():
                        pdf.multi_cell(0, 7, line)
                    else:
                        pdf.ln(3)

            pdf.output(path)
            messagebox.showinfo("导出成功", f"PDF 已保存至：\n{path}")
        except Exception as e:
            messagebox.showerror("导出失败", str(e))

    # ── Page: Tasks ───────────────────────────────────────────────────

    def _build_page_tasks(self):
        page = tk.Frame(self.content, bg=BG)
        self._pages["tasks"] = page

        # Top: add task form
        form = tk.Frame(page, bg=PANEL)
        form.pack(fill="x", padx=12, pady=12)

        tk.Label(form, text="⏰  新建定时写书任务", font=TITLE_F,
                 bg=PANEL, fg=FG).grid(row=0, column=0, columnspan=4,
                                        sticky="w", padx=12, pady=(10, 6))

        def lbl2(text, row, col):
            tk.Label(form, text=text, font=SANS, bg=PANEL, fg=FG2).grid(
                row=row, column=col, sticky="w", padx=(12, 4), pady=4)

        lbl2("书名主题", 1, 0)
        self.t_title = tk.Entry(form, font=SANS, bg=BG, fg=FG,
                                insertbackground=FG, relief="flat", width=22)
        self.t_title.grid(row=1, column=1, sticky="ew", padx=4, pady=4)

        lbl2("类型", 1, 2)
        self.t_genre = ttk.Combobox(form, font=SANS, state="readonly", width=14,
            values=["商业/管理", "个人成长", "科技/AI", "小说/故事", "知识科普"])
        self.t_genre.grid(row=1, column=3, sticky="ew", padx=(4, 12), pady=4)
        self.t_genre.current(0)

        lbl2("执行时间", 2, 0)
        time_frame = tk.Frame(form, bg=PANEL)
        time_frame.grid(row=2, column=1, sticky="w", padx=4, pady=4)
        self.t_hour = ttk.Spinbox(time_frame, from_=0, to=23, width=4, font=SANS)
        self.t_hour.pack(side="left")
        self.t_hour.set("08")
        tk.Label(time_frame, text=":", bg=PANEL, fg=FG, font=SANS_B).pack(side="left")
        self.t_min = ttk.Spinbox(time_frame, from_=0, to=59, width=4, font=SANS)
        self.t_min.pack(side="left")
        self.t_min.set("00")

        lbl2("重复", 2, 2)
        self.t_repeat = ttk.Combobox(form, font=SANS, state="readonly", width=14,
            values=["每天", "每周一", "每周五", "仅一次"])
        self.t_repeat.grid(row=2, column=3, sticky="ew", padx=(4, 12), pady=4)
        self.t_repeat.current(0)

        tk.Button(form, text="＋ 添加任务", font=SANS_B,
                  bg=ACCENT, fg="#fff", activebackground="#c0392b",
                  relief="flat", cursor="hand2", padx=14, pady=6,
                  command=self._add_task).grid(row=3, column=0, columnspan=4,
                                               sticky="w", padx=12, pady=(4, 10))
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)

        # Task list
        tk.Label(page, text="任务列表", font=("Segoe UI", 9),
                 bg=BG, fg=FG2).pack(anchor="w", padx=14)

        list_frame = tk.Frame(page, bg=BG)
        list_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        cols = ("书名", "类型", "时间", "重复", "状态")
        self.task_tree = ttk.Treeview(list_frame, columns=cols,
                                      show="headings", height=12)
        for col in cols:
            self.task_tree.heading(col, text=col)
        self.task_tree.column("书名", width=200)
        self.task_tree.column("类型", width=100)
        self.task_tree.column("时间", width=80)
        self.task_tree.column("重复", width=80)
        self.task_tree.column("状态", width=80)
        self.task_tree.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(list_frame, orient="vertical",
                           command=self.task_tree.yview)
        sb.pack(side="right", fill="y")
        self.task_tree.configure(yscrollcommand=sb.set)

        tk.Button(page, text="🗑  删除选中任务", font=SANS, bg=CARD, fg=FG2,
                  activebackground=ACCENT, activeforeground="#fff",
                  relief="flat", cursor="hand2", padx=10, pady=4,
                  command=self._delete_task).pack(anchor="w", padx=12, pady=(0, 8))

        self._refresh_task_tree()

    def _add_task(self):
        title  = self.t_title.get().strip()
        genre  = self.t_genre.get()
        hour   = self.t_hour.get().zfill(2)
        minute = self.t_min.get().zfill(2)
        repeat = self.t_repeat.get()
        if not title:
            messagebox.showwarning("提示", "请填写书名主题")
            return
        task = {"id": int(time.time()), "title": title, "genre": genre,
                "time": f"{hour}:{minute}", "repeat": repeat, "status": "待机",
                "enabled": True}
        self.data["tasks"].append(task)
        save_data(self.data)
        self._refresh_task_tree()

    def _delete_task(self):
        sel = self.task_tree.selection()
        if not sel:
            return
        iid = sel[0]
        self.data["tasks"] = [t for t in self.data["tasks"]
                              if str(t["id"]) != str(iid)]
        save_data(self.data)
        self._refresh_task_tree()

    def _refresh_task_tree(self):
        self.task_tree.delete(*self.task_tree.get_children())
        for t in self.data["tasks"]:
            self.task_tree.insert("", "end", iid=str(t["id"]),
                values=(t["title"], t["genre"], t["time"],
                        t["repeat"], t.get("status", "待机")))

    def _start_timer_worker(self):
        def worker():
            while True:
                now = datetime.datetime.now().strftime("%H:%M")
                today = datetime.datetime.now().strftime("%A")
                day_map = {"Monday":"每周一","Friday":"每周五"}
                for task in self.data.get("tasks", []):
                    if not task.get("enabled"):
                        continue
                    if task["time"] == now and task.get("status") != "运行中":
                        repeat = task["repeat"]
                        if repeat == "每天" or repeat == "仅一次":
                            self._trigger_task(task)
                        elif repeat in day_map.values():
                            if day_map.get(today) == repeat:
                                self._trigger_task(task)
                time.sleep(55)
        threading.Thread(target=worker, daemon=True).start()

    def _trigger_task(self, task):
        task["status"] = "运行中"
        save_data(self.data)
        self._refresh_task_tree()
        # Switch to write tab and auto-fill
        self._show_page("write")
        self.w_title.delete(0, "end")
        self.w_title.insert(0, task["title"])
        self._start_writing()
        task["status"] = "完成"
        if task["repeat"] == "仅一次":
            task["enabled"] = False
        save_data(self.data)
        self._refresh_task_tree()

    # ── Page: Plaza ───────────────────────────────────────────────────

    def _build_page_plaza(self):
        page = tk.Frame(self.content, bg=BG)
        self._pages["plaza"] = page

        tk.Label(page, text="📚  作品广场", font=TITLE_F,
                 bg=BG, fg=FG).pack(anchor="w", padx=16, pady=(12, 4))
        tk.Label(page, text="发现 AI 写就的好书，前几章免费，完整版付费解锁",
                 font=SANS, bg=BG, fg=FG2).pack(anchor="w", padx=16)

        canvas = tk.Canvas(page, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(page, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True, padx=12, pady=8)

        inner = tk.Frame(canvas, bg=BG)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        cols = 3
        for idx, book in enumerate(PLAZA_BOOKS):
            row, col = divmod(idx, cols)
            card = tk.Frame(inner, bg=CARD, padx=14, pady=12,
                            relief="flat", bd=0)
            card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
            inner.columnconfigure(col, weight=1)

            # Color band by genre
            colors = [ACCENT, ACCENT2, "#7c6af7", "#52c41a", "#00b4d8", "#e76f51"]
            band = tk.Frame(card, bg=colors[idx % len(colors)], height=4)
            band.pack(fill="x", pady=(0, 8))

            tk.Label(card, text=book["title"], font=("Segoe UI", 11, "bold"),
                     bg=CARD, fg=FG, wraplength=180).pack(anchor="w")
            tk.Label(card, text=f"作者：{book['author']}", font=("Segoe UI", 8),
                     bg=CARD, fg=FG2).pack(anchor="w")
            tk.Label(card, text=book["preview"][:60] + "...", font=("Segoe UI", 8),
                     bg=CARD, fg=FG2, wraplength=180).pack(anchor="w", pady=(6, 8))

            bottom = tk.Frame(card, bg=CARD)
            bottom.pack(fill="x")
            price_text = "前3章免费" if book["free"] else f"¥{book['price']}"
            price_color = GREEN if book["free"] else ACCENT2
            tk.Label(bottom, text=price_text, font=SANS_B,
                     bg=CARD, fg=price_color).pack(side="left")

            purchased = book["id"] in self.data.get("purchased", [])
            if purchased:
                tk.Label(bottom, text="已解锁 ✓", font=SANS,
                         bg=CARD, fg=GREEN).pack(side="right")
            else:
                action = "免费阅读" if book["free"] else f"付费解锁 ¥{book['price']}"
                tk.Button(bottom, text=action, font=("Segoe UI", 8),
                          bg=ACCENT if not book["free"] else CARD,
                          fg="#fff" if not book["free"] else FG2,
                          activebackground="#c0392b",
                          relief="flat", cursor="hand2", padx=8,
                          command=lambda b=book: self._open_book(b)).pack(side="right")

    def _open_book(self, book):
        win = tk.Toplevel(self)
        win.title(book["title"])
        win.geometry("620x520")
        win.configure(bg=BG)

        tk.Label(win, text=book["title"], font=("Segoe UI", 14, "bold"),
                 bg=BG, fg=FG).pack(pady=(16, 2))
        tk.Label(win, text=f"作者：{book['author']}", font=SANS,
                 bg=BG, fg=FG2).pack()
        ttk.Separator(win).pack(fill="x", padx=20, pady=10)

        txt = scrolledtext.ScrolledText(win, font=MONO, bg="#0a0a14", fg=FG,
                                        relief="flat", wrap="word")
        txt.pack(fill="both", expand=True, padx=20)
        txt.insert("end", book["preview"] + "\n\n")

        purchased = book["id"] in self.data.get("purchased", [])

        if book["free"] or purchased:
            txt.insert("end", "[完整内容]\n\n这里是书籍的完整正文内容……\n\n（示例：连接后端后可获取真实内容）")
            txt.configure(state="disabled")
        else:
            txt.insert("end", "\n\n" + "█" * 30 + "\n\n内容已锁定，付费后可阅读全文。")
            txt.configure(state="disabled")
            btm = tk.Frame(win, bg=BG)
            btm.pack(fill="x", padx=20, pady=10)
            tk.Button(btm, text=f"确认付费解锁  ¥{book['price']}",
                      font=SANS_B, bg=ACCENT, fg="#fff",
                      activebackground="#c0392b", relief="flat",
                      cursor="hand2", pady=8,
                      command=lambda: self._purchase(book, win)).pack(fill="x")

    def _purchase(self, book, win):
        ans = messagebox.askyesno("确认付费",
            f"确认支付 ¥{book['price']} 解锁《{book['title']}》完整版？\n（演示模式：直接解锁，不扣费）")
        if ans:
            if "purchased" not in self.data:
                self.data["purchased"] = []
            self.data["purchased"].append(book["id"])
            save_data(self.data)
            win.destroy()
            messagebox.showinfo("解锁成功", f"《{book['title']}》已解锁，请重新打开阅读。")

    # ── Settings dialog ───────────────────────────────────────────────

    def _open_settings(self):
        win = tk.Toplevel(self)
        win.title("设置")
        win.geometry("420x260")
        win.configure(bg=PANEL)
        win.resizable(False, False)

        def row(label, var_name, default, show=None):
            tk.Label(win, text=label, font=SANS, bg=PANEL, fg=FG2).pack(
                anchor="w", padx=20, pady=(10, 1))
            e = tk.Entry(win, font=MONO, bg=BG, fg=FG, insertbackground=FG,
                         relief="flat", show=show)
            e.pack(fill="x", padx=20)
            e.insert(0, self.data.get(var_name, default))
            return e, var_name

        entries = [
            row("API Key", "api_key", "", show="*"),
            row("Base URL", "base_url", "https://api.deepseek.com/v1"),
            row("Model", "model", "deepseek-chat"),
        ]

        def save():
            for entry, key in entries:
                self.data[key] = entry.get().strip()
            save_data(self.data)
            win.destroy()
            messagebox.showinfo("已保存", "设置已保存。")

        tk.Button(win, text="保存", font=SANS_B, bg=ACCENT, fg="#fff",
                  activebackground="#c0392b", relief="flat",
                  cursor="hand2", pady=8, command=save).pack(
                      fill="x", padx=20, pady=16)


# ── Entry ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = LobsterBookApp()
    app.mainloop()
