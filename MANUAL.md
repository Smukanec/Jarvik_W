# Jarvik – Manuál k instalaci a použití

Tento krátký manuál popisuje základní kroky pro instalaci a spuštění Jarvika na lokálním stroji.

Ve výchozím nastavení je použit model `openchat`. Model lze kdykoli změnit ve webovém rozhraní nebo voláním endpointu `/model`. V příkladech je předpokládán OpenChat, jiný model zvolíte nastavením proměnné `MODEL_NAME` při spouštění skriptů.
Flask API naslouchá na portu `8010`, který lze změnit proměnnou `FLASK_PORT`.
Pro vzdálenou Ollamu nastavte proměnnou `OLLAMA_URL` (výchozí
`http://localhost:11434`).
Citlivost vyhledávání ve znalostech můžete upravit proměnnou `RAG_THRESHOLD`
(výchozí hodnota je `0.7`).
Znalostní soubory lze nahrávat v rozhraní pomocí tlačítka "Nahrát". Ke každému souboru můžete uvést popis, který se uloží do paměti.
Výchozí umístění adresářů `memory/` a `knowledge/` lze změnit pomocí proměnných `MEMORY_DIR` a `KNOWLEDGE_DIR`.

## Instalace

1. Spusťte instalační skript, který vytvoří virtuální prostředí a nainstaluje závislosti:
   ```bash
   bash install_jarvik.sh
   ```
   Pro čistou instalaci můžete použít přepínač `--clean`, který nejprve odstraní případné starší soubory:
   ```bash
   bash install_jarvik.sh --clean
   ```

2. Po skončení instalace zkontrolujte, že je k dispozici balíček `duckduckgo-search`
    ve verzi 8.0 nebo novější. Pokud chybí, doinstalujte jej v aktivovaném
    virtuálním prostředí příkazem:
   ```bash
     pip install -U duckduckgo-search>=8.0
   ```

3. Po dokončení instalace načtěte aliasy usnadňující práci se skripty:
   ```bash
   bash load.sh
   ```
   Do souboru `~/.bashrc` se přidají příkazy jako `jarvik-start`, `jarvik-status`,
   `jarvik-model`, `jarvik-flask`, `jarvik-ollama` a `jarvik-start-llama3`.

## Spuštění

Jarvika spustíte buď přímo pomocí skriptu `start_jarvik.sh`, nebo přes alias `jarvik-start` (pokud jste provedli krok s načtením aliasů):
```bash
bash start_openchat.sh
# nebo
jarvik-start
```
Skript aktivuje virtuální prostředí, spustí Ollamu, zvolený model (výchozí
OpenChat) a nakonec Flask server na portu 8010 (lze změnit proměnnou
`FLASK_PORT`). Pokud model chybí, stáhne se automaticky. Pro jiný model
nastavte proměnnou `MODEL_NAME` při spuštění – všechny dodané skripty ji nyní
plně respektují. Například:

```bash
MODEL_NAME="llama3:8b" bash start_jarvik.sh
```
nebo použijte připravený skript pro Mistral 7B:

```bash
bash start_llama3_8b.sh
```

Podobné skripty jsou připraveny i pro další modely:

```bash
bash start_llama3_8b.sh      # llama3:8b
bash start_command_r.sh      # command-r
bash start_nous_hermes2.sh   # nous-hermes2
MODEL_NAME=api bash start_jarvik.sh # externí API
```
Každý z těchto skriptů volá `switch_model.sh`,
který nejprve zastaví běžící model i Flask a poté
spustí novou instanci s vybraným modelem. Přepnutí je tak otázkou
jednoho příkazu.
Stejnou hodnotu používá i samotná Flask aplikace.

## Podporované modely

Modely lze stáhnout předem příkazem `ollama pull`:

```bash
ollama pull openchat
ollama pull llama3:8b
ollama pull command-r
ollama pull nous-hermes2
```

### Přepnutí modelu za běhu

Jarvika lze přepnout na jiný model bez ručního zastavení všech služeb.
Stačí spustit skript `switch_model.sh` s názvem požadovaného modelu nebo
vybrat nový model v rozhraní aplikace. Interně se volá endpoint `/model`.

```bash
bash switch_model.sh openchat
```

Případně je možné odeslat HTTP POST požadavek na `/model` s JSON
`{"model": "jméno"}`. Aplikace se restartuje s novým modelem. Dotazem `GET`
na stejnou adresu zjistíte aktuálně spuštěný model.

### Offline použití

Pokud nemáte k dispozici internetové připojení, stáhněte si nejprve soubor s
modelem a vytvořte `Modelfile` s řádkem
`FROM /cesta/k/model.gguf` a zaregistrujte model příkazem:

```bash
ollama create openchat -f Modelfile
```

Nastavíte-li proměnnou `LOCAL_MODEL_FILE` na cestu k tomuto souboru, startovací
skripty registraci provedou automaticky.

### Spuštění pouze Ollamy

Pokud potřebujete spustit jen službu Ollama bez načtení modelu, použijte:

```bash
bash start_ollama.sh
```

Po načtení aliasů stačí příkaz:

```bash
jarvik-ollama
```

### Spuštění pouze modelu

Pokud potřebujete jen běžící model bez Flasku, spusťte:

```bash
bash start_model.sh
```

Po načtení aliasů stačí příkaz:

```bash
jarvik-model
```

### Spuštění pouze Flasku

Pokud už máte spuštěný model a potřebujete jen Flask server, spusťte nový
skript nebo příkaz ručně:

```bash
# Skript automaticky ukončí předchozí Flask
bash start_flask.sh
# nebo ručně
source venv/bin/activate && python main.py
```

Po načtení aliasů stačí příkaz:

```bash
jarvik-flask
```

## Stav běžících služeb

Aktuální stav zjistíte skriptem `status.sh` nebo aliasem `jarvik-status`:
```bash
bash status.sh
# nebo
jarvik-status
```
Zobrazí se informace o běžících procesech a dostupnosti znalostních souborů.

Pro kontrolu více modelů najednou je lze uvést jako argumenty nebo nastavit
proměnnou `MODEL_NAMES`:

```bash
MODEL_NAMES="openchat llama3:8b" bash status.sh
```

## Ukončení a odinstalování

Pro zastavení všech služeb a odstranění prostředí použijte:
```bash
bash uninstall_jarvik.sh
```
Skript ukončí Ollamu, spuštěný model i Flask, smaže adresáře `venv/` a `memory/` a vyčistí aliasy z `~/.bashrc`.

Pokud potřebujete Jarvika jen restartovat s jiným modelem, použijte

```bash
bash switch_model.sh openchat
```

## Rychlý start

Pro jednorázové spuštění všech komponent slouží skript `start_jarvik.sh`, který aktivuje prostředí, spustí model i server v jednom kroku:
```bash
bash start_jarvik.sh
```

## Upgrade

Nejnovější verzi můžete stáhnout a nainstalovat skriptem `upgrade.sh`:
```bash
bash upgrade.sh
```
Skript stáhne nové soubory z repozitáře, provede odinstalování, znovu nainstaluje závislosti, obnoví aliasy v `~/.bashrc` a spustí Jarvika.
Před aktualizací také zastaví běžící procesy Jarvika, aby nedošlo k uzamčení souborů.
