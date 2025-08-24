import customtkinter as ctk
import sys
import os
import json
import pyglet
from tkinter import messagebox
import math
import requests
import threading
from datetime import datetime

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
# API URL instead of local file
API_URL = "https://brsapi.ir/Api/Market/Gold_Currency.php?key=BWUuKdavyBLGXxidEjfNJeb33rsryQfh"
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
        
        # Initialize API status
        self.api_status = "connecting"
        self.last_update = "Never"

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
        
        # Start auto-refresh timer
        self.start_auto_refresh()

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
        
        # === Refresh Controls ===
        self.create_refresh_controls()

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
            text="✨ Liquid Gheymat Live!",
            font=(FALLBACK_FONT, 36, "bold"),
            text_color=(LIQUID_GLASS_COLORS['text_primary_light'], LIQUID_GLASS_COLORS['text_primary_dark'])
        )
        title.pack(anchor="w")

        # Glowing subtitle
        subtitle = ctk.CTkLabel(
            content,
            text="Real-time currency tracking with Live API updates",
            font=(FALLBACK_FONT, 16),
            text_color=(LIQUID_GLASS_COLORS['text_secondary_light'], LIQUID_GLASS_COLORS['text_secondary_dark'])
        )
        subtitle.pack(anchor="w", pady=(8, 0))

        # Live API status indicator
        status_container = ctk.CTkFrame(content, fg_color="transparent")
        status_container.pack(anchor="w", pady=(16, 0))

        # 3D status pill
        self.status_pill = ctk.CTkFrame(
            status_container,
            fg_color=(LIQUID_GLASS_COLORS['glass_overlay_light'], LIQUID_GLASS_COLORS['glass_overlay_dark']),
            corner_radius=20,
            height=36,
            border_width=0.5,
            border_color=(LIQUID_GLASS_COLORS['border_light'], LIQUID_GLASS_COLORS['border_dark'])
        )
        self.status_pill.pack(anchor="w")

        pill_content = ctk.CTkFrame(self.status_pill, fg_color="transparent")
        pill_content.pack(fill="both", expand=True, padx=16, pady=8)

        # Animated dot
        self.status_dot = ctk.CTkLabel(
            pill_content,
            text="●",
            font=(FALLBACK_FONT, 14),
            text_color=LIQUID_GLASS_COLORS['orange_glass']
        )
        self.status_dot.pack(side="left")

        self.status_text = ctk.CTkLabel(
            pill_content,
            text="Connecting to Live API...",
            font=(FALLBACK_FONT, 13, "normal"),
            text_color=(LIQUID_GLASS_COLORS['text_primary_light'], LIQUID_GLASS_COLORS['text_primary_dark'])
        )
        self.status_text.pack(side="left", padx=(8, 0))

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

    def create_refresh_controls(self):
        """بخش کنترل‌های رفرش و آپدیت"""
        refresh_card = self.create_liquid_card(
            self.main_scroll,
            height=120,
            glass_level=2
        )
        refresh_card.grid(row=7, column=0, sticky="ew", pady=(16, 0))

        content = ctk.CTkFrame(refresh_card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=16)

        # Title
        title = ctk.CTkLabel(
            content,
            text="🔄 Live Data Controls",
            font=(FALLBACK_FONT, 16, "normal"),
            text_color=(LIQUID_GLASS_COLORS['text_primary_light'], LIQUID_GLASS_COLORS['text_primary_dark'])
        )
        title.pack(anchor="w", pady=(0, 8))

        # Top controls frame
        controls_frame = ctk.CTkFrame(content, fg_color="transparent")
        controls_frame.pack(anchor="w", pady=(0, 8))

        # Refresh button
        refresh_btn = self.create_liquid_button(
            controls_frame,
            text="🔄 Refresh Now",
            command=self.manual_refresh,
            style="primary_3d",
            width=120
        )
        refresh_btn.pack(side="left", padx=(0, 12))

        # Test API button for debugging
        test_btn = self.create_liquid_button(
            controls_frame,
            text="🔍 Test API",
            command=self.test_api_connection,
            style="crystal",
            width=100
        )
        test_btn.pack(side="left", padx=(0, 12))

        # Last update label
        self.last_update_label = ctk.CTkLabel(
            controls_frame,
            text=f"Last Update: {self.last_update}",
            font=(FALLBACK_FONT, 12),
            text_color=(LIQUID_GLASS_COLORS['text_secondary_light'], LIQUID_GLASS_COLORS['text_secondary_dark'])
        )
        self.last_update_label.pack(side="left")
        
    def test_api_connection(self):
        """تست اتصال API برای debugging"""
        def test_thread():
            try:
                self.after(0, lambda: self.update_api_status("connecting", "Testing API..."))
                
                print("\n" + "="*60)
                print("🧪 API CONNECTION TEST STARTED")
                print("="*60)
                
                # Basic connection test
                print(f"🌐 Testing URL: {API_URL}")
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'application/json, text/plain, */*',
                }
                
                response = requests.get(API_URL, headers=headers, timeout=10)
                
                print(f"📡 Status Code: {response.status_code}")
                print(f"📄 Content-Type: {response.headers.get('content-type', 'Unknown')}")
                print(f"📏 Content Length: {len(response.text)} characters")
                print(f"🔗 Final URL: {response.url}")
                
                if response.status_code == 200:
                    print("✅ HTTP request successful")
                    
                    # Try to parse JSON
                    try:
                        data = response.json()
                        print(f"✅ JSON parsing successful")
                        print(f"📊 Data type: {type(data)}")
                        
                        if isinstance(data, dict):
                            print(f"🗂️ Keys: {list(data.keys())}")
                            for key, value in data.items():
                                print(f"   {key}: {type(value)} ({len(value) if hasattr(value, '__len__') else 'N/A'} items)")
                        elif isinstance(data, list):
                            print(f"📋 List with {len(data)} items")
                            if len(data) > 0:
                                print(f"   First item type: {type(data[0])}")
                                if isinstance(data[0], dict):
                                    print(f"   First item keys: {list(data[0].keys())}")
                        
                        # Test processing
                        test_currencies = {}
                        processed = 0
                        
                        if isinstance(data, dict):
                            for category, items in data.items():
                                if isinstance(items, list):
                                    for item in items:
                                        if isinstance(item, dict) and item.get('symbol'):
                                            processed += 1
                                            test_currencies[item['symbol']] = item
                                            if processed >= 3:  # Just test first 3
                                                break
                        
                        print(f"🔬 Test processing: {processed} currencies found")
                        for symbol, item in test_currencies.items():
                            print(f"   {symbol}: {item.get('price', 'No price')} {item.get('unit', 'No unit')}")
                        
                        self.after(0, lambda: messagebox.showinfo(
                            "✅ API Test Success",
                            f"API is working!\n\n"
                            f"Status: {response.status_code}\n"
                            f"Data Type: {type(data).__name__}\n"
                            f"Currencies Found: {processed}\n\n"
                            f"Check console for detailed info."
                        ))
                        
                    except Exception as json_error:
                        print(f"❌ JSON parsing failed: {json_error}")
                        print(f"📝 Raw response (first 200 chars):")
                        print(response.text[:200])
                        
                        self.after(0, lambda: messagebox.showerror(
                            "❌ JSON Error",
                            f"API responded but data is not valid JSON:\n\n"
                            f"{str(json_error)}\n\n"
                            f"Raw response: {response.text[:100]}..."
                        ))
                else:
                    print(f"❌ HTTP error: {response.status_code}")
                    print(f"📝 Response: {response.text[:200]}")
                    
                    self.after(0, lambda: messagebox.showerror(
                        "❌ HTTP Error",
                        f"API returned error {response.status_code}\n\n"
                        f"Response: {response.text[:100]}..."
                    ))
                
                print("="*60)
                print("🧪 API TEST COMPLETED")
                print("="*60 + "\n")
                
            except Exception as e:
                print(f"💥 API test failed: {e}")
                import traceback
                traceback.print_exc()
                
                self.after(0, lambda: messagebox.showerror(
                    "💥 Connection Failed", 
                    f"Could not connect to API:\n\n{str(e)}"
                ))
            
            finally:
                self.after(0, lambda: self.update_api_status("error", "Test Completed"))
        
        threading.Thread(target=test_thread, daemon=True).start()

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
            text = "– N/A"

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

    def fetch_api_data(self):
        """دریافت داده‌ها از API با headers و debugging بهتر"""
        try:
            print(f"🌐 Fetching data from API: {API_URL}")
            self.update_api_status("connecting", "Fetching Live Data...")
            
            # Headers برای درخواست بهتر
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'fa-IR,fa;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Cache-Control': 'no-cache'
            }
            
            # درخواست با تنظیمات بهتر
            response = requests.get(
                API_URL, 
                headers=headers,
                timeout=15,
                verify=True,  # SSL verification
                allow_redirects=True
            )
            
            print(f"📡 Response status code: {response.status_code}")
            print(f"📝 Response headers: {dict(response.headers)}")
            
            # بررسی status code
            response.raise_for_status()
            
            # بررسی content type
            content_type = response.headers.get('content-type', '')
            print(f"📄 Content type: {content_type}")
            
            # تلاش برای parse کردن JSON
            try:
                data = response.json()
            except ValueError as json_error:
                # اگر JSON نبود، متن خام را چاپ کن
                print(f"❌ JSON parse error: {json_error}")
                print(f"📝 Raw response text (first 500 chars): {response.text[:500]}")
                raise ValueError(f"Invalid JSON response: {json_error}")
            
            # بررسی وجود داده
            if not data:
                raise ValueError("Empty response from API")
            
            # Debug info
            print(f"📊 Response data type: {type(data)}")
            if isinstance(data, dict):
                print(f"🗂️ Available keys: {list(data.keys())}")
                print(f"✅ Successfully fetched {len(data)} categories from API")
            elif isinstance(data, list):
                print(f"📋 List with {len(data)} items")
            else:
                print(f"⚠️ Unexpected data format: {type(data)}")
            
            self.update_api_status("connected", "Live Data Connected")
            self.last_update = datetime.now().strftime("%H:%M:%S")
            
            return data
            
        except requests.exceptions.Timeout:
            print("⏱️ API request timed out after 15 seconds")
            self.update_api_status("error", "Connection Timeout")
            return None
        except requests.exceptions.ConnectionError as e:
            print(f"🌐 Connection error to API: {e}")
            self.update_api_status("error", "Connection Failed")
            return None
        except requests.exceptions.HTTPError as e:
            print(f"📡 HTTP error: {e}")
            print(f"📄 Response text: {e.response.text[:200] if e.response else 'No response'}")
            status_code = e.response.status_code if e.response else "Unknown"
            self.update_api_status("error", f"HTTP Error: {status_code}")
            return None
        except requests.exceptions.SSLError as e:
            print(f"🔒 SSL error: {e}")
            self.update_api_status("error", "SSL Certificate Error")
            return None
        except ValueError as e:
            print(f"📊 Data parsing error: {e}")
            self.update_api_status("error", "Invalid Data Format")
            return None
        except Exception as e:
            print(f"❌ Unexpected API error: {e}")
            import traceback
            traceback.print_exc()
            self.update_api_status("error", "API Error")
            return None

    def update_api_status(self, status, message):
        """به‌روزرسانی وضعیت API در رابط کاربری"""
        self.api_status = status
        
        try:
            if status == "connected":
                color = LIQUID_GLASS_COLORS['green_glass']
                dot_text = "●"
            elif status == "connecting":
                color = LIQUID_GLASS_COLORS['orange_glass']
                dot_text = "●"
            else:  # error
                color = LIQUID_GLASS_COLORS['red_glass']
                dot_text = "●"
            
            self.status_dot.configure(text_color=color, text=dot_text)
            self.status_text.configure(text=message)
            
            if hasattr(self, 'last_update_label'):
                self.last_update_label.configure(text=f"Last Update: {self.last_update}")
                
        except Exception as e:
            print(f"Status update error: {e}")

    def load_and_display_data(self):
        """بارگذاری و نمایش داده‌ها از API با fallback بهتر"""
        self.all_currencies = {}
        self.selected_currencies = set()

        # دریافت داده‌ها از API
        api_data = self.fetch_api_data()
        
        if api_data:
            try:
                # پردازش داده‌های API - انعطاف‌پذیر برای فرمت‌های مختلف
                processed_count = 0
                
                # حالت 1: اگر data یک dict با categories باشد
                if isinstance(api_data, dict):
                    for category, items in api_data.items():
                        if isinstance(items, list):
                            for item in items:
                                if self.process_currency_item(item):
                                    processed_count += 1
                        elif isinstance(items, dict):
                            # اگر items خودش یک currency object باشد
                            if self.process_currency_item(items):
                                processed_count += 1
                
                # حالت 2: اگر data مستقیماً یک list باشد
                elif isinstance(api_data, list):
                    for item in api_data:
                        if self.process_currency_item(item):
                            processed_count += 1
                
                # حالت 3: اگر data یک currency object مستقیم باشد
                elif isinstance(api_data, dict) and api_data.get('symbol'):
                    if self.process_currency_item(api_data):
                        processed_count += 1

                if processed_count > 0:
                    print(f"✅ Processed {processed_count} currencies from API")
                    self.update_api_status("connected", f"Loaded {processed_count} currencies")
                else:
                    print("⚠️ No valid currencies found in API response")
                    self.all_currencies = self.get_sample_data()
                    self.update_api_status("error", "No Valid Data")

            except Exception as e:
                print(f"⚠️ API data processing error: {e}")
                import traceback
                traceback.print_exc()
                self.all_currencies = self.get_sample_data()
                self.update_api_status("error", "Data Processing Error")
        else:
            # در صورت عدم دسترسی به API از داده‌های نمونه استفاده کن
            print("🔄 Using sample data due to API unavailability")
            self.all_currencies = self.get_sample_data()

        # اگر هیچ داده‌ای نداریم، از نمونه استفاده کن
        if not self.all_currencies:
            print("📊 No data available, using sample dataset")
            self.all_currencies = self.get_sample_data()

        self.display_featured_currencies()
        self.update_currency_selector()

    def process_currency_item(self, item):
        """پردازش یک آیتم ارز از API"""
        try:
            if not isinstance(item, dict):
                return False
                
            # استخراج symbol با روش‌های مختلف
            symbol = item.get('symbol') or item.get('Symbol') or item.get('code') or item.get('Code')
            
            if not symbol:
                # تلاش برای استخراج از key های مختلف
                for key in ['name', 'Name', 'currency', 'Currency']:
                    if key in item:
                        symbol = str(item[key]).upper()
                        break
                
            if not symbol:
                return False
            
            # استخراج price
            price = item.get('price') or item.get('Price') or item.get('value') or item.get('Value') or 0
            
            # استخراج change_percent
            change = item.get('change_percent') or item.get('Change_Percent') or item.get('change') or item.get('Change') or 0
            
            # استخراج unit
            unit = item.get('unit') or item.get('Unit') or item.get('currency') or item.get('Currency') or 'USD'
            
            # فرمت کردن نام
            name = self.format_currency_name(item, symbol)
            
            self.all_currencies[symbol] = {
                'name': name,
                'price': str(price),
                'unit': str(unit),
                'change_percent': str(change),
                'symbol': symbol
            }
            
            return True
            
        except Exception as e:
            print(f"Error processing currency item: {e}")
            return False

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
            # استفاده از نام انگلیسی از API
            api_name = item.get('name_en', item.get('name', symbol))
            return f"💱 {api_name}" if api_name != symbol else symbol

    def get_sample_data(self):
        """داده‌های نمونه با کیفیت Liquid - Enhanced Display"""
        return {
            "USD": {"name": "🇺🇸 US Dollar", "price": "93750.25", "unit": "تومان", "change_percent": "1.04", "symbol": "USD"},
            "EUR": {"name": "🇪🇺 Euro", "price": "109330.78", "unit": "تومان", "change_percent": "-0.52", "symbol": "EUR"},
            "BTC": {"name": "₿ Bitcoin", "price": "114390.12345", "unit": "USD", "change_percent": "0.66", "symbol": "BTC"},
            "ETH": {"name": "Ξ Ethereum", "price": "4365.89721", "unit": "USD", "change_percent": "4.82", "symbol": "ETH"},
            "GBP": {"name": "🇬🇧 British Pound", "price": "126210.50", "unit": "تومان", "change_percent": "2.15", "symbol": "GBP"},
            "JPY": {"name": "🇯🇵 Japanese Yen", "price": "639.123", "unit": "تومان", "change_percent": "-0.83", "symbol": "JPY"}
        }

    def display_featured_currencies(self):
        """نمایش ارزهای ویژه با 3D Cards"""
        # انتخاب ارزهای پیش‌فرض یا اولین ارزهای موجود
        preferred_featured = ["USD", "EUR", "BTC", "ETH"]
        available_symbols = list(self.all_currencies.keys())
        
        featured = []
        for symbol in preferred_featured:
            if symbol in self.all_currencies:
                featured.append(symbol)
        
        # اگر کافی نداریم، از بقیه اضافه کن
        while len(featured) < 4 and len(featured) < len(available_symbols):
            for symbol in available_symbols:
                if symbol not in featured:
                    featured.append(symbol)
                    if len(featured) >= 4:
                        break

        for i, symbol in enumerate(featured[:4]):  # حداکثر 4 تا
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

    def manual_refresh(self):
        """رفرش دستی داده‌ها"""
        def refresh_thread():
            try:
                # به‌روزرسانی وضعیت
                self.after(0, lambda: self.update_api_status("connecting", "Refreshing..."))
                
                # دریافت داده‌های جدید
                api_data = self.fetch_api_data()
                
                if api_data:
                    # به‌روزرسانی داده‌ها
                    new_currencies = {}
                    for category, items in api_data.items():
                        if isinstance(items, list):
                            for item in items:
                                symbol = item.get('symbol', '')
                                if symbol:
                                    name = self.format_currency_name(item, symbol)
                                    new_currencies[symbol] = {
                                        'name': name,
                                        'price': str(item.get('price', 0)),
                                        'unit': item.get('unit', 'USD'),
                                        'change_percent': str(item.get('change_percent', 0)),
                                        'symbol': symbol
                                    }
                    
                    # به‌روزرسانی در UI thread
                    self.after(0, lambda: self.update_ui_with_new_data(new_currencies))
                    
                else:
                    self.after(0, lambda: messagebox.showwarning(
                        "⚠️ Refresh Warning",
                        "Could not fetch fresh data from API.\nDisplaying cached data."
                    ))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror(
                    "❌ Refresh Error", 
                    f"Failed to refresh data:\n{str(e)}"
                ))
        
        # اجرای رفرش در thread جداگانه
        threading.Thread(target=refresh_thread, daemon=True).start()

    def update_ui_with_new_data(self, new_currencies):
        """به‌روزرسانی UI با داده‌های جدید"""
        if new_currencies:
            self.all_currencies = new_currencies
            
            # به‌روزرسانی کارت‌های موجود
            self.refresh_existing_cards()
            
            # به‌روزرسانی انتخابگر
            self.update_currency_selector()
            
            # نمایش پیام موفقیت
            self.create_floating_notification("🔄 Data refreshed successfully!")
        else:
            messagebox.showwarning(
                "⚠️ No Data",
                "No valid data received from API."
            )

    def refresh_existing_cards(self):
        """به‌روزرسانی کارت‌های موجود با داده‌های جدید"""
        try:
            # بازسازی featured currencies
            for widget in self.featured_container.winfo_children():
                widget.destroy()
            
            # بازسازی dynamic currencies  
            for widget in self.dynamic_container.winfo_children():
                widget.destroy()
            
            # ریست کردن grid position
            self.dynamic_row = 0
            self.dynamic_col = 0
            
            # نمایش مجدد featured
            self.display_featured_currencies()
            
            # نمایش مجدد ارزهای اضافه شده
            remaining_selected = self.selected_currencies.copy()
            # حذف featured از selected تا دوبار نمایش داده نشوند
            preferred_featured = ["USD", "EUR", "BTC", "ETH"]
            for symbol in preferred_featured:
                remaining_selected.discard(symbol)
            
            for symbol in remaining_selected:
                if symbol in self.all_currencies:
                    card = self.create_3d_currency_card(
                        self.dynamic_container,
                        self.all_currencies[symbol]
                    )
                    card.grid(
                        row=self.dynamic_row,
                        column=self.dynamic_col,
                        padx=6, pady=6, sticky="nsew"
                    )
                    
                    self.dynamic_col += 1
                    if self.dynamic_col >= 4:
                        self.dynamic_col = 0
                        self.dynamic_row += 1
                        
        except Exception as e:
            print(f"Card refresh error: {e}")

    def start_auto_refresh(self):
        """شروع رفرش خودکار هر 5 دقیقه"""
        def auto_refresh_loop():
            while True:
                try:
                    import time
                    time.sleep(300)  # 5 minutes
                    self.after(0, self.auto_refresh_data)
                except Exception as e:
                    print(f"Auto-refresh error: {e}")
                    break
        
        # شروع thread برای auto refresh
        threading.Thread(target=auto_refresh_loop, daemon=True).start()

    def auto_refresh_data(self):
        """رفرش خودکار داده‌ها (بدون نمایش پیام)"""
        def refresh_thread():
            api_data = self.fetch_api_data()
            if api_data:
                new_currencies = {}
                for category, items in api_data.items():
                    if isinstance(items, list):
                        for item in items:
                            symbol = item.get('symbol', '')
                            if symbol:
                                name = self.format_currency_name(item, symbol)
                                new_currencies[symbol] = {
                                    'name': name,
                                    'price': str(item.get('price', 0)),
                                    'unit': item.get('unit', 'USD'),
                                    'change_percent': str(item.get('change_percent', 0)),
                                    'symbol': symbol
                                }
                
                self.after(0, lambda: self.silent_update_ui(new_currencies))
        
        threading.Thread(target=refresh_thread, daemon=True).start()

    def silent_update_ui(self, new_currencies):
        """به‌روزرسانی بی‌صدا UI"""
        if new_currencies:
            self.all_currencies = new_currencies
            self.refresh_existing_cards()
            self.update_currency_selector()
            print("🔄 Auto-refresh completed successfully")

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


def check_liquid_requirements():
    """بررسی نیازمندی‌های Liquid Glass"""
    print("🌊" + "=" * 80 + "🌊")
    print("   LIQUID GLASS PRICE TRACKER - LIVE API VERSION")
    print("🌊" + "=" * 80 + "🌊")

    print(f"\n💻 Operating System: {sys.platform}")
    print(f"🔗 API Endpoint: {API_URL}")
    print(f"📱 App Resolution: {APP_WIDTH}x{APP_HEIGHT}")

    # بررسی اتصال اینترنت
    try:
        response = requests.get("https://httpbin.org/status/200", timeout=5)
        print("✅ Internet connection: Available")
    except:
        print("❌ Internet connection: Limited or unavailable")
        print("   💡 App will use sample data if API fails")

    if IS_WINDOWS:
        print("✅ Windows detected - Full Liquid Glass effects available")

        if PYWINSTYLES_AVAILABLE:
            print("🌊 PyWinStyles available - Premium Liquid experience enabled")
            try:
                import pywinstyles
                print(f"📦 PyWinStyles version: {getattr(pywinstyles, '__version__', 'Unknown')}")
            except Exception as e:
                print(f"⚠️ PyWinStyles test failed: {e}")
        else:
            print("❌ PyWinStyles not installed")
            print("   💡 Install command: pip install pywinstyles")
            print("   🎨 Will use Liquid Glass simulation mode")
    else:
        print("🎏 Non-Windows system detected")
        print("💡 Using high-quality Liquid Glass simulation")

    print("\n🌊 LIVE API FEATURES:" + " " * 35)
    print("   • Real-time data from BRS API")
    print("   • Auto-refresh every 5 minutes")
    print("   • Manual refresh control")
    print("   • Connection status indicator")
    print("   • Fallback to sample data if API fails")
    print("   • Thread-safe data updates")

    print("\n🚀 Launching Live Liquid Glass experience...")
    print("🌊" + "=" * 80 + "🌊\n")


if __name__ == "__main__":
    # بررسی سیستم و نیازمندی‌ها
    check_liquid_requirements()

    # تنظیمات CustomTkinter با بهینه‌سازی Liquid
    ctk.set_appearance_mode("system")  # تشخیص خودکار حالت سیستم
    ctk.set_default_color_theme("blue")  # تم پایه آبی Apple

    # اجرای برنامه Live Liquid Glass
    try:
        print("🌊 Initializing Live Liquid Glass interface...")
        app = LiquidGlassPriceTracker()

        print("🎉 Live Liquid Glass Price Tracker launched successfully!")
        print("🔄 Auto-refresh enabled - data updates every 5 minutes")
        print("💡 Use refresh controls for manual updates")

        app.mainloop()

    except Exception as e:
        print(f"\n💥 Liquid Glass launch failed: {e}")
        print("🔧 Troubleshooting tips:")
        print("   • Check internet connection")
        print("   • Verify API endpoint accessibility") 
        print("   • Check PyWinStyles installation: pip install --upgrade pywinstyles")
        print("   • Try running as administrator")

        import traceback
        traceback.print_exc()
