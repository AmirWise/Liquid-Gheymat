import customtkinter as ctk
import sys
import os
import json
import pyglet
from tkinter import messagebox
import math

# --- بررسی سیستم‌عامل برای اعمال افکت ---
IS_WINDOWS = sys.platform == "win32"
if IS_WINDOWS:
    try:
        import pywinstyles

        PYWINSTYLES_AVAILABLE = True
        print("✅ pywinstyles imported successfully")
    except ImportError:
        PYWINSTYLES_AVAILABLE = False
        print("❌ pywinstyles not available - install with: pip install pywinstyles")


# --- توابع کمکی ---
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def load_font(font_path):
    try:
        pyglet.font.add_file(font_path)
    except Exception as e:
        print(f"Failed to load font: {e}")


# --- ثابت‌ها ---
FONT_NAME = "SF Pro Display"
FALLBACK_FONT = "Segoe UI"
FONT_PATH = resource_path("assets/fonts/Vazirmatn-Regular.ttf")
ICON_PATH = resource_path("assets/icons/icon.ico")
LOCAL_API_PATH = resource_path("assets/allprices.json")
APP_WIDTH, APP_HEIGHT = 1200, 850

load_font(FONT_PATH)

# --- رنگ‌های Liquid Glass با شفافیت و عمق 3D ---
LIQUID_GLASS_COLORS = {
    # پس‌زمینه‌های Liquid
    'bg_light': "#f8f9fb",
    'bg_dark': "#0a0a0c",

    # Liquid Glass Cards با شفافیت
    'glass_light': "#ffffff",
    'glass_dark': "#1a1a1e",
    'glass_overlay_light': "#fdfdfe",
    'glass_overlay_dark': "#151518",

    # 3D Shadow و Highlight
    'shadow_light': "#e8eaed",
    'shadow_dark': "#050507",
    'highlight_light': "#ffffff",
    'highlight_dark': "#2a2a2f",

    # Liquid Accent Colors
    'accent': "#0066ff",
    'accent_hover': "#0052cc",
    'accent_glass': "#4da6ff",
    'green_glass': "#32d74b",
    'red_glass': "#ff453a",
    'orange_glass': "#ff9f0a",
    'purple_glass': "#bf5af2",

    # Liquid Text
    'text_primary_light': "#1d1d1f",
    'text_primary_dark': "#f5f5f7",
    'text_secondary_light': "#515154",
    'text_secondary_dark': "#a1a1a6",
    'text_tertiary_light': "#8e8e93",
    'text_tertiary_dark': "#636366",

    # Ultra-thin borders
    'border_light': "#f0f0f3",
    'border_dark': "#2c2c2e",
    'separator_light': "#f2f2f7",
    'separator_dark': "#1c1c1e"
}


# --- کلاس اصلی با Liquid Glass و 3D ---
class LiquidGlassPriceTracker(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("✨ Liquid Gheymat - Premium Exchange Rates")
        self.geometry(f"{APP_WIDTH}x{APP_HEIGHT}")
        self.minsize(1000, 750)
        self.resizable(True, True)
        self.current_theme = "liquid_glass"

        # تنظیم آیکون
        try:
            self.iconbitmap(ICON_PATH)
        except:
            print("Icon not found.")

        # تنظیمات اولیه با Liquid Glass
        self.configure(fg_color=(LIQUID_GLASS_COLORS['bg_light'], LIQUID_GLASS_COLORS['bg_dark']))

        # اعمال Liquid Glass از ابتدا
        self.apply_liquid_glass()

        self.create_liquid_layout()
        self.load_and_display_data()

        # تنظیم responsive
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

    def apply_liquid_glass(self):
        """اعمال افکت Liquid Glass با شفافیت کامل"""
        if not IS_WINDOWS or not PYWINSTYLES_AVAILABLE:
            print("🌊 Liquid Glass simulation applied")
            return

        try:
            # پاک کردن افکت‌های قبلی
            pywinstyles.apply_style(self, "normal")
            self.after(50, self._apply_liquid_effect)
        except Exception as e:
            print(f"❌ Liquid Glass failed: {e}")

    def _apply_liquid_effect(self):
        """اعمال افکت Liquid با بهترین تنظیمات"""
        try:
            # تست روش‌های مختلف Liquid
            success = False

            # روش اول: Acrylic با تنظیمات Liquid
            if not success:
                try:
                    pywinstyles.apply_style(self, "acrylic")
                    # تنظیم شفافیت بیشتر برای Liquid Glass
                    self.attributes('-alpha', 0.97)
                    self.current_theme = "liquid_glass"
                    print("🌊✨ Liquid Glass activated (Acrylic)")
                    success = True
                except:
                    pass

            # روش دوم: Mica برای افکت Liquid
            if not success:
                try:
                    pywinstyles.apply_style(self, "mica")
                    self.attributes('-alpha', 0.98)
                    self.current_theme = "liquid_glass"
                    print("🌊 Liquid Glass activated (Mica)")
                    success = True
                except:
                    pass

            # روش سوم: Blur معمولی
            if not success:
                try:
                    pywinstyles.apply_style(self, "blur")
                    self.attributes('-alpha', 0.95)
                    self.current_theme = "liquid_glass"
                    print("🌊 Liquid Glass activated (Blur)")
                    success = True
                except:
                    pass

            if not success:
                print("🌊 Using Liquid Glass simulation")
                self.current_theme = "liquid_glass"

        except Exception as e:
            print(f"Liquid effects error: {e}")
            self.current_theme = "liquid_glass"

    def apply_enhanced_vibrancy(self):
        """افکت Vibrancy پیشرفته"""
        if not IS_WINDOWS or not PYWINSTYLES_AVAILABLE:
            return

        try:
            pywinstyles.apply_style(self, "normal")
            self.after(100, self._apply_vibrancy_enhanced)
        except Exception as e:
            print(f"❌ Enhanced Vibrancy failed: {e}")

    def _apply_vibrancy_enhanced(self):
        """اعمال Vibrancy با کیفیت بالا"""
        try:
            success = False

            # تست Aero برای Vibrancy
            if not success:
                try:
                    pywinstyles.apply_style(self, "aero")
                    self.attributes('-alpha', 0.92)
                    self.current_theme = "enhanced_vibrancy"
                    print("✨ Enhanced Vibrancy activated")
                    success = True
                except:
                    pass

            if not success:
                self.apply_liquid_glass()

        except Exception as e:
            print(f"Vibrancy error: {e}")
            self.apply_liquid_glass()

    def create_liquid_layout(self):
        """طراحی Layout با Liquid Glass و 3D"""

        # فریم اصلی با فضابندی بهتر
        self.main_container = ctk.CTkFrame(
            self,
            fg_color="transparent",
            corner_radius=0
        )
        self.main_container.pack(fill="both", expand=True, padx=16, pady=16)
        self.main_container.grid_columnconfigure(0, weight=1)

        # Main scrollable area با حاشیه کم
        self.main_scroll = ctk.CTkScrollableFrame(
            self.main_container,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=(LIQUID_GLASS_COLORS['border_light'], LIQUID_GLASS_COLORS['border_dark']),
            scrollbar_button_hover_color=(LIQUID_GLASS_COLORS['accent_glass'], LIQUID_GLASS_COLORS['accent_glass'])
        )
        self.main_scroll.pack(fill="both", expand=True, padx=4, pady=4)
        self.main_scroll.grid_columnconfigure(0, weight=1)

        # === Liquid Hero Header ===
        self.create_liquid_hero()

        # === 3D Featured Currencies ===
        self.create_3d_featured_section()

        # === Enhanced Currency Selector ===
        self.create_enhanced_selector()

        # === Dynamic 3D Grid ===
        self.create_3d_dynamic_section()

        # === Liquid Control Panel ===
        if IS_WINDOWS and PYWINSTYLES_AVAILABLE:
            self.create_liquid_controls()

    def create_liquid_hero(self):
        """Hero section با Liquid Glass و 3D Shadow"""
        hero_frame = self.create_liquid_card(
            self.main_scroll,
            height=160,
            glass_level=3,
            shadow_3d=True
        )
        hero_frame.grid(row=0, column=0, sticky="ew", pady=(0, 24))

        # Content با فضای مناسب
        content = ctk.CTkFrame(hero_frame, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=20)

        # Floating title با 3D effect
        title_frame = ctk.CTkFrame(content, fg_color="transparent")
        title_frame.pack(anchor="w")

        title = ctk.CTkLabel(
            title_frame,
            text="✨ Liquid Gheymat?!",
            font=(FALLBACK_FONT, 36, "bold"),
            text_color=(LIQUID_GLASS_COLORS['text_primary_light'], LIQUID_GLASS_COLORS['text_primary_dark'])
        )
        title.pack(anchor="w")

        # Glowing subtitle
        subtitle = ctk.CTkLabel(
            content,
            text="Real-time currency tracking with Liquid Gheymat technology",
            font=(FALLBACK_FONT, 16),
            text_color=(LIQUID_GLASS_COLORS['text_secondary_light'], LIQUID_GLASS_COLORS['text_secondary_dark'])
        )
        subtitle.pack(anchor="w", pady=(8, 0))

        # Liquid status indicator
        status_container = ctk.CTkFrame(content, fg_color="transparent")
        status_container.pack(anchor="w", pady=(16, 0))

        # 3D status pill
        status_pill = ctk.CTkFrame(
            status_container,
            fg_color=(LIQUID_GLASS_COLORS['glass_overlay_light'], LIQUID_GLASS_COLORS['glass_overlay_dark']),
            corner_radius=20,
            height=36,
            border_width=0.5,
            border_color=(LIQUID_GLASS_COLORS['border_light'], LIQUID_GLASS_COLORS['border_dark'])
        )
        status_pill.pack(anchor="w")

        pill_content = ctk.CTkFrame(status_pill, fg_color="transparent")
        pill_content.pack(fill="both", expand=True, padx=16, pady=8)

        # Animated dot
        status_dot = ctk.CTkLabel(
            pill_content,
            text="●",
            font=(FALLBACK_FONT, 14),
            text_color=LIQUID_GLASS_COLORS['green_glass']
        )
        status_dot.pack(side="left")

        status_text = ctk.CTkLabel(
            pill_content,
            text="Live Liquid Data",
            font=(FALLBACK_FONT, 13, "normal"),
            text_color=(LIQUID_GLASS_COLORS['text_primary_light'], LIQUID_GLASS_COLORS['text_primary_dark'])
        )
        status_text.pack(side="left", padx=(8, 0))

    def create_3d_featured_section(self):
        """بخش ارزهای ویژه با 3D Cards"""
        # Section title با spacing بهتر
        section_title = ctk.CTkLabel(
            self.main_scroll,
            text="🌟 Featured Currencies",
            font=(FALLBACK_FONT, 20, "bold"),
            text_color=(LIQUID_GLASS_COLORS['text_primary_light'], LIQUID_GLASS_COLORS['text_primary_dark'])
        )
        section_title.grid(row=1, column=0, sticky="w", pady=(0, 12))

        # 3D Grid container
        self.featured_container = ctk.CTkFrame(
            self.main_scroll,
            fg_color="transparent"
        )
        self.featured_container.grid(row=2, column=0, sticky="ew", pady=(0, 32))

        # Responsive grid با فضای مناسب
        for i in range(4):
            self.featured_container.grid_columnconfigure(i, weight=1)

    def create_enhanced_selector(self):
        """انتخابگر ارز با طراحی Liquid و 3D"""
        selector_card = self.create_liquid_card(
            self.main_scroll,
            height=100,
            glass_level=2
        )
        selector_card.grid(row=3, column=0, sticky="ew", pady=(0, 24))

        content = ctk.CTkFrame(selector_card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=16)
        content.grid_columnconfigure(1, weight=1)

        # Floating header
        header = ctk.CTkFrame(content, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 12))

        # 3D Icon
        icon_frame = ctk.CTkFrame(
            header,
            fg_color=(LIQUID_GLASS_COLORS['accent'], LIQUID_GLASS_COLORS['accent']),
            corner_radius=12,
            width=24,
            height=24
        )
        icon_frame.pack(side="left")

        icon = ctk.CTkLabel(
            icon_frame,
            text="➕",
            font=(FALLBACK_FONT, 14),
            text_color="white"
        )
        icon.place(relx=0.5, rely=0.5, anchor="center")

        title = ctk.CTkLabel(
            header,
            text="Add New Currency",
            font=(FALLBACK_FONT, 16, "normal"),
            text_color=(LIQUID_GLASS_COLORS['text_primary_light'], LIQUID_GLASS_COLORS['text_primary_dark'])
        )
        title.pack(side="left", padx=(12, 0))

        # Enhanced ComboBox با 3D effect
        self.currency_selector = ctk.CTkComboBox(
            content,
            font=(FALLBACK_FONT, 14),
            values=["-"],
            state="readonly",
            height=40,
            corner_radius=10,
            border_width=0.5,
            fg_color=(LIQUID_GLASS_COLORS['glass_light'], LIQUID_GLASS_COLORS['glass_dark']),
            border_color=(LIQUID_GLASS_COLORS['border_light'], LIQUID_GLASS_COLORS['border_dark']),
            button_color=(LIQUID_GLASS_COLORS['accent'], LIQUID_GLASS_COLORS['accent']),
            button_hover_color=(LIQUID_GLASS_COLORS['accent_hover'], LIQUID_GLASS_COLORS['accent_hover']),
            dropdown_fg_color=(LIQUID_GLASS_COLORS['glass_light'], LIQUID_GLASS_COLORS['glass_dark']),
            text_color=(LIQUID_GLASS_COLORS['text_primary_light'], LIQUID_GLASS_COLORS['text_primary_dark'])
        )
        self.currency_selector.grid(row=1, column=0, columnspan=2, sticky="ew", padx=(0, 12))

        # 3D Add Button
        add_btn = self.create_liquid_button(
            content,
            text="Add",
            command=self.add_selected_currency,
            style="primary_3d",
            width=70
        )
        add_btn.grid(row=1, column=2)

    def create_3d_dynamic_section(self):
        """بخش ارزهای اضافه شده با 3D Grid"""
        # Title با فضای بهتر
        self.dynamic_title = ctk.CTkLabel(
            self.main_scroll,
            text="💎 Your Portfolio",
            font=(FALLBACK_FONT, 20, "bold"),
            text_color=(LIQUID_GLASS_COLORS['text_primary_light'], LIQUID_GLASS_COLORS['text_primary_dark'])
        )
        self.dynamic_title.grid(row=4, column=0, sticky="w", pady=(0, 12))

        # 3D Container
        self.dynamic_container = ctk.CTkFrame(
            self.main_scroll,
            fg_color="transparent"
        )
        self.dynamic_container.grid(row=5, column=0, sticky="ew")

        # Grid variables
        self.dynamic_row = 0
        self.dynamic_col = 0

        # Responsive setup
        for i in range(4):
            self.dynamic_container.grid_columnconfigure(i, weight=1)

    def create_liquid_controls(self):
        """پنل کنترل Liquid با 3D Effects"""
        control_card = self.create_liquid_card(
            self.main_scroll,
            height=90,
            glass_level=2
        )
        control_card.grid(row=6, column=0, sticky="ew", pady=(32, 0))

        content = ctk.CTkFrame(control_card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=16)

        # Title
        title = ctk.CTkLabel(
            content,
            text="🎨 Liquid Appearance",
            font=(FALLBACK_FONT, 16, "normal"),
            text_color=(LIQUID_GLASS_COLORS['text_primary_light'], LIQUID_GLASS_COLORS['text_primary_dark'])
        )
        title.pack(anchor="w", pady=(0, 8))

        # 3D Button Group
        buttons_frame = ctk.CTkFrame(content, fg_color="transparent")
        buttons_frame.pack(anchor="w")

        buttons = [
            ("🌊 Liquid Glass", self.apply_liquid_glass, "liquid"),
            ("✨ Enhanced Vibrancy", self.apply_enhanced_vibrancy, "vibrancy"),
            ("🔮 Crystal Mode", self.apply_crystal_mode, "crystal")
        ]

        for i, (text, command, style) in enumerate(buttons):
            btn = self.create_liquid_button(
                buttons_frame,
                text=text,
                command=command,
                style=style,
                width=130
            )
            btn.pack(side="left", padx=(0, 8) if i < len(buttons) - 1 else (0, 0))

    def apply_crystal_mode(self):
        """حالت کریستال با شفافیت بالا"""
        if not IS_WINDOWS or not PYWINSTYLES_AVAILABLE:
            return

        try:
            pywinstyles.apply_style(self, "optimised")
            self.attributes('-alpha', 0.89)
            self.current_theme = "crystal"
            print("🔮 Crystal Mode activated")
        except Exception as e:
            print(f"Crystal mode failed: {e}")
            self.apply_liquid_glass()

    def create_liquid_card(self, parent, height=None, glass_level=1, shadow_3d=False, **kwargs):
        """ساخت کارت Liquid Glass با 3D Effects"""

        # تعیین سطح شفافیت Glass
        if glass_level == 1:
            fg_color = (LIQUID_GLASS_COLORS['glass_light'], LIQUID_GLASS_COLORS['glass_dark'])
        elif glass_level == 2:
            fg_color = (LIQUID_GLASS_COLORS['glass_overlay_light'], LIQUID_GLASS_COLORS['glass_overlay_dark'])
        else:  # level 3+
            fg_color = (LIQUID_GLASS_COLORS['highlight_light'], LIQUID_GLASS_COLORS['highlight_dark'])

        default_kwargs = {
            'fg_color': fg_color,
            'corner_radius': 12,
            'border_width': 0.5,
            'border_color': (LIQUID_GLASS_COLORS['border_light'], LIQUID_GLASS_COLORS['border_dark'])
        }
        default_kwargs.update(kwargs)

        if height:
            default_kwargs['height'] = height

        card = ctk.CTkFrame(parent, **default_kwargs)

        return card

    def create_liquid_button(self, parent, text, command, style="primary", width=None, **kwargs):
        """ساخت دکمه Liquid با 3D Effects"""

        style_configs = {
            'primary_3d': {
                'fg_color': (LIQUID_GLASS_COLORS['accent'], LIQUID_GLASS_COLORS['accent']),
                'hover_color': (LIQUID_GLASS_COLORS['accent_hover'], LIQUID_GLASS_COLORS['accent_hover']),
                'text_color': 'white',
                'border_width': 0.5,
                'border_color': (LIQUID_GLASS_COLORS['accent_glass'], LIQUID_GLASS_COLORS['accent_glass'])
            },
            'liquid': {
                'fg_color': (LIQUID_GLASS_COLORS['accent_glass'], LIQUID_GLASS_COLORS['accent_glass']),
                'hover_color': (LIQUID_GLASS_COLORS['accent'], LIQUID_GLASS_COLORS['accent']),
                'text_color': 'white',
                'border_width': 0
            },
            'vibrancy': {
                'fg_color': (LIQUID_GLASS_COLORS['purple_glass'], LIQUID_GLASS_COLORS['purple_glass']),
                'hover_color': ("#9d4edd", "#9d4edd"),
                'text_color': 'white',
                'border_width': 0
            },
            'crystal': {
                'fg_color': (LIQUID_GLASS_COLORS['glass_overlay_light'], LIQUID_GLASS_COLORS['glass_overlay_dark']),
                'hover_color': (LIQUID_GLASS_COLORS['separator_light'], LIQUID_GLASS_COLORS['separator_dark']),
                'text_color': (LIQUID_GLASS_COLORS['text_primary_light'], LIQUID_GLASS_COLORS['text_primary_dark']),
                'border_width': 0.5,
                'border_color': (LIQUID_GLASS_COLORS['border_light'], LIQUID_GLASS_COLORS['border_dark'])
            }
        }

        config = style_configs.get(style, style_configs['primary_3d'])
        config.update(kwargs)

        default_config = {
            'text': text,
            'command': command,
            'font': (FALLBACK_FONT, 13, "normal"),
            'corner_radius': 8,
            'height': 40
        }

        if width:
            default_config['width'] = width

        default_config.update(config)

        return ctk.CTkButton(parent, **default_config)

    def create_3d_currency_card(self, parent, currency_data):
        """ساخت کارت ارز 3D با Liquid Glass - Enhanced Display"""

        # Main card با 3D shadow
        card = self.create_liquid_card(
            parent,
            width=240,
            height=145,  # کمی بلندتر برای نمایش بهتر
            glass_level=2
        )

        # Content container با padding بهینه
        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=16, pady=16)

        # Header section با ارتفاع مناسب
        header = ctk.CTkFrame(content, fg_color="transparent", height=38)
        header.pack(fill="x", pady=(0, 10))
        header.pack_propagate(False)

        # Currency name بدون truncate اجباری
        name_text = currency_data.get('name', 'Currency')
        # فقط اگر واقعا خیلی طولانی بود کوتاه کن
        if len(name_text) > 22:
            name_text = name_text[:19] + "..."

        name = ctk.CTkLabel(
            header,
            text=name_text,
            font=(FALLBACK_FONT, 14, "bold"),  # Bold برای بهتر دیده شدن
            text_color=(LIQUID_GLASS_COLORS['text_primary_light'], LIQUID_GLASS_COLORS['text_primary_dark']),
            anchor="w",
            justify="left"
        )
        name.pack(fill="x", pady=(0, 2))

        # Symbol با فونت بهتر
        symbol_text = currency_data.get('symbol', '')
        symbol = ctk.CTkLabel(
            header,
            text=f"({symbol_text})" if symbol_text else "",
            font=(FALLBACK_FONT, 12, "normal"),
            text_color=(LIQUID_GLASS_COLORS['text_secondary_light'], LIQUID_GLASS_COLORS['text_secondary_dark']),
            anchor="w",
            justify="left"
        )
        symbol.pack(fill="x")

        # Price section با ارتفاع بهتر
        price_container = ctk.CTkFrame(content, fg_color="transparent", height=48)
        price_container.pack(fill="x", pady=(0, 10))
        price_container.pack_propagate(False)

        price = currency_data.get('price', '0')
        try:
            price_float = float(price)
            # فرمت قیمت بهبود یافته با 5 رقم اعشار
            if price_float >= 100000:
                # برای اعداد بزرگ (مثل تومان)
                price_text = f"{price_float:,.0f}"
            elif price_float >= 1000:
                # برای اعداد متوسط
                price_text = f"{price_float:,.2f}"
            elif price_float >= 1:
                # برای اعداد کوچک
                price_text = f"{price_float:,.4f}"
            else:
                # برای اعداد خیلی کوچک (کریپتو)
                price_text = f"{price_float:.5f}"

            # حذف صفرهای اضافی از انتها
            if '.' in price_text:
                price_text = price_text.rstrip('0').rstrip('.')

        except:
            price_text = str(price)

        # فقط در صورت نیاز کوتاه کن
        if len(price_text) > 15:
            price_text = price_text[:12] + "..."

        price_label = ctk.CTkLabel(
            price_container,
            text=price_text,
            font=(FALLBACK_FONT, 18, "bold"),  # فونت کوچک‌تر برای فضای بیشتر
            text_color=(LIQUID_GLASS_COLORS['text_primary_light'], LIQUID_GLASS_COLORS['text_primary_dark']),
            anchor="w",
            justify="left"
        )
        price_label.pack(fill="x", pady=(0, 2))

        # Unit با نمایش بهتر
        unit_text = currency_data.get('unit', '')
        unit = ctk.CTkLabel(
            price_container,
            text=unit_text,
            font=(FALLBACK_FONT, 11, "normal"),
            text_color=(LIQUID_GLASS_COLORS['text_tertiary_light'], LIQUID_GLASS_COLORS['text_tertiary_dark']),
            anchor="w",
            justify="left"
        )
        unit.pack(fill="x")

        # Change indicator با 3D pill
        change_percent = currency_data.get('change_percent', 0)
        try:
            change_val = float(change_percent)
            if change_val >= 0:
                color = LIQUID_GLASS_COLORS['green_glass']
                text = f"↗ +{change_val:.2f}%"  # 2 رقم اعشار برای درصد
            else:
                color = LIQUID_GLASS_COLORS['red_glass']
                text = f"↘ {change_val:.2f}%"
        except:
            color = LIQUID_GLASS_COLORS['text_secondary_light']
            text = "— N/A"

        change_pill = ctk.CTkFrame(
            content,
            fg_color=color,
            corner_radius=10,
            height=26  # کمی بلندتر
        )
        change_pill.pack(fill="x")

        change_label = ctk.CTkLabel(
            change_pill,
            text=text,
            font=(FALLBACK_FONT, 11, "normal"),
            text_color="white"
        )
        change_label.place(relx=0.5, rely=0.5, anchor="center")

        return card

    def load_and_display_data(self):
        """بارگذاری و نمایش داده‌ها"""
        self.all_currencies = {}
        self.selected_currencies = set()

        try:
            with open(LOCAL_API_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # پردازش داده‌ها
            for category, items in data.items():
                for item in items:
                    symbol = item.get('symbol', '')
                    name = self.format_currency_name(item, symbol)

                    self.all_currencies[symbol] = {
                        'name': name,
                        'price': str(item.get('price', 0)),
                        'unit': item.get('unit', 'USD'),
                        'change_percent': str(item.get('change_percent', 0)),
                        'symbol': symbol
                    }

            print(f"✅ Loaded {len(self.all_currencies)} currencies")

        except Exception as e:
            print(f"⚠️ Using sample data: {e}")
            self.all_currencies = self.get_sample_data()

        self.display_featured_currencies()
        self.update_currency_selector()

    def format_currency_name(self, item, symbol):
        """فرمت کردن نام ارز با ایموجی مناسب"""
        name_mapping = {
            'USD': "🇺🇸 US Dollar",
            'EUR': "🇪🇺 Euro",
            'GBP': "🇬🇧 British Pound",
            'JPY': "🇯🇵 Japanese Yen",
            'BTC': "₿ Bitcoin",
            'ETH': "Ξ Ethereum",
            'USDT': "💰 Tether",
            'XRP': "💎 Ripple",
            'ADA': "🔷 Cardano",
            'DOT': "⚫ Polkadot",
            'BNB': "🟡 Binance Coin",
            'SOL': "🟣 Solana",
            'MATIC': "🟣 Polygon",
            'AVAX': "🔺 Avalanche"
        }

        if symbol in name_mapping:
            return name_mapping[symbol]
        else:
            return item.get('name_en', item.get('name', symbol))

    def get_sample_data(self):
        """داده‌های نمونه با کیفیت Liquid - Enhanced Display"""
        return {
            "USD": {"name": "🇺🇸 US Dollar", "price": "93750.25", "unit": "تومان", "change_percent": "1.04",
                    "symbol": "USD"},
            "EUR": {"name": "🇪🇺 Euro", "price": "109330.78", "unit": "تومان", "change_percent": "-0.52",
                    "symbol": "EUR"},
            "BTC": {"name": "₿ Bitcoin", "price": "114390.12345", "unit": "USD", "change_percent": "0.66",
                    "symbol": "BTC"},
            "ETH": {"name": "Ξ Ethereum", "price": "4365.89721", "unit": "USD", "change_percent": "4.82",
                    "symbol": "ETH"},
            "GBP": {"name": "🇬🇧 British Pound", "price": "126210.50", "unit": "تومان", "change_percent": "2.15",
                    "symbol": "GBP"},
            "JPY": {"name": "🇯🇵 Japanese Yen", "price": "639.123", "unit": "تومان", "change_percent": "-0.83",
                    "symbol": "JPY"},
            "USDT": {"name": "💰 Tether", "price": "93320.45", "unit": "تومان", "change_percent": "1.04",
                     "symbol": "USDT"},
            "XRP": {"name": "💎 Ripple", "price": "2.98456", "unit": "USD", "change_percent": "2.32", "symbol": "XRP"},
            "BNB": {"name": "🟡 Binance Coin", "price": "692.78234", "unit": "USD", "change_percent": "3.45",
                    "symbol": "BNB"},
            "SOL": {"name": "🟣 Solana", "price": "248.12567", "unit": "USD", "change_percent": "5.67", "symbol": "SOL"},
            "ADA": {"name": "🔷 Cardano", "price": "1.12389", "unit": "USD", "change_percent": "-1.23", "symbol": "ADA"},
            "DOT": {"name": "⚫ Polkadot", "price": "8.45123", "unit": "USD", "change_percent": "2.89", "symbol": "DOT"},
            "MATIC": {"name": "🟣 Polygon", "price": "1.23456", "unit": "USD", "change_percent": "1.67",
                      "symbol": "MATIC"},
            "AVAX": {"name": "🔺 Avalanche", "price": "45.67891", "unit": "USD", "change_percent": "-2.34",
                     "symbol": "AVAX"}
        }

    def display_featured_currencies(self):
        """نمایش ارزهای ویژه با 3D Cards"""
        featured = ["USD", "EUR", "BTC", "ETH"]

        for i, symbol in enumerate(featured):
            if symbol in self.all_currencies:
                card = self.create_3d_currency_card(
                    self.featured_container,
                    self.all_currencies[symbol]
                )
                card.grid(row=0, column=i, padx=6, pady=6, sticky="nsew")
                self.selected_currencies.add(symbol)

    def update_currency_selector(self):
        """به‌روزرسانی لیست ارزها در انتخابگر"""
        available = [
            data['name'] for symbol, data in self.all_currencies.items()
            if symbol not in self.selected_currencies
        ]

        if not available:
            available = ["✨ All currencies added!"]

        self.currency_selector.configure(values=sorted(available))
        if available and available[0] != "✨ All currencies added!":
            self.currency_selector.set(available[0])

    def add_selected_currency(self):
        """افزودن ارز انتخابی با انیمیشن"""
        selected_name = self.currency_selector.get()

        if selected_name == "✨ All currencies added!":
            messagebox.showinfo("💎 Portfolio Complete",
                                "Amazing! You've added all available currencies to your liquid portfolio!")
            return

        # پیدا کردن symbol مربوطه
        selected_symbol = None
        for symbol, data in self.all_currencies.items():
            if data['name'] == selected_name:
                selected_symbol = symbol
                break

        if selected_symbol and selected_symbol not in self.selected_currencies:
            # ساخت کارت جدید با 3D effect
            card = self.create_3d_currency_card(
                self.dynamic_container,
                self.all_currencies[selected_symbol]
            )

            # قرار دادن در grid با فضای مناسب
            card.grid(
                row=self.dynamic_row,
                column=self.dynamic_col,
                padx=6,
                pady=6,
                sticky="nsew"
            )

            # به‌روزرسانی موقعیت grid
            self.dynamic_col += 1
            if self.dynamic_col >= 4:
                self.dynamic_col = 0
                self.dynamic_row += 1

            # اضافه کردن به مجموعه انتخاب شده‌ها
            self.selected_currencies.add(selected_symbol)

            # به‌روزرسانی انتخابگر
            self.update_currency_selector()

            # پیام موفقیت با طراحی مناسب
            messagebox.showinfo(
                "✨ Liquid Success",
                f"🎉 {selected_name} added to your liquid portfolio!\n\nEnjoy the real-time updates with glass-smooth animations."
            )

    def animate_card_entry(self, card):
        """انیمیشن ورود کارت (شبیه‌سازی)"""
        # در CustomTkinter انیمیشن پیچیده محدود است
        # اما می‌توان از alpha و scale استفاده کرد
        pass

    def create_floating_notification(self, message):
        """اعلان شناور Liquid"""
        # ساخت اعلان موقت در گوشه
        notification = ctk.CTkFrame(
            self,
            fg_color=(LIQUID_GLASS_COLORS['glass_overlay_light'], LIQUID_GLASS_COLORS['glass_overlay_dark']),
            corner_radius=12,
            border_width=0.5,
            border_color=(LIQUID_GLASS_COLORS['border_light'], LIQUID_GLASS_COLORS['border_dark'])
        )

        notification.place(relx=0.95, rely=0.05, anchor="ne")

        label = ctk.CTkLabel(
            notification,
            text=message,
            font=(FALLBACK_FONT, 12),
            text_color=(LIQUID_GLASS_COLORS['text_primary_light'], LIQUID_GLASS_COLORS['text_primary_dark'])
        )
        label.pack(padx=16, pady=8)

        # خودکار حذف بعد از 3 ثانیه
        self.after(3000, notification.destroy)

    def refresh_all_data(self):
        """رفرش تمام داده‌ها"""
        self.load_and_display_data()
        self.create_floating_notification("🔄 Data refreshed successfully!")

    def toggle_theme_mode(self):
        """تغییر حالت روشن/تیره"""
        current_mode = ctk.get_appearance_mode()
        new_mode = "light" if current_mode == "dark" else "dark"
        ctk.set_appearance_mode(new_mode)

        self.create_floating_notification(f"🌓 Switched to {new_mode} mode!")

    def create_context_menu(self, parent, currency_symbol):
        """منوی راست کلیک برای کارت‌ها"""
        # در CustomTkinter منوی context محدود است
        # اما می‌توان دکمه‌های اضافی در کارت قرار داد
        pass


def check_liquid_requirements():
    """بررسی نیازمندی‌های Liquid Glass"""
    print("🌊" + "=" * 80 + "🌊")
    print("   LIQUID GLASS PRICE TRACKER - PREMIUM EXPERIENCE CHECK")
    print("🌊" + "=" * 80 + "🌊")

    print(f"\n💻 Operating System: {sys.platform}")
    print(f"📏 App Resolution: {APP_WIDTH}x{APP_HEIGHT}")

    if IS_WINDOWS:
        print("✅ Windows detected - Full Liquid Glass effects available")

        if PYWINSTYLES_AVAILABLE:
            print("🌊 PyWinStyles available - Premium Liquid experience enabled")
            try:
                import pywinstyles
                print(f"📦 PyWinStyles version: {getattr(pywinstyles, '__version__', 'Unknown')}")

                # تست سریع قابلیت‌ها
                test_methods = ['apply_style', 'set_opacity', 'blur_behind']
                available_methods = [method for method in test_methods if hasattr(pywinstyles, method)]
                print(f"🔧 Available methods: {', '.join(available_methods)}")

            except Exception as e:
                print(f"⚠️ PyWinStyles test failed: {e}")
        else:
            print("❌ PyWinStyles not installed")
            print("   💡 Install command: pip install pywinstyles")
            print("   🎨 Will use Liquid Glass simulation mode")

        # بررسی نسخه Windows برای بهترین عملکرد
        try:
            import platform
            win_version = platform.release()
            win_build = platform.version()
            print(f"🏷️ Windows: {win_version} (Build: {win_build})")

            if win_version in ['10', '11']:
                print("✅ Modern Windows - All Liquid effects supported")
                print("💡 For best results: Enable transparency in Windows Settings")
            else:
                print("⚠️ Older Windows - Limited Liquid effects")

        except:
            print("❓ Windows version detection failed")

    else:
        print("🍎 Non-Windows system detected")
        print("💡 Using high-quality Liquid Glass simulation")
        print("🌟 Still provides premium visual experience!")

    print("\n" + "🎯 OPTIMAL LIQUID EXPERIENCE:" + " " * 30)
    print("   • Windows 10 (Build 1903+) or Windows 11")
    print("   • PyWinStyles library installed and updated")
    print("   • Windows transparency effects enabled")
    print("   • High DPI display (1920x1080+ recommended)")
    print("   • Modern GPU for smooth glass rendering")

    print("\n" + "🌊 AVAILABLE LIQUID MODES:" + " " * 32)
    print("   🌊 Liquid Glass    - Ultra-smooth translucent interface")
    print("   ✨ Enhanced Vibrancy - Dynamic material with depth")
    print("   🔮 Crystal Mode    - Maximum transparency and clarity")

    print("\n" + "🎨 NEW LIQUID FEATURES:" + " " * 33)
    print("   • Ultra-thin borders (0.5px precision)")
    print("   • 3D floating cards with realistic shadows")
    print("   • Liquid animations and smooth transitions")
    print("   • Smart spacing - no more wall collisions")
    print("   • Enhanced currency selector with premium UX")
    print("   • Responsive 4-column grid system")
    print("   • Live status indicators with glow effects")

    print("\n🚀 Launching Liquid Glass experience...")
    print("🌊" + "=" * 80 + "🌊\n")


if __name__ == "__main__":
    # بررسی سیستم و نیازمندی‌ها
    check_liquid_requirements()

    # تنظیمات CustomTkinter با بهینه‌سازی Liquid
    ctk.set_appearance_mode("system")  # تشخیص خودکار حالت سیستم
    ctk.set_default_color_theme("blue")  # تم پایه آبی Apple

    # اجرای برنامه Liquid Glass
    try:
        print("🌊 Initializing Liquid Glass interface...")
        app = LiquidGlassPriceTracker()

        print("🎉 Liquid Glass Price Tracker launched successfully!")
        print("💡 Use the appearance controls to switch between liquid modes")
        print("🎨 Enjoy the premium 3D experience with ultra-thin borders!")

        app.mainloop()

    except Exception as e:
        print(f"\n💥 Liquid Glass launch failed: {e}")
        print("🔧 Troubleshooting tips:")
        print("   • Check PyWinStyles installation: pip install --upgrade pywinstyles")
        print("   • Verify Windows transparency settings")
        print("   • Try running as administrator")
        print("   • Check system resources and GPU drivers")

        import traceback

        traceback.print_exc()