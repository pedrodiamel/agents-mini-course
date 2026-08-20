# Configurando o servidor MCP em cada ambiente

O servidor da [aula 06](../books/aula_06_mcp.ipynb) roda **dentro do container**, e todos os
clientes aqui são de **host** (navegador, VS Code, Claude Code). A ponte entre os dois é sempre a
mesma ideia: `docker exec -i` *é* o transporte stdio — o cliente lança o `docker` no host e o
`stdin`/`stdout` atravessam até o processo Python no container.

Sumário: [pré-requisitos](#0--pré-requisitos) · [notebook](#1--notebook-cliente-python) ·
[Inspector](#2--mcp-inspector) · [VS Code](#3--vs-code) · [Claude Code](#4--claude-code) ·
[Claude Desktop](#5--claude-desktop) · [erros comuns](#erros-comuns)

---

## 0 — Pré-requisitos

**Container de pé.** Sem ele, todo `docker exec` falha:

```bash
make docker-build              # primeira vez (ou após mudar o requirements.txt)
docker start agents-mini-course
docker ps --filter name=agents-mini-course
```

**Versão certa do `mcp`.** A aula usa a API `FastMCP`, que só existe no `mcp` 1.x — o
`requirements.txt` fixa `mcp>=1.7.1,<2.0`:

```bash
docker exec agents-mini-course python -c \
  "from mcp.server.fastmcp import FastMCP; from importlib.metadata import version; print(version('mcp'))"
```

**`server.py` gerado.** Ele nasce do `%%writefile` da seção 3 do notebook:

```bash
docker exec -w /app/books agents-mini-course ls -l mcp_demo/server.py
```

**Chave da OpenWeatherMap no `.env`** da raiz do repo. O `server.py` faz `load_dotenv` e lê o
`/app/.env`, que é o bind mount desse arquivo — por isso **nenhuma** config de cliente abaixo
precisa repetir a chave.

---

## 1 — Notebook (cliente Python)

Não tem configuração: as seções 4 e 5 do notebook sobem o servidor como subprocesso via
`StdioServerParameters`, tudo dentro do container. É o caminho para entender o protocolo antes de
plugar em qualquer cliente.

```python
SERVER = StdioServerParameters(command="python", args=["mcp_demo/server.py"])
```

---

## 2 — MCP Inspector

Interface web para listar e chamar tools na mão. Rode a partir de `books/`, **dentro do
container**:

```bash
make docker-start                                       # abre um bash no container
cd books
npx @modelcontextprotocol/inspector --config mcp_demo/inspector.json --server weather
```

Abra no navegador do host **exatamente a URL que ele imprime**, com o token:

```text
http://localhost:6274?MCP_INSPECTOR_API_TOKEN=<token>
```

Três coisas que costumam dar errado aqui:

- **A porta é a 6274**, a UI. A `6275` é só o sandbox de MCP Apps, e a `6277` não existe mais —
  era o proxy do Inspector 1.x.
- **O bind.** Por padrão o Inspector escuta só em `127.0.0.1` *dentro* do container, o que é
  inalcançável do host mesmo com a porta publicada. E ele se recusa a abrir em todas as interfaces
  sem override explícito. As duas variáveis já estão no [docker-compose.yml](../docker-compose.yml):

  ```yaml
  environment:
    - HOST=0.0.0.0
    - DANGEROUSLY_BIND_ALL_INTERFACES=true
  ports:
    - "127.0.0.1:6274:6274"
    - "127.0.0.1:6275:6275"
  ```

  O `DANGEROUSLY_` é aceitável porque as portas são publicadas só no loopback do host — nada vaza
  para a rede local.
- **O `Opening browser...` não abre nada.** Não existe navegador no container; copie a URL.

O `--config` aponta para um arquivo que descreve o servidor, então a entrada já aparece na UI no
transporte certo:

```json
{
  "mcpServers": {
    "weather": {
      "command": "python",
      "args": ["mcp_demo/server.py"]
    }
  }
}
```

Sem ele, é preciso preencher os campos à mão e **`Transport Type` tem que estar em `STDIO`** — em
`SSE`/`Streamable HTTP` o Inspector trata o comando como URL e tenta OAuth contra ele.

O Inspector avisa que `--server has no effect on the web UI yet`: no modo web ele lista todos os
servidores do arquivo e você escolhe. No modo `--cli`, aí sim o `--server` é respeitado — útil
para testar sem navegador nenhum:

```bash
npx @modelcontextprotocol/inspector --cli --config mcp_demo/inspector.json --server weather \
    --method tools/list

npx @modelcontextprotocol/inspector --cli --config mcp_demo/inspector.json --server weather \
    --method tools/call --tool-name get_current_weather --tool-arg location=Recife
```

---

## 3 — VS Code

**Chave de topo: `servers`.** O VS Code ignora silenciosamente `mcpServers` (essa é a chave do
Claude Desktop e do Claude Code).

1. `Ctrl+Shift+P` → **MCP: Open User Configuration** (abre `~/.config/Code/User/mcp.json`).
   Para uma config que viaja com o repo, use **MCP: Open Workspace Configuration**
   (`.vscode/mcp.json`).

2. Conteúdo:

   ```json
   {
       "servers": {
           "weather": {
               "type": "stdio",
               "command": "docker",
               "args": [
                   "exec", "-i",
                   "-w", "/app/books",
                   "agents-mini-course",
                   "python", "mcp_demo/server.py"
               ]
           }
       }
   }
   ```

3. `Ctrl+Shift+P` → **MCP: List Servers** → `weather` → **Start**.

4. Erros aparecem em **MCP: Show Output** — é onde sai o stderr do container (as linhas
   `INFO Processing request of type ...` do FastMCP).

5. No chat, em modo *agent*, a tool `get_current_weather` passa a aparecer no seletor de
   ferramentas.

Depois de editar o `server.py`, use **MCP: Restart Server** — o VS Code mantém o processo antigo
vivo até você reiniciar.

> Não coloque a `WEATHER_API_KEY` no bloco `env` daqui. Ele define o ambiente do processo que o
> VS Code lança (o `docker`), e o `docker exec` não repassa nada para dentro do container sem
> `-e`. Além de não funcionar, deixa a chave em texto puro num arquivo que o Settings Sync
> sincroniza.

---

## 4 — Claude Code

**Chave de topo: `mcpServers`** (diferente do VS Code). Os dois arquivos coexistem sem conflito.

1. Na raiz do repo:

   ```bash
   claude mcp add --scope project weather -- \
       docker exec -i -w /app/books agents-mini-course python mcp_demo/server.py
   ```

   Tudo depois do `--` é o comando do servidor; o `--` é o que impede o `claude` de ler `-i` e
   `-w` como flags dele. Isso grava o [`.mcp.json`](../.mcp.json) na raiz.

2. Aprovar. Servidor vindo de `.mcp.json` não conecta antes de você autorizar — é a proteção
   contra um repo clonado executar comando arbitrário:

   ```text
   $ claude mcp list
   weather: docker exec -i ... - ⏸ Pending approval (run `claude` to approve)
   ```

   Rode `claude` na pasta do projeto e aceite o prompt.

3. Conferir:

   ```bash
   claude mcp list          # ✔ Connected
   claude mcp get weather   # escopo, comando, status
   ```

4. Na sessão, `/mcp` lista servidores e ferramentas. A tool aparece como
   `mcp__weather__get_current_weather`.

Escopos:

| escopo | onde grava | aprovação | quando usar |
| --- | --- | --- | --- |
| `project` | `.mcp.json` no repo | sim | compartilhar com a turma |
| `local` | `~/.claude.json`, por projeto | não | só você, neste projeto |
| `user` | `~/.claude.json`, global | não | em todos os seus projetos |

Para desfazer: `claude mcp remove weather -s project`.

---

## 5 — Claude Desktop

Mesma chave `mcpServers` do Claude Code, no `claude_desktop_config.json` do cliente (Settings →
Developer → Edit Config):

```json
{
  "mcpServers": {
    "weather": {
      "command": "docker",
      "args": ["exec", "-i", "-w", "/app/books",
               "agents-mini-course", "python", "mcp_demo/server.py"]
    }
  }
}
```

Reinicie o app depois de editar. Não há Claude Desktop instalado no ambiente do curso, então esta
seção é a única aqui que não foi testada de ponta a ponta.

---

## Erros comuns

| Erro | Causa | Correção |
| --- | --- | --- |
| `ModuleNotFoundError: No module named 'mcp.server.fastmcp'` | `mcp` 2.x instalado; o módulo virou `mcp.server.mcpserver` e `FastMCP` virou `MCPServer` | `pip install "mcp>=1.7.1,<2.0"` (com as aspas) |
| `ModuleNotFoundError` no `import mcp` do host | o cliente está usando o Python do host, que não tem as deps | use `docker exec -i ...` como comando |
| Inspector não abre em `localhost:6277` | a `6277` era o proxy do Inspector 1.x | use a **6274**, com o token da URL |
| Inspector abre no container mas não no host | ele escuta em `127.0.0.1` dentro do container | `HOST=0.0.0.0` + `DANGEROUSLY_BIND_ALL_INTERFACES=true` + porta publicada |
| `OAuth authorization failed for "python"` / `OAuth is only supported for HTTP-based transports` | `Transport Type` em SSE/HTTP; o comando está sendo lido como URL | mude para `STDIO`, ou use `--config` |
| `the input device is not a TTY` | `-t` no `docker exec` | só `-i`; o cliente faz pipe do stdin |
| VS Code não mostra nem erro (`mcpGateway.log` só com `Initialized`) | chave `mcpServers` em vez de `servers` | renomeie para `servers` |
| `WEATHER_API_KEY` não chega no servidor | `env` do cliente configura o processo `docker`, não o container | já vem do `/app/.env`; se precisar, `docker exec -e KEY=val` |
| `Error response from daemon: No such container` | container parado | `docker start agents-mini-course` |
| `⏸ Pending approval` no Claude Code | servidor de `.mcp.json` ainda não autorizado | rode `claude` no projeto e aceite |

## Referência de portas

| porta | serviço | publicada como |
| --- | --- | --- |
| 8080 | Jupyter (é a que o README usa) | `127.0.0.1:8080` |
| 8888 | Jupyter na porta default, se você subir sem `--port` | `127.0.0.1:8888` |
| 6274 | MCP Inspector — UI | `127.0.0.1:6274` |
| 6275 | MCP Inspector — sandbox | `127.0.0.1:6275` |
| 11434 | Ollama | `127.0.0.1:11434` |

Tudo publicado só no loopback do host, então nada disso fica visível na rede local.
