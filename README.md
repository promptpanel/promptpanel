<img src="https://promptpanel.com/images/logo.svg" alt="logo" style="width:64px;">
<br/>
<br/>

**PromptPanel**\
The Universal AI Interface\
<a href="http://promptpanel.com/docs">Documentation</a> | <a href="https://hub.docker.com/r/promptpanel/promptpanel">DockerHub</a>


## Installation

Docker Compose (Recommended):
```yaml
version: "3.9"
services:
  promptpanel:
    image: promptpanel/promptpanel:latest
    container_name: promptpanel
    restart: always
    ports:
      - 4000:4000
    environment:
      PROMPT_OLLAMA_HOST: http://ollama:11434
  ollama:
    image: ollama/ollama:latest
    container_name: ollama
    restart: always
```

Docker Run:
```bash
docker run --name promptpanel -p 4000:4000 promptpanel/promptpanel:latest
```

Read more on <a href="http://promptpanel.com/installation/docker-compose-offline/" target="_new">running PromptPanel</a>.

---

AI interfaces are limited and restrictive.

Your models, conversations, and logic are locked in walled-gardens.

We're looking to change that.

- <a target="_new" href="https://promptpanel.com/overview/packaged-plugins-models/">Run any large language model</a>, across any inference provider, any way you want. We're un-opinionated.
- <a target="_new" href="https://promptpanel.com/plugin-authoring/building-plugins/">Create custom plugins</a> and tailor the system to your unique needs.
- <a target="_new" href="https://promptpanel.com/overview/packaged-plugins-models/#llm-document">Bring your own data</a> - host and run models locally using any engine.
- <a target="_new" href="https://promptpanel.com/server-setup/accessing-your-data/">Move and use your data</a> - we're pro data accessibility and portability.

## Want to chat?
Feel free to get in contact with us at:\
info@promptpanel.com
