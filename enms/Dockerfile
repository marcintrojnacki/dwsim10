# syntax=docker/dockerfile:1
# Serwer DWSIM MCP (headless) budowany ze źródeł tego repozytorium.
# Odpowiednik packaging/docker/Dockerfile autora, z budową w obrazie i zabezpieczeniami EnMS:
# użytkownik bez uprawnień, token z pliku .env, zapis tylko do /data i /tmp (compose: read_only).

FROM mcr.microsoft.com/dotnet/sdk:10.0-noble AS build
ARG TARGETARCH
ARG REOGRID_REPO=https://github.com/DanWBR/ReoGrid.git
WORKDIR /src
COPY . .
# Submoduł ReoGrid: serwer na .125 klonuje repo bez submodułów, więc pobieramy przypięty commit.
RUN if [ ! -f external/ReoGrid/ReoGrid/ReoGridAvalonia.csproj ]; then \
      rm -rf external/ReoGrid && git init -q external/ReoGrid \
      && git -C external/ReoGrid fetch -q --depth 1 "$REOGRID_REPO" "$(cat enms/reogrid.sha)" \
      && git -C external/ReoGrid checkout -q FETCH_HEAD; \
    fi
RUN case "$TARGETARCH" in amd64) rid=linux-x64 ;; arm64) rid=linux-arm64 ;; *) echo "brak RID dla $TARGETARCH"; exit 1 ;; esac \
 && dotnet publish tools/DWSIM.MCPServer/DWSIM.MCPServer.csproj -c Release -r "$rid" --self-contained true \
      -p:CoolPropRid="$rid" -o /out \
 && find /out -name '*.dylib' -delete

FROM mcr.microsoft.com/dotnet/runtime-deps:10.0-noble
# SkiaSharp potrzebuje fontconfig; curl do healthchecku.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libfontconfig1 curl \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --uid 10001 --create-home --home-dir /home/dwsim --shell /usr/sbin/nologin dwsim \
 && mkdir -p /data && chown dwsim:dwsim /data
WORKDIR /opt/dwsim-mcp
COPY --from=build /out/ ./
COPY enms/entrypoint.sh /usr/local/bin/dwsim-mcp-start
RUN chmod 755 /opt/dwsim-mcp/dwsim-mcp /usr/local/bin/dwsim-mcp-start
USER dwsim
ENV HOME=/home/dwsim DOTNET_CLI_TELEMETRY_OPTOUT=1
EXPOSE 5901
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD curl -sf -H "Authorization: Bearer ${DWSIM_MCP_TOKEN}" http://127.0.0.1:5901/health || exit 1
ENTRYPOINT ["/usr/local/bin/dwsim-mcp-start"]
