# Jarvik

This repository contains scripts to run the Jarvik assistant locally. OpenChat
is the default model used by all helper scripts. You can switch
models at any time via the web interface or by calling the `/model` endpoint.
Alternatively set the `MODEL_NAME` environment variable when starting a script
to run a different model. Jarvik keeps conversation history for seven days by
default. Set the `MEMORY_RETENTION_DAYS` environment variable to adjust the
retention period.
The Flask API listens on port `8000` by default, but you can override this using
the `FLASK_PORT` environment variable. The `FLASK_HOST` variable controls the
address the server binds to and defaults to `0.0.0.0`. Set `FLASK_HOST=127.0.0.1`
if you want to restrict connections to the local machine. Setting `FLASK_HOST` to
`0.0.0.0` or `::` allows access from Cloudflared or other machines. Set `OLLAMA_URL` to point at a remote Ollama instance if it is not
running locally (defaults to `http://localhost:11434`). When `OLLAMA_URL`
targets another host the start scripts will not attempt to launch a local
Ollama instance and all `ollama` commands automatically use the remote server.
Use `REQUEST_TIMEOUT` to control how long network requests wait for a
response before failing (defaults to `10` seconds). The `FLASK_DEBUG`
environment variable toggles Flask's debug mode and defaults to `true`.


The available API endpoints are documented in [openapi.yaml](openapi.yaml). Keep this file updated as routes change. You can view it with Swagger UI, for example:

```bash
npx swagger-ui-watcher openapi.yaml
```

Then open the printed URL in your browser.
## Installation

Install dependencies and create the virtual environment:

```bash
bash install_jarvik.sh
```

After running the installer, ensure the package `ddgs` (version 9 or newer) is installed. If needed,
activate the virtual environment and run:

```bash
pip install -U "ddgs>=9.0.0"
```

Make sure the commands `ollama`, `curl`, `lsof` and either `ss` (from
`iproute2`) or `nc` (from `netcat`) are available on your system.
On Windows you can install the Windows Subsystem for Linux or download BusyBox for Windows (https://frippery.org/busybox/) to provide these commands. Place `busybox.exe` somewhere in your `PATH` and call `busybox nc` or `busybox ss` when needed.
The start scripts also try to use `pgrep`/`pkill` from the `procps` package to
detect or stop running processes. When these commands are missing the scripts
fall back to `tasklist` on Windows or `ps` and `grep` on Unix systems.

If you need a fresh start, run the installer with `--clean` to first remove
any previous environment:

```bash
bash install_jarvik.sh --clean
```

After installation, add handy shell aliases by executing `load.sh`:

```bash
bash load.sh
```

This will append alias commands such as `jarvik-start`, `jarvik-status`,
`jarvik-model`, `jarvik-flask`, `jarvik-ollama` and wrappers for the
available models to your `~/.bashrc` and reload the file. The `jarvik-start`
alias launches the default OpenChat model.

### Wiping old knowledge

Run the helper script if you want to start with a clean knowledge folder:

```bash
bash clean_knowledge.sh
```

This command deletes everything under `knowledge/` except `_index.json`. The script pauses briefly so you can abort with Ctrl+C.



Knowledge files are loaded from the `knowledge/` folder at startup. Jarvik now
loads only plain text (`.txt`) files by default. See `knowledge/sample.txt` for a minimal example of the expected structure. The `knowledge/` directory now contains topic-specific folders such as `technologie/`, `programovani/` or `historie/`. A new `_index.json` file lists these categories with short descriptions so the UI can present them to users. The `KnowledgeBase` class from
`rag_engine.py` reads these files, splits them into paragraphs and indexes them
with FAISS. Vector search relies on `sentence-transformers` and `faiss-cpu`
listed in `requirements.txt`. Convert existing PDFs or DOCX documents using
`convert_to_txt.py`. The script relies on the optional packages `pdfplumber`
and `python-docx` for PDF and DOCX conversion, so install them manually if
needed.

Files uploaded via `/knowledge/upload` are automatically converted to text. Provide a `description` to store a short summary in memory.
### Folder layout and per-user data

Conversation history is stored in `memory/` and retained for seven days by
default. The public log lives in `memory/public.jsonl` while authenticated users
get their own `memory/<nick>/log.jsonl` file. Set the
`MEMORY_RETENTION_DAYS` environment variable to change how long entries are
kept. Knowledge files reside in `knowledge/` and any `knowledge/<nick>`
subfolders listed in `users.json` are loaded for that user in addition to the
public files. Set the `MEMORY_DIR` or `KNOWLEDGE_DIR` environment variables to
override these default locations.

Authentication tokens persist in `memory/tokens.json` so sessions survive restarts. Tokens expire after seven days by default; set the `TOKEN_LIFETIME_DAYS` environment variable to change this period.

The similarity threshold for vector search defaults to `0.7`. You can tweak how
strictly queries match the knowledge base by setting the `RAG_THRESHOLD`
environment variable to a floating point value.

### Text-only mode

Jarvik works exclusively with text files. Convert any PDF or DOCX inputs to
plain text with `convert_to_txt.py`. Install `pdfplumber` or `python-docx` when
prompted.

## Starting Jarvik

To launch all components run:

```bash
bash start_jarvik.sh
```

The script checks for required commands and automatically downloads the
`openchat` model if it is missing. Po spuštění vypíše, zda se všechny části
správně nastartovaly, případné chyby hledejte v souborech `*.log`.
Pokud vše proběhne bez chyb, otevře se výchozí prohlížeč na adrese
`http://localhost:$FLASK_PORT/`. Nastavte proměnnou prostředí `NO_BROWSER=1`,
pokud si nepřejete prohlížeč spouštět automaticky.
With the aliases loaded you can simply type:

```bash
jarvik-start
```

### Running with a different model

All management scripts now fully honour the `MODEL_NAME` environment variable.
The Flask API will query whichever model is specified. To start Jarvik with any
model simply set the variable when invoking the script. For example:

```bash
MODEL_NAME="llama3:8b" bash start_jarvik.sh
```
Alternatively you can run the dedicated wrapper scripts:

```bash
# Default model
bash start_openchat.sh
# or using the alias
jarvik-start

# LLaMA 3 8B model
bash start_llama3_8b.sh

# Command R model
bash start_command_r.sh

# Nous Hermes 2 model
bash start_nous_hermes2.sh

# External API mode
MODEL_MODE=api bash start_jarvik.sh
```

Switching models is seamless because each wrapper calls `switch_model.sh` to
restart with the selected model. Any running model or Flask instance is
replaced automatically.

## Supported Models

Jarvik supports a handful of local models plus an optional external API. Start
with `MODEL_MODE=api` to route requests through the remote service. Pull
the local models with `ollama pull` before first use:

```
ollama pull openchat
ollama pull llama3:8b
ollama pull command-r
ollama pull nous-hermes2
```

Models marked with a globe icon automatically prepend information from
`web.search()` when active. The selector in the web interface shows which
models support web search.

### Switching models while running

Jarvik can change models on the fly. Use the drop-down selector in the web
interface or send a POST request to `/model` with `{"model": "name"}`. The same
action is available from the shell via `switch_model.sh`:

```bash
bash switch_model.sh openchat
```

The application restarts with the new model.

### Offline usage

If you need to run without internet access, first download the model file. Create
a `Modelfile` that references the downloaded `.gguf` file and register it with:

```bash
ollama create openchat -f Modelfile
```

When you set `LOCAL_MODEL_FILE` to the path of your local model, the start
scripts will create the Ollama model automatically.

### Starting only Ollama

When you want just the Ollama service without loading a model, run:

```bash
bash start_ollama.sh
```

With aliases loaded this is simply:

```bash
jarvik-ollama
```

### Starting only the model

When you just need the model running without Flask, use:

```bash
bash start_model.sh
```

With aliases loaded this is simply:

```bash
jarvik-model
```

### Starting only the Flask server

When the model is already running you can launch just the Flask API using the
new helper script or manually:

```bash
# automatically stops any previous Flask instance
bash start_flask.sh
# or manually
source venv/bin/activate && python main.py
# or using the alias
jarvik-flask
```

### API mode

Jarvik can forward prompts to an external API instead of running a local model.
Set `MODEL_MODE=api` and specify the endpoint parameters:

```bash
MODEL_MODE=api \
API_URL=https://api.openai.com/v1/chat/completions \
API_MODEL=gpt-3.5-turbo \
API_KEY=sk-... bash start_jarvik.sh
```

The start script skips starting Ollama in this mode. The `/ask` endpoints will
send requests to `API_URL` using the provided key (or an `X-API-Key` header).

## Checking Status

See which services are running using:

```bash
bash status.sh
```

or via the alias:

```bash
jarvik-status
```
The script expects the selected model to be running persistently via
`ollama run $MODEL_NAME`.

You can check multiple models at once by listing them as arguments or
via the `MODEL_NAMES` environment variable:

```bash
MODEL_NAMES="openchat llama3:8b" bash status.sh
```

## Stopping Jarvik and Uninstall

Jarvik can be stopped and fully removed using the uninstall script:

```bash
bash uninstall_jarvik.sh
```

The script stops Ollama, the model and Flask, removes the `venv/` and
`memory/` directories and cleans the Jarvik aliases from `~/.bashrc`.

Chcete-li pouze přepnout na jiný model nebo znovu spustit Jarvik, využijte
skript `switch_model.sh` se jménem požadovaného modelu:

```bash
bash switch_model.sh mistral:7b-Q4_K_M
```

## Quick Start Script

For a single command that activates the environment, loads the model and
starts Flask you can also use the main start script:

```bash
bash start_jarvik.sh
```

Once the server is running it stays active in the background.
Model switching is handled from the web interface using the
**Switch model** control, which restarts Jarvik with the selected model.

## Real-time Monitoring

To continuously watch Jarvik's state and recent logs, run:

```bash
bash monitor.sh
```

The script refreshes every two seconds, detects whichever model Ollama
is currently serving and shows the last lines from `flask.log`,
`<model>.log` and `ollama.log` produced by `start_jarvik.sh`.

## Automatic Restart

If any component stops running, you can launch a watchdog that will
restart missing processes automatically:

```bash
bash watchdog.sh
```

The watchdog checks every five seconds that Ollama, the Gemma 2B model and
the Flask server are up and restarts them when needed.

## Upgrade

To download the latest version, reinstall and start Jarvik automatically run:

```bash
bash upgrade.sh
```

The script pulls the newest repository files, performs an uninstall, installs the dependencies again, reloads the shell aliases and starts all components.
It also stops any running Jarvik processes before updating to avoid locked files.
Note that the upgrade process forcefully resets the repository to the remote branch,
so any uncommitted changes will be lost. The `users.json` file is excluded from
cleaning, preserving your configured accounts automatically. The upgrade script
uses `git clean -fd -e knowledge` so the `knowledge/` directory is kept and your
articles remain available after upgrading.

Before cleaning the repository the upgrade script runs `backup_data.sh`. This
script creates a timestamped archive of the `knowledge/` and `memory/`
directories inside the `backups/` folder (e.g.
`backups/backup_20240517_153000.tar.gz`). To restore data simply extract the
desired archive in the repository root.

## API Setup

The Flask server enables Cross-Origin Resource Sharing (CORS) so web
applications can call the API from other domains. The feature is provided by
the `flask-cors` package and activated in `main.py`:

```python
from flask_cors import CORS

app = Flask(__name__, static_folder="static", template_folder="static")
CORS(app)
```

All origins are allowed by default. You can restrict access with
`CORS(app, resources={r"/*": {"origins": "https://example.com"}})` if needed.

## API Usage

Jarvik exposes a few HTTP endpoints on the configured Flask port
(default `8000`) that can be consumed by external applications such as ChatGPT:

* `POST /ask` – ask Jarvik a question. The conversation is stored in memory. Use
  `?debug=1` or an `X-Debug: 1` header to include debugging details in the
  response. Values `1`, `true`, or `yes` are accepted. The same flag works for
  `/ask_web` and `/ask_file`.
* `POST /memory/add` – manually append a `{ "user": "...", "jarvik": "..." }`
  record to the memory log.
* `GET /memory/search?q=term` – search stored memory entries. When no query is
  provided, the last five entries are returned.
* `POST /memory/delete` – delete memory entries by time range or keyword using
  `{ "from": "YYYY-MM-DD", "to": "YYYY-MM-DD" }` or `{ "keyword": "text" }`.
* `GET /knowledge/search?q=term[&threshold=0.5]` – search the local knowledge
  base files. When ``threshold`` is omitted the server falls back to the value
  of ``RAG_THRESHOLD`` or ``0.6``.
* `POST /knowledge/reload` – reload the knowledge base and return the number of loaded chunks. This uses the `KnowledgeBase` class to re-read the `knowledge/` directory.
* `POST /knowledge/upload` – upload a file. Optional fields `private` and `description` mark the file as user-only and store the description in memory.
* `GET /model` – return the currently running model name and the last startup
  status. The response contains the fields `model`, `status` and
  `success`.

* `POST /model` – switch models by posting `{ "model": "name" }`.

## Authentication

When a `users.json` file exists in the repository root the server requires
credentials. The file contains objects with `nick`, `password_hash` and optional
`knowledge_folders` or `memory_folders` entries.

A minimal configuration might look like:

```json
[
  {
    "nick": "bob",
    "password_hash": "<output of auth.hash_password('pw')>",
    "knowledge_folders": ["private"],
    "memory_folders": ["shared"]
  }
]
```

Generate the `password_hash` value with:

```bash
python -c "import auth; print(auth.hash_password('your_password'))"
```

### Adding users via helper script

Run `tools/create_user.py` to append a new account to `users.json`. Existing
nicks are skipped and the file is created automatically when missing. Execute
the helper as a module from the repository root so Python can locate
`auth.py`:

```bash
python -m tools.create_user --nick bob --password pw
```

For example, to create a user `alice` with password `SecretPass123` run:

```bash
python -m tools.create_user --nick alice --password SecretPass123
```

The repository also includes a `users.example.json` file containing the same
sample for quick reference. Restart the Flask server whenever `users.json`
changes so new accounts are loaded.

The web interface now starts with a login form. Enter your nick and password to
obtain a token from the `/login` endpoint. The token is stored in
`localStorage` and every request automatically includes an
`Authorization: Bearer <token>` header (the old `X-Token` header still works).
An optional API key field is provided and saved in `localStorage` as well. If
`users.json` is missing authentication is disabled and the interface loads
immediately.
The token is shown in the web interface and can be copied with a button after
logging in.
Issued tokens are written to `memory/tokens.json` and expire after seven days by default.

A mobile-friendly version is available at `/mobile`. Open this URL on your
phone or tablet for a simplified interface.

## Web Interface Overview

After logging in you will see the main dashboard with several panels and controls.

1. **Model selection** – choose one of the available models from the drop-down list and click *Switch model*. The current model name and short description are displayed above the selector.
2. **Environment toggle** – when `devlab_config.json` is present the **Use DevLab** button switches requests between the local server and the configured remote URL.
3. **Asking a question** – enter a prompt in the text field and optionally attach a file. Check **Save to txt** if you want the answer saved to a text file. Use **Private** to store the exchange only in your personal log. Topics can be selected via checkboxes to help organise questions.
4. **Progress indicator** – while the request is processed the status "⏳ Čekejte…" appears.
5. **Answer panel** – the right panel shows the model response. Below it are buttons to mark the reply as good or bad and to send a correction. If saving is enabled a download link to the text file is displayed.
6. **Additional panels** – context snippets and debug information are shown on the left. You can also expand the *Historie* section to view recent conversation history and inspect status messages.
7. **Knowledge management** – further controls allow uploading new knowledge files, approving or rejecting pending uploads and deleting memory entries by time range or keyword.
8. **Service control** – Jarvik runs continuously. Use *Switch model* to restart it with a different model.
9. **Logout** – use the *Logout* button at the bottom to remove the token and return to the login form.

## Running Tests

Unit tests live in the `tests/` directory. Install the development
dependencies first and then execute the tests and style checks:

```bash
pip install -r dev-requirements.txt
```

Run the test suite and Ruff with:

```bash
pytest
ruff check .
```

Run `ruff --fix` to automatically resolve simple issues.

## Remote testing

Use `tools/test_endpoint.py` to verify that a Jarvik server is reachable. The
helper reads the target URL from the `JARVIK_URL` environment variable or from a
`devlab_config.json` file containing a `url` field.

```bash
JARVIK_URL=http://example.com:8000 python -m tools.test_endpoint -m "ping"
```

Example `devlab_config.json`:

```json
{ "url": "http://example.com:8000" }
```

With this file present you can simply run:

```bash
python -m tools.test_endpoint --log flask.log
```

The script prints the HTTP response and, when `--log` is given, shows the last
lines of the specified log file.

## Remote access via Cloudflare

Expose your running Jarvik instance over a Cloudflare Tunnel. Ensure the server
is active first:

```bash
bash start_jarvik.sh
bash tunel.sh  # or cloudflared tunnel run Jarvik
```

Jarvik now listens on `0.0.0.0` by default. Set `FLASK_HOST=127.0.0.1` if you
want to restrict access to local connections only. Use `FLASK_HOST=0.0.0.0` (or
`::` for IPv6) when Cloudflare needs to reach the server.

## DevLab mode

When a `devlab_config.json` file with a `url` field exists in the repository
root the web interface exposes a **Use DevLab** button. Toggle the button to
send all requests to the configured URL instead of the local server. The current
environment is shown next to the button.

### 🧩 DevLab submodule

Tento projekt obsahuje vývojový modul [`DevLab`](https://github.com/Smukanec/JARVIK_DevLab) jako Git submodul.
Po naklonování nezapomeň spustit:

```bash
git submodule update --init --recursive
```

## GitHub Connector

The helper module `tools/github_connector.py` provides basic GitHub
automation. Configure the repository URL and authentication token to
clone or update a repository, inspect diffs or commit history, and push
changes. Pull requests can be opened either via the `GitPython` library
or the optional `gh` CLI.

Set the following environment variables or pass them directly to the
functions:

- `GITHUB_REPO_URL` – HTTPS address of the repository.
- `GITHUB_TOKEN` – personal access token with repo permissions.


Install the extra dependency `GitPython` and optionally the `gh` CLI if
you prefer using it for authentication and PR creation.

## Troubleshooting

Verify that the `ollama` binary is available and that the service is
reachable:

```bash
ollama --version
tail -n 20 ollama.log
```

When you set `OLLAMA_URL` to a remote instance you can test the
connection with:

```bash
curl -v "$OLLAMA_URL/api/tags"
```

The mobile UI lives at `/mobile` and relies on JavaScript from
`static/app.js`. If the page appears blank, open your browser console and
check for any errors.

For more information consult the log files:
`ollama.log`, `<model>.log` and `flask.log`.

## License

This project is licensed under the [MIT License](LICENSE).

