# JudgieAI テンプレートマーケットプレイス仕様書（要件定義・設計）

本ドキュメントは、JudgieAIの評価テンプレートを共有・検索・導入するための「テンプレートマーケットプレイス」を、別リポジトリ（PixAppsランディングページ等）で構築するための共通仕様・要件定義書です。

* **ステータス**: `approved`
* **最終更新**: 2026-06-11

---

## 1. 背景と目的

JudgieAIがハッカソン審査から汎用的なプロジェクト評価ツールへと移行したことに伴い、多様な「評価軸（Criteria）」や「AI審査員（Personas）」の組み合わせが生まれつつあります。
本マーケットプレイスは、これらをユーザー同士で相互に共有・再利用できる場を提供し、以下のメリットを実現します。

1. **利用の高速化**: ユーザーはゼロからプロンプトを書くことなく、ユースケースに合った公式/コミュニティ製のテンプレートを即座に導入できる。
2. **コミュニティ活性化**: 優れた評価ロジックや面白いペルソナ（AI審査員）をGitHub GistやPRで共有し合える環境を作る。
3. **PixAppsへの流入**: PixAppsのランディングページ上にマーケットプレイスを統合することで、一般ユーザーやビジネス層の流入フック（SEO・集客ハブ）として機能させる。

---

## 2. システムアーキテクチャ

別リポジトリとして、以下の技術スタックでの構築を想定します。

```mermaid
graph TD
    JudgieApp[Judgieアプリ Admin UI] -->|Raw JSON URLをインポート| MarketWeb
    JudgieApp -->|現在の設定をエクスポート| LocalJSON[ローカルJSONファイル]
    LocalJSON -->|Gistに貼り付け| Gist[GitHub Gist]
    Gist -->|URLを登録| MarketWeb[マーケットプレイス Web UI (Cloudflare Pages)]
    MarketWeb -->|APIリクエスト| MarketAPI[マーケットプレイス API (Cloudflare Workers)]
    MarketAPI -->|データ保存| MarketDB[メタデータDB (Cloudflare D1)]
```

* **ホスティング**: Cloudflare Pages（PixAppsランディングページと同一環境）
* **バックエンドAPI**: Cloudflare Workers
* **データベース**: Cloudflare D1 (SQLite) もしくは Cloudflare KV
  * コミュニティテンプレートは「GistのURL」と「メタデータ（タイトル、カテゴリ、タグ等）」のみを管理するため、超軽量なデータストアで充分に運用可能です。

---

## 3. テンプレートの分類と管理フロー

テンプレートは **「公式テンプレート（Official）」** と **「コミュニティテンプレート（Community）」** に大別します。

### 3.1 公式テンプレート
* **定義**: Judgie運営・メンターがレビューし、品質と安全性が保証された標準テンプレート。
* **管理方法**: 
  - Judgie本体リポジトリ（OSS）の `/templates/*.json` ディレクトリでGit管理する。
  - 新規追加や修正は、GitHub上のPull Requestを通じて行い、マージされることで公式に認定される。
* **表示**: 
  - マーケットプレイスのWebサイトは、GitHub API（またはビルド時の静的生成）を利用して、`/templates` 内の最新のJSONファイルを直接読み込んでカタログに表示する。

### 3.2 コミュニティテンプレート
* **定義**: 一般ユーザー（テナント管理者や開発者）が作成し、自由に公開したテンプレート。
* **登録フロー**:
  1. ユーザーは、自身のJudgie Admin UIから設定を「エクスポート（JSONダウンロード）」する。
  2. ダウンロードしたJSONを、自身の **GitHub Gist** にパブリックで新規作成・保存する。
  3. マーケットプレイスのWebサイトの「テンプレートを登録」フォームに、以下の情報を入力して送信する：
     - **Gist URL**: (例: `https://gist.github.com/username/gist_id`)
     - **テンプレート名**: (自動フェッチ、または手動入力)
     - **説明文 / ユースケース**: (対象者や活用シーン)
     - **カテゴリ**: (例: `ハッカソン`, `採用・技術面接`, `スタートアップピッチ`, `アイデア検証` など)
     - **対応言語**: (例: `日本語`, `英語` 等)
     - **作成者名 (表示名)**
  4. バックエンドAPI（Workers）は、入力されたGist URLから中身をテストフェッチし、正しいJudgieテンプレートJSON構造であるかを自動バリデーションした上で、メタデータDBに登録する。

---

## 4. ユーザー体験（UX）フロー

### 4.1 テンプレートを探してJudgieに導入する流れ
1. ユーザーはマーケットプレイス（PixAppsのWebページ）で気になるテンプレートを見つける。
2. 詳細ページで評価基準やAI審査員ペルソナのリストを確認する。
3. **「Raw URLをコピー」** ボタンをクリックし、クリップボードにGistのRaw JSON URLをコピーする。
4. 自身のJudgieのAdmin UI（「プロジェクト設定」タブ）に移動する。
5. **「外部テンプレートのインポート」** フィールドにコピーしたURLを貼り付け、「インポートを実行」を押す。
6. 設定が即座に自分のテナントに適用される。

---

## 5. データ構造（テンプレートJSONスキーマ）

インポート・エクスポートされるJSONファイルは、以下のスキーマを満たしている必要があります。

```json
{
  "name": "Template Name (例: ハッカソン審査)",
  "description": "Template description summary.",
  "re_evaluation_context_mode": "cumulative | independent",
  "max_qa_turns": 1,
  "criteria": [
    {
      "name": "Criteria Name (例: 技術的完成度)",
      "weight": 25,
      "description": "What judges evaluate:\n- Detail prompt instructions..."
    }
  ],
  "personas": [
    {
      "id": "一意のUUIDまたは連番文字列",
      "name": "Persona Name (例: David)",
      "role": "Persona Title (例: Principal SRE)",
      "avatar": "Emoji (例: 💻)",
      "avatar_image": null,
      "prompt": "Detailed persona instructions...",
      "active": true
    }
  ]
}
```

### 必須キーの制約:
* `criteria` の各 `weight` の合計値は必ず **100** になる必要があります（本体側のインポート時にバリデーションチェックが走ります）。
* 各 `personas` の `id` は同一テンプレート内で重複してはなりません。

---

## 6. 将来的なロードマップ

1. **Admin UI内での直接検索**:
   - JudgieのAdmin UI内にマーケットプレイスのAPIからフェッチしたカタログリストを直接表示し、URLのコピー＆ペーストすら不要で「インストール」ボタンを押すだけでインポートできる統合。
2. **テンプレートの評価・スター機能**:
   - ユーザーが良かったテンプレートにスター（いいね）をつけたり、何回インポートされたかのカウンターを表示し、優れたテンプレートが上位に表示される仕組み。
3. **簡易バージョン管理**:
   - Gist側で更新があった場合、Judgie側で「アップデートがあります」と検知して再インポートを促す機能。
