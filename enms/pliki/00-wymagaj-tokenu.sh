#!/bin/sh
# Bez tokenu mapa w szablonie przepuściłaby nagłówek „Bearer ” z pustą wartością: kontener nie startuje.
if [ -z "${DWSIM_MCP_TOKEN:-}" ]; then
  echo "[dwsim-mcp-pliki] brak DWSIM_MCP_TOKEN; kontener nie startuje" >&2
  exit 1
fi
