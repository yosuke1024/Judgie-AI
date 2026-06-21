---
status: implemented
---
# テナント作成時のテンプレート適用およびテナント管理者によるインポート仕様

## 概要
Judgie-AIにおいて、スーパー管理者が新規プロジェクト（テナント）を作成する際、特定のテンプレート（ハッカソン、ヒアリング、スタートアップピッチ、アーキテクチャレビューなど）を選択しない場合の評価基準（criteria）およびジャッジペルソナ（personas）の適用挙動、ならびにテナント管理者（Admin）によるプリセットテンプレートの適用仕様を定義します。

## 仕様詳細
1. **テンプレート未指定時の挙動**
   - スーパー管理者（Super Admin）が新規テナントを作成する際、テンプレートを指定しない場合（`template_id` が `None`）は、そのテナント用の評価基準およびジャッジペルソナの初期データは設定されません。
   - `get_criteria(hackathon_id)` および `get_personas(hackathon_id)` は空のリスト `[]` を返します。
   - これにより、テナント管理者がログイン後にゼロから任意の評価基準やペルソナを設定することが可能になります。

2. **後方互換性とテスト用フォールバック**
   - 既存のテストや、DB上に存在しないID（例: テスト用のダミーIDや `None` など）に対して `get_criteria(hackathon_id)` / `get_personas(hackathon_id)` が呼び出された場合、後方互換性維持のため、デフォルトで `hackathon` テンプレートの設定値を返します。

3. **テナント管理者によるプリセットテンプレートの適用**
   - テナント管理者（Admin）は、ログイン後のコマンドセンター（Admin Center）の「データエクスポート」タブ（Export Data）にて、システムの組み込みプリセットテンプレート（ハッカソン、ヒアリング、スタートアップピッチ、アーキテクチャレビューなど）を選択し、自身のテナントに対して適用（インポート初期化）できます。
   - 既存の設定（評価基準やジャッジペルソナ）が上書きされるため、適用前には確認ダイアログ（Confirmation Alert）が表示されます。
   - テナント管理者はセキュリティ上、**自身のテナントのみ**しか初期化（テンプレート適用）できません。他人のテナントIDを指定した不正なリクエストは、バックエンド側で `403 Forbidden` として拒否されます。

## Implementation Report

### 実装時の変更点

- **テンプレート未選択時のデフォルト適用バグ修正**
  - `core/db.py` および `backend/app/models/db.py` 内の `get_criteria` と `get_personas` 関数において、引数で渡された `hackathon_id` がデータベース上に存在し、かつその `template_id` が `None`（未設定）である場合は、デフォルトで `hackathon` テンプレートを返すのではなく、空リスト `[]` を返すようにロジックを修正しました。
  - `tests/test_db.py` にテストケースを追加し、テンプレート未選択の新規テナント作成直後に `get_criteria` および `get_personas` が空リスト `[]` を返すことをアサートするようにしました。

- **テナント管理者向けプリセットインポート機能の追加とUI調整**
  - バックエンド `backend/app/routers/hackathons.py` の `initialize_template` エンドポイントに権限チェックを追加し、ログインユーザーのロールが `admin` である場合に、パスパラメータの `hackathon_id` が自身の `user.hackathon_id` と一致しているかを検証するようにしました。不一致の場合は `403 Forbidden` を返します。
  - テンプレート適用時にジャッジペルソナのアバターとプロンプトが正しく入力されるよう、キー表記を `avatar` および `prompt` に完全統一しました。これにより、過去の Streamlit 時代から引き継いだ `emoji` や `prompt_instruction` との混在による入力漏れバグを解消しました（なお、過去DBからの移行処理は非考慮とするユーザー承認を得ています）。
  - フロントエンド `frontend/src/pages/admin/AdminCenter.tsx` 内で、テンプレート適用フォーム（インポートカード）を「データエクスポート」タブから「プロジェクト設定 (Project Settings)」タブへ移植しました。
  - フロントエンドにアバター（emoji）およびプロンプト（prompt）の入力項目を整備し、新規ペルソナの追加や既存ペルソナの編集が正常に保存されるようにしました。
  - `ja.json` および `en.json` に多言語用の関連翻訳キーを追加しました。
  - テストコード `tests/test_api_hackathons.py` を新規作成し、`superadmin` による任意のテナント適用、および `admin` による自身のテナントの適用が成功すること、他人のテナント適用が `403 Forbidden` で弾かれることを検証する結合テストを実装しました。また、これに伴い `tests/conftest.py` にて FastAPI バックエンド用の in-memory SQLite モック設定および Streamlit モック（`MockObject` による context manager 対応）を追加しました。全66件のテストスイートが正常パスすることを確認済みです。
  - Dockerfile および entrypoint.sh について、FastAPI と React のマルチステージビルド・ルーティング対応にアップデートしました。

- **2026-06-21 コマンドセンター設定画面の改善と権限修正の追記**
  - **パスコード変更権限**: バックエンド `backend/app/routers/hackathons.py` の `reset_admin_passcode` エンドポイントを緩和し、テナントIDが一致する `admin` ロールのユーザー自身による変更を許可。他テナントへの変更試行は `403 Forbidden` で拒否するロジックを実装。
  - **UI調整**: 「Import Panel」を `settings-grid` の最上部に移動。「API Billing Tier」項目を削除。
  - **Gemini APIキー検証と動的モデルリスト**: APIキーが未設定・未検証の時はモデルドロップダウンを非活性化する制御を導入。「Verify & Save Key」ボタンをクリックした際に、キーを一時的に検証・保存してドロップダウンを有効化し、利用可能な標準LLMモデル（`flash`, `pro` 等）のみをドロップダウンに動的にレンダリングする処理を実装。
  - **テスト環境の修正（非自明なバグ回避）**: テストコード `tests/test_api_hackathons.py` に admin 用のパスコードリセットテストを追加。これに伴い、`sys.path` 多重インポートによる `backend.app.models.db` と `app.models.db` の名前空間の不一致で FastAPI ルーター側がテスト用 DB を参照できなくなっていたバグを発見し、`conftest.py` にて両方の名前空間を同じ `StaticPool` の sqlite データベースに差し替えることで、テスト環境におけるデータ共有問題を根本解消。また、GitHub Actions の CI 環境で FastAPI 関連の依存パッケージがインストールされずテスト実行時に `ModuleNotFoundError` で落ちていたバグを、`ci.yml` のインストール対象に `backend/requirements.txt` を追加することで解消。
