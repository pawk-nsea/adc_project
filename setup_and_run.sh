#!/usr/bin/env bash
# Prepare the local Python environment and optional API key, then launch the app.

set -euo pipefail

project_directory="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
venv_python="${project_directory}/.venv/bin/python"

find_supported_python() {
    local candidate
    for candidate in python3.13 python3.12 python3.11 python3; do
        if command -v "${candidate}" >/dev/null 2>&1 \
            && "${candidate}" -c \
                'import sys; raise SystemExit(0 if (3, 11) <= sys.version_info[:2] < (3, 14) else 1)' \
                >/dev/null 2>&1; then
            printf '%s\n' "${candidate}"
            return 0
        fi
    done
    return 1
}

configure_local_key() {
    local key source_file temporary_file

    if [[ -n "${ADC_GEMINI_API_KEY:-}" ]]; then
        return
    fi

    if [[ -f "${project_directory}/.env" ]] \
        && grep -Eq '^ADC_GEMINI_API_KEY=.+$' "${project_directory}/.env"; then
        return
    fi

    if [[ ! -t 0 ]]; then
        echo "ADC_GEMINI_API_KEY is missing. Add it to .env before using chat."
        return
    fi

    echo
    echo "A Gemini API key is needed for chat. It stays only in your ignored local .env file."
    read -r -s -p "Gemini API key (press Enter to skip): " key
    echo

    if [[ -z "${key}" ]]; then
        echo "No key saved. Upload works, but chat will return 503 until a key is configured."
        return
    fi

    if [[ ! "${key}" =~ ^[A-Za-z0-9._-]+$ ]]; then
        echo "The key contains unexpected characters and was not saved."
        exit 1
    fi

    source_file="${project_directory}/.env.example"
    if [[ -f "${project_directory}/.env" ]]; then
        source_file="${project_directory}/.env"
    fi

    temporary_file="$(mktemp "${project_directory}/.env.tmp.XXXXXX")"
    trap 'rm -f "${temporary_file:-}"' RETURN
    umask 077

    while IFS= read -r line || [[ -n "${line}" ]]; do
        if [[ "${line}" == ADC_GEMINI_API_KEY=* ]]; then
            printf 'ADC_GEMINI_API_KEY=%s\n' "${key}"
        else
            printf '%s\n' "${line}"
        fi
    done < "${source_file}" > "${temporary_file}"

    mv "${temporary_file}" "${project_directory}/.env"
    trap - RETURN
    echo "Gemini key saved locally in .env (ignored by Git)."
}

cd "${project_directory}"

if [[ ! -x "${venv_python}" ]]; then
    if ! system_python="$(find_supported_python)"; then
        echo "Python 3.11, 3.12, or 3.13 is required."
        exit 1
    fi

    echo "Creating .venv with ${system_python}..."
    "${system_python}" -m venv .venv
fi

echo "Installing the application dependencies..."
"${venv_python}" -m pip install -e .

configure_local_key

exec "${project_directory}/run_app.sh"
