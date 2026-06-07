# 軽量な Python 3.9 公式スリムイメージを使用
FROM python:3.9-slim

# コンテナ内の作業ディレクトリを設定
WORKDIR /app

# 依存パッケージのインストールに必要な最小限のシステムツールをインストール
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# レイヤーキャッシュを有効活用するため、まず requirements.txt をコピーしてインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 残りのソースコードをコピー
COPY . .

# Cloud Run が期待する環境変数 PORT (デフォルト 8080) に動的に対応するよう起動
# Streamlit の自動ホットリロード（FileWatcher）は本番環境では不要なため無効化
ENTRYPOINT ["sh", "-c", "streamlit run app.py --server.port=${PORT:-8080} --server.address=0.0.0.0 --server.fileWatcherType=none"]
