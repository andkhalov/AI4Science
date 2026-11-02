# AI4Science

![CI](https://github.com/andkhalov/AI4Science/actions/workflows/test.yml/badge.svg)
![Windows](https://img.shields.io/badge/Windows-10%2F11-brightgreen)
![macOS](https://img.shields.io/badge/macOS-supported-brightgreen)
![Linux](https://img.shields.io/badge/Linux-supported-brightgreen)
![License](https://img.shields.io/badge/license-MIT-blue)

Агент создан для факультатива «ИИ для математики» (сопровождение ОКТЧ),
МФТИ, 2026. Авторы: А. П. Халов, О. М. Атаева — ФИЦ ИУ РАН, МФТИ.
Эта ветка (`MIPT`) — параллельная установка курсового агента AI4Science с
другим бекендом инференса; с основной веткой не объединяется.

AI4Science — открытая обёртка над агентом [Goose](https://github.com/aaif-goose/goose)
с инференсом через произвольный OpenAI-совместимый шлюз (`ENDPOINT` в `.env`).
Агент работает в папке проекта пользователя: выполняет команды, пишет и
запускает код, читает PDF, ищет в сети, проверяет доказательства на Lean 4 и
ищет леммы в Mathlib. Инструменты подключены через один MCP-сервер.

Команда этой установки — `ai4math_mipt` (отдельный системный алиас, чтобы не
конфликтовать с `ai4science` из основной ветки). Удаление без следов в
системе — в разделе [«Удаление»](#удаление).

---

## Установка

Нужны Python 3.10 или новее и git. Ключ, адрес (`ENDPOINT`) и модель
OpenAI-совместимого шлюза выдаются на факультативе.

### Windows 10/11

```powershell
git clone https://github.com/andkhalov/AI4Science.git
cd AI4Science
setup.bat
```

`setup.bat` находит Python (`python` или `py -3`), проверяет git, создаёт
`.venv`, ставит зависимости, скачивает Goose в `.tools\`, запускает мастер
настройки `.env`, добавляет папку `bin` в пользовательский PATH и выполняет
проверку `doctor`. Повторный запуск безопасен.

После установки откройте новый терминал:

```powershell
ai4math_mipt                     # интерактивная сессия
ai4math_mipt run "промпт"        # одна задача и выход
ai4math_mipt doctor              # проверка окружения
```

Без изменения PATH: `setup.bat --no-path`, запуск — `bin\ai4math_mipt.bat`.

Если Python не установлен: <https://www.python.org/downloads/windows/>
(отметить «Add python.exe to PATH») или `winget install -e --id Python.Python.3.12`.
Git: <https://git-scm.com/download/win> или `winget install -e --id Git.Git`.

### Windows: запасной путь через WSL2

Если установка в Windows не завершилась, `setup.bat` выводит этот вариант.

```powershell
wsl --install -d Ubuntu
```

Затем в терминале Ubuntu — команды для Linux из следующего раздела.

### macOS и Linux

```bash
git clone https://github.com/andkhalov/AI4Science.git && cd AI4Science && ./setup.sh
```

На Debian/Ubuntu `setup.sh` сам доставляет `bzip2`, `libgomp1` и
`python3-venv`, если есть права root или sudo без пароля. Команда
`ai4math_mipt` создаётся как symlink в `~/.local/bin`; эта папка должна быть в
PATH.

### Ключ шлюза

Мастер `cli/wizard.py` спрашивает ключ, адрес (`ENDPOINT`) и модель по
умолчанию и записывает `.env`. Для автоматической установки достаточно
задать переменные окружения до запуска установщика:

```bash
export KEY=...
export ENDPOINT=https://.../v1
./setup.sh
```

Шаблон всех параметров — `.env.example`. Файл `.env` не коммитится.

---

## Команды

| Команда | Действие |
|---|---|
| `ai4math_mipt` | интерактивная сессия |
| `ai4math_mipt run "<промпт>"` | одна задача, вывод в консоль, выход |
| `ai4math_mipt models` | модели, их алиасы и окна контекста |
| `ai4math_mipt doctor` | проверка: ключ, Goose, `.venv`, MCP-сервер, Lean checker, бюджет |
| `ai4math_mipt --help` | справка |

| Флаг | Значение |
|---|---|
| `-m <алиас или slug>` | модель на эту сессию |
| `--mode smart_approve` | по умолчанию в сессии: чтение без подтверждения, запись и выполнение команд — с подтверждением |
| `--mode auto` | по умолчанию в `run`: все вызовы инструментов без подтверждения |
| `--mode approve` | подтверждение каждого вызова инструмента |
| `--mode chat` | только диалог, без инструментов |
| `--no-lean` | без инструментов Lean |

### Команды в сессии

Вводятся в строке запроса. Полный список выводит `/help`.

| Команда | Действие |
|---|---|
| `/model` | показать текущую модель |
| `/model <алиас>` | сменить модель; история сессии сохраняется: `/model qwen235`, `/model deepseek` |
| `/status` | модель, режим, расход токенов, заполнение контекста |
| `/mode <режим>` | `auto`, `smart_approve`, `approve`, `chat` |
| `/plan <задача>` | план через модель планирования (`PLANNER_MODEL`; по умолчанию `off`); `/endplan` — выход из режима плана |
| `/compact` | сжать историю сессии |
| `/clear` | очистить историю |
| `/new` | новая сессия в том же процессе |
| `/skills`, `/prompts` | навыки и промпты расширений |
| `/r` | показывать параметры вызовов инструментов полностью |
| `/exit` | выход; Ctrl+C на пустой строке — то же |

### Модели

| Алиас | Id модели у шлюза | Окно контекста | Назначение |
|---|---|---|---|
| `ai-pro` | `ai-pro` | 1M | модель по умолчанию |
| `local-agent` | `samcs-gpu/local-agent` | 1M | альтернатива для сравнения |

Список моделей ограничен тем, что реально отдаёт `GET {ENDPOINT}/models` для
ключа из `.env`; тот же список печатает `ai4math_mipt models`.

### Смена модели

- По умолчанию — `MODEL` в `.env`.
- На одну сессию — флаг при запуске: `ai4math_mipt -m local-agent`.
- Внутри сессии — `/model local-agent`. История сохраняется, следующий ответ
  даёт новая модель; `/model` без аргумента показывает текущую.

Принимаются алиас или произвольный id модели у шлюза — локальный прокси
подставляет полный id по алиасу сам.

- История сжимается при ~100k токенов для любой модели списка. После `/model`
  Goose не пересчитывает окно контекста.
- `/plan` использует модель планирования `PLANNER_MODEL`; по умолчанию `off`
  (отдельная модель для планирования не задана).
- Вызов инструментов проверен для `ai-pro` на задаче «создать файл через
  инструмент» (см. раздел «Разработка и тесты»); `local-agent` — ризонинг-модель,
  для коротких лимитов `max_tokens` может не успеть дойти до ответа.

### Переменные окружения

| Переменная | Значение |
|---|---|
| `KEY`, `ENDPOINT` | ключ и адрес (с `/v1`) OpenAI-совместимого шлюза |
| `MODEL`, `PLANNER_MODEL` | модель по умолчанию и модель для `/plan` (`off` — отключить, значение по умолчанию) |
| `LEAN_CHECKER_URL` | адрес Lean checker (по умолчанию `https://scilibai.ru/grag`) |
| `BRAVE_API_KEY` | поиск через Brave вместо DuckDuckGo |
| `AI4SCIENCE_DAILY_TOKEN_LIMIT` | суточный лимит токенов (по умолчанию 3 000 000) |
| `AI4SCIENCE_QUIET=1`, `AI4SCIENCE_NOCOLOR=1` | без баннера, без цвета |
| `AI4SCIENCE_LEAN_DISABLED=1`, `AI4SCIENCE_WEB_DISABLED=1` | отключить группы инструментов |
| `AI4SCIENCE_SKILLS_DIR` | дополнительная папка со skills |
| `GOOSE_CONTEXT_LIMIT`, `GOOSE_AUTO_COMPACT_THRESHOLD`, `GOOSE_MAX_TOKENS` | параметры Goose |
| `GOOSE_PATH_ROOT` | папка данных Goose: сессии, журналы, история ввода (по умолчанию `.goose` в папке агента) |
| `GOOSE_TELEMETRY_ENABLED` | анонимная статистика Goose (по умолчанию `false`) |

---

## Инструменты агента

Встроенное расширение Goose `developer` даёт командную оболочку, редактор
файлов и список задач. MCP-сервер `ai4science` (`src/ai4science_mcp.py`) добавляет:

| Группа | Инструменты |
|---|---|
| Lean 4 | `lean_check` — проверка кода Lean 4 с классом ошибки; `lean_health` |
| Поиск по Mathlib | `lean_search_scilib` (граф зависимостей Mathlib), `lean_search_loogle`, `lean_search_leansearch`, `lean_search_moogle`, `lean_search_engines` |
| Сеть | `web_search`, `web_fetch` |
| PDF | `pdf_download`, `pdf_info`, `pdf_read`, `pdf_search` |
| Служебные | `list_skills`, `load_skill`, `load_artifact`, `token_budget` |

Большие ответы инструментов возвращаются как фрагмент и идентификатор
артефакта; полный текст загружается через `load_artifact` только при
необходимости. Skills — короткие руководства в `skills/*.md` (python, latex,
markdown, lean, literature, debug-loop), которые агент подгружает по теме
задачи.

## Файл-договор проекта

При старте агент читает первый найденный файл из списка `AGENT.md`,
`AGENTS.md`, `CLAUDE.md`, `.cursorrules` в папке проекта. В нём описываются
цель проекта, структура, соглашения, разрешённые и запрещённые действия,
команды проверки. Правила этого файла уточняют общие инструкции агента.

## Суточный лимит токенов

Локальный прокси между Goose и шлюзом (`ENDPOINT` из `.env`) считает
`usage.total_tokens` каждого ответа и записывает итог в
`~/.ai4science_budget.json`. При исчерпании лимита новая сессия не
запускается, текущая останавливается. Остаток показывают баннер,
`ai4math_mipt doctor` и инструмент `token_budget`. Счётчик обнуляется в
полночь по местному времени. Тот же прокси подставляет id модели по алиасу,
если в запросе короткое имя.

---

## Обновление с AI4Math 1.x

```bash
cd AI4Math                   # папка установки 1.x
git remote set-url origin https://github.com/andkhalov/AI4Science.git
git pull
rm -rf .venv .tools          # Windows: Remove-Item -Recurse -Force .venv, .tools
./setup.sh                   # Windows: setup.bat
```

- Репозиторий переименован: `andkhalov/AI4Math` → `andkhalov/AI4Science`;
  старый адрес перенаправляется на новый.
- Команда `ai4math` заменена на `ai4science`. Старый symlink
  `~/.local/bin/ai4math` установщик не трогает; удалить его можно вручную.
- `AI4MATH_*` версии 1.x принимается как запасное имя для `AI4SCIENCE_*`.
  Ключ и модель версии 1.x (`YANDEX_CLOUD_API_KEY` и т. п.) в этой ветке не
  читаются: бекенд инференса здесь — OpenAI-совместимый шлюз (`KEY`,
  `ENDPOINT`, `MODEL` в `.env`), формат `.env` другой — см. `.env.example`.

## Удаление

Установщик меняет систему в трёх местах:

| Что | Где |
|---|---|
| код, `.venv`, Goose (`.tools`), ключ (`.env`), сессии и журналы Goose (`.goose`), локальный Lean checker (`vendor/`) | папка агента, созданная `git clone` |
| команда `ai4math_mipt` | macOS и Linux: symlink `~/.local/bin/ai4math_mipt`; Windows: папка `<агент>\bin` в пользовательской переменной PATH |
| счётчик токенов | `~/.ai4science_budget.json` (Windows: `%USERPROFILE%\.ai4science_budget.json`) |

Python, git и системные пакеты, поставленные для установки, не удаляются: ими
пользуются и другие программы. Проекты, в которых работал агент, лежат в своих
папках и не затрагиваются. Перед удалением сохраните нужное: `.env` содержит
ключ, `.goose` — историю сессий.

### macOS, Linux, WSL

```bash
cd AI4Science                    # папка агента
# только если ставился локальный Lean checker (./setup.sh --with-lean-local):
( cd vendor/lean-checker && docker compose down --rmi all --volumes )
cd ..
rm -rf AI4Science
rm -f ~/.local/bin/ai4math_mipt ~/.ai4science_budget.json
```

Проверка в новом терминале: `command -v ai4math_mipt` ничего не выводит.

### Windows (PowerShell)

```powershell
cd AI4Science                    # папка агента
$d = (Resolve-Path .\bin).Path
$p = [Environment]::GetEnvironmentVariable('Path', 'User')
$rest = ($p -split ';') | Where-Object { $_ -and ($_.TrimEnd('\') -ine $d.TrimEnd('\')) }
[Environment]::SetEnvironmentVariable('Path', ($rest -join ';'), 'User')
cd ..
Remove-Item -Recurse -Force AI4Science
Remove-Item -Force "$env:USERPROFILE\.ai4science_budget.json" -ErrorAction SilentlyContinue
```

Проверка в новом терминале: `where.exe ai4math_mipt` сообщает, что файл не найден.

### Следы AI4Math 1.x

- Команда `~/.local/bin/ai4math`, файл `~/.ai4math_budget.json`, папка старой
  установки.
- Версия 1.x хранила сессии Goose в общих папках Goose: macOS и Linux —
  `~/.config/goose`, `~/.local/share/goose`, `~/.local/state/goose`; Windows —
  `%APPDATA%\Block\goose`. Эти папки используют все установки Goose на
  компьютере: удаляйте их, только если Goose не используется отдельно.

---

## Разработка и тесты

```bash
.venv/bin/python -m pytest tests/ -q                                   # без сети
AI4SCIENCE_TEST_NETWORK=1 .venv/bin/python -m pytest tests/test_network.py   # внешние сервисы
```

CI (GitHub Actions) на каждый push: модульные тесты на Ubuntu, Windows и
macOS; установка с нуля и `doctor` на всех трёх системах; сквозной прогон
задачи через агента на Ubuntu и Windows при заданных секретах
`YANDEX_CLOUD_API_KEY` (или `YANDEX_AI_API`) и `YANDEX_CLOUD_FOLDER`.

Версия Goose закреплена в `setup.py` (`GOOSE_VERSION`). Другой выпуск:
переменная `AI4SCIENCE_GOOSE_RELEASE` с адресом каталога релиза.

## Структура репозитория

```
AI4Science/
├── setup.bat / setup.sh / setup.py   установка (Windows / Linux и macOS / общая логика)
├── requirements.txt                  зависимости Python
├── .env.example                      шаблон .env
├── bin/
│   ├── ai4math_mipt, ai4math_mipt.bat команда (алиас) для Linux/macOS и Windows
│   ├── ai4science, ai4science.bat    исходный shim, к которому форвардит алиас
│   ├── ai4science.py                 точка входа: окружение Goose, прокси, doctor
│   └── ai4science-mcp[.bat]          запуск MCP-сервера
├── src/
│   ├── ai4science_mcp.py             MCP-сервер с инструментами
│   ├── ai4science_models.py          каталог моделей: алиасы, окна контекста
│   └── token_proxy.py                учёт токенов, суточный лимит, id модели по алиасу
├── recipes/ai4science.yaml           системные инструкции агента и список расширений
├── cli/wizard.py                     мастер настройки .env
├── skills/                           руководства по темам
├── scripts/                          локальный Lean checker, проверка чистой установки в Docker
├── tests/                            модульные тесты
├── docs/ARCHITECTURE.md              устройство агента
├── report/                           отчёт об экспериментах версии 1.x
└── .goose/                           данные Goose: сессии, журналы (создаётся при запуске)
```

## Связанные проекты

- [SciLib-GRC21](https://github.com/andkhalov/SciLib-GRC21) — проверка Lean 4 и поиск лемм по графу Mathlib, сервис по умолчанию для `lean_check` и `lean_search_scilib`.
- [andkhalov/lean-checker](https://github.com/andkhalov/lean-checker) — локальный Lean checker в Docker.
- [Goose](https://github.com/aaif-goose/goose) — агент, на котором построена обёртка.
- [Model Context Protocol](https://modelcontextprotocol.io/) — протокол подключения инструментов.

## Лицензия и цитирование

MIT, см. [LICENSE](LICENSE). Метаданные для цитирования — `CITATION.cff`.
