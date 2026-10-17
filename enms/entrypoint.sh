#!/bin/sh
# Token z zmiennej środowiskowej (plik .env), nie z linii poleceń compose; bez tokenu serwer nie startuje.
set -eu
if [ -z "${DWSIM_MCP_TOKEN:-}" ]; then
  echo "[dwsim-mcp] brak DWSIM_MCP_TOKEN; serwer bez tokenu nie startuje" >&2
  exit 1
fi
exec /opt/dwsim-mcp/dwsim-mcp --http --host 0.0.0.0 --port "${DWSIM_MCP_PORT:-5901}" --token "$DWSIM_MCP_TOKEN"
