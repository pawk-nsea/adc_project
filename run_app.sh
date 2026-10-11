#!/usr/bin/env bash

set -euo pipefail

project_directory="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python_executable="${project_directory}/.venv/bin/python"
app_host="${ADC_APP_HOST:-127.0.0.1}"
app_port="${ADC_APP_PORT:-8000}"
reload_enabled="${ADC_APP_RELOAD:-true}"
open_browser="${ADC_APP_OPEN_BROWSER:-true}"
app_url="http://${app_host}:${app_port}/"
docs_url="http://${app_host}:${app_port}/docs"
health_url="http://${app_host}:${app_port}/health"

if [[ ! -x "${python_executable}" ]]; then
    echo "Project environment not found at ${project_directory}/.venv"
    echo "Create it and install the project first:"
    echo "  python3.13 -m venv .venv"
    echo "  .venv/bin/python -m pip install -e '.[dev]'"
    exit 1
fi

cd "${project_directory}"

if ! "${python_executable}" -c "import fastapi, uvicorn, chromadb, google.genai" 2>/dev/null; then
    echo "Project dependencies are incomplete. Install them with:"
    echo "  .venv/bin/python -m pip install -e '.[dev]'"
    exit 1
fi

if ! "${python_executable}" -c \
    "from app.config import Settings; raise SystemExit(0 if Settings().gemini_api_key else 1)"; then
    echo "Warning: ADC_GEMINI_API_KEY is not set in .env."
    echo "Health and upload will work, but /chat will return 503."
fi

echo "Starting Apex Global Policy Assistant"
echo "Web application:  ${app_url}"
echo "API documentation: ${docs_url}"
echo "Health check:      ${health_url}"
echo "Stop the server with Ctrl+C."

open_app_when_ready() {
    for _ in {1..40}; do
        if "${python_executable}" -c \
            "import sys, urllib.request; urllib.request.urlopen(sys.argv[1], timeout=1)" \
            "${health_url}" \
            >/dev/null 2>&1; then
            if ! xdg-open "${app_url}" >/dev/null 2>&1; then
                echo "Could not open the browser automatically. Open ${app_url} manually."
            fi
            return
        fi
        sleep 0.25
    done
    echo "The browser was not opened because the application did not become ready in time."
}

if [[ "${open_browser}" == "true" ]]; then
    if command -v xdg-open >/dev/null 2>&1; then
        open_app_when_ready &
    else
        echo "xdg-open is unavailable. Open ${app_url} manually."
    fi
fi

uvicorn_arguments=(
    "app.main:app"
    "--host" "${app_host}"
    "--port" "${app_port}"
)

if [[ "${reload_enabled}" == "true" ]]; then
    uvicorn_arguments+=("--reload")
fi

exec "${python_executable}" -m uvicorn "${uvicorn_arguments[@]}"
