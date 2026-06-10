---
title: Evaluation Templates and Advanced Customization Settings
status: implemented
last_updated: 2026-06-11
---

# 評価テンプレートと高度なカスタマイズ設定

## 概要

Judgie-AIを単一のハッカソン審査ツールから、Startup Pitchや採用、コード監査など、多様な評価要件に対応する汎用的な「AI評価プラットフォーム（AI Evaluation Platform）」へと移行・拡張するための機能仕様です。

本設計は、評価プロジェクト作成時の初期テンプレート適用、詳細な再評価（イテレーション）の振る舞い設定、Q&A対話メッセージ履歴のテーブル（リレーション）化、およびカスタムJSONテンプレートの外部インポート機能を備えています。

---

## システムアーキテクチャとデータモデル

### 1. プロジェクト設定の拡張 (`Hackathon` テーブル)
従来の `Hackathon` テーブルにカラムを追加し、個別の評価プロジェクトの挙動と適用されているテンプレートを定義します。

* **`template_id`** (`String`): 適用されている評価テンプレート識別子（例: `hackathon`, `startup_pitch`, `hiring`, `architecture`, `custom`）。
* **`re_evaluation_context_mode`** (`String` / デフォルト: `"cumulative"`):
  - `"cumulative"`: 前回の評価結果と改善点をコンテキストに含め、改善度を考慮して再採点を行います。
  - `"independent"`: 前回のフィードバックを完全に無視し、常にまっさらな状態で提出物のみを審査します。
* **`max_qa_turns`** (`Integer` / デフォルト: `1`):
  - Q&A（異議申し立て）の最大往復回数。`0` で無効、`-1` で無制限の会話スレッドになります。

### 2. Q&A対話履歴のテーブル化 (`TeamChat` テーブル)
従来の `Evaluation.qa_json` による単発対話の制限を排除し、複数回のQ&Aメッセージをリレーショナルに管理するためのテーブルです。

* **`id`** (`Integer`, 主キー)
* **`evaluation_id`** (`Integer`, `Evaluation.id` への外部キー)
* **`sender`** (`String`): `'team'` (ユーザーの質問) または `'judges'` (AI審査員パネルの回答)
* **`message_json`** (`Text`): 送信されたメッセージのテキスト、またはAIパネルからの構造化フィードバックデータを保持するJSON文字列
* **`created_at`** (`DateTime`): 発言日時

---

## 評価テンプレートパックの構成

組み込みテンプレートは [core/templates.py](file:///Users/suzukiyousuke/repo/Judgie/core/templates.py) にて静的に定義されています。

1. **Hackathon Evaluation (`hackathon`)**:
   - コンテキスト: `cumulative` (改善の審査) / Q&Aターン数: 1回
   - 審査員: Alex (起業家), David (エンジニア), Lisa (デザイナー), Sarah (PM), Marcus (VC)
2. **Startup Pitch Review (`startup_pitch`)**:
   - コンテキスト: `independent` (ピッチ比較) / Q&Aターン数: 3回
   - 審査員: Marcus (VC), Alex (起業家), David (技術評価者)
3. **Hiring & Technical Interview (`hiring`)**:
   - コンテキスト: `independent` (独立した候補者) / Q&Aターン数: 5回
   - 審査員: Elena (Engineering Manager), Ken (Senior Engineer), Aria (Peer mid-level)
4. **Software Architecture Review (`architecture`)**:
   - コンテキスト: `independent` / Q&Aターン数: 0回 (フィードバック返却のみ)
   - 審査員: Sophia (Principal Architect), Taro (Senior SRE), Vikram (Security Architect)

### カスタムテンプレートのインポート
JSON URL（例: GitHub Raw URLやGist）をプロジェクト作成時に入力することで、インターネット経由でカスタムテンプレート（ペルソナプロンプト、重み付き評価軸）を動的にシードできます。

---

## ユーザーインターフェース

### 1. プロジェクト作成 (`superadmin_center.py`)
- プロジェクト名、管理者アカウント情報に加え、上記テンプレートまたはカスタムURLによる外部JSON指定を入力するフォームを提供します。

### 2. プロジェクト詳細設定 (`admin_center.py` Tab 7)
- 稼働中のプロジェクトに対して、再評価コンテキストモード (`cumulative`/`independent`) と Q&A制限回数の上書き・変更が可能です。

### 3. Q&Aスレッドビュー (`team_view.py`)
- `st.chat_message` コンポーネントを使用し、チームからの質問とAI審査員全体の回答を会話スレッド形式で順次描画します。
- 残りターン数に応じて送信フォームが自動で非活性化されます。

---

## Implementation Report (実装レポート)

### 実装日
2026年6月11日

### 実装概要
- [templates.py](file:///Users/suzukiyousuke/repo/Judgie/core/templates.py) を新設し、4種の豊富なドメインテンプレート定義を構築。
- [db.py](file:///Users/suzukiyousuke/repo/Judgie/core/db.py) のスキーマ修正、マイグレーション記述、`TeamChat` テーブルの定義を追加。
- [gemini.py](file:///Users/suzukiyousuke/repo/Judgie/core/gemini.py) と [evaluation_service.py](file:///Users/suzukiyousuke/repo/Judgie/core/services/evaluation_service.py) を修正し、`TeamChat` の累積履歴による文脈維持型マルチターン討論ロジックへ移行。
- [superadmin_center.py](file:///Users/suzukiyousuke/repo/Judgie/views/superadmin_center.py), [admin_center.py](file:///Users/suzukiyousuke/repo/Judgie/views/admin_center.py), [team_view.py](file:///Users/suzukiyousuke/repo/Judgie/views/team_view.py) にそれぞれ対応するUIコンポーネントを追加。
- pytestを用いてすべての新規テンプレートバリデーション、DB操作、Q&A討論テストの合格（56 passed）を確認。
- `README.md` にて「AI Evaluation Platform」としての定義更新と、カスタムテンプレート作成ガイドを追記。
