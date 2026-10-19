#!/usr/bin/env bash
# Build both images for one platform and run them once, as the release gate asks
# (requirements S17.8.1, S17.9.7.8): the server refuses a keyring it can't read; starts
# uninitialised, locked down as compose runs it, and alive to its health check; makes its key
# and first admin through the welcome's routes; stops cleanly, starts again locked, is unlocked
# with `keys unlock`, answers /healthz and a sign-in, reads a receipt, and stops cleanly; the
# connector refuses to start without a vault, then serves, unlocks and stops.
#
#   web/install/smoke.sh                 the host's own platform
#   web/install/smoke.sh linux/arm64     under QEMU: docker run --privileged --rm \
#                                            tonistiigi/binfmt --install arm64   (once)
#
# Images are tagged moneykata:<version>-smoke and moneykata-connector:<version>-smoke.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLATFORM="${1:-}"
VERSION="$(cat "$ROOT/web/VERSION")"
TAG="$VERSION-smoke"
PF=()
[[ -n "$PLATFORM" ]] && PF=(--platform "$PLATFORM")
WORK="$(mktemp -d)"
cleanup() {
  docker rm -f mk-smoke mkc-smoke >/dev/null 2>&1 || true
  docker volume rm -f mkc-smoke >/dev/null 2>&1 || true
  # The server's files belong to uid 10001: removed as root, inside a container.
  docker run --rm --user 0:0 -v "$WORK:/w" --entrypoint sh "moneykata:$TAG" -c 'rm -rf /w/*' >/dev/null 2>&1 || true
  rm -rf "$WORK"
}
trap cleanup EXIT

echo "== building for ${PLATFORM:-this host}"
docker buildx build "${PF[@]}" -q -f "$ROOT/web/install/Dockerfile" -t "moneykata:$TAG" --load "$ROOT" >/dev/null
docker buildx build "${PF[@]}" -q -f "$ROOT/connector/Dockerfile" -t "moneykata-connector:$TAG" --load "$ROOT/connector" >/dev/null

mkdir -p "$WORK/data" "$WORK/backups"
chmod 777 "$WORK/data" "$WORK/backups"
cp "$ROOT/web/install/moneykata.toml" "$WORK/"
MOUNTS=(-v "$WORK/data:/var/lib/moneykata" -v "$WORK/backups:/var/backups/moneykata"
  -v "$WORK/moneykata.toml:/etc/moneykata.toml:ro")
LOCKED=(--read-only --tmpfs /tmp --cap-drop ALL --security-opt no-new-privileges:true)
# The server's host-command socket (S13.6), on a tmpfs of its account as compose.yaml has it.
SOCK=(--tmpfs /run/moneykata:uid=10001,gid=10001,mode=0700)

URL=http://127.0.0.1:37399
JSON=(-H "Origin: $URL" -H 'Content-Type: application/json')
# Wait until /healthz answers with this status, at most this many seconds.
wait_for() {
  for i in $(seq 1 "$2"); do
    [[ "$(curl -s "$URL/healthz" || true)" == *"\"$1\""* ]] && return 0
    sleep 1
  done
  echo "FAILED: /healthz never answered $1"
  docker logs mk-smoke 2>&1 | tail -20
  exit 1
}
post() { curl -s -o /dev/null -w '%{http_code}' -X POST "${JSON[@]}" -d "$2" "$URL$1"; }

echo "== the server: a refused start, with a keyring it can't read (exit 78)"
echo "not a keyring" > "$WORK/data/keyring"
set +e
docker run --rm "${PF[@]}" "${LOCKED[@]}" "${SOCK[@]}" "${MOUNTS[@]}" "moneykata:$TAG" >/dev/null 2>&1
[[ $? -eq 78 ]] || { echo "FAILED: expected exit 78"; exit 1; }
set -e
rm -f "$WORK/data/keyring"
echo "== the server: new, uninitialised; the welcome makes its key and its first admin"
docker run -d --name mk-smoke "${PF[@]}" "${LOCKED[@]}" "${SOCK[@]}" "${MOUNTS[@]}" \
  -p 127.0.0.1:37399:37373 "moneykata:$TAG" >/dev/null
wait_for uninitialised 240
echo "   uninitialised after ${i}s"
docker exec mk-smoke moneykata health >/dev/null || { echo "FAILED: not alive while uninitialised"; exit 1; }
OFFER="$(curl -s -X POST "${JSON[@]}" "$URL/ui/api/welcome/phrase")"
PHRASE="$(printf '%s' "$OFFER" | python3 -c 'import json, sys; print(" ".join(json.load(sys.stdin)["words"]))')"
BACK="$(printf '%s' "$OFFER" | python3 -c 'import json, sys
o = json.load(sys.stdin)
print(json.dumps({"token": o["token"], "words": {str(n): o["words"][n - 1] for n in o["check"]}}))')"
code="$(post /ui/api/welcome/key "$BACK")"
[[ "$code" == 200 ]] || { echo "FAILED: the key answered $code"; exit 1; }
wait_for ok 60
code="$(post /ui/api/welcome/admin '{"displayName":"Smoke Test","sex":"female","email":"smoke@example.org","password":"a long smoke passphrase"}')"
[[ "$code" == 200 ]] || { echo "FAILED: the first admin answered $code"; exit 1; }
echo "   key made, unlocked, first admin set up"
docker stop -t 10 mk-smoke >/dev/null
[[ "$(docker inspect mk-smoke --format '{{.State.ExitCode}}')" == 0 ]] || { echo "FAILED: unclean stop"; exit 1; }
echo "   stopped cleanly"
echo "== the server: restarted, locked; the phrase opens it from the host; sign-in, stop"
docker start mk-smoke >/dev/null
wait_for locked 240
echo "   locked after ${i}s"
docker exec mk-smoke moneykata health >/dev/null || { echo "FAILED: not alive while locked"; exit 1; }
echo "$PHRASE" | docker exec -i mk-smoke moneykata keys unlock >/dev/null
wait_for ok 60
echo "   unlocked and healthy"
code="$(post /ui/api/session '{"login":"admin","password":"a long smoke passphrase"}')"
[[ "$code" == 200 ]] || { echo "FAILED: sign-in answered $code"; exit 1; }
echo "   signed in"
docker stop -t 10 mk-smoke >/dev/null
[[ "$(docker inspect mk-smoke --format '{{.State.ExitCode}}')" == 0 ]] || { echo "FAILED: unclean stop"; exit 1; }
echo "   stopped cleanly"
echo "== the server: a receipt read"
docker run --rm "${PF[@]}" "${LOCKED[@]}" --entrypoint python "moneykata:$TAG" -c '
import io
from PIL import Image, ImageDraw
from moneykata.receipts import ocr
img = Image.new("L", (600, 300), 255); ImageDraw.Draw(img).text((20, 20), "TOTAL 12.34", fill=0)
b = io.BytesIO(); img.save(b, "PNG")
r = ocr.read(b.getvalue(), "image/png"); assert r.lines, "nothing read"; print("   read", r.method)'

echo "== the connector: a refused start without a vault (exit 78)"
docker volume create mkc-smoke >/dev/null
CM=(-v mkc-smoke:/var/lib/moneykata-connector --tmpfs /run/moneykata-connector:uid=10002,gid=10002,mode=0700)
set +e
docker run --rm "${PF[@]}" "${LOCKED[@]}" "${CM[@]}" "moneykata-connector:$TAG" >/dev/null 2>&1
[[ $? -eq 78 ]] || { echo "FAILED: expected exit 78"; exit 1; }
set -e
echo "== the connector: vault, serve, unlock, stop"
WORDS="$(docker run --rm "${PF[@]}" "${LOCKED[@]}" "${CM[@]}" --entrypoint python "moneykata-connector:$TAG" -c \
  'from moneykata_connector.vault import Vault; from pathlib import Path
print(" ".join(Vault(Path("/var/lib/moneykata-connector/vault.json")).create()))')"
docker run -d --name mkc-smoke "${PF[@]}" "${LOCKED[@]}" "${CM[@]}" "moneykata-connector:$TAG" >/dev/null
for i in $(seq 1 60); do docker exec mkc-smoke moneykata-connector status >/dev/null 2>&1 && break; sleep 1; done
echo "$WORDS" | docker exec -i mkc-smoke moneykata-connector unlock >/dev/null 2>&1
docker exec mkc-smoke moneykata-connector status | grep -q "locked: False" || { echo "FAILED: not unlocked"; exit 1; }
echo "   unlocked after ${i}s"
docker stop -t 10 mkc-smoke >/dev/null
[[ "$(docker inspect mkc-smoke --format '{{.State.ExitCode}}')" == 0 ]] || { echo "FAILED: unclean stop"; exit 1; }
echo "   stopped cleanly"
echo "smoke passed for ${PLATFORM:-this host}: moneykata:$TAG, moneykata-connector:$TAG"
