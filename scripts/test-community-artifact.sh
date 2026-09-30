#!/bin/sh
set -eu

repository=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
output=${ARTIFACT_DIR:-"$repository/dist"}
community_output="$output/community"
environment=$(mktemp -d /tmp/radiusdeck-community-artifact.XXXXXX)
trap 'rm -rf "$environment"' EXIT INT TERM

python_command=${PYTHON:-python}
if [ -z "${PYTHON:-}" ] && [ -x "$repository/.venv/bin/python" ]; then
  python_command="$repository/.venv/bin/python"
fi

rm -rf "$community_output"
mkdir -p "$community_output"
"$python_command" -m pip wheel --no-deps --no-cache-dir \
  "$repository" --wheel-dir "$community_output"
wheel=$(find "$community_output" -maxdepth 1 -type f -name 'radiusdeck-*.whl' -print)
test -n "$wheel"
"$python_command" "$repository/scripts/artifact_checks.py" \
  inspect-community-wheel "$wheel"

"$python_command" -m venv "$environment/venv"
"$environment/venv/bin/pip" install "$wheel" pytest pytest-asyncio
cd /tmp
PYTHONPATH= "$environment/venv/bin/python" \
  "$repository/scripts/artifact_checks.py" installed-manifest \
  "$community_output/community-installed-manifest.json"
cp "$repository/tests/artifact_smoke.py" "$environment/community_smoke.py"
PYTHONPATH= "$environment/venv/bin/python" "$environment/community_smoke.py"

mkdir -p "$environment/tests"
cp "$repository/tests/__init__.py" "$environment/tests/__init__.py"
for test_file in \
  test_backup_mutations.py test_backup_status.py test_backup_store.py \
  test_community_safety.py test_log_file_store.py test_status_service.py; do
  cp "$repository/tests/$test_file" "$environment/tests/$test_file"
done
cp "$repository/tests/conftest.py" "$environment/tests/conftest.py"
cd "$environment"
PYTHONPATH= "$environment/venv/bin/python" -m pytest tests -q

echo "Community artifact gate passed: $wheel"
