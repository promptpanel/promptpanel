# Formatting script

Easy to use, Dockerized, formatting via Black (Python) and Prettier (Everything Else).

## Build local image

From this directory, run:

```
docker build -t code-formatter .
```

## Run formatting

From this directory, run:

```
docker run --name code-formatter -v $(dirname $(pwd)):/app code-formatter
```

This will mount the parent directory into the container under `/app` and format it.

## Cleanup

Run:

```
docker stop code-formatter && docker rm -v code-formatter
```

to remove the formatting container and it's associated volume
