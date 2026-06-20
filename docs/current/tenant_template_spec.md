---
status: implemented
---
# テナント作成時のテンプレート適用仕様

## 概要
Judgie-AIにおいて、スーパー管理者が新規プロジェクト（テナント）を作成する際、特定のテンプレート（ハッカソン、ヒアリング、スタートアップピッチ、アーキテクチャレビューなど）を選択しない場合の評価基準（criteria）およびジャッジペルソナ（personas）の適用挙動を定義します。

## 仕様詳細
1. **テンプレート未指定時の挙動**
   - スーパー管理者（Super Admin）が新規テナントを作成する際、テンプレートを指定しない場合（`template_id` が `None`）は、そのテナント用の評価基準およびジャッジペルソナの初期データは設定されません。
   - `get_criteria(hackathon_id)` および `get_personas(hackathon_id)` は空のリスト `[]` を返します。
   - これにより、テナント管理者がログイン後にゼロから任意の評価基準やペルソナを設定することが可能になります。

2. **後方互換性とテスト用フォールバック**
   - 既存のテストや、DB上に存在しないID（例: テスト用のダミーIDや `None` など）に対して `get_criteria(hackathon_id)` / `get_personas(hackathon_id)` が呼び出された場合、後方互換性維持のため、デフォルトで `hackathon` テンプレートの設定値を返します。

## Implementation Report

### 実装時の変更点
- `core/db.py` および `backend/app/models/db.py` 内の `get_criteria` と `get_personas` 関数において、引数で渡された `hackathon_id` がデータベース上に存在し、かつその `template_id` が `None`（未設定）である場合は、デフォルトで `hackathon` テンプレートを返すのではなく、空リスト `[]` を返すようにロジックを修正しました。
- `tests/test_db.py` にテストケースを追加し、テンプレート未選択の新規テナント作成直後に `get_criteria` および `get_personas` が空リスト `[]` を返すことをアサートするようにしました。
