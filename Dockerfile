# 軽量な Python 3.11 公式スリムイメージを使用
FROM python:3.11-slim

# コンテナ内の作業ディレクトリを設定
WORKDIR /app

# 依存パッケージのインストールに必要な最小限のシステムツールをインストール
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Litestreamのダウンロードとインストール
ADD https://github.com/benbjohnson/litestream/releases/download/v0.3.13/litestream-v0.3.13-linux-amd64.deb /tmp/litestream.deb
RUN dpkg -i /tmp/litestream.deb && rm /tmp/litestream.deb

# レイヤーキャッシュを有効活用するため、まず requirements.txt をコピーしてインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 残りのソースコードをコピー
COPY . .

# 起動スクリプトを実行可能にする
RUN chmod +x /app/entrypoint.sh

# エントリーポイントとして起動スクリプトを指定
ENTRYPOINT ["/app/entrypoint.sh"]
