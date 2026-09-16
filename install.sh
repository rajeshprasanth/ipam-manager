#!/usr/bin/env bash
#
# IPAM Manager — interactive installer / manager
#
# Modes:
#   1) Docker Compose  : PostgreSQL 16 + app (recommended for self-hosting)
#   2) Host + Postgres : venv + bare-metal app against PostgreSQL
#   3) Host + SQLite   : quick local dev database (no PostgreSQL required)
#
# Common tasks: admin accounts, migrations, start/stop/status, uninstall.
# Logs accumulate in ./logs/ for both host (ipam-app.log) and Docker
# (gunicorn-*.log, postgresql-*.log) installs.
#
# Usage:
#   ./install.sh                interactive menu (asks about DB, port, passwords…)
#   ./install.sh check          print detected environment and exit
#   ./install.sh <mode>         run a specific install mode (prompts if a TTY,
#                               otherwise uses env vars or defaults)
#        docker | host-postgres | host-sqlite
#   ./install.sh <cmd>          admin | migrate | run | start | stop | status
#                               | uninstall | docs | docs-build
#   ./install.sh start          start detached (host) / compose up -d (docker)
#   ./install.sh stop           stop the app / stack
#
# Values can be pre-set via environment variables to make it non-interactive,
# e.g. APP_PORT=9000 POSTGRES_USER=ops ./install.sh host-postgres
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

ENV_FILE="$SCRIPT_DIR/.env"
COMPOSE_FILE="$SCRIPT_DIR/Docker/docker-compose.yml"
STATE_FILE="$SCRIPT_DIR/.install-mode"

# --------------------------------------------------------------------------- #
# Output helpers
# --------------------------------------------------------------------------- #
if [ -t 1 ]; then
    C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'; C_RED=$'\033[31m'; C_BOLD=$'\033[1m'; C_RESET=$'\033[0m'
else
    C_GREEN=""; C_YELLOW=""; C_RED=""; C_BOLD=""; C_RESET=""
fi

info() { printf '%s\n' "${C_GREEN}==>${C_RESET} $*"; }
warn() { printf '%s\n' "${C_YELLOW}!! $*${C_RESET}"; }
err()  { printf '%s\n' "${C_RED}!! $*${C_RESET}"; }
die()  { err "$*"; exit 1; }
need() { for c in "$@"; do command -v "$c" >/dev/null 2>&1 || die "required tool not found: $c"; done; }

confirm() {  # confirm "text" [default]
    local default="${2:-n}" ans
    printf '%s [%s/%s] ' "$1" "$([ "$default" = y ] && echo Y || echo y)" "$([ "$default" = y ] && echo n || echo N)"
    read -r ans || return 1
    [ -z "$ans" ] && ans="$default"
    case "$ans" in y|Y|yes|Yes) return 0;; *) return 1;; esac
}

# Interactive prompt helpers. When stdin is not a TTY (or the variable is
# already set in the environment) they fall back to defaults, so automation
# and CI work without prompting.
INTERACTIVE=0
[ -t 0 ] && INTERACTIVE=1

ask() {  # ask <varname> <label> <default>
    local _v="$1" _label="$2" _default="$3" _val=""
    if [ -n "${!_v:-}" ]; then
        printf -v "$_v" '%s' "${!_v}"
    elif [ "$INTERACTIVE" = 1 ]; then
        printf '%s [%s]: ' "$_label" "$_default"
        read -r _val
        printf -v "$_v" '%s' "${_val:-$_default}"
    else
        printf -v "$_v" '%s' "$_default"
    fi
}

ask_number() {  # ask_number <varname> <label> <default>
    local _v="$1" _label="$2" _default="$3"
    while :; do
        ask "$_v" "$_label" "$_default"
        [[ "${!_v}" =~ ^[0-9]+$ ]] && [ "${!_v}" -ge 1 ] && [ "${!_v}" -le 65535 ] && return 0
        warn "Invalid port: '${!_v}' (must be 1-65535)."
        printf -v "$_v" '%s' ""
    done
}

# --------------------------------------------------------------------------- #
# Environment detection
# --------------------------------------------------------------------------- #
DOCKER=""; COMPOSE=""
detect_docker() {
    if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
        DOCKER=docker; COMPOSE="docker compose"
    elif command -v podman >/dev/null 2>&1 && podman info >/dev/null 2>&1; then
        DOCKER=podman; COMPOSE="podman compose"
    fi
}

PY=""
detect_python() {
    local p
    for p in python3 python; do
        if command -v "$p" >/dev/null 2>&1 && "$p" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)' 2>/dev/null; then
            PY="$p"; return 0
        fi
    done
    return 1
}

VENV_DIR="$SCRIPT_DIR/.venv"
venv_py() { printf '%s' "$VENV_DIR/bin/python"; }

ensure_venv() {
    [ -n "$PY" ] || { warn "Python 3.12+ not found; host modes are unavailable."; return 1; }
    if [ ! -x "$(venv_py)" ]; then
        info "Creating virtual environment in $VENV_DIR"
        "$PY" -m venv "$VENV_DIR"
    fi
}

ensure_pip() {
    info "Installing dependencies into the virtual environment..."
    "$(venv_py)" -m pip install --upgrade --quiet pip
    "$(venv_py)" -m pip install --quiet -r requirements.txt || die "pip install failed"
    info "Dependencies installed."
}

# --------------------------------------------------------------------------- #
# .env management
# --------------------------------------------------------------------------- #
ensure_env_file() {
    if [ ! -f "$ENV_FILE" ]; then
        if [ -f "$SCRIPT_DIR/.env.example" ]; then cp "$SCRIPT_DIR/.env.example" "$ENV_FILE"; else : > "$ENV_FILE"; fi
        info "Created $ENV_FILE from .env.example"
    fi
}

env_get()    { grep -E "^$1=" "$ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2-; }
env_set()    { if grep -qE "^$1=" "$ENV_FILE" 2>/dev/null; then sed -i -E "s|^$1=.*|$1=$2|" "$ENV_FILE"; else printf '%s=%s\n' "$1" "$2" >> "$ENV_FILE"; fi; }
env_unset()  { sed -i -E "/^$1=.*$/d" "$ENV_FILE" 2>/dev/null || true; }

gen_secret() {
    if [ -n "${PY:-}" ] && command -v "$PY" >/dev/null 2>&1; then
        "$PY" -c 'import secrets; print(secrets.token_urlsafe(48))'
    else
        LC_ALL=C tr -dc 'A-Za-z0-9_-' < /dev/urandom | head -c 48
    fi
}

# Ask for the common configuration and persist it to .env.
configure_common() {
    ensure_env_file
    if ! grep -qE '^(APP_NAME|APP_OWNER|COPYRIGHT)=' "$ENV_FILE"; then
        ask APP_NAME "Application name" "IPAM Manager"
        ask APP_OWNER "Owner / organisation (shown in footers)" "IPAM Manager Team"
        env_set APP_NAME "${APP_NAME:-IPAM Manager}"
        env_set APP_OWNER "${APP_OWNER:-IPAM Manager Team}"
    fi
    ask_number APP_PORT "Web UI port" "${APP_PORT:-8076}"
    env_set APP_PORT "$APP_PORT"

    ask_number DOCS_PORT "MkDocs documentation port" "${DOCS_PORT:-8000}"
    env_set DOCS_PORT "$DOCS_PORT"

    local sk
    sk="$(env_get SECRET_KEY || true)"
    if [ -z "$sk" ] || [ "$sk" = "change-me-in-production" ]; then
        if [ "$INTERACTIVE" = 1 ]; then
            printf '%s' "Generate a random SECRET_KEY? [Y/n]: "; read -r g
            case "${g:-y}" in y|Y|yes) g=1;; *) g=0;; esac
        else
            g=1
        fi
        if [ "$g" = 1 ]; then
            sk="$(gen_secret)"
            info "Generated SECRET_KEY."
        else
            ask sk "Enter your SECRET_KEY" ""
        fi
        [ -n "$sk" ] || die "SECRET_KEY is required."
        env_set SECRET_KEY "$sk"
    fi
}

# Ask about the database for a Docker install and persist POSTGRES_* / DATABASE_URL.
configure_docker_db() {
    local choice
    if [ "$INTERACTIVE" = 1 ] && [ -z "${DATABASE_URL:-}" ] && [ -z "${POSTGRES_USER:-}" ] && [ -z "${POSTGRES_PASSWORD:-}" ]; then
        printf '%s\n' "Database setup:"
        printf '%s\n' "  b) Bundled PostgreSQL container (default; recommended)"
        printf '%s\n' "  e) Use an existing/managed database (DATABASE_URL)"
        printf '%s'   "Choose [b/e]: "; read -r choice
    elif [ -n "${DATABASE_URL:-}" ]; then
        choice="e"
    else
        choice="b"
    fi
    case "${choice:-b}" in
        e|E)
            ask DATABASE_URL "DATABASE_URL for the existing database" ""
            [ -n "$DATABASE_URL" ] || die "DATABASE_URL cannot be empty."
            env_set DATABASE_URL "$DATABASE_URL"
            env_unset POSTGRES_USER; env_unset POSTGRES_PASSWORD; env_unset POSTGRES_DB
            ;;
        b|B|"")
            ask POSTGRES_USER "PostgreSQL username" "${POSTGRES_USER:-ipam}"
            ask POSTGRES_PASSWORD "PostgreSQL password" "${POSTGRES_PASSWORD:-ipam}"
            ask POSTGRES_DB     "PostgreSQL database name" "${POSTGRES_DB:-ipam}"
            env_set POSTGRES_USER "$POSTGRES_USER"
            env_set POSTGRES_PASSWORD "$POSTGRES_PASSWORD"
            env_set POSTGRES_DB "$POSTGRES_DB"
            env_unset DATABASE_URL   # let the app auto-detect the "db" host
            ;;
    esac
}

# Ask about the database for a host install. $1 is the default choice used in
# non-interactive runs (p=PostgreSQL, s=SQLite, e=existing DATABASE_URL).
configure_host_db() {
    local dflt="${1:-p}" choice
    ensure_env_file
    if [ "$INTERACTIVE" = 1 ] && [ -z "${DATABASE_URL:-}" ] && [ -z "${POSTGRES_USER:-}" ] && [ -z "${POSTGRES_PASSWORD:-}" ]; then
        printf '%s\n' "Database for this host:"
        printf '%s\n' "  p) PostgreSQL on this host (default; created if missing)"
        printf '%s\n' "  e) Existing/managed PostgreSQL (DATABASE_URL)"
        printf '%s\n' "  s) SQLite (quick dev database)"
        printf '%s'   "Choose [p/e/s]: "; read -r choice
    elif [ -n "${DATABASE_URL:-}" ]; then
        case "$DATABASE_URL" in
            sqlite://*) choice="s" ;;
            *)          choice="e" ;;
        esac
    elif [ -n "${POSTGRES_USER:-}" ] || [ -n "${POSTGRES_PASSWORD:-}" ]; then
        choice="p"
    else
        choice="$dflt"
    fi
    case "${choice:-p}" in
        p|P|"")
            ask POSTGRES_USER "PostgreSQL username" "${POSTGRES_USER:-ipam}"
            ask POSTGRES_PASSWORD "PostgreSQL password" "${POSTGRES_PASSWORD:-ipam}"
            ask POSTGRES_DB     "PostgreSQL database name" "${POSTGRES_DB:-ipam}"
            env_set POSTGRES_USER "$POSTGRES_USER"
            env_set POSTGRES_PASSWORD "$POSTGRES_PASSWORD"
            env_set POSTGRES_DB "$POSTGRES_DB"
            env_unset DATABASE_URL    # host auto-detect -> localhost with POSTGRES_*
            env_set AUTO_CREATE_TABLES false
            ;;
        e|E)
            ask DATABASE_URL "DATABASE_URL for the existing database" ""
            [ -n "$DATABASE_URL" ] || die "DATABASE_URL cannot be empty."
            env_set DATABASE_URL "$DATABASE_URL"
            env_set AUTO_CREATE_TABLES false
            ;;
        s|S)
            env_set DATABASE_URL "sqlite:///$SCRIPT_DIR/dev.db"
            env_set AUTO_CREATE_TABLES true
            ;;
    esac
}

# --------------------------------------------------------------------------- #
# Model options
# --------------------------------------------------------------------------- #
set_mode() { printf '%s\n' "$1" > "$STATE_FILE"; }
current_mode() { [ -f "$STATE_FILE" ] && cat "$STATE_FILE" || echo "(none)"; }

# --------------------------------------------------------------------------- #
# Logs (shared host/container location)
# --------------------------------------------------------------------------- #
LOG_DIR="$SCRIPT_DIR/logs"
LOG_FILE="$LOG_DIR/ipam-app.log"
ACCESS_FILE="$LOG_DIR/ipam-access.log"
PID_FILE="$LOG_DIR/ipam-app.pid"

ensure_logs_dir() {
    mkdir -p "$LOG_DIR"
    # Containers (gunicorn "app" user, postgres user) need write access when
    # logs/ is bind-mounted into them; wide permissions keep this simple.
    chmod 777 "$LOG_DIR" 2>/dev/null || true
}

# --------------------------------------------------------------------------- #
# Admin account helpers
# --------------------------------------------------------------------------- #
read_admin_args() {
    if [ "$INTERACTIVE" != 1 ]; then
        ADMIN_USER="${ADMIN_USER:-admin}"
        ADMIN_EMAIL="${ADMIN_EMAIL:-}"
        ADMIN_PASS="${ADMIN_PASS:-}"
        [ -n "$ADMIN_EMAIL" ] || die "non-interactive admin needs ADMIN_USER/ADMIN_EMAIL/ADMIN_PASS env"
        return 0
    fi
    ask ADMIN_USER "Admin username" "${ADMIN_USER:-admin}"
    printf '%s' "Admin email: "; read -r ADMIN_EMAIL; [ -n "$ADMIN_EMAIL" ] || die "email is required"
    while :; do
        printf '%s' "Admin password: "; read -rs ADMIN_PASS; echo
        printf '%s' "Confirm password: "; read -rs PASS2; echo
        [ "$ADMIN_PASS" = "$PASS2" ] && [ -n "$ADMIN_PASS" ] && break
        warn "Passwords do not match or are empty. Try again."
    done
}

create_admin_host() {
    read_admin_args
    info "Creating administrator '${ADMIN_USER}'..."
    "$(venv_py)" -m app.scripts.create_admin --username "$ADMIN_USER" --email "$ADMIN_EMAIL" --password "$ADMIN_PASS"
    info "Administrator ready."
}

create_admin_compose() {
    read_admin_args
    info "Creating administrator '${ADMIN_USER}' in the running stack..."
    compose_cmd exec -T web python -m app.scripts.create_admin \
        --username "$ADMIN_USER" --email "$ADMIN_EMAIL" --password "$ADMIN_PASS"
    info "Administrator ready."
}

# --------------------------------------------------------------------------- #
# PostgreSQL bootstrap (best-effort, Fedora/RHEL + Debian styles)
# --------------------------------------------------------------------------- #
bootstrap_postgres() {
    local u="${POSTGRES_USER:-ipam}" p="${POSTGRES_PASSWORD:-ipam}" d="${POSTGRES_DB:-ipam}"
    local url="postgresql://${u}:${p}@localhost:5432/${d}"
    if command -v psql >/dev/null 2>&1 && psql "$url" -qtAc "SELECT 1" >/dev/null 2>&1; then
        info "PostgreSQL is already reachable at host localhost:5432 ($d)"
        return 0
    fi
    command -v psql >/dev/null 2>&1 || { warn "psql not found; create the '$u' role/database '$d' yourself, then re-run."; return 1; }
    warn "Creating role '$u' and database '$d' (best-effort; sudo may prompt)..."
    if command -v sudo >/dev/null 2>&1; then
        sudo -u postgres psql -qc "CREATE ROLE \"$u\" LOGIN PASSWORD '$p';" 2>/dev/null || true
        sudo -u postgres psql -qc "CREATE DATABASE \"$d\" OWNER \"$u\";" 2>/dev/null || true
        # Fedora defaults to "ident" for localhost TCP; switch to scram-sha-256.
        if [ -f /var/lib/pgsql/data/pg_hba.conf ]; then
            sudo sed -i 's|^\(host *all *all *127\.0\.0\.1/32 *\)ident$|\1scram-sha-256|;s|^\(host *all *all *::1/128 *\)ident$|\1scram-sha-256|' /var/lib/pgsql/data/pg_hba.conf
            sudo systemctl reload postgresql >/dev/null 2>&1 || true
        fi
    fi
    if psql "$url" -qtAc "SELECT 1" >/dev/null 2>&1; then
        info "PostgreSQL now reachable at $url"
    else
        warn "Could not configure PostgreSQL automatically. Please create role '$u' / database '$d' manually, e.g.:"
        echo "  sudo -u postgres psql -c \"CREATE ROLE $u LOGIN PASSWORD '$p';\""
        echo "  sudo -u postgres psql -c \"CREATE DATABASE $d OWNER $u;\""
        return 1
    fi
}

# --------------------------------------------------------------------------- #
# Install modes
# --------------------------------------------------------------------------- #
install_docker() {
    detect_docker
    [ -n "$COMPOSE" ] || die "Docker (or Podman) Compose is unavailable."
    $COMPOSE version >/dev/null 2>&1 || die "The '$DOCKER' Compose plugin is not available ($($DOCKER) compose)."
    need "$DOCKER"
    configure_common
    configure_docker_db
    ensure_logs_dir
    info "Building and starting the Docker stack (${DOCKER})..."
    compose_cmd up -d --build
    set_mode docker
    info "Stack is up: http://localhost:${APP_PORT}"
    compose_cmd ps
    if confirm "Create an administrator account now?"; then create_admin_compose; fi
    info "Done. Logs accumulate in ./logs/ (gunicorn-access.log, gunicorn-error.log, postgresql-*.log)"
}

install_host_postgres() {
    detect_python || die "Python 3.12+ is required for host installation."
    configure_common
    configure_host_db p
    ensure_venv && ensure_pip
    local db_url; db_url="$(env_get DATABASE_URL || true)"
    if [ -n "$db_url" ] && ! [[ "$db_url" == sqlite://* ]]; then
        info "Using configured database: ${db_url}"
    else
        if confirm "Bootstrap local PostgreSQL if not present? [Y/n] " y; then bootstrap_postgres || true; fi
    fi
    info "Running database migrations..."
    "$(venv_py)" -m alembic upgrade head
    set_mode host-postgres
    if confirm "Create an administrator account now?"; then create_admin_host; fi
    info "Installed. Run detached: ./install.sh start  (foreground: ./install.sh run)"
}

install_host_sqlite() {
    detect_python || die "Python 3.12+ is required for host installation."
    configure_common
    configure_host_db s        # default choice s => sqlite
    ensure_venv && ensure_pip
    info "SQLite database ready (tables auto-create on startup at dev.db)."
    set_mode host-sqlite
    if confirm "Create an administrator account now?"; then create_admin_host; fi
    info "Installed. Run detached: ./install.sh start  (foreground: ./install.sh run)"
}

# --------------------------------------------------------------------------- #
# Run / start / stop / status
# --------------------------------------------------------------------------- #
read_app_port() { APP_PORT="$(env_get APP_PORT || true)"; APP_PORT="${APP_PORT:-8076}"; }

host_app_pid() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        cat "$PID_FILE"
    fi
}

# Export the values we manage in .env so Docker Compose's ${VAR:-default}
# interpolation picks them up (compose does not read the root .env otherwise).
export_compose_env() {
    local v val
    for v in APP_PORT POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB APP_NAME APP_OWNER COPYRIGHT GUNICORN_WORKERS COOKIE_SECURE; do
        val="$(env_get "$v" || true)"
        if [ -n "$val" ]; then
            export "$v=$val"
        else
            unset "$v" 2>/dev/null || true
        fi
    done
    export COMPOSE_PROJECT_NAME=ipam-manager
}

compose_cmd() { export_compose_env; $COMPOSE -f "$COMPOSE_FILE" "$@"; }

pick_server() {
    local choice
    printf '%s\n' "How do you want to run the app?"
    printf '%s\n' "  d) Dev:  uvicorn --reload (auto-restart on code changes)"
    printf '%s\n' "  p) Prod: gunicorn + uvicorn workers (2)"
    printf '%s'   "  c) Cancel  [d/p/c] "; read -r choice || choice="c"
    case "$choice" in p|P) echo prod;; d|D|"") echo dev;; *) return 1;; esac
}

run_app() {  # foreground (interactive)
    read_app_port
    case "$(current_mode)" in
        docker)
            [ -n "$COMPOSE" ] || die "Docker/Podman Compose unavailable."
            compose_cmd version >/dev/null 2>&1 || die "Compose plugin not available."
            compose_cmd up -d
            info "Stack running at http://localhost:${APP_PORT}"
            ;;
        host-postgres|host-sqlite)
            [ -x "$(venv_py)" ] || die "Not installed; run ./install.sh first (mode 2 or 3)."
            local server; server="$(pick_server)" || return 0
            if [ "$server" = prod ]; then
                info "Starting gunicorn at http://localhost:${APP_PORT} (Ctrl+C to stop)"
                exec "$(venv_py)" -m gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 2 -b "0.0.0.0:${APP_PORT}"
            else
                info "Starting uvicorn at http://localhost:${APP_PORT} (Ctrl+C to stop)"
                exec "$(venv_py)" -m uvicorn app.main:app --reload --host 0.0.0.0 --port "${APP_PORT}"
            fi
            ;;
        *) die "No installation mode recorded; run an install option first." ;;
    esac
}

start_app() {  # detached — returns to the shell, logs accumulate in logs/
    read_app_port
    case "$(current_mode)" in
        docker)
            [ -n "$COMPOSE" ] || die "Docker/Podman Compose unavailable."
            ensure_logs_dir
            compose_cmd up -d
            info "Stack running in background: http://localhost:${APP_PORT}"
            info "Logs accumulate in ./logs/ (gunicorn-access.log, gunicorn-error.log, postgresql-*.log)"
            ;;
        host-postgres|host-sqlite)
            [ -x "$(venv_py)" ] || die "Not installed; run ./install.sh first (mode 2 or 3)."
            ensure_logs_dir
            local pid; pid="$(host_app_pid)"
            if [ -n "$pid" ]; then
                warn "Already running (pid $pid). Stop it first: ./install.sh stop"
                return 1
            fi
            info "Starting app detached at http://localhost:${APP_PORT} (logs: $LOG_DIR/)"
            setsid "$(venv_py)" -m gunicorn app.main:app -k uvicorn.workers.UvicornWorker \
                -w 2 -b "0.0.0.0:${APP_PORT}" \
                --access-logfile "$ACCESS_FILE" \
                --error-logfile "$LOG_FILE" \
                >>"$LOG_FILE" 2>&1 </dev/null &
            printf '%s\n' "$!" > "$PID_FILE"
            # Wait briefly and verify it actually bound (gunicorn keeps running
            # and retrying even when the port is already in use).
            local ok=""
            local i
            for i in 1 2 3 4 5; do
                sleep 1
                if grep -q "Address already in use" "$LOG_FILE" 2>/dev/null; then
                    warn "Port ${APP_PORT} is already in use — the app could not bind. See $LOG_FILE"
                    return 1
                fi
                if grep -q "Listening at:" "$LOG_FILE" 2>/dev/null; then
                    ok="yes"; break
                fi
                if ! kill -0 "$!" 2>/dev/null; then
                    warn "App exited before binding; see $LOG_FILE"
                    rm -f "$PID_FILE"
                    return 1
                fi
            done
            info "App running detached (pid $(cat "$PID_FILE")). Stop with: ./install.sh stop"
            [ -n "$ok" ] || warn "Not yet confirmed bound — tail $LOG_FILE to check."
            ;;
        *) die "No installation mode recorded; run an install option first." ;;
    esac
}

stop_app() {
    case "$(current_mode)" in
        docker)
            [ -n "$COMPOSE" ] || return 0
            compose_cmd down
            info "Stack stopped (data volume kept)."
            ;;
        host-postgres|host-sqlite)
            local pid; pid="$(host_app_pid)"
            if [ -n "$pid" ]; then
                kill "$pid" 2>/dev/null || true
                rm -f "$PID_FILE"
                info "Stopped app (pid $pid)."
            fi
            pkill -f "gunicorn app.main" 2>/dev/null || true
            pkill -f "uvicorn app.main" 2>/dev/null || true
            ;;
        *) warn "No installation mode recorded." ;;
    esac
}

status() {
    detect_docker; detect_python || true
    printf '%s\n' "Install mode : $(current_mode)"
    printf '%s\n' "Python       : ${PY:-not found}"
    printf '%s\n' "Docker/Podman: ${DOCKER:-unavailable}"
    printf '%s\n' "App port     : $(env_get APP_PORT || true)${APP_PORT:+ (env: $APP_PORT)}"
    case "$(current_mode)" in
        docker)
            if [ -n "$COMPOSE" ]; then compose_cmd ps 2>/dev/null || echo "  (stack not running)"; fi
            printf '%s\n' "Logs (docker) : ./logs/gunicorn-access.log, gunicorn-error.log, postgresql-*.log"
            ;;
        host-postgres|host-sqlite)
            local pid; pid="$(host_app_pid)"
            if [ -n "$pid" ]; then
                echo "  App is running (pid $pid)."
            elif pgrep -f "uvicorn app.main" >/dev/null 2>&1 || pgrep -f "gunicorn app.main" >/dev/null 2>&1; then
                echo "  App is running (pid file missing)."
            else
                echo "  App is NOT running."
            fi
            printf '%s\n' "Logs (host)   : $LOG_DIR/ (ipam-access.log, ipam-app.log)"
            ;;
    esac
}

uninstall() {
    warn "This will remove the installation. Your database is NOT wiped by default."
    confirm "Proceed?" || { info "Uninstall cancelled."; return; }
    case "$(current_mode)" in
        docker)
            if [ -n "$COMPOSE" ] && compose_cmd ps 2>/dev/null | grep -q running; then
                compose_cmd down
            fi
            if confirm "Also delete the Docker 'pgdata' volume (all data lost)?"; then
                compose_cmd down -v 2>/dev/null || true
            fi
            ;;
    esac
    if confirm "Remove the virtual environment, local SQLite DB and state file?" y; then
        rm -rf "$VENV_DIR"
        rm -f "$SCRIPT_DIR"/dev.db "$STATE_FILE"
        info "Removed venv/state."
    fi
    info "Uninstall complete. The .env file (with your SECRET_KEY) was left in place."
}

# --------------------------------------------------------------------------- #
# Docs (mkdocs) — local hosting
# --------------------------------------------------------------------------- #
docs_install() {
    [ -x "$(venv_py)" ] || { warn "No virtual environment; run an install option first (or set one up manually)."; return 1; }
    info "Installing documentation dependencies (mkdocs + material)..."
    "$(venv_py)" -m pip install --quiet -r "$SCRIPT_DIR/requirements-docs.txt" || die "pip install failed"
    info "Documentation dependencies ready."
}

docs_serve() {
    docs_install
    local port; port="${DOCS_PORT:-$(env_get DOCS_PORT || true)}"; port="${port:-8000}"
    info "Serving documentation at http://127.0.0.1:${port} (Ctrl+C to stop)"
    exec "$(venv_py)" -m mkdocs serve --dev-addr "127.0.0.1:${port}"
}

docs_build() {
    docs_install
    info "Building static site into ./site ..."
    "$(venv_py)" -m mkdocs build --strict
    local port; port="${DOCS_PORT:-$(env_get DOCS_PORT || true)}"; port="${port:-8000}"
    info "Built. Serve ./site with any static server, e.g.:"
    echo "  python3 -m http.server ${port} --directory site"
}

# --------------------------------------------------------------------------- #
# Check mode (non-interactive environment report)
# --------------------------------------------------------------------------- #
check() {
    detect_docker; detect_python || true
    printf '%s\n' "Working dir : $SCRIPT_DIR"
    printf '%s\n' "Python      : ${PY:-none (needs 3.12+)} ${PY:+-$("$PY" --version)}"
    printf '%s\n' "Container   : ${DOCKER:-none} (${COMPOSE:-compose unavailable})"
    printf '%s\n' "Install mode: $(current_mode)"
    printf '%s\n' "App port    : $(env_get APP_PORT || true); default 8076"
    printf '%s\n' "Docs port   : $(env_get DOCS_PORT || true); default 8000"
    if command -v psql >/dev/null 2>&1; then
        printf '%s\n' "psql        : available"
    else
        printf '%s\n' "psql        : not found (host Postgres bootstrap will be manual)"
    fi
    printf '%s\n' "VENV present: $([ -x "$(venv_py)" ] && echo yes || echo no)"
    printf '%s\n' ".env present: $([ -f "$ENV_FILE" ] && echo yes || echo no)"
}

# --------------------------------------------------------------------------- #
# Interactive menu
# --------------------------------------------------------------------------- #
menu() {
    while true; do
        printf '\n'
        printf '%s\n' "${C_BOLD}================ IPAM Manager ================${C_RESET}"
        printf '%s\n' "  Mode: ${C_GREEN}$(current_mode)${C_RESET}   App: ${C_GREEN}http://localhost:$(env_get APP_PORT || true)${C_RESET}"
        printf '%s\n' "──────────────────────────────────────────────"
        printf '%s\n' "${C_BOLD}Installation${C_RESET}"
        printf '%s\n' "  1) Docker Compose  — PostgreSQL 16 + app"
        printf '%s\n' "  2) Host + PostgreSQL — bare-metal app + DB"
        printf '%s\n' "  3) Host + SQLite    — quick local dev"
        printf '%s\n' "──────────────────────────────────────────────"
        printf '%s\n' "${C_BOLD}Management${C_RESET}"
        printf '%s\n' "  4) Create / reset an admin account"
        printf '%s\n' "  5) Run database migrations (alembic)"
        printf '%s\n' "  6) Start the app     (detached, logs → ./logs)"
        printf '%s\n' "  7) Stop the app / stack"
        printf '%s\n' "  8) Status"
        printf '%s\n' "  9) Uninstall"
        printf '%s\n' "──────────────────────────────────────────────"
        printf '%s\n' "${C_BOLD}Documentation (MkDocs)${C_RESET}"
        printf '%s\n' "  d) Serve locally     http://127.0.0.1:$(env_get DOCS_PORT || true)"
        printf '%s\n' "  b) Build static site (./site)"
        printf '%s\n' "──────────────────────────────────────────────"
        printf '%s\n' '  0) Exit'
        printf '%s'   "${C_BOLD}Choose [0-9/d/b]: ${C_RESET}"
        local choice; read -r choice || break
        case "$choice" in
            1) install_docker ;;
            2) install_host_postgres ;;
            3) install_host_sqlite ;;
            4) case "$(current_mode)" in docker) create_admin_compose;; *) create_admin_host;; esac ;;
            5) detect_python && [ -x "$(venv_py)" ] && "$(venv_py)" -m alembic upgrade head || warn "Not installed/available." ;;
            6) start_app ;;
            7) stop_app ;;
            8) status ;;
            9) uninstall ;;
            d|D) docs_serve ;;
            b|B) docs_build ;;
            0) echo; exit 0 ;;
            *) warn "Invalid choice." ;;
        esac
    done
}

# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
case "${1:-}" in
    check)         check ;;
    docker)        install_docker ;;
    host-postgres) install_host_postgres ;;
    host-sqlite)   install_host_sqlite ;;
    admin)         case "$(current_mode)" in docker) create_admin_compose;; *) create_admin_host;; esac ;;
    migrate)       detect_python && [ -x "$(venv_py)" ] && "$(venv_py)" -m alembic upgrade head || die "Not installed." ;;
    run)           run_app ;;
    start)         start_app ;;
    stop)          stop_app ;;
    status)        status ;;
    uninstall)     uninstall ;;
    docs)          docs_serve ;;
    docs-build)    docs_build ;;
    "")            menu ;;
    *)             echo "unknown command: $1"; echo "try: check|docker|host-postgres|host-sqlite|admin|migrate|run|start|stop|status|uninstall|docs|docs-build"; exit 1 ;;
esac