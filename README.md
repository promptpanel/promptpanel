<img src="https://promptpanel.com/images/logo.svg" alt="logo" style="width:64px;">

**Prompt Panel**\
Accelerating your AI agent adoption\
<a href="https://promptpanel.com/docs">Documentation</a> | <a href="https://hub.docker.com/r/promptpanel/promptpanel">DockerHub</a> | <a href="https://github.com/promptpanel/promptpanel">GitHub</a>

## Installation

### Via Docker Compose:

```bash
curl -sSL https://promptpanel.com/manifest/docker-compose.yml | docker compose -f - up
```

which runs the following `docker-compose.yml`:

```yaml
version: "3.9"
services:
  promptpanel:
    image: promptpanel/promptpanel:latest
    container_name: promptpanel
    restart: always
    volumes:
      - ./database:/app/database
      - ./media:/app/media
    ports:
      - 4000:4000
    environment:
      PROMPT_OLLAMA_HOST: http://ollama:11434
  ollama:
    image: ollama/ollama:latest
    container_name: ollama
    restart: always
```

After running, your environment will be available at:
`http://localhost:4000`

Read more on <a href="https://promptpanel.com/getting-started/quickstart/" target="_new">running Prompt Panel</a>.

---

Your models, conversations, and logic are locked in walled-gardens.

Let's free your AI interface.

- <a target="_new" href="https://promptpanel.com/getting-started/your-first-message/#step-2-download-a-model-with-ollama-for-offline-use">Run any large language model</a>, across any inference provider, any way you want. From commercial models like OpenAI, Anthropic, Gemini, or Cohere - to open source models, either hosted or running locally via Ollama.
- <a target="_new" href="https://promptpanel.com/user-management/access-controls/">Access controls</a> to assign users to agents without revealing your API tokens or credentials. Enable user sign-up and login with OpenID Connect (OIDC) single sign-on.
- <a target="_new" href="https://promptpanel.com/data-model/packaged-plugins-models/">Bring your own data</a> and store it locally on your instance. Use it safely by pairing it with any language model, whether online or offline.
- <a target="_new" href="https://promptpanel.com/data-model/packaged-plugins-models/">Create custom agent plugins</a> using Python, to customize your AI agent capabilities, and retrieval augmented generation (RAG) pipelines.

## Build your own agent plugins

Get started developing using a one-click cloud development environment using GitPod:

[![Open in Gitpod](https://gitpod.io/button/open-in-gitpod.svg)](https://gitpod.io/#https://github.com/promptpanel/promptpanel/tree/gitpod-one-click)

This `./plugins` directory contains the community plugin agents found in Prompt Panel as well as a sample agent as a template for you to get started with your own development.

- The `./hello_agent` directory gives you some scaffolding for a sample agent.
- The other community plugin agents give you references to sample from.
- The `docker-compose-agent-dev.yml` file gives you a sample with the various mounts and environment variables we recommend for development.

To get more information about how to build your first plugin we recommend giving a read to: 
- <a href="https://promptpanel.com/plugin-agent-authoring/building-plugin-agents/" target="_new">Building Plugin Agents</a>
- <a href="https://promptpanel.com/data-model/data-model/" target="_new">Data Model</a>

Running `DEV_PORT=4001 docker compose up -f docker-compose-agent-dev.yml` from this directory with a development port set will bring up a development environment you can use to start developing your agent plugin.

Command:
```bash
DEV_PORT=4001 docker compose up -f docker-compose-agent-dev.yml
```

With these settings, your development environment will be available at: `http://localhost:4001`

## Questions?

Feel free to get in contact with us at:\
hello@promptpanel.com

---

![screenshot](https://github.com/promptpanel/promptpanel/assets/161855417/6e7a303d-0fbc-4896-870d-19700b579e71)
