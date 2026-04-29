# Local Backend With Ngrok

Use this guide for the Red Hat/local script workflow with local Postgres and ngrok.

## Terminal 1: Backend

```bash
cd /home/pjbd103/Projects/luke-bot
./scripts/start_local_postgres_apptainer.sh
```

Open another terminal:

```bash
cd /home/pjbd103/Projects/luke-bot
./scripts/migrate_local.sh
./scripts/start_backend_local.sh
```

## Terminal 2: Ngrok

```bash
cd /home/pjbd103/Projects/luke-bot
ngrok http 8000
```

Use the public URL in Meta:

```text
https://YOUR-NGROK-DOMAIN/webhook/meta
```

## Quick Checks

```bash
curl http://127.0.0.1:8000/health
pgrep -a -f 'uvicorn|ngrok|postgres'
```

## Stop

Use `Ctrl+C` in each running terminal.

If you lost the terminal:

```bash
pkill -f uvicorn
pkill -f ngrok
```
