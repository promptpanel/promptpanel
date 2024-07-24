#!/bin/bash
# Detect architecture
# ARCH=$(uname -m)
# case "$ARCH" in
#     x86_64) ARCH="amd64" TAILWIND_ARCH="x64" ;;
#     aarch64|arm64) ARCH="arm64" TAILWIND_ARCH="arm64" ;;
#     *) echo "🤷 Unsupported architecture: $ARCH" ;;
# esac

# Additional requirements
if [ "$PROMPT_DEV_INSTALL_REQS" == "ENABLED" ]; then
    echo "💡 Development requirements enabled"
    echo "🕒 Installing requirements"
    find . -name requirements.txt -exec pip install --no-cache-dir -r {} \;
fi

if [ "$PROMPT_SQLITE_WAL" == "ENABLED" ]; then
    echo "💡 Enabling SQLite WAL"
    touch /app/database/db.sqlite3
    sqlite3 /app/database/db.sqlite3 "PRAGMA journal_mode=WAL;"
else
  touch /app/database/db.sqlite3
  sqlite3 /app/database/db.sqlite3 <<EOF
PRAGMA journal_mode=DELETE;
PRAGMA wal_checkpoint(TRUNCATE);
EOF
  rm -f /app/database/db.sqlite3-wal /app/database/db.sqlite3-shm
fi

# Setup .json
if [ ! -f /app/system.json ]; then
    cp /app/system.default.json /app/system.json
fi
if [ ! -f /app/licence.json ]; then
    cp /app/licence.default.json /app/licence.json
fi

# Run migrations
echo "🕒 Running database migrations"
python manage.py makemigrations && python manage.py migrate
python manage.py createcachetable

# Setup cron
service cron start && \
python /app/manage.py update_stats && \
echo "0 * * * * python /app/manage.py update_stats" >> cronjobs && \
crontab cronjobs && \
rm cronjobs

if [ "$PROMPT_MODE" == "DEVELOPMENT" ]; then
    echo "🚀 Running server..."
    echo """
         ____
     ▄▓█████████▄_
   ▓███████████████▄                       +------------------------------------+
 ┌███████████████████     ▄▄_▓╕            | PromptPanel interface running at:  |
 ████████████████████▌   ██████▄           | http://localhost:4000/             |
 ███████    ╙█████████   ██  ▀▀████▄       +------------------------------------+
 ╙███████▄▓  ████████▌  ▐██     ,▄╙██▌    /  
   ▀██████Γ ╓████████ _▓██      ▀▀+ ╙██  / 
          ▄█████████▓██▀+         _▄██+ 
        ▓██████████▀+─          ╓██▀+
      ╓█████████╙         ╔▄    ██
      ████████▀           ╟█▌   ██▄
     ▐███████▌       ╓▄▄▄_ ╙███▓▄██
     ▐███████▌       ╙▀▀▀██▄  └██▀▀
      ╟███████            ██▄ ▓█▌
       ▀███████           ╟████▀
         ▀██████▓▄      ,▓███▀
           └▀▀███████████▀▀+
                 '└+└+
    """
    python manage.py runserver 0.0.0.0:4000 --insecure &
fi
if [ "$PROMPT_MODE" == "PRODUCTION" ]; then
    echo "💡 Production mode enabled"
    echo "🕒 Collecting static files"
    python manage.py collectstatic --noinput --verbosity 0
    echo "🚀 Running production server..."
    echo """
         ____
     ▄▓█████████▄_
   ▓███████████████▄                       +------------------------------------+
 ┌███████████████████     ▄▄_▓╕            | PromptPanel interface running at:  |
 ████████████████████▌   ██████▄           | http://localhost:4000/             |
 ███████    ╙█████████   ██  ▀▀████▄       +------------------------------------+
 ╙███████▄▓  ████████▌  ▐██     ,▄╙██▌    /  
   ▀██████Γ ╓████████ _▓██      ▀▀+ ╙██  / 
          ▄█████████▓██▀+         _▄██+ 
        ▓██████████▀+─          ╓██▀+
      ╓█████████╙         ╔▄    ██
      ████████▀           ╟█▌   ██▄
     ▐███████▌       ╓▄▄▄_ ╙███▓▄██
     ▐███████▌       ╙▀▀▀██▄  └██▀▀
      ╟███████            ██▄ ▓█▌
       ▀███████           ╟████▀
         ▀██████▓▄      ,▓███▀
           └▀▀███████████▀▀+
                 '└+└+
    """
    gunicorn --bind 0.0.0.0:4000 --workers $PROMPT_WORKERS --timeout $PROMPT_WORKER_TIMEOUT promptpanel.wsgi &
fi

# Keep Container Running
wait
