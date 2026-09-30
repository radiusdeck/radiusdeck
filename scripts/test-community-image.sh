#!/bin/sh
set -eu

repository=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
output=${ARTIFACT_DIR:-"$repository/dist"}
image=${COMMUNITY_IMAGE:-radiusdeck-community:artifact-test}
container="radiusdeck-community-smoke-$$"
exported=$(mktemp /tmp/radiusdeck-community-image.XXXXXX.tar)
created=

python_command=${PYTHON:-python}
if [ -z "${PYTHON:-}" ] && [ -x "$repository/.venv/bin/python" ]; then
  python_command="$repository/.venv/bin/python"
fi

cleanup() {
  docker rm -f "$container" >/dev/null 2>&1 || true
  if [ -n "$created" ]; then
    docker rm "$created" >/dev/null 2>&1 || true
  fi
  rm -f "$exported"
}
trap cleanup EXIT INT TERM

if [ "${SKIP_ARTIFACT_TEST:-false}" != "true" ]; then
  ARTIFACT_DIR="$output" "$repository/scripts/test-community-artifact.sh"
fi

wheel=$(find "$output/community" -maxdepth 1 -type f -name 'radiusdeck-*.whl' -print)
test -n "$wheel"
version=$("$python_command" -c \
  'import pathlib,sys,zipfile; p=pathlib.Path(sys.argv[1]); z=zipfile.ZipFile(p); n=next(x for x in z.namelist() if x.endswith(".dist-info/METADATA")); print(next(line.split(": ",1)[1] for line in z.read(n).decode().splitlines() if line.startswith("Version: ")))' \
  "$wheel")
wheel_sha=$("$python_command" -c \
  'import hashlib,pathlib,sys; print(hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest())' \
  "$wheel")

docker build \
  --build-arg "COMMUNITY_VERSION=$version" \
  --build-arg "COMMUNITY_WHEEL_SHA256=$wheel_sha" \
  --tag "$image" \
  --file "$repository/Dockerfile" "$repository"

test "$(docker image inspect --format '{{.Config.User}}' "$image")" = "10001:10001"
test "$(docker image inspect --format '{{index .Config.Labels "org.radiusdeck.community-wheel-sha256"}}' "$image")" = "$wheel_sha"

created=$(docker create "$image")
docker export --output "$exported" "$created"
if tar -tf "$exported" | grep -E '(^|/)radiusdeck_pro(/|\.|$)|(^|/)pro/' >/dev/null; then
  echo "Community image contains a forbidden Pro path" >&2
  exit 1
fi

docker run --rm \
  --volume "$repository/tests/artifact_smoke.py:/tmp/artifact_smoke.py:ro" \
  --entrypoint python "$image" /tmp/artifact_smoke.py

docker run --detach --name "$container" \
  --env APP_ENV=test \
  --env APP_AUTH_METHOD=none \
  --env APP_RADIUS_CLIENTS_PATH=/tmp/clients.conf \
  --env APP_BACKUP_DIR=/tmp/backups \
  --entrypoint /bin/sh "$image" -c \
  'printf "client localhost {\n ipaddr = 127.0.0.1\n secret = test\n}\n" > /tmp/clients.conf; exec radiusdeck serve --host 0.0.0.0 --port 8000' \
  >/dev/null

attempt=0
until docker exec "$container" python -c \
  "import urllib.request; assert urllib.request.urlopen('http://127.0.0.1:8000/health').status == 200" \
  >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 30 ]; then
    docker logs "$container" >&2
    exit 1
  fi
  sleep 1
done

docker exec "$container" python -c \
  "import urllib.error,urllib.request
try:
    urllib.request.urlopen('http://127.0.0.1:8000/api/v1/clients/')
except urllib.error.HTTPError as error:
    assert error.code == 404
else:
    raise AssertionError('Community image exposed /api/v1')"

echo "Community image purity gate passed: $image"
