#!/bin/sh
set -e

# PORTのデフォルト設定
PORT=${PORT:-8080}

# データベースファイルのディレクトリ作成
mkdir -p /app/data

# DATABASE_URLがsqliteかどうか、かつLITESTREAM_REPLICA_URLが指定されているかを判定
if [ -n "$DATABASE_URL" ] && echo "$DATABASE_URL" | grep -q "^sqlite://"; then
    echo "SQLite database detected. Checking Litestream config..."
    
    # 接続文字列からSQLiteファイルパスを抽出
    # sqlite:////app/data/judgie.db -> /app/data/judgie.db
    # sqlite:///data/judgie.db -> data/judgie.db
    DB_PATH=$(echo "$DATABASE_URL" | sed 's|^sqlite:///||')
    if echo "$DB_PATH" | grep -q "^/"; then
        # 絶対パス
        true
    else
        # 相対パスの場合は /app/ を付与して絶対パス化
        DB_PATH="/app/$DB_PATH"
    fi

    # データベースファイルの親ディレクトリが存在することを確認
    mkdir -p "$(dirname "$DB_PATH")"

    if [ -n "$LITESTREAM_REPLICA_URL" ]; then
        echo "LITESTREAM_REPLICA_URL is set. Restoring database from replica if exists..."
        # データベースがまだ存在しない場合のみ、レプリカからリストアを試みる
        if [ ! -f "$DB_PATH" ]; then
            litestream restore -if-replica-exists "$DB_PATH" || echo "No replica found or restore failed. Starting with empty database."
        else
            echo "Database file already exists. Skipping restore."
        fi

        echo "Starting Litestream replication and Streamlit app..."
        # litestream replicateの制御下でStreamlitアプリを実行
        exec litestream replicate -exec "streamlit run app.py --server.port=${PORT} --server.address=0.0.0.0 --server.fileWatcherType=none"
    else
        echo "LITESTREAM_REPLICA_URL is not set. Running without replication..."
        exec streamlit run app.py --server.port=${PORT} --server.address=0.0.0.0 --server.fileWatcherType=none
    fi
else
    echo "Non-SQLite database detected (or DATABASE_URL is not set). Starting Streamlit directly..."
    exec streamlit run app.py --server.port=${PORT} --server.address=0.0.0.0 --server.fileWatcherType=none
fi
