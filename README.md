# AI AGENTS MINI CURSO

```bash
mv .env.template .env
# Edit the .env file to add your OpenAI API key

# Build and start the Docker container
make docker-build
make docker-start

# Access Jupyter Notebook
jupyter notebook --port 8080 --allow-root --ip 0.0.0.0 --no-browser
```

## Docs

- [doc/mcp.md](doc/mcp.md) — configurando o servidor MCP da aula 06 em cada ambiente
  (Inspector, VS Code, Claude Code) e os erros comuns.
