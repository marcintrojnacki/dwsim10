# DWSIM MCP w infrastrukturze EnMS

Fork `DanWBR/dwsim10` z warstwą wdrożeniową EnMS. Kod autora zostaje bez zmian; nasze pliki to `enms/`,
`docker-compose.prod.yml`, `docker-compose.staging.yml`, `azure-pipelines.yml`, `.dockerignore`, `.env.example`,
`CLAUDE.md` i wpis `.env` w `.gitignore`.

## Remote'y i gałęzie

- `origin`: Azure DevOps `MT_AIProjects/_git/dwsim10` (pipeline, serwery klonują stąd).
- `github`: `github.com/marcintrojnacki/dwsim10` (fork).
- `upstream`: `github.com/DanWBR/dwsim10` (autor).
- `main` i `staging` są nasze; `master` śledzi autora.

Aktualizacja do nowej wersji autora:

```sh
git fetch upstream && git checkout master && git merge --ff-only upstream/master
git checkout main && git merge master
git ls-tree HEAD external/ReoGrid | awk '{print $3}' > enms/reogrid.sha   # gdy autor przesunie submoduł
git push origin master main && git push github master main
```

## Obraz

`enms/Dockerfile` buduje serwer ze źródeł (`dotnet publish tools/DWSIM.MCPServer`, self-contained) tak jak workflow
wydania autora, a następnie dokłada zabezpieczenia:

- użytkownik `dwsim` (uid 10001) zamiast root;
- token wymagany: `DWSIM_MCP_TOKEN` z `.env`, bez tokenu serwer nie startuje (`enms/entrypoint.sh`);
- system plików tylko do odczytu; serwer nie ogranicza ścieżek zapisu, więc zapis jest możliwy wyłącznie do `/data`
  (wolumen `dwsim_mcp_data`) i `/tmp`;
- port tylko na loopbacku hosta, aplikacje przez sieć `proxy` (`http://dwsim-mcp:5901/mcp`);
- `cap_drop: ALL`, `no-new-privileges`, limit 2 GB i 2 CPU.

Submoduł `external/ReoGrid` nie jest klonowany na serwerze; Dockerfile pobiera commit z `enms/reogrid.sha`.

## Wdrożenie

Jak każda aplikacja (developer-guide `enms/deployment.md`): push `staging` → .122, push `main` → .125 po zatwierdzeniu.
Etap `Test` buduje obraz i uruchamia `enms/smoke.py` (zdrowie z tokenem, odmowa bez tokenu, lista narzędzi,
bilans wody z tablicami IAPWS względem NIST, zapis do `/data`).

Pierwsze uruchomienie na serwerze (jednorazowo): klon do `/srv/dwsim-mcp` (staging: `/srv/staging/dwsim-mcp`),
pipeline `dwsim-mcp-deploy`. Tokeny są w `production.env.enc` i `staging.env.enc` (age, odbiorcy z
developer-guide `scripts/age-recipients.txt`); `deploy.sh` odszyfrowuje je do `.env`. Odczyt tokenu na Macu:
`age -d -i ~/.config/age/key.txt production.env.enc`. Port hosta 5911 (5900–5902 na .122 zajmuje VNC).

## Klient

```sh
curl -s -H "Authorization: Bearer $DWSIM_MCP_TOKEN" http://127.0.0.1:5911/health   # na serwerze; z sieci proxy: http://dwsim-mcp:5901
```

Wskazówki budowy schematów i pułapki narzędzi: repozytorium `~/aiprojects/dwsim-automation`.
