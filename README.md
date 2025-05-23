# AI Email Classifier and Forwarder (Ollama Local LLM, IMAP, Gmail)

> **Note:** This project was fully developed using AI tools (ChatGPT, Cursor) by a non-programmer. All code was generated via natural language prompts. Please excuse any non-standard coding practices.

## Overview

This project is an intelligent, automated email classification and forwarding system.  
It uses local LLMs via Ollama, integrates with Gmail (IMAP + Gmail API), and supports customizable rules for email labeling, auto-forwarding, and tray control on Windows.

## Features

- **Local LLM Email Classification:**  
  Categorizes emails into Work, Personal, Transaction, Promotion, Security, Update, Opportunities, and LowPriority using Ollama and local models (Mistral, Llama, etc.).
- **IMAP/Gmail API Integration:**  
  Robust mailbox access, label management, and forwarding with custom subject prefix.
- **Automated Labeling & Deduplication:**  
  Each message is labeled and processed only once.
- **Windows Tray App:**  
  Background service with tray icon for pause/resume/exit.
- **iCloud Support:**  
  Uses Gmail API (not SMTP) for forwarding and custom subject prefixing.
- **Offline/Local-First:**  
  No external/paid AI APIs; all processing is local.
- **Logging:**  
  Detailed logs for debugging and status inspection.

## Quick Start

1. **Clone the repo and install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
2. **Fill out `.env`** with your Gmail/SMTP/iCloud info.
3. **Place your Gmail API `credentials.json`** in the project root.
4. **Start Ollama** and load your preferred local LLM model.
5. **Run the main service:**
   ```bash
   python launcher_old.py
   ```
6. **(Optional) Launch the tray app:**
   ```bash
   pythonw aiemail_tray.pyw
   ```

## Configuration

- All credentials and settings are managed via `.env`.
- For advanced category mappings and label rules, edit `config.py`.

## Requirements

- Python 3.8+
- Ollama (local LLM server, e.g. Mistral, Llama)
- Gmail (IMAP enabled, API credentials: `credentials.json`)
- IMAPClient, google-api-python-client, google-auth-oauthlib
- Windows (for tray app; core logic is cross-platform)
- (Optional) iCloud or other SMTP-capable email for forwarding

## Key Files

- `config.py` — Configuration and label/category definitions
- `classification_utils.py` — LLM prompt and rule-based fallback
- `ollama_utils.py` — Ollama process control
- `gmailauth.py` — Gmail API OAuth
- `gmail_utils.py` — Gmail label helpers
- `launcher_old.py` — Main daemon: polling, IMAP/Gmail API logic, forwarding, batch handling, DB
- `main.py` — Batch classification/labelling
- `aiemail_tray.pyw` — Windows tray controller
- `delete.py` — Cleanup script for old Gmail labels

## Limitations

- No web UI (CLI/tray/logfile only)
- Gmail-specific features; other providers may need adaptation
- Tray app is Windows-only
- Limited error recovery (manual restart may be needed)
- No real-time notification or webhook
- Email reply automation not implemented

## License

MIT License (see LICENSE).

---



