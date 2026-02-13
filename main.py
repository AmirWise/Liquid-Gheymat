"""
Liquid Gheymat Price Tracker — Professional Edition
Real-time currency/crypto/metal price monitor (CustomTkinter GUI)

What’s new in this update:
- Faster UI updates (card reuse instead of full re-render)
- Portfolio management (remove items, sort)
- Searchable currency picker
- Market insights (top gainers/losers)
- Startup from local cache for instant first paint
- Better auto-refresh (Tk scheduler, no busy background loop)
- Export selected data to CSV + copy to clipboard
- Settings (refresh interval, alerts threshold, notifications, cache tools)
- More resilient API layer (retries, circuit breaker, in-memory cache)

Note:
This code focuses on clean structure, maintainability, and robust behavior.
"""

from __future__ import annotations

import asyncio
import ctypes
import io
import json
import logging
import math
import os
import queue
import sqlite3
import sys
import threading
import time
import uuid
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import requests
import customtkinter as ctk
import pyglet
import tkinter as tk
from tkinter import messagebox

# Ensure console uses UTF-8 (helps on some Windows terminals)
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# Optional / platform-specific
try:
    import aiohttp  # type: ignore
    AIOHTTP_AVAILABLE = True
except Exception:
    aiohttp = None  # type: ignore
    AIOHTTP_AVAILABLE = False

IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

PYWINSTYLES_AVAILABLE = False
if IS_WINDOWS:
    try:
        import pywinstyles  # type: ignore
        PYWINSTYLES_AVAILABLE = True
    except Exception:
        PYWINSTYLES_AVAILABLE = False


# =============================================================================
# Logging
# =============================================================================

class LogManager:
    """Central logging configuration (console + optional file)."""

    @staticmethod
    def setup_logging() -> logging.Logger:
        logger = logging.getLogger("LiquidGheymat")
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()

        # Console handler (UTF-8 safe)
        try:
            wrapped_stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
            console_handler = logging.StreamHandler(wrapped_stdout)
        except Exception:
            console_handler = logging.StreamHandler(sys.stdout)

        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        ))
        logger.addHandler(console_handler)

        # File handler (optional)
        try:
            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)
            file_handler = logging.FileHandler(
                log_dir / f"liquid_gheymat_{datetime.now().strftime('%Y%m%d')}.log",
                encoding="utf-8",
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
            ))
            logger.addHandler(file_handler)
        except Exception:
            # File logging is nice-to-have
            pass

        return logger


logger = LogManager.setup_logging()


# =============================================================================
# Configuration
# =============================================================================

class ConnectionStatus(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    CACHED = "cached"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"


@dataclass(frozen=True)
class AppConfiguration:
    # App
    APP_NAME: str = "Liquid Gheymat Price Tracker"
    APP_VERSION: str = "4.0.0"
    APP_AUTHOR: str = "Local App"

    # Window
    WINDOW_WIDTH: int = 1200
    WINDOW_HEIGHT: int = 900
    MIN_WIDTH: int = 1000
    MIN_HEIGHT: int = 780

    # Layout
    GRID_COLUMNS: int = 4
    CARD_WIDTH: int = 240
    CARD_HEIGHT: int = 160
    CARD_PADDING: int = 8

    # Fonts
    PRIMARY_FONT: str = "SF Pro Display"
    FALLBACK_FONT: str = "Segoe UI"
    PERSIAN_FONT: str = "Vazirmatn"

    # API
    PRIMARY_API_URL: str = (
        "https://brsapi.ir/Api/Market/Gold_Currency.php?key=BWUuKdavyBLGXxidEjfNJeb33rsryQfh"
    )
    BACKUP_API_ENDPOINTS: List[str] = field(default_factory=lambda: [
        "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,binancecoin,cardano,solana,polkadot,dogecoin,avalanche-2,polygon,chainlink&vs_currencies=usd&include_24hr_change=true",
        "https://api.exchangerate-api.com/v4/latest/USD",
    ])
    API_TIMEOUT: int = 15
    API_RETRY_COUNT: int = 3
    API_RETRY_DELAY: float = 1.0  # base delay
    VERIFY_SSL: bool = True
    USER_AGENT: str = "LiquidGheymat/4.0 (Desktop)"

    # Refresh
    DEFAULT_REFRESH_INTERVAL: int = 300  # seconds
    MIN_REFRESH_INTERVAL: int = 30
    MAX_REFRESH_INTERVAL: int = 3600

    # Cache
    CACHE_DURATION: int = 45  # in-memory seconds
    DATABASE_PATH: str = "liquid_glass_data.db"

    # Performance
    MAX_WORKER_THREADS: int = 4
    UI_UPDATE_BATCH_SIZE: int = 12

    # History / Widgets
    HISTORY_RETENTION_DAYS: int = 14
    HISTORY_MAX_POINTS: int = 240  # max points rendered in sparklines
    WIDGET_WIDTH: int = 280
    WIDGET_HEIGHT: int = 170
    WIDGET_MIN_WIDTH: int = 210
    WIDGET_MIN_HEIGHT: int = 130
    WIDGET_DEFAULT_OPACITY: float = 0.98

config = AppConfiguration()


# =============================================================================
# Resources / Colors
# =============================================================================

class ResourceManager:
    """Resource loading with caching, PyInstaller friendly."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @staticmethod
    def get_resource_path(relative_path: str) -> Path:
        try:
            base_path = Path(sys._MEIPASS)  # type: ignore[attr-defined]
        except Exception:
            base_path = Path(__file__).parent
        return base_path / relative_path

    @lru_cache(maxsize=32)
    def load_font(self, font_path: str) -> bool:
        """Load a font file so Tk/CustomTkinter can use it reliably on Windows."""
        try:
            full_path = self.get_resource_path(font_path)
            if not full_path.exists():
                return False

            # 1) Register for Tk / CustomTkinter
            try:
                ctk.FontManager.load_font(str(full_path))
            except Exception:
                pass

            # 2) Private font registration on Windows (no system install required)
            if IS_WINDOWS:
                try:
                    FR_PRIVATE = 0x10
                    gdi32 = ctypes.windll.gdi32
                    user32 = ctypes.windll.user32
                    gdi32.AddFontResourceExW(str(full_path), FR_PRIVATE, 0)
                    try:
                        user32.SendMessageW(0xFFFF, 0x001D, 0, 0)  # WM_FONTCHANGE
                    except Exception:
                        pass
                except Exception:
                    pass

            # 3) Keep pyglet registration as a harmless fallback
            try:
                pyglet.font.add_file(str(full_path))
            except Exception:
                pass

            logger.info(f"Font loaded: {font_path}")
            return True
        except Exception as e:
            logger.debug(f"Font load failed for {font_path}: {e}")
            return False

    @lru_cache(maxsize=16)
    def load_icon(self, icon_path: str) -> Optional[str]:
        try:
            full_path = self.get_resource_path(icon_path)
            if full_path.exists():
                return str(full_path)
        except Exception:
            pass
        return None

    def cleanup_resources(self) -> None:
        try:
            self.load_font.cache_clear()
            self.load_icon.cache_clear()
        except Exception:
            pass


resource_manager = ResourceManager()


@dataclass(frozen=True)
class ColorPalette:
    # Backgrounds
    bg_light: str = "#f8f9fb"
    bg_dark: str = "#0a0a0c"

    # Glass
    glass_light: str = "#ffffff"
    glass_dark: str = "#1a1a1e"
    glass_overlay_light: str = "#fdfdfe"
    glass_overlay_dark: str = "#151518"

    # Accents
    accent_blue: str = "#007AFF"
    accent_blue_hover: str = "#0056CC"
    accent_green: str = "#32D74B"
    accent_red: str = "#FF453A"
    accent_orange: str = "#FF9F0A"

    # Text
    text_primary_light: str = "#1d1d1f"
    text_primary_dark: str = "#f5f5f7"
    text_secondary_light: str = "#515154"
    text_secondary_dark: str = "#a1a1a6"
    text_tertiary_light: str = "#8e8e93"
    text_tertiary_dark: str = "#636366"

    # Borders
    border_light: str = "#f0f0f3"
    border_dark: str = "#2c2c2e"
    separator_light: str = "#f2f2f7"
    separator_dark: str = "#1c1c1e"

    # Status
    status_success: str = "#32D74B"
    status_warning: str = "#FF9F0A"
    status_error: str = "#FF453A"
    status_info: str = "#007AFF"


colors = ColorPalette()

DEFAULT_COLORS = colors

MIDNIGHT_COLORS = ColorPalette(
    # Force midnight to be truly dark even if a widget accidentally resolves "light" colors
    bg_light="#07080c",
    bg_dark="#07080c",

    # Dark glass base (distinct from Crystal)
    glass_light="#0f111a",
    glass_dark="#0f111a",
    glass_overlay_light="#101327",
    glass_overlay_dark="#101327",

    # Accents
    accent_blue="#4E8CFF",
    accent_blue_hover="#3B6ED6",
    accent_green=DEFAULT_COLORS.accent_green,
    accent_red=DEFAULT_COLORS.accent_red,
    accent_orange=DEFAULT_COLORS.accent_orange,

    # Text
    text_primary_light="#F2F4FF",
    text_primary_dark="#F2F4FF",
    text_secondary_light="#A8AFC6",
    text_secondary_dark="#A8AFC6",
    text_tertiary_light="#6E7691",
    text_tertiary_dark="#6E7691",

    # Borders / separators
    border_light="#232536",
    border_dark="#232536",
    separator_light="#121424",
    separator_dark="#121424",

    # Status
    status_success=DEFAULT_COLORS.status_success,
    status_warning=DEFAULT_COLORS.status_warning,
    status_error=DEFAULT_COLORS.status_error,
    status_info="#4E8CFF",
)

# =============================================================================
# Localization
# =============================================================================

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "en": {
        "portfolio_items": "Items",
        "best": "Best",
        "worst": "Worst",
        "updated": "Updated",

        # Toolbar / hero
        "toolbar_title": "Liquid Gheymat",
        "btn_add_currency": "➕ Add Currency",
        "language_label": "Language",

        "hero_title": "💎 Liquid Gheymat",
        "hero_subtitle": "Real-time Currency • Crypto • Gold • Portfolio",
        "hero_version": "Version {version} • Cached startup • Smoother UI",

        # Sections
        "section_featured": "📈 Featured Markets",
        "section_insights": "⚡ Market Insights",
        "section_portfolio": "💼 Your Portfolio",
        "section_controls": "🎛️ Data Controls",
        "section_settings": "⚙️ Settings",
        "section_theme": "🎨 Theme",
        "section_history": "📉 Price History",
        "section_converter": "🧮 Converter",
        "section_widgets": "🧩 Desktop Widgets",
        "theme_liquid_glass": "💧 Liquid Glass",
        "theme_vibrancy": "🌟 Vibrancy",
        "theme_crystal": "💎 Crystal",
        "theme_midnight": "🌙 Midnight",
        "theme_paper": "📄 Paper",
        "theme_paper_noir": "⬛ Paper Noir",
        "theme_name_liquid_glass": "Liquid Glass",
        "theme_name_vibrancy": "Vibrancy",
        "theme_name_crystal": "Crystal",
        "theme_name_midnight": "Midnight",
        "theme_name_paper": "Paper",
        "theme_name_paper_noir": "Paper Noir",

        # Insights
        "top_gainers": "Top Gainers",
        "top_losers": "Top Losers",

        # History
        "history_symbol": "Symbol",
        "history_period": "Period",
        "history_loading": "Loading history…",
        "history_no_data": "No history yet",
        "history_change": "Change",
        "history_min": "Min",
        "history_max": "Max",
        "period_1h": "1h",
        "period_6h": "6h",
        "period_24h": "24h",
        "period_7d": "7d",

        # Converter
        "converter_amount": "Amount",
        "converter_from": "From",
        "converter_to": "To",
        "converter_result": "Result",
        "converter_need_usd": "USD price is needed for this conversion",

        # Widgets
        "widgets_add_title": "Add a widget",
        "widgets_active_title": "Active widgets",
        "widgets_type": "Type",
        "widgets_symbol": "Symbol",
        "widget_type_price": "Price card",
        "widget_type_movers": "Top movers",
        "widget_type_portfolio": "Portfolio mini",
        "btn_add_widget": "➕ Add Widget",
        "btn_remove_widget": "Remove",
        "toast_widget_added": "🧩 Widget added",
        "toast_widget_removed": "🧹 Widget removed",
        "toast_widget_not_supported": "⚠️ Desktop widgets are supported on Windows only",

        # Background
        "run_in_background": "Run in background when closing",
        "toast_background_on": "🟣 Background mode enabled (close = minimize)",
        "toast_background_off": "⚪ Background mode disabled",

        # Controls / settings labels
        "api": "API",
        "data": "Data",
        "effects": "Effects",
        "sort": "Sort:",
        "auto_refresh": "Auto-refresh",
        "last_update": "Last Update: {time}",
        "refresh_interval": "Refresh interval",
        "alerts_title": "Price change alerts",
        "enable_alerts": "Enable alerts",
        "threshold": "Threshold: {value:.1f}%",
        "tools": "Tools",
        "window_options": "Window",
        "always_on_top": "Always on top",

        # Buttons
        "btn_refresh": "🔄 Refresh",
        "btn_test_api": "🧪 Test API",
        "btn_export_csv": "📄 Export CSV",
        "btn_copy": "📋 Copy",
        "btn_clear_cache": "🧹 Clear cache",
        "btn_performance": "📈 Performance",
        "btn_add": "Add",
        "btn_close": "Close",

        # Placeholders
        "placeholder_search": "Search…",
        "placeholder_portfolio_filter": "Filter portfolio…",
        "portfolio_add_title": "➕ Add to portfolio",

        # Sort modes
        "sort_default": "Default",
        "sort_name": "Name",
        "sort_symbol": "Symbol",
        "sort_price": "Price",
        "sort_change": "Change",

        # Connection messages
        "status_connected": "🟢 Connected • {count} items",
        "status_cached": "🟠 Cached • {count} items",
        "status_connecting": "🔵 Connecting…",
        "status_rate_limited": "🟠 Rate limited",
        "status_error": "🔴 Offline / Error",

        # Data status
        "data_quality_excellent": "Excellent",
        "data_quality_cached": "Cached",
        "data_quality_connecting": "Connecting",
        "data_quality_limited": "Limited",
        "data_source_live": "Live API",
        "data_source_db": "Local DB",
        "data_source_offline": "Fallback/Offline",

        # Toasts / misc
        "toast_updated": "✅ Updated",
        "toast_loaded_cache": "🗃️ Loaded cached data (will refresh online)",
        "toast_added": "✅ Added {sym}",
        "toast_removed": "🗑️ Removed {sym}",
        "toast_interval_set": "⏱️ Interval set to {interval}",
        "toast_autorefresh_on": "▶️ Auto-refresh ON",
        "toast_autorefresh_off": "⏸️ Auto-refresh OFF",
        "toast_alerts_on": "🔔 Alerts ON",
        "toast_alerts_off": "🔕 Alerts OFF",
        "toast_cache_cleared": "🧹 Cache cleared",
        "toast_topmost_on": "📌 Always on top ON",
        "toast_topmost_off": "📌 Always on top OFF",
        "toast_copied": "📋 Copied to clipboard",
        "toast_csv_exported": "📄 CSV exported",
        "toast_refresh_failed": "❌ Could not refresh (offline?)",
        "toast_applying_theme": "🎨 Applying {name}…",
        "toast_price_moved": "{direction} {sym} moved {delta:+.2f}% since last update",
        "status_refreshing": "🔄 Refreshing…",

        # Dialogs / errors
        "dlg_add_currency_title": "Add Currency",
        "no_matches": "No matches",
        "api_test_title": "API Test",
        "api_test_ok": "✅ API Test Successful\n\nResponse time: {elapsed:.2f}s\nItems parsed: {count}\n",
        "api_test_fail": "❌ API Test Failed\n\nNo data received.",
        "export_title": "Export CSV",
        "filetype_csv": "CSV files",
        "filetype_all": "All files",
        "export_failed": "Failed:\n{error}",
        "clear_cache_title": "Clear cache",
        "performance_title": "Performance",
        "critical_error_title": "Critical Error",
    },
    "fa": {
        "portfolio_items": "آیتم ها",
        "best": "بهترین",
        "worst": "بدترین",
        "updated": "آخرین بروزرسانی",

        # Toolbar / hero
        "toolbar_title": "لیکوئید قیمت",
        "btn_add_currency": "➕ افزودن ارز",
        "language_label": "زبان",

        "hero_title": "💎 لیکوئید قیمت",
        "hero_subtitle": "نمایش لحظه‌ای ارز • کریپتو • طلا • پورتفو",
        "hero_version": "نسخه {version} • اجرای سریع از کش • رابط نرم‌تر",

        # Sections
        "section_featured": "📈 بازارهای منتخب",
        "section_insights": "⚡ تحلیل بازار",
        "section_portfolio": "💼 پورتفوی شما",
        "section_controls": "🎛️ کنترل داده",
        "section_settings": "⚙️ تنظیمات",
        "section_theme": "🎨 تم",
        "section_history": "📉 تاریخچه قیمت",
        "section_converter": "🧮 تبدیل‌کننده",
        "section_widgets": "🧩 ویجت‌های دسکتاپ",
        "theme_liquid_glass": "💧 شیشه‌ای",
        "theme_vibrancy": "🌟 درخشندگی",
        "theme_crystal": "💎 کریستال",
        "theme_midnight": "🌙 نیمه‌شب",
        "theme_paper": "📄 کاغذی",
        "theme_name_liquid_glass": "شیشه‌ای",
        "theme_name_vibrancy": "درخشندگی",
        "theme_name_crystal": "کریستال",
        "theme_name_midnight": "نیمه‌شب",
        "theme_name_paper": "کاغذی",

        # Insights
        "top_gainers": "بیشترین رشد",
        "top_losers": "بیشترین افت",

        # History
        "history_symbol": "نماد",
        "history_period": "بازه",
        "history_loading": "در حال بارگذاری تاریخچه…",
        "history_no_data": "تاریخچه‌ای موجود نیست",
        "history_change": "تغییر",
        "history_min": "کمینه",
        "history_max": "بیشینه",
        "period_1h": "۱ ساعت",
        "period_6h": "۶ ساعت",
        "period_24h": "۲۴ ساعت",
        "period_7d": "۷ روز",

        # Converter
        "converter_amount": "مقدار",
        "converter_from": "از",
        "converter_to": "به",
        "converter_result": "نتیجه",
        "converter_need_usd": "برای این تبدیل، نرخ دلار لازم است",

        # Widgets
        "widgets_add_title": "افزودن ویجت",
        "widgets_active_title": "ویجت‌های فعال",
        "widgets_type": "نوع",
        "widgets_symbol": "نماد",
        "widget_type_price": "کارت قیمت",
        "widget_type_movers": "تاپ‌موور",
        "widget_type_portfolio": "خلاصه پورتفو",
        "btn_add_widget": "➕ افزودن ویجت",
        "btn_remove_widget": "حذف",
        "toast_widget_added": "🧩 ویجت اضافه شد",
        "toast_widget_removed": "🧹 ویجت حذف شد",
        "toast_widget_not_supported": "⚠️ ویجت دسکتاپ فعلاً فقط ویندوز را پشتیبانی می‌کند",

        # Background
        "run_in_background": "اجرای پس‌زمینه هنگام بستن",
        "toast_background_on": "🟣 پس‌زمینه فعال شد (بستن = مینیمایز)",
        "toast_background_off": "⚪ پس‌زمینه غیرفعال شد",

        # Controls / settings labels
        "api": "API",
        "data": "داده",
        "effects": "افکت‌ها",
        "sort": "مرتب‌سازی:",
        "auto_refresh": "به‌روزرسانی خودکار",
        "last_update": "آخرین بروزرسانی: {time}",
        "refresh_interval": "فاصله بروزرسانی",
        "alerts_title": "هشدار تغییر قیمت",
        "enable_alerts": "فعال‌سازی هشدار",
        "threshold": "آستانه: {value:.1f}٪",
        "tools": "ابزارها",
        "window_options": "پنجره",
        "always_on_top": "همیشه روی صفحه",

        # Buttons
        "btn_refresh": "🔄 بروزرسانی",
        "btn_test_api": "🧪 تست API",
        "btn_export_csv": "📄 خروجی CSV",
        "btn_copy": "📋 کپی",
        "btn_clear_cache": "🧹 پاکسازی کش",
        "btn_performance": "📈 عملکرد",
        "btn_add": "افزودن",
        "btn_close": "بستن",

        # Placeholders
        "placeholder_search": "جستجو…",
        "placeholder_portfolio_filter": "فیلتر پورتفو…",
        "portfolio_add_title": "➕ افزودن به پورتفو",

        # Sort modes
        "sort_default": "پیش‌فرض",
        "sort_name": "نام",
        "sort_symbol": "نماد",
        "sort_price": "قیمت",
        "sort_change": "تغییر",

        # Connection messages
        "status_connected": "🟢 متصل • {count} مورد",
        "status_cached": "🟠 کش • {count} مورد",
        "status_connecting": "🔵 در حال اتصال…",
        "status_rate_limited": "🟠 محدودیت درخواست",
        "status_error": "🔴 آفلاین / خطا",

        # Data status
        "data_quality_excellent": "عالی",
        "data_quality_cached": "کش",
        "data_quality_connecting": "در حال اتصال",
        "data_quality_limited": "محدود",
        "data_source_live": "API آنلاین",
        "data_source_db": "دیتابیس محلی",
        "data_source_offline": "آفلاین/پیش‌فرض",

        # Toasts / misc
        "toast_updated": "✅ بروزرسانی شد",
        "toast_loaded_cache": "🗃️ داده‌های کش بارگذاری شد (به‌زودی آنلاین بروزرسانی می‌شود)",
        "toast_added": "✅ {sym} اضافه شد",
        "toast_removed": "🗑️ {sym} حذف شد",
        "toast_interval_set": "⏱️ فاصله روی {interval} تنظیم شد",
        "toast_autorefresh_on": "▶️ بروزرسانی خودکار فعال",
        "toast_autorefresh_off": "⏸️ بروزرسانی خودکار غیرفعال",
        "toast_alerts_on": "🔔 هشدار فعال",
        "toast_alerts_off": "🔕 هشدار غیرفعال",
        "toast_cache_cleared": "🧹 کش پاک شد",
        "toast_topmost_on": "📌 همیشه روی صفحه فعال شد",
        "toast_topmost_off": "📌 همیشه روی صفحه غیرفعال شد",
        "toast_copied": "📋 کپی شد",
        "toast_csv_exported": "📄 CSV ذخیره شد",
        "toast_refresh_failed": "❌ امکان بروزرسانی نیست (آفلاین؟)",
        "toast_applying_theme": "🎨 در حال اعمال {name}…",
        "toast_price_moved": "{direction} {sym} نسبت به بروزرسانی قبل {delta:+.2f}٪ تغییر کرد",
        "status_refreshing": "🔄 در حال بروزرسانی…",

        # Dialogs / errors
        "dlg_add_currency_title": "افزودن ارز",
        "no_matches": "موردی پیدا نشد",
        "api_test_title": "تست API",
        "api_test_ok": "✅ تست API موفق بود\n\nزمان پاسخ: {elapsed:.2f} ثانیه\nتعداد آیتم: {count}\n",
        "api_test_fail": "❌ تست API ناموفق بود\n\nداده‌ای دریافت نشد.",
        "export_title": "خروجی CSV",
        "filetype_csv": "فایل‌های CSV",
        "filetype_all": "همه فایل‌ها",
        "export_failed": "ناموفق:\n{error}",
        "clear_cache_title": "پاکسازی کش",
        "performance_title": "عملکرد",
        "critical_error_title": "خطای بحرانی",
    },
}


def tr(lang: str, key: str, **kwargs) -> str:
    """Lightweight translation helper with safe fallback to English."""
    lang_key = str(lang or "en").lower()
    base = TRANSLATIONS.get(lang_key, TRANSLATIONS["en"])
    template = base.get(key) or TRANSLATIONS["en"].get(key) or key
    try:
        return template.format(**kwargs)
    except Exception:
        return template


def is_rtl(lang: str) -> bool:
    return str(lang or "").lower().startswith("fa")


# =============================================================================
# Database
# =============================================================================

class DatabaseManager:
    """SQLite store for cache + preferences."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_database()

    def _init_database(self) -> None:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS currency_cache (
                        symbol TEXT PRIMARY KEY,
                        data TEXT NOT NULL,
                        timestamp REAL NOT NULL
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS user_preferences (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS selected_currencies (
                        symbol TEXT PRIMARY KEY,
                        added_at REAL NOT NULL
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS price_history (
                        symbol TEXT NOT NULL,
                        ts REAL NOT NULL,
                        price REAL NOT NULL,
                        PRIMARY KEY(symbol, ts)
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS desktop_widgets (
                        widget_id TEXT PRIMARY KEY,
                        data TEXT NOT NULL,
                        created_at REAL NOT NULL
                    )
                """)
                conn.commit()
        except Exception as e:
            logger.error(f"Database init failed: {e}")

    # ----- cache -----

    def cache_bulk_currency_data(self, currencies: Dict[str, Dict[str, Any]]) -> None:
        """Cache the latest dataset for faster startup."""
        try:
            now = time.time()
            rows = [(sym, json.dumps(data, ensure_ascii=False), now) for sym, data in currencies.items()]
            with sqlite3.connect(self.db_path) as conn:
                conn.executemany(
                    "INSERT OR REPLACE INTO currency_cache(symbol, data, timestamp) VALUES (?, ?, ?)",
                    rows,
                )
                conn.commit()
        except Exception as e:
            logger.debug(f"Bulk cache write failed: {e}")

    def load_cached_currencies(self, max_age_seconds: int = 6 * 3600) -> Dict[str, Dict[str, Any]]:
        """Load cached dataset (not expired)."""
        try:
            cutoff = time.time() - max_age_seconds
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT symbol, data, timestamp FROM currency_cache WHERE timestamp >= ?",
                    (cutoff,),
                )
                out: Dict[str, Dict[str, Any]] = {}
                for sym, raw, ts in cursor.fetchall():
                    try:
                        item = json.loads(raw)
                        if isinstance(item, dict):
                            item.setdefault("symbol", sym)
                            item.setdefault("timestamp", ts)
                            out[sym] = item
                    except Exception:
                        continue
                return out
        except Exception as e:
            logger.debug(f"Load cached currencies failed: {e}")
            return {}

    def prune_cache(self, keep_last_seconds: int = 24 * 3600) -> None:
        """Delete old cache rows (or clear all if keep_last_seconds<=0)."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if keep_last_seconds <= 0:
                    conn.execute("DELETE FROM currency_cache")
                else:
                    cutoff = time.time() - keep_last_seconds
                    conn.execute("DELETE FROM currency_cache WHERE timestamp < ?", (cutoff,))
                conn.commit()
        except Exception as e:
            logger.debug(f"Cache prune failed: {e}")

    # ----- preferences -----

    def save_preference(self, key: str, value: Any) -> None:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO user_preferences(key, value) VALUES (?, ?)",
                    (str(key), json.dumps(value, ensure_ascii=False)),
                )
                conn.commit()
        except Exception as e:
            logger.debug(f"Preference save failed: {e}")

    def load_preference(self, key: str, default: Any = None) -> Any:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT value FROM user_preferences WHERE key = ?",
                    (str(key),),
                )
                row = cursor.fetchone()
            if row is None:
                return default
            raw = row[0]
            try:
                return json.loads(raw)
            except Exception:
                return raw
        except Exception as e:
            logger.debug(f"Preference load failed: {e}")
            return default

    # ----- portfolio -----

    def save_selected_currencies(self, currencies: Iterable[str]) -> None:
        try:
            symbols = sorted({str(s).upper().strip() for s in currencies if str(s).strip()})
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM selected_currencies")
                conn.executemany(
                    "INSERT INTO selected_currencies(symbol, added_at) VALUES (?, ?)",
                    [(sym, time.time()) for sym in symbols],
                )
                conn.commit()
        except Exception as e:
            logger.debug(f"Selected currencies save failed: {e}")

    def load_selected_currencies(self) -> set[str]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT symbol FROM selected_currencies")
                return {row[0] for row in cursor.fetchall()}
        except Exception as e:
            logger.debug(f"Selected currencies load failed: {e}")
            return set()


    # ----- history -----

    def insert_price_history_bulk(self, rows: Sequence[Tuple[str, float, float]]) -> None:
        """Insert (symbol, ts, price) rows. Safe to call often; runs quickly with executemany."""
        if not rows:
            return
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.executemany(
                    "INSERT OR REPLACE INTO price_history(symbol, ts, price) VALUES (?, ?, ?)",
                    [(str(sym).upper().strip(), float(ts), float(price)) for sym, ts, price in rows],
                )
                conn.commit()
        except Exception as e:
            logger.debug(f"History bulk insert failed: {e}")

    def load_price_history(self, symbol: str, *, since_ts: float, limit: int = 2000) -> List[Tuple[float, float]]:
        sym = str(symbol or "").upper().strip()
        if not sym:
            return []
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT ts, price FROM price_history WHERE symbol = ? AND ts >= ? ORDER BY ts ASC LIMIT ?",
                    (sym, float(since_ts), int(max(1, limit))),
                )
                return [(float(ts), float(price)) for ts, price in cursor.fetchall()]
        except Exception as e:
            logger.debug(f"History load failed: {e}")
            return []

    def prune_price_history(self, keep_days: int = 14) -> None:
        try:
            keep_days = int(max(1, keep_days))
            cutoff = time.time() - keep_days * 86400
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM price_history WHERE ts < ?", (float(cutoff),))
                conn.commit()
        except Exception as e:
            logger.debug(f"History prune failed: {e}")

    # ----- desktop widgets -----

    def save_desktop_widget(self, widget_id: str, data: Dict[str, Any]) -> None:
        wid = str(widget_id or "").strip()
        if not wid:
            return
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO desktop_widgets(widget_id, data, created_at) VALUES (?, ?, ?)",
                    (wid, json.dumps(dict(data or {}), ensure_ascii=False), time.time()),
                )
                conn.commit()
        except Exception as e:
            logger.debug(f"Widget save failed: {e}")

    def delete_desktop_widget(self, widget_id: str) -> None:
        wid = str(widget_id or "").strip()
        if not wid:
            return
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM desktop_widgets WHERE widget_id = ?", (wid,))
                conn.commit()
        except Exception as e:
            logger.debug(f"Widget delete failed: {e}")

    def load_desktop_widgets(self) -> List[Dict[str, Any]]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT widget_id, data FROM desktop_widgets ORDER BY created_at ASC")
                out: List[Dict[str, Any]] = []
                for wid, raw in cursor.fetchall():
                    try:
                        item = json.loads(raw)
                        if isinstance(item, dict):
                            item.setdefault("widget_id", wid)
                            out.append(item)
                    except Exception:
                        continue
                return out
        except Exception as e:
            logger.debug(f"Widgets load failed: {e}")
            return []


db_manager = DatabaseManager(config.DATABASE_PATH)


# =============================================================================
# API
# =============================================================================

class APIManager:
    """Robust API access (primary + fallbacks, retries, circuit breaker, cache)."""

    def __init__(self):
        self.session = self._create_session()
        self._last_data: Optional[Dict[str, Any]] = None
        self._last_data_ts: float = 0.0

        self.last_request_time = 0.0
        self.rate_limit_delay = 1.0

        self.failure_count = 0
        self.circuit_breaker_until = 0.0  # epoch seconds
        self.circuit_breaker_base = 15.0  # seconds

    def _create_session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update({
            "User-Agent": config.USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        })

        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=0,  # manual retries
        )
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _respect_rate_limit(self) -> None:
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self.last_request_time = time.time()

    def _circuit_open(self) -> bool:
        return time.time() < self.circuit_breaker_until

    def _trip_circuit(self) -> None:
        self.failure_count += 1
        backoff = min(self.circuit_breaker_base * (2 ** (self.failure_count - 1)), 300.0)
        self.circuit_breaker_until = time.time() + backoff

    def fetch_data_sync(self, force: bool = False, skip_primary: bool = False) -> Optional[Dict[str, Any]]:
        # In-memory cache for very frequent calls
        if not force and self._last_data is not None:
            if time.time() - self._last_data_ts < config.CACHE_DURATION:
                return self._last_data

        if self._circuit_open():
            logger.warning("Circuit breaker open — skipping network call.")
            return None

        # 1) Primary API
        if not skip_primary:
            data = self._request_with_retries(config.PRIMARY_API_URL, is_primary=True)
            if data:
                self._last_data = data
                self._last_data_ts = time.time()
                self.failure_count = 0
                return data

        # 2) Backups
        for url in config.BACKUP_API_ENDPOINTS:
            data = self._request_with_retries(url, is_primary=False)
            if data:
                self._last_data = data
                self._last_data_ts = time.time()
                self.failure_count = 0
                return data

        self._trip_circuit()
        return None

    def _request_with_retries(self, url: str, is_primary: bool) -> Optional[Dict[str, Any]]:
        delay = config.API_RETRY_DELAY
        last_err: str = ""
        for attempt in range(1, config.API_RETRY_COUNT + 1):
            try:
                self._respect_rate_limit()
                resp = self.session.get(url, timeout=config.API_TIMEOUT, verify=config.VERIFY_SSL)
                if resp.status_code == 429:
                    logger.warning("Rate limited (429).")
                    self.rate_limit_delay = min(max(self.rate_limit_delay, 1.0) * 1.5, 10.0)
                    time.sleep(min(delay * attempt, 10.0))
                    continue

                resp.raise_for_status()
                try:
                    data = resp.json()
                except Exception:
                    raw = (resp.text or "").strip()
                    raw = raw.lstrip("\ufeff").strip()
                    data = json.loads(raw) if raw else None
                if not data:
                    raise ValueError("Empty response")
                return data

            except requests.exceptions.Timeout as e:
                last_err = f"Timeout: {e}"
                logger.debug(f"Timeout ({attempt}/{config.API_RETRY_COUNT}) for {url}")
            except requests.exceptions.RequestException as e:
                last_err = f"RequestException: {e}"
                logger.debug(f"Request failed ({attempt}/{config.API_RETRY_COUNT}) for {url}: {e}")
            except (ValueError, json.JSONDecodeError) as e:
                last_err = f"ParseError: {e}"
                logger.debug(f"Parse failed ({attempt}/{config.API_RETRY_COUNT}) for {url}: {e}")
            except Exception as e:
                last_err = f"Unexpected: {e}"
                logger.debug(f"Unexpected error ({attempt}/{config.API_RETRY_COUNT}) for {url}: {e}")

            time.sleep(min(delay * attempt, 6.0))

        if last_err:
            logger.warning(f"API request failed for {url} (verify_ssl={config.VERIFY_SSL}): {last_err}")
        return None


    # ----- number helpers -----

    @staticmethod
    def _digits_to_en(s: str) -> str:
        if not s:
            return s
        trans = str.maketrans({
            "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4",
            "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
            "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
            "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
            "٬": ",", "،": ",", "٫": ".",  # Arabic/Persian separators
        })
        return s.translate(trans)

    @classmethod
    def _clean_number_str(cls, v: Any) -> str:
        if v is None:
            return ""
        if isinstance(v, (int, float)):
            return str(v)
        s = str(v).strip()
        s = cls._digits_to_en(s)
        # keep digits, sign and separators only
        # remove common tokens
        for tok in ("%", "٪", "ریال", "تومان", "USD", "USDT"):
            s = s.replace(tok, "")
        s = s.strip()
        # normalize separators
        s = s.replace(" ", "")
        s = s.replace("_", "")
        # remove thousands separators
        s = s.replace(",", "")
        return s

    @classmethod
    def _safe_float(cls, v: Any) -> Optional[float]:
        s = cls._clean_number_str(v)
        if not s:
            return None
        # handle leading/trailing junk
        try:
            return float(s)
        except Exception:
            # last attempt: keep only valid characters
            filtered = "".join(ch for ch in s if ch.isdigit() or ch in ".-+")
            try:
                return float(filtered) if filtered else None
            except Exception as e:
                try:
                    logger.warning(f"API request error: {e}")
                except Exception:
                    pass
                return None


    # ----- data processing -----

    def process_currency_data(self, raw_data: Any) -> Dict[str, Dict[str, Any]]:
        try:
            if self._is_primary_api_format(raw_data):
                return self._process_primary_api_format(raw_data)

            # CoinGecko "simple/price" format (backup endpoint)
            if isinstance(raw_data, dict) and self._looks_like_coingecko_simple_price(raw_data):
                return self._process_coingecko_simple_price(raw_data)

            # exchangerate-api format (backup endpoint)
            if isinstance(raw_data, dict) and isinstance(raw_data.get("rates"), dict):
                return self._process_exchangerate_api(raw_data)

            # Other backups (explicit format)
            if isinstance(raw_data, dict) and ("crypto" in raw_data or "fiat" in raw_data):
                return self._process_backup_api_format(raw_data)

            return self._process_generic_format(raw_data)
        except Exception as e:
            logger.debug(f"Currency processing failed: {e}")
            return {}

    def _is_primary_api_format(self, data: Any) -> bool:
        if not isinstance(data, dict):
            return False

        # Accept common primary API shapes (case-insensitive keys)
        indicators = {"gold", "currency", "crypto", "digital_currency", "arz", "tala", "sekke"}
        try:
            for k in data.keys():
                if str(k).strip().lower() in indicators:
                    return True
        except Exception:
            pass

        # Heuristic: lists of dict items with common fields
        for _, v in data.items():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                sample = v[0]
                if any(f in sample for f in ("symbol", "price", "unit", "name_fa", "name_en", "p", "c")):
                    return True
            if isinstance(v, dict) and self._looks_like_currency_item(v):
                return True
        return False

        indicators = ("Gold", "Currency", "Crypto", "Digital_Currency", "Arz", "Tala", "Sekke")
        if any(k in data for k in indicators):
            return True

        # Heuristic: lists of dict items with common fields
        for _, v in data.items():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                sample = v[0]
                if any(f in sample for f in ("symbol", "price", "unit", "name_fa", "name_en")):
                    return True
        return False

    def _process_primary_api_format(self, data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        for category_name, category_data in data.items():
            if isinstance(category_data, list):
                for item in category_data:
                    cur = self._process_single_currency_primary(item, str(category_name))
                    if cur:
                        out[cur["symbol"]] = cur
            elif isinstance(category_data, dict):
                if self._looks_like_currency_item(category_data):
                    cur = self._process_single_currency_primary(category_data, str(category_name))
                    if cur:
                        out[cur["symbol"]] = cur
                else:
                    for sub_key, sub_data in category_data.items():
                        if isinstance(sub_data, list):
                            for item in sub_data:
                                cur = self._process_single_currency_primary(item, f"{category_name}_{sub_key}")
                                if cur:
                                    out[cur["symbol"]] = cur
        return out

    def _process_single_currency_primary(self, item: Any, category: str) -> Optional[Dict[str, Any]]:
        if not isinstance(item, dict):
            return None

        symbol = self._extract_field(item, [
            "symbol", "Symbol", "SYMBOL", "code", "Code", "currency_code", "Currency_Code", "name_en", "Name_En"
        ])
        if not symbol:
            return None
        symbol = str(symbol).upper().strip()
        if not symbol:
            return None

        price = self._extract_field(item, [
            "price", "Price", "value", "Value", "rate", "Rate", "sell", "Sell", "buy", "Buy", "last_price", "Last_Price"
        ], default="0")

        price_f = self._safe_float(price)
        if price_f is None:
            return None
        price = price_f
        change = self._extract_field(item, [
            "change_percent", "Change_Percent", "change", "Change", "daily_change", "Daily_Change", "percent_change_24h"
        ], default="0")

        ch_f = self._safe_float(change)
        change = ch_f if ch_f is not None else 0.0
        unit = self._extract_field(item, [
            "unit", "Unit", "currency", "Currency", "base_currency", "Base_Currency", "quote_currency", "Quote_Currency"
        ], default="Toman")

        name = self._extract_field(item, [
            "name_fa", "Name_Fa", "name_en", "Name_En", "name", "Name", "title", "Title", "full_name", "Full_Name"
        ])
        if not name:
            name = self._get_currency_name_by_symbol(symbol)

        currency = {
            "symbol": symbol,
            "name": str(name),
            "price": str(price),
            "unit": str(unit),
            "change_percent": str(change),
            "category": category,
            "timestamp": time.time(),
            "source": "primary_api",
        }
        return currency if self._validate_currency_data(currency) else None

    def _process_backup_api_format(self, data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        for key in ("crypto", "fiat"):
            if key in data and isinstance(data[key], list):
                for item in data[key]:
                    if isinstance(item, dict) and item.get("symbol"):
                        sym = str(item["symbol"]).upper().strip()
                        if sym:
                            out[sym] = item
        return out


    def _looks_like_coingecko_simple_price(self, data: Dict[str, Any]) -> bool:
        # Expected: {"bitcoin": {"usd": 123, "usd_24h_change": 1.2}, ...}
        try:
            if not data:
                return False
            sample_key = next(iter(data.keys()))
            v = data.get(sample_key)
            if not isinstance(v, dict):
                return False
            return ("usd" in v) or ("usd_24h_change" in v)
        except Exception:
            return False

    def _process_coingecko_simple_price(self, data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        id_to_symbol = {
            "bitcoin": "BTC",
            "ethereum": "ETH",
            "binancecoin": "BNB",
            "cardano": "ADA",
            "solana": "SOL",
            "polkadot": "DOT",
            "dogecoin": "DOGE",
            "avalanche-2": "AVAX",
            "polygon": "MATIC",
            "chainlink": "LINK",
        }

        out: Dict[str, Dict[str, Any]] = {}
        for cid, payload in data.items():
            if not isinstance(payload, dict):
                continue
            sym = id_to_symbol.get(str(cid).strip().lower())
            if not sym:
                # Unknown id -> skip (keep predictable set)
                continue

            price = payload.get("usd")
            if price is None:
                continue

            change = payload.get("usd_24h_change", 0) or 0
            try:
                price_f = float(price)
            except Exception:
                continue

            try:
                change_f = float(change)
            except Exception:
                change_f = 0.0

            out[sym] = {
                "symbol": sym,
                "name": self._get_currency_name_by_symbol(sym),
                "price": str(price_f),
                "unit": "USD",
                "change_percent": str(change_f),
                "category": "crypto",
                "source": "coingecko",
            }

        return out

    def _process_exchangerate_api(self, data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        # Example: {"base_code":"USD","rates":{"EUR":0.91,...}}
        rates = data.get("rates") or {}
        base = str(data.get("base_code") or data.get("base") or "USD").upper().strip()

        # Convert rates so that "price" means 1 unit of currency in base currency.
        # If base=USD and rates["EUR"]=0.91 (1 USD = 0.91 EUR) => 1 EUR = 1/0.91 USD.
        out: Dict[str, Dict[str, Any]] = {}
        common = {"USD", "EUR", "GBP", "TRY", "AED", "CAD", "AUD", "JPY", "CHF", "CNY"}
        for sym, r in rates.items():
            sym_u = str(sym).upper().strip()
            if sym_u not in common:
                continue
            try:
                r_f = float(r)
            except Exception:
                continue
            if r_f <= 0:
                continue

            if sym_u == base:
                price_in_base = 1.0
            else:
                # 1 base = r sym => 1 sym = 1/r base
                price_in_base = 1.0 / r_f

            out[sym_u] = {
                "symbol": sym_u,
                "name": self._get_currency_name_by_symbol(sym_u),
                "price": str(price_in_base),
                "unit": base,
                "change_percent": "0",
                "category": "fiat",
                "source": "exchangerate-api",
            }

        return out

    def _process_generic_format(self, data: Any) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        items = self._extract_items_generic(data)
        for item in items:
            cur = self._process_single_currency_generic(item)
            if cur and self._validate_currency_data(cur):
                out[cur["symbol"]] = cur
        return out

    def _extract_items_generic(self, data: Any) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        if isinstance(data, dict):
            for _, v in data.items():
                if isinstance(v, list):
                    items.extend([x for x in v if isinstance(x, dict)])
                elif isinstance(v, dict) and self._looks_like_currency_item(v):
                    items.append(v)
        elif isinstance(data, list):
            items.extend([x for x in data if isinstance(x, dict)])
        return items

    def _process_single_currency_generic(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        symbol = self._extract_field(item, ["symbol", "Symbol", "code", "Code"])
        if not symbol:
            return None

        sym = str(symbol).upper().strip()
        price = self._extract_field(item, ["price", "Price", "value", "Value", "rate", "Rate"], default=0)
        price_f = self._safe_float(price)
        if price_f is None:
            return None
        price = price_f
        change = self._extract_field(item, ["change_percent", "change", "Change"], default=0)
        ch_f = self._safe_float(change)
        change = ch_f if ch_f is not None else 0.0
        unit = self._extract_field(item, ["unit", "Unit", "currency", "Currency"], default="USD")
        name = self._get_currency_name_by_symbol(sym)

        return {
            "symbol": sym,
            "name": name,
            "price": str(price),
            "unit": str(unit),
            "change_percent": str(change),
            "timestamp": time.time(),
            "source": "generic",
        }

    def _looks_like_currency_item(self, item: Dict[str, Any]) -> bool:
        essentials = (("symbol", "price"), ("Symbol", "Price"), ("code", "value"), ("name_en", "price"))
        return any(all(k in item for k in pair) for pair in essentials)

    def _extract_field(self, data: Dict[str, Any], field_names: Sequence[str], default: Any = None) -> Any:
        for name in field_names:
            if name in data:
                val = data.get(name)
                if val is not None and str(val).strip() != "":
                    return val
        return default

    def _validate_currency_data(self, currency: Dict[str, Any]) -> bool:
        for field in ("symbol", "name", "price", "unit"):
            if not str(currency.get(field, "")).strip():
                return False

        price_f = self._safe_float(currency.get("price"))
        if price_f is None:
            return False
        # store normalized numeric string (UI formatting will re-apply separators)
        currency["price"] = str(price_f)

        ch_f = self._safe_float(currency.get("change_percent", 0) or 0)
        if ch_f is None:
            currency["change_percent"] = "0"
        else:
            currency["change_percent"] = str(ch_f)
        return True



    def _get_currency_name_by_symbol(self, symbol: str) -> str:
        # Keep this map compact but useful for Iranian users
        currency_map = {
            "USD": "دلار آمریکا",
            "EUR": "یورو",
            "GBP": "پوند انگلیس",
            "AED": "درهم امارات",
            "TRY": "لیر ترکیه",
            "CNY": "یوان چین",
            "SAR": "ریال عربستان",
            "IQD": "دینار عراق",
            "AFN": "افغانی افغانستان",

            "BTC": "بیت کوین",
            "ETH": "اتریوم",
            "BNB": "بایننس کوین",
            "XRP": "ریپل",
            "SOL": "سولانا",
            "ADA": "کاردانو",
            "DOGE": "دوج کوین",

            "GOLD": "طلا",
            "SILVER": "نقره",
            "SEKEH": "سکه طلا",
            "GERAM18": "گرم طلای ۱۸ عیار",
            "GERAM24": "گرم طلای ۲۴ عیار",
            "MESGHAL": "مثقال طلا",
            "OUNCE": "اونس طلا",
        }
        return currency_map.get(symbol, symbol)

    @staticmethod
    def get_fallback_data() -> Dict[str, Dict[str, Any]]:
        now = time.time()
        return {
            "USD": {"symbol": "USD", "name": "دلار آمریکا", "price": "57250", "unit": "تومان", "change_percent": "1.24", "timestamp": now, "source": "fallback"},
            "EUR": {"symbol": "EUR", "name": "یورو", "price": "62180", "unit": "تومان", "change_percent": "-0.68", "timestamp": now, "source": "fallback"},
            "GBP": {"symbol": "GBP", "name": "پوند انگلیس", "price": "72340", "unit": "تومان", "change_percent": "2.15", "timestamp": now, "source": "fallback"},
            "BTC": {"symbol": "BTC", "name": "بیت کوین", "price": "97543", "unit": "USD", "change_percent": "3.45", "timestamp": now, "source": "fallback"},
            "ETH": {"symbol": "ETH", "name": "اتریوم", "price": "3892", "unit": "USD", "change_percent": "5.23", "timestamp": now, "source": "fallback"},
            "GOLD": {"symbol": "GOLD", "name": "طلا", "price": "2234", "unit": "USD/oz", "change_percent": "0.89", "timestamp": now, "source": "fallback"},
            "SEKEH": {"symbol": "SEKEH", "name": "سکه طلا", "price": "28500000", "unit": "تومان", "change_percent": "2.50", "timestamp": now, "source": "fallback"},
            "GERAM18": {"symbol": "GERAM18", "name": "گرم طلای ۱۸ عیار", "price": "2870000", "unit": "تومان", "change_percent": "1.80", "timestamp": now, "source": "fallback"},
        }

    # ---------------------------------------------------------------------
    # History (Crypto) via CoinGecko
    # ---------------------------------------------------------------------

    _COINGECKO_ID_MAP: Dict[str, str] = {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "BNB": "binancecoin",
        "ADA": "cardano",
        "SOL": "solana",
        "DOT": "polkadot",
        "DOGE": "dogecoin",
        "AVAX": "avalanche-2",
        "MATIC": "polygon",
        "LINK": "chainlink",
    }

    def fetch_crypto_history(self, symbol: str, *, period_seconds: int) -> List[Tuple[float, float]]:
        """Return (ts_seconds, price) points for supported crypto symbols."""
        sym = str(symbol or "").upper().strip()
        coin_id = self._COINGECKO_ID_MAP.get(sym)
        if not coin_id:
            return []

        # CoinGecko expects days; clamp to a reasonable range to keep it fast.
        try:
            days = int(max(1, min(90, math.ceil(float(period_seconds) / 86400.0))))
        except Exception:
            days = 1

        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
        params = {"vs_currency": "usd", "days": str(days), "interval": "hourly"}
        try:
            r = self.session.get(url, params=params, timeout=config.API_TIMEOUT, verify=config.VERIFY_SSL)
            if r.status_code != 200:
                return []
            payload = r.json() if r.content else {}
            prices = payload.get("prices") or []
            points: List[Tuple[float, float]] = []
            for item in prices:
                try:
                    ts_ms = float(item[0])
                    price = float(item[1])
                    points.append((ts_ms / 1000.0, price))
                except Exception:
                    continue
            return points
        except Exception:
            return []


# =============================================================================
# Visual Effects
# =============================================================================

class VisualEffectsManager:
    """Windows effects with safe fallbacks (no-op on non-Windows)."""

    def __init__(self, window: ctk.CTk):
        self.window = window
        self.current_effect = "normal"
        self.transparency_level = 1.0
        self.is_applying = False

    def reset_to_normal(self) -> None:
        try:
            if IS_WINDOWS and PYWINSTYLES_AVAILABLE:
                pywinstyles.apply_style(self.window, "normal")  # type: ignore[name-defined]
            self.window.attributes("-alpha", 1.0)
            self.window.update_idletasks()
            self.current_effect = "normal"
            self.transparency_level = 1.0
        except Exception:
            pass

    def apply_liquid_glass_effect(self) -> None:
        self._apply_windows_style(
            target="liquid_glass",
            candidates=[("acrylic", 0.97), ("mica", 0.96), ("blur", 0.95), ("aero", 0.94)],
            simulation_alpha=0.985,
        )

    def apply_vibrancy_effect(self) -> None:
        self._apply_windows_style(
            target="vibrancy",
            candidates=[("aero", 0.92), ("blur", 0.90)],
            simulation_alpha=0.985,
        )

    def apply_crystal_mode(self) -> None:
        self._apply_windows_style(
            target="crystal",
            candidates=[("optimised", 0.89), ("acrylic", 0.88), ("blur", 0.90)],
            simulation_alpha=0.985,
        )


    def apply_midnight_glow_effect(self) -> None:
        """A darker, punchier effect (pairs well with dark appearance mode)."""
        self._apply_windows_style(
            target="midnight",
            candidates=[("acrylic", 0.84), ("aero", 0.82), ("blur", 0.86)],
            simulation_alpha=0.92,
        )

    def apply_paper_mode(self) -> None:
        """Solid, clean look (no transparency / glass)."""
        if self.is_applying:
            return
        self.is_applying = True
        try:
            # reset_to_normal already clears styles on Windows + restores alpha
            self.reset_to_normal()
            try:
                self.window.attributes("-alpha", 1.0)
            except Exception:
                pass
            self.current_effect = "paper"
            self.transparency_level = 1.0
        finally:
            self.is_applying = False

    def apply_paper_noir_mode(self) -> None:
        """Dark solid look (paper style in dark mode)."""
        if self.is_applying:
            return
        self.is_applying = True
        try:
            self.reset_to_normal()
            try:
                self.window.attributes("-alpha", 1.0)
            except Exception:
                pass
            self.current_effect = "paper_noir"
            self.transparency_level = 1.0
        finally:
            self.is_applying = False


    def _apply_windows_style(
        self,
        target: str,
        candidates: Sequence[Tuple[str, float]],
        simulation_alpha: float,
    ) -> None:
        if self.is_applying:
            return

        self.is_applying = True
        try:
            self.reset_to_normal()

            if not (IS_WINDOWS and PYWINSTYLES_AVAILABLE):
                self.window.attributes("-alpha", simulation_alpha)
                self.current_effect = f"{target}_simulation"
                self.transparency_level = simulation_alpha
                return

            for style_name, alpha in candidates:
                try:
                    pywinstyles.apply_style(self.window, style_name)  # type: ignore[name-defined]
                    self.window.attributes("-alpha", alpha)
                    self.window.update_idletasks()
                    self.current_effect = target
                    self.transparency_level = alpha
                    return
                except Exception:
                    continue

            # fallback
            self.window.attributes("-alpha", simulation_alpha)
            self.current_effect = f"{target}_simulation"
            self.transparency_level = simulation_alpha
        finally:
            self.is_applying = False

    def get_current_effect_info(self) -> Dict[str, Any]:
        return {
            "effect": self.current_effect,
            "transparency": self.transparency_level,
            "supported": bool(IS_WINDOWS and PYWINSTYLES_AVAILABLE),
        }


# =============================================================================
# Performance
# =============================================================================

class PerformanceMonitor:
    def __init__(self):
        self.start_time = time.time()
        self.metrics = {
            "ui_updates": 0,
            "api_calls": 0,
            "cache_loads": 0,
            "errors": 0,
        }

    def inc(self, key: str) -> None:
        if key in self.metrics:
            self.metrics[key] += 1

    def report(self) -> Dict[str, Any]:
        runtime = max(0.001, time.time() - self.start_time)
        return {
            "runtime_seconds": runtime,
            "runtime_formatted": str(timedelta(seconds=int(runtime))),
            "metrics": dict(self.metrics),
            "ui_updates_per_min": self.metrics["ui_updates"] / (runtime / 60.0),
        }


performance_monitor = PerformanceMonitor()


# =============================================================================
# UI Components
# =============================================================================

class ToastManager:
    """Stackable toast notifications (top-right)."""

    def __init__(
        self,
        root: ctk.CTk,
        *,
        font_getter: Optional[Callable[[int, bool], Tuple[Any, ...]]] = None,
        rtl: bool = False,
    ):
        self.root = root
        self._toasts: List[ctk.CTkFrame] = []
        self.max_toasts = 3
        self.offset_x = 16
        self.offset_y = 16
        self.gap = 10

        self.font_getter = font_getter or (lambda size, bold=False: (config.FALLBACK_FONT, size, "bold") if bold else (config.FALLBACK_FONT, size))
        self.rtl = rtl

    def set_typography(
        self,
        *,
        font_getter: Optional[Callable[[int, bool], Tuple[Any, ...]]] = None,
        rtl: Optional[bool] = None,
    ) -> None:
        if font_getter is not None:
            self.font_getter = font_getter
        if rtl is not None:
            self.rtl = rtl

    def show(self, message: str, duration: int = 2800) -> None:
        try:
            toast = ctk.CTkFrame(
                self.root,
                fg_color=(colors.glass_overlay_light, colors.glass_overlay_dark),
                corner_radius=12,
                border_width=1,
                border_color=(colors.border_light, colors.border_dark),
            )
            label = ctk.CTkLabel(
                toast,
                text=message,
                font=self.font_getter(13, False),
                text_color=(colors.text_primary_light, colors.text_primary_dark),
                anchor="e" if self.rtl else "w",
                justify="right" if self.rtl else "left",
            )
            label.pack(padx=14, pady=10)

            self._toasts.append(toast)
            if len(self._toasts) > self.max_toasts:
                old = self._toasts.pop(0)
                try:
                    old.destroy()
                except Exception:
                    pass

            self._reposition()
            self.root.after(duration, lambda: self._dismiss(toast))
        except Exception as e:
            logger.debug(f"Toast failed: {e}")

    def _dismiss(self, toast: ctk.CTkFrame) -> None:
        try:
            if toast in self._toasts:
                self._toasts.remove(toast)
            toast.destroy()
        except Exception:
            pass
        self._reposition()

    def _reposition(self) -> None:
        try:
            for i, toast in enumerate(reversed(self._toasts)):
                toast.update_idletasks()
                w = toast.winfo_reqwidth()
                h = toast.winfo_reqheight()
                x = self.root.winfo_width() - w - self.offset_x
                y = self.offset_y + i * (h + self.gap)
                toast.place(x=x, y=y)
        except Exception:
            pass


class CurrencyCardWidget(ctk.CTkFrame):
    """Reusable currency card with fast update (no destroy/recreate)."""

    def __init__(
        self,
        parent: ctk.CTkBaseClass,
        *,
        on_remove: Optional[Callable[[str], None]] = None,
        show_remove: bool = False,
        font_getter: Optional[Callable[[int, bool], Tuple[Any, ...]]] = None,
        rtl: bool = False,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ):
        self._card_width = int(width or config.CARD_WIDTH)
        self._card_height = int(height or config.CARD_HEIGHT)

        super().__init__(
            parent,
            fg_color=(colors.glass_overlay_light, colors.glass_overlay_dark),
            corner_radius=16,
            border_width=1,
            border_color=(colors.border_light, colors.border_dark),
            width=self._card_width,
            height=self._card_height,
        )
        self.pack_propagate(False)

        self.symbol: str = ""
        self._on_remove = on_remove
        self._show_remove = show_remove

        self.font_getter = font_getter or (lambda size, bold=False: (config.FALLBACK_FONT, size, "bold") if bold else (config.FALLBACK_FONT, size))
        self.rtl = rtl

        # Header row
        self.header = ctk.CTkFrame(self, fg_color="transparent")
        self.header.pack(fill="x", padx=16, pady=(14, 6))

        badge_side = "right" if self.rtl else "left"
        name_side = "right" if self.rtl else "left"
        remove_side = "left" if self.rtl else "right"

        self.symbol_badge = ctk.CTkFrame(
            self.header,
            fg_color=(colors.accent_blue, colors.accent_blue),
            corner_radius=8,
            width=44,
            height=26,
        )
        self.symbol_badge.pack(side=badge_side)
        self.symbol_badge.pack_propagate(False)

        self.symbol_label = ctk.CTkLabel(
            self.symbol_badge,
            text="---",
            font=self.font_getter(10, True),
            text_color="white",
        )
        self.symbol_label.place(relx=0.5, rely=0.5, anchor="center")

        self.name_label = ctk.CTkLabel(
            self.header,
            text="",
            font=self.font_getter(14, True),
            text_color=(colors.text_primary_light, colors.text_primary_dark),
            anchor="e" if self.rtl else "w",
            justify="right" if self.rtl else "left",
            wraplength=int(self._card_width * 0.62),
        )
        self.name_label.pack(side=name_side, padx=(12, 8), fill="x", expand=True)

        self.remove_btn: Optional[ctk.CTkButton] = None
        if self._show_remove:
            self.remove_btn = ctk.CTkButton(
                self.header,
                text="✕",
                width=32,
                height=28,
                corner_radius=10,
                fg_color=(colors.separator_light, colors.separator_dark),
                hover_color=(colors.accent_orange, colors.accent_orange),
                text_color=(colors.text_primary_light, colors.text_primary_dark),
                border_width=1,
                border_color=(colors.border_light, colors.border_dark),
                command=self._remove_clicked,
            )
            self.remove_btn.pack(side=remove_side)

        # Price
        self.price_section = ctk.CTkFrame(self, fg_color="transparent")
        self.price_section.pack(fill="x", padx=16, pady=(0, 6))

        self.price_label = ctk.CTkLabel(
            self.price_section,
            text="—",
            font=self.font_getter(23, True),
            text_color=(colors.text_primary_light, colors.text_primary_dark),
            anchor="e" if self.rtl else "w",
        )
        self.price_label.pack(fill="x")

        self.unit_label = ctk.CTkLabel(
            self.price_section,
            text="",
            font=self.font_getter(11, False),
            text_color=(colors.text_tertiary_light, colors.text_tertiary_dark),
            anchor="e" if self.rtl else "w",
            justify="right" if self.rtl else "left",
        )
        self.unit_label.pack(fill="x", pady=(2, 0))

        # Change pill
        self.change_pill = ctk.CTkFrame(self, corner_radius=12, height=28)
        self.change_pill.pack(fill="x", padx=16, pady=(6, 12))
        self.change_pill.pack_propagate(False)

        self.change_label = ctk.CTkLabel(
            self.change_pill,
            text="",
            font=self.font_getter(12, True),
        )
        self.change_label.place(relx=0.5, rely=0.5, anchor="center")

        self._set_change(None)

    def set_typography(
        self,
        *,
        font_getter: Optional[Callable[[int, bool], Tuple[Any, ...]]] = None,
        rtl: Optional[bool] = None,
    ) -> None:
        if font_getter is not None:
            self.font_getter = font_getter
        if rtl is not None:
            self.rtl = rtl

        try:
            self.symbol_label.configure(font=self.font_getter(10, True))
            self.name_label.configure(
                font=self.font_getter(14, True),
                anchor="e" if self.rtl else "w",
                justify="right" if self.rtl else "left",
            )
            self.price_label.configure(font=self.font_getter(23, True), anchor="e" if self.rtl else "w")
            self.unit_label.configure(
                font=self.font_getter(11, False),
                anchor="e" if self.rtl else "w",
                justify="right" if self.rtl else "left",
            )
            self.change_label.configure(font=self.font_getter(12, True))
        except Exception:
            pass

    def _remove_clicked(self) -> None:
        if self._on_remove and self.symbol:
            self._on_remove(self.symbol)

    @staticmethod
    def _format_price(price: Any) -> str:
        try:
            val = float(price)
            if val >= 1_000_000_000:
                return f"{val/1_000_000_000:.2f}B"
            if val >= 1_000_000:
                return f"{val/1_000_000:.2f}M"
            if val >= 100_000:
                return f"{val:,.0f}"
            if val >= 1_000:
                return f"{val:,.2f}"
            if val >= 1:
                return f"{val:.4f}"
            return f"{val:.6f}"
        except Exception:
            s = str(price)
            return s[:12] + "…" if len(s) > 12 else s

    def _set_change(self, change_percent: Any) -> None:
        try:
            val = float(change_percent)
            if val > 0:
                self.change_pill.configure(fg_color=colors.accent_green)
                self.change_label.configure(text=f"↗ +{val:.2f}%", text_color="white")
            elif val < 0:
                self.change_pill.configure(fg_color=colors.accent_red)
                self.change_label.configure(text=f"↘ {val:.2f}%", text_color="white")
            else:
                self.change_pill.configure(fg_color=(colors.separator_light, colors.separator_dark))
                self.change_label.configure(text="0.00%", text_color=(colors.text_primary_light, colors.text_primary_dark))
        except Exception:
            self.change_pill.configure(fg_color=(colors.separator_light, colors.separator_dark))
            self.change_label.configure(text="N/A", text_color=(colors.text_primary_light, colors.text_primary_dark))

    def update_data(self, currency: Dict[str, Any]) -> None:
        sym = str(currency.get("symbol", "")).upper().strip()
        self.symbol = sym

        self.symbol_label.configure(text=sym[:4] if sym else "---")

        name = str(currency.get("name", sym or "Currency"))
        # Keep the UI stable; allow longer names but avoid stretching the header too much
        if len(name) > 36:
            name = name[:33] + "…"
        self.name_label.configure(text=name)

        self.price_label.configure(text=self._format_price(currency.get("price", "0")))
        self.unit_label.configure(text=str(currency.get("unit", "")))

        self._set_change(currency.get("change_percent", None))




# =============================================================================
# Desktop Widgets + History UI helpers
# =============================================================================

@dataclass
class DesktopWidgetConfig:
    widget_id: str
    widget_type: str = "price"  # price | movers | portfolio
    symbol: str = "USD"
    x: int = 80
    y: int = 80
    width: int = config.WIDGET_WIDTH
    height: int = config.WIDGET_HEIGHT
    opacity: float = config.WIDGET_DEFAULT_OPACITY

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "DesktopWidgetConfig":
        src = dict(d or {})
        return DesktopWidgetConfig(
            widget_id=str(src.get("widget_id") or uuid.uuid4().hex[:10]),
            widget_type=str(src.get("widget_type") or "price"),
            symbol=str(src.get("symbol") or "USD").upper().strip(),
            x=int(src.get("x") or 80),
            y=int(src.get("y") or 80),
            width=int(src.get("width") or config.WIDGET_WIDTH),
            height=int(src.get("height") or config.WIDGET_HEIGHT),
            opacity=float(src.get("opacity") or config.WIDGET_DEFAULT_OPACITY),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "widget_id": self.widget_id,
            "widget_type": self.widget_type,
            "symbol": self.symbol,
            "x": int(self.x),
            "y": int(self.y),
            "width": int(self.width),
            "height": int(self.height),
            "opacity": float(self.opacity),
        }


class DesktopWindowHelper:
    """Windows-only helper to pin a Tk window to the desktop (behind all apps)."""

    @staticmethod
    def is_supported() -> bool:
        return bool(IS_WINDOWS)

    @staticmethod
    def _get_workerw() -> Optional[int]:
        if not IS_WINDOWS:
            return None

        try:
            user32 = ctypes.windll.user32
            progman = user32.FindWindowW("Progman", None)
            if not progman:
                return None

            # Ask Progman to spawn a WorkerW behind the desktop icons
            result = ctypes.c_ulong()
            user32.SendMessageTimeoutW(
                progman,
                0x052C,
                0,
                0,
                0,
                1000,
                ctypes.byref(result),
            )

            workerw = ctypes.c_void_p()

            def enum_proc(hwnd, lparam):
                nonlocal workerw
                shell = user32.FindWindowExW(hwnd, 0, "SHELLDLL_DefView", None)
                if shell:
                    # Get the WorkerW behind the icons
                    w = user32.FindWindowExW(0, hwnd, "WorkerW", None)
                    if w:
                        workerw = ctypes.c_void_p(w)
                return True

            # EnumWindows callback
            cb_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            user32.EnumWindows(cb_type(enum_proc), 0)

            if workerw and workerw.value:
                return int(workerw.value)
            return int(progman)
        except Exception:
            return None

    @staticmethod
    def _set_toolwindow(hwnd: int) -> None:
        if not IS_WINDOWS:
            return
        try:
            user32 = ctypes.windll.user32
            GWL_EXSTYLE = -20
            WS_EX_TOOLWINDOW = 0x00000080
            WS_EX_APPWINDOW = 0x00040000
            WS_EX_NOACTIVATE = 0x08000000

            ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ex = ex | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
            ex = ex & ~WS_EX_APPWINDOW
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex)
        except Exception:
            pass

    @staticmethod
    def _send_to_bottom(hwnd: int) -> None:
        if not IS_WINDOWS:
            return
        try:
            user32 = ctypes.windll.user32
            HWND_BOTTOM = 1
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_NOACTIVATE = 0x0010
            SWP_SHOWWINDOW = 0x0040
            user32.SetWindowPos(hwnd, HWND_BOTTOM, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW)
        except Exception:
            pass

    @staticmethod
    def attach_to_desktop(hwnd: int) -> bool:
        """Re-parent the window to the desktop worker window and keep it behind other apps."""
        if not IS_WINDOWS:
            return False
        try:
            user32 = ctypes.windll.user32
            parent = DesktopWindowHelper._get_workerw()
            if not parent:
                return False
            DesktopWindowHelper._set_toolwindow(hwnd)
            user32.SetParent(hwnd, int(parent))
            DesktopWindowHelper._send_to_bottom(hwnd)
            return True
        except Exception:
            return False


    @staticmethod
    def is_desktop_foreground() -> bool:
        """Return True if foreground window is desktop (Progman/WorkerW/taskbar). Windows-only."""
        if not IS_WINDOWS:
            return True
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32

            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return True

            try:
                shell_hwnd = user32.GetShellWindow()
                if shell_hwnd and int(hwnd) == int(shell_hwnd):
                    return True
            except Exception:
                pass

            buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(wintypes.HWND(hwnd), buf, 256)
            cls = (buf.value or "").strip()

            return cls in {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}
        except Exception:
            return True


class WinTrayIcon:
    """Minimal Windows tray icon (no external dependencies)."""

    def __init__(self, app: Any):
        self.app = app
        self._thread: Optional[threading.Thread] = None
        self._hwnd: Optional[int] = None
        self._running = False
        self._msg_id = 0x400 + 91
        self._icon_added = False

    def start(self) -> None:
        if not IS_WINDOWS:
            return
        if self._thread and self._thread.is_alive():
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, name="TrayIcon", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if not IS_WINDOWS:
            return
        self._running = False
        try:
            if self._hwnd:
                ctypes.windll.user32.PostMessageW(int(self._hwnd), 0x0010, 0, 0)  # WM_CLOSE
        except Exception:
            pass

    def show_icon(self) -> None:
        self._add_icon()

    def hide_icon(self) -> None:
        self._remove_icon()

    def _run_loop(self) -> None:
        if not IS_WINDOWS:
            return

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        # Set WinAPI signatures (prevents 64-bit overflow issues in callbacks)
        try:
            from ctypes import wintypes as _w
            if not hasattr(_w, "LRESULT"):
                _w.LRESULT = ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long

            PTR_SIZE = ctypes.sizeof(ctypes.c_void_p)
            WPARAM_T = ctypes.c_uint64 if PTR_SIZE == 8 else ctypes.c_uint32
            LPARAM_T = ctypes.c_int64 if PTR_SIZE == 8 else ctypes.c_int32
            LRESULT_T = ctypes.c_int64 if PTR_SIZE == 8 else ctypes.c_int32

            user32.DefWindowProcW.argtypes = [_w.HWND, _w.UINT, WPARAM_T, LPARAM_T]
            user32.DefWindowProcW.restype = LRESULT_T

            user32.CreatePopupMenu.argtypes = []
            user32.CreatePopupMenu.restype = _w.HMENU

            user32.AppendMenuW.argtypes = [_w.HMENU, _w.UINT, _w.UINT_PTR, _w.LPCWSTR]
            user32.AppendMenuW.restype = _w.BOOL

            user32.TrackPopupMenu.argtypes = [_w.HMENU, _w.UINT, _w.INT, _w.INT, _w.INT, _w.HWND, _w.LPCRECT]
            user32.TrackPopupMenu.restype = _w.UINT

            user32.DestroyMenu.argtypes = [_w.HMENU]
            user32.DestroyMenu.restype = _w.BOOL

            user32.GetCursorPos.argtypes = [ctypes.c_void_p]
            user32.GetCursorPos.restype = _w.BOOL

            user32.SetForegroundWindow.argtypes = [_w.HWND]
            user32.SetForegroundWindow.restype = _w.BOOL

            user32.PostQuitMessage.argtypes = [ctypes.c_int]
            user32.PostQuitMessage.restype = None
        except Exception:
            pass
        from ctypes import wintypes

        # Compatibility: some Python/Windows builds omit these aliases in ctypes.wintypes
        if not hasattr(wintypes, "HCURSOR"):
            wintypes.HCURSOR = wintypes.HANDLE
        if not hasattr(wintypes, "HICON"):
            wintypes.HICON = wintypes.HANDLE
        if not hasattr(wintypes, "LRESULT"):
            wintypes.LRESULT = ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long

        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        WM_DESTROY = 0x0002
        WM_COMMAND = 0x0111
        WM_RBUTTONUP = 0x0205
        WM_LBUTTONDBLCLK = 0x0203

        IDM_SHOW = 1001
        IDM_EXIT = 1002

        PTR_SIZE = ctypes.sizeof(ctypes.c_void_p)
        WPARAM_T = ctypes.c_uint64 if PTR_SIZE == 8 else ctypes.c_uint32
        LPARAM_T = ctypes.c_int64 if PTR_SIZE == 8 else ctypes.c_int32
        LRESULT_T = ctypes.c_int64 if PTR_SIZE == 8 else ctypes.c_int32

        WNDPROCTYPE = ctypes.WINFUNCTYPE(LRESULT_T, wintypes.HWND, wintypes.UINT, WPARAM_T, LPARAM_T)

        @WNDPROCTYPE
        def wndproc(hwnd, msg, wparam, lparam):
            try:
                if msg == self._msg_id:
                    lp = int(lparam) if lparam else 0
                    if lp == WM_LBUTTONDBLCLK:
                        try:
                            self.app._enqueue_ui(self.app._show_from_tray)
                        except Exception:
                            pass
                        return 0

                    if lp == WM_RBUTTONUP:
                        try:
                            menu = user32.CreatePopupMenu()
                            show_label = "باز کردن" if getattr(self.app, "language", "fa") == "fa" else "Open"
                            exit_label = "خروج" if getattr(self.app, "language", "fa") == "fa" else "Exit"
                            user32.AppendMenuW(menu, 0, IDM_SHOW, show_label)
                            user32.AppendMenuW(menu, 0, IDM_EXIT, exit_label)

                            pt = POINT()
                            user32.GetCursorPos(ctypes.byref(pt))
                            user32.SetForegroundWindow(hwnd)
                            cmd = user32.TrackPopupMenu(menu, 0x0100 | 0x0002, pt.x, pt.y, 0, hwnd, None)
                            user32.DestroyMenu(menu)

                            if cmd == IDM_SHOW:
                                self.app._enqueue_ui(self.app._show_from_tray)
                            elif cmd == IDM_EXIT:
                                self.app._enqueue_ui(self.app._exit_from_tray)
                        except Exception:
                            pass
                        return 0

                if msg == WM_COMMAND:
                    return 0

                if msg == WM_DESTROY:
                    try:
                        self._remove_icon()
                    except Exception:
                        pass
                    try:
                        user32.PostQuitMessage(0)
                    except Exception:
                        pass
                    return 0
            except Exception:
                pass

            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        hinst = kernel32.GetModuleHandleW(None)
        cls_name = f"LiquidGheymatTray_{os.getpid()}"

        class WNDCLASSW(ctypes.Structure):
            _fields_ = [
                ("style", wintypes.UINT),
                ("lpfnWndProc", WNDPROCTYPE),
                ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int),
                ("hInstance", wintypes.HINSTANCE),
                ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HCURSOR),
                ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR),
                ("lpszClassName", wintypes.LPCWSTR),
            ]

        wc = WNDCLASSW()
        wc.style = 0
        wc.lpfnWndProc = wndproc
        wc.cbClsExtra = 0
        wc.cbWndExtra = 0
        wc.hInstance = hinst
        wc.hIcon = user32.LoadIconW(None, 32512)  # IDI_APPLICATION
        wc.hCursor = None
        wc.hbrBackground = None
        wc.lpszMenuName = None
        wc.lpszClassName = cls_name

        try:
            user32.RegisterClassW(ctypes.byref(wc))
        except Exception:
            pass

        hwnd = user32.CreateWindowExW(0, cls_name, cls_name, 0, 0, 0, 0, 0, 0, 0, hinst, None)
        self._hwnd = int(hwnd) if hwnd else None

        msg = wintypes.MSG()
        while self._running and user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) != 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        try:
            if hwnd:
                user32.DestroyWindow(hwnd)
        except Exception:
            pass
        try:
            user32.UnregisterClassW(cls_name, hinst)
        except Exception:
            pass

    def _add_icon(self) -> None:
        if not IS_WINDOWS:
            return
        if self._icon_added:
            return
        hwnd = self._hwnd
        if not hwnd:
            return

        shell32 = ctypes.windll.shell32
        user32 = ctypes.windll.user32

        class NOTIFYICONDATAW(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_uint),
                ("hWnd", ctypes.c_void_p),
                ("uID", ctypes.c_uint),
                ("uFlags", ctypes.c_uint),
                ("uCallbackMessage", ctypes.c_uint),
                ("hIcon", ctypes.c_void_p),
                ("szTip", ctypes.c_wchar * 128),
            ]

        NIM_ADD = 0x00000000
        NIF_MESSAGE = 0x00000001
        NIF_ICON = 0x00000002
        NIF_TIP = 0x00000004

        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = ctypes.c_void_p(int(hwnd))
        nid.uID = 1
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = self._msg_id
        nid.hIcon = user32.LoadIconW(None, 32512)

        tip = "Liquid Gheymat"
        try:
            tip = str(getattr(self.app, "config", config).APP_NAME)
        except Exception:
            pass
        nid.szTip = tip[:127]

        shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))
        self._icon_added = True

    def _remove_icon(self) -> None:
        if not IS_WINDOWS:
            return
        if not self._icon_added:
            return
        hwnd = self._hwnd
        if not hwnd:
            return

        shell32 = ctypes.windll.shell32

        class NOTIFYICONDATAW(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_uint),
                ("hWnd", ctypes.c_void_p),
                ("uID", ctypes.c_uint),
                ("uFlags", ctypes.c_uint),
                ("uCallbackMessage", ctypes.c_uint),
                ("hIcon", ctypes.c_void_p),
                ("szTip", ctypes.c_wchar * 128),
            ]

        NIM_DELETE = 0x00000002

        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = ctypes.c_void_p(int(hwnd))
        nid.uID = 1

        shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
        self._icon_added = False

class SparklineCanvas(tk.Canvas):
    """Tiny, fast chart without matplotlib."""

    def __init__(self, parent: Any, width: int = 520, height: int = 110):
        super().__init__(parent, width=width, height=height, highlightthickness=0, bd=0, relief="flat")
        self._values: List[float] = []
        self._padding = 8
        self._width = int(width)
        self._height = int(height)
        self._last_mode = None

    def _bg(self) -> str:
        mode = str(ctk.get_appearance_mode() or "").lower()
        if "dark" in mode:
            return colors.glass_overlay_dark
        return colors.glass_overlay_light

    def _fg(self) -> str:
        return colors.accent_blue

    def set_values(self, values: Sequence[float]) -> None:
        self._values = [float(v) for v in values if v is not None]
        self._redraw()

    def clear(self) -> None:
        self._values = []
        self.delete("all")
        self.configure(bg=self._bg())

    def _redraw(self) -> None:
        self.delete("all")
        self.configure(bg=self._bg())
        if len(self._values) < 2:
            return

        vals = self._values[-int(max(2, config.HISTORY_MAX_POINTS)) :]
        mn = min(vals)
        mx = max(vals)
        if mx - mn < 1e-9:
            mx = mn + 1.0

        w = self._width
        h = self._height
        pad = self._padding
        inner_w = max(10, w - 2 * pad)
        inner_h = max(10, h - 2 * pad)

        points = []
        n = len(vals)
        for i, v in enumerate(vals):
            x = pad + (i / (n - 1)) * inner_w
            # higher value -> higher on chart
            y = pad + (1.0 - (v - mn) / (mx - mn)) * inner_h
            points.append((x, y))

        # Draw polyline
        flat = []
        for x, y in points:
            flat.extend([x, y])
        try:
            self.create_line(*flat, fill=self._fg(), width=2, smooth=True)
        except Exception:
            self.create_line(*flat, fill=self._fg(), width=2)

        # Optional: baseline dots (subtle)
        try:
            self.create_oval(pad - 1, h - pad - 1, pad + 1, h - pad + 1, fill=self._fg(), outline="")
            self.create_oval(w - pad - 1, h - pad - 1, w - pad + 1, h - pad + 1, fill=self._fg(), outline="")
        except Exception:
            pass


class DesktopWidgetWindow(tk.Toplevel):
    """Borderless, lightweight desktop widget (Windows).
    - Rounded corners via transparentcolor (true rounded widget)
    - Interactive (drag/remove) when desktop is foreground
    - Hidden automatically when user switches to other apps (never overlays apps)
    """

    _DESKTOP_CHECK_MS = 420
    _DATA_TICK_MS = 900

    def __init__(
        self,
        app: Any,
        cfg: DesktopWidgetConfig,
        *,
        on_remove: Callable[[str], None],
        on_moved: Optional[Callable[[DesktopWidgetConfig], None]] = None,
    ):
        super().__init__(app)

        self.app = app
        self.cfg = cfg
        self._on_remove = on_remove
        self._on_moved = on_moved

        self._drag_dx = 0
        self._drag_dy = 0
        self._dragging = False

        self._transparent_key = "#ff00ff"  # magenta; used as transparent background on Windows
        self._last_sig: Optional[str] = None
        self._render_cache: Dict[str, Any] = {}

        self.overrideredirect(True)

        try:
            self.attributes("-topmost", False)
        except Exception:
            pass

        try:
            self.attributes("-alpha", float(self.cfg.opacity))
        except Exception:
            pass

        self.geometry(f"{int(self.cfg.width)}x{int(self.cfg.height)}+{int(self.cfg.x)}+{int(self.cfg.y)}")
        self.configure(bg=self._transparent_key)

        # True rounded widget: remove square window corners
        if IS_WINDOWS:
            try:
                self.wm_attributes("-transparentcolor", self._transparent_key)
            except Exception:
                pass

        self.canvas = tk.Canvas(self, highlightthickness=0, bd=0, relief="flat", bg=self._transparent_key)
        self.canvas.pack(fill="both", expand=True)

        # Bindings
        self.canvas.bind("<ButtonPress-1>", self._on_drag_start)
        self.canvas.bind("<B1-Motion>", self._on_drag_move)
        self.canvas.bind("<ButtonRelease-1>", self._on_drag_end)

        self.canvas.tag_bind("remove_dot", "<Button-1>", self._remove_clicked)
        self.canvas.tag_bind("remove_dot", "<Enter>", lambda e: self.canvas.configure(cursor="hand2"))
        self.canvas.tag_bind("remove_dot", "<Leave>", lambda e: self.canvas.configure(cursor=""))

        self.bind("<Configure>", lambda e: self._redraw(force=True))

        self._redraw(force=True)

        # Window tweaks + periodic ticks
        self.after(60, self._setup_widget_window)

    def _setup_widget_window(self) -> None:
        if IS_WINDOWS:
            try:
                hwnd = int(self.winfo_id())
                DesktopWindowHelper._set_toolwindow(hwnd)
            except Exception:
                pass

        # Immediate data paint (no waiting for next app refresh)
        try:
            currencies = getattr(self.app, "currencies", {}) or {}
            if not currencies:
                try:
                    currencies = db_manager.load_cached_currencies()
                except Exception:
                    currencies = {}
            self.update_from_data(currencies)
        except Exception:
            pass

        self._desktop_visibility_tick()
        self._data_tick()

    def _rounded_rect(self, x1: float, y1: float, x2: float, y2: float, r: float, *, fill: str, outline: str, width: int) -> None:
        r = max(0.0, min(r, (x2 - x1) / 2.0, (y2 - y1) / 2.0))

        # fill
        self.canvas.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline="")
        self.canvas.create_rectangle(x1, y1 + r, x2, y2 - r, fill=fill, outline="")
        self.canvas.create_arc(x1, y1, x1 + 2 * r, y1 + 2 * r, start=90, extent=90, fill=fill, outline="")
        self.canvas.create_arc(x2 - 2 * r, y1, x2, y1 + 2 * r, start=0, extent=90, fill=fill, outline="")
        self.canvas.create_arc(x1, y2 - 2 * r, x1 + 2 * r, y2, start=180, extent=90, fill=fill, outline="")
        self.canvas.create_arc(x2 - 2 * r, y2 - 2 * r, x2, y2, start=270, extent=90, fill=fill, outline="")

        # outline
        if width > 0:
            self.canvas.create_arc(x1, y1, x1 + 2 * r, y1 + 2 * r, start=90, extent=90, style="arc", outline=outline, width=width)
            self.canvas.create_arc(x2 - 2 * r, y1, x2, y1 + 2 * r, start=0, extent=90, style="arc", outline=outline, width=width)
            self.canvas.create_arc(x1, y2 - 2 * r, x1 + 2 * r, y2, start=180, extent=90, style="arc", outline=outline, width=width)
            self.canvas.create_arc(x2 - 2 * r, y2 - 2 * r, x2, y2, start=270, extent=90, style="arc", outline=outline, width=width)
            self.canvas.create_line(x1 + r, y1, x2 - r, y1, fill=outline, width=width)
            self.canvas.create_line(x1 + r, y2, x2 - r, y2, fill=outline, width=width)
            self.canvas.create_line(x1, y1 + r, x1, y2 - r, fill=outline, width=width)
            self.canvas.create_line(x2, y1 + r, x2, y2 - r, fill=outline, width=width)

    def _redraw(self, *, force: bool = False) -> None:
        w = int(self.winfo_width() or self.cfg.width or config.WIDGET_WIDTH)
        h = int(self.winfo_height() or self.cfg.height or config.WIDGET_HEIGHT)

        self.canvas.delete("all")

        try:
            pal = self.app._widget_palette()
        except Exception:
            pal = {
                "bg": "#0a0a0c",
                "fill": "#151518",
                "border": "#2c2c2e",
                "txt": "#f5f5f7",
                "sub": "#a1a1a6",
                "dot": "#1c1c1e",
                "shine": "#7DA7FF",
            }

        fill = pal.get("fill", "#151518")
        border = pal.get("border", "#2c2c2e")
        txt = pal.get("txt", "#f5f5f7")
        sub = pal.get("sub", "#a1a1a6")

        # Single rounded widget surface (no outer sharp box)
        self._rounded_rect(0, 0, w, h, 20, fill=fill, outline=border, width=1)

        # Glass shine hint
        try:
            shine = pal.get("shine", "#7DA7FF")
            self.canvas.create_line(18, 14, w - 18, 14, fill=shine, width=1)
        except Exception:
            pass

        # Remove dot (top-right)
        dot_r = 10
        cx = w - 18
        cy = 18
        dot_fill = pal.get("dot", "#1c1c1e")
        self.canvas.create_oval(cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r, fill=dot_fill, outline=border, width=1, tags=("remove_dot",))
        self.canvas.create_text(cx, cy + 0.5, text="●", fill=txt, font=self.app._ui_font(12, True), tags=("remove_dot",))

        # Content
        t = str(self.cfg.widget_type or "price").lower().strip()
        padx = 18
        y = 36

        if t == "movers":
            title = self.app._t("widget_type_movers")
            self.canvas.create_text(padx, y, text=title, fill=txt, anchor="nw", font=self.app._ui_font(13, True))
            y += 26

            gainers = self._render_cache.get("gainers", [])
            losers = self._render_cache.get("losers", [])

            left_x = padx
            right_x = w / 2 + 6

            self.canvas.create_text(left_x, y, text=self.app._t("top_gainers"), fill=sub, anchor="nw", font=self.app._ui_font(11, True))
            self.canvas.create_text(right_x, y, text=self.app._t("top_losers"), fill=sub, anchor="nw", font=self.app._ui_font(11, True))
            y += 20

            lines = max(len(gainers), len(losers), 3)
            for i in range(lines):
                g = gainers[i] if i < len(gainers) else ("—", 0.0)
                l = losers[i] if i < len(losers) else ("—", 0.0)
                self.canvas.create_text(left_x, y + i * 18, text=f"{g[0]}  {g[1]:+.2f}%", fill=txt, anchor="nw", font=self.app._ui_font(11, False))
                self.canvas.create_text(right_x, y + i * 18, text=f"{l[0]}  {l[1]:+.2f}%", fill=txt, anchor="nw", font=self.app._ui_font(11, False))
            return

        if t == "portfolio":
            title = self.app._t("widget_type_portfolio")
            self.canvas.create_text(padx, y, text=title, fill=txt, anchor="nw", font=self.app._ui_font(13, True))
            y += 28

            total = int(self._render_cache.get("total", 0) or 0)
            best = self._render_cache.get("best", ("—", 0.0))
            worst = self._render_cache.get("worst", ("—", 0.0))
            upd = self._render_cache.get("updated", "—")

            self.canvas.create_text(padx, y, text=f"{self.app._t('portfolio_items')}: {total}", fill=txt, anchor="nw", font=self.app._ui_font(12, False))
            y += 22
            self.canvas.create_text(padx, y, text=f"{self.app._t('best')}: {best[0]}  {float(best[1]):+.2f}%", fill=sub, anchor="nw", font=self.app._ui_font(11, False))
            y += 18
            self.canvas.create_text(padx, y, text=f"{self.app._t('worst')}: {worst[0]}  {float(worst[1]):+.2f}%", fill=sub, anchor="nw", font=self.app._ui_font(11, False))
            y += 24
            self.canvas.create_text(padx, y, text=f"{self.app._t('updated')}: {upd}", fill=sub, anchor="nw", font=self.app._ui_font(10, False))
            return

        # price
        sym = str(self.cfg.symbol or "USD").upper().strip()
        title = f"{self.app._t('widget_type_price')}: {sym}"
        self.canvas.create_text(padx, y, text=title, fill=txt, anchor="nw", font=self.app._ui_font(13, True))
        y += 30

        price_str = self._render_cache.get("price_str", "—")
        change_str = self._render_cache.get("change_str", "")
        unit = self._render_cache.get("unit", self.app._t("toman"))

        self.canvas.create_text(padx, y, text=f"{price_str} {unit}", fill=txt, anchor="nw", font=self.app._ui_font(18, True))
        y += 28
        if change_str:
            self.canvas.create_text(padx, y, text=change_str, fill=sub, anchor="nw", font=self.app._ui_font(12, False))

    def _remove_clicked(self, _event=None) -> None:
        try:
            if callable(self._on_remove):
                self._on_remove(str(self.cfg.widget_id))
        finally:
            try:
                self.destroy()
            except Exception:
                pass

    def _on_drag_start(self, event) -> None:
        # Ignore if click was on remove dot
        try:
            x, y = int(event.x), int(event.y)
            w = int(self.winfo_width() or self.cfg.width or config.WIDGET_WIDTH)
            if x >= w - 32 and y <= 32:
                return
        except Exception:
            pass

        self._dragging = True
        try:
            self._drag_dx = int(event.x)
            self._drag_dy = int(event.y)
        except Exception:
            self._drag_dx = 0
            self._drag_dy = 0

    def _on_drag_move(self, event) -> None:
        if not self._dragging:
            return
        try:
            x = int(self.winfo_x() + (event.x - self._drag_dx))
            y = int(self.winfo_y() + (event.y - self._drag_dy))
            self.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def _on_drag_end(self, _event=None) -> None:
        if not self._dragging:
            return
        self._dragging = False

        try:
            self.cfg.x = int(self.winfo_x())
            self.cfg.y = int(self.winfo_y())
        except Exception:
            return

        try:
            if callable(self._on_moved):
                self._on_moved(self.cfg)
        except Exception:
            pass

    def _desktop_visibility_tick(self) -> None:
        if not IS_WINDOWS:
            return

        try:
            on_desktop = DesktopWindowHelper.is_desktop_foreground()
        except Exception:
            on_desktop = True

        if on_desktop:
            try:
                if str(self.state()) == "withdrawn":
                    self.deiconify()
            except Exception:
                pass

            # Keep above wallpaper/icons but never overlay apps (we hide when apps are focused)
            try:
                self.attributes("-topmost", True)
                self.after(30, lambda: self.attributes("-topmost", False))
            except Exception:
                pass
        else:
            # Keep the widget behind other windows. It will naturally disappear when apps are in front.
            try:
                self.attributes("-topmost", False)
            except Exception:
                pass
            if IS_WINDOWS:
                try:
                    hwnd = int(self.winfo_id())
                    DesktopWindowHelper._send_to_bottom(hwnd)
                except Exception:
                    pass

        self.after(self._DESKTOP_CHECK_MS, self._desktop_visibility_tick)

    def _data_tick(self) -> None:
        try:
            currencies = getattr(self.app, "currencies", {}) or {}
        except Exception:
            currencies = {}

        try:
            t = str(self.cfg.widget_type or "price").lower().strip()
            sig = f"{t}|lang:{getattr(self.app,'language','fa')}"
            if t == "price":
                sym = str(self.cfg.symbol or "").upper().strip()
                d = currencies.get(sym) or {}
                sig = f"price|{sym}|{d.get('price')}|{d.get('change_percent')}|{d.get('unit')}|lang:{getattr(self.app, 'language', 'fa')}"
            elif t == "movers":
                sig = f"movers|{getattr(self.app,'top_gainers',None)}|{getattr(self.app,'top_losers',None)}"
            elif t == "portfolio":
                sig = f"portfolio|{sorted(list(getattr(self.app,'user_portfolio',set()) or []))}|{getattr(self.app,'last_update','')}"
        except Exception:
            sig = None

        if sig is not None and sig != self._last_sig:
            self._last_sig = sig
            try:
                self.update_from_data(currencies)
            except Exception:
                pass

        self.after(self._DATA_TICK_MS, self._data_tick)

    def apply_typography(self) -> None:
        """Re-apply fonts + refresh rendered strings (language/unit labels)"""
        try:
            # Force signature refresh so periodic ticks won't early-exit
            self._last_sig = None
        except Exception:
            pass

        # Refresh cache using current app data so language-dependent labels update immediately
        try:
            cur = getattr(self.app, "currencies", None)
            if isinstance(cur, dict):
                self.update_from_data(cur)
                return
        except Exception:
            pass

        self._redraw(force=True)

    def update_from_data(self, currencies: Dict[str, Dict[str, Any]]) -> None:
        t = str(self.cfg.widget_type or "price").lower().strip()

        if t == "movers":
            gainers = list(getattr(self.app, "top_gainers", []) or [])[:3]
            losers = list(getattr(self.app, "top_losers", []) or [])[:3]
            self._render_cache["gainers"] = [(g[0], float(g[1])) for g in gainers] if gainers else []
            self._render_cache["losers"] = [(l[0], float(l[1])) for l in losers] if losers else []
            self._redraw()
            return

        if t == "portfolio":
            items = list(getattr(self.app, "user_portfolio", set()) or [])
            total = len(items)
            best = ("—", 0.0)
            worst = ("—", 0.0)
            for sym in items:
                d = currencies.get(str(sym).upper().strip()) or {}
                try:
                    ch = float(d.get("change_percent", 0) or 0)
                except Exception:
                    ch = 0.0
                if best[0] == "—" or ch > best[1]:
                    best = (str(sym).upper().strip(), ch)
                if worst[0] == "—" or ch < worst[1]:
                    worst = (str(sym).upper().strip(), ch)

            self._render_cache["total"] = total
            self._render_cache["best"] = best
            self._render_cache["worst"] = worst
            self._render_cache["updated"] = getattr(self.app, "last_update", "—")
            self._redraw()
            return

        # price
        sym = str(self.cfg.symbol or "").upper().strip()
        d = currencies.get(sym) or {}
        price_str = "—"
        raw_unit = d.get("unit") or ""
        try:
            unit = self.app._unit_display(raw_unit) if raw_unit else self.app._t("toman")
        except Exception:
            unit = raw_unit or self.app._t("toman")
        try:
            price_str = CurrencyCardWidget._format_price(float(d.get("price", 0) or 0))
        except Exception:
            pass
        ch_str = ""
        try:
            ch = float(d.get("change_percent", 0) or 0)
            if abs(ch) > 1e-9:
                ch_str = f"{ch:+.2f}%"
        except Exception:
            pass

        self._render_cache["price_str"] = price_str
        self._render_cache["change_str"] = ch_str
        self._render_cache["unit"] = unit
        self._redraw()

    def apply_typography(self) -> None:
        try:
            self._last_sig = None
        except Exception:
            pass
        self._redraw(force=True)

class DesktopWidgetManager:
    def __init__(self, app: Any):
        self.app = app
        self.widgets: Dict[str, DesktopWidgetWindow] = {}
        self._restore_done = False

    def restore(self) -> None:
        if self._restore_done:
            return
        self._restore_done = True

        if not DesktopWindowHelper.is_supported():
            return

        try:
            saved = db_manager.load_desktop_widgets()
            for item in saved:
                cfg = DesktopWidgetConfig.from_dict(item)
                self._create(cfg, save=False)
        except Exception:
            pass

    def shutdown(self) -> None:
        for wid in list(self.widgets.keys()):
            try:
                self.remove(wid, save=False)
            except Exception:
                pass

    def _create(self, cfg: DesktopWidgetConfig, *, save: bool) -> None:
        wid = str(cfg.widget_id or uuid.uuid4().hex[:10])
        cfg.widget_id = wid

        try:
            win = DesktopWidgetWindow(self.app, cfg, on_remove=self.remove, on_moved=self._on_widget_moved)
            self.widgets[wid] = win
            if save:
                db_manager.save_desktop_widget(wid, cfg.to_dict())
        except Exception:
            return

        # Update the UI list if present
        try:
            if hasattr(self.app, "_refresh_widgets_ui"):
                self.app._refresh_widgets_ui()
        except Exception:
            pass

    def add(self, widget_type: str, symbol: str = "USD") -> None:
        if not DesktopWindowHelper.is_supported():
            try:
                self.app.toasts.show(self.app._t("toast_widget_not_supported"), duration=2600)
            except Exception:
                pass
            return

        base_x = 80 + (len(self.widgets) % 6) * 40
        base_y = 80 + (len(self.widgets) % 6) * 30

        cfg = DesktopWidgetConfig(
            widget_id=uuid.uuid4().hex[:10],
            widget_type=str(widget_type or "price"),
            symbol=str(symbol or "USD").upper().strip(),
            x=base_x,
            y=base_y,
        )
        self._create(cfg, save=True)
        try:
            self.app.toasts.show(self.app._t("toast_widget_added"), duration=1800)
        except Exception:
            pass

    def remove(self, widget_id: str, *, save: bool = True) -> None:
        wid = str(widget_id or "").strip()
        if not wid:
            return
        win = self.widgets.pop(wid, None)
        if win is not None:
            try:
                win.destroy()
            except Exception:
                pass
        if save:
            try:
                db_manager.delete_desktop_widget(wid)
            except Exception:
                pass
            try:
                self.app.toasts.show(self.app._t("toast_widget_removed"), duration=1800)
            except Exception:
                pass

        try:
            if hasattr(self.app, "_refresh_widgets_ui"):
                self.app._refresh_widgets_ui()
        except Exception:
            pass

    def _on_widget_moved(self, cfg: DesktopWidgetConfig) -> None:
        try:
            db_manager.save_desktop_widget(cfg.widget_id, cfg.to_dict())
        except Exception:
            pass

    def update_all(self, currencies: Dict[str, Dict[str, Any]]) -> None:
        for win in list(self.widgets.values()):
            try:
                win.update_from_data(currencies)
            except Exception:
                continue

    def apply_typography(self) -> None:
        for win in list(self.widgets.values()):
            try:
                win.apply_typography()
            except Exception:
                continue

    def get_summaries(self) -> List[str]:
        out: List[str] = []
        for wid, w in self.widgets.items():
            try:
                t = str(w.cfg.widget_type)
                if t == "price":
                    out.append(f"{wid} • {w.cfg.symbol}")
                elif t == "movers":
                    out.append(f"{wid} • movers")
                elif t == "portfolio":
                    out.append(f"{wid} • portfolio")
                else:
                    out.append(f"{wid} • {t}")
            except Exception:
                out.append(wid)
        return out



# =============================================================================
# Main App
# =============================================================================

class LiquidGlassPriceTracker(ctk.CTk):
    def __init__(self):
        super().__init__()

        # ---------------------------------------------------------------------
        # Language / layout defaults
        # ---------------------------------------------------------------------
        self.language: str = "en"
        self.rtl: bool = False

        # Typography (resolved at runtime; helps packaged builds where font family names can vary)
        self._primary_font_family: str = config.PRIMARY_FONT or config.FALLBACK_FONT
        self._persian_font_family: str = config.PERSIAN_FONT or config.FALLBACK_FONT

        # Responsive grid (featured + portfolio)
        self.grid_columns: int = int(max(2, min(config.GRID_COLUMNS, 4)))
        self._resize_after_id: Optional[str] = None

        # Managers
        self.api_manager = APIManager()
        self.effects_manager = VisualEffectsManager(self)
        self.executor = ThreadPoolExecutor(max_workers=config.MAX_WORKER_THREADS)
        self.toasts = ToastManager(self, font_getter=self._ui_font, rtl=self.rtl)
        self.widget_manager = DesktopWidgetManager(self)

        # State
        self.currencies: Dict[str, Dict[str, Any]] = {}
        self.user_portfolio: set[str] = set()
        self.featured_symbols: List[str] = []

        self.connection_status: ConnectionStatus = ConnectionStatus.DISCONNECTED
        self.last_update: str = "—"

        # Preferences (defaults)
        self.selected_theme: str = "liquid_glass"
        self.auto_refresh_active: bool = True
        self.refresh_interval_seconds: int = config.DEFAULT_REFRESH_INTERVAL
        self.alerts_enabled: bool = True
        self.alert_threshold_percent: float = 2.5
        self.always_on_top: bool = False
        self.run_in_background: bool = False
        # Portfolio sort key: default | name | symbol | price | change
        self.portfolio_sort_mode_key: str = "default"

        # Internals
        self._auto_refresh_after_id: Optional[str] = None
        self._selector_update_after_id: Optional[str] = None
        self._last_seen_prices: Dict[str, float] = {}
        # Session tracking (for "Session Tracker" section)
        self._session_open: Dict[str, float] = {}
        self._session_min: Dict[str, float] = {}
        self._session_max: Dict[str, float] = {}
        self._last_alert_ts: Dict[str, float] = {}
        self._history_points: deque[Tuple[float, float]] = deque(maxlen=config.HISTORY_MAX_POINTS)
        self._history_symbol: str = "USD"
        self._history_period_seconds: int = 24 * 3600
        self._history_last_loaded: float = 0.0
        self._last_history_prune: float = 0.0

        self._converter_symbol_map: Dict[str, str] = {}
        self._converter_last_update: float = 0.0
        self._symbol_menu_sig: str = ""

        self._portfolio_filter_after_id: Optional[str] = None

        # UI refs
        self.ui_elements: Dict[str, Any] = {}
        self.theme_buttons: Dict[str, ctk.CTkButton] = {}
        self.featured_cards: Dict[str, CurrencyCardWidget] = {}
        self.portfolio_cards: Dict[str, CurrencyCardWidget] = {}

        # Extra UI refs (localization-friendly)
        self.toolbar_title_label: Optional[ctk.CTkLabel] = None
        self.language_var: Optional[ctk.StringVar] = None
        self.language_menu: Optional[ctk.CTkOptionMenu] = None
        self.always_on_top_var: Optional[ctk.BooleanVar] = None
        self.always_on_top_cb: Optional[ctk.CTkCheckBox] = None
        self.background_var: Optional[ctk.BooleanVar] = None
        self.background_cb: Optional[ctk.CTkCheckBox] = None
        self.window_options_label: Optional[ctk.CTkLabel] = None

        self.hero_title_label: Optional[ctk.CTkLabel] = None
        self.hero_subtitle_label: Optional[ctk.CTkLabel] = None
        self.hero_version_label: Optional[ctk.CTkLabel] = None

        self.featured_title_label: Optional[ctk.CTkLabel] = None
        self.insights_title_label: Optional[ctk.CTkLabel] = None
        self.portfolio_title_label: Optional[ctk.CTkLabel] = None
        self.history_title_label: Optional[ctk.CTkLabel] = None
        self.converter_title_label: Optional[ctk.CTkLabel] = None
        self.widgets_title_label: Optional[ctk.CTkLabel] = None
        self.controls_title_label: Optional[ctk.CTkLabel] = None
        self.settings_title_label: Optional[ctk.CTkLabel] = None
        self.theme_title_label: Optional[ctk.CTkLabel] = None

        self.gainers_title_label: Optional[ctk.CTkLabel] = None
        self.losers_title_label: Optional[ctk.CTkLabel] = None

        self.sort_label: Optional[ctk.CTkLabel] = None

        # New: portfolio filter
        self.portfolio_filter_var: Optional[ctk.StringVar] = None
        self.portfolio_filter_entry: Optional[ctk.CTkEntry] = None

        # New: history section
        self.history_symbol_var: Optional[ctk.StringVar] = None
        self.history_period_var: Optional[ctk.StringVar] = None
        self.history_symbol_menu: Optional[ctk.CTkOptionMenu] = None
        self.history_period_menu: Optional[ctk.CTkOptionMenu] = None
        self.history_sparkline: Optional[SparklineCanvas] = None
        self.history_stats_label: Optional[ctk.CTkLabel] = None

        # New: converter section
        self.converter_amount_var: Optional[ctk.StringVar] = None
        self.converter_from_var: Optional[ctk.StringVar] = None
        self.converter_to_var: Optional[ctk.StringVar] = None
        self.converter_result_label: Optional[ctk.CTkLabel] = None
        self.converter_from_menu: Optional[ctk.CTkOptionMenu] = None
        self.converter_to_menu: Optional[ctk.CTkOptionMenu] = None

        # New: widgets section
        self.widgets_type_var: Optional[ctk.StringVar] = None
        self.widgets_symbol_var: Optional[ctk.StringVar] = None
        self.widgets_type_menu: Optional[ctk.CTkOptionMenu] = None
        self.widgets_symbol_menu: Optional[ctk.CTkOptionMenu] = None
        self.widgets_active_list: Optional[ctk.CTkFrame] = None


        # Build
        self._setup_window()
        self._load_resources()
        self._resolve_font_families()

        # Load preferences early so the initial layout/text matches (language, RTL, interval, theme)
        self._load_saved_preferences()
        self.rtl = is_rtl(self.language)

        self._create_user_interface()
        self._bind_shortcuts()

        # Responsive layout
        try:
            self.bind("<Configure>", self._on_window_resize)
        except Exception:
            pass

        # Cached data (fast first paint) + apply language now that widgets exist
        self._apply_language()
        self._apply_grid_columns()
        self._load_cached_first_paint()

        # Apply theme + start data systems
        self.after(120, lambda: self._apply_theme_with_feedback(self.selected_theme, show_feedback=False, save_preference=False))
                # Thread-safe UI dispatch queue (used by worker threads)
        self._ui_task_queue: "queue.Queue[Callable[[], None]]" = queue.Queue()
        self._ui_queue_running = True
        self.after(50, self._drain_ui_task_queue)

        self._start_data_systems()

        # Restore desktop widgets (if any)
        self.after(950, self.widget_manager.restore)

        logger.info("App initialized.")


    # -------------------------------------------------------------------------
    # Window / resources
    # -------------------------------------------------------------------------

    def _setup_window(self) -> None:
        self.title(f"{config.APP_NAME} v{config.APP_VERSION}")
        self.geometry(f"{config.WINDOW_WIDTH}x{config.WINDOW_HEIGHT}")
        self.minsize(config.MIN_WIDTH, config.MIN_HEIGHT)
        self.resizable(True, True)

        # Theme baseline
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")
        self.configure(fg_color=(colors.bg_light, colors.bg_dark))

        # Icon
        icon_path = resource_manager.load_icon("assets/icons/icon.ico")
        if icon_path:
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

        try:
            self.protocol("WM_DELETE_WINDOW", self._on_close_requested)
            self.bind("<Unmap>", self._on_window_unmap)
            self._tray_icon = None
            if IS_WINDOWS:
                self._ensure_tray()
        except Exception:
            pass

        self.after(50, self._center_window)

    def _center_window(self) -> None:
        try:
            self.update_idletasks()
            w = self.winfo_width()
            h = self.winfo_height()
            x = (self.winfo_screenwidth() // 2) - (w // 2)
            y = (self.winfo_screenheight() // 2) - (h // 2)
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass

    def _ensure_tray(self) -> None:
        if not IS_WINDOWS:
            return
        try:
            if getattr(self, "_tray_icon", None) is None:
                self._tray_icon = WinTrayIcon(self)
                self._tray_icon.start()
        except Exception:
            pass

    def _hide_to_tray(self) -> None:
        if not IS_WINDOWS:
            try:
                self.iconify()
            except Exception:
                pass
            return
        self._ensure_tray()
        try:
            if getattr(self, "_tray_icon", None) is not None:
                self._tray_icon.show_icon()
                try:
                    self.after(200, self._tray_icon.show_icon)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            self.withdraw()
        except Exception:
            pass

    def _show_from_tray(self) -> None:
        try:
            self.deiconify()
        except Exception:
            pass
        try:
            self.lift()
            self.focus_force()
        except Exception:
            pass
        try:
            if getattr(self, "_tray_icon", None) is not None:
                self._tray_icon.hide_icon()
        except Exception:
            pass

    def _exit_from_tray(self) -> None:
        try:
            if getattr(self, "_tray_icon", None) is not None:
                self._tray_icon.hide_icon()
        except Exception:
            pass
        try:
            self.widget_manager.shutdown()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass

    def _on_window_unmap(self, event: Any = None) -> None:
        try:
            if not self.run_in_background:
                return
        except Exception:
            return
        try:
            if str(self.state()) == "iconic":
                self._hide_to_tray()
        except Exception:
            pass


    def _on_close_requested(self) -> None:
        """Close button behavior: either exit, or keep running (tray) for background updates + widgets."""
        if self.run_in_background:
            try:
                if IS_WINDOWS:
                    self._hide_to_tray()
                else:
                    self.iconify()
                self.toasts.show(self._t("toast_background_on"), duration=2200)
            except Exception:
                pass
            return

        try:
            try:
                if getattr(self, "_tray_icon", None) is not None:
                    self._tray_icon.hide_icon()
            except Exception:
                pass
            try:
                self.widget_manager.shutdown()
            except Exception:
                pass
            self.destroy()
        except Exception:
            pass

    def _load_resources(self) -> None:
        for fp in (
            "assets/fonts/Vazirmatn-Regular.ttf",
            "assets/fonts/SF-Pro-Display-Regular.ttf",
            "assets/fonts/Inter-Regular.ttf",
        ):
            resource_manager.load_font(fp)

    def _resolve_font_families(self) -> None:
        """Resolve real font family names available to Tk (helps packaged builds)."""
        try:
            import tkinter.font as tkfont  # local import to avoid overhead on startup
            fams = set(tkfont.families(self))
        except Exception:
            fams = set()

        def pick(preferred: Sequence[str], fallback: str) -> str:
            for name in preferred:
                if not name:
                    continue
                if name in fams:
                    return name

            # Case-insensitive exact match
            try:
                low_map = {f.lower(): f for f in fams}
                for name in preferred:
                    if not name:
                        continue
                    hit = low_map.get(name.lower())
                    if hit:
                        return hit
            except Exception:
                pass

            # Partial match (e.g., "Vazirmatn" vs "Vazirmatn Regular")
            for name in preferred:
                if not name:
                    continue
                nlow = str(name).lower()
                for f in fams:
                    if nlow in str(f).lower():
                        return f

            return fallback

        # Prefer bundled fonts when available, otherwise fall back gracefully
        self._persian_font_family = pick(
            [config.PERSIAN_FONT, "Vazirmatn", "Vazirmatn Regular", "Vazirmatn-Regular", "Vazir"],
            config.FALLBACK_FONT,
        )
        self._primary_font_family = pick(
            [config.PRIMARY_FONT, "Inter", "Segoe UI", config.FALLBACK_FONT],
            config.FALLBACK_FONT,
        )




    # -------------------------------------------------------------------------
    # Language / typography / responsive layout
    # -------------------------------------------------------------------------

    def _t(self, key: str, **kwargs) -> str:
        return tr(self.language, key, **kwargs)

    @staticmethod
    def _normalize_language(value: str) -> str:
        v = str(value or "").strip().lower()
        if v.startswith("fa") or v in {"فارسی", "persian", "farsi"}:
            return "fa"
        return "en"
    def _language_display(self, lang_key: str) -> str:
        """Return the display label for a language code, in the CURRENT UI language."""
        key = self._normalize_language(lang_key)
        if self.language == "fa":
            mapping = {"fa": "فارسی", "en": "انگلیسی"}
        else:
            mapping = {"fa": "Persian", "en": "English"}
        return mapping.get(key, "English")

    def _language_menu_values(self) -> List[str]:
        return [self._language_display("fa"), self._language_display("en")]

    def _display_to_language(self, display: str) -> str:
        d = str(display or "").strip().lower()
        # Accept both Persian and English labels (and tolerate minor variations)
        if d in {"fa", "فارسی", "farsi", "persian"}:
            return "fa"
        if d in {"en", "english", "انگلیسی"}:
            return "en"
        if d.startswith("fa") or "فارسی" in d:
            return "fa"
        if d.startswith("en") or "english" in d or "انگلیسی" in d:
            return "en"
        return "en"

    def _font_family(self) -> str:
        if self.language == "fa":
            return (getattr(self, "_persian_font_family", None) or config.PERSIAN_FONT or config.FALLBACK_FONT)
        # English
        return (getattr(self, "_primary_font_family", None) or config.PRIMARY_FONT or config.FALLBACK_FONT)

    def _ui_font(self, size: int, bold: bool = False) -> Tuple[Any, ...]:
        family = self._font_family()
        if bold:
            return (family, int(size), "bold")
        return (family, int(size))

    def _widget_palette(self) -> Dict[str, str]:
        """Colors for desktop widgets. Independent from app theme when user chooses."""
        key = str(getattr(self, "widget_theme", "auto") or "auto").strip().lower()

        # Base palettes (6-digit hex only for Tk canvas)
        palettes: Dict[str, Dict[str, str]] = {
            "glass_light": {
                "bg": "#f8f9fb",
                "fill": "#ffffff",
                "border": "#e7e7ee",
                "txt": "#1d1d1f",
                "sub": "#515154",
                "dot": "#f2f2f7",
                "shine": "#ffffff",
            },
            "glass_dark": {
                "bg": "#0a0a0c",
                "fill": "#151518",
                "border": "#2c2c2e",
                "txt": "#f5f5f7",
                "sub": "#a1a1a6",
                "dot": "#1c1c1e",
                "shine": "#9AB7FF",
            },
            "midnight": {
                "bg": "#07080c",
                "fill": "#0e1018",
                "border": "#232536",
                "txt": "#f2f4ff",
                "sub": "#a8afc6",
                "dot": "#141622",
                "shine": "#7DA7FF",
            },
            "paper": {
                "bg": "#ffffff",
                "fill": "#ffffff",
                "border": "#e9e9ef",
                "txt": "#111114",
                "sub": "#4a4a4f",
                "dot": "#f2f2f7",
                "shine": "#ffffff",
            },
            "paper_noir": {
                "bg": "#0b0b0d",
                "fill": "#0b0b0d",
                "border": "#2a2a2e",
                "txt": "#f5f5f7",
                "sub": "#a1a1a6",
                "dot": "#141416",
                "shine": "#d9d9de",
            },
        }

        if key == "auto":
            # Follow app appearance mode
            try:
                mode = str(ctk.get_appearance_mode() or "").lower()
                if "dark" in mode:
                    return palettes["glass_dark"]
            except Exception:
                pass
            return palettes["glass_light"]

        return palettes.get(key, palettes["glass_light"])


    # ----- currency localization -----

    _CURRENCY_NAME_MAP: Dict[str, Dict[str, str]] = {
        "USD": {"fa": "دلار آمریکا", "en": "US Dollar"},
        "EUR": {"fa": "یورو", "en": "Euro"},
        "GBP": {"fa": "پوند انگلیس", "en": "British Pound"},
        "AED": {"fa": "درهم امارات", "en": "UAE Dirham"},
        "TRY": {"fa": "لیر ترکیه", "en": "Turkish Lira"},
        "CNY": {"fa": "یوان چین", "en": "Chinese Yuan"},
        "JPY": {"fa": "ین ژاپن", "en": "Japanese Yen"},
        "RUB": {"fa": "روبل روسیه", "en": "Russian Ruble"},
        "CAD": {"fa": "دلار کانادا", "en": "Canadian Dollar"},
        "AUD": {"fa": "دلار استرالیا", "en": "Australian Dollar"},
        "CHF": {"fa": "فرانک سوئیس", "en": "Swiss Franc"},
        "USDT": {"fa": "تتر", "en": "Tether"},
        "BTC": {"fa": "بیت‌کوین", "en": "Bitcoin"},
        "ETH": {"fa": "اتریوم", "en": "Ethereum"},
        "BNB": {"fa": "بایننس‌کوین", "en": "BNB"},
        "SOL": {"fa": "سولانا", "en": "Solana"},
        "DOGE": {"fa": "دوج‌کوین", "en": "Dogecoin"},
        "ADA": {"fa": "کاردانو", "en": "Cardano"},
        "DOT": {"fa": "پولکادات", "en": "Polkadot"},
        "AVAX": {"fa": "آوالانچ", "en": "Avalanche"},
        "MATIC": {"fa": "پالیگان", "en": "Polygon"},
        "TRX": {"fa": "ترون", "en": "TRON"},
        "LTC": {"fa": "لایت‌کوین", "en": "Litecoin"},
        "XRP": {"fa": "ریپل", "en": "XRP"},
        "TON": {"fa": "تون", "en": "Toncoin"},
        "GOLD": {"fa": "طلای ۲۴ عیار", "en": "24K Gold"},
        "GERAM18": {"fa": "طلای ۱۸ عیار", "en": "18K Gold"},
        "SEKEH": {"fa": "سکه امامی", "en": "Emami Coin"},
        "NIM": {"fa": "نیم سکه", "en": "Half Coin"},
        "ROB": {"fa": "ربع سکه", "en": "Quarter Coin"},
        "SEK": {"fa": "سکه طرح قدیم", "en": "Old Coin"},
    }

    _UNIT_MAP_EN: Dict[str, str] = {
        "تومان": "Toman",
        "ریال": "Rial",
        "دلار": "Dollar",
        "یورو": "Euro",
        "پوند": "Pound",
        "درهم": "Dirham",
        "لیر": "Lira",
    }

    _UNIT_MAP_FA: Dict[str, str] = {
        "toman": "تومان",
        "rial": "ریال",
        "dollar": "دلار",
        "euro": "یورو",
        "pound": "پوند",
        "dirham": "درهم",
        "lira": "لیر",
    }

    @staticmethod
    def _has_persian_letters(text: str) -> bool:
        s = str(text or "")
        ranges = [
            ("؀", "ۿ"),
            ("ݐ", "ݿ"),
            ("ࢠ", "ࣿ"),
            ("ﭐ", "﷿"),
            ("ﹰ", "﻿"),
        ]
        for ch in s:
            for a, b in ranges:
                if a <= ch <= b:
                    return True
        return False

    @staticmethod
    def _has_latin_letters(text: str) -> bool:
        s = str(text or "")
        return any(("A" <= ch <= "Z") or ("a" <= ch <= "z") for ch in s)

    def _currency_display_name(self, sym: str, data: Optional[Dict[str, Any]] = None) -> str:
        symbol = str(sym or "").upper().strip()
        data = data or {}
        mapping = self._CURRENCY_NAME_MAP.get(symbol, {})

        if self.language == "fa":
            for k in ("name_fa", "name_farsi", "fa_name"):
                v = data.get(k)
                if v and self._has_persian_letters(str(v)):
                    return str(v).strip()
            if mapping.get("fa"):
                return mapping["fa"]

            v = str(data.get("name", "") or "").strip()
            if v and self._has_persian_letters(v) and not self._has_latin_letters(v):
                return v
            return symbol

        # English
        for k in ("name_en", "name_english", "en_name"):
            v = data.get(k)
            if v and not self._has_persian_letters(str(v)):
                return str(v).strip()
        if mapping.get("en"):
            return mapping["en"]

        v = str(data.get("name", "") or "").strip()
        if v and not self._has_persian_letters(v):
            return v
        return symbol

    def _unit_display(self, unit: Any) -> str:
        u = str(unit or "").strip()
        if not u:
            return ""

        if self.language == "fa":
            if self._has_persian_letters(u):
                return u
            key = u.strip().lower()
            return self._UNIT_MAP_FA.get(key, u)

        # English
        if self._has_persian_letters(u):
            return self._UNIT_MAP_EN.get(u, u)
        return u

    def _display_currency_data(self, sym: str, data: Dict[str, Any]) -> Dict[str, Any]:
        d = dict(data or {})
        d["symbol"] = str(sym or "").upper().strip()
        d["name"] = self._currency_display_name(sym, d)
        d["unit"] = self._unit_display(d.get("unit", ""))
        return d

# ----- sort helpers -----

    @staticmethod
    def _normalize_sort_key(value: str) -> str:
        v = str(value or "").strip().lower()
        mapping = {
            # English (legacy)
            "default": "default",
            "name": "name",
            "symbol": "symbol",
            "price": "price",
            "change": "change",
            # Capitalized legacy values
            "Default".lower(): "default",
            "Name".lower(): "name",
            "Symbol".lower(): "symbol",
            "Price".lower(): "price",
            "Change".lower(): "change",
            # Persian display (if saved accidentally)
            "پیش‌فرض": "default",
            "پیش فرض": "default",
            "نام": "name",
            "نماد": "symbol",
            "قیمت": "price",
            "تغییر": "change",
        }
        return mapping.get(v, "default")

    def _sort_key_to_display(self, key: str) -> str:
        k = self._normalize_sort_key(key)
        tr_key = {
            "default": "sort_default",
            "name": "sort_name",
            "symbol": "sort_symbol",
            "price": "sort_price",
            "change": "sort_change",
        }.get(k, "sort_default")
        return self._t(tr_key)

    def _sort_display_to_key(self, display: str) -> str:
        d = str(display or "").strip()
        for k in ("default", "name", "symbol", "price", "change"):
            if d == self._sort_key_to_display(k):
                return k
        return self._normalize_sort_key(d)

    def _get_sort_display_values(self) -> List[str]:
        return [self._sort_key_to_display(k) for k in ("default", "name", "symbol", "price", "change")]

    # ----- language apply -----

    def _apply_language(self) -> None:
        self.language = self._normalize_language(self.language)
        self.rtl = is_rtl(self.language)

        # Update toast typography
        try:
            self.toasts.set_typography(font_getter=self._ui_font, rtl=self.rtl)
        except Exception:
            pass

        # Window title
        try:
            self.title(f"{self._t('toolbar_title')} v{config.APP_VERSION}")
        except Exception:
            pass

        # Toolbar title
        try:
            if self.toolbar_title_label is not None:
                self.toolbar_title_label.configure(
                    text=self._t("toolbar_title"),
                    font=self._ui_font(16, True),
                    anchor="e" if self.rtl else "w",
                )
        except Exception:
            pass

        # Status indicator titles
        try:
            if "api_status" in self.ui_elements:
                self.ui_elements["api_status"]["title_label"].configure(
                    text=self._t("api"),
                    font=self._ui_font(12, True),
                    anchor="e" if self.rtl else "w",
                    justify="right" if self.rtl else "left",
                )
            if "data_status" in self.ui_elements:
                self.ui_elements["data_status"]["title_label"].configure(
                    text=self._t("data"),
                    font=self._ui_font(12, True),
                    anchor="e" if self.rtl else "w",
                    justify="right" if self.rtl else "left",
                )
            if "effects_status" in self.ui_elements:
                self.ui_elements["effects_status"]["title_label"].configure(
                    text=self._t("effects"),
                    font=self._ui_font(12, True),
                    anchor="e" if self.rtl else "w",
                    justify="right" if self.rtl else "left",
                )
        except Exception:
            pass

        # Hero
        try:
            if self.hero_title_label is not None:
                self.hero_title_label.configure(text=self._t("hero_title"), font=self._ui_font(40, True), anchor="e" if self.rtl else "w")
            if self.hero_subtitle_label is not None:
                self.hero_subtitle_label.configure(text=self._t("hero_subtitle"), font=self._ui_font(18, False), anchor="e" if self.rtl else "w")
            if self.hero_version_label is not None:
                ver = str(config.APP_VERSION)
                if self.language == "fa":
                    ver = ver.translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))
                else:
                    ver = ver.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))
                self.hero_version_label.configure(text=self._t("hero_version", version=ver), font=self._ui_font(14, False), anchor="e" if self.rtl else "w")
        except Exception:
            pass

        # Section titles
        for attr, key, size in (
            ("featured_title_label", "section_featured", 24),
            ("insights_title_label", "section_insights", 18),
            ("portfolio_title_label", "section_portfolio", 24),
            ("history_title_label", "section_history", 18),
            ("converter_title_label", "section_converter", 18),
            ("widgets_title_label", "section_widgets", 18),
            ("controls_title_label", "section_controls", 18),
            ("settings_title_label", "section_settings", 18),
            ("theme_title_label", "section_theme", 18),
        ):
            try:
                w = getattr(self, attr, None)
                if w is not None:
                    w.configure(
                        text=self._t(key),
                        font=self._ui_font(size, True),
                        anchor="e" if self.rtl else "w",
                        justify="right" if self.rtl else "left",
                    )
            except Exception:
                continue

        # Insights titles
        try:
            if self.gainers_title_label is not None:
                self.gainers_title_label.configure(text=self._t("top_gainers"), font=self._ui_font(13, True))
            if self.losers_title_label is not None:
                self.losers_title_label.configure(text=self._t("top_losers"), font=self._ui_font(13, True))
        except Exception:
            pass

        # Buttons / checkboxes / misc labels
        try:
            if hasattr(self, "refresh_btn"):
                self.refresh_btn.configure(text=self._t("btn_refresh"), font=self._ui_font(13, False))
            if hasattr(self, "test_btn"):
                self.test_btn.configure(text=self._t("btn_test_api"), font=self._ui_font(13, False))
            if hasattr(self, "export_btn"):
                self.export_btn.configure(text=self._t("btn_export_csv"), font=self._ui_font(13, False))
            if hasattr(self, "copy_btn"):
                self.copy_btn.configure(text=self._t("btn_copy"), font=self._ui_font(13, False))
        except Exception:
            pass

        try:
            if hasattr(self, "auto_refresh_checkbox"):
                self.auto_refresh_checkbox.configure(text=self._t("auto_refresh"), font=self._ui_font(13, False))
        except Exception:
            pass

        # Settings controls
        try:
            if hasattr(self, "refresh_interval_title_label"):
                self.refresh_interval_title_label.configure(text=self._t("refresh_interval"), font=self._ui_font(12, True))
            if hasattr(self, "refresh_interval_menu") and hasattr(self, "refresh_interval_var"):
                self.refresh_interval_menu.configure(values=self._interval_choices(), font=self._ui_font(13, False))
                self.refresh_interval_var.set(self._format_interval(self.refresh_interval_seconds))
                try:
                    self.refresh_interval_menu.configure(dropdown_font=self._ui_font(13, False))
                except Exception:
                    pass
        except Exception:
            pass

        try:
            if getattr(self, "language_setting_label", None) is not None:
                self.language_setting_label.configure(text=self._t("language_label"), font=self._ui_font(12, True))
            if self.language_var is not None and self.language_menu is not None:
                self.language_menu.configure(values=self._language_menu_values(), font=self._ui_font(13, False))
                self.language_var.set(self._language_display(self.language))
                try:
                    self.language_menu.configure(dropdown_font=self._ui_font(13, False))
                except Exception:
                    pass
        except Exception:
            pass

        # Window options
        try:
            if getattr(self, "window_options_label", None) is not None:
                self.window_options_label.configure(text=self._t("window_options"), font=self._ui_font(12, True), anchor="e" if self.rtl else "w")
            if getattr(self, "always_on_top_cb", None) is not None:
                self.always_on_top_cb.configure(text=self._t("always_on_top"), font=self._ui_font(13, False))
            if getattr(self, "background_cb", None) is not None:
                self.background_cb.configure(text=self._t("run_in_background"), font=self._ui_font(13, False))
        except Exception:
            pass

        # Alerts
        try:
            if hasattr(self, "alerts_title_label"):
                self.alerts_title_label.configure(text=self._t("alerts_title"), font=self._ui_font(12, True))
            if hasattr(self, "alerts_cb"):
                self.alerts_cb.configure(text=self._t("enable_alerts"), font=self._ui_font(13, False))
        except Exception:
            pass

        try:
            if hasattr(self, "alert_threshold_label"):
                self.alert_threshold_label.configure(text=self._t("threshold", value=float(self.alert_threshold_percent)), font=self._ui_font(12, False))
        except Exception:
            pass

        # Tools
        try:
            if hasattr(self, "tools_title_label"):
                self.tools_title_label.configure(text=self._t("tools"), font=self._ui_font(12, True))
            if hasattr(self, "clear_cache_btn"):
                self.clear_cache_btn.configure(text=self._t("btn_clear_cache"), font=self._ui_font(13, False))
            if hasattr(self, "perf_btn"):
                self.perf_btn.configure(text=self._t("btn_performance"), font=self._ui_font(13, False))
        except Exception:
            pass

        # Add / sort controls
        try:
            if hasattr(self, "selector_search_entry"):
                self.selector_search_entry.configure(
                    placeholder_text=self._t("placeholder_search"),
                    font=self._ui_font(13, False),
                    justify="right" if self.rtl else "left",
                )
            if getattr(self, "portfolio_filter_entry", None) is not None:
                self.portfolio_filter_entry.configure(
                    placeholder_text=self._t("placeholder_portfolio_filter"),
                    font=self._ui_font(12, False),
                    justify="right" if self.rtl else "left",
                )
            if hasattr(self, "currency_selector"):
                self.currency_selector.configure(font=self._ui_font(13, False), justify="right" if self.rtl else "left")
                try:
                    self.currency_selector.configure(dropdown_font=self._ui_font(13, False))
                except Exception:
                    pass
            if hasattr(self, "add_currency_inline_btn"):
                self.add_currency_inline_btn.configure(text=self._t("btn_add"), font=self._ui_font(13, False))
        except Exception:
            pass

        # Inline add panel label + RTL/LTR placement
        try:
            if getattr(self, "portfolio_add_title_label", None) is not None:
                self.portfolio_add_title_label.configure(
                    text=self._t("portfolio_add_title"),
                    font=self._ui_font(12, True),
                    anchor="e" if self.rtl else "w",
                    justify="right" if self.rtl else "left",
                )
            self._regrid_add_currency_panel()
        except Exception:
            pass

        # Sort menu text + values
        try:
            if self.sort_label is not None:
                self.sort_label.configure(text=self._t("sort"), font=self._ui_font(12, True))
            if hasattr(self, "portfolio_sort_menu"):
                self.portfolio_sort_menu.configure(values=self._get_sort_display_values(), font=self._ui_font(13, False))
                try:
                    self.portfolio_sort_menu.configure(dropdown_font=self._ui_font(13, False))
                except Exception:
                    pass
            if hasattr(self, "portfolio_sort_var"):
                self.portfolio_sort_var.set(self._sort_key_to_display(self.portfolio_sort_mode_key))
        except Exception:
            pass

        # Theme buttons
        try:
            if "liquid_glass" in self.theme_buttons:
                self.theme_buttons["liquid_glass"].configure(text=self._t("theme_liquid_glass"), font=self._ui_font(13, False))
            if "vibrancy" in self.theme_buttons:
                self.theme_buttons["vibrancy"].configure(text=self._t("theme_vibrancy"), font=self._ui_font(13, False))
            if "crystal" in self.theme_buttons:
                self.theme_buttons["crystal"].configure(text=self._t("theme_crystal"), font=self._ui_font(13, False))
            if "midnight" in self.theme_buttons:
                self.theme_buttons["midnight"].configure(text=self._t("theme_midnight"), font=self._ui_font(13, False))
            if "paper" in self.theme_buttons:
                self.theme_buttons["paper"].configure(text=self._t("theme_paper"), font=self._ui_font(13, False))
        except Exception:
            pass

        # Last update label
        try:
            if hasattr(self, "last_update_label"):
                tval = str(self.last_update)
                if self.language == "fa":
                    tval = tval.translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))
                else:
                    tval = tval.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))
                self.last_update_label.configure(text=self._t("last_update", time=tval), font=self._ui_font(12, False))
        except Exception:
            pass

        # Update cards typography
        try:
            for card in list(self.featured_cards.values()) + list(self.portfolio_cards.values()):
                card.set_typography(font_getter=self._ui_font, rtl=self.rtl)
        except Exception:
            pass

        # Re-render text-heavy UI pieces so names/units switch cleanly
        try:
            self._render_featured_cards()
            self._render_portfolio_cards()
            self._update_insights()
        except Exception:
            pass

        # Update status strings in the current language
        try:
            self._update_connection_status(self.connection_status)
            self._update_status_displays()
        except Exception:
            pass


        # Refresh translated menus + desktop widgets
        try:
            self.widget_manager.apply_typography()
        except Exception:
            pass

        try:
            # Force rebuild because display strings depend on language
            self._symbol_menu_sig = ""
            self._refresh_symbol_menus()
        except Exception:
            pass

        # History period values are language-dependent
        try:
            if self.history_period_menu is not None:
                old_seconds = int(getattr(self, "_history_period_seconds", 24 * 3600))
                vals, self._history_period_map = self._history_period_options()
                self.history_period_menu.configure(values=vals)

                # Keep selection by seconds
                best = vals[0] if vals else self._t("period_24h")
                sec_map = {
                    1 * 3600: self._t("period_1h"),
                    6 * 3600: self._t("period_6h"),
                    24 * 3600: self._t("period_24h"),
                    7 * 86400: self._t("period_7d"),
                }
                best = sec_map.get(old_seconds, best)
                if self.history_period_var is not None:
                    self.history_period_var.set(best)
        except Exception:
            pass

        # Widget type values are language-dependent
        try:
            if self.widgets_type_menu is not None and self.widgets_type_var is not None:
                old_disp = self.widgets_type_var.get()
                old_map = getattr(self, "_widget_type_map", {}) or {}
                internal = old_map.get(old_disp, "price")

                vals, self._widget_type_map = self._widget_type_options()
                self.widgets_type_menu.configure(values=vals)

                rev = {v: k for k, v in self._widget_type_map.items()}
                self.widgets_type_var.set(rev.get(internal, vals[0] if vals else old_disp))
                self._on_widget_type_changed()
        except Exception:
            pass

        try:
            self._update_converter_result()
        except Exception:
            pass

        # Update selector (strings like "No matches")
        try:
            self._update_currency_selector()
        except Exception:
            pass


    def _on_language_changed(self, *_: Any) -> None:
        try:
            if self.language_var is None:
                return
            new_lang = self._display_to_language(self.language_var.get())
            if new_lang == self.language:
                return
            self.language = new_lang
            # Direction-dependent widgets (pack/grid order) must be rebuilt.
            self.rtl = is_rtl(self.language)
            db_manager.save_preference("language", self.language)

            try:
                self._rebuild_main_sections()
            except Exception:
                # Fallback: at least refresh text/font/anchors
                self._apply_language()
        except Exception:
            pass

    # ----- selector helpers -----

    def _get_selector_values(self, *, search: str, excluded: set[str]) -> List[str]:
        search = (search or "").strip().lower()
        options: List[str] = []
        for sym, data in self.currencies.items():
            if sym in excluded:
                continue
            name = self._currency_display_name(sym, data)
            display = f"{name} ({sym})"
            if search:
                if search not in sym.lower() and search not in name.lower() and search not in display.lower():
                    continue
            options.append(display)

        if not options:
            return [self._t("no_matches")]

        return sorted(options, key=lambda s: s.lower())

    # ----- responsive layout -----

    def _on_window_resize(self, event: Any) -> None:
        try:
            if event.widget is not self:
                return
            if self._resize_after_id:
                self.after_cancel(self._resize_after_id)
        except Exception:
            pass

        try:
            self._resize_after_id = self.after(180, self._recalculate_layout)
        except Exception:
            pass

    def _recalculate_layout(self) -> None:
        try:
            w = int(self.winfo_width())
        except Exception:
            return

        # Approximate available width inside the scroll frame
        available = max(400, w - 120)
        card_total = int(config.CARD_WIDTH + config.CARD_PADDING * 2)
        new_cols = int(max(2, min(4, available // max(1, card_total))))

        if new_cols != self.grid_columns:
            self.grid_columns = new_cols
            self._apply_grid_columns()
            self._refresh_featured_symbols()
            self._render_featured_cards()
            self._render_portfolio_cards()

    def _apply_grid_columns(self) -> None:
        try:
            max_cols = 4
            for container in (getattr(self, "featured_container", None), getattr(self, "portfolio_container", None)):
                if container is None:
                    continue
                for i in range(max_cols):
                    container.grid_columnconfigure(i, weight=1 if i < self.grid_columns else 0)
        except Exception:
            pass


    # -------------------------------------------------------------------------
    # Startup helpers (missing in earlier builds)
    # -------------------------------------------------------------------------

    def _bind_shortcuts(self) -> None:
        """Keyboard shortcuts (safe to call even if some widgets aren't ready)."""
        try:
            self.bind("<Control-r>", lambda _e: self._manual_refresh())
            self.bind("<F5>", lambda _e: self._manual_refresh())
        except Exception:
            pass

        # Quick focus helpers
        try:
            self.bind("<Control-f>", lambda _e: self._focus_portfolio_filter())
        except Exception:
            pass

        # Exit / hide
        try:
            self.bind("<Control-q>", lambda _e: self._on_close_requested())
            self.bind("<Escape>", lambda _e: self._maybe_close_transient())
        except Exception:
            pass

    def _focus_portfolio_filter(self) -> None:
        try:
            if self.portfolio_filter_entry is not None:
                self.portfolio_filter_entry.focus_set()
                self.portfolio_filter_entry.select_range(0, "end")
        except Exception:
            pass

    def _maybe_close_transient(self) -> None:
        """Close transient dialogs/popups if any; otherwise do nothing."""
        # Keep intentionally conservative; the main window should not close on Escape.
        try:
            if hasattr(self, "toasts"):
                self.toasts.clear_all()
        except Exception:
            pass

    def _refresh_featured_symbols(self) -> None:
        """Pick a stable set of featured symbols (top row)."""
        priority = [
            "USD", "EUR", "GBP", "AED", "TRY",
            "BTC", "ETH",
            "GOLD", "SEKEH", "GERAM18",
        ]

        out: List[str] = []
        seen: set[str] = set()

        for sym in priority:
            s = str(sym).upper().strip()
            if s in self.currencies and s not in seen:
                out.append(s)
                seen.add(s)

        # Fill remaining slots with whatever is available (deterministic)
        try:
            for sym in sorted(self.currencies.keys()):
                s = str(sym).upper().strip()
                if s and s not in seen:
                    out.append(s)
                    seen.add(s)
                if len(out) >= 12:
                    break
        except Exception:
            pass

        self.featured_symbols = out

    def _load_cached_first_paint(self) -> None:
        """Use DB cache to render something instantly on startup."""
        try:
            cached = db_manager.load_cached_currencies(max_age_seconds=6 * 3600)
        except Exception:
            cached = {}

        if not cached:
            return

        try:
            performance_monitor.inc("cache_loads")
        except Exception:
            pass

        old = dict(self.currencies)
        self.currencies = dict(cached)

        # Populate featured + refresh UI
        self._refresh_featured_symbols()
        self._render_featured_cards()
        self._render_portfolio_cards()
        self._update_currency_selector()
        self._refresh_symbol_menus()
        self._update_insights()

        self._update_connection_status(ConnectionStatus.CACHED)
        self._update_status_displays()

        # Update desktop widgets
        try:
            self.widget_manager.update_all(self.currencies)
        except Exception:
            pass

        # Alerts should compare live updates only, not cache load
        try:
            self._last_seen_prices.clear()
            for sym, d in self.currencies.items():
                try:
                    self._last_seen_prices[str(sym).upper().strip()] = float(d.get("price", 0) or 0)
                except Exception:
                    continue
        except Exception:
            pass

    def _enqueue_ui(self, fn: Callable[[], None]) -> None:
        """Enqueue a callable to run on the Tk/UI thread.
        This avoids calling Tk methods from worker threads.
        """
        try:
            q = getattr(self, "_ui_task_queue", None)
            if q is not None:
                q.put(fn)
        except Exception:
            pass

    def _drain_ui_task_queue(self) -> None:
        """Run queued UI tasks on the main thread."""
        try:
            if not getattr(self, "_ui_queue_running", True):
                return
            q = getattr(self, "_ui_task_queue", None)
            if q is not None:
                while True:
                    try:
                        fn = q.get_nowait()
                    except queue.Empty:
                        break
                    try:
                        fn()
                    except Exception:
                        try:
                            logger.exception("UI task failed")
                        except Exception:
                            pass
        finally:
            try:
                self.after(50, self._drain_ui_task_queue)
            except Exception:
                pass

    def _start_data_systems(self) -> None:
        """Kick off networking and periodic refresh."""
        # First live refresh
        self._update_connection_status(ConnectionStatus.CONNECTING)
        try:
            self.executor.submit(self._initial_refresh_worker)
        except Exception:
            # Fallback: try sync (should still be safe)
            self._enqueue_ui(self._manual_refresh)

        # Auto refresh scheduler
        self._schedule_auto_refresh()

        # Small periodic tasks (history UI smoothness)
        try:
            self.after(20_000, self._periodic_light_tasks)
        except Exception:
            pass

    def _periodic_light_tasks(self) -> None:
        try:
            self._history_live_append()
        except Exception:
            pass
        try:
            self._update_converter_result()
        except Exception:
            pass

        # Re-arm
        try:
            self.after(20_000, self._periodic_light_tasks)
        except Exception:
            pass

    def _initial_refresh_worker(self) -> None:
        try:
            performance_monitor.inc("api_calls")
            data = self.api_manager.fetch_data_sync(force=True)
            if data:
                currencies = self.api_manager.process_currency_data(data)
                if currencies:
                    self._enqueue_ui(lambda: self._update_ui_with_data(currencies, ConnectionStatus.CONNECTED, quiet=True))
                    return

            # If primary payload was present but unparseable / empty, try backups explicitly
            data2 = self.api_manager.fetch_data_sync(force=True, skip_primary=True)
            if data2:
                currencies2 = self.api_manager.process_currency_data(data2)
                if currencies2:
                    self._enqueue_ui(lambda: self._update_ui_with_data(currencies2, ConnectionStatus.CONNECTED, quiet=True))
                    return

            self._enqueue_ui(lambda: self._update_connection_status(ConnectionStatus.ERROR))
        except Exception as e:
            try:
                logger.warning(f"Initial refresh failed: {e}")
            except Exception:
                pass
            self._enqueue_ui(lambda: self._update_connection_status(ConnectionStatus.ERROR))

    def _schedule_auto_refresh(self) -> None:
        """(Re)Schedule auto refresh based on current settings."""
        # Cancel previous
        try:
            if self._auto_refresh_after_id:
                try:
                    self.after_cancel(self._auto_refresh_after_id)
                except Exception:
                    pass
                self._auto_refresh_after_id = None
        except Exception:
            pass

        if not self.auto_refresh_active:
            return

        try:
            interval_ms = int(max(config.MIN_REFRESH_INTERVAL, min(config.MAX_REFRESH_INTERVAL, int(self.refresh_interval_seconds)))) * 1000
        except Exception:
            interval_ms = int(config.DEFAULT_REFRESH_INTERVAL) * 1000

        try:
            self._auto_refresh_after_id = self.after(interval_ms, self._auto_refresh_tick)
        except Exception:
            self._auto_refresh_after_id = None

    def _auto_refresh_tick(self) -> None:
        # Re-arm first (so failures don't stop the loop)
        self._schedule_auto_refresh()

        # Don't stack refreshes
        if getattr(self, "_refresh_inflight", False):
            return

        self._refresh_inflight = True
        try:
            self.executor.submit(self._auto_refresh_worker)
        except Exception:
            self._refresh_inflight = False

    def _auto_refresh_worker(self) -> None:
        try:
            performance_monitor.inc("api_calls")
            data = self.api_manager.fetch_data_sync(force=False)
            if data:
                currencies = self.api_manager.process_currency_data(data)
                if currencies:
                    self._enqueue_ui(lambda: self._update_ui_with_data(currencies, ConnectionStatus.CONNECTED, quiet=True))
                    return
            self._enqueue_ui(lambda: self._update_connection_status(ConnectionStatus.ERROR))
        except Exception:
            self._enqueue_ui(lambda: self._update_connection_status(ConnectionStatus.ERROR))
        finally:
            self._refresh_inflight = False

    def _update_ui_with_data(self, currencies: Dict[str, Dict[str, Any]], status: ConnectionStatus, *, quiet: bool = True) -> None:
        """Apply fresh currency data to the app state + UI."""
        performance_monitor.inc("ui_updates")

        old = dict(self.currencies)
        self.currencies = dict(currencies or {})

        # Update featured selections first (affects portfolio view)
        self._refresh_featured_symbols()

        # UI updates
        self._render_featured_cards()
        self._render_portfolio_cards()
        self._update_currency_selector()
        self._refresh_symbol_menus()
        self._update_insights()

        # Status text
        try:
            self.last_update = time.strftime("%H:%M:%S")
        except Exception:
            self.last_update = "—"

        self._update_connection_status(status)
        self._update_status_displays()

        # Alerts (compare to previous snapshot)
        try:
            self._maybe_emit_price_alerts(old, self.currencies)
        except Exception:
            pass

        # Desktop widgets
        try:
            self.widget_manager.update_all(self.currencies)
        except Exception:
            pass

        # Cache write (async)
        try:
            self.executor.submit(db_manager.cache_bulk_currency_data, dict(self.currencies))
        except Exception:
            pass

        # Session tracker (no chart)
        try:
            self._update_session_tracker()
        except Exception:
            pass

        if not quiet:
            try:
                self.toasts.show(self._t("toast_updated"), duration=1800)
            except Exception:
                pass


    # -------------------------------------------------------------------------
    # UI building blocks
    # -------------------------------------------------------------------------

    def _create_glass_card(self, parent: ctk.CTkBaseClass, *, height: Optional[int] = None, glass_level: int = 1) -> ctk.CTkFrame:
        glass_colors = [
            (colors.glass_light, colors.glass_dark),
            (colors.glass_overlay_light, colors.glass_overlay_dark),
        ]
        fg_color = glass_colors[min(max(glass_level - 1, 0), len(glass_colors) - 1)]
        kwargs: Dict[str, Any] = dict(
            fg_color=fg_color,
            corner_radius=16,
            border_width=1,
            border_color=(colors.border_light, colors.border_dark),
        )
        if height:
            kwargs["height"] = height
        frame = ctk.CTkFrame(parent, **kwargs)
        if height:
            frame.pack_propagate(False)
        return frame

    def _create_button(
        self,
        parent: ctk.CTkBaseClass,
        *,
        text: str,
        command: Callable[[], None],
        style: str = "primary",
        width: Optional[int] = None,
    ) -> ctk.CTkButton:
        styles = {
            "primary": dict(
                fg_color=(colors.accent_blue, colors.accent_blue),
                hover_color=(colors.accent_blue_hover, colors.accent_blue_hover),
                text_color="white",
                border_width=0,
            ),
            "secondary": dict(
                fg_color=(colors.glass_overlay_light, colors.glass_overlay_dark),
                hover_color=(colors.separator_light, colors.separator_dark),
                text_color=(colors.text_primary_light, colors.text_primary_dark),
                border_width=1,
                border_color=(colors.border_light, colors.border_dark),
            ),
            "danger": dict(
                fg_color=(colors.accent_red, colors.accent_red),
                hover_color=(colors.accent_orange, colors.accent_orange),
                text_color="white",
                border_width=0,
            ),
        }
        cfg = styles.get(style, styles["primary"]).copy()
        kwargs: Dict[str, Any] = dict(
            text=text,
            command=command,
            font=self._ui_font(13, False),
            corner_radius=10,
            height=40,
        )
        if width:
            kwargs["width"] = width
        kwargs.update(cfg)
        return ctk.CTkButton(parent, **kwargs)

    # -------------------------------------------------------------------------
    # UI layout
    # -------------------------------------------------------------------------

    def _create_user_interface(self) -> None:
        self.main_container = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.main_container.pack(fill="both", expand=True, padx=20, pady=20)
        self.main_container.grid_columnconfigure(0, weight=1)
        # Scrollable content
        self.scroll_frame = ctk.CTkScrollableFrame(
            self.main_container,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=(colors.border_light, colors.border_dark),
            scrollbar_button_hover_color=(colors.accent_blue, colors.accent_blue),
        )
        self.scroll_frame.pack(fill="both", expand=True)
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        self._ui_row = 0

        builders: Dict[str, Callable[[], None]] = {
            "hero": self._create_hero_section,
            "status": self._create_status_section,
            "featured": self._create_featured_section,
            "insights": self._create_insights_section,
            "history": self._create_history_section,
            "portfolio": self._create_portfolio_section,
            "converter": self._create_converter_section,
            "widgets": self._create_widgets_section,
            "controls": self._create_controls_section,
            "settings": self._create_settings_section,
            "theme": self._create_theme_section,
        }

        order = list(getattr(self, "section_order", []) or builders.keys())
        enabled_map = dict(getattr(self, "section_enabled", {}) or {})

        for key in order:
            fn = builders.get(key)
            if not fn:
                continue
            if not enabled_map.get(key, True):
                continue
            fn()


    def _next_row(self, inc: int = 1) -> int:
        r = self._ui_row
        self._ui_row += inc
        return r

    
    # -------------------------------------------------------------------------
    # Layout customization (sections)
    # -------------------------------------------------------------------------

    def _save_layout_preferences(self) -> None:
        try:
            db_manager.save_preference("section_order_json", json.dumps(list(self.section_order)))
            db_manager.save_preference("section_enabled_json", json.dumps(dict(self.section_enabled)))
        except Exception:
            pass

    def _rebuild_main_sections(self) -> None:
        # Ensure direction is up-to-date BEFORE rebuilding so pack/grid order is correct.
        try:
            self.language = self._normalize_language(self.language)
        except Exception:
            pass
        self.rtl = is_rtl(self.language)

        # Destroy existing section widgets
        try:
            for child in list(self.scroll_frame.winfo_children()):
                child.destroy()
        except Exception:
            pass

        # Reset UI caches/handles (avoid stale references to destroyed widgets)
        try:
            self.ui_elements = {}
            self.theme_buttons = {}
            self.featured_cards = {}
            self.portfolio_cards = {}
        except Exception:
            pass

        # Reset common widget refs so _apply_language won't touch destroyed widgets
        for attr in (
            "toolbar_title_label",
            "language_var",
            "language_menu",
            "always_on_top_var",
            "always_on_top_cb",
            "background_var",
            "background_cb",
            "window_options_label",
            "hero_title_label",
            "hero_subtitle_label",
            "hero_version_label",
            "featured_title_label",
            "insights_title_label",
            "portfolio_title_label",
            "history_title_label",
            "converter_title_label",
            "widgets_title_label",
            "controls_title_label",
            "settings_title_label",
            "theme_title_label",
            "gainers_title_label",
            "losers_title_label",
            "sort_label",
            "portfolio_filter_var",
            "portfolio_filter_entry",
            "history_symbol_var",
            "history_period_var",
            "history_symbol_menu",
            "history_period_menu",
            "history_sparkline",
            "history_stats_label",
            "converter_amount_var",
            "converter_from_var",
            "converter_to_var",
            "converter_result_label",
            "converter_from_menu",
            "converter_to_menu",
            "widgets_type_var",
            "widgets_symbol_var",
            "widgets_type_menu",
            "widgets_symbol_menu",
            "widgets_active_list",
        ):
            try:
                setattr(self, attr, None)
            except Exception:
                pass

        for attr in (
            "refresh_btn",
            "test_btn",
            "export_btn",
            "copy_btn",
            "layout_btn",
            "auto_refresh_checkbox",
            "refresh_interval_title_label",
            "refresh_interval_menu",
            "refresh_interval_var",
            "language_setting_label",
            "alerts_title_label",
            "alerts_cb",
            "alert_threshold_label",
            "tools_title_label",
            "clear_cache_btn",
            "perf_btn",
            "selector_search_entry",
            "currency_selector",
            "add_currency_inline_btn",
            "portfolio_add_title_label",
            "portfolio_sort_menu",
            "portfolio_sort_var",
            "last_update_label",
        ):
            try:
                setattr(self, attr, None)
            except Exception:
                pass

        self._ui_row = 0

        builders: Dict[str, Callable[[], None]] = {
            "hero": self._create_hero_section,
            "status": self._create_status_section,
            "featured": self._create_featured_section,
            "insights": self._create_insights_section,
            "history": self._create_history_section,
            "portfolio": self._create_portfolio_section,
            "converter": self._create_converter_section,
            "widgets": self._create_widgets_section,
            "controls": self._create_controls_section,
            "settings": self._create_settings_section,
            "theme": self._create_theme_section,
        }

        order = list(getattr(self, "section_order", []) or builders.keys())
        enabled_map = dict(getattr(self, "section_enabled", {}) or {})

        for key in order:
            fn = builders.get(key)
            if not fn:
                continue
            if not enabled_map.get(key, True):
                continue
            fn()

        try:
            self._apply_language()
            self._apply_grid_columns()
        except Exception:
            pass


    def _layout_move(self, key: str, direction: int) -> None:
        try:
            order = list(self.section_order)
            i = order.index(key)
            j = i + int(direction)
            if j < 0 or j >= len(order):
                return
            order[i], order[j] = order[j], order[i]
            self.section_order = order
            self._save_layout_preferences()
            self._rebuild_main_sections()
        except Exception:
            pass

    
    def _open_layout_popup(self) -> None:
        try:
            win = ctk.CTkToplevel(self)
        except Exception:
            return
        try:
            win.title("Layout")
            win.geometry("520x520")
            win.resizable(False, False)
            win.transient(self)
            win.grab_set()
        except Exception:
            pass

        try:
            win.configure(fg_color=(colors.bg_light, colors.bg_dark))
        except Exception:
            pass

        card = ctk.CTkFrame(win, fg_color=(colors.glass_overlay_light, colors.glass_overlay_dark), corner_radius=18)
        card.pack(fill="both", expand=True, padx=16, pady=16)

        title = ctk.CTkLabel(
            card,
            text=("چیدمان بخش ها" if self.language == "fa" else "Sections Layout"),
            font=self._ui_font(16, True),
            text_color=(colors.text_primary_light, colors.text_primary_dark),
            anchor="e" if self.rtl else "w",
        )
        title.pack(fill="x", padx=18, pady=(16, 10))

        container = ctk.CTkScrollableFrame(card, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        section_labels = {
            "hero": self._t("section_hero") if "section_hero" in TRANSLATIONS.get(self.language, {}) else ("خانه" if self.language == "fa" else "Home"),
            "status": self._t("section_status") if "section_status" in TRANSLATIONS.get(self.language, {}) else ("وضعیت" if self.language == "fa" else "Status"),
            "featured": self._t("section_featured"),
            "insights": self._t("section_insights"),
            "portfolio": self._t("section_portfolio"),
            "converter": self._t("section_converter"),
            "widgets": self._t("section_widgets"),
            "controls": self._t("section_controls"),
            "settings": self._t("section_settings"),
            "theme": self._t("section_theme"),
        }

        vars_map: Dict[str, tk.BooleanVar] = {}

        order = list(getattr(self, "section_order", []) or [])
        enabled_map = dict(getattr(self, "section_enabled", {}) or {})

        for key in order:
            line = ctk.CTkFrame(container, fg_color="transparent")
            line.pack(fill="x", pady=4)

            var = tk.BooleanVar(value=bool(enabled_map.get(key, True)))
            vars_map[key] = var

            cb = ctk.CTkCheckBox(
                line,
                text=section_labels.get(key, key),
                variable=var,
                onvalue=True,
                offvalue=False,
                command=lambda k=key, v=var: self._layout_set_enabled(k, bool(v.get())),
                text_color=(colors.text_primary_light, colors.text_primary_dark),
                fg_color=(colors.accent_blue, colors.accent_blue),
                border_color=(colors.border_light, colors.border_dark),
            )
            cb.pack(side="right" if self.rtl else "left", padx=(0, 8))

            btn_up = self._create_button(line, text="▲", command=lambda k=key: self._layout_move(k, -1), style="secondary", width=44)
            btn_down = self._create_button(line, text="▼", command=lambda k=key: self._layout_move(k, +1), style="secondary", width=44)

            if self.rtl:
                btn_down.pack(side="left", padx=(0, 6))
                btn_up.pack(side="left")
            else:
                btn_up.pack(side="right", padx=(6, 0))
                btn_down.pack(side="right")

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=18, pady=(0, 16))

        close_btn = self._create_button(btn_row, text=("بستن" if self.language == "fa" else "Close"), command=lambda: win.destroy(), style="secondary", width=140)
        close_btn.pack(side="left" if self.rtl else "right")

    def _layout_set_enabled(self, key: str, enabled: bool) -> None:
        try:
            self.section_enabled[str(key)] = bool(enabled)
            self._save_layout_preferences()
            self._rebuild_main_sections()
        except Exception:
            pass

    def _create_hero_section(self) -> None:
        row = self._next_row()
        hero_card = self._create_glass_card(self.scroll_frame, height=185, glass_level=2)
        hero_card.grid(row=row, column=0, sticky="ew", pady=(0, 20))

        content = ctk.CTkFrame(hero_card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=32, pady=24)

        self.hero_title_label = ctk.CTkLabel(
            content,
            text=self._t("hero_title"),
            font=self._ui_font(40, True),
            text_color=(colors.text_primary_light, colors.text_primary_dark),
            anchor="e" if self.rtl else "w",
        )
        self.hero_title_label.pack(fill="x")

        self.hero_subtitle_label = ctk.CTkLabel(
            content,
            text=self._t("hero_subtitle"),
            font=self._ui_font(18, False),
            text_color=(colors.text_secondary_light, colors.text_secondary_dark),
            anchor="e" if self.rtl else "w",
        )
        self.hero_subtitle_label.pack(fill="x", pady=(8, 0))

        self.hero_version_label = ctk.CTkLabel(
            content,
            text=self._t("hero_version", version=config.APP_VERSION),
            font=self._ui_font(14, False),
            text_color=(colors.text_tertiary_light, colors.text_tertiary_dark),
            anchor="e" if self.rtl else "w",
        )
        self.hero_version_label.pack(fill="x", pady=(12, 0))


    def _create_status_section(self) -> None:
        row = self._next_row()
        status_card = self._create_glass_card(self.scroll_frame, height=120, glass_level=2)
        status_card.grid(row=row, column=0, sticky="ew", pady=(0, 20))

        content = ctk.CTkFrame(status_card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=18)

        grid = ctk.CTkFrame(content, fg_color="transparent")
        grid.pack(fill="x")
        grid.grid_columnconfigure((0, 1, 2), weight=1)

        self._create_status_indicator(grid, self._t("api"), "🔗", "api_status", row=0, col=0)
        self._create_status_indicator(grid, self._t("data"), "📊", "data_status", row=0, col=1)
        self._create_status_indicator(grid, self._t("effects"), "✨", "effects_status", row=0, col=2)

    def _create_status_indicator(self, parent, title: str, icon: str, key: str, row: int, col: int) -> None:
        box = ctk.CTkFrame(
            parent,
            fg_color=(colors.glass_overlay_light, colors.glass_overlay_dark),
            corner_radius=12,
            border_width=1,
            border_color=(colors.border_light, colors.border_dark),
            height=70,
        )
        box.grid(row=row, column=col, padx=8, pady=4, sticky="ew")
        box.pack_propagate(False)

        content = ctk.CTkFrame(box, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=16, pady=10)

        header = ctk.CTkFrame(content, fg_color="transparent")
        header.pack(fill="x")

        ctk.CTkLabel(header, text=icon, font=self._ui_font(16, False)).pack(side="left")
        ctk.CTkLabel(
            header,
            text=title,
            font=self._ui_font(13, True),
            text_color=(colors.text_primary_light, colors.text_primary_dark),
        ).pack(side="left", padx=(8, 0))

        status_label = ctk.CTkLabel(
            content,
            text=self._t("status_connecting"),
            font=self._ui_font(12, False),
            text_color=(colors.text_secondary_light, colors.text_secondary_dark),
        )
        status_label.pack(anchor="w", pady=(6, 0))

        self.ui_elements[key] = {"status_label": status_label}

    def _create_featured_section(self) -> None:
        row = self._next_row(2)
        self.featured_title_label = ctk.CTkLabel(
            self.scroll_frame,
            text=self._t("section_featured"),
            font=self._ui_font(24, True),
            text_color=(colors.text_primary_light, colors.text_primary_dark),
            anchor="e" if self.rtl else "w",
        )
        self.featured_title_label.grid(row=row, column=0, sticky="w", pady=(0, 14))

        self.featured_container = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.featured_container.grid(row=row + 1, column=0, sticky="ew", pady=(0, 26))
        for i in range(4):
            self.featured_container.grid_columnconfigure(i, weight=1)


    def _create_insights_section(self) -> None:
        row = self._next_row()
        card = self._create_glass_card(self.scroll_frame, height=155, glass_level=2)
        card.grid(row=row, column=0, sticky="ew", pady=(0, 20))

        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=18)

        header = ctk.CTkFrame(content, fg_color="transparent")
        header.pack(fill="x")

        self.insights_title_label = ctk.CTkLabel(
            header,
            text=self._t("section_insights"),
            font=self._ui_font(18, True),
            text_color=(colors.text_primary_light, colors.text_primary_dark),
            anchor="e" if self.rtl else "w",
        )
        self.insights_title_label.pack(side="left" if not self.rtl else "right")

        body = ctk.CTkFrame(content, fg_color="transparent")
        body.pack(fill="both", expand=True, pady=(10, 0))
        body.grid_columnconfigure((0, 1), weight=1)

        left = ctk.CTkFrame(body, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        right = ctk.CTkFrame(body, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(14, 0))

        self.gainers_title_label = ctk.CTkLabel(
            left,
            text=self._t("top_gainers"),
            font=self._ui_font(13, True),
            text_color=(colors.accent_green, colors.accent_green),
        )
        self.gainers_title_label.pack(anchor="w")

        self.ui_elements["top_gainers"] = [
            ctk.CTkLabel(
                left,
                text="—",
                font=self._ui_font(12, False),
                text_color=(colors.text_secondary_light, colors.text_secondary_dark),
                anchor="e" if self.rtl else "w",
                justify="right" if self.rtl else "left",
            )
            for _ in range(3)
        ]
        for lbl in self.ui_elements["top_gainers"]:
            lbl.pack(anchor="w", pady=1, fill="x")

        self.losers_title_label = ctk.CTkLabel(
            right,
            text=self._t("top_losers"),
            font=self._ui_font(13, True),
            text_color=(colors.accent_red, colors.accent_red),
        )
        self.losers_title_label.pack(anchor="w")

        self.ui_elements["top_losers"] = [
            ctk.CTkLabel(
                right,
                text="—",
                font=self._ui_font(12, False),
                text_color=(colors.text_secondary_light, colors.text_secondary_dark),
                anchor="e" if self.rtl else "w",
                justify="right" if self.rtl else "left",
            )
            for _ in range(3)
        ]
        for lbl in self.ui_elements["top_losers"]:
            lbl.pack(anchor="w", pady=1, fill="x")


    # -------------------------------------------------------------------------
    # New Sections: History / Converter / Widgets
    # -------------------------------------------------------------------------

    def _symbol_to_display(self, sym: str, data: Optional[Dict[str, Any]] = None) -> str:
        s = str(sym or "").upper().strip()
        if s == "TOMAN":
            return "TOMAN • تومان" if self.language == "fa" else "Toman (IRR)"

        d = data or self.currencies.get(s, {}) or {}
        name = self._currency_display_name(s, d) if d else s
        if self.language == "fa":
            return f"{s} • {name}"
        return f"{name} ({s})"

    def _display_to_symbol_value(self, display: str) -> str:
        raw = str(display or "").strip()
        if raw in self._converter_symbol_map:
            return self._converter_symbol_map[raw]

        # Fallback parsing (in case of old saved UI values)
        if "(" in raw and raw.endswith(")"):
            inside = raw.split("(")[-1].rstrip(")").strip()
            if inside:
                return inside.upper()
        if "•" in raw:
            left = raw.split("•", 1)[0].strip()
            if left:
                return left.upper()
        return raw.upper()

    def _refresh_symbol_menus(self) -> None:
        # Build signature to avoid reconfiguring menus every refresh
        try:
            keys = sorted([k for k in self.currencies.keys() if k])
            sig = "|".join(keys[:2000])
            if sig == self._symbol_menu_sig:
                return
            self._symbol_menu_sig = sig
        except Exception:
            keys = sorted(list(self.currencies.keys()))

        # Build display list
        display_values: List[str] = []
        mapping: Dict[str, str] = {}

        # Converter gets a pseudo TOMAN unit
        toman_display = self._symbol_to_display("TOMAN", None)
        display_values.append(toman_display)
        mapping[toman_display] = "TOMAN"

        for sym in keys:
            d = self.currencies.get(sym, {})
            disp = self._symbol_to_display(sym, d)
            display_values.append(disp)
            mapping[disp] = str(sym).upper().strip()

        self._converter_symbol_map = mapping

        # Update menus safely
        try:
            if self.converter_from_menu is not None:
                self.converter_from_menu.configure(values=display_values)
                try:
                    self.converter_from_menu.configure(dropdown_font=self._ui_font(13, False))
                except Exception:
                    pass
            if self.converter_to_menu is not None:
                self.converter_to_menu.configure(values=display_values)
                try:
                    self.converter_to_menu.configure(dropdown_font=self._ui_font(13, False))
                except Exception:
                    pass

            # History / widgets menus: no TOMAN
            hw_values = [v for v in display_values if mapping.get(v) != "TOMAN"]

            if self.history_symbol_menu is not None:
                self.history_symbol_menu.configure(values=hw_values)
                try:
                    self.history_symbol_menu.configure(dropdown_font=self._ui_font(13, False))
                except Exception:
                    pass
            if self.widgets_symbol_menu is not None:
                self.widgets_symbol_menu.configure(values=hw_values)
                try:
                    self.widgets_symbol_menu.configure(dropdown_font=self._ui_font(13, False))
                except Exception:
                    pass
        except Exception:
            pass

        # Ensure vars are valid
        try:
            if self.converter_from_var is not None and self.converter_from_var.get() not in display_values:
                self.converter_from_var.set(display_values[1] if len(display_values) > 1 else display_values[0])
            if self.converter_to_var is not None and self.converter_to_var.get() not in display_values:
                self.converter_to_var.set(display_values[2] if len(display_values) > 2 else display_values[0])
            if self.history_symbol_var is not None:
                # Keep previously selected symbol if possible
                cur = self.history_symbol_var.get()
                if cur not in display_values:
                    # pick USD if exists
                    pick = None
                    for v, s in mapping.items():
                        if s == "USD":
                            pick = v
                            break
                    self.history_symbol_var.set(pick or (display_values[1] if len(display_values) > 1 else display_values[0]))
            if self.widgets_symbol_var is not None and self.widgets_symbol_var.get() not in display_values:
                self.widgets_symbol_var.set(display_values[1] if len(display_values) > 1 else display_values[0])
        except Exception:
            pass

    # ----- History -----

    def _history_period_options(self) -> Tuple[List[str], Dict[str, int]]:
        opts = [
            ("period_1h", 1 * 3600),
            ("period_6h", 6 * 3600),
            ("period_24h", 24 * 3600),
            ("period_7d", 7 * 86400),
        ]
        display = [self._t(k) for k, _ in opts]
        mapping = {self._t(k): int(sec) for k, sec in opts}
        return display, mapping

    
    def _create_history_section(self) -> None:
        """Session Tracker (replaces chart)."""
        row = self._next_row()
        card = self._create_glass_card(self.scroll_frame, glass_level=2)
        card.grid(row=row, column=0, sticky="ew", pady=(0, 20))

        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=18)

        title_txt = ("📌 ردیاب جلسه" if self.language == "fa" else "📌 Session Tracker")
        title = ctk.CTkLabel(
            content,
            text=title_txt,
            font=self._ui_font(18, True),
            text_color=(colors.text_primary_light, colors.text_primary_dark),
            anchor="e" if self.rtl else "w",
        )
        title.pack(fill="x")

        hint = ctk.CTkLabel(
            content,
            text=("این بخش فقط از زمان باز بودن برنامه داده جمع میکند." if self.language == "fa" else "Tracks changes only while the app is running."),
            font=self._ui_font(12, False),
            text_color=(colors.text_secondary_light, colors.text_secondary_dark),
            anchor="e" if self.rtl else "w",
            justify="right" if self.rtl else "left",
            wraplength=640,
        )
        hint.pack(fill="x", pady=(8, 0))

        self.session_tracker_label = ctk.CTkLabel(
            content,
            text="—",
            font=self._ui_font(13, False),
            text_color=(colors.text_primary_light, colors.text_primary_dark),
            anchor="e" if self.rtl else "w",
            justify="right" if self.rtl else "left",
        )
        self.session_tracker_label.pack(fill="x", pady=(12, 0))

        # Disable old history controls for safety
        self.history_symbol_menu = None
        self.history_period_menu = None
        self.history_sparkline = None
        self.history_stats_label = None

    def _update_session_tracker(self) -> None:
        try:
            watch: List[str] = []
            watch.extend([str(s).upper().strip() for s in (self.featured_symbols or []) if s])
            watch.extend([str(s).upper().strip() for s in (self.user_portfolio or set()) if s])
            watch = [s for s in watch if s and s in self.currencies]
            if not watch:
                if getattr(self, "session_tracker_label", None) is not None:
                    self.session_tracker_label.configure(text="—")
                return

            # Update session maps
            for sym in watch:
                d = self.currencies.get(sym) or {}
                try:
                    price = float(d.get("price", 0) or 0)
                except Exception:
                    continue
                if price <= 0:
                    continue

                if sym not in self._session_open:
                    self._session_open[sym] = price
                    self._session_min[sym] = price
                    self._session_max[sym] = price
                else:
                    self._session_min[sym] = min(self._session_min.get(sym, price), price)
                    self._session_max[sym] = max(self._session_max.get(sym, price), price)

            # Build summary lines (top movers in this session)
            items = []
            for sym in watch:
                if sym not in self._session_open:
                    continue
                open_p = float(self._session_open.get(sym, 0) or 0)
                cur_p = float(self.currencies.get(sym, {}).get("price", 0) or 0)
                if open_p <= 0 or cur_p <= 0:
                    continue
                ch_pct = (cur_p - open_p) / open_p * 100.0
                items.append((sym, ch_pct, cur_p))

            items.sort(key=lambda x: x[1], reverse=True)
            top = items[:5]
            bottom = list(reversed(items[-5:])) if len(items) > 5 else items[-5:]

            lines: List[str] = []
            hdr = ("از شروع جلسه" if self.language == "fa" else "Since session start")
            lines.append(hdr + f" • {self._t('last_update', time=getattr(self, 'last_update', '—'))}")
            lines.append("")

            if top:
                lines.append(("بیشترین رشد:" if self.language == "fa" else "Top gainers:"))
                for sym, ch_pct, cur_p in top:
                    lines.append(f"  ▲ {sym}: {ch_pct:+.2f}%  •  {CurrencyCardWidget._format_price(cur_p)}")
                lines.append("")

            if bottom:
                lines.append(("بیشترین افت:" if self.language == "fa" else "Top losers:"))
                for sym, ch_pct, cur_p in bottom:
                    lines.append(f"  ▼ {sym}: {ch_pct:+.2f}%  •  {CurrencyCardWidget._format_price(cur_p)}")

            txt = "\n".join(lines).strip()
            if getattr(self, "session_tracker_label", None) is not None:
                self.session_tracker_label.configure(text=txt)
        except Exception:
            pass


    def _on_history_selection_changed(self) -> None:
        try:
            if self.history_symbol_var is None or self.history_period_var is None:
                return
            sym = self._display_to_symbol_value(self.history_symbol_var.get())
            period_seconds = int(self._history_period_map.get(self.history_period_var.get(), 24 * 3600))
            self._history_symbol = sym
            self._history_period_seconds = period_seconds
            self._load_history_async(sym, period_seconds)
        except Exception:
            pass

    def _load_history_async(self, sym: str, period_seconds: int) -> None:
        if self.history_stats_label is not None:
            self.history_stats_label.configure(text=self._t("history_loading"))
        if self.history_sparkline is not None:
            self.history_sparkline.clear()

        since_ts = time.time() - float(max(60, period_seconds))
        self._history_last_loaded = time.time()

        def worker():
            points = db_manager.load_price_history(sym, since_ts=since_ts, limit=2000)

            # If we do not have enough cached data and the symbol is a supported crypto,
            # fetch a real market chart once and persist it for future sessions.
            if len(points) < 10:
                try:
                    if str(sym).upper().strip() in getattr(api_manager, "_COINGECKO_ID_MAP", {}):
                        fetched = api_manager.fetch_crypto_history(str(sym).upper().strip(), period_seconds=period_seconds)
                        if fetched:
                            db_manager.insert_price_history_bulk([(str(sym).upper().strip(), ts, price) for ts, price in fetched])
                            points = db_manager.load_price_history(sym, since_ts=since_ts, limit=2000)
                except Exception:
                    pass

            return points

        fut = None
        try:
            fut = self.executor.submit(worker)
        except Exception:
            return

        def done(_):
            try:
                points = fut.result() if fut else []
            except Exception:
                points = []
            self._enqueue_ui(lambda: self._apply_history_points(sym, points))

        try:
            fut.add_done_callback(done)  # type: ignore[union-attr]
        except Exception:
            self._enqueue_ui(lambda: done(None))

    def _apply_history_points(self, sym: str, points: List[Tuple[float, float]]) -> None:
        try:
            self._history_points.clear()
            for ts, price in points[-config.HISTORY_MAX_POINTS :]:
                self._history_points.append((float(ts), float(price)))
            self._update_history_chart()
        except Exception:
            pass

    def _update_history_chart(self) -> None:
        if self.history_sparkline is None or self.history_stats_label is None:
            return
        if not self._history_points:
            self.history_sparkline.clear()
            self.history_stats_label.configure(text=self._t("history_no_data"))
            return

        values = [p for _, p in self._history_points]
        self.history_sparkline.set_values(values)

        first = values[0]
        last = values[-1]
        mn = min(values)
        mx = max(values)
        ch = last - first
        ch_pct = (ch / first * 100.0) if abs(first) > 1e-9 else 0.0

        stats = f"{self._t('history_change')}: {ch_pct:+.2f}%   •   {self._t('history_min')}: {CurrencyCardWidget._format_price(mn)}   •   {self._t('history_max')}: {CurrencyCardWidget._format_price(mx)}"
        self.history_stats_label.configure(text=stats)

    def _history_live_append(self) -> None:
        """Append the latest point for the selected symbol and redraw quickly."""
        sym = str(self._history_symbol or "").upper().strip()
        if not sym or sym not in self.currencies:
            return
        data = self.currencies.get(sym, {})
        try:
            price = float(data.get("price", 0) or 0)
        except Exception:
            return
        if price <= 0:
            return
        self._history_points.append((time.time(), float(price)))
        self._update_history_chart()

    # ----- Converter -----



    def _record_history_snapshots(self) -> None:
        """Persist snapshots to SQLite (fast, async)."""
        now = time.time()

        watch: Set[str] = set()
        try:
            watch.update([str(s).upper().strip() for s in self.featured_symbols])
            watch.update([str(s).upper().strip() for s in self.user_portfolio])
        except Exception:
            pass

        # Ensure converter + selected history symbol work well
        watch.add("USD")
        try:
            if self._history_symbol:
                watch.add(str(self._history_symbol).upper().strip())
        except Exception:
            pass

        rows: List[Tuple[str, float, float]] = []
        for sym in watch:
            d = self.currencies.get(sym)
            if not d:
                continue
            try:
                price = float(d.get("price", 0) or 0)
            except Exception:
                continue
            if price <= 0:
                continue
            rows.append((sym, float(now), float(price)))

        if rows:
            try:
                self.executor.submit(db_manager.insert_price_history_bulk, rows)
            except Exception:
                pass

        # Prune occasionally (every ~6 hours)
        try:
            if now - float(getattr(self, "_last_history_prune", 0.0)) > 6 * 3600:
                self._last_history_prune = float(now)
                self.executor.submit(db_manager.prune_price_history, int(config.HISTORY_RETENTION_DAYS))
        except Exception:
            pass

    def _create_converter_section(self) -> None:
        row = self._next_row()
        card = self._create_glass_card(self.scroll_frame, glass_level=2)
        card.grid(row=row, column=0, sticky="ew", pady=(0, 20))

        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=18)

        title = ctk.CTkLabel(
            content,
            text=self._t("section_converter"),
            font=self._ui_font(18, True),
            text_color=(colors.text_primary_light, colors.text_primary_dark),
            anchor="e" if self.rtl else "w",
        )
        title.pack(fill="x")
        self.converter_title_label = title

        rowf = ctk.CTkFrame(content, fg_color="transparent")
        rowf.pack(fill="x", pady=(12, 0))
        rowf.grid_columnconfigure((0, 1, 2), weight=1)

        # Amount
        amount_block = ctk.CTkFrame(rowf, fg_color="transparent")
        amount_block.grid(row=0, column=0, sticky="ew", padx=(0, 12) if not self.rtl else (12, 0))

        amount_label = ctk.CTkLabel(
            amount_block,
            text=self._t("converter_amount"),
            font=self._ui_font(12, True),
            text_color=(colors.text_secondary_light, colors.text_secondary_dark),
            anchor="e" if self.rtl else "w",
        )
        amount_label.pack(fill="x")

        self.converter_amount_var = ctk.StringVar(value="1")
        amount_entry = ctk.CTkEntry(
            amount_block,
            textvariable=self.converter_amount_var,
            height=36,
            corner_radius=10,
            fg_color=(colors.glass_light, colors.glass_dark),
            border_color=(colors.border_light, colors.border_dark),
            text_color=(colors.text_primary_light, colors.text_primary_dark),
            font=self._ui_font(13, False),
            justify="right" if self.rtl else "left",
        )
        amount_entry.pack(fill="x", pady=(6, 0))
        try:
            self.converter_amount_var.trace_add("write", lambda *args: self._update_converter_result())
        except Exception:
            pass

        # From
        from_block = ctk.CTkFrame(rowf, fg_color="transparent")
        from_block.grid(row=0, column=1, sticky="ew", padx=12)

        from_label = ctk.CTkLabel(
            from_block,
            text=self._t("converter_from"),
            font=self._ui_font(12, True),
            text_color=(colors.text_secondary_light, colors.text_secondary_dark),
            anchor="e" if self.rtl else "w",
        )
        from_label.pack(fill="x")

        self.converter_from_var = ctk.StringVar(value="USD")
        self.converter_from_menu = ctk.CTkOptionMenu(
            from_block,
            variable=self.converter_from_var,
            values=["USD"],
            width=220,
            height=36,
            corner_radius=10,
            fg_color=(colors.glass_light, colors.glass_dark),
            button_color=(colors.accent_blue, colors.accent_blue),
            button_hover_color=(colors.accent_blue_hover, colors.accent_blue_hover),
            text_color=(colors.text_primary_light, colors.text_primary_dark),
            dropdown_fg_color=(colors.glass_light, colors.glass_dark),
            dropdown_text_color=(colors.text_primary_light, colors.text_primary_dark),
            font=self._ui_font(13, False),
            command=lambda _: self._update_converter_result(),
        )
        self.converter_from_menu.pack(fill="x", pady=(6, 0))

        # To
        to_block = ctk.CTkFrame(rowf, fg_color="transparent")
        to_block.grid(row=0, column=2, sticky="ew")

        to_label = ctk.CTkLabel(
            to_block,
            text=self._t("converter_to"),
            font=self._ui_font(12, True),
            text_color=(colors.text_secondary_light, colors.text_secondary_dark),
            anchor="e" if self.rtl else "w",
        )
        to_label.pack(fill="x")

        self.converter_to_var = ctk.StringVar(value="EUR")
        self.converter_to_menu = ctk.CTkOptionMenu(
            to_block,
            variable=self.converter_to_var,
            values=["EUR"],
            width=220,
            height=36,
            corner_radius=10,
            fg_color=(colors.glass_light, colors.glass_dark),
            button_color=(colors.accent_blue, colors.accent_blue),
            button_hover_color=(colors.accent_blue_hover, colors.accent_blue_hover),
            text_color=(colors.text_primary_light, colors.text_primary_dark),
            dropdown_fg_color=(colors.glass_light, colors.glass_dark),
            dropdown_text_color=(colors.text_primary_light, colors.text_primary_dark),
            font=self._ui_font(13, False),
            command=lambda _: self._update_converter_result(),
        )
        self.converter_to_menu.pack(fill="x", pady=(6, 0))

        self.converter_result_label = ctk.CTkLabel(
            content,
            text="—",
            font=self._ui_font(16, True),
            text_color=(colors.text_primary_light, colors.text_primary_dark),
            anchor="e" if self.rtl else "w",
        )
        self.converter_result_label.pack(fill="x", pady=(12, 0))

        # We will fill menu values after first data load
        self.after(400, self._refresh_symbol_menus)

    def _usd_toman_rate(self) -> Optional[float]:
        d = self.currencies.get("USD")
        if not d:
            return None
        try:
            unit = str(d.get("unit", "")).lower()
            price = float(d.get("price", 0) or 0)
        except Exception:
            return None
        if price <= 0:
            return None
        # If USD itself is already in toman/rial, treat it as toman
        if "ریال" in unit and "تومان" not in unit:
            return price / 10.0
        return price

    def _value_in_toman(self, sym: str) -> Optional[float]:
        s = str(sym or "").upper().strip()
        if s == "TOMAN":
            return 1.0

        data = self.currencies.get(s)
        if not data:
            return None

        try:
            price = float(data.get("price", 0) or 0)
        except Exception:
            return None
        if price <= 0:
            return None

        unit = str(data.get("unit", "")).lower()

        # Toman / Rial
        if "تومان" in unit or "toman" in unit:
            return price
        if "ریال" in unit or "rial" in unit:
            return price / 10.0

        # Assume USD-priced
        usd_toman = self._usd_toman_rate()
        if usd_toman is None:
            return None
        return price * usd_toman

    def _update_converter_result(self) -> None:
        if self.converter_result_label is None:
            return

        try:
            amount_raw = (self.converter_amount_var.get() if self.converter_amount_var is not None else "1").strip()
            amount_raw = amount_raw.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))
            amount_raw = amount_raw.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
            amount = float(amount_raw)
        except Exception:
            self.converter_result_label.configure(text="—")
            return

        from_sym = self._display_to_symbol_value(self.converter_from_var.get() if self.converter_from_var is not None else "USD")
        to_sym = self._display_to_symbol_value(self.converter_to_var.get() if self.converter_to_var is not None else "EUR")

        v_from = self._value_in_toman(from_sym)
        v_to = self._value_in_toman(to_sym)

        if v_from is None or v_to is None or v_to == 0:
            self.converter_result_label.configure(text=self._t("converter_need_usd"))
            return

        out = amount * v_from / v_to

        # Pretty output
        out_s = CurrencyCardWidget._format_price(out)
        self.converter_result_label.configure(text=f"{out_s}  →  {to_sym}")

    # ----- Widgets -----

    def _widget_type_options(self) -> Tuple[List[str], Dict[str, str]]:
        opts = [
            ("widget_type_price", "price"),
            ("widget_type_movers", "movers"),
            ("widget_type_portfolio", "portfolio"),
        ]
        values = [self._t(k) for k, _ in opts]
        mapping = {self._t(k): t for k, t in opts}
        return values, mapping

    def _create_widgets_section(self) -> None:
        row = self._next_row()
        card = self._create_glass_card(self.scroll_frame, glass_level=2)
        card.grid(row=row, column=0, sticky="ew", pady=(0, 20))

        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=18)

        title = ctk.CTkLabel(
            content,
            text=self._t("section_widgets"),
            font=self._ui_font(18, True),
            text_color=(colors.text_primary_light, colors.text_primary_dark),
            anchor="e" if self.rtl else "w",
        )
        title.pack(fill="x")
        self.widgets_title_label = title

        add_title = ctk.CTkLabel(
            content,
            text=self._t("widgets_add_title"),
            font=self._ui_font(12, True),
            text_color=(colors.text_secondary_light, colors.text_secondary_dark),
            anchor="e" if self.rtl else "w",
        )
        add_title.pack(fill="x", pady=(10, 0))

        rowf = ctk.CTkFrame(content, fg_color="transparent")
        rowf.pack(fill="x", pady=(8, 0))
        rowf.grid_columnconfigure((0, 1, 2), weight=1)

        # Type
        type_block = ctk.CTkFrame(rowf, fg_color="transparent")
        type_block.grid(row=0, column=0, sticky="ew", padx=(0, 12) if not self.rtl else (12, 0))

        type_lbl = ctk.CTkLabel(
            type_block,
            text=self._t("widgets_type"),
            font=self._ui_font(12, True),
            text_color=(colors.text_secondary_light, colors.text_secondary_dark),
            anchor="e" if self.rtl else "w",
        )
        type_lbl.pack(fill="x")

        type_values, self._widget_type_map = self._widget_type_options()
        self.widgets_type_var = ctk.StringVar(value=type_values[0])
        self.widgets_type_menu = ctk.CTkOptionMenu(
            type_block,
            variable=self.widgets_type_var,
            values=type_values,
            width=220,
            height=36,
            corner_radius=10,
            fg_color=(colors.glass_light, colors.glass_dark),
            button_color=(colors.accent_blue, colors.accent_blue),
            button_hover_color=(colors.accent_blue_hover, colors.accent_blue_hover),
            text_color=(colors.text_primary_light, colors.text_primary_dark),
            dropdown_fg_color=(colors.glass_light, colors.glass_dark),
            dropdown_text_color=(colors.text_primary_light, colors.text_primary_dark),
            font=self._ui_font(13, False),
            command=lambda _: self._on_widget_type_changed(),
        )
        self.widgets_type_menu.pack(fill="x", pady=(6, 0))

        # Symbol (only for price widget)
        sym_block = ctk.CTkFrame(rowf, fg_color="transparent")
        sym_block.grid(row=0, column=1, sticky="ew", padx=12)

        sym_lbl = ctk.CTkLabel(
            sym_block,
            text=self._t("widgets_symbol"),
            font=self._ui_font(12, True),
            text_color=(colors.text_secondary_light, colors.text_secondary_dark),
            anchor="e" if self.rtl else "w",
        )
        sym_lbl.pack(fill="x")

        self.widgets_symbol_var = ctk.StringVar(value="USD")
        self.widgets_symbol_menu = ctk.CTkOptionMenu(
            sym_block,
            variable=self.widgets_symbol_var,
            values=["USD"],
            width=220,
            height=36,
            corner_radius=10,
            fg_color=(colors.glass_light, colors.glass_dark),
            button_color=(colors.accent_blue, colors.accent_blue),
            button_hover_color=(colors.accent_blue_hover, colors.accent_blue_hover),
            text_color=(colors.text_primary_light, colors.text_primary_dark),
            dropdown_fg_color=(colors.glass_light, colors.glass_dark),
            dropdown_text_color=(colors.text_primary_light, colors.text_primary_dark),
            font=self._ui_font(13, False),
        )
        self.widgets_symbol_menu.pack(fill="x", pady=(6, 0))

        # Add button
        btn_block = ctk.CTkFrame(rowf, fg_color="transparent")
        btn_block.grid(row=0, column=2, sticky="ew")

        btn_dummy = ctk.CTkLabel(btn_block, text="", fg_color="transparent")
        btn_dummy.pack(fill="x")  # spacing line

        add_btn = self._create_button(
            btn_block,
            text=self._t("btn_add_widget"),
            command=self._add_desktop_widget,
            style="primary",
            width=180,
        )
        add_btn.pack(anchor="e" if self.rtl else "w", pady=(6, 0))

        # Active list
        active_title = ctk.CTkLabel(
            content,
            text=self._t("widgets_active_title"),
            font=self._ui_font(12, True),
            text_color=(colors.text_secondary_light, colors.text_secondary_dark),
            anchor="e" if self.rtl else "w",
        )
        active_title.pack(fill="x", pady=(16, 0))

        self.widgets_active_list = ctk.CTkFrame(content, fg_color="transparent")
        self.widgets_active_list.pack(fill="x", pady=(8, 0))

        self._refresh_widgets_ui()
        self.after(400, self._refresh_symbol_menus)

    def _on_widget_type_changed(self) -> None:
        # Disable symbol menu for non-price widgets
        try:
            t_disp = self.widgets_type_var.get() if self.widgets_type_var is not None else ""
            t = self._widget_type_map.get(t_disp, "price")
            if self.widgets_symbol_menu is None:
                return
            if t == "price":
                self.widgets_symbol_menu.configure(state="normal")
            else:
                self.widgets_symbol_menu.configure(state="disabled")
        except Exception:
            pass

    def _add_desktop_widget(self) -> None:
        try:
            t_disp = self.widgets_type_var.get() if self.widgets_type_var is not None else ""
            w_type = self._widget_type_map.get(t_disp, "price")

            sym = "USD"
            if w_type == "price":
                sym = self._display_to_symbol_value(self.widgets_symbol_var.get() if self.widgets_symbol_var is not None else "USD")

            self.widget_manager.add(w_type, sym)
            self._refresh_widgets_ui()
        except Exception:
            pass

    def _refresh_widgets_ui(self) -> None:
        if self.widgets_active_list is None:
            return

        for child in list(self.widgets_active_list.winfo_children()):
            try:
                child.destroy()
            except Exception:
                pass

        items = list(self.widget_manager.widgets.items())
        if not items:
            empty = ctk.CTkLabel(
                self.widgets_active_list,
                text="—",
                font=self._ui_font(12, False),
                text_color=(colors.text_tertiary_light, colors.text_tertiary_dark),
                anchor="e" if self.rtl else "w",
            )
            empty.pack(fill="x")
            return

        for wid, win in items:
            row = ctk.CTkFrame(self.widgets_active_list, fg_color="transparent")
            row.pack(fill="x", pady=4)

            label_text = wid
            try:
                if win.cfg.widget_type == "price":
                    label_text = f"{wid} • {win.cfg.symbol}"
                elif win.cfg.widget_type == "movers":
                    label_text = f"{wid} • {self._t('widget_type_movers')}"
                elif win.cfg.widget_type == "portfolio":
                    label_text = f"{wid} • {self._t('widget_type_portfolio')}"
                else:
                    label_text = f"{wid} • {win.cfg.widget_type}"
            except Exception:
                pass

            lbl = ctk.CTkLabel(
                row,
                text=label_text,
                font=self._ui_font(12, False),
                text_color=(colors.text_primary_light, colors.text_primary_dark),
                anchor="e" if self.rtl else "w",
            )
            lbl.pack(side="right" if self.rtl else "left", fill="x", expand=True)

            btn = self._create_button(
                row,
                text=self._t("btn_remove_widget"),
                command=lambda _wid=wid: self.widget_manager.remove(_wid),
                style="secondary",
                width=100,
            )
            btn.pack(side="left" if self.rtl else "right")





    def _create_portfolio_section(self) -> None:
        # Header + inline add panel + portfolio cards
        row = self._next_row(3)

        header = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        header.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        header.grid_columnconfigure(0, weight=1)

        self.portfolio_title_label = ctk.CTkLabel(
            header,
            text=self._t("section_portfolio"),
            font=self._ui_font(24, True),
            text_color=(colors.text_primary_light, colors.text_primary_dark),
            anchor="e" if self.rtl else "w",
        )
        self.portfolio_title_label.grid(row=0, column=0, sticky="ew")

        sort_controls = self._create_portfolio_sort_controls(header)
        sort_controls.grid(row=0, column=1, sticky="w" if self.rtl else "e")

        # Quick filter (doesn't affect saved portfolio; only filters the view)
        self.portfolio_filter_var = ctk.StringVar(value="")
        self.portfolio_filter_entry = ctk.CTkEntry(
            header,
            textvariable=self.portfolio_filter_var,
            placeholder_text=self._t("placeholder_portfolio_filter"),
            height=34,
            corner_radius=10,
            fg_color=(colors.glass_light, colors.glass_dark),
            border_color=(colors.border_light, colors.border_dark),
            text_color=(colors.text_primary_light, colors.text_primary_dark),
            font=self._ui_font(12, False),
            justify="right" if self.rtl else "left",
        )
        self.portfolio_filter_entry.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        try:
            self.portfolio_filter_var.trace_add("write", lambda *args: self._debounced_portfolio_filter())
        except Exception:
            pass

        self.add_currency_panel = self._create_add_currency_panel(self.scroll_frame)
        self.add_currency_panel.grid(row=row + 1, column=0, sticky="ew", pady=(0, 14))

        self.portfolio_container = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.portfolio_container.grid(row=row + 2, column=0, sticky="ew", pady=(0, 26))
        for i in range(4):
            self.portfolio_container.grid_columnconfigure(i, weight=1)

    def _create_add_currency_panel(self, parent: ctk.CTkBaseClass) -> ctk.CTkFrame:
        """Inline "Add Currency" controls shown inside the Portfolio section."""
        card = self._create_glass_card(parent, glass_level=2)
        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=18, pady=16)

        self.portfolio_add_title_label = ctk.CTkLabel(
            content,
            text=self._t("portfolio_add_title"),
            font=self._ui_font(12, True),
            text_color=(colors.text_secondary_light, colors.text_secondary_dark),
            anchor="e" if self.rtl else "w",
            justify="right" if self.rtl else "left",
        )
        self.portfolio_add_title_label.pack(fill="x")

        row = ctk.CTkFrame(content, fg_color="transparent")
        row.pack(fill="x", pady=(10, 0))
        self.add_currency_row = row

        # Search
        self.selector_search_var = ctk.StringVar(value="")
        self.selector_search_entry = ctk.CTkEntry(
            row,
            width=240,
            height=36,
            corner_radius=10,
            border_width=1,
            fg_color=(colors.glass_light, colors.glass_dark),
            border_color=(colors.border_light, colors.border_dark),
            text_color=(colors.text_primary_light, colors.text_primary_dark),
            placeholder_text=self._t("placeholder_search"),
            textvariable=self.selector_search_var,
            font=self._ui_font(13, False),
            justify="right" if self.rtl else "left",
        )

        # Combo
        self.currency_selector = ctk.CTkComboBox(
            row,
            font=self._ui_font(13, False),
            justify="right" if self.rtl else "left",
            values=[self._t("status_connecting")],
            state="readonly",
            width=300,
            height=36,
            corner_radius=10,
            border_width=1,
            fg_color=(colors.glass_light, colors.glass_dark),
            border_color=(colors.border_light, colors.border_dark),
            button_color=(colors.accent_blue, colors.accent_blue),
            button_hover_color=(colors.accent_blue_hover, colors.accent_blue_hover),
            dropdown_fg_color=(colors.glass_light, colors.glass_dark),
            dropdown_text_color=(colors.text_primary_light, colors.text_primary_dark),
            text_color=(colors.text_primary_light, colors.text_primary_dark),
        )
        try:
            self.currency_selector.configure(dropdown_font=self._ui_font(13, False))
        except Exception:
            pass

        self.add_currency_inline_btn = self._create_button(
            row,
            text=self._t("btn_add"),
            command=self._add_selected_currency,
            style="primary",
            width=110,
        )

        # Responsive placement + RTL/LTR ordering
        self._regrid_add_currency_panel()

        self.selector_search_var.trace_add("write", lambda *_: self._debounced_update_currency_selector())
        return card


    def _regrid_add_currency_panel(self) -> None:
        """Re-apply the grid for the inline add panel (supports RTL/LTR switching)."""
        row = getattr(self, "add_currency_row", None)
        if row is None:
            return

        entry = getattr(self, "selector_search_entry", None)
        combo = getattr(self, "currency_selector", None)
        btn = getattr(self, "add_currency_inline_btn", None)

        # Forget previous grid placements
        for w in (entry, combo, btn):
            try:
                if w is not None:
                    w.grid_forget()
            except Exception:
                pass

        # Reset weights
        try:
            for i in range(3):
                row.grid_columnconfigure(i, weight=0)
        except Exception:
            pass

        if self.rtl:
            # [button][combo][search]  (search at the far right)
            row.grid_columnconfigure(0, weight=0)
            row.grid_columnconfigure(1, weight=1)
            row.grid_columnconfigure(2, weight=1)

            if btn is not None:
                btn.grid(row=0, column=0, sticky="w")
            if combo is not None:
                combo.grid(row=0, column=1, sticky="ew", padx=(10, 10))
            if entry is not None:
                entry.grid(row=0, column=2, sticky="ew")
        else:
            # [search][combo][button]
            row.grid_columnconfigure(0, weight=1)
            row.grid_columnconfigure(1, weight=1)
            row.grid_columnconfigure(2, weight=0)

            if entry is not None:
                entry.grid(row=0, column=0, sticky="ew")
            if combo is not None:
                combo.grid(row=0, column=1, sticky="ew", padx=(10, 10))
            if btn is not None:
                btn.grid(row=0, column=2, sticky="e")

    def _create_portfolio_sort_controls(self, parent: ctk.CTkBaseClass) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(
            parent,
            fg_color=(colors.glass_overlay_light, colors.glass_overlay_dark),
            corner_radius=12,
            border_width=1,
            border_color=(colors.border_light, colors.border_dark),
            height=50,
        )
        frame.pack_propagate(False)

        content = ctk.CTkFrame(frame, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=12, pady=8)

        self.sort_label = ctk.CTkLabel(
            content,
            text=self._t("sort"),
            font=self._ui_font(12, True),
            text_color=(colors.text_secondary_light, colors.text_secondary_dark),
        )
        self.sort_label.pack(side="left", padx=(0, 8))

        self.portfolio_sort_var = ctk.StringVar(value=self._sort_key_to_display(self.portfolio_sort_mode_key))

        self.portfolio_sort_menu = ctk.CTkOptionMenu(
            content,
            variable=self.portfolio_sort_var,
            values=self._get_sort_display_values(),
            command=self._on_portfolio_sort_changed,
            width=135,
            height=34,
            corner_radius=8,
            fg_color=(colors.glass_light, colors.glass_dark),
            button_color=(colors.accent_blue, colors.accent_blue),
            button_hover_color=(colors.accent_blue_hover, colors.accent_blue_hover),
            text_color=(colors.text_primary_light, colors.text_primary_dark),
            dropdown_fg_color=(colors.glass_light, colors.glass_dark),
            dropdown_text_color=(colors.text_primary_light, colors.text_primary_dark),
            font=self._ui_font(13, False),
        )
        self.portfolio_sort_menu.pack(side="left")

        return frame


    def _create_controls_section(self) -> None:
        row = self._next_row()
        card = self._create_glass_card(self.scroll_frame, height=165, glass_level=2)
        card.grid(row=row, column=0, sticky="ew", pady=(0, 20))

        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=18)

        self.controls_title_label = ctk.CTkLabel(
            content,
            text=self._t("section_controls"),
            font=self._ui_font(18, True),
            text_color=(colors.text_primary_light, colors.text_primary_dark),
            anchor="e" if self.rtl else "w",
        )
        self.controls_title_label.pack(fill="x")

        btn_row = ctk.CTkFrame(content, fg_color="transparent")
        btn_row.pack(anchor="w", pady=(12, 6))

        self.refresh_btn = self._create_button(btn_row, text=self._t("btn_refresh"), command=self._manual_refresh, style="primary", width=130)
        self.refresh_btn.pack(side="left", padx=(0, 10))

        self.test_btn = self._create_button(btn_row, text=self._t("btn_test_api"), command=self._test_api_connection, style="secondary", width=120)
        self.test_btn.pack(side="left", padx=(0, 10))

        self.export_btn = self._create_button(btn_row, text=self._t("btn_export_csv"), command=self._export_csv, style="secondary", width=130)
        self.export_btn.pack(side="left", padx=(0, 10))

        self.copy_btn = self._create_button(btn_row, text=self._t("btn_copy"), command=self._copy_to_clipboard, style="secondary", width=100)
        self.copy_btn.pack(side="left", padx=(0, 14))

        self.auto_refresh_var = ctk.BooleanVar(value=True)
        self.auto_refresh_checkbox = ctk.CTkCheckBox(
            btn_row,
            text=self._t("auto_refresh"),
            variable=self.auto_refresh_var,
            command=self._toggle_auto_refresh,
            font=self._ui_font(13, False),
            text_color=(colors.text_primary_light, colors.text_primary_dark),
            fg_color=(colors.accent_blue, colors.accent_blue),
            hover_color=(colors.accent_blue_hover, colors.accent_blue_hover),
            border_color=(colors.border_light, colors.border_dark),
        )
        self.auto_refresh_checkbox.pack(side="left")

        self.last_update_label = ctk.CTkLabel(
            content,
            text=self._t("last_update", time=self.last_update),
            font=self._ui_font(12, False),
            text_color=(colors.text_secondary_light, colors.text_secondary_dark),
            anchor="e" if self.rtl else "w",
        )
        self.last_update_label.pack(fill="x", pady=(8, 0))


    def _create_settings_section(self) -> None:
        row = self._next_row()
        # Let the card size itself (avoids cramped/overlapping controls)
        card = self._create_glass_card(self.scroll_frame, glass_level=2)
        card.grid(row=row, column=0, sticky="ew", pady=(0, 20))

        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=18)

        self.settings_title_label = ctk.CTkLabel(
            content,
            text=self._t("section_settings"),
            font=self._ui_font(18, True),
            text_color=(colors.text_primary_light, colors.text_primary_dark),
            anchor="e" if self.rtl else "w",
        )
        self.settings_title_label.pack(fill="x")

        # Row 1: refresh interval + language
        top = ctk.CTkFrame(content, fg_color="transparent")
        top.pack(fill="x", pady=(12, 0))
        top.grid_columnconfigure((0, 1, 2), weight=1)

        # Refresh interval
        refresh_block = ctk.CTkFrame(top, fg_color="transparent")
        refresh_block.grid(row=0, column=0, sticky="ew", padx=(0, 14) if not self.rtl else (14, 0))

        self.refresh_interval_title_label = ctk.CTkLabel(
            refresh_block,
            text=self._t("refresh_interval"),
            font=self._ui_font(12, True),
            text_color=(colors.text_primary_light, colors.text_primary_dark),
            anchor="e" if self.rtl else "w",
        )
        self.refresh_interval_title_label.pack(fill="x")

        self.refresh_interval_var = ctk.StringVar(value=self._format_interval(self.refresh_interval_seconds))
        self.refresh_interval_menu = ctk.CTkOptionMenu(
            refresh_block,
            variable=self.refresh_interval_var,
            values=self._interval_choices(),
            width=200,
            height=36,
            corner_radius=10,
            fg_color=(colors.glass_light, colors.glass_dark),
            button_color=(colors.accent_blue, colors.accent_blue),
            button_hover_color=(colors.accent_blue_hover, colors.accent_blue_hover),
            text_color=(colors.text_primary_light, colors.text_primary_dark),
            dropdown_fg_color=(colors.glass_light, colors.glass_dark),
            dropdown_text_color=(colors.text_primary_light, colors.text_primary_dark),
            font=self._ui_font(13, False),
            command=lambda _: self._on_refresh_interval_changed(),
        )
        self.refresh_interval_menu.pack(anchor="e" if self.rtl else "w", pady=(6, 0))
        try:
            self.refresh_interval_menu.configure(dropdown_font=self._ui_font(13, False))
        except Exception:
            pass

        # Language (moved into settings)
        lang_block = ctk.CTkFrame(top, fg_color="transparent")
        lang_block.grid(row=0, column=1, sticky="ew", padx=14)

        self.language_setting_label = ctk.CTkLabel(
            lang_block,
            text=self._t("language_label"),
            font=self._ui_font(12, True),
            text_color=(colors.text_primary_light, colors.text_primary_dark),
            anchor="e" if self.rtl else "w",
        )
        self.language_setting_label.pack(fill="x")

        self.language_var = ctk.StringVar(value=self._language_display(self.language))
        self.language_menu = ctk.CTkOptionMenu(
            lang_block,
            variable=self.language_var,
            values=self._language_menu_values(),
            width=200,
            height=36,
            corner_radius=10,
            fg_color=(colors.glass_light, colors.glass_dark),
            button_color=(colors.accent_blue, colors.accent_blue),
            button_hover_color=(colors.accent_blue_hover, colors.accent_blue_hover),
            text_color=(colors.text_primary_light, colors.text_primary_dark),
            dropdown_fg_color=(colors.glass_light, colors.glass_dark),
            dropdown_text_color=(colors.text_primary_light, colors.text_primary_dark),
            font=self._ui_font(13, False),
            command=self._on_language_changed,
        )
        self.language_menu.pack(anchor="e" if self.rtl else "w", pady=(6, 0))
        try:
            self.language_menu.configure(dropdown_font=self._ui_font(13, False))
        except Exception:
            pass


        # Window options
        window_block = ctk.CTkFrame(top, fg_color="transparent")
        window_block.grid(row=0, column=2, sticky="ew")

        self.window_options_label = ctk.CTkLabel(
            window_block,
            text=self._t("window_options"),
            font=self._ui_font(12, True),
            text_color=(colors.text_primary_light, colors.text_primary_dark),
            anchor="e" if self.rtl else "w",
        )
        self.window_options_label.pack(fill="x")

        self.always_on_top_var = ctk.BooleanVar(value=self.always_on_top)
        self.always_on_top_cb = ctk.CTkCheckBox(
            window_block,
            text=self._t("always_on_top"),
            variable=self.always_on_top_var,
            command=self._on_always_on_top_toggle,
            font=self._ui_font(13, False),
            text_color=(colors.text_primary_light, colors.text_primary_dark),
            fg_color=(colors.accent_blue, colors.accent_blue),
            hover_color=(colors.accent_blue_hover, colors.accent_blue_hover),
            border_color=(colors.border_light, colors.border_dark),
        )
        self.always_on_top_cb.pack(anchor="e" if self.rtl else "w", pady=(6, 0))

        self.background_var = ctk.BooleanVar(value=self.run_in_background)
        self.background_cb = ctk.CTkCheckBox(
            window_block,
            text=self._t("run_in_background"),
            variable=self.background_var,
            command=self._on_background_toggle,
            font=self._ui_font(13, False),
            text_color=(colors.text_primary_light, colors.text_primary_dark),
            fg_color=(colors.accent_blue, colors.accent_blue),
            hover_color=(colors.accent_blue_hover, colors.accent_blue_hover),
            border_color=(colors.border_light, colors.border_dark),
        )
        self.background_cb.pack(anchor="e" if self.rtl else "w", pady=(8, 0))

        # Row 2: alerts (full width)
        alerts_block = ctk.CTkFrame(content, fg_color="transparent")
        alerts_block.pack(fill="x", pady=(16, 0))

        self.alerts_title_label = ctk.CTkLabel(
            alerts_block,
            text=self._t("alerts_title"),
            font=self._ui_font(12, True),
            text_color=(colors.text_primary_light, colors.text_primary_dark),
            anchor="e" if self.rtl else "w",
        )
        self.alerts_title_label.pack(fill="x")

        self.alerts_var = ctk.BooleanVar(value=self.alerts_enabled)
        self.alerts_cb = ctk.CTkCheckBox(
            alerts_block,
            text=self._t("enable_alerts"),
            variable=self.alerts_var,
            command=self._on_alerts_toggle,
            font=self._ui_font(13, False),
            text_color=(colors.text_primary_light, colors.text_primary_dark),
            fg_color=(colors.accent_blue, colors.accent_blue),
            hover_color=(colors.accent_blue_hover, colors.accent_blue_hover),
            border_color=(colors.border_light, colors.border_dark),
        )
        self.alerts_cb.pack(anchor="e" if self.rtl else "w", pady=(6, 0))

        self.alert_threshold_label = ctk.CTkLabel(
            alerts_block,
            text=self._t("threshold", value=float(self.alert_threshold_percent)),
            font=self._ui_font(12, False),
            text_color=(colors.text_secondary_light, colors.text_secondary_dark),
            anchor="e" if self.rtl else "w",
        )
        self.alert_threshold_label.pack(fill="x", pady=(10, 0))

        self.alert_threshold_slider = ctk.CTkSlider(
            alerts_block,
            from_=0.5,
            to=10.0,
            number_of_steps=95,
            command=self._on_threshold_changed,
        )
        self.alert_threshold_slider.set(self.alert_threshold_percent)
        self.alert_threshold_slider.pack(fill="x", pady=(6, 0))

        # Row 3: tools
        tools_block = ctk.CTkFrame(content, fg_color="transparent")
        tools_block.pack(fill="x", pady=(16, 0))

        self.tools_title_label = ctk.CTkLabel(
            tools_block,
            text=self._t("tools"),
            font=self._ui_font(12, True),
            text_color=(colors.text_primary_light, colors.text_primary_dark),
            anchor="e" if self.rtl else "w",
        )
        self.tools_title_label.pack(fill="x")

        tools_row = ctk.CTkFrame(tools_block, fg_color="transparent")
        tools_row.pack(anchor="e" if self.rtl else "w", pady=(8, 0))

        self.clear_cache_btn = self._create_button(tools_row, text=self._t("btn_clear_cache"), command=self._clear_cache, style="secondary", width=160)
        self.perf_btn = self._create_button(tools_row, text=self._t("btn_performance"), command=self._show_performance_report, style="secondary", width=140)
        self.layout_btn = self._create_button(
            tools_row,
            text=("🧩 چیدمان" if self.language == "fa" else "🧩 Layout"),
            command=self._open_layout_popup,
            style="secondary",
            width=140,
        )

        if self.rtl:
            self.layout_btn.pack(side="left", padx=(0, 10))
            self.perf_btn.pack(side="left", padx=(0, 10))
            self.clear_cache_btn.pack(side="left")
        else:
            self.clear_cache_btn.pack(side="left", padx=(0, 10))
            self.perf_btn.pack(side="left", padx=(0, 10))
            self.layout_btn.pack(side="left")

    def _create_theme_section(self) -> None:
        row = self._next_row()
        card = self._create_glass_card(self.scroll_frame)
        card.grid(row=row, column=0, sticky="ew", pady=(0, 20))

        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=18)

        title = ctk.CTkLabel(
            content,
            text=self._t("section_theme"),
            font=self._ui_font(18, True),
            text_color=(colors.text_primary_light, colors.text_primary_dark),
            anchor="e" if self.rtl else "w",
        )
        title.pack(fill="x")

        themes = [
            ("liquid_glass", self._t("theme_liquid_glass")),
            ("vibrancy", self._t("theme_vibrancy")),
            ("crystal", self._t("theme_crystal")),
            ("midnight", self._t("theme_midnight")),
            ("paper", self._t("theme_paper")),
            ("paper_noir", self._t("theme_paper_noir")),
        ]

        button_grid = ctk.CTkFrame(content, fg_color="transparent")
        button_grid.pack(fill="x", pady=(14, 0))
        button_grid.grid_columnconfigure((0, 1, 2), weight=1)

        self.theme_buttons = {}

        for i, (key, label) in enumerate(themes):
            r = 0 if i < 3 else 1
            c = i if i < 3 else i - 3

            # RTL-safe column mirroring (prevents negative column index)
            if self.rtl:
                c = 2 - c

            # Absolute safety clamp (never allow negative column)
            c = max(0, c)

            btn = self._create_button(
                button_grid,
                text=label,
                command=lambda k=key: self._apply_theme_with_feedback(k),
                style="secondary",
                width=220,
            )
            btn.grid(row=r, column=c, sticky="ew", padx=6, pady=6)
            self.theme_buttons[key] = btn

        self._update_theme_button_states(self.selected_theme)


    def _render_featured_cards(self) -> None:
        desired = self.featured_symbols[: self.grid_columns]
        desired_set = set(desired)

        # Remove unused cards
        for sym in list(self.featured_cards.keys()):
            if sym not in desired_set:
                try:
                    self.featured_cards[sym].destroy()
                except Exception:
                    pass
                self.featured_cards.pop(sym, None)

        # Create/update cards
        for idx, sym in enumerate(desired):
            data = self.currencies.get(sym)
            if not data:
                continue
            card = self.featured_cards.get(sym)
            if card is not None:
                try:
                    if not card.winfo_exists():
                        self.featured_cards.pop(sym, None)
                        card = None
                except Exception:
                    self.featured_cards.pop(sym, None)
                    card = None

            if card is None:
                card = CurrencyCardWidget(self.featured_container, show_remove=False, font_getter=self._ui_font, rtl=self.rtl)
                self.featured_cards[sym] = card
                card.grid(row=0, column=idx, padx=config.CARD_PADDING, pady=config.CARD_PADDING, sticky="nsew")
            else:
                try:
                    card.grid_configure(row=0, column=idx)
                except Exception:
                    try:
                        card.grid(row=0, column=idx, padx=config.CARD_PADDING, pady=config.CARD_PADDING, sticky="nsew")
                    except Exception:
                        try:
                            self.featured_cards.pop(sym, None)
                            card.destroy()
                        except Exception:
                            pass
                        card = CurrencyCardWidget(self.featured_container, show_remove=False, font_getter=self._ui_font, rtl=self.rtl)
                        self.featured_cards[sym] = card
                        card.grid(row=0, column=idx, padx=config.CARD_PADDING, pady=config.CARD_PADDING, sticky="nsew")

            try:
                card.update_data(self._display_currency_data(sym, data))
            except Exception:
                pass

        # Fill empty slots (to keep layout stable)
        for idx in range(len(desired), self.grid_columns):
            pass


    def _debounced_portfolio_filter(self) -> None:
        try:
            if self._portfolio_filter_after_id:
                try:
                    self.after_cancel(self._portfolio_filter_after_id)
                except Exception:
                    pass
            self._portfolio_filter_after_id = self.after(220, self._render_portfolio_cards)
        except Exception:
            pass

    def _render_portfolio_cards(self) -> None:
        # Exclude featured from portfolio view (same UX as older versions)
        featured_set = set(self.featured_symbols)
        symbols = [s for s in self.user_portfolio if s in self.currencies and s not in featured_set]
        symbols = self._sort_portfolio_symbols(symbols)

        # Apply quick filter (UI-only)
        try:
            ft = (self.portfolio_filter_var.get() if self.portfolio_filter_var is not None else "").strip().lower()
        except Exception:
            ft = ""
        if ft:
            filtered: List[str] = []
            for sym in symbols:
                d = self.currencies.get(sym, {})
                name = self._currency_display_name(sym, d)
                if ft in sym.lower() or (name and ft in str(name).lower()):
                    filtered.append(sym)
            symbols = filtered

        desired_set = set(symbols)

        for sym in list(self.portfolio_cards.keys()):
            if sym not in desired_set:
                try:
                    self.portfolio_cards[sym].destroy()
                except Exception:
                    pass
                self.portfolio_cards.pop(sym, None)

        row = 0
        col = 0
        for sym in symbols:
            data = self.currencies.get(sym)
            if not data:
                continue
            card = self.portfolio_cards.get(sym)
            if card is None:
                card = CurrencyCardWidget(self.portfolio_container, on_remove=self._remove_currency, show_remove=True, font_getter=self._ui_font, rtl=self.rtl)
                self.portfolio_cards[sym] = card
            card.grid(row=row, column=col, padx=config.CARD_PADDING, pady=config.CARD_PADDING, sticky="nsew")
            card.update_data(self._display_currency_data(sym, data))

            col += 1
            if col >= self.grid_columns:
                col = 0
                row += 1

    def _update_currency_selector(self) -> None:
        try:
            if not self.currencies:
                self.currency_selector.configure(values=[self._t("status_connecting")])
                self.currency_selector.set(self._t("status_connecting"))
                return
        except Exception:
            pass

        try:
            search = str(self.selector_search_var.get() or "")
        except Exception:
            search = ""

        excluded = set(self.user_portfolio) | set(self.featured_symbols)
        values = self._get_selector_values(search=search, excluded=excluded)

        try:
            self.currency_selector.configure(values=values)
            if values:
                self.currency_selector.set(values[0])
        except Exception:
            pass


    def _debounced_update_currency_selector(self) -> None:
        try:
            if self._selector_update_after_id:
                self.after_cancel(self._selector_update_after_id)
        except Exception:
            pass
        self._selector_update_after_id = self.after(180, self._update_currency_selector)

    def _update_insights(self) -> None:
        try:
            movers: List[Tuple[float, str]] = []
            for sym, data in self.currencies.items():
                try:
                    ch = float(data.get("change_percent", 0) or 0)
                except Exception:
                    ch = 0.0
                movers.append((ch, sym))

            movers.sort(key=lambda x: x[0], reverse=True)
            top_gainers = [m for m in movers if m[0] > 0][:3]
            top_losers = sorted([m for m in movers if m[0] < 0], key=lambda x: x[0])[:3]

            gain_labels: List[ctk.CTkLabel] = self.ui_elements.get("top_gainers", [])
            loss_labels: List[ctk.CTkLabel] = self.ui_elements.get("top_losers", [])

            for i in range(3):
                if i < len(top_gainers):
                    ch, sym = top_gainers[i]
                    name = self._currency_display_name(sym, self.currencies.get(sym, {}))
                    gain_labels[i].configure(text=f"{sym} • {name} • +{ch:.2f}%")
                else:
                    gain_labels[i].configure(text="—")

                if i < len(top_losers):
                    ch, sym = top_losers[i]
                    name = self._currency_display_name(sym, self.currencies.get(sym, {}))
                    loss_labels[i].configure(text=f"{sym} • {name} • {ch:.2f}%")
                else:
                    loss_labels[i].configure(text="—")
        except Exception:
            pass

    def _update_status_displays(self) -> None:
        # Data status
        try:
            if "data_status" in self.ui_elements:
                if self.connection_status == ConnectionStatus.CONNECTED:
                    quality = self._t("data_quality_excellent")
                    source = self._t("data_source_live")
                elif self.connection_status == ConnectionStatus.CACHED:
                    quality = self._t("data_quality_cached")
                    source = self._t("data_source_db")
                elif self.connection_status == ConnectionStatus.CONNECTING:
                    quality = self._t("data_quality_connecting")
                    source = "—"
                elif self.connection_status == ConnectionStatus.RATE_LIMITED:
                    quality = self._t("data_quality_limited")
                    source = self._t("data_source_live")
                else:
                    quality = self._t("data_quality_limited")
                    source = self._t("data_source_offline")

                suffix = "مورد" if self.language == "fa" else "items"
                self.ui_elements["data_status"]["status_label"].configure(
                    text=f"📊 {quality} • {source} • {len(self.currencies)} {suffix}"
                )
        except Exception:
            pass

        # Effects status
        self._update_effects_status()

        # Last update
        try:
            self.last_update_label.configure(text=self._t("last_update", time=self.last_update))
        except Exception:
            pass


    def _update_connection_status(self, status: ConnectionStatus, message: Optional[str] = None) -> None:
        self.connection_status = status

        if status == ConnectionStatus.CONNECTED:
            color = colors.status_success
            msg = message or self._t("status_connected", count=len(self.currencies))
        elif status == ConnectionStatus.CACHED:
            color = colors.status_warning
            msg = message or self._t("status_cached", count=len(self.currencies))
        elif status == ConnectionStatus.CONNECTING:
            color = colors.status_info
            msg = message or self._t("status_connecting")
        elif status == ConnectionStatus.RATE_LIMITED:
            color = colors.status_warning
            msg = message or self._t("status_rate_limited")
        else:
            color = colors.status_error
            msg = message or self._t("status_error")

        try:
            if "api_status" in self.ui_elements:
                self.ui_elements["api_status"]["status_label"].configure(text=msg, text_color=color)
        except Exception:
            pass


    def _update_effects_status(self) -> None:
        try:
            info = self.effects_manager.get_current_effect_info()
            effect = str(info.get("effect", "normal") or "normal").lower()

            if "liquid" in effect:
                name = self._t("theme_name_liquid_glass")
            elif "vibrancy" in effect:
                name = self._t("theme_name_vibrancy")
            elif "crystal" in effect:
                name = self._t("theme_name_crystal")
            else:
                name = "نرمال" if self.language == "fa" else "Normal"

            if "simulation" in effect:
                name += " (شبیه‌سازی)" if self.language == "fa" else " (Simulation)"

            if "effects_status" in self.ui_elements:
                self.ui_elements["effects_status"]["status_label"].configure(text=f"✨ {name}")
        except Exception:
            pass


    # -------------------------------------------------------------------------
    # Preferences
    # -------------------------------------------------------------------------

    def _load_saved_preferences(self) -> None:
        """Load persisted user preferences from the local DB.

        Note: This runs BEFORE UI widgets are created, so it must only populate state.
        """
        # Portfolio
        self.user_portfolio = db_manager.load_selected_currencies()

        # Legacy cleanup: older versions used to auto-save featured items in the portfolio table
        legacy_auto_featured = {"USD", "EUR", "GBP", "BTC", "ETH", "SEKEH", "GOLD", "GERAM18", "AED", "TRY"}
        if self.user_portfolio & legacy_auto_featured:
            self.user_portfolio -= legacy_auto_featured
            db_manager.save_selected_currencies(self.user_portfolio)

        # Language
        saved_lang = db_manager.load_preference("language", "en")
        self.language = self._normalize_language(str(saved_lang))

        # Theme
        saved_theme = db_manager.load_preference("selected_theme", "liquid_glass")
        self.selected_theme = self._normalize_theme_key(str(saved_theme))

        # Settings
        self.auto_refresh_active = bool(db_manager.load_preference("auto_refresh", True))

        raw_interval = db_manager.load_preference("refresh_interval_seconds", config.DEFAULT_REFRESH_INTERVAL)
        try:
            self.refresh_interval_seconds = int(raw_interval or config.DEFAULT_REFRESH_INTERVAL)
        except Exception:
            self.refresh_interval_seconds = int(config.DEFAULT_REFRESH_INTERVAL)
        self.refresh_interval_seconds = int(max(config.MIN_REFRESH_INTERVAL, min(config.MAX_REFRESH_INTERVAL, self.refresh_interval_seconds)))

        self.alerts_enabled = bool(db_manager.load_preference("alerts_enabled", True))
        try:
            self.alert_threshold_percent = float(db_manager.load_preference("alert_threshold_percent", 2.5) or 2.5)
        except Exception:
            self.alert_threshold_percent = 2.5
        self.alert_threshold_percent = float(max(0.5, min(10.0, self.alert_threshold_percent)))

        self.always_on_top = bool(db_manager.load_preference("always_on_top", False))
        try:
            self.attributes("-topmost", bool(self.always_on_top))
        except Exception:
            pass

        self.run_in_background = bool(db_manager.load_preference("run_in_background", False))
        raw_sort = db_manager.load_preference("portfolio_sort_mode", "default")
        self.portfolio_sort_mode_key = self._normalize_sort_key(str(raw_sort))

        # Layout (sections order + visibility)
        default_order = [
            "hero",
            "status",
            "featured",
            "insights",
            "history",
            "portfolio",
            "converter",
            "widgets",
            "controls",
            "settings",
            "theme",
        ]

        try:
            raw_order = db_manager.load_preference("section_order_json", "")
            order = json.loads(raw_order) if raw_order else []
            if isinstance(order, list) and order:
                # keep only known keys, preserve defaults for missing ones
                cleaned = [k for k in order if k in default_order]
                for k in default_order:
                    if k not in cleaned:
                        cleaned.append(k)
                self.section_order = cleaned
            else:
                self.section_order = list(default_order)
        except Exception:
            self.section_order = list(default_order)

        try:
            raw_enabled = db_manager.load_preference("section_enabled_json", "")
            enabled = json.loads(raw_enabled) if raw_enabled else {}
            if isinstance(enabled, dict) and enabled:
                self.section_enabled = {k: bool(enabled.get(k, True)) for k in default_order}
            else:
                self.section_enabled = {k: True for k in default_order}
        except Exception:
            self.section_enabled = {k: True for k in default_order}

    # -------------------------------------------------------------------------
    # Portfolio actions
    # -------------------------------------------------------------------------

    def _add_selected_currency(self) -> None:
        try:
            selected = self.currency_selector.get()
            if not selected or selected == self._t("no_matches") or selected == self._t("status_connecting"):
                return

            sym = None
            if "(" in selected and ")" in selected:
                sym = selected.split("(")[-1].split(")")[0].strip().upper()
            if not sym:
                return

            if sym in self.currencies and sym not in self.user_portfolio and sym not in set(self.featured_symbols):
                self.user_portfolio.add(sym)
                db_manager.save_selected_currencies(self.user_portfolio)
                self._render_portfolio_cards()
                self._update_currency_selector()
                self.toasts.show(self._t("toast_added", sym=sym), duration=1800)
        except Exception as e:
            logger.debug(f"Add currency failed: {e}")

    def _remove_currency(self, symbol: str) -> None:
        sym = str(symbol).upper().strip()
        if not sym:
            return
        if sym in self.user_portfolio:
            self.user_portfolio.remove(sym)
            db_manager.save_selected_currencies(self.user_portfolio)
            self._render_portfolio_cards()
            self._update_currency_selector()
            self.toasts.show(self._t("toast_removed", sym=sym), duration=1800)

    def _sort_portfolio_symbols(self, symbols: List[str]) -> List[str]:
        mode = self._normalize_sort_key(self.portfolio_sort_mode_key)

        def safe_float(x: Any) -> float:
            try:
                return float(x)
            except Exception:
                return float("nan")

        if mode in ("default", "symbol"):
            return sorted(symbols)

        if mode == "name":
            return sorted(symbols, key=lambda s: str(self._currency_display_name(s, self.currencies.get(s, {}))).lower())

        if mode == "price":
            return sorted(symbols, key=lambda s: safe_float(self.currencies.get(s, {}).get("price", 0)), reverse=True)

        if mode == "change":
            return sorted(symbols, key=lambda s: safe_float(self.currencies.get(s, {}).get("change_percent", 0)), reverse=True)

        return sorted(symbols)

    def _on_portfolio_sort_changed(self, selection: Optional[str] = None) -> None:
        display = str(selection or self.portfolio_sort_var.get() or "")
        self.portfolio_sort_mode_key = self._sort_display_to_key(display)
        db_manager.save_preference("portfolio_sort_mode", self.portfolio_sort_mode_key)
        self._render_portfolio_cards()
    def _manual_refresh(self) -> None:
        msg = self._t("status_refreshing")
        self._update_connection_status(ConnectionStatus.CONNECTING, msg)
        self.executor.submit(self._manual_refresh_worker)

    def _manual_refresh_worker(self) -> None:
        try:
            performance_monitor.inc("api_calls")
            data = self.api_manager.fetch_data_sync(force=True)
            if data:
                currencies = self.api_manager.process_currency_data(data)
                if currencies:
                    self._enqueue_ui(lambda: self._update_ui_with_data(currencies, ConnectionStatus.CONNECTED, quiet=False))
                    return
            self._enqueue_ui(lambda: self._handle_refresh_failed())
        except Exception:
            self._enqueue_ui(lambda: self._handle_refresh_failed())

    def _handle_refresh_failed(self) -> None:
        performance_monitor.inc("errors")
        self._update_connection_status(ConnectionStatus.ERROR)
        self.toasts.show(self._t("toast_refresh_failed"), duration=2600)

    def _test_api_connection(self) -> None:
        self._update_connection_status(ConnectionStatus.CONNECTING, f"🧪 {self._t('api_test_title')}…")
        self.executor.submit(self._api_test_worker)

    def _api_test_worker(self) -> None:
        try:
            start = time.time()
            performance_monitor.inc("api_calls")
            data = self.api_manager.fetch_data_sync(force=True)
            elapsed = time.time() - start
            if data:
                currencies = self.api_manager.process_currency_data(data)
                msg = self._t("api_test_ok", elapsed=elapsed, count=len(currencies))
                self._enqueue_ui(lambda: messagebox.showinfo(self._t("api_test_title"), msg))
                self._enqueue_ui(lambda: self._update_connection_status(ConnectionStatus.CONNECTED))
            else:
                msg = self._t("api_test_fail")
                self._enqueue_ui(lambda: messagebox.showerror(self._t("api_test_title"), msg))
                self._enqueue_ui(lambda: self._update_connection_status(ConnectionStatus.ERROR))
        except Exception as e:
            err_prefix = "خطا" if self.language == "fa" else "Error"
            self._enqueue_ui(lambda: messagebox.showerror(self._t("api_test_title"), f"{err_prefix}:\n{e}"))
            self._enqueue_ui(lambda: self._update_connection_status(ConnectionStatus.ERROR))

    def _toggle_auto_refresh(self) -> None:
        self.auto_refresh_active = bool(self.auto_refresh_var.get())
        db_manager.save_preference("auto_refresh", self.auto_refresh_active)
        self.toasts.show(self._t("toast_autorefresh_on") if self.auto_refresh_active else self._t("toast_autorefresh_off"), duration=1800)

    def _export_csv(self) -> None:
        try:
            from tkinter import filedialog
            import csv

            path = filedialog.asksaveasfilename(
                title=self._t("export_title"),
                defaultextension=".csv",
                filetypes=[(self._t("filetype_csv"), "*.csv"), (self._t("filetype_all"), "*.*")],
            )
            if not path:
                return

            symbols = list(dict.fromkeys(self.featured_symbols + sorted(self.user_portfolio)))
            rows = []
            for sym in symbols:
                d = self.currencies.get(sym)
                if not d:
                    continue
                dd = self._display_currency_data(sym, d)
                rows.append({
                    "symbol": sym,
                    "name": dd.get("name", ""),
                    "price": d.get("price", ""),
                    "unit": dd.get("unit", ""),
                    "change_percent": d.get("change_percent", ""),
                    "category": d.get("category", ""),
                    "source": d.get("source", ""),
                    "timestamp": d.get("timestamp", ""),
                })

            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["symbol", "name", "price", "unit", "change_percent"])
                writer.writeheader()
                for r in rows:
                    writer.writerow(r)

            self.toasts.show(self._t("toast_csv_exported"), duration=2400)
        except Exception as e:
            messagebox.showerror(self._t("export_title"), self._t("export_failed", error=e))

    def _copy_to_clipboard(self) -> None:
        try:
            symbols = list(dict.fromkeys(self.featured_symbols + sorted(self.user_portfolio)))
            lines = []
            for sym in symbols:
                d = self.currencies.get(sym, {})
                dd = self._display_currency_data(sym, d) if d else {"name": "", "unit": ""}
                lines.append(f"{sym}\t{dd.get('name','')}\t{d.get('price','')}\t{dd.get('unit','')}\t{d.get('change_percent','')}")
            text = "\n".join(lines) if lines else ""
            self.clipboard_clear()
            self.clipboard_append(text)
            self.update()
            self.toasts.show(self._t("toast_copied"), duration=2000)
        except Exception as e:
            logger.debug(f"Clipboard copy failed: {e}")

    # -------------------------------------------------------------------------
    # Settings actions
    # -------------------------------------------------------------------------
    def _interval_choices(self) -> List[str]:
        return [self._format_interval(s) for s in (30, 60, 120, 300, 600, 900)]

    def _parse_interval(self, value: str) -> int:
        raw = str(value or "").strip()
        low = raw.lower()

        # Normalize digits (Persian/Arabic-Indic -> English)
        norm = low.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))
        norm = norm.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
        norm = norm.replace(" ", "")

        mapping = {"30s": 30, "60s": 60, "2m": 120, "5m": 300, "10m": 600, "15m": 900}
        if norm in mapping:
            return mapping[norm]

        digits = "".join(ch for ch in norm if ch.isdigit())
        if not digits:
            return config.DEFAULT_REFRESH_INTERVAL

        try:
            num = int(digits)
        except Exception:
            return config.DEFAULT_REFRESH_INTERVAL

        if ("دقیقه" in low) or norm.endswith("m") or ("min" in norm):
            return max(0, num) * 60
        if ("ثانیه" in low) or norm.endswith("s") or ("sec" in norm) or ("ث" in low):
            return max(0, num)

        return config.DEFAULT_REFRESH_INTERVAL

    def _format_interval(self, seconds: int) -> str:
        try:
            sec = int(seconds)
        except Exception:
            sec = int(config.DEFAULT_REFRESH_INTERVAL)

        if self.language == "fa":
            fa_digits = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
            if sec < 60:
                return f"{str(sec).translate(fa_digits)} ثانیه"
            if sec % 60 == 0:
                m = sec // 60
                return f"{str(m).translate(fa_digits)} دقیقه"
            return f"{str(sec).translate(fa_digits)} ثانیه"

        # English
        if sec < 60:
            return f"{sec}s"
        if sec == 60:
            return "60s"
        if sec % 60 == 0:
            return f"{sec // 60}m"
        return f"{sec}s"
        if seconds % 60 == 0:
            m = seconds // 60
            return f"{m}m"
        return f"{seconds}s"

    def _on_refresh_interval_changed(self) -> None:
        val = self.refresh_interval_var.get()
        self.refresh_interval_seconds = self._parse_interval(val)
        self.refresh_interval_seconds = int(max(config.MIN_REFRESH_INTERVAL, min(config.MAX_REFRESH_INTERVAL, self.refresh_interval_seconds)))
        db_manager.save_preference("refresh_interval_seconds", self.refresh_interval_seconds)
        self.toasts.show(self._t("toast_interval_set", interval=self._format_interval(self.refresh_interval_seconds)), duration=2000)
        self._schedule_auto_refresh()

    def _on_alerts_toggle(self) -> None:
        self.alerts_enabled = bool(self.alerts_var.get())
        db_manager.save_preference("alerts_enabled", self.alerts_enabled)
        self.toasts.show(self._t("toast_alerts_on") if self.alerts_enabled else self._t("toast_alerts_off"), duration=1800)

    def _on_threshold_changed(self, value: float) -> None:
        try:
            self.alert_threshold_percent = float(value)
            self.alert_threshold_label.configure(text=self._t("threshold", value=float(self.alert_threshold_percent)))
        except Exception:
            return

        # Persist lazily (avoid too many writes)
        self.after(250, lambda: db_manager.save_preference("alert_threshold_percent", float(self.alert_threshold_percent)))



    def _on_background_toggle(self) -> None:
        try:
            if self.background_var is None:
                return
            self.run_in_background = bool(self.background_var.get())
            db_manager.save_preference("run_in_background", bool(self.run_in_background))
            self.toasts.show(self._t("toast_background_on") if self.run_in_background else self._t("toast_background_off"), duration=2200)
        except Exception:
            pass

    def _on_always_on_top_toggle(self) -> None:
        """Toggle window 'always on top' (useful for a price tracker)."""
        try:
            if self.always_on_top_var is None:
                return
            self.always_on_top = bool(self.always_on_top_var.get())
            db_manager.save_preference("always_on_top", bool(self.always_on_top))
            try:
                self.attributes("-topmost", bool(self.always_on_top))
            except Exception:
                pass
            self.toasts.show(
                self._t("toast_topmost_on") if self.always_on_top else self._t("toast_topmost_off"),
                duration=1800,
            )
        except Exception:
            pass


    def _clear_cache(self) -> None:
        try:
            db_manager.prune_cache(keep_last_seconds=0)
            self.toasts.show(self._t("toast_cache_cleared"), duration=2400)
        except Exception as e:
            messagebox.showerror(self._t("clear_cache_title"), str(e))

    def _show_performance_report(self) -> None:
        rep = performance_monitor.report()
        if self.language == "fa":
            msg = (
                f"مدت اجرا: {rep['runtime_formatted']}\n\n"
                f"بروزرسانی رابط: {rep['metrics']['ui_updates']}\n"
                f"فراخوانی API: {rep['metrics']['api_calls']}\n"
                f"بارگذاری کش: {rep['metrics']['cache_loads']}\n"
                f"خطاها: {rep['metrics']['errors']}\n"
            )
        else:
            msg = (
                f"Runtime: {rep['runtime_formatted']}\n\n"
                f"UI updates: {rep['metrics']['ui_updates']}\n"
                f"API calls: {rep['metrics']['api_calls']}\n"
                f"Cache loads: {rep['metrics']['cache_loads']}\n"
                f"Errors: {rep['metrics']['errors']}\n"
            )
        messagebox.showinfo(self._t("performance_title"), msg)

    # Alerts
    # -------------------------------------------------------------------------

    def _maybe_emit_price_alerts(self, old: Dict[str, Dict[str, Any]], new: Dict[str, Dict[str, Any]]) -> None:
        if not self.alerts_enabled:
            return

        now = time.time()
        cooldown = 60.0  # seconds per symbol
        watch = set(self.featured_symbols) | set(self.user_portfolio)

        for sym in watch:
            if sym not in new:
                continue
            try:
                new_price = float(new[sym].get("price", 0) or 0)
            except Exception:
                continue
            if new_price <= 0:
                continue

            old_price = self._last_seen_prices.get(sym)
            if old_price is None or old_price <= 0:
                self._last_seen_prices[sym] = new_price
                continue

            delta = (new_price - old_price) / old_price * 100.0
            if abs(delta) >= self.alert_threshold_percent:
                last_ts = self._last_alert_ts.get(sym, 0.0)
                if now - last_ts >= cooldown:
                    direction = "▲" if delta > 0 else "▼"
                    msg = self._t("toast_price_moved", direction=direction, sym=sym, delta=delta)
                    self.toasts.show(msg, duration=3200)
                    self._last_alert_ts[sym] = now

            self._last_seen_prices[sym] = new_price

    # -------------------------------------------------------------------------
    # Theme
    # -------------------------------------------------------------------------

    def _normalize_theme_key(self, theme_key: str) -> str:
        key = str(theme_key or "").strip().lower()
        mapping = {
            "liquid": "liquid_glass",
            "liquid_glass": "liquid_glass",
            "liquid glass": "liquid_glass",
            "vibrancy": "vibrancy",
            "enhanced_vibrancy": "vibrancy",
            "crystal": "crystal",
            "crystal_mode": "crystal",
            "midnight": "midnight",
            "night": "midnight",
            "dark": "midnight",
            "paper": "paper",
            "paper_noir": "paper_noir",
            "paper noir": "paper_noir",
            "noir": "paper_noir",
            "dark paper": "paper_noir",
            "flat": "paper",
            "light": "paper",
        }
        return mapping.get(key, "liquid_glass")

    def _get_theme_display_name(self, theme_key: str) -> str:
        mapping = {
            "liquid_glass": self._t("theme_name_liquid_glass"),
            "vibrancy": self._t("theme_name_vibrancy"),
            "crystal": self._t("theme_name_crystal"),
            "midnight": self._t("theme_name_midnight"),
            "paper": self._t("theme_name_paper"),
            "paper_noir": self._t("theme_name_paper_noir"),
        }
        return mapping.get(theme_key, str(theme_key))

    def _update_theme_button_states(self, active_theme_key: str) -> None:
        active = self._normalize_theme_key(active_theme_key)
        for key, btn in (self.theme_buttons or {}).items():
            try:
                if key == active:
                    btn.configure(
                        fg_color=(colors.accent_blue, colors.accent_blue),
                        hover_color=(colors.accent_blue_hover, colors.accent_blue_hover),
                        text_color="white",
                        border_width=0,
                    )
                else:
                    btn.configure(
                        fg_color=(colors.glass_overlay_light, colors.glass_overlay_dark),
                        hover_color=(colors.separator_light, colors.separator_dark),
                        text_color=(colors.text_primary_light, colors.text_primary_dark),
                        border_width=1,
                        border_color=(colors.border_light, colors.border_dark),
                    )
            except Exception:
                pass

    def _apply_theme_with_feedback(
        self, theme_type: str, show_feedback: bool = True, save_preference: bool = True
    ) -> None:
        theme_key = self._normalize_theme_key(theme_type)
        if theme_key not in {"liquid_glass", "vibrancy", "crystal", "midnight", "paper", "paper_noir"}:
            return

        self.selected_theme = theme_key
        self._update_theme_button_states(theme_key)
        if save_preference:
            db_manager.save_preference("selected_theme", theme_key)

        if show_feedback:
            display_name = self._get_theme_display_name(theme_key)
            self.toasts.show(self._t("toast_applying_theme", name=display_name), duration=1400)

        try:
            # Reset palette (themes may override it)
            try:
                globals()["colors"] = DEFAULT_COLORS
            except Exception:
                pass

            # Appearance mode per theme (keeps themes distinct without slowing UI)
            if theme_key == "midnight":
                # Deeper dark-glass palette
                try:
                    globals()["colors"] = MIDNIGHT_COLORS
                except Exception:
                    pass
                try:
                    ctk.set_appearance_mode("Dark")
                except Exception:
                    pass
                self.effects_manager.apply_midnight_glow_effect()

            elif theme_key == "paper":
                try:
                    ctk.set_appearance_mode("Light")
                except Exception:
                    pass
                self.effects_manager.apply_paper_mode()

            elif theme_key == "paper_noir":
                try:
                    ctk.set_appearance_mode("Dark")
                except Exception:
                    pass
                self.effects_manager.apply_paper_noir_mode()

            else:
                # Default themes follow system appearance
                try:
                    ctk.set_appearance_mode("System")
                except Exception:
                    pass

                if theme_key == "liquid_glass":
                    self.effects_manager.apply_liquid_glass_effect()
                elif theme_key == "vibrancy":
                    self.effects_manager.apply_vibrancy_effect()
                elif theme_key == "crystal":
                    self.effects_manager.apply_crystal_mode()

        except Exception as e:
            logger.debug(f"Theme apply failed: {e}")

        # Rebuild UI to ensure all panels pick up the new palette
        try:
            self._rebuild_main_sections()
        except Exception:
            pass

        # Widgets/menus might need a refresh after appearance change
        try:
            self._symbol_menu_sig = ""
            self._refresh_symbol_menus()
        except Exception:
            pass

# =============================================================================
# Diagnostics / main
# =============================================================================

def run_system_diagnostics() -> None:
    print("=" * 80)
    print("Liquid Gheymat Price Tracker — Diagnostics")
    print("=" * 80)
    print(f"OS: {sys.platform}")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Version: {config.APP_VERSION}")
    print(f"CustomTkinter: {getattr(ctk, '__version__', 'unknown')}")
    print(f"Requests: {getattr(requests, '__version__', 'unknown')}")
    print(f"Pyglet: {getattr(pyglet, 'version', 'unknown')}")
    if IS_WINDOWS:
        print(f"PyWinStyles: {'Available' if PYWINSTYLES_AVAILABLE else 'Not available'}")
    print("=" * 80)
    print()


def main() -> None:
    try:
        run_system_diagnostics()
        app = LiquidGlassPriceTracker()
        app.mainloop()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Critical error: {e}")
        try:
            messagebox.showerror("Critical Error", f"Application failed:\n\n{e}")
        except Exception:
            pass
        raise
    finally:
        logger.info("Session ended")


if __name__ == "__main__":
    main()
    
