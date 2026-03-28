# Code Standards

## Language & Style

- **Python 3.x** with type hints on function signatures (PEP 484)
- **Class-based** for core modules (HttpSession, ProductHandler, CheckoutHandler, LoginHandler)
- **Function-based** for orchestration logic (main.py)
- Docstrings for classes and public methods
- Comments in English in code; Vietnamese in config/docs is OK

## Project Structure

```
yodobashi-bot/
├── main.py                 # Entry point, CLI, orchestrator (no business logic)
├── bot/                    # Core modules
│   ├── __init__.py
│   ├── http_session.py     # HTTP layer (curl_cffi + Chrome TLS)
│   ├── product_handler.py  # Product search & availability detection
│   ├── checkout_handler.py # Playwright checkout automation
│   ├── login_handler.py    # HTTP & checkout authentication
│   └── utils.py            # Config, logging, helpers
├── config.yaml             # User config (gitignored, credentials)
├── config.example.yaml     # Config template with comments
├── requirements.txt        # Dependencies (pinned versions)
├── logs/                   # Runtime logs + screenshots (auto-created)
├── session/                # Persistent cookies (auto-created)
└── docs/                   # Documentation
```

## Naming Conventions

| Type | Convention | Example |
|------|-----------|---------|
| Files | snake_case | `product_handler.py` |
| Classes | PascalCase | `CheckoutHandler` |
| Functions | snake_case | `is_product_available()` |
| Constants | UPPER_SNAKE | `BASE_URL`, `ORDER_URL` |
| Private methods | `_prefix` | `_click_proceed()` |
| Config keys | snake_case | `check_interval` |
| Variables | snake_case | `daily_count`, `current_soup` |

## Error Handling

- Wrap all HTTP requests & browser actions in `try/except`
- Log error message with context (URL, step, exception)
- Screenshot on error in checkout flow
- Return `bool` for success/failure; avoid raising exceptions from module internals
- Use loguru for structured error logging with stack traces

## Logging

- Use `loguru` instead of standard `logging` library
- Log levels:
  - `DEBUG` — HTTP request/response details (file only, not console)
  - `INFO` — Step progress, general status updates
  - `SUCCESS` — Key milestones (login OK, add to cart OK, purchase OK)
  - `WARNING` — Non-critical issues, dry-run stop
  - `ERROR` — Failures that affect flow, exceptions
- Per-product thread tag: `[P{index}]` prefix (e.g., `[P0]`, `[P1]`)
- Timestamp: `HH:MM:SS` (console), `YYYY-MM-DD HH:MM:SS` (file logs)

## Configuration

- YAML format for readability & simplicity
- `config.example.yaml` template with inline comments explaining each field
- `config.yaml` for actual credentials (gitignored, never committed)
- Default values in code for optional config fields
- Validate required fields early in `load_config()` (fail fast principle)
- Support custom config via `--config path` CLI argument

## Testing

Manual CLI testing via commands:
- `--test-login` — Test Playwright login (opens browser)
- `--test-search` — Test HTTP search (prints first result)
- `--test-checkout` — Test full checkout (dry-run, no purchase)
- `--run-now` — Override all products to listening mode (no wait)
- No unit test framework; integration tests via CLI

## Dependencies

- Pin **major versions only** in `requirements.txt` (e.g., `>=0.7.0` not `==0.7.1`)
- **curl_cffi** for HTTP with TLS fingerprint (not requests/urllib3)
- **BeautifulSoup4** + **lxml** for HTML/XML parsing (lxml as backend)
- **Playwright** for browser automation (Chromium only)
- **loguru** for structured logging (not standard logging)
- **PyYAML** for YAML config parsing
- apscheduler installed but not currently used; OK to keep or remove

## Git & Version Control

- `.gitignore` covers: `config.yaml`, `session/`, `logs/`, `venv/`, `__pycache__/`, `*.pyc`
- Never commit: credentials, cookies, logs, screenshots, local config
- `config.example.yaml` is the ONLY config file committed; user must copy & customize
- Use `.gitignore` to prevent accidental commits of sensitive data
