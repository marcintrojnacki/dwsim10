# dwsim10 (EnMS)

Fork `DanWBR/dwsim10` (GPL 3). Wdrażamy wyłącznie serwer MCP `tools/DWSIM.MCPServer` jako kontener, jak każdą naszą
aplikację. Opis wdrożenia, remote'ów i aktualizacji od autora: `enms/README.md`.

- Kodu autora nie zmieniaj na `main`; poprawki serwera najpierw zgłoś autorowi, łatka lokalna tylko z decyzji prowadzącego.
- Nasze pliki: `enms/`, `docker-compose.prod.yml`, `docker-compose.staging.yml`, `azure-pipelines.yml`, `.dockerignore`,
  `.env.example`. `.env` nigdy w git (age: `production.env.enc`).
- Push na oba remote'y: `origin` (Azure, pipeline) i `github` (fork).
- Lokalnie: `docker build -f enms/Dockerfile -t dwsim-mcp:enms .`, potem `enms/smoke.py`.
