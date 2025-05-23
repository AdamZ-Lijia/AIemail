# config.py
import os
from pathlib import Path

# Load .env if present
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path)
    except ImportError:
        for line in env_path.read_text().splitlines():
            if line.strip().startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip())

# IMAP (Gmail) configuration
IMAP_HOST = os.getenv("IMAP_HOST")
IMAP_USER = os.getenv("IMAP_USER")
IMAP_PASS = os.getenv("IMAP_PASS")
PROCESSED_CAT = os.getenv("PROCESSED_CAT", "Processed")

# Reporting feature toggle and recipient
REPORT_ENABLED = os.getenv("REPORT_ENABLED", "False").lower() in ("1", "true", "yes")
print("[DEBUG] config REPORT_ENABLED =", REPORT_ENABLED)

REPORT_TO      = os.getenv("REPORT_TO", "")

# SMTP configuration for sending reports
SMTP_HOST      = os.getenv("SMTP_HOST", "")
SMTP_PORT      = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER      = os.getenv("SMTP_USER", "")
SMTP_PASS      = os.getenv("SMTP_PASS", "")

# iCloud mail configuration
ICLOUD_ENABLED = os.getenv("ICLOUD_ENABLED", "False").lower() in ("1", "true", "yes")
ICLOUD_TO      = os.getenv("ICLOUD_TO", "")
ICLOUD_HOST    = os.getenv("ICLOUD_HOST", "smtp.mail.me.com")
ICLOUD_PORT    = int(os.getenv("ICLOUD_PORT", "587"))
ICLOUD_USER    = os.getenv("ICLOUD_USER", "")
ICLOUD_PASS    = os.getenv("ICLOUD_PASS", "")

# Try to load working model name from working_api.txt
working_model_path = Path(__file__).parent / 'working_api.txt'
working_model = None
if working_model_path.exists():
    try:
        with open(working_model_path, 'r') as f:
            for line in f:
                if line.startswith('WORKING_MODEL='):
                    working_model = line.split('=', 1)[1].strip()
                    break
    except:
        pass

# Ollama configuration
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "127.0.0.1")  # Use specific IP instead of localhost
OLLAMA_PORT = int(os.getenv("OLLAMA_PORT", "11434"))  # Use default port 11434
# Fix Ollama API URL - use the correct endpoint for the current Ollama version
OLLAMA_URL  = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/generate"  # Use /api/generate path
# Model name priority: environment variable > working_api.txt > default value
MODEL_NAME  = os.getenv("MODEL_NAME", working_model or "mistral:latest")  # Use a verified available model

# Label mapping (main categories)
MAIN_CATS = [
    "Work", "Personal", "Transaction", "Promotion", "Security", "Update", "LowPriority", "Opportunities",
]
LABEL_MAP = {cat: cat for cat in MAIN_CATS}
LABEL_MAP[PROCESSED_CAT] = PROCESSED_CAT

# Used for cleanup
OLD_LABELS = list(LABEL_MAP.values())

# Used by classification_utils
CONTENT_CATS = list(LABEL_MAP.keys())

# Validate critical settings
_missing = [v for v in ("IMAP_HOST", "IMAP_USER", "IMAP_PASS") if not globals().get(v)]
if _missing:
    raise RuntimeError(f"Missing required config vars in .env: {', '.join(_missing)}")

CATEGORY_PREFIX = {
    "Work": "【工作】",
    "Personal": "【私人】",
    "Transaction": "【交易】",
    "Promotion": "【推广】",
    "Security": "【安全】",
    "Update": "【更新】",
    "ImportantUser": "【重要】",
    "Opportunities": "【机会】"
}

# 标签映射（可与 Gmail label 对应）
LABEL_MAP = {cat: cat for cat in MAIN_CATS}
PROCESSED_CAT = os.getenv("PROCESSED_CAT", "Processed")
LABEL_MAP[PROCESSED_CAT] = PROCESSED_CAT

# 导出用于分类模块
CONTENT_CATS = MAIN_CATS

EXCLUDED_CATEGORIES = {'LowPriority', 'Promotion'}  # 可配置或放入 config.py
