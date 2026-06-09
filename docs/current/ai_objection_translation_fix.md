---
title: AI Response Multilingual Compatibility Fix
status: implemented
last_updated: 2026-06-09
---

# AI Response Multilingual Compatibility Fix

多言語対応（英語・日本語以外の追加言語設定）が導入されたハッカソンにおいて、AI審査員からの異議あり（Objection）レスポンス、および管理者質問（Admin Chat）の回答が正しく取得できなくなっていた問題を修正しました。

## 要件・仕様

1. **意義あり（Objection）レスポンスのサニタイズ処理の多言語対応**
   - 設定されたすべてのAIレスポンス言語（`ai_response_languages`）に基づいて動的なキー（`qa_summary_{lang_key}`, `response_{lang_key}`）をサニタイズ・保護する。
   - 既存のレコードやフォールバックのために、旧互換キー（`qa_summary_en` / `qa_summary_ja` / `response_en` / `response_ja`）も併せて維持する。

2. **管理者質問（Admin Chat）保存時の多言語マッピング**
   - 管理者質問で得られた多言語のAI回答（`question_{lang_key}`, `answer_{lang_key}`）を、データベースの既存カラムである `question_en`, `question_ja`, `answer_en`, `answer_ja` に適切にマッピングして保存し、データベースの言語別カラムが空にならないようにする。

## Implementation Report

### 実装時の変更点

* **[evaluation_service.py](file:///Users/suzukiyousuke/repo/Judgie/core/services/evaluation_service.py)**:
  `sanitize_objection_response` で `hackathon_id` を受け取り、多言語設定を動的に処理するよう修正。
* **[admin_center.py](file:///Users/suzukiyousuke/repo/Judgie/views/admin_center.py)**:
  `save_admin_chat` に値を引き渡す際、動的言語キー（`question_english`, `answer_japanese` 等）から対応するカラムへマッピングするロジックを追加。
* **[test_evaluation_service.py](file:///Users/suzukiyousuke/repo/Judgie/tests/test_evaluation_service.py)**:
  多言語サニタイズ（韓国語を含む）が正常に機能し、動的キーが保護されることを検証するユニットテストを追加。

### テストおよび検証結果

* ユニットテストを実行し、全55件のテストがパスすることを確認。
* ローカル Streamlit でデモデータを利用した手動動作確認をブラウザサブエージェントで行い、日本語および韓国語のテキストが正しく表示されることを確認。
* Cloud Build / Cloud Run へのデプロイを行い、本番環境でも正しく動くことをユーザーが確認。
