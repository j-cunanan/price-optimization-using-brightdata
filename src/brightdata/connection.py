"""
Bright Data connection management.
"""

import os
import zipfile
import tempfile
from typing import Optional
from dataclasses import dataclass
from selenium.webdriver import Remote
from selenium.webdriver.chrome.options import Options as ChromeOptions
from loguru import logger


@dataclass
class BrightDataConfig:
    """Configuration for Bright Data API."""
    zone: str = "datacenter"  # datacenter, residential, mobile
    username: str = ""
    password: str = ""
    session_id: Optional[str] = None
    
    @classmethod
    def from_env(cls) -> "BrightDataConfig":
        """Create config from environment variables."""
        return cls(
            zone=os.getenv("BRIGHT_DATA_ZONE", "datacenter"),
            username=os.getenv("BRIGHT_DATA_USERNAME", ""),
            password=os.getenv("BRIGHT_DATA_PASSWORD", ""),
            session_id=os.getenv("BRIGHT_DATA_SESSION_ID")
        )


class BrightDataConnection:
    """Manages connection to Bright Data proxy."""
    
    def __init__(self, config: BrightDataConfig):
        self.config = config
        self.driver: Optional[Remote] = None
        
        # Bright Data proxy settings
        self.proxy_host = "brd.superproxy.io"
        self.proxy_port = 22225
        
        # Build proxy authentication
        session_suffix = f"-session-{self.config.session_id}" if self.config.session_id else ""
        self.proxy_user = f"{self.config.username}-zone-{self.config.zone}{session_suffix}"
        self.proxy_password = self.config.password
    
    def _create_proxy_auth_extension(self) -> str:
        """Create a Chrome extension for proxy authentication."""
        
        # Chrome extension manifest
        manifest_json = """
        {
            "version": "1.0.0",
            "manifest_version": 2,
            "name": "Chrome Proxy Auth",
            "permissions": [
                "proxy",
                "tabs",
                "unlimitedStorage",
                "storage",
                "<all_urls>",
                "webRequest",
                "webRequestBlocking"
            ],
            "background": {
                "scripts": ["background.js"]
            },
            "minimum_chrome_version":"22.0.0"
        }
        """
        
        # Background script for proxy authentication
        background_js = f"""
        var config = {{
            mode: "fixed_servers",
            rules: {{
                singleProxy: {{
                    scheme: "http",
                    host: "{self.proxy_host}",
                    port: parseInt({self.proxy_port})
                }},
                bypassList: ["localhost"]
            }}
        }};
        
        chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});
        
        function callbackFn(details) {{
            return {{
                authCredentials: {{
                    username: "{self.proxy_user}",
                    password: "{self.proxy_password}"
                }}
            }};
        }}
        
        chrome.webRequest.onAuthRequired.addListener(
            callbackFn,
            {{urls: ["<all_urls>"]}},
            ['blocking']
        );
        """
        
        # Create temporary directory and extension files
        temp_dir = tempfile.mkdtemp()
        extension_dir = os.path.join(temp_dir, "proxy_auth_extension")
        os.makedirs(extension_dir)
        
        # Write manifest
        with open(os.path.join(extension_dir, "manifest.json"), "w") as f:
            f.write(manifest_json)
        
        # Write background script
        with open(os.path.join(extension_dir, "background.js"), "w") as f:
            f.write(background_js)
        
        # Create ZIP file
        extension_path = os.path.join(temp_dir, "proxy_auth.zip")
        with zipfile.ZipFile(extension_path, 'w') as zipf:
            zipf.write(os.path.join(extension_dir, "manifest.json"), "manifest.json")
            zipf.write(os.path.join(extension_dir, "background.js"), "background.js")
        
        return extension_path
    
    def connect(self) -> Remote:
        """Establish connection to Bright Data."""
        try:
            # Create proxy authentication extension
            extension_path = self._create_proxy_auth_extension()
            
            # Chrome options
            chrome_options = ChromeOptions()
            chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_argument("--disable-web-security")
            chrome_options.add_argument("--allow-running-insecure-content")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            # Add the proxy authentication extension
            chrome_options.add_extension(extension_path)
            
            # Create driver
            from selenium import webdriver
            self.driver = webdriver.Chrome(options=chrome_options)
            
            # Set user agent to look more natural
            self.driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            
            # Add stealth properties
            self.driver.execute_script("""
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['ja-JP', 'ja', 'en-US', 'en']
                });
            """)
            
            logger.info("Connected to Bright Data proxy with authentication extension")
            return self.driver
            
        except Exception as e:
            logger.error(f"Failed to connect to Bright Data: {e}")
            raise
    
    def disconnect(self) -> None:
        """Close Bright Data connection."""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Disconnected from Bright Data")
            except Exception as e:
                logger.warning(f"Error disconnecting from Bright Data: {e}")
            finally:
                self.driver = None
    
    def __enter__(self):
        """Context manager entry."""
        return self.connect()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()


async def test_brightdata_connection(config: Optional[BrightDataConfig] = None) -> bool:
    """Test Bright Data connection by visiting a test page."""
    if config is None:
        config = BrightDataConfig.from_env()
    
    if not config.username or not config.password:
        logger.error("Bright Data credentials not provided")
        return False
    
    connection = BrightDataConnection(config)
    
    try:
        with connection as driver:
            # Test with a simple page first
            test_url = "https://www.amazon.co.jp"
            logger.info(f"Testing Bright Data connection with {test_url}")
            
            driver.get(test_url)
            
            # Wait a moment for page to load
            import time
            time.sleep(3)
            
            # Get page content
            page_source = driver.page_source
            logger.info(f"Test successful. Page content length: {len(page_source)}")
            
            # Check if we got actual content
            if len(page_source) > 1000 and ("amazon" in page_source.lower() or "アマゾン" in page_source):
                logger.info("Proxy connection verified - Amazon page loaded successfully")
                return True
            else:
                logger.warning("Page loaded but content seems incomplete")
                return False
            
    except Exception as e:
        logger.error(f"Bright Data connection test failed: {e}")
        return False
