#!/usr/bin/env python3
"""AI4Science wizard — настройка .env при первой установке.

Спрашивает ключ, адрес (ENDPOINT) и модель OpenAI-совместимого шлюза,
записывает .env в корень репозитория. Только стандартная библиотека.

Неинтерактивный режим (CI, скрипты): заданы переменные окружения
KEY и ENDPOINT, а stdin не терминал или
AI4SCIENCE_WIZARD_NONINTERACTIVE=1 → .env пишется без вопросов.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass

REPO = Path(__file__).resolve().parent.parent
ENV_FILE = REPO / ".env"

GREEN, YELLOW, BOLD, RESET = "\033[0;32m", "\033[0;33m", "\033[1m", "\033[0m"
DEFAULT_MODEL = "ai-pro"
DEFAULT_LEAN_URL = "https://scilibai.ru/grag"

MODELS = [
    ("ai-pro", "ai-pro — модель по умолчанию. Рекомендуется."),
    ("samcs-gpu/local-agent", "local-agent — альтернатива для сравнения."),
]


def banner() -> None:
    print(f"""
  ─── AI4Science wizard ───────────────────────────────────────
    Настройка .env: OpenAI-совместимый шлюз, модель, Lean checker
  ─────────────────────────────────────────────────────────────
""")


def ask(label: str, default: str | None = None, secret: bool = False) -> str:
    hint = f" [{default}]" if default and not secret else ""
    prompt = f"  {label}{hint}: "
    try:
        if secret:
            import getpass
            val = getpass.getpass(prompt)
        else:
            val = input(prompt)
    except (EOFError, KeyboardInterrupt):
        print("\nОтменено.")
        sys.exit(1)
    val = val.strip()
    return default if (not val and default is not None) else val


def ask_choice(label: str, options: list[tuple[str, str]], default: int = 0) -> str:
    print(f"\n  {BOLD}{label}{RESET}")
    for i, (key, desc) in enumerate(options, 1):
        marker = " (по умолчанию)" if i - 1 == default else ""
        print(f"    [{i}] {key}{marker}\n        {desc}")
    while True:
        raw = ask("Номер", default=str(default + 1))
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                return options[idx][0]
        except ValueError:
            pass
        print(f"  {YELLOW}Введи число от 1 до {len(options)}.{RESET}")


def write_env(api_key: str, endpoint: str, model: str, lean_url: str = DEFAULT_LEAN_URL, brave: str = "") -> None:
    lines = [
        "# AI4Science .env — сгенерировано cli/wizard.py. Не коммитить.",
        "",
        "# === бекенд инференса (OpenAI-совместимый шлюз) ===",
        f"KEY={api_key}",
        f"ENDPOINT={endpoint}",
        f"MODEL={model}",
        "PLANNER_MODEL=off",
        "",
        "# === Lean checker ===",
        f"LEAN_CHECKER_URL={lean_url}",
        "",
        "# === Необязательные настройки ===",
        f"BRAVE_API_KEY={brave}" if brave else "# BRAVE_API_KEY=            # поиск через Brave вместо DuckDuckGo",
        "# GOOSE_CONTEXT_LIMIT=128000",
        "",
    ]
    ENV_FILE.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    env_key = os.environ.get("KEY", "")
    env_endpoint = os.environ.get("ENDPOINT", "")
    non_interactive = bool(env_key and env_endpoint) and (
        os.environ.get("AI4SCIENCE_WIZARD_NONINTERACTIVE") == "1" or not sys.stdin.isatty()
    )
    if non_interactive:
        write_env(env_key, env_endpoint,
                  os.environ.get("MODEL", DEFAULT_MODEL),
                  os.environ.get("LEAN_CHECKER_URL", DEFAULT_LEAN_URL),
                  os.environ.get("BRAVE_API_KEY", ""))
        print(f"[ok] .env записан из переменных окружения: {ENV_FILE}")
        return 0

    banner()
    if ENV_FILE.exists():
        print(f"  {YELLOW}[warn]{RESET} {ENV_FILE} уже существует.")
        if ask("Перезаписать? (y/N)", default="N").lower() not in ("y", "yes", "д", "да"):
            print("  Оставляю существующий .env без изменений.")
            return 0

    print("  Ключ и адрес (ENDPOINT) OpenAI-совместимого шлюза выдаются на курсе.")
    print()
    api_key = ask("KEY", secret=True)
    if len(api_key) < 10:
        print(f"  {YELLOW}Ключ выглядит коротким. Продолжаю; doctor это покажет.{RESET}")
    endpoint = ask("ENDPOINT (вида https://.../v1)")
    if endpoint and not endpoint.startswith("http"):
        print(f"  {YELLOW}ENDPOINT обычно начинается с 'http(s)://'. Продолжаю.{RESET}")
    model = ask_choice("Модель по умолчанию", MODELS, default=0)
    print()
    print("  Lean checker: по умолчанию используется удалённый сервис курса.")
    print("  Для локального варианта: http://localhost:8888 и ./setup.sh --with-lean-local.")
    lean_url = ask("LEAN_CHECKER_URL", default=DEFAULT_LEAN_URL)
    brave = ask("BRAVE_API_KEY (Enter — пропустить, будет DuckDuckGo)", default="")
    write_env(api_key, endpoint, model, lean_url, brave)
    print()
    print(f"  {GREEN}[ok]{RESET} .env записан: {ENV_FILE}")
    print(f"  Модель: {BOLD}{model}{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
