#!/usr/bin/env bash
# MoneyKata's developer front door. Run alone to list the commands.
set -euo pipefail

WEB="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$WEB")"
SERVER="$WEB/server"
TOOLS="$WEB/.tools"
# shellcheck source=pins
source "$WEB/pins"
unset VIRTUAL_ENV

usage() {
  cat <<'USAGE'
web/dev.sh <command>

  setup        install the Python environment (uv), Deno and Playwright's Chromium,
               and unpack the vendored browser libraries
  run [args]   run the dev server (moneykata dev): https://localhost:37373
               --seed  seed users and a year of data    --stubs  stub price source
               --peer  a second server on another port, for links
               --listen ADDR  --hostname NAME  --port N  --data DIR
                       for testing from another machine: see web/dev.md
  test [args]  run pytest (arguments pass through)
  check        run every check: what CI runs (web/check)
  mail         list the emails dev mode has written
  mockup       rebuild docs/mockups/MoneyKata-app.html from the app
  help-shots   rebuild the help guides' screenshots from the mockup
  deno [args]  run the pinned Deno
USAGE
}

deno_bin() { echo "$TOOLS/deno-$DENO_VERSION/deno"; }

setup_deno() {
  local bin arch sum zip
  bin="$(deno_bin)"
  [[ -x "$bin" ]] && return 0
  arch="$(uname -m)"
  case "$arch" in
    x86_64) sum="$DENO_SHA256_x86_64" ;;
    aarch64 | arm64) arch=aarch64; sum="$DENO_SHA256_aarch64" ;;
    *) echo "no pinned Deno for $arch" >&2; return 1 ;;
  esac
  mkdir -p "$(dirname "$bin")"
  zip="$(dirname "$bin")/deno.zip"
  curl -fsSL -o "$zip" \
    "https://github.com/denoland/deno/releases/download/v$DENO_VERSION/deno-$arch-unknown-linux-gnu.zip"
  echo "$sum  $zip" | sha256sum -c --quiet -
  python3 -c 'import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extract("deno", sys.argv[2])' \
    "$zip" "$(dirname "$bin")"
  chmod 0755 "$bin"
  rm -f "$zip"
}

setup_playwright() {
  (cd "$SERVER" && uv run --frozen playwright install chromium-headless-shell >/dev/null)
  local dir="${PLAYWRIGHT_BROWSERS_PATH:-$HOME/.cache/ms-playwright}"
  if [[ ! -d "$dir/chromium_headless_shell-$PLAYWRIGHT_CHROMIUM_REVISION" ]]; then
    echo "Playwright installed a Chromium other than revision $PLAYWRIGHT_CHROMIUM_REVISION;" \
      "update PLAYWRIGHT_CHROMIUM_REVISION in web/pins" >&2
    return 1
  fi
}

cmd="${1:-}"
[[ $# -gt 0 ]] && shift
case "$cmd" in
  setup)
    (cd "$SERVER" && uv sync --frozen)
    python3 "$WEB/ui/vendor/vendor.py" extract
    setup_deno
    setup_playwright
    echo "ready: web/dev.sh run --seed --stubs"
    ;;
  run)
    python3 "$WEB/ui/vendor/vendor.py" extract
    # The server runs from web/server, so a --data path is made absolute from here first.
    args=()
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --data) args+=(--data "$(realpath -m -- "$2")"); shift 2 ;;
        --data=*) args+=(--data "$(realpath -m -- "${1#--data=}")"); shift ;;
        *) args+=("$1"); shift ;;
      esac
    done
    cd "$SERVER" && exec uv run --frozen moneykata dev "${args[@]}"
    ;;
  test)
    cd "$SERVER" && exec uv run --frozen pytest "$@"
    ;;
  check)
    exec "$WEB/check" "$@"
    ;;
  mail)
    ls -1t "$WEB/.dev/mail" 2>/dev/null || echo "no mail yet"
    ;;
  mockup)
    cd "$SERVER" && exec uv run --frozen python "$WEB/ui/mockup/build.py"
    ;;
  help-shots)
    cd "$SERVER" && exec uv run --frozen python "$WEB/ui/mockup/help_shots.py" "$@"
    ;;
  deno)
    setup_deno
    exec "$(deno_bin)" "$@"
    ;;
  *)
    usage
    ;;
esac
