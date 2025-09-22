"""
**KOD BEZAN HAMMAL**

Liquid Gheymat Price Tracker - Professional Edition (Fixed API & Themes)
Advanced Real-time Currency Exchange Rate Monitor
Author: Professional Development Team
Version: 3.0.0 (API & Theme Fixed)
"""

import customtkinter as ctk
import sys
import os
import json
import pyglet
from tkinter import messagebox
import math
import requests
import threading
from datetime import datetime, timedelta
import time
from typing import Dict, List, Optional, Tuple, Callable, Any
import logging
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor
import weakref
from functools import lru_cache, wraps
import sqlite3
from pathlib import Path

# ============================================================================
# ADVANCED LOGGING CONFIGURATION
# ============================================================================

class LogManager:
    """Advanced logging manager with file and console output"""
    
    @staticmethod
    def setup_logging() -> logging.Logger:
        logger = logging.getLogger("LiquidGlass")
        logger.setLevel(logging.DEBUG)
        
        # Clear existing handlers
        logger.handlers.clear()
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_format)
        logger.addHandler(console_handler)
        
        # File handler (optional)
        try:
            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)
            file_handler = logging.FileHandler(
                log_dir / f"liquid_glass_{datetime.now().strftime('%Y%m%d')}.log",
                encoding='utf-8'
            )
            file_handler.setLevel(logging.DEBUG)
            file_format = logging.Formatter(
                '%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s'
            )
            file_handler.setFormatter(file_format)
            logger.addHandler(file_handler)
        except Exception:
            pass  # File logging is optional
        
        return logger

logger = LogManager.setup_logging()

# ============================================================================
# SYSTEM DETECTION AND DEPENDENCIES
# ============================================================================

IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

# Windows-specific effects
PYWINSTYLES_AVAILABLE = False
if IS_WINDOWS:
    try:
        import pywinstyles
        PYWINSTYLES_AVAILABLE = True
        logger.info("✅ PyWinStyles loaded - Premium effects enabled")
    except ImportError:
        logger.warning("⚠️ PyWinStyles not available - Using simulation mode")

# ============================================================================
# CONFIGURATION SYSTEM
# ============================================================================

class ConnectionStatus(Enum):
    """API Connection status enumeration"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"

@dataclass
class AppConfiguration:
    """Centralized application configuration"""
    
    # Application Info
    APP_NAME: str = "Liquid Gheymat Price Tracker"
    APP_VERSION: str = "3.0.0"
    APP_AUTHOR: str = "Professional Team"
    
    # Window Configuration
    WINDOW_WIDTH: int = 1200
    WINDOW_HEIGHT: int = 850
    MIN_WIDTH: int = 1000
    MIN_HEIGHT: int = 750
    
    # Grid Layout
    GRID_COLUMNS: int = 4
    CARD_WIDTH: int = 240
    CARD_HEIGHT: int = 145
    CARD_PADDING: int = 6
    
    # Font Configuration
    PRIMARY_FONT: str = "SF Pro Display"
    FALLBACK_FONT: str = "Segoe UI"
    PERSIAN_FONT: str = "Vazirmatn"
    
    # API Configuration - اصلاح شده!
    PRIMARY_API_URL: str = "https://brsapi.ir/Api/Market/Gold_Currency.php?key=BWUuKdavyBLGXxidEjfNJeb33rsryQfh"
    BACKUP_API_ENDPOINTS: List[str] = field(default_factory=lambda: [
        "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,binancecoin,cardano,solana,polkadot,dogecoin,avalanche-2,polygon,chainlink&vs_currencies=usd&include_24hr_change=true",
        "https://api.exchangerate-api.com/v4/latest/USD"
    ])
    API_TIMEOUT: int = 15
    API_RETRY_COUNT: int = 3
    API_RETRY_DELAY: float = 1.0
    
    # Auto-refresh Configuration
    AUTO_REFRESH_INTERVAL: int = 300  # 5 minutes
    FAST_REFRESH_INTERVAL: int = 60   # 1 minute for active mode
    
    # Cache Configuration
    CACHE_DURATION: int = 60  # seconds
    MAX_CACHE_SIZE: int = 1000
    
    # Performance Settings
    MAX_WORKER_THREADS: int = 4
    UI_UPDATE_BATCH_SIZE: int = 10
    
    # Database Configuration
    DATABASE_PATH: str = "liquid_glass_data.db"
    
    # Security Settings
    VERIFY_SSL: bool = True
    USER_AGENT: str = "LiquidGlass/2.0 (Professional Edition)"

# Initialize global config
config = AppConfiguration()

# ============================================================================
# RESOURCE MANAGEMENT SYSTEM
# ============================================================================

class ResourceManager:
    """Advanced resource management with caching and optimization"""
    
    _instance = None
    _resource_cache: Dict[str, Any] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @staticmethod
    def get_resource_path(relative_path: str) -> Path:
        """Get absolute path to resource with PyInstaller support"""
        try:
            # PyInstaller temporary folder
            base_path = Path(sys._MEIPASS)
        except AttributeError:
            # Development mode
            base_path = Path(__file__).parent
        
        return base_path / relative_path
    
    @lru_cache(maxsize=32)
    def load_font(self, font_path: str) -> bool:
        """Load font with caching and error handling"""
        if font_path in self._resource_cache:
            return True
        
        try:
            full_path = self.get_resource_path(font_path)
            if full_path.exists():
                pyglet.font.add_file(str(full_path))
                self._resource_cache[font_path] = True
                logger.info(f"✅ Font loaded: {font_path}")
                return True
        except Exception as e:
            logger.error(f"❌ Font loading failed: {e}")
        
        return False
    
    @lru_cache(maxsize=16)
    def load_icon(self, icon_path: str) -> Optional[str]:
        """Load application icon with fallback"""
        try:
            full_path = self.get_resource_path(icon_path)
            if full_path.exists():
                return str(full_path)
        except Exception as e:
            logger.warning(f"Icon not found: {e}")
        
        return None
    
    def cleanup_resources(self):
        """Clean up cached resources"""
        self._resource_cache.clear()
        try:
            pyglet.font.have_font.cache_clear()  # Clear font cache
        except:
            pass

resource_manager = ResourceManager()

# ============================================================================
# ADVANCED COLOR SYSTEM
# ============================================================================

@dataclass
class ColorPalette:
    """Advanced color palette with dynamic theme support"""
    
    # Background Colors
    bg_light: str = "#f8f9fb"
    bg_dark: str = "#0a0a0c"
    
    # Glass Effect Colors (with transparency)
    glass_light: str = "#ffffff"
    glass_dark: str = "#1a1a1e"
    glass_overlay_light: str = "#fdfdfe"
    glass_overlay_dark: str = "#151518"
    
    # 3D Effect Colors
    shadow_light: str = "#e8eaed"
    shadow_dark: str = "#050507"
    highlight_light: str = "#ffffff"
    highlight_dark: str = "#2a2a2f"
    
    # Accent Colors (Apple-inspired)
    accent_blue: str = "#007AFF"
    accent_blue_hover: str = "#0056CC"
    accent_green: str = "#32D74B"
    accent_red: str = "#FF453A"
    accent_orange: str = "#FF9F0A"
    accent_purple: str = "#BF5AF2"
    accent_pink: str = "#FF2D92"
    accent_yellow: str = "#FFD60A"
    
    # Text Colors (with hierarchy)
    text_primary_light: str = "#1d1d1f"
    text_primary_dark: str = "#f5f5f7"
    text_secondary_light: str = "#515154"
    text_secondary_dark: str = "#a1a1a6"
    text_tertiary_light: str = "#8e8e93"
    text_tertiary_dark: str = "#636366"
    
    # Border Colors
    border_light: str = "#f0f0f3"
    border_dark: str = "#2c2c2e"
    separator_light: str = "#f2f2f7"
    separator_dark: str = "#1c1c1e"
    
    # Status Colors
    status_success: str = "#32D74B"
    status_warning: str = "#FF9F0A"
    status_error: str = "#FF453A"
    status_info: str = "#007AFF"
    
    def get_theme_color(self, color_name: str, is_dark_mode: bool = None) -> str:
        """Get color based on current theme"""
        if is_dark_mode is None:
            is_dark_mode = ctk.get_appearance_mode() == "Dark"
        
        suffix = "_dark" if is_dark_mode else "_light"
        
        # Try to get theme-specific color
        theme_color = getattr(self, f"{color_name}{suffix}", None)
        if theme_color:
            return theme_color
        
        # Fallback to base color
        return getattr(self, color_name, "#000000")

colors = ColorPalette()

# ============================================================================
# DATABASE MANAGEMENT
# ============================================================================

class DatabaseManager:
    """Lightweight database for caching and preferences"""
    
    def __init__(self):
        self.db_path = config.DATABASE_PATH
        self._init_database()
    
    def _init_database(self):
        """Initialize database tables"""
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
                
                conn.commit()
                logger.info("✅ Database initialized")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
    
    def cache_currency_data(self, symbol: str, data: Dict):
        """Cache currency data with timestamp"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO currency_cache VALUES (?, ?, ?)",
                    (symbol, json.dumps(data), time.time())
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Cache write failed: {e}")
    
    def get_cached_currency_data(self, symbol: str, max_age: int = 60) -> Optional[Dict]:
        """Get cached currency data if not expired"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT data, timestamp FROM currency_cache WHERE symbol = ?",
                    (symbol,)
                )
                result = cursor.fetchone()
                
                if result:
                    data_json, timestamp = result
                    if time.time() - timestamp < max_age:
                        return json.loads(data_json)
        except Exception as e:
            logger.error(f"Cache read failed: {e}")
        
        return None
    
    def save_selected_currencies(self, currencies: set):
        """Save user's selected currencies"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Clear existing
                conn.execute("DELETE FROM selected_currencies")
                
                # Insert current selection
                for symbol in currencies:
                    conn.execute(
                        "INSERT INTO selected_currencies VALUES (?, ?)",
                        (symbol, time.time())
                    )
                
                conn.commit()
        except Exception as e:
            logger.error(f"Selected currencies save failed: {e}")
    
    def load_selected_currencies(self) -> set:
        """Load user's selected currencies"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT symbol FROM selected_currencies")
                return {row[0] for row in cursor.fetchall()}
        except Exception as e:
            logger.error(f"Selected currencies load failed: {e}")
            return set()

db_manager = DatabaseManager()

# ============================================================================
# ENHANCED API MANAGEMENT - اصلاح شده!
# ============================================================================

class APIManager:
    """Professional API management with focus on your original API"""
    
    def __init__(self):
        self.session = self._create_session()
        self.last_request_time = 0
        self.rate_limit_delay = 1.0
        self.retry_count = 0
        self.circuit_breaker_until = 0
        
    def _create_session(self) -> requests.Session:
        """Create optimized requests session"""
        session = requests.Session()
        
        # Advanced headers for Iranian API
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'DNT': '1',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1'
        })
        
        # Connection pooling
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=0  # We handle retries manually
        )
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        
        return session
    
    def _respect_rate_limit(self):
        """Implement rate limiting"""
        time_since_last = time.time() - self.last_request_time
        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def fetch_data_sync(self) -> Optional[Dict]:
        """Fetch data with priority on your original API"""
        # اول API اصلی شما رو امتحان می‌کنیم
        logger.info("🔄 Trying primary API (BRS)...")
        data = self._try_primary_api()
        if data:
            logger.info("✅ Primary API successful!")
            return data
        
        # اگر نشد، backup APIs رو امتحان می‌کنیم
        logger.info("⚠️ Primary API failed, trying backups...")
        for i, backup_url in enumerate(config.BACKUP_API_ENDPOINTS):
            logger.info(f"🔄 Trying backup API {i+1}...")
            data = self._try_backup_api(backup_url)
            if data:
                logger.info(f"✅ Backup API {i+1} successful!")
                return data
        
        logger.error("❌ All APIs failed")
        return None
    
    def _try_primary_api(self) -> Optional[Dict]:
        """Try your original BRS API"""
        try:
            self._respect_rate_limit()
            
            response = self.session.get(
                config.PRIMARY_API_URL,
                timeout=config.API_TIMEOUT,
                verify=config.VERIFY_SSL
            )
            
            response.raise_for_status()
            
            # Check content type
            content_type = response.headers.get('content-type', '')
            if 'json' not in content_type.lower():
                logger.warning(f"Unexpected content type: {content_type}")
            
            data = response.json()
            
            if not data:
                raise ValueError("Empty response from primary API")
            
            logger.info(f"Primary API response structure: {type(data)}")
            logger.debug(f"Primary API sample keys: {list(data.keys())[:5] if isinstance(data, dict) else 'Not a dict'}")
            
            return data
            
        except requests.exceptions.Timeout:
            logger.warning("Primary API timeout")
        except requests.exceptions.RequestException as e:
            logger.warning(f"Primary API request failed: {e}")
        except (ValueError, json.JSONDecodeError) as e:
            logger.warning(f"Primary API parsing error: {e}")
        except Exception as e:
            logger.warning(f"Primary API unexpected error: {e}")
        
        return None
    
    def _try_backup_api(self, url: str) -> Optional[Dict]:
        """Try backup APIs"""
        try:
            self._respect_rate_limit()
            
            response = self.session.get(url, timeout=config.API_TIMEOUT)
            response.raise_for_status()
            
            data = response.json()
            
            if not data:
                return None
            
            # Transform backup data to standard format
            if 'coingecko.com' in url:
                return self._transform_coingecko_data(data)
            elif 'exchangerate-api.com' in url:
                return self._transform_exchange_rate_data(data)
            
            return data
            
        except Exception as e:
            logger.warning(f"Backup API failed: {e}")
            return None
    
    def process_currency_data(self, raw_data: Dict) -> Dict[str, Dict]:
        """Process currency data with focus on your original API format"""
        currencies = {}
        processed_count = 0
        
        try:
            # اول format API اصلی شما رو چک می‌کنیم
            if self._is_primary_api_format(raw_data):
                logger.info("🎯 Processing primary API format")
                currencies = self._process_primary_api_format(raw_data)
            # اگر backup format بود
            elif 'crypto' in raw_data or 'fiat' in raw_data:
                logger.info("🔄 Processing backup API format")
                currencies = self._process_backup_api_format(raw_data)
            # اگر هیچکدوم نبود، generic processing
            else:
                logger.info("🔍 Processing generic format")
                currencies = self._process_generic_format(raw_data)
            
            processed_count = len(currencies)
            logger.info(f"✅ Successfully processed {processed_count} currencies")
            
            return currencies
            
        except Exception as e:
            logger.error(f"Currency processing failed: {e}")
            return {}
    
    def _is_primary_api_format(self, data: Any) -> bool:
        """Check if data is from your original API"""
        if not isinstance(data, dict):
            return False
        
        # API شما معمولاً category هایی مثل Gold, Currency, Crypto داره
        primary_indicators = [
            'Gold', 'Currency', 'Crypto', 'Digital_Currency',
            'Arz', 'Tala', 'Sekke', 'gold', 'currency', 'crypto'
        ]
        
        # بررسی می‌کنیم که آیا کلیدهای مشخصه‌ای داره یا نه
        for indicator in primary_indicators:
            if indicator in data:
                return True
        
        # اگر structure مشخصی داره که نشان‌دهنده API اصلی هست
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, list) and len(value) > 0:
                    if isinstance(value[0], dict):
                        # بررسی فیلدهای مشخصه ایرانی
                        sample = value[0]
                        iranian_fields = ['symbol', 'price', 'unit', 'name_fa', 'name_en']
                        if any(field in sample for field in iranian_fields):
                            return True
        
        return False
    
    def _process_primary_api_format(self, data: Dict) -> Dict[str, Dict]:
        """Process your original API format"""
        currencies = {}
        
        try:
            # پردازش تمام category ها
            for category_name, category_data in data.items():
                logger.debug(f"Processing category: {category_name}")
                
                if isinstance(category_data, list):
                    # اگر لیست باشه، هر آیتم رو پردازش می‌کنیم
                    for item in category_data:
                        currency = self._process_single_currency_primary(item, category_name)
                        if currency:
                            currencies[currency['symbol']] = currency
                
                elif isinstance(category_data, dict):
                    # اگر dict باشه، ممکنه خودش یک currency باشه
                    if self._looks_like_currency_item(category_data):
                        currency = self._process_single_currency_primary(category_data, category_name)
                        if currency:
                            currencies[currency['symbol']] = currency
                    else:
                        # یا ممکنه nested structure باشه
                        for sub_key, sub_data in category_data.items():
                            if isinstance(sub_data, list):
                                for item in sub_data:
                                    currency = self._process_single_currency_primary(item, f"{category_name}_{sub_key}")
                                    if currency:
                                        currencies[currency['symbol']] = currency
            
            logger.info(f"Primary API processing completed: {len(currencies)} currencies")
            return currencies
            
        except Exception as e:
            logger.error(f"Primary API processing error: {e}")
            return {}
    
    def _process_single_currency_primary(self, item: Dict, category: str = "") -> Optional[Dict]:
        """Process single currency from your original API"""
        if not isinstance(item, dict):
            return None
        
        try:
            # استخراج symbol با اولویت‌های مختلف
            symbol = self._extract_field(item, [
                'symbol', 'Symbol', 'SYMBOL',
                'code', 'Code', 'CODE',
                'currency_code', 'Currency_Code',
                'name_en', 'Name_En', 'NAME_EN'
            ])
            
            if not symbol:
                return None
            
            # پاک‌سازی symbol
            symbol = str(symbol).upper().strip()
            if not symbol:
                return None
            
            # استخراج قیمت
            price = self._extract_field(item, [
                'price', 'Price', 'PRICE',
                'value', 'Value', 'VALUE',
                'rate', 'Rate', 'RATE',
                'sell', 'Sell', 'SELL',
                'buy', 'Buy', 'BUY',
                'last_price', 'Last_Price'
            ], default="0")
            
            # استخراج تغییر درصد
            change = self._extract_field(item, [
                'change_percent', 'Change_Percent', 'CHANGE_PERCENT',
                'change', 'Change', 'CHANGE',
                'daily_change', 'Daily_Change',
                'percent_change_24h', 'Percent_Change_24h'
            ], default="0")
            
            # استخراج واحد
            unit = self._extract_field(item, [
                'unit', 'Unit', 'UNIT',
                'currency', 'Currency', 'CURRENCY',
                'base_currency', 'Base_Currency',
                'quote_currency', 'Quote_Currency'
            ], default="Toman")
            
            # استخراج نام
            name = self._extract_field(item, [
                'name_fa', 'Name_Fa', 'NAME_FA',
                'name_en', 'Name_En', 'NAME_EN',
                'name', 'Name', 'NAME',
                'title', 'Title', 'TITLE',
                'full_name', 'Full_Name'
            ])
            
            if not name:
                name = self._get_currency_name_by_symbol(symbol)
            
            # ایجاد currency object
            currency = {
                'symbol': symbol,
                'name': name,
                'price': str(price),
                'unit': str(unit),
                'change_percent': str(change),
                'category': category,
                'timestamp': time.time(),
                'source': 'primary_api'
            }
            
            # Validation
            if self._validate_currency_data(currency):
                return currency
            
        except Exception as e:
            logger.debug(f"Single currency processing error: {e}")
        
        return None
    
    def _get_currency_name_by_symbol(self, symbol: str) -> str:
        """Get currency name by symbol - Enhanced for Iranian market"""
        # نقشه کامل ارزها و طلا و سکه
        currency_map = {
            # ارزهای اصلی
            'USD': 'دلار آمریکا', 'EUR': 'یورو', 'GBP': 'پوند انگلیس',
            'JPY': 'ین ژاپن', 'CHF': 'فرانک سوئیس', 'CAD': 'دلار کانادا',
            'AUD': 'دلار استرالیا', 'SEK': 'کرون سوئد', 'NOK': 'کرون نروژ',
            'DKK': 'کرون دانمارک', 'TRY': 'لیر ترکیه', 'CNY': 'یوان چین',
            'INR': 'روپیه هند', 'PKR': 'روپیه پاکستان', 'KWD': 'دینار کویت',
            'AED': 'درهم امارات', 'SAR': 'ریال عربستان', 'QAR': 'ریال قطر',
            'OMR': 'ریال عمان', 'BHD': 'دینار بحرین', 'IQD': 'دینار عراق',
            'LBP': 'لیر لبنان', 'AFN': 'افغانی افغانستان',
            
            # ارزهای دیجیتال
            'BTC': 'بیت کوین', 'ETH': 'اتریوم', 'BNB': 'بایننس کوین',
            'XRP': 'ریپل', 'ADA': 'کاردانو', 'SOL': 'سولانا',
            'DOT': 'پولکادات', 'DOGE': 'دوج کوین', 'AVAX': 'آوالانچ',
            'MATIC': 'پولیگون', 'LINK': 'چین لینک', 'UNI': 'یونی سواپ',
            'LTC': 'لایت کوین', 'BCH': 'بیت کوین کش', 'XLM': 'استلار',
            'VET': 'وی چین', 'ICP': 'اینترنت کامپیوتر', 'FIL': 'فایل کوین',
            'TRX': 'ترون', 'ETC': 'اتریوم کلاسیک', 'ATOM': 'کازموس',
            'XMR': 'مونرو', 'ALGO': 'الگورند', 'XTZ': 'تزوس',
            
            # طلا و فلزات
            'GOLD': 'طلا', 'SILVER': 'نقره', 'PLATINUM': 'پلاتین',
            'PALLADIUM': 'پالادیوم',
            
            # سکه‌ها
            'SEKEH': 'سکه طلا', 'SEKEH_GOLD': 'سکه طلای بهار آزادی',
            'GERAM18': 'گرم طلای ۱۸ عیار', 'GERAM24': 'گرم طلای ۲۴ عیار',
            'MESGHAL': 'مثقال طلا', 'OUNCE': 'اونس طلا',
            
            # ارزهای محلی
            'AFN': 'افغانی', 'AMD': 'درام ارمنستان', 'AZN': 'منات آذربایجان',
            'GEL': 'لاری گرجستان', 'KGS': 'سوم قرقیزستان', 'KZT': 'تنگه قزاقستان',
            'RUB': 'روبل روسیه', 'TJS': 'سامانی تاجیکستان', 'TMT': 'منات ترکمنستان',
            'UZS': 'سوم ازبکستان'
        }
        
        # اگر پیدا شد، برگردان
        if symbol in currency_map:
            return currency_map[symbol]
        
        # اگر نه، خود symbol رو برگردان
        return symbol
    
    def _looks_like_currency_item(self, item: Dict) -> bool:
        """Check if item looks like a currency"""
        if not isinstance(item, dict):
            return False
        
        # Check for essential fields
        essential_fields = [
            ['symbol', 'price'], ['Symbol', 'Price'],
            ['code', 'value'], ['name_en', 'price'],
            ['currency_code', 'rate']
        ]
        
        for field_set in essential_fields:
            if all(field in item for field in field_set):
                return True
        
        return False
    
    def _process_backup_api_format(self, data: Dict) -> Dict[str, Dict]:
        """Process backup API formats"""
        currencies = {}
        
        try:
            if 'crypto' in data:
                for item in data['crypto']:
                    if isinstance(item, dict) and 'symbol' in item:
                        currencies[item['symbol']] = item
            
            if 'fiat' in data:
                for item in data['fiat']:
                    if isinstance(item, dict) and 'symbol' in item:
                        currencies[item['symbol']] = item
            
            return currencies
            
        except Exception as e:
            logger.error(f"Backup API processing error: {e}")
            return {}
    
    def _process_generic_format(self, data: Any) -> Dict[str, Dict]:
        """Process generic data format"""
        currencies = {}
        
        try:
            items = self._extract_items_generic(data)
            
            for item in items:
                currency = self._process_single_currency_generic(item)
                if currency and self._validate_currency_data(currency):
                    currencies[currency['symbol']] = currency
            
            return currencies
            
        except Exception as e:
            logger.error(f"Generic processing error: {e}")
            return {}
    
    def _extract_items_generic(self, data: Any) -> List[Dict]:
        """Extract items from generic data structure"""
        items = []
        
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, list):
                    items.extend(value)
                elif isinstance(value, dict) and self._looks_like_currency_item(value):
                    items.append(value)
        elif isinstance(data, list):
            items.extend(data)
        
        return items
    
    def _process_single_currency_generic(self, item: Dict) -> Optional[Dict]:
        """Process single currency from generic format"""
        if not isinstance(item, dict):
            return None
        
        symbol = self._extract_field(item, [
            'symbol', 'Symbol', 'code', 'Code'
        ])
        
        if not symbol:
            return None
        
        price = self._extract_field(item, [
            'price', 'Price', 'value', 'Value', 'rate', 'Rate'
        ], default=0)
        
        change = self._extract_field(item, [
            'change_percent', 'change', 'Change'
        ], default=0)
        
        unit = self._extract_field(item, [
            'unit', 'Unit', 'currency', 'Currency'
        ], default='USD')
        
        name = self._get_currency_name_by_symbol(str(symbol).upper())
        
        return {
            'symbol': str(symbol).upper(),
            'name': name,
            'price': str(price),
            'unit': str(unit),
            'change_percent': str(change),
            'timestamp': time.time(),
            'source': 'generic'
        }
    
    def _transform_coingecko_data(self, data: Dict) -> Dict:
        """Transform CoinGecko data"""
        transformed = {}
        
        crypto_mapping = {
            'bitcoin': 'BTC', 'ethereum': 'ETH', 'binancecoin': 'BNB',
            'cardano': 'ADA', 'solana': 'SOL', 'polkadot': 'DOT',
            'dogecoin': 'DOGE', 'avalanche-2': 'AVAX', 'polygon': 'MATIC',
            'chainlink': 'LINK'
        }
        
        for coin_id, coin_data in data.items():
            if coin_id in crypto_mapping:
                symbol = crypto_mapping[coin_id]
                transformed[symbol] = {
                    'symbol': symbol,
                    'name': self._get_currency_name_by_symbol(symbol),
                    'price': str(coin_data.get('usd', 0)),
                    'unit': 'USD',
                    'change_percent': str(coin_data.get('usd_24h_change', 0)),
                    'timestamp': time.time(),
                    'source': 'coingecko'
                }
        
        return {'crypto': list(transformed.values())}
    
    def _transform_exchange_rate_data(self, data: Dict) -> Dict:
        """Transform Exchange Rate API data"""
        transformed = {}
        
        rates = data.get('rates', {})
        major_currencies = ['EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'CHF']
        
        # Add USD
        transformed['USD'] = {
            'symbol': 'USD',
            'name': self._get_currency_name_by_symbol('USD'),
            'price': '1.0',
            'unit': 'USD',
            'change_percent': '0',
            'timestamp': time.time(),
            'source': 'exchangerate-api'
        }
        
        for symbol in major_currencies:
            if symbol in rates:
                rate = rates[symbol]
                transformed[symbol] = {
                    'symbol': symbol,
                    'name': self._get_currency_name_by_symbol(symbol),
                    'price': str(1 / rate),
                    'unit': 'USD',
                    'change_percent': '0',
                    'timestamp': time.time(),
                    'source': 'exchangerate-api'
                }
        
        return {'fiat': list(transformed.values())}
    
    def _extract_field(self, data: Dict, field_names: List[str], default: Any = None) -> Any:
        """Extract field with multiple name variations"""
        for field_name in field_names:
            if field_name in data:
                value = data[field_name]
                if value is not None and str(value).strip():
                    return value
        return default
    
    def _validate_currency_data(self, currency: Dict) -> bool:
        """Validate currency data"""
        required_fields = ['symbol', 'name', 'price', 'unit']
        
        for field in required_fields:
            if field not in currency or not str(currency[field]).strip():
                return False
        
        try:
            float(currency['price'])
        except (ValueError, TypeError):
            return False
        
        try:
            float(currency.get('change_percent', 0))
        except (ValueError, TypeError):
            currency['change_percent'] = '0'
        
        return True
    
    @staticmethod
    def get_fallback_data() -> Dict[str, Dict]:
        """Enhanced fallback data with Iranian focus"""
        return {
            "USD": {
                "symbol": "USD",
                "name": "دلار آمریکا",
                "price": "57250",
                "unit": "تومان",
                "change_percent": "1.24",
                "timestamp": time.time(),
                "source": "fallback"
            },
            "EUR": {
                "symbol": "EUR", 
                "name": "یورو",
                "price": "62180",
                "unit": "تومان",
                "change_percent": "-0.68",
                "timestamp": time.time(),
                "source": "fallback"
            },
            "GBP": {
                "symbol": "GBP",
                "name": "پوند انگلیس", 
                "price": "72340",
                "unit": "تومان",
                "change_percent": "2.15",
                "timestamp": time.time(),
                "source": "fallback"
            },
            "BTC": {
                "symbol": "BTC",
                "name": "بیت کوین",
                "price": "97543",
                "unit": "USD",
                "change_percent": "3.45",
                "timestamp": time.time(),
                "source": "fallback"
            },
            "ETH": {
                "symbol": "ETH",
                "name": "اتریوم",
                "price": "3892",
                "unit": "USD", 
                "change_percent": "5.23",
                "timestamp": time.time(),
                "source": "fallback"
            },
            "GOLD": {
                "symbol": "GOLD",
                "name": "طلا",
                "price": "2234",
                "unit": "USD/oz",
                "change_percent": "0.89",
                "timestamp": time.time(),
                "source": "fallback"
            },
            "SEKEH": {
                "symbol": "SEKEH",
                "name": "سکه طلا",
                "price": "28500000",
                "unit": "تومان",
                "change_percent": "2.5",
                "timestamp": time.time(),
                "source": "fallback"
            },
            "GERAM18": {
                "symbol": "GERAM18",
                "name": "گرم طلای ۱۸ عیار",
                "price": "2870000",
                "unit": "تومان",
                "change_percent": "1.8",
                "timestamp": time.time(),
                "source": "fallback"
            }
        }

# ============================================================================
# FIXED VISUAL EFFECTS MANAGER - مشکل تم‌ها حل شد!
# ============================================================================

class VisualEffectsManager:
    """Fixed visual effects manager with proper theme switching"""
    
    def __init__(self, window):
        self.window = window
        self.current_effect = "liquid_glass"
        self.transparency_level = 0.95
        self.effects_history = []
        self.is_applying = False  # جلوگیری از تداخل
        
    def apply_liquid_glass_effect(self, intensity: float = 0.95):
        """Apply liquid glass effect with proper cleanup"""
        if self.is_applying:
            return
            
        try:
            self.is_applying = True
            logger.info("🔄 Applying Liquid Glass effect...")
            
            self._cleanup_previous_effects()
            self.transparency_level = intensity
            
            if not IS_WINDOWS or not PYWINSTYLES_AVAILABLE:
                self._apply_simulation_mode("liquid_glass")
                return
            
            # Try liquid glass effects in order
            effects_to_try = [
                ('acrylic', 0.97),
                ('mica', 0.96), 
                ('blur', 0.95),
                ('aero', 0.94)
            ]
            
            for effect_name, alpha in effects_to_try:
                if self._try_apply_effect(effect_name, alpha):
                    self.current_effect = "liquid_glass"
                    self._record_effect_change("liquid_glass")
                    logger.info("✅ Liquid Glass effect applied successfully")
                    return
            
            # All effects failed
            self._apply_simulation_mode("liquid_glass")
            
        except Exception as e:
            logger.error(f"Liquid Glass effect failed: {e}")
            self._apply_simulation_mode("liquid_glass")
        finally:
            self.is_applying = False
    
    def apply_vibrancy_effect(self):
        """Apply vibrancy effect with proper cleanup"""
        if self.is_applying:
            return
            
        try:
            self.is_applying = True
            logger.info("🔄 Applying Vibrancy effect...")
            
            self._cleanup_previous_effects()
            
            if not IS_WINDOWS or not PYWINSTYLES_AVAILABLE:
                self._apply_simulation_mode("vibrancy")
                return
            
            # Try vibrancy specific effects
            if self._try_apply_effect('aero', 0.92):
                self.current_effect = "vibrancy"
                self._record_effect_change("vibrancy")
                logger.info("✅ Vibrancy effect applied successfully")
            elif self._try_apply_effect('blur', 0.90):
                self.current_effect = "vibrancy"
                self._record_effect_change("vibrancy")
                logger.info("✅ Vibrancy effect applied successfully (fallback)")
            else:
                self._apply_simulation_mode("vibrancy")
                
        except Exception as e:
            logger.error(f"Vibrancy effect failed: {e}")
            self._apply_simulation_mode("vibrancy")
        finally:
            self.is_applying = False
    
    def apply_crystal_mode(self):
        """Apply crystal mode with proper cleanup"""
        if self.is_applying:
            return
            
        try:
            self.is_applying = True
            logger.info("🔄 Applying Crystal mode...")
            
            self._cleanup_previous_effects()
            
            if not IS_WINDOWS or not PYWINSTYLES_AVAILABLE:
                self._apply_simulation_mode("crystal")
                return
            
            # Try crystal specific effects
            if self._try_apply_effect('optimised', 0.89):
                self.current_effect = "crystal"
                self._record_effect_change("crystal")
                logger.info("✅ Crystal mode applied successfully")
            elif self._try_apply_effect('acrylic', 0.88):
                self.current_effect = "crystal"
                self._record_effect_change("crystal") 
                logger.info("✅ Crystal mode applied successfully (fallback)")
            else:
                self._apply_simulation_mode("crystal")
                
        except Exception as e:
            logger.error(f"Crystal mode failed: {e}")
            self._apply_simulation_mode("crystal")
        finally:
            self.is_applying = False
    
    def _cleanup_previous_effects(self):
        """Clean up previous effects properly"""
        try:
            # Reset window to normal state
            if IS_WINDOWS and PYWINSTYLES_AVAILABLE:
                pywinstyles.apply_style(self.window, "normal")
                
            # Reset transparency
            self.window.attributes('-alpha', 1.0)
            
            # Force update
            self.window.update_idletasks()
            
            # Small delay to ensure cleanup
            time.sleep(0.1)
            
        except Exception as e:
            logger.debug(f"Cleanup warning: {e}")
    
    def _try_apply_effect(self, effect_name: str, alpha: float) -> bool:
        """Try to apply a specific effect with proper error handling"""
        try:
            # Apply the effect
            pywinstyles.apply_style(self.window, effect_name)
            
            # Small delay for effect to take hold
            time.sleep(0.05)
            
            # Apply transparency
            self.window.attributes('-alpha', alpha)
            
            # Force update
            self.window.update_idletasks()
            
            logger.debug(f"✅ {effect_name} effect applied successfully")
            return True
            
        except Exception as e:
            logger.debug(f"❌ {effect_name} effect failed: {e}")
            
            # Try to reset if failed
            try:
                self.window.attributes('-alpha', 1.0)
            except:
                pass
                
            return False
    
    def _apply_simulation_mode(self, effect_type: str):
        """Apply simulation mode for unsupported systems"""
        try:
            self.current_effect = f"{effect_type}_simulation"
            
            # Apply subtle transparency if supported
            self.window.attributes('-alpha', 0.98)
            
            self._record_effect_change(f"{effect_type}_simulation")
            logger.info(f"🎨 {effect_type.title()} simulation applied")
            
        except Exception as e:
            logger.debug(f"Simulation mode warning: {e}")
            self.current_effect = f"{effect_type}_simulation"
            self._record_effect_change(f"{effect_type}_simulation")
    
    def _record_effect_change(self, effect_name: str):
        """Record effect change for debugging"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.effects_history.append({
            'effect': effect_name,
            'timestamp': timestamp,
            'transparency': getattr(self, 'transparency_level', 1.0)
        })
        
        # Keep only last 10 changes
        if len(self.effects_history) > 10:
            self.effects_history = self.effects_history[-10:]
    
    def get_current_effect_info(self) -> Dict[str, Any]:
        """Get current effect information"""
        return {
            'effect': self.current_effect,
            'transparency': self.transparency_level,
            'supported': IS_WINDOWS and PYWINSTYLES_AVAILABLE,
            'history': self.effects_history[-3:],  # Last 3 changes
            'is_applying': self.is_applying
        }
    
    def reset_to_normal(self):
        """Reset window to normal state"""
        try:
            self._cleanup_previous_effects()
            self.current_effect = "normal"
            self._record_effect_change("normal")
            logger.info("🔄 Window reset to normal state")
        except Exception as e:
            logger.error(f"Reset failed: {e}")

# ============================================================================
# PERFORMANCE MONITORING
# ============================================================================

class PerformanceMonitor:
    """Monitor application performance"""
    
    def __init__(self):
        self.metrics = {
            'ui_updates': 0,
            'api_calls': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'errors': 0
        }
        self.start_time = time.time()
    
    def record_ui_update(self):
        """Record UI update event"""
        self.metrics['ui_updates'] += 1
    
    def record_api_call(self):
        """Record API call event"""
        self.metrics['api_calls'] += 1
    
    def record_cache_hit(self):
        """Record cache hit event"""
        self.metrics['cache_hits'] += 1
    
    def record_cache_miss(self):
        """Record cache miss event"""
        self.metrics['cache_misses'] += 1
    
    def record_error(self):
        """Record error event"""
        self.metrics['errors'] += 1
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Get performance report"""
        runtime = time.time() - self.start_time
        total_cache = self.metrics['cache_hits'] + self.metrics['cache_misses']
        cache_ratio = self.metrics['cache_hits'] / total_cache if total_cache > 0 else 0
        
        return {
            'runtime_seconds': runtime,
            'runtime_formatted': str(timedelta(seconds=int(runtime))),
            'metrics': self.metrics.copy(),
            'cache_hit_ratio': cache_ratio,
            'ui_updates_per_minute': self.metrics['ui_updates'] / (runtime / 60) if runtime > 0 else 0,
            'error_rate': self.metrics['errors'] / self.metrics['api_calls'] if self.metrics['api_calls'] > 0 else 0
        }

performance_monitor = PerformanceMonitor()

# ============================================================================
# MAIN APPLICATION CLASS - ادامه کد اصلی...
# ============================================================================

class LiquidGlassPriceTracker(ctk.CTk):
    """Professional Liquid Glass Price Tracker - API & Theme Fixed"""
    
    def __init__(self):
        super().__init__()
        
        # Initialize core systems
        self.api_manager = APIManager()
        self.effects_manager = VisualEffectsManager(self)
        self.executor = ThreadPoolExecutor(max_workers=config.MAX_WORKER_THREADS)
        
        # Application state
        self.currencies: Dict[str, Dict] = {}
        self.selected_currencies: set = set()
        self.connection_status = ConnectionStatus.DISCONNECTED
        self.last_update = "Never"
        self.auto_refresh_active = True
        self.grid_position = {"row": 0, "col": 0}
        self.ui_elements = {}
        
        # Initialize application
        self._setup_window()
        self._load_resources()
        self._apply_visual_effects()
        self._create_user_interface()
        self._load_saved_preferences()
        self._start_data_systems()
        
        logger.info("🚀 Liquid Glass Price Tracker initialized successfully!")
    
    def _setup_window(self):
        """Configure main application window"""
        self.title(f"{config.APP_NAME} v{config.APP_VERSION}")
        self.geometry(f"{config.WINDOW_WIDTH}x{config.WINDOW_HEIGHT}")
        self.minsize(config.MIN_WIDTH, config.MIN_HEIGHT)
        self.resizable(True, True)
        
        # Center window
        self._center_window()
        
        # Configure theme
        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")
        
        # Set background
        self.configure(fg_color=(colors.bg_light, colors.bg_dark))
        
        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Set icon
        icon_path = resource_manager.load_icon("assets/icons/icon.ico")
        if icon_path:
            try:
                self.iconbitmap(icon_path)
            except Exception as e:
                logger.warning(f"Could not set icon: {e}")
    
    def _center_window(self):
        """Center window on screen"""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')
    
    def _load_resources(self):
        """Load application resources"""
        font_paths = [
            "assets/fonts/Vazirmatn-Regular.ttf",
            "assets/fonts/SF-Pro-Display-Regular.ttf",
            "assets/fonts/Inter-Regular.ttf"
        ]
        
        for font_path in font_paths:
            resource_manager.load_font(font_path)
    
    def _apply_visual_effects(self):
        """Apply initial visual effects"""
        self.after(100, self.effects_manager.apply_liquid_glass_effect)
    
    def _create_user_interface(self):
        """Create the complete user interface"""
        # Main container
        self.main_container = ctk.CTkFrame(
            self, 
            fg_color="transparent", 
            corner_radius=0
        )
        self.main_container.pack(fill="both", expand=True, padx=20, pady=20)
        self.main_container.grid_columnconfigure(0, weight=1)
        
        # Scrollable content
        self.scroll_frame = ctk.CTkScrollableFrame(
            self.main_container,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=(colors.border_light, colors.border_dark),
            scrollbar_button_hover_color=(colors.accent_blue, colors.accent_blue)
        )
        self.scroll_frame.pack(fill="both", expand=True)
        self.scroll_frame.grid_columnconfigure(0, weight=1)
        
        # Create interface sections
        self._create_hero_section()
        self._create_status_section()
        self._create_featured_section()
        self._create_portfolio_section()
        self._create_controls_section()
        if IS_WINDOWS and PYWINSTYLES_AVAILABLE:
            self._create_advanced_controls()
    
    def _create_hero_section(self):
        """Create hero header"""
        hero_card = self._create_glass_card(
            self.scroll_frame,
            height=180,
            glass_level=3
        )
        hero_card.grid(row=0, column=0, sticky="ew", pady=(0, 24))
        
        content = ctk.CTkFrame(hero_card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=32, pady=24)
        
        # Title
        title = ctk.CTkLabel(
            content,
            text="💎 Liquid Gheymat?!",
            font=(config.FALLBACK_FONT, 42, "bold"),
            text_color=(colors.text_primary_light, colors.text_primary_dark)
        )
        title.pack(anchor="w")
        
        # Subtitle
        subtitle = ctk.CTkLabel(
            content,
            text="Professional Real-time Currency & Crypto Tracker",
            font=(config.FALLBACK_FONT, 18),
            text_color=(colors.text_secondary_light, colors.text_secondary_dark)
        )
        subtitle.pack(anchor="w", pady=(8, 0))
        
        # Version
        version_info = ctk.CTkLabel(
            content,
            text=f"Version {config.APP_VERSION} • API & Theme Fixed",
            font=(config.FALLBACK_FONT, 14),
            text_color=(colors.text_tertiary_light, colors.text_tertiary_dark)
        )
        version_info.pack(anchor="w", pady=(12, 0))
    
    def _create_status_section(self):
        """Create status indicators"""
        status_card = self._create_glass_card(
            self.scroll_frame,
            height=120,
            glass_level=2
        )
        status_card.grid(row=1, column=0, sticky="ew", pady=(0, 24))
        
        content = ctk.CTkFrame(status_card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=20)
        
        # Status grid
        status_grid = ctk.CTkFrame(content, fg_color="transparent")
        status_grid.pack(fill="x")
        status_grid.grid_columnconfigure((0, 1, 2), weight=1)
        
        # API Status
        self._create_status_indicator(
            status_grid, 
            "API Connection", 
            "🔗", 
            "api_status",
            row=0, col=0
        )
        
        # Data Status
        self._create_status_indicator(
            status_grid, 
            "Data Quality", 
            "📊", 
            "data_status",
            row=0, col=1
        )
        
        # Effects Status
        self._create_status_indicator(
            status_grid, 
            "Visual Effects", 
            "✨", 
            "effects_status",
            row=0, col=2
        )
    
    def _create_status_indicator(self, parent, title, icon, key, row, col):
        """Create individual status indicator"""
        container = ctk.CTkFrame(
            parent,
            fg_color=(colors.glass_overlay_light, colors.glass_overlay_dark),
            corner_radius=12,
            border_width=1,
            border_color=(colors.border_light, colors.border_dark),
            height=70
        )
        container.grid(row=row, column=col, padx=8, pady=4, sticky="ew")
        
        content = ctk.CTkFrame(container, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=16, pady=12)
        
        # Header
        header = ctk.CTkFrame(content, fg_color="transparent")
        header.pack(fill="x")
        
        icon_label = ctk.CTkLabel(
            header,
            text=icon,
            font=(config.FALLBACK_FONT, 16)
        )
        icon_label.pack(side="left")
        
        title_label = ctk.CTkLabel(
            header,
            text=title,
            font=(config.FALLBACK_FONT, 13, "bold"),
            text_color=(colors.text_primary_light, colors.text_primary_dark)
        )
        title_label.pack(side="left", padx=(8, 0))
        
        # Status
        status_label = ctk.CTkLabel(
            content,
            text="Initializing...",
            font=(config.FALLBACK_FONT, 11),
            text_color=(colors.text_secondary_light, colors.text_secondary_dark)
        )
        status_label.pack(anchor="w", pady=(4, 0))
        
        # Store reference
        self.ui_elements[key] = {
            'container': container,
            'status_label': status_label
        }
    
    def _create_featured_section(self):
        """Create featured currencies section"""
        section_title = ctk.CTkLabel(
            self.scroll_frame,
            text="📈 Featured Markets",
            font=(config.FALLBACK_FONT, 24, "bold"),
            text_color=(colors.text_primary_light, colors.text_primary_dark)
        )
        section_title.grid(row=2, column=0, sticky="w", pady=(0, 16))
        
        self.featured_container = ctk.CTkFrame(
            self.scroll_frame,
            fg_color="transparent"
        )
        self.featured_container.grid(row=3, column=0, sticky="ew", pady=(0, 32))
        
        # Configure grid
        for i in range(config.GRID_COLUMNS):
            self.featured_container.grid_columnconfigure(i, weight=1)
    
    def _create_portfolio_section(self):
        """Create portfolio section"""
        # Header
        portfolio_header = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        portfolio_header.grid(row=4, column=0, sticky="ew", pady=(0, 16))
        portfolio_header.grid_columnconfigure(1, weight=1)
        
        # Title
        portfolio_title = ctk.CTkLabel(
            portfolio_header,
            text="💼 Your Portfolio",
            font=(config.FALLBACK_FONT, 24, "bold"),
            text_color=(colors.text_primary_light, colors.text_primary_dark)
        )
        portfolio_title.grid(row=0, column=0, sticky="w")
        
        # Add controls
        add_controls = self._create_add_currency_controls(portfolio_header)
        add_controls.grid(row=0, column=1, sticky="e")
        
        # Portfolio container
        self.portfolio_container = ctk.CTkFrame(
            self.scroll_frame,
            fg_color="transparent"
        )
        self.portfolio_container.grid(row=5, column=0, sticky="ew", pady=(0, 32))
        
        # Configure grid
        for i in range(config.GRID_COLUMNS):
            self.portfolio_container.grid_columnconfigure(i, weight=1)
    
    def _create_add_currency_controls(self, parent):
        """Create add currency controls"""
        controls_frame = ctk.CTkFrame(
            parent,
            fg_color=(colors.glass_overlay_light, colors.glass_overlay_dark),
            corner_radius=12,
            border_width=1,
            border_color=(colors.border_light, colors.border_dark),
            height=50
        )
        
        content = ctk.CTkFrame(controls_frame, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=16, pady=8)
        
        # Currency selector
        self.currency_selector = ctk.CTkComboBox(
            content,
            font=(config.FALLBACK_FONT, 13),
            values=["Loading currencies..."],
            state="readonly",
            width=200,
            height=34,
            corner_radius=8,
            border_width=1,
            fg_color=(colors.glass_light, colors.glass_dark),
            border_color=(colors.border_light, colors.border_dark),
            button_color=(colors.accent_blue, colors.accent_blue),
            button_hover_color=(colors.accent_blue_hover, colors.accent_blue_hover),
            dropdown_fg_color=(colors.glass_light, colors.glass_dark),
            text_color=(colors.text_primary_light, colors.text_primary_dark)
        )
        self.currency_selector.pack(side="left", padx=(0, 12))
        
        # Add button
        add_button = self._create_professional_button(
            content,
            text="Add",
            command=self._add_selected_currency,
            style="primary",
            width=70
        )
        add_button.pack(side="left")
        
        return controls_frame
    
    def _create_controls_section(self):
        """Create main controls"""
        controls_card = self._create_glass_card(
            self.scroll_frame,
            height=140,
            glass_level=2
        )
        controls_card.grid(row=6, column=0, sticky="ew", pady=(0, 24))
        
        content = ctk.CTkFrame(controls_card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=20)
        
        # Title
        title = ctk.CTkLabel(
            content,
            text="🎛️ Data Controls",
            font=(config.FALLBACK_FONT, 18, "bold"),
            text_color=(colors.text_primary_light, colors.text_primary_dark)
        )
        title.pack(anchor="w", pady=(0, 12))
        
        # Controls
        controls_grid = ctk.CTkFrame(content, fg_color="transparent")
        controls_grid.pack(fill="x")
        
        # Buttons
        buttons_frame = ctk.CTkFrame(controls_grid, fg_color="transparent")
        buttons_frame.pack(anchor="w", pady=(0, 8))
        
        # Refresh
        refresh_btn = self._create_professional_button(
            buttons_frame,
            text="🔄 Refresh Now",
            command=self._manual_refresh,
            style="primary",
            width=140
        )
        refresh_btn.pack(side="left", padx=(0, 12))
        
        # Test API
        test_btn = self._create_professional_button(
            buttons_frame,
            text="🧪 Test API",
            command=self._test_api_connection,
            style="secondary",
            width=120
        )
        test_btn.pack(side="left", padx=(0, 12))
        
        # Auto-refresh
        self.auto_refresh_var = ctk.BooleanVar(value=True)
        auto_refresh_checkbox = ctk.CTkCheckBox(
            buttons_frame,
            text="Auto-refresh",
            variable=self.auto_refresh_var,
            command=self._toggle_auto_refresh,
            font=(config.FALLBACK_FONT, 13),
            text_color=(colors.text_primary_light, colors.text_primary_dark),
            fg_color=(colors.accent_blue, colors.accent_blue),
            hover_color=(colors.accent_blue_hover, colors.accent_blue_hover),
            border_color=(colors.border_light, colors.border_dark)
        )
        auto_refresh_checkbox.pack(side="left")
        
        # Last update
        self.last_update_label = ctk.CTkLabel(
            controls_grid,
            text=f"Last Update: {self.last_update}",
            font=(config.FALLBACK_FONT, 12),
            text_color=(colors.text_secondary_light, colors.text_secondary_dark)
        )
        self.last_update_label.pack(anchor="w")
    
    def _create_advanced_controls(self):
        """Create advanced visual controls - با مشکل تم‌ها حل شده!"""
        advanced_card = self._create_glass_card(
            self.scroll_frame,
            height=120,
            glass_level=2
        )
        advanced_card.grid(row=7, column=0, sticky="ew", pady=(0, 24))
        
        content = ctk.CTkFrame(advanced_card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=20)
        
        # Title
        title = ctk.CTkLabel(
            content,
            text="✨ Visual Effects (Fixed)",
            font=(config.FALLBACK_FONT, 18, "bold"),
            text_color=(colors.text_primary_light, colors.text_primary_dark)
        )
        title.pack(anchor="w", pady=(0, 12))
        
        # Effects buttons
        effects_frame = ctk.CTkFrame(content, fg_color="transparent")
        effects_frame.pack(anchor="w")
        
        # دکمه‌های تم با کنترل بهتر
        liquid_btn = self._create_professional_button(
            effects_frame,
            text="💧 Liquid Glass",
            command=lambda: self._apply_theme_with_feedback("liquid"),
            style="secondary",
            width=160
        )
        liquid_btn.pack(side="left", padx=(0, 12))
        
        vibrancy_btn = self._create_professional_button(
            effects_frame,
            text="🌟 Enhanced Vibrancy", 
            command=lambda: self._apply_theme_with_feedback("vibrancy"),
            style="secondary",
            width=160
        )
        vibrancy_btn.pack(side="left", padx=(0, 12))
        
        crystal_btn = self._create_professional_button(
            effects_frame,
            text="💎 Crystal Mode",
            command=lambda: self._apply_theme_with_feedback("crystal"),
            style="secondary",
            width=160
        )
        crystal_btn.pack(side="left")
    
    def _apply_theme_with_feedback(self, theme_type: str):
        """Apply theme with user feedback"""
        try:
            self._show_temporary_notification(f"🔄 Applying {theme_type.title()} theme...")
            
            # Apply theme based on type
            if theme_type == "liquid":
                self.effects_manager.apply_liquid_glass_effect()
            elif theme_type == "vibrancy":
                self.effects_manager.apply_vibrancy_effect()
            elif theme_type == "crystal":
                self.effects_manager.apply_crystal_mode()
            
            # Show success notification
            self.after(500, lambda: self._show_temporary_notification(
                f"✅ {theme_type.title()} theme applied successfully!"
            ))
            
            # Update effects status
            self.after(600, self._update_effects_status)
            
        except Exception as e:
            logger.error(f"Theme application failed: {e}")
            self._show_temporary_notification(f"❌ Failed to apply {theme_type} theme")
    
    def _update_effects_status(self):
        """Update effects status display"""
        try:
            if 'effects_status' in self.ui_elements:
                effect_info = self.effects_manager.get_current_effect_info()
                effect_name = effect_info['effect'].replace('_', ' ').title()
                
                self.ui_elements['effects_status']['status_label'].configure(
                    text=f"✨ {effect_name} • Active"
                )
        except Exception as e:
            logger.error(f"Effects status update failed: {e}")
    
    # ادامه متدهای کلاس مثل قبل...
    def _create_glass_card(self, parent, height: Optional[int] = None, 
                          glass_level: int = 1, **kwargs) -> ctk.CTkFrame:
        """Create glass card"""
        glass_colors = [
            (colors.glass_light, colors.glass_dark),
            (colors.glass_overlay_light, colors.glass_overlay_dark),
            (colors.highlight_light, colors.highlight_dark)
        ]
        
        fg_color = glass_colors[min(glass_level - 1, 2)]
        
        default_config = {
            'fg_color': fg_color,
            'corner_radius': 16,
            'border_width': 1,
            'border_color': (colors.border_light, colors.border_dark)
        }
        
        if height:
            default_config['height'] = height
        
        default_config.update(kwargs)
        return ctk.CTkFrame(parent, **default_config)
    
    def _create_professional_button(self, parent, text: str, command: Callable, 
                                  style: str = "primary", width: Optional[int] = None, 
                                  **kwargs) -> ctk.CTkButton:
        """Create professional button"""
        styles = {
            'primary': {
                'fg_color': (colors.accent_blue, colors.accent_blue),
                'hover_color': (colors.accent_blue_hover, colors.accent_blue_hover),
                'text_color': 'white',
                'border_width': 0
            },
            'secondary': {
                'fg_color': (colors.glass_overlay_light, colors.glass_overlay_dark),
                'hover_color': (colors.separator_light, colors.separator_dark),
                'text_color': (colors.text_primary_light, colors.text_primary_dark),
                'border_width': 1,
                'border_color': (colors.border_light, colors.border_dark)
            }
        }
        
        style_config = styles.get(style, styles['primary']).copy()
        style_config.update(kwargs)
        
        default_config = {
            'text': text,
            'command': command,
            'font': (config.FALLBACK_FONT, 13, "normal"),
            'corner_radius': 10,
            'height': 40
        }
        
        if width:
            default_config['width'] = width
        
        default_config.update(style_config)
        return ctk.CTkButton(parent, **default_config)
    
    def _create_currency_card(self, parent, currency_data: Dict, 
                            enhanced: bool = True) -> ctk.CTkFrame:
        """Create currency card"""
        card = self._create_glass_card(
            parent,
            width=config.CARD_WIDTH,
            height=config.CARD_HEIGHT,
            glass_level=2
        )
        
        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=18, pady=18)
        
        # Header
        header = ctk.CTkFrame(content, fg_color="transparent", height=40)
        header.pack(fill="x", pady=(0, 12))
        header.pack_propagate(False)
        
        # Symbol badge
        symbol_badge = ctk.CTkFrame(
            header,
            fg_color=(colors.accent_blue, colors.accent_blue),
            corner_radius=8,
            width=40,
            height=24
        )
        symbol_badge.pack(side="left", anchor="nw")
        
        symbol_text = currency_data.get('symbol', '')[:3]
        symbol_label = ctk.CTkLabel(
            symbol_badge,
            text=symbol_text,
            font=(config.FALLBACK_FONT, 10, "bold"),
            text_color="white"
        )
        symbol_label.place(relx=0.5, rely=0.5, anchor="center")
        
        # Currency name
        name_text = currency_data.get('name', 'Currency')
        if len(name_text) > 20:
            name_text = name_text[:17] + "..."
        
        name_label = ctk.CTkLabel(
            header,
            text=name_text,
            font=(config.FALLBACK_FONT, 14, "bold"),
            text_color=(colors.text_primary_light, colors.text_primary_dark),
            anchor="w"
        )
        name_label.pack(side="left", padx=(12, 0), fill="x", expand=True)
        
        # Price section
        price_section = ctk.CTkFrame(content, fg_color="transparent", height=50)
        price_section.pack(fill="x", pady=(0, 12))
        price_section.pack_propagate(False)
        
        # Format price
        price = currency_data.get('price', '0')
        price_text = self._format_price(price)
        
        price_label = ctk.CTkLabel(
            price_section,
            text=price_text,
            font=(config.FALLBACK_FONT, 20, "bold"),
            text_color=(colors.text_primary_light, colors.text_primary_dark),
            anchor="w"
        )
        price_label.pack(fill="x", pady=(0, 4))
        
        # Unit
        unit_text = currency_data.get('unit', '')
        unit_label = ctk.CTkLabel(
            price_section,
            text=unit_text,
            font=(config.FALLBACK_FONT, 11, "normal"),
            text_color=(colors.text_tertiary_light, colors.text_tertiary_dark),
            anchor="w"
        )
        unit_label.pack(fill="x")
        
        # Change indicator
        change_percent = currency_data.get('change_percent', 0)
        change_pill = self._create_change_indicator(content, change_percent)
        change_pill.pack(fill="x")
        
        return card
    
    def _format_price(self, price: str) -> str:
        """Format price intelligently"""
        try:
            price_float = float(price)
            
            if price_float >= 1_000_000:
                return f"{price_float/1_000_000:.2f}M"
            elif price_float >= 100_000:
                return f"{price_float:,.0f}"
            elif price_float >= 1_000:
                return f"{price_float:,.2f}"
            elif price_float >= 1:
                return f"{price_float:.4f}"
            else:
                return f"{price_float:.6f}"
                
        except (ValueError, TypeError):
            return str(price)[:12] + "..." if len(str(price)) > 12 else str(price)
    
    def _create_change_indicator(self, parent, change_percent) -> ctk.CTkFrame:
        """Create change indicator"""
        try:
            change_val = float(change_percent)
            
            if change_val > 0:
                bg_color = colors.accent_green
                text_color = "white"
                text = f"↗ +{change_val:.2f}%"
            elif change_val < 0:
                bg_color = colors.accent_red
                text_color = "white"
                text = f"↘ {change_val:.2f}%"
            else:
                bg_color = (colors.text_secondary_light, colors.text_secondary_dark)
                text_color = (colors.text_primary_light, colors.text_primary_dark)
                text = "— 0.00%"
                
        except (ValueError, TypeError):
            bg_color = (colors.text_secondary_light, colors.text_secondary_dark)
            text_color = (colors.text_primary_light, colors.text_primary_dark)
            text = "— N/A"
        
        pill = ctk.CTkFrame(
            parent,
            fg_color=bg_color,
            corner_radius=12,
            height=28
        )
        
        label = ctk.CTkLabel(
            pill,
            text=text,
            font=(config.FALLBACK_FONT, 12, "bold"),
            text_color=text_color
        )
        label.place(relx=0.5, rely=0.5, anchor="center")
        
        return pill
    
    def _load_saved_preferences(self):
        """Load saved preferences"""
        try:
            self.selected_currencies = db_manager.load_selected_currencies()
            logger.info(f"Loaded {len(self.selected_currencies)} saved currencies")
        except Exception as e:
            logger.error(f"Failed to load preferences: {e}")
    
    def _start_data_systems(self):
        """Start data management systems"""
        self._update_connection_status(ConnectionStatus.CONNECTING)
        self.executor.submit(self._initial_data_load)
        self._start_auto_refresh_system()
    
    def _initial_data_load(self):
        """Load initial data"""
        try:
            logger.info("Starting initial data load...")
            performance_monitor.record_api_call()
            
            # Try API
            data = self.api_manager.fetch_data_sync()
            
            if data:
                currencies = self.api_manager.process_currency_data(data)
                if currencies:
                    self.after(0, lambda: self._update_ui_with_data(currencies, ConnectionStatus.CONNECTED))
                    return
            
            # Fallback
            logger.info("Using fallback data...")
            fallback_data = self.api_manager.get_fallback_data()
            self.after(0, lambda: self._update_ui_with_data(fallback_data, ConnectionStatus.ERROR))
            
        except Exception as e:
            logger.error(f"Initial data load failed: {e}")
            performance_monitor.record_error()
            self.after(0, lambda: self._handle_data_load_error(str(e)))
    
    def _update_ui_with_data(self, currencies: Dict[str, Dict], status: ConnectionStatus):
        """Update UI with data"""
        try:
            self.currencies = currencies
            self.last_update = datetime.now().strftime("%H:%M:%S")
            
            self._update_connection_status(status)
            self._display_featured_currencies()
            self._display_portfolio_currencies()
            self._update_currency_selector()
            self._update_status_displays()
            
            performance_monitor.record_ui_update()
            logger.info(f"UI updated with {len(currencies)} currencies")
            
        except Exception as e:
            logger.error(f"UI update failed: {e}")
            performance_monitor.record_error()
    
    def _update_connection_status(self, status: ConnectionStatus, message: str = None):
        """Update connection status"""
        self.connection_status = status
        
        status_config = {
            ConnectionStatus.CONNECTED: {
                'color': colors.status_success,
                'message': message or f"🟢 Primary API Connected • {len(self.currencies)} currencies"
            },
            ConnectionStatus.CONNECTING: {
                'color': colors.status_info,
                'message': message or "🔵 Connecting to BRS API..."
            },
            ConnectionStatus.ERROR: {
                'color': colors.status_error,
                'message': message or "🔴 API failed • Using fallback data"
            }
        }
        
        config_data = status_config.get(status, status_config[ConnectionStatus.ERROR])
        
        if 'api_status' in self.ui_elements:
            self.ui_elements['api_status']['status_label'].configure(
                text=config_data['message'],
                text_color=config_data['color']
            )
    
    def _display_featured_currencies(self):
        """Display featured currencies"""
        # Clear existing
        for widget in self.featured_container.winfo_children():
            widget.destroy()
        
        # Select featured
        featured_symbols = self._select_featured_currencies()
        
        # Create cards
        for i, symbol in enumerate(featured_symbols[:config.GRID_COLUMNS]):
            if symbol in self.currencies:
                card = self._create_currency_card(
                    self.featured_container,
                    self.currencies[symbol],
                    enhanced=True
                )
                card.grid(
                    row=0, 
                    column=i, 
                    padx=config.CARD_PADDING, 
                    pady=config.CARD_PADDING, 
                    sticky="nsew"
                )
                self.selected_currencies.add(symbol)
    
    def _select_featured_currencies(self) -> List[str]:
        """Select featured currencies with Iranian focus"""
        # اولویت‌بندی ارزها با تمرکز بر بازار ایران
        priority = [
            'USD', 'EUR', 'GBP',  # ارزهای اصلی
            'BTC', 'ETH', 'BNB',  # کریپتوهای محبوب
            'SEKEH', 'GOLD',      # طلا و سکه
            'GERAM18', 'GERAM24', # طلای گرمی
            'AED', 'TRY', 'CNY'   # ارزهای منطقه‌ای
        ]
        
        available = list(self.currencies.keys())
        featured = []
        
        for symbol in priority:
            if symbol in self.currencies:
                featured.append(symbol)
                if len(featured) >= config.GRID_COLUMNS:
                    break
        
        # اگر هنوز جا مونده، از ارزهای موجود اضافه کن
        while len(featured) < config.GRID_COLUMNS and len(featured) < len(available):
            for symbol in available:
                if symbol not in featured:
                    featured.append(symbol)
                    if len(featured) >= config.GRID_COLUMNS:
                        break
        
        return featured
    
    def _display_portfolio_currencies(self):
        """Display portfolio currencies"""
        # Clear existing
        for widget in self.portfolio_container.winfo_children():
            widget.destroy()
        
        # Reset grid
        self.grid_position = {"row": 0, "col": 0}
        
        # Get portfolio currencies
        featured_symbols = self._select_featured_currencies()[:config.GRID_COLUMNS]
        portfolio_symbols = [
            symbol for symbol in self.selected_currencies
            if symbol not in featured_symbols and symbol in self.currencies
        ]
        
        # Display
        for symbol in portfolio_symbols:
            card = self._create_currency_card(
                self.portfolio_container,
                self.currencies[symbol],
                enhanced=True
            )
            card.grid(
                row=self.grid_position["row"],
                column=self.grid_position["col"],
                padx=config.CARD_PADDING,
                pady=config.CARD_PADDING,
                sticky="nsew"
            )
            
            self.grid_position["col"] += 1
            if self.grid_position["col"] >= config.GRID_COLUMNS:
                self.grid_position["col"] = 0
                self.grid_position["row"] += 1
    
    def _update_currency_selector(self):
        """Update currency selector"""
        try:
            available = []
            for symbol, data in self.currencies.items():
                if symbol not in self.selected_currencies:
                    available.append(f"{data.get('name', symbol)} ({symbol})")
            
            if not available:
                available = ["All currencies added! 🎉"]
            
            self.currency_selector.configure(values=sorted(available))
            if available and not available[0].startswith("All currencies"):
                self.currency_selector.set(available[0])
            
        except Exception as e:
            logger.error(f"Currency selector update failed: {e}")
    
    def _update_status_displays(self):
        """Update status displays"""
        try:
            # Data status
            if 'data_status' in self.ui_elements:
                quality = "Excellent" if self.connection_status == ConnectionStatus.CONNECTED else "Limited"
                source = "BRS API" if self.connection_status == ConnectionStatus.CONNECTED else "Fallback"
                self.ui_elements['data_status']['status_label'].configure(
                    text=f"📊 {quality} • {source} • {len(self.currencies)} pairs"
                )
            
            # Effects status
            self._update_effects_status()
            
            # Last update
            if hasattr(self, 'last_update_label'):
                self.last_update_label.configure(text=f"Last Update: {self.last_update}")
            
        except Exception as e:
            logger.error(f"Status display update failed: {e}")
    
    def _add_selected_currency(self):
        """Add selected currency"""
        try:
            selected = self.currency_selector.get()
            
            if selected.startswith("All currencies"):
                self._show_info_dialog(
                    "Portfolio Complete! 🎉",
                    "You've added all available currencies!"
                )
                return
            
            # Extract symbol
            if '(' in selected and ')' in selected:
                symbol = selected.split('(')[1].split(')')[0]
            else:
                symbol = None
                selected_name = selected.split(' (')[0]
                for s, data in self.currencies.items():
                    if data.get('name', '') == selected_name:
                        symbol = s
                        break
            
            if symbol and symbol in self.currencies and symbol not in self.selected_currencies:
                self.selected_currencies.add(symbol)
                self._display_portfolio_currencies()
                self._update_currency_selector()
                db_manager.save_selected_currencies(self.selected_currencies)
                
                currency_name = self.currencies[symbol].get('name', symbol)
                self._show_temporary_notification(f"✅ {currency_name} added!")
            
        except Exception as e:
            logger.error(f"Add currency failed: {e}")
    
    def _manual_refresh(self):
        """Manual refresh"""
        try:
            self._update_connection_status(ConnectionStatus.CONNECTING, "🔄 Refreshing...")
            self.executor.submit(self._perform_manual_refresh)
        except Exception as e:
            logger.error(f"Manual refresh failed: {e}")
    
    def _perform_manual_refresh(self):
        """Perform manual refresh"""
        try:
            performance_monitor.record_api_call()
            data = self.api_manager.fetch_data_sync()
            
            if data:
                currencies = self.api_manager.process_currency_data(data)
                if currencies:
                    self.after(0, lambda: self._handle_successful_refresh(currencies))
                    return
            
            self.after(0, lambda: self._handle_failed_refresh())
            
        except Exception as e:
            logger.error(f"Manual refresh failed: {e}")
            self.after(0, lambda: self._handle_failed_refresh(str(e)))
    
    def _handle_successful_refresh(self, currencies: Dict[str, Dict]):
        """Handle successful refresh"""
        self._update_ui_with_data(currencies, ConnectionStatus.CONNECTED)
        self._show_temporary_notification("🔄 Data refreshed successfully!")
    
    def _handle_failed_refresh(self, error_msg: str = None):
        """Handle failed refresh"""
        self._update_connection_status(ConnectionStatus.ERROR, "🔴 Refresh failed")
        self._show_warning_dialog("Refresh Failed", "Could not refresh data from API.")
        performance_monitor.record_error()
    
    def _test_api_connection(self):
        """Test API connection"""
        try:
            self._update_connection_status(ConnectionStatus.CONNECTING, "🧪 Testing BRS API...")
            self.executor.submit(self._perform_api_test)
        except Exception as e:
            logger.error(f"API test failed: {e}")
    
    def _perform_api_test(self):
        """Perform API test"""
        try:
            start_time = time.time()
            performance_monitor.record_api_call()
            
            data = self.api_manager.fetch_data_sync()
            end_time = time.time()
            
            response_time = end_time - start_time
            
            if data:
                currencies = self.api_manager.process_currency_data(data)
                success_msg = (
                    f"✅ BRS API Test Successful!\n\n"
                    f"Response Time: {response_time:.2f} seconds\n"
                    f"Currencies Found: {len(currencies)}\n"
                    f"Connection: Stable\n"
                    f"Source: Primary BRS API"
                )
                self.after(0, lambda: self._show_success_dialog("API Test", success_msg))
            else:
                error_msg = (
                    f"❌ BRS API Test Failed!\n\n"
                    f"Response Time: {response_time:.2f} seconds\n"
                    f"Connection: Failed\n"
                    f"Check your internet or API key"
                )
                self.after(0, lambda: self._show_error_dialog("API Test", error_msg))
            
        except Exception as e:
            error_msg = f"❌ API Test Error!\n\nException: {str(e)}"
            self.after(0, lambda: self._show_error_dialog("API Test", error_msg))
            performance_monitor.record_error()
    
    def _toggle_auto_refresh(self):
        """Toggle auto-refresh"""
        self.auto_refresh_active = self.auto_refresh_var.get()
        if self.auto_refresh_active:
            self._show_temporary_notification("🔄 Auto-refresh enabled")
        else:
            self._show_temporary_notification("⏸️ Auto-refresh disabled")
    
    def _start_auto_refresh_system(self):
        """Start auto-refresh system"""
        def auto_refresh_worker():
            while True:
                try:
                    time.sleep(config.AUTO_REFRESH_INTERVAL)
                    if self.auto_refresh_active:
                        self.after(0, self._auto_refresh_data)
                except Exception as e:
                    logger.error(f"Auto-refresh error: {e}")
                    time.sleep(60)
        
        threading.Thread(target=auto_refresh_worker, daemon=True).start()
        logger.info("Auto-refresh system started")
    
    def _auto_refresh_data(self):
        """Auto refresh data"""
        if not self.auto_refresh_active:
            return
        try:
            self.executor.submit(self._background_refresh_worker)
        except Exception as e:
            logger.error(f"Auto-refresh failed: {e}")
    
    def _background_refresh_worker(self):
        """Background refresh worker"""
        try:
            performance_monitor.record_api_call()
            data = self.api_manager.fetch_data_sync()
            
            if data:
                currencies = self.api_manager.process_currency_data(data)
                if currencies:
                    self.after(0, lambda: self._silent_update_ui(currencies))
        except Exception as e:
            logger.error(f"Background refresh failed: {e}")
    
    def _silent_update_ui(self, currencies: Dict[str, Dict]):
        """Silent UI update"""
        try:
            self.currencies = currencies
            self.last_update = datetime.now().strftime("%H:%M:%S")
            
            self._display_featured_currencies()
            self._display_portfolio_currencies()
            self._update_currency_selector()
            
            if hasattr(self, 'last_update_label'):
                self.last_update_label.configure(text=f"Last Update: {self.last_update}")
            
            performance_monitor.record_ui_update()
            logger.debug("Silent UI update completed")
            
        except Exception as e:
            logger.error(f"Silent UI update failed: {e}")
    
    def _show_temporary_notification(self, message: str, duration: int = 3000):
        """Show temporary notification"""
        try:
            notification = ctk.CTkFrame(
                self,
                fg_color=(colors.glass_overlay_light, colors.glass_overlay_dark),
                corner_radius=12,
                border_width=1,
                border_color=(colors.border_light, colors.border_dark)
            )
            
            notification.place(relx=0.95, rely=0.05, anchor="ne")
            
            content = ctk.CTkFrame(notification, fg_color="transparent")
            content.pack(fill="both", expand=True, padx=16, pady=12)
            
            message_label = ctk.CTkLabel(
                content,
                text=message,
                font=(config.FALLBACK_FONT, 13),
                text_color=(colors.text_primary_light, colors.text_primary_dark)
            )
            message_label.pack()
            
            self.after(duration, notification.destroy)
            
        except Exception as e:
            logger.error(f"Notification failed: {e}")
    
    def _show_info_dialog(self, title: str, message: str):
        """Show info dialog"""
        messagebox.showinfo(title, message)
    
    def _show_success_dialog(self, title: str, message: str):
        """Show success dialog"""
        messagebox.showinfo(title, message)
    
    def _show_warning_dialog(self, title: str, message: str):
        """Show warning dialog"""
        messagebox.showwarning(title, message)
    
    def _show_error_dialog(self, title: str, message: str):
        """Show error dialog"""
        messagebox.showerror(title, message)
    
    def _handle_data_load_error(self, error_msg: str):
        """Handle data load error"""
        self._update_connection_status(ConnectionStatus.ERROR, "🔴 Critical error")
        self._show_error_dialog("Data Load Error", f"Failed to load data: {error_msg}")
    
    def destroy(self):
        """Clean shutdown"""
        try:
            logger.info("Shutting down...")
            db_manager.save_selected_currencies(self.selected_currencies)
            self.executor.shutdown(wait=False)
            resource_manager.cleanup_resources()
            logger.info("Shutdown complete")
        except Exception as e:
            logger.error(f"Shutdown error: {e}")
        finally:
            super().destroy()

# ============================================================================
# SYSTEM DIAGNOSTICS
# ============================================================================

def run_system_diagnostics():
    """Run system diagnostics"""
    print("=" * 80)
    print(" 💎 LIQUID GLASS PRICE TRACKER - API & THEME FIXED")
    print("=" * 80)
    
    print(f"\n🖥️  SYSTEM INFORMATION")
    print(f"Operating System: {sys.platform.upper()}")
    print(f"Python Version: {sys.version.split()[0]}")
    print(f"Application Version: {config.APP_VERSION}")
    
    print(f"\n📦 DEPENDENCIES")
    
    try:
        import customtkinter
        print(f"✅ CustomTkinter: {customtkinter.__version__}")
    except Exception as e:
        print(f"❌ CustomTkinter: Not available")
    
    try:
        import requests
        print(f"✅ Requests: {requests.__version__}")
    except Exception as e:
        print(f"❌ Requests: Not available")
    
    try:
        import pyglet
        print(f"✅ Pyglet: {pyglet.version}")
    except Exception as e:
        print(f"❌ Pyglet: Not available")
    
    if IS_WINDOWS:
        if PYWINSTYLES_AVAILABLE:
            print(f"✅ PyWinStyles: Available (Theme switching fixed)")
        else:
            print(f"⚠️ PyWinStyles: Not available")
    else:
        print(f"ℹ️ PyWinStyles: Not needed ({sys.platform})")
    
    print(f"\n🌐 NETWORK CONNECTIVITY")
    try:
        response = requests.get("https://httpbin.org/status/200", timeout=5)
        print("✅ Internet Connection: Available")
    except Exception:
        print("❌ Internet Connection: Limited")
    
    print(f"\n🔗 API ENDPOINTS")
    print(f"Primary API: {config.PRIMARY_API_URL}")
    try:
        response = requests.head(config.PRIMARY_API_URL, timeout=10)
        print(f"✅ Primary BRS API: Reachable")
    except Exception:
        print(f"❌ Primary BRS API: Failed")
    
    print(f"\n✨ FIXED FEATURES")
    print("✅ Your Original BRS API (Priority #1)")
    print("✅ Multi-API Fallback System")
    print("✅ Theme Switching (Fixed)")
    print("✅ Enhanced Currency Support")
    print("✅ Iranian Market Focus")
    print("✅ Professional Error Handling")
    
    print(f"\n🚀 LAUNCHING APPLICATION...")
    print("=" * 80 + "\n")

def main():
    """Main entry point"""
    try:
        run_system_diagnostics()
        
        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")
        
        logger.info("Initializing Liquid Glass Price Tracker...")
        
        app = LiquidGlassPriceTracker()
        
        logger.info("🎉 Application started successfully!")
        app.mainloop()
        
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Critical error: {e}")
        
        try:
            import tkinter.messagebox as mb
            mb.showerror(
                "Critical Error",
                f"Application failed:\n\n{str(e)}\n\n"
                f"Check console for details."
            )
        except:
            pass
        
        print(f"\n❌ CRITICAL ERROR: {e}")
        print("\n🔧 TROUBLESHOOTING:")
        print("• Check BRS API key validity")
        print("• Verify internet connection")
        print("• Check firewall settings")
        
        import traceback
        traceback.print_exc()
    
    finally:
        logger.info("Application session ended")

if __name__ == "__main__":
    main()
