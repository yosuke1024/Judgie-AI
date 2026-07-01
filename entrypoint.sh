#!/bin/sh
set -e

# Redirect stderr to stdout so that standard logs (like Uvicorn/FastAPI startup messages)
# are not colored as red "errors" in cloud platforms like Railway.
exec 2>&1

# Default configuration for PORT
PORT=${PORT:-8080}

# Create directory for database files
mkdir -p /app/data

# Check if DATABASE_URL is SQLite and LITESTREAM_REPLICA_URL is specified
if [ -n "$DATABASE_URL" ] && echo "$DATABASE_URL" | grep -q "^sqlite://"; then
    echo "SQLite database detected. Checking Litestream config..."
    
    # Extract the SQLite file path from the connection string
    # sqlite:////app/data/judgie.db -> /app/data/judgie.db
    # sqlite:///data/judgie.db -> data/judgie.db
    DB_PATH=$(echo "$DATABASE_URL" | sed 's|^sqlite:///||')
    if echo "$DB_PATH" | grep -q "^/"; then
        # Absolute path
        true
    else
        # For relative path, prefix with /app/ to make it absolute
        DB_PATH="/app/$DB_PATH"
    fi

    # Ensure the parent directory of the database file exists
    mkdir -p "$(dirname "$DB_PATH")"

    if [ -n "$LITESTREAM_REPLICA_URL" ]; then
        echo "LITESTREAM_REPLICA_URL is set. Restoring database from replica if exists..."
        # Only restore from replica if the database file does not exist yet
        if [ ! -f "$DB_PATH" ]; then
            litestream restore -config /app/litestream.yml -if-replica-exists "$DB_PATH" || echo "No replica found or restore failed. Starting with empty database."
        else
            echo "Database file already exists. Skipping restore."
        fi

        echo "Starting Litestream replication and FastAPI app..."
        # Run the FastAPI app under the control of litestream replicate
        exec litestream replicate -config /app/litestream.yml -exec "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"
    else
        echo "LITESTREAM_REPLICA_URL is not set. Running without replication..."
        exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
    fi
else
    echo "Non-SQLite database detected (or DATABASE_URL is not set). Starting FastAPI directly..."
    exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
fi
