#!/usr/bin/env bash
# Tries MoolaKata's two TrueNAS catalog apps (requirements S17.8.3.1): each test case is
# rendered by TrueNAS's own renderer, in a checkout of their catalog, then started with Docker,
# and what came up is looked at: the server's /healthz or the connector's status, the account
# each runs as, a read-only root unless a certificate is chosen, and the certificate each page
# serves. The connector's install must also stop when it has no address. Needs docker with
# compose, jq, openssl, curl, git, python3 with PyYAML, and the network, for the catalog and
# the images.
#
#   publish/truenas/check.sh                       both apps, every test case
#   publish/truenas/check.sh moolakata             one app
#   publish/truenas/check.sh moolakata https       one case
#
# TRUENAS_APPS names the catalog checkout (web/.dev/truenas-apps by default); it is brought up
# to date with TrueNAS's master at each run, and only ix-dev/community changes in it.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
CATALOG="${TRUENAS_APPS:-$ROOT/web/.dev/truenas-apps}"
UPSTREAM="https://github.com/truenas/apps.git"
APPS=(moolakata moolakata-connector)
CASES=(basic https hostnet)

say() { printf '== %s\n' "$*"; }
fail() {
  printf 'FAILED: %s\n' "$*" >&2
  exit 1
}

catalog() {
  if [[ -d "$CATALOG/.git" ]]; then
    git -C "$CATALOG" fetch --quiet --depth 1 origin master
    git -C "$CATALOG" checkout --quiet --force --detach FETCH_HEAD
    git -C "$CATALOG" clean --quiet -fdx ix-dev/community
  else
    mkdir -p "$(dirname "$CATALOG")"
    git clone --quiet --depth 1 "$UPSTREAM" "$CATALOG"
  fi
  say "TrueNAS's catalog at $(git -C "$CATALOG" log -1 --format='%h, %cs')"
}

# A value from one of an app's YAML files: value <file> <python expression on d>.
value() { python3 -c 'import sys, yaml; d = yaml.safe_load(open(sys.argv[1])); print(eval(sys.argv[2]))' "$@"; }

# What a page's certificate names: its subject and its alternative names.
names() {
  openssl s_client -connect "127.0.0.1:$1" </dev/null 2>/dev/null |
    openssl x509 -noout -subject -ext subjectAltName 2>/dev/null
}

try() {
  local app="$1" case="$2" dir="$CATALOG/ix-dev/community/$1"
  local values="$dir/templates/test_values/$case-values.yaml"
  [[ -f "$values" ]] || fail "$app has no $case-values.yaml"
  say "$app, $case"
  # A folder of the run's own for the datasets, so each case starts from nothing.
  local run
  run="$(mktemp -d "${TMPDIR:-/tmp}/truenas-check.XXXXXX")"
  sed "s#/opt/tests/mnt/#$run/#" "$values" >"$dir/templates/test_values/check-values.yaml"
  if ! (cd "$CATALOG" && python3 .github/scripts/ci.py --app "$app" --train community \
    --test-file check-values.yaml --render-only=true >"$run/render.log" 2>&1); then
    cat "$run/render.log"
    fail "$app, $case: TrueNAS's renderer refused it"
  fi
  local compose=(docker compose -p "check-$app-$case" -f "$dir/templates/rendered/docker-compose.yaml")
  local service image port cert
  service="$(value "$dir/ix_values.yaml" "[v for k, v in d['consts'].items() if k.endswith('_container_name') and not k.startswith('perms')][0]")"
  image="$(value "$dir/ix_values.yaml" "d['images']['image']['repository'] + ':' + d['images']['image']['tag']")"
  port="$(value "$values" "d['network']['web_port']['port_number']")"
  cert="$(value "$values" "d['network'].get('certificate_id') or ''")"
  local ok=1
  if ! "${compose[@]}" up --detach --quiet-pull --wait --wait-timeout 300; then
    ok=0
  else
    local id
    id="$("${compose[@]}" ps -q "$service")"
    local user rootfs
    user="$(docker inspect -f '{{.Config.User}}' "$id")"
    rootfs="$(docker inspect -f '{{.HostConfig.ReadonlyRootfs}}' "$id")"
    [[ "$user" == "$(value "$dir/ix_values.yaml" "'%(run_as_user)s:%(run_as_group)s' % d['consts']")" ]] ||
      { echo "runs as $user"; ok=0; }
    [[ "$rootfs" == "$([[ -n "$cert" ]] && echo false || echo true)" ]] ||
      { echo "read-only root: $rootfs"; ok=0; }
    if [[ "$app" == moolakata ]]; then
      local health
      health="$(curl -sk "https://127.0.0.1:$port/healthz" || true)"
      [[ "$health" == *'"uninitialised"'* ]] || { echo "/healthz: $health"; ok=0; }
    else
      docker exec "$id" moolakata-connector status | grep -q "vault: None" || { echo "a vault before its welcome"; ok=0; }
      [[ "$(curl -sk -o /dev/null -w '%{http_code}' "https://127.0.0.1:$port/")" == 200 ]] || { echo "its page did not answer"; ok=0; }
    fi
    local served
    served="$(names "$port")"
    if [[ -n "$cert" ]]; then
      [[ "$served" == *"CN=moolakata.test"* || "$served" == *"CN = moolakata.test"* ]] ||
        { echo "serves $served, not the chosen certificate"; ok=0; }
    else
      [[ "$served" == *"192.168.1.20"* && "$served" == *"moolakata.local"* ]] ||
        { echo "its own certificate names $served"; ok=0; }
    fi
  fi
  [[ "$ok" == 1 ]] || "${compose[@]}" logs --no-color | tail -n 40
  "${compose[@]}" down --volumes --remove-orphans --timeout 20 >/dev/null 2>&1 || true
  # The datasets belong to the app's account by now: removed as root, by its own image.
  docker run --rm --user 0:0 --network none --entrypoint find -v "$run:/run-dir" "$image" \
    /run-dir -mindepth 1 -delete >/dev/null 2>&1 || true
  rm -rf "$run" "$dir/templates/test_values/check-values.yaml" || true
  [[ "$ok" == 1 ]] || fail "$app, $case"
}

# The connector's install stops when it is given no address, and says why.
refused() {
  local app=moolakata-connector dir="$CATALOG/ix-dev/community/moolakata-connector" out
  say "$app, no address"
  python3 - "$dir/templates/test_values/basic-values.yaml" "$dir/templates/test_values/check-values.yaml" <<'PY'
import sys, yaml
values = yaml.safe_load(open(sys.argv[1]))
values["moolakata_connector"]["names"] = []
yaml.safe_dump(values, open(sys.argv[2], "w"))
PY
  local stopped=0
  out="$(cd "$CATALOG" && python3 .github/scripts/ci.py --app "$app" --train community \
    --test-file check-values.yaml --render-only=true 2>&1)" || stopped=1
  rm -f "$dir/templates/test_values/check-values.yaml"
  [[ "$stopped" == 1 ]] || fail "$app: rendered with no address"
  [[ "$out" == *"Add at least one Page Address"* ]] ||
    { echo "$out" | tail -n 20; fail "$app: refused, but not for its address"; }
}

main() {
  local apps=("${APPS[@]}") cases=("${CASES[@]}")
  [[ $# -ge 1 ]] && apps=("$1")
  [[ $# -ge 2 ]] && cases=("$2")
  for cmd in docker jq openssl curl git python3; do
    command -v "$cmd" >/dev/null || fail "needs $cmd"
  done
  python3 -c 'import yaml' 2>/dev/null || fail "needs PyYAML for python3"
  catalog
  for app in "${apps[@]}"; do
    [[ -d "$HERE/$app" ]] || fail "no app $app"
    rm -rf "$CATALOG/ix-dev/community/$app"
    cp -r "$HERE/$app" "$CATALOG/ix-dev/community/$app"
    for case in "${cases[@]}"; do try "$app" "$case"; done
    [[ "$app" != moolakata-connector || $# -ge 2 ]] || refused
  done
  (cd "$CATALOG" && python3 .github/scripts/port_validation.py >/dev/null) ||
    fail "a default port the catalog already uses"
  say "all cases passed"
}

main "$@"
