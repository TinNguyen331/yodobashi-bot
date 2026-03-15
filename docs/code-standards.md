# Code Standards

## Ngôn ngữ & Style

- **Python 3.x** với type hints cho function signatures
- **Class-based** cho các module chính (HttpSession, ProductHandler, etc.)
- **Function-based** cho orchestration logic (main.py)
- Docstrings cho classes và public methods
- Comments bằng tiếng Anh trong code, tiếng Việt trong config

## Cấu trúc project

```
yodobashi-bot-fast/
├── main.py              # Entry point + orchestration (không logic business)
├── bot/                 # Core modules
│   ├── __init__.py
│   ├── http_session.py  # HTTP layer
│   ├── product_handler.py  # Product logic
│   ├── checkout_handler.py # Checkout logic
│   ├── login_handler.py    # Auth logic
│   └── utils.py            # Shared utilities
├── config.yaml          # User config (gitignored)
├── config.example.yaml  # Config template
├── logs/                # Runtime logs
├── session/             # Persistent sessions
└── docs/                # Documentation
```

## Naming Conventions

| Type | Convention | Example |
|------|-----------|---------|
| Files | snake_case | `product_handler.py` |
| Classes | PascalCase | `CheckoutHandler` |
| Functions | snake_case | `is_product_available()` |
| Constants | UPPER_SNAKE | `BASE_URL`, `ORDER_URL` |
| Private methods | _prefix | `_click_proceed()` |
| Config keys | snake_case | `check_interval` |

## Error Handling

- `try/except` wrap cho tất cả HTTP requests và browser actions
- Log error message + context (URL, step number)
- Screenshot on error (checkout flow)
- Return `bool` cho success/failure
- Không raise exception ra ngoài module

## Logging

- Dùng `loguru` thay `logging` standard
- Log levels:
  - `DEBUG` — HTTP request/response details (file only)
  - `INFO` — Step progress, status updates
  - `SUCCESS` — Key milestones (login, add to cart, purchase)
  - `WARNING` — Non-critical issues, dry run stops
  - `ERROR` — Failures that affect flow
- Tag format: `[P{index}]` cho mỗi product thread
- Timestamp format: `HH:MM:SS` (console), `YYYY-MM-DD HH:MM:SS` (file)

## Configuration

- YAML format cho readability
- `config.example.yaml` template với comments giải thích
- `config.yaml` cho real data (gitignored)
- Default values trong code cho optional fields
- Validate required fields sớm (fail fast)

## Testing

- CLI test commands: `--test-login`, `--test-search`, `--test-checkout`
- `--test-checkout` force `dry_run: true`
- `--run-now` override tất cả products sang listening mode
- Không có unit tests framework (test thủ công qua CLI)

## Dependencies

- Pin major versions trong `requirements.txt`
- curl_cffi cho HTTP (không dùng requests/urllib)
- BeautifulSoup + lxml cho HTML parsing
- Playwright cho browser automation
- Loguru cho logging
- PyYAML cho config

## Git

- `.gitignore` cover: `config.yaml`, `session/`, `logs/`, `venv/`, `__pycache__/`
- Không commit credentials, cookies, logs
- `config.example.yaml` là template duy nhất được commit
