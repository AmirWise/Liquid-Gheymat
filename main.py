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
import time
from typing import Dict, List, Optional, Tuple
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Operating System Detection and Effects ---
IS_WINDOWS = sys.platform == "win32"
if IS_WINDOWS:
    try:
        import pywinstyles
        PYWINSTYLES_AVAILABLE = True
        logger.info("✅ pywinstyles imported successfully")
    except ImportError:
        PYWINSTYLES_AVAILABLE = False
        logger.warning("❌ pywinstyles not available - install with: pip install pywinstyles")

class ResourceManager:
    """Handles resource paths and font loading"""
    
    @staticmethod
    def resource_path(relative_path: str) -> str:
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)

    @staticmethod
    def load_font(font_path: str) -> None:
        try:
            pyglet.font.add_file(font_path)
            logger.info(f"✅ Font loaded: {font_path}")
        except Exception as e:
            logger.error(f"Failed to load font: {e}")

class AppConfig:
    """Application configuration constants"""
    
    # Fonts
    FONT_NAME = "SF Pro Display"
    FALLBACK_FONT = "Segoe UI"
    FONT_PATH = ResourceManager.resource_path("assets/fonts/Vazirmatn-Regular.ttf")
    ICON_PATH = ResourceManager.resource_path("assets/icons/icon.ico")
    
    # API Configuration
    API_URL = "https://brsapi.ir/Api/Market/Gold_Currency.php?key=BWUuKdavyBLGXxidEjfNJeb33rsryQfh"
    API_TIMEOUT = 15
    AUTO_REFRESH_INTERVAL = 300  # 5 minutes
    
    # UI Dimensions
    APP_WIDTH, APP_HEIGHT = 1200, 850
    MIN_WIDTH, MIN_HEIGHT = 1000, 750
    CARD_WIDTH = 240
    CARD_HEIGHT = 145
    GRID_COLUMNS = 4

class ColorScheme:
    """Liquid Glass color scheme with transparency and depth"""
    
    # Background colors
    BG_LIGHT = "#f8f9fb"
    BG_DARK = "#0a0a0c"
    
    # Glass effect colors
    GLASS_LIGHT = "#ffffff"
    GLASS_DARK = "#1a1a1e"
    GLASS_OVERLAY_LIGHT = "#fdfdfe"
    GLASS_OVERLAY_DARK = "#151518"
    
    # Shadow and highlight for 3D effect
    SHADOW_LIGHT = "#e8eaed"
    SHADOW_DARK = "#050507"
    HIGHLIGHT_LIGHT = "#ffffff"
    HIGHLIGHT_DARK = "#2a2a2f"
    
    # Accent colors
    ACCENT = "#0066ff"
    ACCENT_HOVER = "#0052cc"
    ACCENT_GLASS = "#4da6ff"
    GREEN_GLASS = "#32d74b"
    RED_GLASS = "#ff453a"
    ORANGE_GLASS = "#ff9f0a"
    PURPLE_GLASS = "#bf5af2"
    
    # Text colors
    TEXT_PRIMARY_LIGHT = "#1d1d1f"
    TEXT_PRIMARY_DARK = "#f5f5f7"
    TEXT_SECONDARY_LIGHT = "#515154"
    TEXT_SECONDARY_DARK = "#a1a1a6"
    TEXT_TERTIARY_LIGHT = "#8e8e93"
    TEXT_TERTIARY_DARK = "#636366"
    
    # Border colors
    BORDER_LIGHT = "#f0f0f3"
    BORDER_DARK = "#2c2c2e"
    SEPARATOR_LIGHT = "#f2f2f7"
    SEPARATOR_DARK = "#1c1c1e"

class APIManager:
    """Handles API communication and data processing"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'fa-IR,fa;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache'
        })
    
    def fetch_data(self) -> Optional[Dict]:
        """Fetch data from API with comprehensive error handling"""
        try:
            logger.info(f"Fetching data from API: {AppConfig.API_URL}")
            
            response = self.session.get(
                AppConfig.API_URL,
                timeout=AppConfig.API_TIMEOUT,
                verify=True,
                allow_redirects=True
            )
            
            response.raise_for_status()
            
            # Validate content type
            content_type = response.headers.get('content-type', '')
            if 'json' not in content_type.lower():
                logger.warning(f"Unexpected content type: {content_type}")
            
            data = response.json()
            
            if not data:
                raise ValueError("Empty response from API")
            
            logger.info(f"Successfully fetched data: {type(data)} with {len(data) if hasattr(data, '__len__') else 0} items")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            return None
        except ValueError as e:
            logger.error(f"Data parsing error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected API error: {e}")
            return None
    
    def process_currency_data(self, api_data: Dict) -> Dict[str, Dict]:
        """Process raw API data into standardized currency format"""
        currencies = {}
        processed_count = 0
        
        try:
            if isinstance(api_data, dict):
                for category, items in api_data.items():
                    if isinstance(items, list):
                        for item in items:
                            currency = self._process_currency_item(item)
                            if currency:
                                currencies[currency['symbol']] = currency
                                processed_count += 1
                    elif isinstance(items, dict) and items.get('symbol'):
                        currency = self._process_currency_item(items)
                        if currency:
                            currencies[currency['symbol']] = currency
                            processed_count += 1
            
            elif isinstance(api_data, list):
                for item in api_data:
                    currency = self._process_currency_item(item)
                    if currency:
                        currencies[currency['symbol']] = currency
                        processed_count += 1
            
            logger.info(f"Processed {processed_count} currencies")
            return currencies
            
        except Exception as e:
            logger.error(f"Currency processing error: {e}")
            return {}
    
    def _process_currency_item(self, item: Dict) -> Optional[Dict]:
        """Process a single currency item"""
        try:
            if not isinstance(item, dict):
                return None
            
            # Extract symbol with fallbacks
            symbol = (item.get('symbol') or item.get('Symbol') or 
                     item.get('code') or item.get('Code'))
            
            if not symbol:
                return None
            
            # Extract other fields with defaults
            price = item.get('price', item.get('Price', item.get('value', 0)))
            change = item.get('change_percent', item.get('Change_Percent', item.get('change', 0)))
            unit = item.get('unit', item.get('Unit', item.get('currency', 'USD')))
            name = self._format_currency_name(item, symbol)
            
            return {
                'name': name,
                'price': str(price),
                'unit': str(unit),
                'change_percent': str(change),
                'symbol': symbol
            }
            
        except Exception as e:
            logger.error(f"Error processing currency item: {e}")
            return None
    
    def _format_currency_name(self, item: Dict, symbol: str) -> str:
        """Format currency name with appropriate emoji"""
        name_mapping = {
            'USD': "US Dollar",
            'EUR': "Euro",
            'GBP': "British Pound",
            'JPY': "Japanese Yen",
            'BTC': "Bitcoin",
            'ETH': "Ethereum",
            'USDT': "Tether",
            'XRP': "Ripple",
            'ADA': "Cardano",
            'DOT': "Polkadot",
            'BNB': "Binance Coin",
            'SOL': "Solana",
            'MATIC': "Polygon",
            'AVAX': "Avalanche"
        }
        
        if symbol in name_mapping:
            return name_mapping[symbol]
        
        api_name = item.get('name_en', item.get('name', symbol))
        return api_name if api_name != symbol else symbol
    
    @staticmethod
    def get_sample_data() -> Dict[str, Dict]:
        """Generate sample data for fallback"""
        return {
            "USD": {"name": "US Dollar", "price": "93750.25", "unit": "Toman", "change_percent": "1.04", "symbol": "USD"},
            "EUR": {"name": "Euro", "price": "109330.78", "unit": "Toman", "change_percent": "-0.52", "symbol": "EUR"},
            "BTC": {"name": "Bitcoin", "price": "114390.12", "unit": "USD", "change_percent": "0.66", "symbol": "BTC"},
            "ETH": {"name": "Ethereum", "price": "4365.89", "unit": "USD", "change_percent": "4.82", "symbol": "ETH"},
            "GBP": {"name": "British Pound", "price": "126210.50", "unit": "Toman", "change_percent": "2.15", "symbol": "GBP"},
            "JPY": {"name": "Japanese Yen", "price": "639.12", "unit": "Toman", "change_percent": "-0.83", "symbol": "JPY"}
        }

class WindowEffectsManager:
    """Manages window transparency and visual effects"""
    
    def __init__(self, window):
        self.window = window
        self.current_theme = "liquid_glass"
    
    def test_transparency_support(self) -> bool:
        """Test if system supports transparency effects"""
        if not IS_WINDOWS or not PYWINSTYLES_AVAILABLE:
            return False
        
        try:
            current_alpha = self.window.attributes('-alpha')
            self.window.attributes('-alpha', 0.99)
            self.window.update()
            self.window.attributes('-alpha', current_alpha)
            return True
        except Exception:
            try:
                self.window.attributes('-alpha', 1.0)
            except:
                pass
            return False
    
    def apply_liquid_glass(self) -> None:
        """Apply liquid glass effect with fallback protection"""
        if not IS_WINDOWS or not PYWINSTYLES_AVAILABLE:
            logger.info("Liquid Glass simulation applied")
            return
        
        try:
            pywinstyles.apply_style(self.window, "normal")
            self.window.after(50, self._apply_effect_with_fallback)
        except Exception as e:
            logger.error(f"Liquid Glass failed: {e}")
    
    def _apply_effect_with_fallback(self) -> None:
        """Apply effects with multiple fallback methods"""
        effects = [
            ("acrylic", 0.97),
            ("mica", 0.98),
            ("blur", 0.95)
        ]
        
        for effect, alpha in effects:
            try:
                pywinstyles.apply_style(self.window, effect)
                if self.test_transparency_support():
                    self.window.attributes('-alpha', alpha)
                logger.info(f"Liquid Glass activated ({effect})")
                self.current_theme = "liquid_glass"
                return
            except Exception as e:
                logger.warning(f"{effect} method failed: {e}")
                try:
                    self.window.attributes('-alpha', 1.0)
                except:
                    pass
        
        logger.info("Using Liquid Glass simulation")
        self.current_theme = "liquid_glass"
    
    def apply_vibrancy(self) -> None:
        """Apply enhanced vibrancy effect"""
        if not IS_WINDOWS or not PYWINSTYLES_AVAILABLE:
            return
        
        try:
            pywinstyles.apply_style(self.window, "aero")
            if self.test_transparency_support():
                self.window.attributes('-alpha', 0.92)
            logger.info("Enhanced Vibrancy activated")
            self.current_theme = "vibrancy"
        except Exception as e:
            logger.error(f"Vibrancy failed: {e}")
            self.apply_liquid_glass()
    
    def apply_crystal_mode(self) -> None:
        """Apply crystal mode effect"""
        if not IS_WINDOWS or not PYWINSTYLES_AVAILABLE:
            return
        
        try:
            pywinstyles.apply_style(self.window, "optimised")
            if self.test_transparency_support():
                self.window.attributes('-alpha', 0.89)
            logger.info("Crystal Mode activated")
            self.current_theme = "crystal"
        except Exception as e:
            logger.error(f"Crystal mode failed: {e}")
            self.apply_liquid_glass()

class LiquidGlassPriceTracker(ctk.CTk):
    """Main application class with optimized liquid glass interface"""
    
    def __init__(self):
        super().__init__()
        
        # Initialize core components
        self.api_manager = APIManager()
        self.effects_manager = WindowEffectsManager(self)
        
        # Application state
        self.all_currencies: Dict[str, Dict] = {}
        self.selected_currencies: set = set()
        self.api_status = "connecting"
        self.last_update = "Never"
        self.auto_refresh_thread = None
        self.grid_position = {"row": 0, "col": 0}
        
        self._setup_window()
        self._apply_initial_effects()
        self._create_interface()
        self._load_initial_data()
        self._start_auto_refresh()
    
    def _setup_window(self) -> None:
        """Configure main window properties"""
        self.title("Liquid Gheymat - Premium Exchange Rates")
        self.geometry(f"{AppConfig.APP_WIDTH}x{AppConfig.APP_HEIGHT}")
        self.minsize(AppConfig.MIN_WIDTH, AppConfig.MIN_HEIGHT)
        self.resizable(True, True)
        
        # Set icon if available
        try:
            self.iconbitmap(AppConfig.ICON_PATH)
        except:
            logger.warning("Icon not found")
        
        # Configure colors
        self.configure(fg_color=(ColorScheme.BG_LIGHT, ColorScheme.BG_DARK))
        
        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
    
    def _apply_initial_effects(self) -> None:
        """Apply initial visual effects"""
        self.effects_manager.apply_liquid_glass()
    
    def _create_interface(self) -> None:
        """Create the main user interface"""
        # Main container
        self.main_container = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.main_container.pack(fill="both", expand=True, padx=16, pady=16)
        self.main_container.grid_columnconfigure(0, weight=1)
        
        # Scrollable content area
        self.main_scroll = ctk.CTkScrollableFrame(
            self.main_container,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=(ColorScheme.BORDER_LIGHT, ColorScheme.BORDER_DARK),
            scrollbar_button_hover_color=(ColorScheme.ACCENT_GLASS, ColorScheme.ACCENT_GLASS)
        )
        self.main_scroll.pack(fill="both", expand=True, padx=4, pady=4)
        self.main_scroll.grid_columnconfigure(0, weight=1)
        
        # Create interface sections
        self._create_hero_section()
        self._create_featured_section()
        self._create_currency_selector()
        self._create_dynamic_section()
        if IS_WINDOWS and PYWINSTYLES_AVAILABLE:
            self._create_effects_controls()
        self._create_refresh_controls()
    
    def _create_hero_section(self) -> None:
        """Create hero header section"""
        hero_frame = self._create_glass_card(self.main_scroll, height=160, glass_level=3)
        hero_frame.grid(row=0, column=0, sticky="ew", pady=(0, 24))
        
        content = ctk.CTkFrame(hero_frame, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=20)
        
        # Title
        title = ctk.CTkLabel(
            content,
            text="Liquid Gheymat Live!",
            font=(AppConfig.FALLBACK_FONT, 36, "bold"),
            text_color=(ColorScheme.TEXT_PRIMARY_LIGHT, ColorScheme.TEXT_PRIMARY_DARK)
        )
        title.pack(anchor="w")
        
        # Subtitle
        subtitle = ctk.CTkLabel(
            content,
            text="Real-time currency tracking with Live API updates",
            font=(AppConfig.FALLBACK_FONT, 16),
            text_color=(ColorScheme.TEXT_SECONDARY_LIGHT, ColorScheme.TEXT_SECONDARY_DARK)
        )
        subtitle.pack(anchor="w", pady=(8, 0))
        
        # Status indicator
        self._create_status_indicator(content)
    
    def _create_status_indicator(self, parent) -> None:
        """Create API status indicator"""
        status_container = ctk.CTkFrame(parent, fg_color="transparent")
        status_container.pack(anchor="w", pady=(16, 0))
        
        self.status_pill = ctk.CTkFrame(
            status_container,
            fg_color=(ColorScheme.GLASS_OVERLAY_LIGHT, ColorScheme.GLASS_OVERLAY_DARK),
            corner_radius=20,
            height=36,
            border_width=0.5,
            border_color=(ColorScheme.BORDER_LIGHT, ColorScheme.BORDER_DARK)
        )
        self.status_pill.pack(anchor="w")
        
        pill_content = ctk.CTkFrame(self.status_pill, fg_color="transparent")
        pill_content.pack(fill="both", expand=True, padx=16, pady=8)
        
        self.status_dot = ctk.CTkLabel(
            pill_content,
            text="●",
            font=(AppConfig.FALLBACK_FONT, 14),
            text_color=ColorScheme.ORANGE_GLASS
        )
        self.status_dot.pack(side="left")
        
        self.status_text = ctk.CTkLabel(
            pill_content,
            text="Connecting to Live API...",
            font=(AppConfig.FALLBACK_FONT, 13, "normal"),
            text_color=(ColorScheme.TEXT_PRIMARY_LIGHT, ColorScheme.TEXT_PRIMARY_DARK)
        )
        self.status_text.pack(side="left", padx=(8, 0))
    
    def _create_featured_section(self) -> None:
        """Create featured currencies section"""
        section_title = ctk.CTkLabel(
            self.main_scroll,
            text="Featured Currencies",
            font=(AppConfig.FALLBACK_FONT, 20, "bold"),
            text_color=(ColorScheme.TEXT_PRIMARY_LIGHT, ColorScheme.TEXT_PRIMARY_DARK)
        )
        section_title.grid(row=1, column=0, sticky="w", pady=(0, 12))
        
        self.featured_container = ctk.CTkFrame(self.main_scroll, fg_color="transparent")
        self.featured_container.grid(row=2, column=0, sticky="ew", pady=(0, 32))
        
        # Configure responsive grid
        for i in range(AppConfig.GRID_COLUMNS):
            self.featured_container.grid_columnconfigure(i, weight=1)
    
    def _create_currency_selector(self) -> None:
        """Create currency selection interface"""
        selector_card = self._create_glass_card(self.main_scroll, height=100, glass_level=2)
        selector_card.grid(row=3, column=0, sticky="ew", pady=(0, 24))
        
        content = ctk.CTkFrame(selector_card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=16)
        content.grid_columnconfigure(1, weight=1)
        
        # Header
        self._create_selector_header(content)
        
        # Controls
        self.currency_selector = ctk.CTkComboBox(
            content,
            font=(AppConfig.FALLBACK_FONT, 14),
            values=["-"],
            state="readonly",
            height=40,
            corner_radius=10,
            border_width=0.5,
            fg_color=(ColorScheme.GLASS_LIGHT, ColorScheme.GLASS_DARK),
            border_color=(ColorScheme.BORDER_LIGHT, ColorScheme.BORDER_DARK),
            button_color=(ColorScheme.ACCENT, ColorScheme.ACCENT),
            button_hover_color=(ColorScheme.ACCENT_HOVER, ColorScheme.ACCENT_HOVER),
            dropdown_fg_color=(ColorScheme.GLASS_LIGHT, ColorScheme.GLASS_DARK),
            text_color=(ColorScheme.TEXT_PRIMARY_LIGHT, ColorScheme.TEXT_PRIMARY_DARK)
        )
        self.currency_selector.grid(row=1, column=0, columnspan=2, sticky="ew", padx=(0, 12))
        
        add_btn = self._create_liquid_button(
            content, text="Add", command=self._add_selected_currency,
            style="primary", width=70
        )
        add_btn.grid(row=1, column=2)
    
    def _create_selector_header(self, parent) -> None:
        """Create header for currency selector"""
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 12))
        
        icon_frame = ctk.CTkFrame(
            header,
            fg_color=(ColorScheme.ACCENT, ColorScheme.ACCENT),
            corner_radius=12,
            width=24,
            height=24
        )
        icon_frame.pack(side="left")
        
        icon = ctk.CTkLabel(icon_frame, text="+", font=(AppConfig.FALLBACK_FONT, 14), text_color="white")
        icon.place(relx=0.5, rely=0.5, anchor="center")
        
        title = ctk.CTkLabel(
            header,
            text="Add New Currency",
            font=(AppConfig.FALLBACK_FONT, 16, "normal"),
            text_color=(ColorScheme.TEXT_PRIMARY_LIGHT, ColorScheme.TEXT_PRIMARY_DARK)
        )
        title.pack(side="left", padx=(12, 0))
    
    def _create_dynamic_section(self) -> None:
        """Create dynamic currencies section"""
        self.dynamic_title = ctk.CTkLabel(
            self.main_scroll,
            text="Your Portfolio",
            font=(AppConfig.FALLBACK_FONT, 20, "bold"),
            text_color=(ColorScheme.TEXT_PRIMARY_LIGHT, ColorScheme.TEXT_PRIMARY_DARK)
        )
        self.dynamic_title.grid(row=4, column=0, sticky="w", pady=(0, 12))
        
        self.dynamic_container = ctk.CTkFrame(self.main_scroll, fg_color="transparent")
        self.dynamic_container.grid(row=5, column=0, sticky="ew")
        
        # Configure responsive grid
        for i in range(AppConfig.GRID_COLUMNS):
            self.dynamic_container.grid_columnconfigure(i, weight=1)
    
    def _create_effects_controls(self) -> None:
        """Create visual effects control panel"""
        control_card = self._create_glass_card(self.main_scroll, height=90, glass_level=2)
        control_card.grid(row=6, column=0, sticky="ew", pady=(32, 0))
        
        content = ctk.CTkFrame(control_card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=16)
        
        title = ctk.CTkLabel(
            content,
            text="Liquid Appearance",
            font=(AppConfig.FALLBACK_FONT, 16, "normal"),
            text_color=(ColorScheme.TEXT_PRIMARY_LIGHT, ColorScheme.TEXT_PRIMARY_DARK)
        )
        title.pack(anchor="w", pady=(0, 8))
        
        buttons_frame = ctk.CTkFrame(content, fg_color="transparent")
        buttons_frame.pack(anchor="w")
        
        buttons = [
            ("Liquid Glass", self.effects_manager.apply_liquid_glass),
            ("Enhanced Vibrancy", self.effects_manager.apply_vibrancy),
            ("Crystal Mode", self.effects_manager.apply_crystal_mode)
        ]
        
        for i, (text, command) in enumerate(buttons):
            btn = self._create_liquid_button(
                buttons_frame, text=text, command=command,
                style="secondary", width=130
            )
            btn.pack(side="left", padx=(0, 8) if i < len(buttons) - 1 else (0, 0))
    
    def _create_refresh_controls(self) -> None:
        """Create data refresh controls"""
        refresh_card = self._create_glass_card(self.main_scroll, height=120, glass_level=2)
        refresh_card.grid(row=7, column=0, sticky="ew", pady=(16, 0))
        
        content = ctk.CTkFrame(refresh_card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=16)
        
        title = ctk.CTkLabel(
            content,
            text="Live Data Controls",
            font=(AppConfig.FALLBACK_FONT, 16, "normal"),
            text_color=(ColorScheme.TEXT_PRIMARY_LIGHT, ColorScheme.TEXT_PRIMARY_DARK)
        )
        title.pack(anchor="w", pady=(0, 8))
        
        controls_frame = ctk.CTkFrame(content, fg_color="transparent")
        controls_frame.pack(anchor="w", pady=(0, 8))
        
        # Refresh button
        refresh_btn = self._create_liquid_button(
            controls_frame, text="Refresh Now", command=self._manual_refresh,
            style="primary", width=120
        )
        refresh_btn.pack(side="left", padx=(0, 12))
        
        # Test API button
        test_btn = self._create_liquid_button(
            controls_frame, text="Test API", command=self._test_api,
            style="secondary", width=100
        )
        test_btn.pack(side="left", padx=(0, 12))
        
        # Last update label
        self.last_update_label = ctk.CTkLabel(
            controls_frame,
            text=f"Last Update: {self.last_update}",
            font=(AppConfig.FALLBACK_FONT, 12),
            text_color=(ColorScheme.TEXT_SECONDARY_LIGHT, ColorScheme.TEXT_SECONDARY_DARK)
        )
        self.last_update_label.pack(side="left")
    
    def _create_glass_card(self, parent, height: Optional[int] = None, glass_level: int = 1, **kwargs) -> ctk.CTkFrame:
        """Create a liquid glass card with specified transparency level"""
        glass_colors = [
            (ColorScheme.GLASS_LIGHT, ColorScheme.GLASS_DARK),
            (ColorScheme.GLASS_OVERLAY_LIGHT, ColorScheme.GLASS_OVERLAY_DARK),
            (ColorScheme.HIGHLIGHT_LIGHT, ColorScheme.HIGHLIGHT_DARK)
        ]
        
        fg_color = glass_colors[min(glass_level - 1, 2)]
        
        default_kwargs = {
            'fg_color': fg_color,
            'corner_radius': 12,
            'border_width': 0.5,
            'border_color': (ColorScheme.BORDER_LIGHT, ColorScheme.BORDER_DARK)
        }
        
        if height:
            default_kwargs['height'] = height
            
        default_kwargs.update(kwargs)
        return ctk.CTkFrame(parent, **default_kwargs)
    
    def _create_liquid_button(self, parent, text: str, command, style: str = "primary", width: Optional[int] = None, **kwargs) -> ctk.CTkButton:
        """Create liquid button with specified style"""
        styles = {
            'primary': {
                'fg_color': (ColorScheme.ACCENT, ColorScheme.ACCENT),
                'hover_color': (ColorScheme.ACCENT_HOVER, ColorScheme.ACCENT_HOVER),
                'text_color': 'white',
                'border_width': 0
            },
            'secondary': {
                'fg_color': (ColorScheme.GLASS_OVERLAY_LIGHT, ColorScheme.GLASS_OVERLAY_DARK),
                'hover_color': (ColorScheme.SEPARATOR_LIGHT, ColorScheme.SEPARATOR_DARK),
                'text_color': (ColorScheme.TEXT_PRIMARY_LIGHT, ColorScheme.TEXT_PRIMARY_DARK),
                'border_width': 0.5,
                'border_color': (ColorScheme.BORDER_LIGHT, ColorScheme.BORDER_DARK)
            }
        }
        
        config = styles.get(style, styles['primary'])
        config.update(kwargs)
        
        default_config = {
            'text': text,
            'command': command,
            'font': (AppConfig.FALLBACK_FONT, 13, "normal"),
            'corner_radius': 8,
            'height': 40
        }
        
        if width:
            default_config['width'] = width
        
        default_config.update(config)
        return ctk.CTkButton(parent, **default_config)
    
    def _create_currency_card(self, parent, currency_data: Dict) -> ctk.CTkFrame:
        """Create currency display card with optimized layout"""
        card = self._create_glass_card(parent, width=AppConfig.CARD_WIDTH, height=AppConfig.CARD_HEIGHT, glass_level=2)
        
        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=16, pady=16)
        
        # Header section
        header = ctk.CTkFrame(content, fg_color="transparent", height=38)
        header.pack(fill="x", pady=(0, 10))
        header.pack_propagate(False)
        
        # Currency name
        name_text = currency_data.get('name', 'Currency')
        if len(name_text) > 22:
            name_text = name_text[:19] + "..."
        
        name = ctk.CTkLabel(
            header,
            text=name_text,
            font=(AppConfig.FALLBACK_FONT, 14, "bold"),
            text_color=(ColorScheme.TEXT_PRIMARY_LIGHT, ColorScheme.TEXT_PRIMARY_DARK),
            anchor="w"
        )
        name.pack(fill="x", pady=(0, 2))
        
        # Symbol
        symbol_text = currency_data.get('symbol', '')
        symbol = ctk.CTkLabel(
            header,
            text=f"({symbol_text})" if symbol_text else "",
            font=(AppConfig.FALLBACK_FONT, 12, "normal"),
            text_color=(ColorScheme.TEXT_SECONDARY_LIGHT, ColorScheme.TEXT_SECONDARY_DARK),
            anchor="w"
        )
        symbol.pack(fill="x")
        
        # Price section
        price_container = ctk.CTkFrame(content, fg_color="transparent", height=48)
        price_container.pack(fill="x", pady=(0, 10))
        price_container.pack_propagate(False)
        
        # Format price
        price = currency_data.get('price', '0')
        try:
            price_float = float(price)
            if price_float >= 100000:
                price_text = f"{price_float:,.0f}"
            elif price_float >= 1000:
                price_text = f"{price_float:,.2f}"
            elif price_float >= 1:
                price_text = f"{price_float:,.4f}"
            else:
                price_text = f"{price_float:.5f}"
            
            # Remove trailing zeros
            if '.' in price_text:
                price_text = price_text.rstrip('0').rstrip('.')
                
        except ValueError:
            price_text = str(price)
        
        # Truncate if too long
        if len(price_text) > 15:
            price_text = price_text[:12] + "..."
        
        price_label = ctk.CTkLabel(
            price_container,
            text=price_text,
            font=(AppConfig.FALLBACK_FONT, 18, "bold"),
            text_color=(ColorScheme.TEXT_PRIMARY_LIGHT, ColorScheme.TEXT_PRIMARY_DARK),
            anchor="w"
        )
        price_label.pack(fill="x", pady=(0, 2))
        
        # Unit
        unit_text = currency_data.get('unit', '')
        unit = ctk.CTkLabel(
            price_container,
            text=unit_text,
            font=(AppConfig.FALLBACK_FONT, 11, "normal"),
            text_color=(ColorScheme.TEXT_TERTIARY_LIGHT, ColorScheme.TEXT_TERTIARY_DARK),
            anchor="w"
        )
        unit.pack(fill="x")
        
        # Change indicator
        change_percent = currency_data.get('change_percent', 0)
        try:
            change_val = float(change_percent)
            if change_val >= 0:
                color = ColorScheme.GREEN_GLASS
                text = f"↗ +{change_val:.2f}%"
            else:
                color = ColorScheme.RED_GLASS
                text = f"↘ {change_val:.2f}%"
        except ValueError:
            color = ColorScheme.TEXT_SECONDARY_LIGHT
            text = "– N/A"
        
        change_pill = ctk.CTkFrame(content, fg_color=color, corner_radius=10, height=26)
        change_pill.pack(fill="x")
        
        change_label = ctk.CTkLabel(
            change_pill,
            text=text,
            font=(AppConfig.FALLBACK_FONT, 11, "normal"),
            text_color="white"
        )
        change_label.place(relx=0.5, rely=0.5, anchor="center")
        
        return card
    
    def _load_initial_data(self) -> None:
        """Load initial data from API or fallback"""
        def load_thread():
            # Fetch from API
            api_data = self.api_manager.fetch_data()
            
            if api_data:
                currencies = self.api_manager.process_currency_data(api_data)
                if currencies:
                    self.after(0, lambda: self._update_currencies(currencies, "connected"))
                else:
                    self.after(0, lambda: self._use_fallback_data("error"))
            else:
                self.after(0, lambda: self._use_fallback_data("error"))
        
        threading.Thread(target=load_thread, daemon=True).start()
    
    def _use_fallback_data(self, status: str) -> None:
        """Use fallback sample data"""
        sample_data = self.api_manager.get_sample_data()
        self._update_currencies(sample_data, status)
        logger.info("Using sample data due to API unavailability")
    
    def _update_currencies(self, currencies: Dict[str, Dict], status: str) -> None:
        """Update currency data and UI"""
        self.all_currencies = currencies
        self.last_update = datetime.now().strftime("%H:%M:%S")
        
        # Update status
        self._update_api_status(status)
        
        # Display currencies
        self._display_featured_currencies()
        self._update_currency_selector()
    
    def _update_api_status(self, status: str, message: str = None) -> None:
        """Update API status indicator"""
        self.api_status = status
        
        if status == "connected":
            color = ColorScheme.GREEN_GLASS
            message = message or f"Live Data Connected - {len(self.all_currencies)} currencies"
        elif status == "connecting":
            color = ColorScheme.ORANGE_GLASS
            message = message or "Connecting to Live API..."
        else:  # error
            color = ColorScheme.RED_GLASS
            message = message or "Connection Failed - Using Sample Data"
        
        try:
            self.status_dot.configure(text_color=color)
            self.status_text.configure(text=message)
            if hasattr(self, 'last_update_label'):
                self.last_update_label.configure(text=f"Last Update: {self.last_update}")
        except Exception as e:
            logger.error(f"Status update error: {e}")
    
    def _display_featured_currencies(self) -> None:
        """Display featured currencies in grid"""
        # Clear existing
        for widget in self.featured_container.winfo_children():
            widget.destroy()
        
        # Select featured currencies
        preferred_featured = ["USD", "EUR", "BTC", "ETH"]
        available_symbols = list(self.all_currencies.keys())
        
        featured = []
        for symbol in preferred_featured:
            if symbol in self.all_currencies:
                featured.append(symbol)
        
        # Add more if needed
        while len(featured) < 4 and len(featured) < len(available_symbols):
            for symbol in available_symbols:
                if symbol not in featured:
                    featured.append(symbol)
                    if len(featured) >= 4:
                        break
        
        # Create cards
        for i, symbol in enumerate(featured[:4]):
            if symbol in self.all_currencies:
                card = self._create_currency_card(self.featured_container, self.all_currencies[symbol])
                card.grid(row=0, column=i, padx=6, pady=6, sticky="nsew")
                self.selected_currencies.add(symbol)
    
    def _update_currency_selector(self) -> None:
        """Update currency selector options"""
        available = [
            data['name'] for symbol, data in self.all_currencies.items()
            if symbol not in self.selected_currencies
        ]
        
        if not available:
            available = ["All currencies added!"]
        
        self.currency_selector.configure(values=sorted(available))
        if available and available[0] != "All currencies added!":
            self.currency_selector.set(available[0])
    
    def _add_selected_currency(self) -> None:
        """Add selected currency to portfolio"""
        selected_name = self.currency_selector.get()
        
        if selected_name == "All currencies added!":
            messagebox.showinfo("Portfolio Complete", "You've added all available currencies!")
            return
        
        # Find corresponding symbol
        selected_symbol = None
        for symbol, data in self.all_currencies.items():
            if data['name'] == selected_name:
                selected_symbol = symbol
                break
        
        if selected_symbol and selected_symbol not in self.selected_currencies:
            # Create and place card
            card = self._create_currency_card(self.dynamic_container, self.all_currencies[selected_symbol])
            card.grid(
                row=self.grid_position["row"],
                column=self.grid_position["col"],
                padx=6, pady=6, sticky="nsew"
            )
            
            # Update grid position
            self.grid_position["col"] += 1
            if self.grid_position["col"] >= AppConfig.GRID_COLUMNS:
                self.grid_position["col"] = 0
                self.grid_position["row"] += 1
            
            # Update selections
            self.selected_currencies.add(selected_symbol)
            self._update_currency_selector()
            
            messagebox.showinfo("Success", f"{selected_name} added to your portfolio!")
    
    def _manual_refresh(self) -> None:
        """Manually refresh data"""
        def refresh_thread():
            try:
                self.after(0, lambda: self._update_api_status("connecting", "Refreshing..."))
                
                api_data = self.api_manager.fetch_data()
                
                if api_data:
                    currencies = self.api_manager.process_currency_data(api_data)
                    if currencies:
                        self.after(0, lambda: self._refresh_ui_with_data(currencies))
                    else:
                        self.after(0, lambda: messagebox.showwarning(
                            "Refresh Warning", "Could not parse fresh data from API."
                        ))
                else:
                    self.after(0, lambda: messagebox.showwarning(
                        "Refresh Warning", "Could not fetch fresh data from API."
                    ))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror(
                    "Refresh Error", f"Failed to refresh data: {str(e)}"
                ))
        
        threading.Thread(target=refresh_thread, daemon=True).start()
    
    def _refresh_ui_with_data(self, new_currencies: Dict[str, Dict]) -> None:
        """Refresh UI with new data"""
        self.all_currencies = new_currencies
        self.last_update = datetime.now().strftime("%H:%M:%S")
        self._update_api_status("connected")
        
        # Refresh existing cards
        self._refresh_existing_cards()
        self._update_currency_selector()
        
        # Show success notification
        self._show_notification("Data refreshed successfully!")
    
    def _refresh_existing_cards(self) -> None:
        """Refresh existing currency cards"""
        try:
            # Clear featured currencies
            for widget in self.featured_container.winfo_children():
                widget.destroy()
            
            # Clear dynamic currencies
            for widget in self.dynamic_container.winfo_children():
                widget.destroy()
            
            # Reset grid position
            self.grid_position = {"row": 0, "col": 0}
            
            # Redisplay featured
            self._display_featured_currencies()
            
            # Redisplay added currencies
            remaining_selected = self.selected_currencies.copy()
            preferred_featured = ["USD", "EUR", "BTC", "ETH"]
            for symbol in preferred_featured:
                remaining_selected.discard(symbol)
            
            for symbol in remaining_selected:
                if symbol in self.all_currencies:
                    card = self._create_currency_card(self.dynamic_container, self.all_currencies[symbol])
                    card.grid(
                        row=self.grid_position["row"],
                        column=self.grid_position["col"],
                        padx=6, pady=6, sticky="nsew"
                    )
                    
                    self.grid_position["col"] += 1
                    if self.grid_position["col"] >= AppConfig.GRID_COLUMNS:
                        self.grid_position["col"] = 0
                        self.grid_position["row"] += 1
        
        except Exception as e:
            logger.error(f"Card refresh error: {e}")
    
    def _test_api(self) -> None:
        """Test API connection"""
        def test_thread():
            try:
                self.after(0, lambda: self._update_api_status("connecting", "Testing API..."))
                
                api_data = self.api_manager.fetch_data()
                
                if api_data:
                    currencies = self.api_manager.process_currency_data(api_data)
                    count = len(currencies)
                    
                    self.after(0, lambda: messagebox.showinfo(
                        "API Test Success",
                        f"API is working!\n\nStatus: OK\nCurrencies Found: {count}\n\nConnection is stable."
                    ))
                else:
                    self.after(0, lambda: messagebox.showerror(
                        "API Test Failed", "Could not connect to API or parse data."
                    ))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror(
                    "API Test Error", f"API test failed: {str(e)}"
                ))
            finally:
                self.after(0, lambda: self._update_api_status(self.api_status))
        
        threading.Thread(target=test_thread, daemon=True).start()
    
    def _start_auto_refresh(self) -> None:
        """Start automatic refresh timer"""
        def auto_refresh_loop():
            while True:
                try:
                    time.sleep(AppConfig.AUTO_REFRESH_INTERVAL)
                    self.after(0, self._auto_refresh_data)
                except Exception as e:
                    logger.error(f"Auto-refresh error: {e}")
                    break
        
        self.auto_refresh_thread = threading.Thread(target=auto_refresh_loop, daemon=True)
        self.auto_refresh_thread.start()
    
    def _auto_refresh_data(self) -> None:
        """Automatically refresh data silently"""
        def refresh_thread():
            api_data = self.api_manager.fetch_data()
            if api_data:
                currencies = self.api_manager.process_currency_data(api_data)
                if currencies:
                    self.after(0, lambda: self._silent_update_ui(currencies))
        
        threading.Thread(target=refresh_thread, daemon=True).start()
    
    def _silent_update_ui(self, new_currencies: Dict[str, Dict]) -> None:
        """Silently update UI with new data"""
        self.all_currencies = new_currencies
        self.last_update = datetime.now().strftime("%H:%M:%S")
        self._update_api_status("connected")
        self._refresh_existing_cards()
        self._update_currency_selector()
        logger.info("Auto-refresh completed successfully")
    
    def _show_notification(self, message: str) -> None:
        """Show temporary notification"""
        notification = ctk.CTkFrame(
            self,
            fg_color=(ColorScheme.GLASS_OVERLAY_LIGHT, ColorScheme.GLASS_OVERLAY_DARK),
            corner_radius=12,
            border_width=0.5,
            border_color=(ColorScheme.BORDER_LIGHT, ColorScheme.BORDER_DARK)
        )
        
        notification.place(relx=0.95, rely=0.05, anchor="ne")
        
        label = ctk.CTkLabel(
            notification,
            text=message,
            font=(AppConfig.FALLBACK_FONT, 12),
            text_color=(ColorScheme.TEXT_PRIMARY_LIGHT, ColorScheme.TEXT_PRIMARY_DARK)
        )
        label.pack(padx=16, pady=8)
        
        # Auto-remove after 3 seconds
        self.after(3000, notification.destroy)

def check_requirements():
    """Check system requirements and display info"""
    print("=" * 80)
    print("   LIQUID GLASS PRICE TRACKER - OPTIMIZED VERSION")
    print("=" * 80)
    
    print(f"\nOperating System: {sys.platform}")
    print(f"API Endpoint: {AppConfig.API_URL}")
    print(f"App Resolution: {AppConfig.APP_WIDTH}x{AppConfig.APP_HEIGHT}")
    
    # Check internet connection
    try:
        response = requests.get("https://httpbin.org/status/200", timeout=5)
        print("Internet connection: Available")
    except:
        print("Internet connection: Limited - will use sample data")
    
    if IS_WINDOWS:
        print("Windows detected - Liquid Glass effects available")
        if PYWINSTYLES_AVAILABLE:
            print("PyWinStyles available - Premium effects enabled")
        else:
            print("PyWinStyles not installed - using simulation mode")
            print("Install command: pip install pywinstyles")
    else:
        print("Non-Windows system - using simulation mode")
    
    print("\nOPTIMIZATIONS:")
    print("• Modular architecture with separated concerns")
    print("• Improved error handling and logging")
    print("• Thread-safe data operations")
    print("• Optimized UI rendering and responsiveness")
    print("• Better resource management")
    print("• Enhanced fallback mechanisms")
    
    print("\nLaunching optimized application...")
    print("=" * 80 + "\n")

def main():
    """Main application entry point"""
    # Load font
    ResourceManager.load_font(AppConfig.FONT_PATH)
    
    # Check requirements
    check_requirements()
    
    # Configure CustomTkinter
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")
    
    try:
        logger.info("Initializing Liquid Glass interface...")
        app = LiquidGlassPriceTracker()
        logger.info("Application launched successfully!")
        app.mainloop()
        
    except Exception as e:
        logger.error(f"Application launch failed: {e}")
        print(f"\nApplication launch failed: {e}")
        print("Troubleshooting tips:")
        print("• Check internet connection")
        print("• Verify API endpoint accessibility")
        print("• Check PyWinStyles installation: pip install pywinstyles")
        print("• Try running as administrator")
        
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
