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

# ── Database ──────────────────────────────────────────────────────────────────
try:
    import pymysql
    HAS_DB = True
except ImportError:
    HAS_DB = False

DB_CONFIG = dict(
    host="106.53.86.215", port=3306,
    user="root", password="Ffqm110013!@#",
    database="lobster_book", charset="utf8mb4",
    connect_timeout=8,
)

WECHAT_CONTACT = "13342491933"

def db_verify_code(code: str, book_id: int) -> tuple[bool, str]:
    """
    验证激活码。返回 (success, message)。
    book_id=0 表示任意书籍均可。
    """
    if not HAS_DB:
        return False, "数据库模块未加载"
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute(
            "SELECT book_id, used FROM activation_codes WHERE code=%s",
            (code.strip().upper(),)
        )
        row = cur.fetchone()
        if not row:
            conn.close()
            return False, "激活码无效"
        db_book_id, used = row
        if used:
            conn.close()
            return False, "该激活码已被使用"
        # book_id=0 的码可解锁任意书；特定 book_id 的码只能解锁对应书
        if db_book_id != 0 and db_book_id != book_id:
            conn.close()
            return False, "该激活码不适用于此书籍"
        # 标记为已用
        cur.execute(
            "UPDATE activation_codes SET used=1, used_at=NOW() WHERE code=%s",
            (code.strip().upper(),)
        )
        conn.commit()
        conn.close()
        return True, "激活成功"
    except Exception as e:
        return False, f"网络错误: {e}"

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

DEFAULT_SOUL = (
    "你是一位资深专业作家，文字功底深厚，逻辑严密，擅长把复杂知识讲得深入浅出。"
    "你写的书结构清晰、观点鲜明、案例丰富，读者读完后有明显的收获感。"
    "用中文写作，语言流畅自然，避免堆砌辞藻。"
)

# category → color
SKILL_CATS = {
    "结构": "#7c6af7",
    "表达": "#3b9eff",
    "节奏": "#f4a261",
    "互动": "#52c41a",
    "深度": "#20c997",
    "风格": "#e85d9a",
}

DEFAULT_SKILLS = [
    # 结构
    {"id":1,  "cat":"结构", "name":"故事驱动",   "desc":"每章以真实故事开场，让读者自然融入",
     "enabled":False, "prompt":"每章以一个真实故事或案例开头，用叙事方式引入核心观点，增强代入感。"},
    {"id":2,  "cat":"结构", "name":"总分总",     "desc":"先亮结论，再展开，最后总结升华",
     "enabled":False, "prompt":"每章严格遵循总-分-总结构：先给出核心结论，再逐点展开论述，最后总结并升华。"},
    {"id":3,  "cat":"结构", "name":"金字塔原理", "desc":"结论前置，逻辑层层递进",
     "enabled":False, "prompt":"采用金字塔原理：最重要的结论放在最前面，后续内容都是对结论的支撑和论证。"},
    {"id":4,  "cat":"结构", "name":"章节呼应",   "desc":"前后章节相互引用，形成整体感",
     "enabled":False, "prompt":"章节之间相互呼应，后章引用前章内容并深化，前章为后章埋下伏笔，增强全书整体感。"},
    {"id":5,  "cat":"结构", "name":"反转叙事",   "desc":"先呈现常见误解，再揭示真相",
     "enabled":False, "prompt":"每章先呈现读者普遍持有的误解或常识，然后用证据揭示真相，制造认知反转。"},
    # 表达
    {"id":6,  "cat":"表达", "name":"数据支撑",   "desc":"关键观点配具体数字和研究佐证",
     "enabled":False, "prompt":"关键论点必须引用具体数据、研究报告或权威来源，增强说服力和可信度。"},
    {"id":7,  "cat":"表达", "name":"类比教学",   "desc":"用生活比喻把抽象概念讲透彻",
     "enabled":False, "prompt":"用生动的比喻和类比解释抽象概念，让零基础读者也能快速理解。"},
    {"id":8,  "cat":"表达", "name":"金句提炼",   "desc":"每章萃取2-3句值得收藏的精华",
     "enabled":True,  "prompt":"每章提炼2-3句核心金句，用加粗或独立段落标注，方便读者摘录。"},
    {"id":9,  "cat":"表达", "name":"对话体",     "desc":"穿插对话和问答，轻松好读",
     "enabled":False, "prompt":"穿插对话、采访或问答形式，让内容像交谈一样自然流畅，减少阅读疲劳。"},
    {"id":10, "cat":"表达", "name":"专家背书",   "desc":"引用权威人士观点增强可信度",
     "enabled":False, "prompt":"引用知名专家、学者或成功人士的观点和经历，为核心论点提供权威背书。"},
    {"id":11, "cat":"表达", "name":"案例矩阵",   "desc":"每个观点配正反两个真实案例",
     "enabled":False, "prompt":"每个核心观点提供正面成功案例和反面失败案例各一个，通过对比加深理解。"},
    # 节奏
    {"id":12, "cat":"节奏", "name":"悬念钩子",   "desc":"每章结尾留悬念，让人忍不住翻页",
     "enabled":False, "prompt":"每章结尾设置悬念或留下问题，驱动读者继续阅读下一章。"},
    {"id":13, "cat":"节奏", "name":"短句冲击",   "desc":"关键观点用短句呈现，直击内心",
     "enabled":False, "prompt":"关键观点和核心结论使用短句表达，1句话1个意思，增强冲击力和记忆度。"},
    {"id":14, "cat":"节奏", "name":"留白呼吸",   "desc":"张弛有度，给读者留下思考空间",
     "enabled":False, "prompt":"内容张弛有度，重要观点之后留有过渡段落，给读者消化和思考的空间。"},
    {"id":15, "cat":"节奏", "name":"情绪起伏",   "desc":"高潮与舒缓交替，阅读不疲劳",
     "enabled":False, "prompt":"章节内容安排情绪起伏：紧张与舒缓交替，高潮与平静相间，维持读者阅读动力。"},
    # 互动
    {"id":16, "cat":"互动", "name":"行动导向",   "desc":"每章结尾给出可立刻执行的步骤",
     "enabled":True,  "prompt":"每章结尾提供3-5条可立即执行的行动清单，让读者知道下一步怎么做。"},
    {"id":17, "cat":"互动", "name":"问题引导",   "desc":"用问题开启段落，激发读者思考",
     "enabled":False, "prompt":"每个重要段落用一个问题开启，引发读者思考，再给出解答，增强参与感。"},
    {"id":18, "cat":"互动", "name":"读者代入",   "desc":'大量用"你"，让读者感同身受',
     "enabled":False, "prompt":'大量使用第二人称"你"，将读者直接代入场景，让内容与读者产生直接关联。'},
    {"id":19, "cat":"互动", "name":"读者痛点",   "desc":"从读者痛点切入，引发强烈共鸣",
     "enabled":False, "prompt":"每章从读者最熟悉的痛点或困惑切入，精准戳中内心，引发强烈共鸣后再给出解法。"},
    {"id":20, "cat":"互动", "name":"实用工具",   "desc":"提供清单、表格、框架等工具",
     "enabled":False, "prompt":"为读者提供可直接使用的工具：清单、框架、表格、公式，让书变成工具书。"},
    # 深度
    {"id":21, "cat":"深度", "name":"批判视角",   "desc":"主动呈现反对声音，体现思考深度",
     "enabled":False, "prompt":"主动呈现反对观点和潜在风险，体现客观性，避免一味正面论述。"},
    {"id":22, "cat":"深度", "name":"历史溯源",   "desc":"追溯概念的来龙去脉，增加厚度",
     "enabled":False, "prompt":'追溯核心概念的历史背景、起源和演变过程，让读者理解"为什么"而非只知道"是什么"。'},
    {"id":23, "cat":"深度", "name":"跨领域连接", "desc":"打通不同领域，产生意外洞见",
     "enabled":False, "prompt":"将本书主题与其他领域（哲学、心理学、生物学等）的知识连接，产生跨界洞见。"},
    {"id":24, "cat":"深度", "name":"第一原理",   "desc":"回归底层逻辑，重建认知框架",
     "enabled":False, "prompt":"用第一原理思维，从最基础的事实和假设出发，重新推导结论，而不是依赖行业惯例。"},
    # 风格
    {"id":25, "cat":"风格", "name":"幽默调侃",   "desc":"适当加入幽默，阅读不枯燥",
     "enabled":False, "prompt":"适当加入幽默感和自嘲，让严肃内容变得轻松，减少读者的阅读疲劳。"},
    {"id":26, "cat":"风格", "name":"极简克制",   "desc":"每句话都有信息量，去掉废话",
     "enabled":False, "prompt":"极简写作：去除所有冗余词汇和套话，每句话都必须有实质信息量，宁可少说不废话。"},
    {"id":27, "cat":"风格", "name":"场景还原",   "desc":"还原真实场景，画面感十足",
     "enabled":False, "prompt":"用细节还原真实场景：时间、地点、人物、对话，让读者如临其境，增强代入感。"},
]

def load_data():
    defaults = {
        "api_key": "", "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat", "tasks": [], "purchased": [],
        "soul": DEFAULT_SOUL, "skills": DEFAULT_SKILLS,
    }
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                defaults.update(saved)
                # 补全新增字段
                if "soul" not in saved:
                    defaults["soul"] = DEFAULT_SOUL
                if "skills" not in saved:
                    defaults["skills"] = DEFAULT_SKILLS
                return defaults
        except Exception:
            pass
    return defaults


def llm_call(api_key, base_url, model, messages, timeout=30) -> str:
    """Non-streaming LLM call, returns full response text."""
    url = base_url.rstrip("/") + "/chat/completions"
    payload = json.dumps({
        "model": model, "messages": messages,
        "stream": False, "max_tokens": 512,
    }).encode()
    req = urllib.request.Request(url, data=payload, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"]

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
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="ignore")
        except Exception:
            pass
        if e.code == 401:
            on_error("401 未认证 — 请在「设置」中检查 API Key 是否正确")
        elif e.code == 429:
            on_error("429 请求过频 — 请稍后重试")
        else:
            on_error(f"HTTP {e.code}: {body[:120]}")
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
        self._build_page_skills()
        self._build_page_soul()
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
        for key, label in [("write", "✍ 写书"), ("skills", "⚡ 技能"), ("soul", "✨ 灵魂"), ("tasks", "⏰ 定时任务"), ("plaza", "🏪 广场")]:
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

    # ── Thread-safe UI helpers ────────────────────────────────────────

    def _ui(self, fn):
        """Schedule fn() on the main thread (safe to call from any thread)."""
        self.after(0, fn)

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

    def _set_progress(self, val):
        self.w_progress_var.set(val)

    # ── Writing logic ─────────────────────────────────────────────────

    def _start_writing(self):
        if self._writing:
            return
        if not self.data["api_key"]:
            messagebox.showwarning("提示", "请先在「设置」中填写 API Key")
            return

        title  = self.w_title.get().strip() or "未命名书籍"
        genre  = self.w_genre.get()
        n_chap = int(self.w_chapters.get())
        style  = self.w_style.get()
        brief  = self.w_brief.get("1.0", "end").strip()

        self._book_text = f"# {title}\n\n"
        self._writing = True
        self.w_start_btn.config(state="disabled", text="写作中...")
        self.w_export_btn.config(state="disabled")
        self._set_preview("")
        self._preview_append(f"《{title}》\n\n", "chapter")

        def run():
            try:
                # 灵魂 + 已启用技能 拼接成最终 system prompt
                soul = self.data.get("soul", DEFAULT_SOUL)
                active_skills = [s for s in self.data.get("skills", []) if s.get("enabled")]
                skill_lines = "\n".join(f"- {s['name']}：{s['prompt']}" for s in active_skills)
                system_prompt = (
                    f"{soul}\n\n"
                    f"当前写作方向：{genre}类书籍，风格{style}。每章约800-1200字，结构清晰。"
                    + (f"\n\n写作技能要求：\n{skill_lines}" if skill_lines else "")
                )

                # ── Step 1: 生成大纲 ──────────────────────────────
                self._ui(lambda: self._set_status("正在生成大纲..."))
                outline_prompt = (
                    f"为书籍《{title}》设计{n_chap}章的大纲，每章给出章节名和100字摘要。"
                    + (f"\n参考方向：{brief}" if brief else "")
                    + "\n仅输出章节列表，格式：第N章 章节名：摘要"
                )
                outline_parts = []
                error_box = [None]

                def _outline_chunk(c):
                    outline_parts.append(c)
                    self._ui(lambda c=c: self._preview_append(c))

                def _outline_err(e):
                    error_box[0] = e

                llm_stream(
                    self.data["api_key"], self.data["base_url"], self.data["model"],
                    [{"role": "system", "content": system_prompt},
                     {"role": "user",   "content": outline_prompt}],
                    _outline_chunk, lambda: None, _outline_err
                )

                if error_box[0]:
                    self._ui(lambda e=error_box[0]: self._set_status(f"错误: {e}"))
                    self._ui(lambda: self.w_start_btn.config(state="normal", text="▶  开始写书"))
                    self._writing = False
                    return

                outline = "".join(outline_parts)
                self._book_text += f"## 大纲\n\n{outline}\n\n"
                self._ui(lambda: self._set_progress(10))

                # ── Step 2: 逐章写作 ──────────────────────────────
                chapters = [
                    l.strip() for l in outline.split("\n")
                    if l.strip() and l.strip()[0] in "第123456789" and "章" in l
                ]
                if not chapters:
                    chapters = [f"第{i+1}章" for i in range(n_chap)]

                total = len(chapters[:n_chap])
                for i, chap_line in enumerate(chapters[:n_chap]):
                    chap_name = chap_line.split("：")[0].split(":")[0].strip()
                    sep = "─" * 38
                    self._ui(lambda s=sep, cn=chap_name:
                             self._preview_append(f"\n\n{s}\n{cn}\n{s}\n\n", "chapter"))
                    self._ui(lambda cn=chap_name: self._set_status(f"正在写 {cn}..."))

                    chap_parts = []
                    chap_error = [None]

                    def _chap_chunk(c, store=chap_parts):
                        store.append(c)
                        self._ui(lambda c=c: self._preview_append(c))

                    def _chap_err(e, eb=chap_error):
                        eb[0] = e

                    llm_stream(
                        self.data["api_key"], self.data["base_url"], self.data["model"],
                        [{"role": "system", "content": system_prompt},
                         {"role": "user",   "content":
                          f"书名：《{title}》\n大纲：{outline}\n\n"
                          f"请完整写出「{chap_name}」的全部正文内容，约1000字，只写正文不要重复列大纲。"}],
                        _chap_chunk, lambda: None, _chap_err
                    )

                    if chap_error[0]:
                        self._ui(lambda e=chap_error[0]: self._set_status(f"章节错误: {e}"))
                        break

                    self._book_text += f"\n\n## {chap_name}\n\n{''.join(chap_parts)}"
                    prog = 10 + int(90 * (i + 1) / total)
                    self._ui(lambda p=prog: self._set_progress(p))

                # ── 完成 ──────────────────────────────────────────
                self._writing = False
                self._ui(lambda: self._set_status("写作完成 ✓"))
                self._ui(lambda: self._set_progress(100))
                self._ui(lambda: self.w_start_btn.config(state="normal", text="▶  开始写书"))
                self._ui(lambda: self.w_export_btn.config(state="normal"))

            except Exception as e:
                self._writing = False
                self._ui(lambda e=e: self._set_status(f"异常: {e}"))
                self._ui(lambda: self.w_start_btn.config(state="normal", text="▶  开始写书"))

        threading.Thread(target=run, daemon=True).start()

    def _export_pdf(self):
        if not self._book_text.strip():
            messagebox.showinfo("提示", "书籍内容为空，请先完成写作。")
            return
        if not HAS_PDF:
            messagebox.showerror("错误", "PDF 导出模块未安装 (fpdf2)")
            return
        self._show_export_dialog()

    # ── Export dialog ─────────────────────────────────────────────────

    PDF_STYLES = {
        "简约白": {
            "cover_bg": (255, 255, 255), "cover_fg": (20, 20, 30),
            "accent": (220, 80, 50),     "body_bg": (255, 255, 255),
            "body_fg": (30, 30, 30),     "chapter_fg": (200, 70, 40),
        },
        "商务深": {
            "cover_bg": (18, 24, 52),    "cover_fg": (240, 240, 255),
            "accent": (100, 140, 255),   "body_bg": (255, 255, 255),
            "body_fg": (20, 20, 40),     "chapter_fg": (60, 100, 200),
        },
        "暖 橙": {
            "cover_bg": (220, 80, 40),   "cover_fg": (255, 245, 235),
            "accent": (255, 200, 60),    "body_bg": (255, 255, 255),
            "body_fg": (40, 20, 10),     "chapter_fg": (200, 70, 30),
        },
        "松 绿": {
            "cover_bg": (28, 72, 58),    "cover_fg": (230, 255, 240),
            "accent": (90, 210, 140),    "body_bg": (255, 255, 255),
            "body_fg": (20, 40, 30),     "chapter_fg": (30, 130, 90),
        },
        "学术灰": {
            "cover_bg": (55, 58, 68),    "cover_fg": (240, 240, 245),
            "accent": (180, 180, 210),   "body_bg": (255, 255, 255),
            "body_fg": (30, 30, 35),     "chapter_fg": (80, 80, 110),
        },
    }

    def _show_export_dialog(self):
        win = tk.Toplevel(self)
        win.title("导出书籍 PDF")
        win.geometry("720x620")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.grab_set()

        title = self.w_title.get().strip() or "未命名书籍"
        self._export_style = tk.StringVar(value="商务深")

        # ── Header ───────────────────────────────────────────────────
        tk.Label(win, text=f"导出《{title}》", font=("Segoe UI", 13, "bold"),
                 bg=BG, fg=FG).pack(anchor="w", padx=20, pady=(16, 4))

        # ── Style picker ──────────────────────────────────────────────
        style_frame = tk.Frame(win, bg=PANEL)
        style_frame.pack(fill="x", padx=20, pady=(0, 8))
        tk.Label(style_frame, text="封面风格", font=SANS_B,
                 bg=PANEL, fg=FG2).pack(anchor="w", padx=12, pady=(8, 4))
        btn_row = tk.Frame(style_frame, bg=PANEL)
        btn_row.pack(anchor="w", padx=12, pady=(0, 10))
        self._style_btns = {}
        for name, st in self.PDF_STYLES.items():
            bg_hex = "#{:02x}{:02x}{:02x}".format(*st["cover_bg"])
            fg_hex = "#{:02x}{:02x}{:02x}".format(*st["cover_fg"])
            ac_hex = "#{:02x}{:02x}{:02x}".format(*st["accent"])
            btn = tk.Button(btn_row, text=name, font=("Segoe UI", 9, "bold"),
                            bg=bg_hex, fg=fg_hex,
                            activebackground=ac_hex, activeforeground=fg_hex,
                            relief="flat", cursor="hand2", padx=14, pady=8,
                            command=lambda n=name: self._select_style(n))
            btn.pack(side="left", padx=3)
            self._style_btns[name] = btn
        self._select_style("商务深")

        # ── Book info ─────────────────────────────────────────────────
        info_frame = tk.Frame(win, bg=PANEL)
        info_frame.pack(fill="x", padx=20, pady=(0, 8))

        def info_row(parent, label, default="", show=None):
            row = tk.Frame(parent, bg=PANEL)
            row.pack(fill="x", padx=12, pady=3)
            tk.Label(row, text=label, font=SANS, bg=PANEL, fg=FG2,
                     width=6, anchor="e").pack(side="left", padx=(0, 8))
            e = tk.Entry(row, font=SANS, bg=BG, fg=FG, insertbackground=FG,
                         relief="flat", show=show)
            e.pack(side="left", fill="x", expand=True, ipady=4)
            e.insert(0, default)
            return e

        tk.Label(info_frame, text="书籍信息", font=SANS_B,
                 bg=PANEL, fg=FG2).pack(anchor="w", padx=12, pady=(8, 2))
        self.exp_author   = info_row(info_frame, "作者", "龙虾写书")
        self.exp_subtitle = info_row(info_frame, "副标题", "")
        tk.Frame(info_frame, bg=BG, height=6).pack()

        # ── Preface + Postscript ──────────────────────────────────────
        mid = tk.Frame(win, bg=BG)
        mid.pack(fill="both", expand=True, padx=20, pady=(0, 8))
        mid.columnconfigure(0, weight=1)
        mid.columnconfigure(1, weight=1)

        def section(parent, col, label, attr):
            f = tk.Frame(parent, bg=PANEL)
            f.grid(row=0, column=col, sticky="nsew", padx=(0 if col else 0, 6 if col==0 else 0))
            hdr = tk.Frame(f, bg=PANEL)
            hdr.pack(fill="x", padx=10, pady=(8, 2))
            tk.Label(hdr, text=label, font=SANS_B, bg=PANEL, fg=FG2).pack(side="left")
            tk.Button(hdr, text="AI生成", font=("Segoe UI", 8),
                      bg=ACCENT, fg="#fff", activebackground="#c0392b",
                      relief="flat", cursor="hand2", padx=6, pady=2,
                      command=lambda a=attr, lbl=label: self._ai_gen_section(a, lbl, title)
                      ).pack(side="right")
            txt = tk.Text(f, font=("Segoe UI", 9), bg=BG, fg=FG,
                          insertbackground=FG, relief="flat", wrap="word", height=7)
            txt.pack(fill="both", expand=True, padx=10, pady=(0, 10))
            setattr(self, attr, txt)

        section(mid, 0, "前  言", "exp_preface")
        section(mid, 1, "后  记", "exp_postscript")

        # ── Back cover text ───────────────────────────────────────────
        back_frame = tk.Frame(win, bg=PANEL)
        back_frame.pack(fill="x", padx=20, pady=(0, 10))
        tk.Label(back_frame, text="封底简介（可选）", font=SANS_B,
                 bg=PANEL, fg=FG2).pack(anchor="w", padx=12, pady=(8, 2))
        self.exp_backcover = tk.Entry(back_frame, font=SANS, bg=BG, fg=FG,
                                      insertbackground=FG, relief="flat")
        self.exp_backcover.pack(fill="x", padx=12, pady=(0, 10), ipady=4)
        self.exp_backcover.insert(0, "本书由 AI 自主创作，龙虾写书出品")

        # ── Buttons ───────────────────────────────────────────────────
        btn_bar = tk.Frame(win, bg=BG)
        btn_bar.pack(fill="x", padx=20, pady=(0, 14))
        tk.Button(btn_bar, text="取消", font=SANS, bg=CARD, fg=FG2,
                  relief="flat", cursor="hand2", padx=16, pady=6,
                  command=win.destroy).pack(side="right", padx=4)
        tk.Button(btn_bar, text="📄  导出 PDF", font=SANS_B,
                  bg=ACCENT, fg="#fff", activebackground="#c0392b",
                  relief="flat", cursor="hand2", padx=20, pady=6,
                  command=lambda: self._do_export(win, title)).pack(side="right")

    def _select_style(self, name):
        self._export_style.set(name)
        for n, btn in self._style_btns.items():
            st = self.PDF_STYLES[n]
            bg_hex = "#{:02x}{:02x}{:02x}".format(*st["cover_bg"])
            fg_hex = "#{:02x}{:02x}{:02x}".format(*st["cover_fg"])
            if n == name:
                btn.config(relief="solid", bd=2)
            else:
                btn.config(relief="flat", bd=0)

    def _ai_gen_section(self, attr, label, title):
        if not self.data["api_key"]:
            messagebox.showwarning("提示", "请先在「设置」中填写 API Key")
            return
        widget = getattr(self, attr)
        widget.delete("1.0", "end")
        widget.insert("1.0", "AI生成中…")

        is_preface = "前" in label
        prompt = (
            f"为书籍《{title}》写一段{'前言' if is_preface else '后记'}，"
            f"约200字，{'介绍本书的写作背景、目的和读者收益' if is_preface else '总结写作感悟、致谢和展望'}，"
            "语言真诚自然，不要太正式。"
        )
        def gen():
            try:
                text = llm_call(
                    self.data["api_key"], self.data["base_url"], self.data["model"],
                    [{"role": "user", "content": prompt}], timeout=30
                )
                def update():
                    widget.delete("1.0", "end")
                    widget.insert("1.0", text)
                self.after(0, update)
            except Exception as e:
                self.after(0, lambda: widget.delete("1.0", "end"))
                self.after(0, lambda: widget.insert("1.0", f"生成失败: {e}"))
        threading.Thread(target=gen, daemon=True).start()

    def _do_export(self, win, title):
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF 文件", "*.pdf")],
            initialfile=title,
            parent=win,
        )
        if not path:
            return

        style_name = self._export_style.get()
        st = self.PDF_STYLES[style_name]
        author    = self.exp_author.get().strip() or "龙虾写书"
        subtitle  = self.exp_subtitle.get().strip()
        preface   = self.exp_preface.get("1.0", "end").strip()
        postscript= self.exp_postscript.get("1.0", "end").strip()
        back_text = self.exp_backcover.get().strip()
        book_text = self._book_text

        win.destroy()

        def build():
            try:
                # ── 加载中文字体 ──────────────────────────────────────
                font_candidates = [
                    r"C:\Windows\Fonts\simhei.ttf",
                    r"C:\Windows\Fonts\simsun.ttc",
                    r"C:\Windows\Fonts\msyh.ttc",
                ]
                font_path = next((p for p in font_candidates if os.path.exists(p)), None)

                pdf = FPDF(orientation="P", unit="mm", format="A4")
                pdf.set_auto_page_break(auto=True, margin=22)

                if font_path:
                    pdf.add_font("CN", "", font_path)
                    fn = "CN"
                else:
                    fn = "Helvetica"

                W, H = 210, 297

                def r(rgb): return rgb  # alias

                # ── 封面 ──────────────────────────────────────────────
                pdf.add_page()
                cbg = st["cover_bg"]
                pdf.set_fill_color(*cbg)
                pdf.rect(0, 0, W, H, "F")

                # accent bar left
                ac = st["accent"]
                pdf.set_fill_color(*ac)
                pdf.rect(0, 0, 12, H, "F")

                # title
                cfg = st["cover_fg"]
                pdf.set_text_color(*cfg)
                pdf.set_font(fn, size=36)
                pdf.set_xy(22, H * 0.28)
                pdf.multi_cell(W - 34, 14, title, align="L")

                # subtitle
                if subtitle:
                    pdf.set_font(fn, size=14)
                    pdf.set_text_color(*ac)
                    pdf.set_x(22)
                    pdf.cell(0, 10, subtitle, ln=True)

                # divider line
                pdf.set_draw_color(*ac)
                pdf.set_line_width(0.8)
                y_line = pdf.get_y() + 6
                pdf.line(22, y_line, W - 22, y_line)

                # author
                pdf.set_font(fn, size=13)
                pdf.set_text_color(*cfg)
                pdf.set_xy(22, y_line + 8)
                pdf.cell(0, 8, f"作者：{author}", ln=True)

                # brand bottom
                pdf.set_font(fn, size=9)
                pdf.set_text_color(*[c//2 + 80 for c in cbg])
                pdf.set_xy(22, H - 20)
                pdf.cell(0, 6, "龙虾写书  ·  AI 自主创作", ln=True)

                # ── 版权页 ────────────────────────────────────────────
                pdf.add_page()
                pdf.set_text_color(80, 80, 90)
                pdf.set_font(fn, size=10)
                pdf.set_xy(25, 40)
                pdf.multi_cell(W - 50, 7,
                    f"书名：{title}\n作者：{author}\n"
                    f"{"副标题：" + subtitle + chr(10) if subtitle else ""}"
                    f"出版：龙虾写书\n\n"
                    "本书由 AI 自主创作完成。\n版权所有，未经授权不得转载。",
                    align="L"
                )

                # ── 前言 ──────────────────────────────────────────────
                if preface:
                    pdf.add_page()
                    _chapter_header(pdf, fn, st, W, "前  言")
                    pdf.set_font(fn, size=11)
                    pdf.set_text_color(*st["body_fg"])
                    pdf.set_x(25)
                    pdf.multi_cell(W - 50, 7, preface)

                # ── 目录 ──────────────────────────────────────────────
                chapters_list = [
                    l.strip() for l in book_text.split("\n")
                    if l.startswith("## ") and not l.startswith("## 大纲")
                ]
                if chapters_list:
                    pdf.add_page()
                    _chapter_header(pdf, fn, st, W, "目  录")
                    pdf.set_font(fn, size=11)
                    pdf.set_text_color(*st["body_fg"])
                    for i, ch in enumerate(chapters_list, 1):
                        name = ch[3:].strip()
                        pdf.set_x(25)
                        pdf.cell(W - 50, 8, f"{i}.  {name}", ln=True)

                # ── 正文各章 ──────────────────────────────────────────
                lines = book_text.split("\n")
                skip_outline = False
                for line in lines:
                    if line.startswith("# "):
                        continue  # 封面已有标题
                    if line.startswith("## 大纲"):
                        skip_outline = True
                        continue
                    if skip_outline and line.startswith("## "):
                        skip_outline = False
                    if skip_outline:
                        continue
                    if line.startswith("## "):
                        pdf.add_page()
                        _chapter_header(pdf, fn, st, W, line[3:].strip())
                    else:
                        pdf.set_font(fn, size=11)
                        pdf.set_text_color(*st["body_fg"])
                        if line.strip():
                            pdf.set_x(25)
                            pdf.multi_cell(W - 50, 7, line.strip())
                        else:
                            pdf.ln(3)

                # ── 后记 ──────────────────────────────────────────────
                if postscript:
                    pdf.add_page()
                    _chapter_header(pdf, fn, st, W, "后  记")
                    pdf.set_font(fn, size=11)
                    pdf.set_text_color(*st["body_fg"])
                    pdf.set_x(25)
                    pdf.multi_cell(W - 50, 7, postscript)

                # ── 封底 ──────────────────────────────────────────────
                pdf.add_page()
                pdf.set_fill_color(*st["cover_bg"])
                pdf.rect(0, 0, W, H, "F")
                pdf.set_fill_color(*st["accent"])
                pdf.rect(W - 12, 0, 12, H, "F")

                if back_text:
                    pdf.set_font(fn, size=12)
                    pdf.set_text_color(*st["cover_fg"])
                    pdf.set_xy(22, H * 0.4)
                    pdf.multi_cell(W - 46, 8, back_text, align="L")

                pdf.set_font(fn, size=10)
                pdf.set_text_color(*st["accent"])
                pdf.set_xy(22, H - 24)
                pdf.cell(0, 6, f"《{title}》  ·  {author}", ln=True)

                pdf.output(path)
                self.after(0, lambda: messagebox.showinfo("导出成功", f"PDF 已保存至：\n{path}"))
            except Exception as e:
                self.after(0, lambda e=e: messagebox.showerror("导出失败", str(e)))

        threading.Thread(target=build, daemon=True).start()


def _repaint_card(widget, bg):
    """Recursively update bg of a card and its children."""
    try:
        widget.configure(bg=bg)
    except Exception:
        pass
    for child in widget.winfo_children():
        # Don't repaint the colored top bar
        if isinstance(child, tk.Frame) and child.winfo_height() == 3:
            continue
        _repaint_card(child, bg)


def _chapter_header(pdf, fn, st, W, text):
    """渲染章节标题页眉样式。"""
    ac = st["accent"]
    pdf.set_fill_color(*ac)
    pdf.rect(0, 0, 8, 40, "F")
    pdf.set_font(fn, size=18)
    pdf.set_text_color(*st["chapter_fg"])
    pdf.set_xy(16, 14)
    pdf.cell(0, 10, text, ln=True)
    pdf.set_draw_color(*ac)
    pdf.set_line_width(0.4)
    pdf.line(16, 28, W - 20, 28)
    pdf.ln(8)

    # ── Page: Tasks (NLP input) ───────────────────────────────────────

    def _build_page_tasks(self):
        page = tk.Frame(self.content, bg=BG)
        self._pages["tasks"] = page

        # Input area
        top = tk.Frame(page, bg=PANEL)
        top.pack(fill="x", padx=12, pady=12)

        tk.Label(top, text="⏰  定时写书任务", font=TITLE_F,
                 bg=PANEL, fg=FG).pack(anchor="w", padx=14, pady=(12, 4))
        tk.Label(top, text="用一句话描述任务，AI 自动解析",
                 font=SANS, bg=PANEL, fg=FG2).pack(anchor="w", padx=14)

        input_row = tk.Frame(top, bg=PANEL)
        input_row.pack(fill="x", padx=14, pady=(8, 12))

        self.t_nlp = tk.Entry(input_row, font=("Segoe UI", 11), bg=BG, fg=FG,
                              insertbackground=FG, relief="flat")
        self.t_nlp.pack(side="left", fill="x", expand=True, ipady=6)
        self.t_nlp.insert(0, "每天早上8点写一本关于AI创业的书，5章，轻松风格")
        self.t_nlp.bind("<Return>", lambda e: self._parse_task())

        self.t_parse_btn = tk.Button(input_row, text="AI 解析 →", font=SANS_B,
                                     bg=ACCENT, fg="#fff",
                                     activebackground="#c0392b",
                                     relief="flat", cursor="hand2", padx=14, pady=6,
                                     command=self._parse_task)
        self.t_parse_btn.pack(side="left", padx=(8, 0))

        # Parsed result confirmation card
        self.t_confirm_frame = tk.Frame(page, bg=CARD)
        # (packed on demand)

        # Task list
        tk.Label(page, text="任务列表", font=("Segoe UI", 9),
                 bg=BG, fg=FG2).pack(anchor="w", padx=14, pady=(4, 2))

        list_frame = tk.Frame(page, bg=BG)
        list_frame.pack(fill="both", expand=True, padx=12, pady=(0, 4))

        cols = ("描述", "时间", "重复", "章节", "风格", "状态")
        self.task_tree = ttk.Treeview(list_frame, columns=cols,
                                      show="headings", height=10)
        widths = [220, 70, 80, 50, 90, 70]
        for col, w in zip(cols, widths):
            self.task_tree.heading(col, text=col)
            self.task_tree.column(col, width=w)
        self.task_tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(list_frame, orient="vertical",
                           command=self.task_tree.yview)
        sb.pack(side="right", fill="y")
        self.task_tree.configure(yscrollcommand=sb.set)

        tk.Button(page, text="🗑  删除选中", font=SANS, bg=CARD, fg=FG2,
                  activebackground=ACCENT, activeforeground="#fff",
                  relief="flat", cursor="hand2", padx=10, pady=4,
                  command=self._delete_task).pack(anchor="w", padx=12, pady=(0, 8))

        self._refresh_task_tree()

    def _parse_task(self):
        text = self.t_nlp.get().strip()
        if not text:
            return
        if not self.data["api_key"]:
            messagebox.showwarning("提示", "请先在「设置」中填写 API Key")
            return
        self.t_parse_btn.config(state="disabled", text="解析中...")

        def do_parse():
            parse_prompt = (
                "从用户描述中提取写书任务信息，只输出 JSON，不要解释，格式：\n"
                '{"title":"书名/主题","genre":"商业/管理|个人成长|科技/AI|小说/故事|知识科普|投资理财",'
                '"chapters":章节数整数,"style":"专业严谨|轻松易读|故事驱动|数据导向|励志激励",'
                '"time":"HH:MM","repeat":"每天|每周一|每周三|每周五|仅一次"}\n\n'
                f'用户描述：{text}'
            )
            try:
                raw = llm_call(
                    self.data["api_key"], self.data["base_url"], self.data["model"],
                    [{"role": "user", "content": parse_prompt}]
                )
                # 提取 JSON
                start = raw.find("{")
                end   = raw.rfind("}") + 1
                parsed = json.loads(raw[start:end])
                self.after(0, lambda p=parsed: self._show_task_confirm(p))
            except Exception as e:
                self.after(0, lambda e=e: messagebox.showerror("解析失败", str(e)))
            finally:
                self.after(0, lambda: self.t_parse_btn.config(state="normal", text="AI 解析 →"))

        threading.Thread(target=do_parse, daemon=True).start()

    def _show_task_confirm(self, parsed):
        # 清掉旧卡片
        for w in self.t_confirm_frame.winfo_children():
            w.destroy()
        self.t_confirm_frame.pack(fill="x", padx=12, pady=(0, 8))

        tk.Label(self.t_confirm_frame, text="解析结果 — 确认后添加任务",
                 font=SANS_B, bg=CARD, fg=ACCENT2).pack(anchor="w", padx=14, pady=(10, 4))

        info = [
            ("书名/主题", parsed.get("title", "—")),
            ("类型",     parsed.get("genre", "—")),
            ("执行时间", parsed.get("time", "—")),
            ("重复",     parsed.get("repeat", "—")),
            ("章节数",   str(parsed.get("chapters", 5))),
            ("写作风格", parsed.get("style", "—")),
        ]
        grid = tk.Frame(self.t_confirm_frame, bg=CARD)
        grid.pack(fill="x", padx=14, pady=4)
        for i, (k, v) in enumerate(info):
            tk.Label(grid, text=k + "：", font=SANS, bg=CARD, fg=FG2,
                     width=8, anchor="e").grid(row=i//3, column=(i%3)*2,
                                                sticky="e", padx=(10,2), pady=2)
            tk.Label(grid, text=v, font=SANS_B, bg=CARD, fg=FG,
                     anchor="w").grid(row=i//3, column=(i%3)*2+1, sticky="w", pady=2)

        btn_row = tk.Frame(self.t_confirm_frame, bg=CARD)
        btn_row.pack(anchor="e", padx=14, pady=(4, 10))
        tk.Button(btn_row, text="取消", font=SANS, bg=BG, fg=FG2,
                  relief="flat", cursor="hand2", padx=10,
                  command=lambda: self.t_confirm_frame.pack_forget()
                  ).pack(side="left", padx=4)
        tk.Button(btn_row, text="✓ 确认添加任务", font=SANS_B,
                  bg=ACCENT, fg="#fff", activebackground="#c0392b",
                  relief="flat", cursor="hand2", padx=14, pady=4,
                  command=lambda p=parsed: self._confirm_add_task(p)
                  ).pack(side="left")

    def _confirm_add_task(self, parsed):
        task = {
            "id":       int(time.time()),
            "title":    parsed.get("title", "未命名"),
            "genre":    parsed.get("genre", "个人成长"),
            "time":     parsed.get("time", "08:00"),
            "repeat":   parsed.get("repeat", "每天"),
            "chapters": parsed.get("chapters", 5),
            "style":    parsed.get("style", "轻松易读"),
            "status":   "待机",
            "enabled":  True,
        }
        self.data["tasks"].append(task)
        save_data(self.data)
        self.t_confirm_frame.pack_forget()
        self.t_nlp.delete(0, "end")
        self._refresh_task_tree()

    def _delete_task(self):
        sel = self.task_tree.selection()
        if not sel:
            return
        self.data["tasks"] = [t for t in self.data["tasks"]
                              if str(t["id"]) != sel[0]]
        save_data(self.data)
        self._refresh_task_tree()

    def _refresh_task_tree(self):
        self.task_tree.delete(*self.task_tree.get_children())
        for t in self.data["tasks"]:
            self.task_tree.insert("", "end", iid=str(t["id"]),
                values=(t.get("title",""), t.get("time",""), t.get("repeat",""),
                        t.get("chapters",""), t.get("style",""),
                        t.get("status","待机")))

    # ── Page: Skills & Soul ───────────────────────────────────────────

    # ── Page: Skills (card grid) ──────────────────────────────────────

    def _build_page_skills(self):
        page = tk.Frame(self.content, bg=BG)
        self._pages["skills"] = page

        # Header
        hdr = tk.Frame(page, bg=PANEL)
        hdr.pack(fill="x", padx=12, pady=(12, 0))
        tk.Label(hdr, text="⚡  写作技能", font=TITLE_F,
                 bg=PANEL, fg=FG).pack(side="left", padx=14, pady=(10, 4))
        tk.Label(hdr, text="勾选技能后写书时自动应用，可多选叠加",
                 font=SANS, bg=PANEL, fg=FG2).pack(side="left", pady=(10, 4))

        # Category filter bar
        cat_bar = tk.Frame(page, bg=PANEL)
        cat_bar.pack(fill="x", padx=12, pady=(0, 8))
        self._cat_filter = tk.StringVar(value="全部")
        for cat in ["全部"] + list(SKILL_CATS.keys()):
            color = SKILL_CATS.get(cat, FG2)
            btn = tk.Button(cat_bar, text=cat, font=("Segoe UI", 8, "bold"),
                            bg=PANEL, fg=color,
                            activebackground=color, activeforeground="#fff",
                            relief="flat", cursor="hand2", padx=10, pady=4,
                            command=lambda c=cat: self._filter_skills(c))
            btn.pack(side="left", padx=(14 if cat == "全部" else 2, 0), pady=(0, 8))

        # Scrollable card grid
        outer = tk.Frame(page, bg=BG)
        outer.pack(fill="both", expand=True, padx=12)

        canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self._skills_inner = tk.Frame(canvas, bg=BG)
        self._skills_win_id = canvas.create_window((0, 0), window=self._skills_inner, anchor="nw")
        self._skills_inner.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
            lambda e: canvas.itemconfig(self._skills_win_id, width=e.width))
        canvas.bind_all("<MouseWheel>",
            lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))

        self._skills_canvas = canvas
        self._skill_vars = {}
        self._render_skill_cards("全部")

    def _filter_skills(self, cat):
        self._cat_filter.set(cat)
        self._render_skill_cards(cat)

    def _render_skill_cards(self, cat_filter):
        for w in self._skills_inner.winfo_children():
            w.destroy()
        self._skill_vars = {}

        skills = self.data.get("skills", [])
        if cat_filter != "全部":
            skills = [s for s in skills if s.get("cat") == cat_filter]

        COLS = 3
        for idx, skill in enumerate(skills):
            row_i, col_i = divmod(idx, COLS)
            enabled = skill.get("enabled", False)
            cat_color = SKILL_CATS.get(skill.get("cat", ""), FG2)
            card_bg = "#1e2a1e" if enabled else CARD

            card = tk.Frame(self._skills_inner, bg=card_bg, padx=0, pady=0)
            card.grid(row=row_i, column=col_i, padx=6, pady=6, sticky="nsew")
            self._skills_inner.columnconfigure(col_i, weight=1)

            # Color top bar
            tk.Frame(card, bg=cat_color, height=3).pack(fill="x")

            body = tk.Frame(card, bg=card_bg, padx=12, pady=8)
            body.pack(fill="both", expand=True)

            # Top row: category tag + checkbox
            top_row = tk.Frame(body, bg=card_bg)
            top_row.pack(fill="x")
            tk.Label(top_row, text=skill.get("cat", ""),
                     font=("Segoe UI", 7, "bold"), bg=cat_color,
                     fg="#fff", padx=5, pady=1).pack(side="left")

            var = tk.BooleanVar(value=enabled)
            self._skill_vars[skill["id"]] = var
            cb = tk.Checkbutton(top_row, variable=var, bg=card_bg,
                                activebackground=card_bg, selectcolor=BG,
                                cursor="hand2",
                                command=lambda sid=skill["id"], v=var, c=card:
                                    self._toggle_skill(sid, v, c))
            cb.pack(side="right")

            # Skill name
            tk.Label(body, text=skill["name"], font=("Segoe UI", 11, "bold"),
                     bg=card_bg,
                     fg=cat_color if enabled else FG).pack(anchor="w", pady=(4, 2))

            # Description (user-friendly, no prompt shown)
            desc = skill.get("desc", "")
            tk.Label(body, text=desc, font=("Segoe UI", 8),
                     bg=card_bg, fg=FG2, wraplength=180,
                     justify="left").pack(anchor="w")

            # Click card to toggle
            for w in [card, body]:
                w.bind("<Button-1>", lambda e, sid=skill["id"], v=var, c=card:
                       (v.set(not v.get()), self._toggle_skill(sid, v, c)))

    def _toggle_skill(self, sid, var, card=None):
        enabled = var.get()
        for s in self.data["skills"]:
            if s["id"] == sid:
                s["enabled"] = enabled
        save_data(self.data)
        # Update card color live
        if card:
            new_bg = "#1e2a1e" if enabled else CARD
            _repaint_card(card, new_bg)
        # Refresh active count badge if exists
        self._update_active_count()

    def _update_active_count(self):
        active = sum(1 for s in self.data.get("skills", []) if s.get("enabled"))
        if hasattr(self, "_active_lbl"):
            self._active_lbl.config(text=f"已启用 {active} 项技能")

    # ── Page: Soul ────────────────────────────────────────────────────

    def _build_page_soul(self):
        page = tk.Frame(self.content, bg=BG)
        self._pages["soul"] = page

        # Left: soul editor
        left = tk.Frame(page, bg=BG)
        left.pack(side="left", fill="both", expand=True, padx=(16, 8), pady=16)

        tk.Label(left, text="✨  AI 写作灵魂", font=("Segoe UI", 14, "bold"),
                 bg=BG, fg=ACCENT2).pack(anchor="w")
        tk.Label(left, text="这是 AI 的底层人格设定，影响每一本书的气质与风格",
                 font=SANS, bg=BG, fg=FG2).pack(anchor="w", pady=(2, 12))

        self.soul_text = tk.Text(left, font=("Segoe UI", 10), bg=PANEL, fg=FG,
                                 insertbackground=FG, relief="flat",
                                 wrap="word", padx=14, pady=12)
        self.soul_text.pack(fill="both", expand=True)
        self.soul_text.insert("1.0", self.data.get("soul", DEFAULT_SOUL))

        btn_row = tk.Frame(left, bg=BG)
        btn_row.pack(fill="x", pady=(10, 0))
        tk.Button(btn_row, text="恢复默认", font=SANS, bg=CARD, fg=FG2,
                  relief="flat", cursor="hand2", padx=12, pady=6,
                  command=self._reset_soul).pack(side="left")
        tk.Button(btn_row, text="保存灵魂设定", font=SANS_B,
                  bg=ACCENT2, fg="#1a1a2e", activebackground="#d4813e",
                  relief="flat", cursor="hand2", padx=16, pady=6,
                  command=self._save_soul).pack(side="right")

        # Right: tips panel
        right = tk.Frame(page, bg=PANEL, width=260)
        right.pack(side="right", fill="y", padx=(0, 16), pady=16)
        right.pack_propagate(False)

        tk.Label(right, text="写作什么？", font=SANS_B,
                 bg=PANEL, fg=FG).pack(anchor="w", padx=16, pady=(16, 6))

        presets = [
            ("商业导师", "你是一位有20年实战经验的商业导师，善用真实案例，语言犀利直接，帮助读者解决实际问题。"),
            ("学术严谨", "你是一位学术研究者，文风严谨，论据充分，注重逻辑推理，引用权威资料，语言精准克制。"),
            ("故事高手", "你是一位擅长讲故事的作家，善于用叙事构建情感共鸣，文字生动，节奏感强，让读者欲罢不能。"),
            ("轻松博主", "你是一位受欢迎的知识博主，语言轻松幽默，善于把复杂知识讲得简单有趣，读者定位是普通大众。"),
            ("励志教练", "你是一位激励型作家，文字充满力量，善于触达读者内心深处，激发行动力和改变欲望。"),
        ]
        for name, soul in presets:
            def apply(s=soul):
                self.soul_text.delete("1.0", "end")
                self.soul_text.insert("1.0", s)
            tk.Button(right, text=name, font=SANS, bg=CARD, fg=FG,
                      activebackground=ACCENT2, activeforeground="#1a1a2e",
                      relief="flat", cursor="hand2", anchor="w", padx=12, pady=5,
                      command=apply).pack(fill="x", padx=12, pady=2)

        tk.Frame(right, bg=BORDER, height=1).pack(fill="x", padx=12, pady=10)
        tk.Label(right, text="提示：修改灵魂后点击「保存」\n再去写书，效果立刻生效。",
                 font=("Segoe UI", 8), bg=PANEL, fg=FG2,
                 justify="left").pack(anchor="w", padx=16)

        # Active skills count badge (referenced in _update_active_count)
        self._active_lbl = tk.Label(right, font=("Segoe UI", 8), bg=PANEL, fg=GREEN)
        self._active_lbl.pack(anchor="w", padx=16, pady=(6, 0))
        self._update_active_count()

    def _save_soul(self):
        self.data["soul"] = self.soul_text.get("1.0", "end").strip()
        save_data(self.data)
        messagebox.showinfo("已保存", "灵魂设定已保存，下次写书立刻生效。")

    def _reset_soul(self):
        self.soul_text.delete("1.0", "end")
        self.soul_text.insert("1.0", DEFAULT_SOUL)

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
        def _do():
            self._refresh_task_tree()
            self._show_page("write")
            self.w_title.delete(0, "end")
            self.w_title.insert(0, task.get("title", ""))
            # 同步章节数和风格
            try:
                self.w_chapters.set(task.get("chapters", 5))
            except Exception:
                pass
            styles = ["专业严谨", "轻松易读", "故事驱动", "数据导向", "励志激励"]
            s = task.get("style", "轻松易读")
            if s in styles:
                self.w_style.current(styles.index(s))
            self._start_writing()
            task["status"] = "完成"
            if task["repeat"] == "仅一次":
                task["enabled"] = False
            save_data(self.data)
            self._refresh_task_tree()
        self.after(0, _do)

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
        win.geometry("640x560")
        win.configure(bg=BG)
        win.resizable(False, False)

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
            txt.insert("end", "─" * 40 + "\n【完整正文】\n\n"
                       "这里是书籍的完整正文内容……\n\n"
                       "（书籍已解锁，连接后端后可获取真实内容）")
            txt.configure(state="disabled")
        else:
            txt.insert("end", "\n\n" + "▓" * 28 + "\n\n  内容已加密锁定\n  输入激活码后解锁全文")
            txt.configure(state="disabled")
            self._build_unlock_panel(win, book)

    def _build_unlock_panel(self, win, book):
        panel = tk.Frame(win, bg=PANEL)
        panel.pack(fill="x", padx=20, pady=(8, 16))

        # 微信获取激活码提示
        tip = tk.Frame(panel, bg="#1e2d1e")
        tip.pack(fill="x", pady=(10, 8))
        tk.Label(tip, text="获取激活码方式", font=SANS_B,
                 bg="#1e2d1e", fg=GREEN).pack(anchor="w", padx=10, pady=(8, 2))
        tk.Label(tip,
                 text=f"添加微信  {WECHAT_CONTACT}  →  备注「龙虾写书」→ 获取激活码",
                 font=("Segoe UI", 10), bg="#1e2d1e", fg=FG).pack(anchor="w", padx=10)
        tk.Label(tip, text=f"书籍定价  ¥{book['price']}",
                 font=SANS, bg="#1e2d1e", fg=ACCENT2).pack(anchor="w", padx=10, pady=(0, 8))

        # 激活码输入
        row = tk.Frame(panel, bg=PANEL)
        row.pack(fill="x", pady=(4, 10))
        tk.Label(row, text="激活码：", font=SANS, bg=PANEL, fg=FG2).pack(side="left", padx=(10, 4))
        code_var = tk.StringVar()
        code_entry = tk.Entry(row, textvariable=code_var, font=("Consolas", 11),
                              bg=BG, fg=FG, insertbackground=FG, relief="flat",
                              width=22)
        code_entry.pack(side="left", ipady=4)
        code_entry.focus_set()

        msg_lbl = tk.Label(panel, text="", font=("Segoe UI", 9), bg=PANEL)
        msg_lbl.pack(anchor="w", padx=10)

        def do_activate():
            code = code_var.get().strip()
            if not code:
                msg_lbl.config(text="请输入激活码", fg=ACCENT)
                return
            btn.config(state="disabled", text="验证中...")
            msg_lbl.config(text="正在连接服务器...", fg=FG2)

            def verify():
                ok, msg = db_verify_code(code, book["id"])
                def update():
                    btn.config(state="normal", text="立即激活")
                    if ok:
                        if "purchased" not in self.data:
                            self.data["purchased"] = []
                        self.data["purchased"].append(book["id"])
                        save_data(self.data)
                        win.destroy()
                        messagebox.showinfo("解锁成功",
                            f"《{book['title']}》已解锁！\n重新点击书籍即可阅读完整内容。")
                    else:
                        msg_lbl.config(text=f"✗  {msg}", fg=ACCENT)
                self.after(0, update)
            threading.Thread(target=verify, daemon=True).start()

        btn = tk.Button(row, text="立即激活", font=SANS_B,
                        bg=ACCENT, fg="#fff", activebackground="#c0392b",
                        relief="flat", cursor="hand2", padx=14, pady=4,
                        command=do_activate)
        btn.pack(side="left", padx=8)
        win.bind("<Return>", lambda e: do_activate())

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
