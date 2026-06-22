<p align="center">
  <img src="./docs/images/miroshark-logo.jpg" alt="MiroShark" width="120" />
</p>

<h1 align="center">MiroShark</h1>

<p align="center">
  <a href="https://github.com/aaronjmars/MiroShark/stargazers"><img src="https://img.shields.io/github/stars/aaronjmars/MiroShark?style=flat-square&logo=github" alt="GitHub stars"></a>
  <a href="https://github.com/aaronjmars/MiroShark/network/members"><img src="https://img.shields.io/github/forks/aaronjmars/MiroShark?style=flat-square&logo=github" alt="GitHub forks"></a>
  <a href="https://x.com/miroshark_"><img src="https://img.shields.io/badge/Follow-%40miroshark__-black?style=flat-square&logo=x&labelColor=000000" alt="Follow on X"></a>
  <a href="https://bankr.bot/discover/0xd7bc6a05a56655fb2052f742b012d1dfd66e1ba3"><img src="https://img.shields.io/badge/MiroShark%20on-Bankr-orange?style=flat-square&labelColor=1a1a2e" alt="MiroShark on Bankr"></a>
</p>

<p align="center">
  <a href="./README.md">English</a> · <a href="./README.zh-CN.md">中文</a> · <b>日本語</b> · <a href="./README.fr.md">Français</a>
</p>

<p align="center">
  <img src="./docs/images/miroshark-demo.gif" alt="MiroShark デモ" />
</p>

---

> **あらゆるシナリオをシミュレート、$1 以下・10 分未満で。**
> 何でも投入してください — プレスリリース、ニュースの見出し、政策草案、答えの出ない問い、歴史の「もしも」。MiroShark は数百のエージェントを生成し、1 時間刻みでそれに反応します。投稿し、議論し、取引し、考えを変えていきます。

<p align="center">
  <img src="./docs/images/simulate-anything-hero-v2.jpg" alt="あらゆるシナリオをシミュレート — 1 回 $1、最初の結果まで 10 分、100 エージェント:入力 → 世界構築 → スウォーム → レポート" width="100%" />
</p>

## 何ができるか

- あなたがシナリオを持ち込み、MiroShark がその周囲に世界を組み立てます。
- 根拠を持った数百のエージェントが Twitter、Reddit、予測市場で 1 時間刻みに動きます。
- どのエージェントとも対話できます。実行中に速報を投入できます。タイムラインを分岐できます。
- 実際の投稿や取引を引用しながら、何が起きたかを記述したレポートが得られます。

<p align="center">
  <img src="./docs/images/simulation-phases-v2.jpg" alt="MiroShark パイプライン:フェーズ 1 オントロジー生成 → フェーズ 2 グラフ構築 → フェーズ 3 エージェント設定 → フェーズ 4 シミュレーション実行 → フェーズ 5 レポートとインタラクション" width="100%" />
</p>

## クイックスタート

推奨パス:**[OpenRouter](https://openrouter.ai/) のキー 1 本 + `./miroshark` ランチャー**。初回シミュレーションは約 10 分、約 $1。

**前提条件** — Python 3.11+、Node 18+、Neo4j、そして [OpenRouter のキー](https://openrouter.ai/)。

Neo4j をインストールしてください — ランチャーが起動を引き受けます:

- **macOS** — `brew install neo4j`
- **Linux** — `sudo apt install neo4j` *(またはお使いのディストリビューションの同等コマンド)*
- **Windows** — [Neo4j Desktop](https://neo4j.com/download/) をインストール *(ネイティブ GUI — そこで DB を起動してから、WSL2 もしくは Git Bash でランチャーを実行)*、あるいは [WSL2](https://learn.microsoft.com/windows/wsl/install) 内で一式を動かして Linux の手順に従う
- **インストール不要** — 無料の [Neo4j Aura](https://neo4j.com/cloud/aura-free/) クラウドインスタンスを作成し、`.env` の `NEO4J_URI` / `NEO4J_PASSWORD` をそこに向ける

その後:

```bash
git clone https://github.com/aaronjmars/MiroShark.git && cd MiroShark
cp .env.example .env
# OpenRouter のキーを LLM_API_KEY / SMART_API_KEY /
# NER_API_KEY / OPENAI_API_KEY / EMBEDDING_API_KEY の
# 5 か所に貼り付けてください(同じキーを 5 か所に)。
# 既定の組み合わせは Mimo V2.5 + Gemini 3 Flash です。
./miroshark
```

ランチャーは依存関係を確認し、Neo4j を起動し、フロントエンドとバックエンドをインストールして `:3000` + `:5001` で配信します。Ctrl+C ですべて停止します。`http://localhost:3000` を開き、ドキュメントを投入してください。

**その他のパス** — [Railway / Render ワンクリック・デプロイ](docs/INSTALL.md#one-click-cloud)、[Docker + Ollama](docs/INSTALL.md#option-b-docker--local-ollama)、[手動 Ollama](docs/INSTALL.md#option-c-manual--local-ollama)、[Claude Code CLI](docs/INSTALL.md#option-d-claude-code-no-api-key) — すべて **[docs/INSTALL.md](docs/INSTALL.md)** に記載しています。

<p align="center">
  <img src="./docs/images/miroshark-overview-diagram-v2.jpg" alt="MiroShark 全体像" />
</p>

## 画面の言語

起動後、ナビゲーションバー右上の **中 / EN** トグルをクリックすると英語と中国語を切り替えられます。選択はブラウザに保存され、公開ギャラリーのカード見出しと説明も現在のロケールに追随します。

## ユースケース

- **PR 危機テスト** — プレスリリースを公開する前に、社会の反応をシミュレート
- **市場反応** — 金融ニュースを投入し、模擬トレーダーや投資家のセンチメントを観察
- **広告** — キャンペーン、見出し、ピッチを、出稿前に模擬オーディエンスで検証
- **政策分析** — 規制の草案を、模擬された市民に当てて検証
- **人生の意思決定** — 個人の決断(転職、引っ越し、ローンチのタイミング)をシナリオ化し、多様なペルソナの議論を観察
- **歴史の if** — 歴史上の出来事を書き換え、ペルソナ集団がその後をどう語り直すかを観察
- **創作実験** — 結末のない小説を投入し、エージェントに物語として整合する続きを書かせる

<p align="center">
  <img src="./docs/images/agent-grounding-v2.jpg" alt="エージェントごとの 5 層のグラウンディング:デモグラフィック・シード、Web エンリッチメント、セマンティック検索、関係、グラフ属性" width="100%" />
</p>

## 機能

主なハイライト:

| 機能 | 内容 |
|---|---|
| **スマート・セットアップ** | ドキュメントを投入 → 約 2 秒で Bull / Bear / Neutral 3 シナリオを自動生成 |
| **そのまま質問** | ドキュメントなしで質問を入力 — MiroShark が調査し、シードのブリーフィングを執筆 |
| **反事実ブランチ** | 実行中のシミュレーションをイベント注入で分岐(「ラウンド 24 で CEO が辞任したら?」) |
| **ディレクター・モード** | 分岐せずに、現行タイムラインへ速報を直接投入 |
| **エージェントごとの MCP ツール** | ペルソナがシミュレーション中に本物の MCP ツール(Web 検索、API など)を呼び出す |
| **記事生成** | 実際の投稿と取引にひも付いた Substack 風の振り返り記事 |
| **公開ギャラリーと検証済みの予言** | `/explore` で公開済みシムを閲覧・フォーク、`/verified` で的中した予言を追跡 |
| **どこへでも共有** | ソーシャルカード、リプレイ GIF、ツリー投稿、RSS / Atom、埋め込み、Slack / Discord / Telegram / Webhook 通知 |

…さらに **40 以上** — 共有用サーフェス、エクスポート、連携、可観測性、オンチェーンの引用まで。**[全機能リストと詳細解説は docs/FEATURES.md](docs/FEATURES.md)** をご覧ください。

<p align="center">
  <img src="./docs/images/graph-memory-pipeline-v2.jpg" alt="グラフ記憶パイプライン:取り込み(NER、エンベディング、エンティティ解決、矛盾チェック、時間エッジ)と検索(ベクトル + BM25 + BFS の融合、リランク)" width="100%" />
</p>

## ドキュメント

| | |
|---|---|
| [インストール](docs/INSTALL.md) | あらゆるデプロイ経路:クラウド、Docker、Ollama、Claude Code |
| [設定](docs/CONFIGURATION.md) | 環境変数、モデルルーティング、フィーチャーフラグ |
| [モデル](docs/MODELS.md) | クラウド既定、ローカル Ollama モデル、ベンチマーク所見 |
| [アーキテクチャ](docs/ARCHITECTURE.md) | シミュレーション・エンジン、記憶パイプライン、グラフ検索 |
| [機能](docs/FEATURES.md) | 上記の機能一覧、各項目の詳細 |
| [HTTP API](docs/API.md) | 関心事ごとにグループ化された全エンドポイント — `/api/docs` の対話的 Swagger UI と `/api/openapi.yaml` の仕様も含む |
| [CLI](docs/CLI.md) | `miroshark-cli` リファレンス |
| [MCP](docs/MCP.md) | Claude Desktop / Cursor / Windsurf / Continue 連携 + レポート用エージェントツール(設定 → AI 連携で自動生成スニペット) |
| [Webhook](docs/WEBHOOKS.md) | 完了 Webhook のペイロード、ヘッダー、配送セマンティクス、Slack / Discord / Zapier / n8n のレシピ |
| [DKG 引用](docs/DKG.md) | OriginTrail DKG アンカリング — 完了済みシムの UAL + Merkle ルート + オンチェーン引用キー |
| [WaybackClaw アーカイブ](docs/WAYBACKCLAW.md) | WaybackClaw 投稿 — 完了済みシムのスナップショット id + IPFS CID + Nostr イベント id |
| [可観測性](docs/OBSERVABILITY.md) | デバッグパネル、イベントストリーム、ロギング |
| [エコシステム](ECOSYSTEM.md) | MiroShark の上に構築されたプロジェクト、エージェント、プロダクト |
| [コントリビュート](CONTRIBUTING.md) | テストと開発 |

---

## ライセンス

AGPL-3.0。[LICENSE](./LICENSE) を参照してください。

プロジェクトを支援する:`0xd7bc6a05a56655fb2052f742b012d1dfd66e1ba3`

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=aaronjmars/miroshark&type=Date)](https://www.star-history.com/#aaronjmars/miroshark&Date)
