"""Windows native dashboard for FGO-JP-AutoRoute v0.6.0."""
from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from .catalog import LONDON_ROUTE_ID, PART_ONE_CHAPTERS, executable_chapter_ids, get_chapter
from .config import AppConfig, load_config, save_config
from .planner import estimate_affordable_runs, make_custom_route
from .storage import StatsStore

# Restored by the Windows build workflow from the retained v0.5 source bundle.
from legacy_main import TemplateWizard, find_adb, required_template_names
from fgoauto.engine import Automation
from fgoauto.profiles import LONDON_GUIDE, LONDON_RULES, london_job
from fgoauto.storage import TEMPLATES, read, safe_template_name, write

APP_NAME = "FGO-JP-AutoRoute"
PREVIEW_INTERVAL_MS = 220


def configure_london_profile(progress_target: int, max_runs: int, skip_story: bool) -> None:
    job = london_job()
    stage = job["stages"][0]
    stage["progress_target"] = max(1, min(5, int(progress_target)))
    stage["max_runs"] = max(1, min(30, int(max_runs)))
    if not skip_story:
        stage["required_rule_templates"] = [
            name for name in stage["required_rule_templates"]
            if name not in ("story_skip", "skip_confirm_yes")
        ]
    jobs = read("jobs")
    existing = next((index for index, item in enumerate(jobs) if item.get("id") == LONDON_ROUTE_ID), None)
    if existing is None:
        jobs.append(job)
    else:
        jobs[existing] = job
    write("jobs", jobs)

    rules = read("rules")
    for rule in LONDON_RULES:
        updated = dict(rule)
        if updated["template"] in ("story_skip", "skip_confirm_yes", "dialogue_next"):
            updated["enabled"] = bool(skip_story)
        index = next((i for i, item in enumerate(rules) if item.get("template") == updated["template"]), None)
        if index is None:
            rules.append(updated)
        else:
            rules[index] = updated
    write("rules", rules)


class AutoRouteDesktopApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"{APP_NAME} v0.6.0 — Windows 原生控制中心")
        self.root.geometry("1180x780")
        self.root.minsize(1020, 690)
        self.root.configure(bg="#0b1220")

        self.config: AppConfig = load_config()
        if get_chapter(self.config.selected_chapter) is None:
            self.config.selected_chapter = "london"
        self.stats = StatsStore()
        self.bot = None
        self.adb_path = find_adb()
        self.device_var = tk.StringVar(value=self.config.adb_serial)
        self.status_var = tk.StringVar(value="尚未連線")
        self.chapter_var = tk.StringVar(value=self.config.selected_chapter)
        self.max_runs_var = tk.StringVar(value=str(self.config.max_runs))
        self.progress_target_var = tk.StringVar(value=str(self.config.progress_target))
        self.skip_story_var = tk.BooleanVar(value=self.config.skip_story)
        self.ap_current_var = tk.StringVar(value="" if self.config.ap_current is None else str(self.config.ap_current))
        self.ap_cost_var = tk.StringVar(value="" if self.config.ap_cost is None else str(self.config.ap_cost))
        self.ap_estimate_var = tk.StringVar(value="輸入目前 AP 與關卡消耗以估算")
        self.servant_var = tk.StringVar(value=self.config.preferred_servant)
        self.ce_var = tk.StringVar(value=self.config.preferred_ce)
        self.farm_item_var = tk.StringVar(value=self.config.farm_item_name)
        self.farm_target_var = tk.StringVar(value=str(self.config.farm_target_quantity))
        self.drop_quantity_var = tk.StringVar(value="1")
        self.route_name_var = tk.StringVar(value="")
        self.route_stages_var = tk.StringVar(value="")
        self.route_status_var = tk.StringVar(value="")
        self.frame_lock = threading.RLock()
        self.last_frame = None
        self.preview_photo = None
        self.capture_thread = None
        self.capture_stop = threading.Event()
        self.scrcpy_process = None
        self.wizard = None
        self.closing = False
        self.session_started_at = None
        self.session_runs_observed = 0
        self.last_log_signature = None
        self.log_lines: list[str] = []

        self._configure_style()
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<F8>", lambda _event: self.stop_automation())
        self.root.after(500, self._refresh_status)
        self.refresh_template_status()
        self.refresh_stats()

    def _configure_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background="#0b1220")
        style.configure("Panel.TFrame", background="#142033")
        style.configure("TLabel", background="#0b1220", foreground="#e6edf7", font=("Segoe UI", 10))
        style.configure("Panel.TLabel", background="#142033", foreground="#e6edf7", font=("Segoe UI", 10))
        style.configure("Title.TLabel", background="#0b1220", foreground="#f4c77b", font=("Segoe UI", 21, "bold"))
        style.configure("Sub.TLabel", background="#0b1220", foreground="#91a4bf", font=("Segoe UI", 9))
        style.configure("Accent.TButton", background="#d7a85e", foreground="#111827",
                        font=("Segoe UI", 10, "bold"), padding=(12, 8))
        style.map("Accent.TButton", background=[("active", "#edc47d")])
        style.configure("Danger.TButton", background="#6d3440", foreground="#fff0f0",
                        font=("Segoe UI", 10, "bold"), padding=(12, 8))
        style.map("Danger.TButton", background=[("active", "#8a4654")])
        style.configure("TButton", padding=(9, 6))
        style.configure("TEntry", fieldbackground="#0e192a", foreground="#e6edf7", insertcolor="#e6edf7", padding=6)
        style.configure("Treeview", rowheight=25, background="#0e192a", fieldbackground="#0e192a",
                        foreground="#e6edf7")
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    def _build_ui(self):
        outer = ttk.Frame(self.root, padding=14)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 10))
        ttk.Label(header, text="FGO AUTO", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="日本版 FATE / GRAND ORDER  ·  Windows 11  ·  MuMu Player 12",
                  style="Sub.TLabel").pack(anchor="w")

        connection = ttk.Frame(outer, style="Panel.TFrame", padding=9)
        connection.pack(fill="x", pady=(0, 10))
        ttk.Label(connection, text="ADB 位址", style="Panel.TLabel").pack(side="left")
        ttk.Entry(connection, textvariable=self.device_var, width=20).pack(side="left", padx=(8, 8))
        ttk.Button(connection, text="連接 MuMu", style="Accent.TButton", command=self.connect_device).pack(side="left")
        ttk.Button(connection, text="選擇 adb.exe", command=self.choose_adb).pack(side="left", padx=6)
        ttk.Button(connection, text="即時鏡像", command=self.start_scrcpy).pack(side="left")
        ttk.Label(connection, textvariable=self.status_var, style="Panel.TLabel").pack(side="right")

        self.tabs = ttk.Notebook(outer)
        self.tabs.pack(fill="both", expand=True)
        self.dashboard_tab = ttk.Frame(self.tabs, padding=10)
        self.route_tab = ttk.Frame(self.tabs, padding=12)
        self.battle_tab = ttk.Frame(self.tabs, padding=12)
        self.support_tab = ttk.Frame(self.tabs, padding=12)
        self.farm_tab = ttk.Frame(self.tabs, padding=12)
        self.stats_tab = ttk.Frame(self.tabs, padding=12)
        self.system_tab = ttk.Frame(self.tabs, padding=12)
        for tab, title in (
            (self.dashboard_tab, "總覽"),
            (self.route_tab, "章節與路線"),
            (self.battle_tab, "戰鬥策略"),
            (self.support_tab, "支援偏好"),
            (self.farm_tab, "素材與 AP"),
            (self.stats_tab, "戰鬥統計"),
            (self.system_tab, "系統設定"),
        ):
            self.tabs.add(tab, text=title)

        self._build_dashboard()
        self._build_routes()
        self._build_battle()
        self._build_support()
        self._build_farm()
        self._build_stats()
        self._build_system()

    def _build_dashboard(self):
        body = ttk.Frame(self.dashboard_tab)
        body.pack(fill="both", expand=True)
        left = ttk.Frame(body, style="Panel.TFrame", padding=10)
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        ttk.Label(left, text="MuMu 即時畫面預覽", style="Panel.TLabel",
                  font=("Segoe UI", 11, "bold")).pack(anchor="w")
        self.preview = tk.Canvas(left, bg="#050a12", highlightthickness=0, width=700, height=394)
        self.preview.pack(fill="both", expand=True, pady=(8, 6))
        self.preview.bind("<Configure>", self._draw_preview)
        ttk.Label(left, text="高流暢度鏡像請使用上方「即時鏡像」；程式內預覽為 ADB 擷取。",
                  style="Panel.TLabel").pack(anchor="w")

        right = ttk.Frame(body, style="Panel.TFrame", padding=12, width=310)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)
        ttk.Label(right, text="任務控制", style="Panel.TLabel",
                  font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(0, 10))
        ttk.Label(right, text="第一部章節", style="Panel.TLabel").pack(anchor="w")
        ttk.Label(right, textvariable=self.route_status_var, style="Panel.TLabel",
                  wraplength=280).pack(anchor="w", pady=(4, 12))
        ttk.Button(right, text="設定畫面模板", command=self.open_template_wizard).pack(fill="x", pady=4)
        ttk.Button(right, text="檢查目前設定", command=self.check_setup).pack(fill="x", pady=4)
        ttk.Button(right, text="開始自動推關", style="Accent.TButton",
                   command=self.start_automation).pack(fill="x", pady=(12, 5))
        row = ttk.Frame(right, style="Panel.TFrame")
        row.pack(fill="x")
        ttk.Button(row, text="暫停", command=self.pause_automation).pack(side="left", expand=True, fill="x", padx=(0, 3))
        ttk.Button(row, text="繼續", command=self.resume_automation).pack(side="left", expand=True, fill="x", padx=3)
        ttk.Button(row, text="停止", style="Danger.TButton",
                   command=self.stop_automation).pack(side="left", expand=True, fill="x", padx=(3, 0))
        self.template_count_var = tk.StringVar(value="模板 0 / 0")
        ttk.Label(right, textvariable=self.template_count_var, style="Panel.TLabel").pack(anchor="w", pady=(14, 2))
        ttk.Label(right, text="緊急停止：F8。AP 恢復與未知畫面需人工處理。",
                  style="Panel.TLabel", wraplength=280).pack(anchor="w", pady=(8, 0))

        log_panel = ttk.Frame(self.dashboard_tab, style="Panel.TFrame", padding=8)
        log_panel.pack(fill="x", pady=(10, 0))
        ttk.Label(log_panel, text="執行紀錄", style="Panel.TLabel",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.log_box = tk.Text(log_panel, height=5, bg="#0b1627", fg="#b9c9df",
                               insertbackground="#ffffff", relief="flat",
                               font=("Consolas", 9), wrap="word", state="disabled")
        self.log_box.pack(fill="x", pady=(6, 0))
        self.log("v0.6.0 開發版已啟動。只有已驗證路線會開放自動執行。")

    def _build_routes(self):
        ttk.Label(self.route_tab, text="第一部章節目錄", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        ttk.Label(self.route_tab,
                  text="所有第一部章節均列入路線架構；只有已完成畫面與流程驗證的路線才可執行。",
                  wraplength=850).pack(anchor="w", pady=(4, 12))
        row = ttk.Frame(self.route_tab)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="章節", width=12).pack(side="left")
        values = [f"{chapter.name}  ·  {chapter.japanese_name}" for chapter in PART_ONE_CHAPTERS]
        self.chapter_combo = ttk.Combobox(row, state="readonly", values=values, width=66)
        self.chapter_combo.pack(side="left", padx=6)
        self.chapter_combo.current(next((i for i, item in enumerate(PART_ONE_CHAPTERS)
                                          if item.chapter_id == self.chapter_var.get()), 4))
        self.chapter_combo.bind("<<ComboboxSelected>>", self._chapter_changed)
        self.chapter_detail_var = tk.StringVar()
        ttk.Label(self.route_tab, textvariable=self.chapter_detail_var,
                  wraplength=900).pack(anchor="w", pady=10)
        settings = ttk.LabelFrame(self.route_tab, text="路線執行上限", padding=10)
        settings.pack(fill="x", pady=8)
        ttk.Label(settings, text="最多戰鬥次數").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        ttk.Spinbox(settings, from_=1, to=30, textvariable=self.max_runs_var, width=8).grid(row=0, column=1, sticky="w")
        ttk.Label(settings, text="倫敦任務進度目標（1～5）").grid(row=0, column=2, sticky="w", padx=(20, 5))
        ttk.Spinbox(settings, from_=1, to=5, textvariable=self.progress_target_var, width=8).grid(row=0, column=3, sticky="w")
        ttk.Checkbutton(settings, text="自動略過劇情（需完成模板設定）",
                        variable=self.skip_story_var).grid(row=1, column=0, columnspan=3, sticky="w", padx=5, pady=8)

        custom = ttk.LabelFrame(self.route_tab, text="自訂路線（先儲存規劃，不會直接執行）", padding=10)
        custom.pack(fill="x", pady=10)
        ttk.Label(custom, text="路線名稱").grid(row=0, column=0, sticky="w", padx=4)
        ttk.Entry(custom, textvariable=self.route_name_var, width=28).grid(row=0, column=1, sticky="w", padx=4)
        ttk.Label(custom, text="關卡名稱（以逗號分隔）").grid(row=1, column=0, sticky="w", padx=4, pady=6)
        ttk.Entry(custom, textvariable=self.route_stages_var, width=68).grid(row=1, column=1, sticky="w", padx=4)
        ttk.Button(custom, text="儲存自訂路線", command=self.save_custom_route).grid(row=1, column=2, padx=8)
        self.custom_routes_box = tk.Listbox(custom, height=4)
        self.custom_routes_box.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        self._refresh_custom_routes()
        self._update_chapter_detail()

    def _build_battle(self):
        ttk.Label(self.battle_tab, text="戰鬥策略", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        ttk.Label(self.battle_tab, text="目前採用穩定優先。技能、寶具與卡牌價值判斷必須先建立可驗證的畫面辨識資料。",
                  wraplength=900).pack(anchor="w", pady=(5, 12))
        card = ttk.LabelFrame(self.battle_tab, text="目前可執行策略", padding=12)
        card.pack(fill="x", pady=6)
        ttk.Label(card, text="穩定優先：沿用已存在的倫敦路線戰鬥流程；不自動使用技能或寶具。",
                  wraplength=900).pack(anchor="w")
        future = ttk.LabelFrame(self.battle_tab, text="後續策略模組", padding=12)
        future.pack(fill="x", pady=8)
        for line in (
            "敵方職階與目標辨識：待建立並驗證模板。",
            "技能冷卻與效果判斷：待建立並驗證模板。",
            "寶具時機與指令卡策略：待建立並驗證策略。",
            "遇到未知戰鬥畫面：暫停並交由使用者確認。",
        ):
            ttk.Label(future, text="• " + line).pack(anchor="w", pady=3)

    def _build_support(self):
        ttk.Label(self.support_tab, text="支援從者偏好", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        ttk.Label(self.support_tab,
                  text="先保存你偏好的支援從者與禮裝名稱。自動篩選尚未接入 OCR，未驗證前不會代替你點選。",
                  wraplength=900).pack(anchor="w", pady=(5, 14))
        form = ttk.LabelFrame(self.support_tab, text="偏好條件", padding=12)
        form.pack(fill="x")
        ttk.Label(form, text="偏好從者名稱").grid(row=0, column=0, sticky="w", padx=5, pady=7)
        ttk.Entry(form, textvariable=self.servant_var, width=42).grid(row=0, column=1, sticky="w")
        ttk.Label(form, text="偏好概念禮裝").grid(row=1, column=0, sticky="w", padx=5, pady=7)
        ttk.Entry(form, textvariable=self.ce_var, width=42).grid(row=1, column=1, sticky="w")
        ttk.Button(form, text="儲存偏好", command=self.save_support_preferences).grid(row=2, column=1, sticky="w", pady=10)

    def _build_farm(self):
        ttk.Label(self.farm_tab, text="素材與 AP 管理", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        ttk.Label(self.farm_tab,
                  text="本版 AP 估算使用手動輸入；素材掉落由你確認後登記。自動 OCR 尚未啟用。",
                  wraplength=900).pack(anchor="w", pady=(5, 12))
        ap = ttk.LabelFrame(self.farm_tab, text="AP 預算", padding=12)
        ap.pack(fill="x", pady=5)
        ttk.Label(ap, text="目前 AP").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(ap, textvariable=self.ap_current_var, width=10).grid(row=0, column=1, sticky="w")
        ttk.Label(ap, text="每場 AP 消耗").grid(row=0, column=2, sticky="w", padx=(18, 5))
        ttk.Entry(ap, textvariable=self.ap_cost_var, width=10).grid(row=0, column=3, sticky="w")
        ttk.Button(ap, text="計算可刷次數", command=self.update_ap_estimate).grid(row=0, column=4, padx=10)
        ttk.Label(ap, textvariable=self.ap_estimate_var).grid(row=1, column=0, columnspan=5, sticky="w", padx=5, pady=8)

        farm = ttk.LabelFrame(self.farm_tab, text="素材目標與掉落登記", padding=12)
        farm.pack(fill="x", pady=10)
        ttk.Label(farm, text="目標素材").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(farm, textvariable=self.farm_item_var, width=26).grid(row=0, column=1, sticky="w")
        ttk.Label(farm, text="目標數量").grid(row=0, column=2, sticky="w", padx=(18, 5))
        ttk.Entry(farm, textvariable=self.farm_target_var, width=8).grid(row=0, column=3, sticky="w")
        ttk.Label(farm, text="本次確認掉落").grid(row=1, column=0, sticky="w", padx=5, pady=8)
        ttk.Entry(farm, textvariable=self.drop_quantity_var, width=8).grid(row=1, column=1, sticky="w")
        ttk.Button(farm, text="登記素材", command=self.record_drop).grid(row=1, column=2, padx=8, sticky="w")
        ttk.Button(farm, text="儲存素材目標", command=self.save_farm_goal).grid(row=1, column=3, padx=8, sticky="w")

    def _build_stats(self):
        header = ttk.Frame(self.stats_tab)
        header.pack(fill="x")
        ttk.Label(header, text="戰鬥與素材統計", font=("Segoe UI", 14, "bold")).pack(side="left")
        ttk.Button(header, text="重新整理", command=self.refresh_stats).pack(side="right", padx=4)
        ttk.Button(header, text="匯出戰鬥 CSV", command=self.export_stats).pack(side="right", padx=4)
        self.stats_summary_var = tk.StringVar(value="")
        ttk.Label(self.stats_tab, textvariable=self.stats_summary_var).pack(anchor="w", pady=10)
        columns = ("route", "start", "runs", "status", "duration")
        self.stats_tree = ttk.Treeview(self.stats_tab, columns=columns, show="headings", height=14)
        for key, title, width in (
            ("route", "路線", 240), ("start", "開始時間", 180),
            ("runs", "觀察到的戰鬥次數", 140), ("status", "狀態", 100),
            ("duration", "耗時（秒）", 100),
        ):
            self.stats_tree.heading(key, text=title)
            self.stats_tree.column(key, width=width, anchor="center")
        self.stats_tree.pack(fill="both", expand=True)

    def _build_system(self):
        ttk.Label(self.system_tab, text="系統設定", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        ttk.Label(self.system_tab, text="固定基準解析度：1280 × 720；ADB 與使用者設定只保存在本機。",
                  wraplength=900).pack(anchor="w", pady=(6, 14))
        ttk.Label(self.system_tab, text=f"目前找到的 ADB：{self.adb_path or '尚未找到，請選擇 adb.exe'}").pack(anchor="w")
        ttk.Button(self.system_tab, text="選擇 adb.exe", command=self.choose_adb).pack(anchor="w", pady=10)
        ttk.Label(self.system_tab, text="使用者設定資料夾：" + str(Path(os.environ.get("LOCALAPPDATA", Path.home())) / "FGO-JP-AutoRoute"),
                  wraplength=900).pack(anchor="w", pady=5)
        ttk.Label(self.system_tab, text="程式不會自動使用聖晶石或任何蘋果恢復 AP。遇到未知畫面應停止並人工確認。",
                  wraplength=900).pack(anchor="w", pady=5)

    def _selected_chapter(self):
        index = self.chapter_combo.current()
        if index < 0:
            return get_chapter(self.chapter_var.get())
        return PART_ONE_CHAPTERS[index]

    def _chapter_changed(self, _event=None):
        chapter = self._selected_chapter()
        if chapter:
            self.chapter_var.set(chapter.chapter_id)
            self.config.selected_chapter = chapter.chapter_id
            save_config(self.config)
        self._update_chapter_detail()

    def _update_chapter_detail(self):
        chapter = get_chapter(self.chapter_var.get())
        if chapter is None:
            self.chapter_detail_var.set("請選擇章節。")
            self.route_status_var.set("尚未選擇章節")
            return
        if chapter.chapter_id == "london":
            detail = "部分支援：第四特異點第六節範例路線可使用既有引擎；其他倫敦關卡尚未驗證。"
        else:
            detail = "已納入第一部章節目錄；自動路線資料尚未建立，請勿啟動自動操作。"
        self.chapter_detail_var.set(f"{chapter.name}｜{chapter.japanese_name}\n{detail}")
        self.route_status_var.set(detail)

    def _refresh_custom_routes(self):
        self.custom_routes_box.delete(0, "end")
        for route in self.config.custom_routes:
            self.custom_routes_box.insert("end", f"{route.get('name', '未命名')}（規劃中，不可自動執行）")

    def save_custom_route(self):
        chapter = self._selected_chapter()
        if chapter is None:
            messagebox.showwarning("尚未選擇章節", "請先選擇章節。")
            return
        try:
            route = make_custom_route(
                self.route_name_var.get(),
                chapter.chapter_id,
                self.route_stages_var.get().split(","),
            )
        except ValueError as exc:
            messagebox.showwarning("路線資料不完整", str(exc))
            return
        self.config.custom_routes.append(route)
        save_config(self.config)
        self.route_name_var.set("")
        self.route_stages_var.set("")
        self._refresh_custom_routes()
        self.log(f"已儲存自訂路線規劃：{route['name']}")

    def save_support_preferences(self):
        self.config.preferred_servant = self.servant_var.get().strip()
        self.config.preferred_ce = self.ce_var.get().strip()
        save_config(self.config)
        messagebox.showinfo("已儲存", "支援從者與禮裝偏好已保存在本機；自動篩選尚未啟用。")

    def save_farm_goal(self):
        self.config.farm_item_name = self.farm_item_var.get().strip()
        try:
            self.config.farm_target_quantity = max(0, int(self.farm_target_var.get() or "0"))
        except ValueError:
            messagebox.showwarning("數量格式錯誤", "目標數量請輸入整數。")
            return
        save_config(self.config)
        messagebox.showinfo("已儲存", "素材目標已保存；本版掉落數量需人工確認後登記。")

    def update_ap_estimate(self):
        try:
            current = int(self.ap_current_var.get())
            cost = int(self.ap_cost_var.get())
            max_runs = max(1, min(30, int(self.max_runs_var.get())))
            runs = estimate_affordable_runs(current, cost, max_runs)
        except ValueError as exc:
            messagebox.showwarning("AP 資料格式錯誤", str(exc) or "請輸入有效整數。")
            return
        self.config.ap_current = current
        self.config.ap_cost = cost
        save_config(self.config)
        self.ap_estimate_var.set(f"目前 AP 可負擔 {runs} 場（已套用最多 {max_runs} 場上限）")

    def record_drop(self):
        item = self.farm_item_var.get().strip()
        try:
            quantity = int(self.drop_quantity_var.get())
        except ValueError:
            messagebox.showwarning("數量格式錯誤", "掉落數量請輸入整數。")
            return
        if not item or quantity <= 0:
            messagebox.showwarning("資料不完整", "請輸入素材名稱與大於 0 的掉落數量。")
            return
        self.stats.record_drop(self.config.route_id, item, quantity)
        self.log(f"素材登記：{item} × {quantity}")
        self.refresh_stats()

    def refresh_stats(self):
        if not hasattr(self, "stats_tree"):
            return
        summary = self.stats.summary()
        self.stats_summary_var.set(
            f"工作階段：{summary['sessions']}　觀察到的戰鬥次數：{summary['runs']}　"
            f"素材紀錄：{summary['drop_records']} 筆／共 {summary['drop_quantity']} 個"
        )
        for item in self.stats_tree.get_children():
            self.stats_tree.delete(item)
        for row in self.stats.recent_sessions():
            self.stats_tree.insert(
                "", "end",
                values=(row["route_id"], row["started_at"], row["runs_observed"],
                        row["status"], row["duration_seconds"]),
            )

    def export_stats(self):
        target = filedialog.asksaveasfilename(
            title="匯出戰鬥統計",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile="FGO-JP-AutoRoute-sessions.csv",
        )
        if not target:
            return
        self.stats.export_csv(Path(target))
        messagebox.showinfo("匯出完成", f"已匯出：{target}")

    def connect_device(self):
        try:
            self.config.adb_serial = self.device_var.get().strip() or "auto"
            if self.adb_path:
                settings = read("settings")
                settings["adb_path"] = str(self.adb_path)
                settings["serial"] = self.config.adb_serial
                write("settings", settings)
            save_config(self.config)
            self.bot = Automation()
            serial = self.bot.device.connect(self.config.adb_serial)
            self.status_var.set(f"ADB 已連線：{serial}")
            self.log(f"ADB 連線成功：{serial}")
            self._start_capture_loop()
            self.start_scrcpy(show_error=False)
        except Exception as exc:
            self.status_var.set("連線失敗")
            messagebox.showerror("ADB 連線失敗", str(exc))

    def choose_adb(self):
        selected = filedialog.askopenfilename(
            title="選擇 MuMu 的 adb.exe",
            filetypes=[("ADB executable", "adb.exe"), ("Executable", "*.exe")],
        )
        if selected:
            self.adb_path = Path(selected)
            settings = read("settings")
            settings["adb_path"] = selected
            write("settings", settings)
            self.log(f"ADB 路徑已設定：{selected}")

    def _find_scrcpy(self):
        roots = []
        if getattr(__import__("sys"), "frozen", False):
            roots.append(Path(getattr(__import__("sys"), "_MEIPASS", "")) / "scrcpy")
        roots.append(Path(__file__).resolve().parent.parent / "vendor" / "scrcpy")
        found = shutil.which("scrcpy")
        for root in roots:
            candidate = root / "scrcpy.exe"
            if candidate.is_file():
                return candidate
        return Path(found) if found else None

    def start_scrcpy(self, show_error=True):
        if not self.bot or not self.bot.device.serial:
            if show_error:
                messagebox.showwarning("尚未連線", "請先連接 MuMu ADB。")
            return
        if self.scrcpy_process and self.scrcpy_process.poll() is None:
            return
        executable = self._find_scrcpy()
        if not executable:
            if show_error:
                messagebox.showwarning("找不到 scrcpy", "請重新下載包含 scrcpy 的 Windows EXE 套件。")
            return
        env = os.environ.copy()
        if getattr(self.bot.device, "exe", None):
            env["ADB"] = self.bot.device.exe
        command = [
            str(executable), "--serial", self.bot.device.serial,
            "--window-title", "FGO-JP-AutoRoute｜MuMu 即時鏡像",
            "--max-size", "1280", "--max-fps", "60",
            "--video-bit-rate", "8M", "--no-audio",
        ]
        try:
            self.scrcpy_process = subprocess.Popen(
                command, cwd=str(executable.parent), env=env,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            self.log("scrcpy 即時鏡像已啟動。")
        except OSError as exc:
            self.log(f"scrcpy 啟動失敗：{exc}")

    def _start_capture_loop(self):
        if self.capture_thread and self.capture_thread.is_alive():
            return
        self.capture_stop.clear()
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()

    def _capture_loop(self):
        while not self.capture_stop.is_set() and not self.closing:
            try:
                frame = self.bot.device.screenshot_scaled()
                with self.frame_lock:
                    self.last_frame = frame
                self.root.after(0, self._draw_preview)
            except Exception as exc:
                self.root.after(0, self.status_var.set, f"畫面擷取中斷：{exc}")
                time.sleep(0.8)
            time.sleep(PREVIEW_INTERVAL_MS / 1000.0)

    def get_latest_frame(self):
        with self.frame_lock:
            return None if self.last_frame is None else self.last_frame.copy()

    def capture_once(self):
        if not self.bot:
            return False
        try:
            frame = self.bot.device.screenshot_scaled()
            with self.frame_lock:
                self.last_frame = frame
            self._draw_preview()
            return True
        except Exception as exc:
            self.log(f"擷取畫面失敗：{exc}")
            return False

    def _draw_preview(self, _event=None):
        if not hasattr(self, "preview"):
            return
        self.preview.delete("all")
        width = max(1, self.preview.winfo_width())
        height = max(1, self.preview.winfo_height())
        frame = self.get_latest_frame()
        if frame is None:
            self.preview.create_text(width // 2, height // 2, text="等待 MuMu 連線…",
                                     fill="#7f91aa", font=("Segoe UI", 15))
            return
        try:
            rgb = frame[:, :, ::-1]
            image = Image.fromarray(rgb)
            image.thumbnail((width - 8, height - 8), Image.Resampling.LANCZOS)
            self.preview_photo = ImageTk.PhotoImage(image)
            self.preview.create_image(width // 2, height // 2, image=self.preview_photo, anchor="center")
        except Exception as exc:
            self.preview.create_text(width // 2, height // 2, text=f"畫面轉換失敗：{exc}",
                                     fill="#f0a0a0")

    def open_template_wizard(self):
        if not self.bot or not self.bot.device.serial:
            messagebox.showwarning("尚未連線", "請先連接 MuMu。")
            return
        if self.wizard and self.wizard.window.winfo_exists():
            self.wizard.window.lift()
            return
        self.wizard = TemplateWizard(self)

    def refresh_template_status(self):
        if not hasattr(self, "template_count_var"):
            return
        names = {path.stem for path in TEMPLATES.glob("*.png")}
        required = required_template_names(bool(self.skip_story_var.get()))
        count = sum(1 for name in required if name in names)
        self.template_count_var.set(f"模板 {count} / {len(required)}")

    def check_setup(self):
        if self.chapter_var.get() != "london":
            messagebox.showinfo("路線尚未開放", "此章節已列入第一部路線目錄；完成對應畫面與流程驗證後才會開放自動執行。")
            return
        if not self.bot or not self.bot.device.serial:
            messagebox.showwarning("尚未連線", "請先連接 MuMu。")
            return
        try:
            target = int(self.progress_target_var.get())
            runs = int(self.max_runs_var.get())
            if not (1 <= target <= 5 and 1 <= runs <= 30):
                raise ValueError
        except ValueError:
            messagebox.showwarning("設定錯誤", "進度目標需為 1～5，最大戰鬥次數需為 1～30。")
            return
        configure_london_profile(target, runs, bool(self.skip_story_var.get()))
        names = {path.stem for path in TEMPLATES.glob("*.png")}
        missing = [name for name in required_template_names(bool(self.skip_story_var.get())) if name not in names]
        self.refresh_template_status()
        if missing:
            messagebox.showwarning("模板尚未完成", "尚缺少模板：\n\n" + "、".join(missing[:10]))
            return
        messagebox.showinfo("設定完成", "倫敦第六節必要模板已齊全。第一次執行請全程監看。")

    def start_automation(self):
        if self.chapter_var.get() != "london":
            messagebox.showinfo("路線尚未開放", "目前只有倫敦第六節範例路線接上既有自動化引擎。")
            return
        if not self.bot or not self.bot.device.serial:
            messagebox.showwarning("尚未連線", "請先連接 MuMu。")
            return
        try:
            target = int(self.progress_target_var.get())
            max_runs = max(1, min(30, int(self.max_runs_var.get())))
            if not (1 <= target <= 5):
                raise ValueError
            ap_current = self.ap_current_var.get().strip()
            ap_cost = self.ap_cost_var.get().strip()
            if ap_current and ap_cost:
                affordable = estimate_affordable_runs(int(ap_current), int(ap_cost), max_runs)
                if affordable <= 0:
                    messagebox.showwarning("AP 不足", "依照手動輸入的 AP 與關卡消耗，無法負擔下一場。")
                    return
                max_runs = affordable
                self.config.ap_current = int(ap_current)
                self.config.ap_cost = int(ap_cost)
            elif ap_current or ap_cost:
                messagebox.showwarning("AP 資料不完整", "請同時輸入目前 AP 與每場 AP 消耗，或兩欄都留空。")
                return
        except ValueError:
            messagebox.showwarning("設定錯誤", "請確認次數、AP 與 AP 消耗都是有效整數。")
            return

        configure_london_profile(target, max_runs, bool(self.skip_story_var.get()))
        names = {path.stem for path in TEMPLATES.glob("*.png")}
        missing = [name for name in required_template_names(bool(self.skip_story_var.get())) if name not in names]
        self.refresh_template_status()
        if missing:
            messagebox.showwarning("尚未完成設定", "請先完成畫面模板設定。缺少：\n\n" + "、".join(missing[:8]))
            self.open_template_wizard()
            return

        self.config.max_runs = max_runs
        self.config.progress_target = target
        self.config.skip_story = bool(self.skip_story_var.get())
        self.config.selected_chapter = self.chapter_var.get()
        save_config(self.config)
        try:
            self.bot.start(LONDON_ROUTE_ID, safe_mode=False)
            self.session_started_at = datetime.now()
            self.session_runs_observed = 0
            self.log(f"已開始倫敦第六節測試；本次最多 {max_runs} 場。")
        except Exception as exc:
            messagebox.showerror("無法開始", str(exc))

    def pause_automation(self):
        if self.bot:
            self.bot.pause()

    def resume_automation(self):
        if self.bot:
            self.bot.resume()

    def stop_automation(self):
        if self.bot:
            self.bot.stop()
            self.log("已送出停止指令。")

    def _finish_session_if_needed(self, state: str):
        if self.session_started_at and state == "idle":
            ended = datetime.now()
            status = "completed" if self.session_runs_observed >= self.config.progress_target else "stopped_or_incomplete"
            self.stats.record_session(
                LONDON_ROUTE_ID, self.session_started_at, ended,
                self.session_runs_observed, status,
            )
            self.session_started_at = None
            self.refresh_stats()
            self.log(f"本次工作階段已記錄：觀察到 {self.session_runs_observed} 場。")

    def _refresh_status(self):
        if self.closing:
            return
        if self.bot:
            try:
                status = self.bot.status()
                state = status.get("state", "idle")
                current = status.get("current") or {}
                run_number = int(current.get("run", 0) or 0)
                self.session_runs_observed = max(self.session_runs_observed, run_number)
                state_label = {"idle": "待命", "running": "執行中", "paused": "已暫停",
                               "stopping": "停止中"}.get(state, state)
                if current:
                    self.status_var.set(f"{state_label} · {current.get('stage_name', current.get('stage', ''))} · {run_number} 次")
                else:
                    self.status_var.set(f"ADB 已連線 · {state_label}")
                logs = status.get("logs", [])
                signature = tuple((item.get("time"), item.get("text")) for item in logs[:8])
                if logs and signature != self.last_log_signature:
                    self.last_log_signature = signature
                    for item in reversed(logs[:8]):
                        self._append_log(f"[{item.get('time', '')}] {item.get('text', '')}")
                self._finish_session_if_needed(state)
            except Exception:
                pass
        self.root.after(500, self._refresh_status)

    def _append_log(self, message: str):
        if not hasattr(self, "log_box"):
            return
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def log(self, message: str):
        if threading.current_thread() is threading.main_thread():
            self._append_log(f"[{time.strftime('%H:%M:%S')}] {message}")
        else:
            self.root.after(0, self.log, message)

    def close(self):
        self.closing = True
        if self.bot:
            self.bot.stop()
        self.capture_stop.set()
        if self.scrcpy_process and self.scrcpy_process.poll() is None:
            try:
                self.scrcpy_process.terminate()
                self.scrcpy_process.wait(timeout=3)
            except Exception:
                try:
                    self.scrcpy_process.kill()
                except Exception:
                    pass
        self.root.destroy()


def main():
    root = tk.Tk()
    AutoRouteDesktopApp(root)
    root.mainloop()
