#!/bin/sh
set -e

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

        echo "Starting Litestream replication and Streamlit app..."
        # Run the Streamlit app under the control of litestream replicate
        exec litestream replicate -config /app/litestream.yml -exec "streamlit run app.py --server.port=${PORT} --server.address=0.0.0.0 --server.fileWatcherType=none"
    else
        echo "LITESTREAM_REPLICA_URL is not set. Running without replication..."
        exec streamlit run app.py --server.port=${PORT} --server.address=0.0.0.0 --server.fileWatcherType=none
    fi
else
    echo "Non-SQLite database detected (or DATABASE_URL is not set). Starting Streamlit directly..."
    exec streamlit run app.py --server.port=${PORT} --server.address=0.0.0.0 --server.fileWatcherType=none
fi
