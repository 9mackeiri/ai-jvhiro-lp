# ai-jvhiro-lp

「50代からのAI相棒｜ひろき」（Instagram @ai_jvhiro）の LINE 登録用ランディングページ。
1ページの静的サイト（HTML/CSS のみ、JS なし）を GitHub Pages で公開しています。

- 公開 URL：https://9mackeiri.github.io/ai-jvhiro-lp/
- 登録先（LINE）：https://lin.ee/yuBrECZ5
- 商品販売はしない。目的は LINE 登録のみ

## ファイル構成

| ファイル | 役割 |
|---|---|
| `index.html` | ページ本体（文面・配色・OGP はすべてここ） |
| `assets/icon.jpg` | アイコン原本（1024×1024）。ページからは直接使わない |
| `assets/icon-480.jpg` | ページ表示用に縮小したアイコン（480×480） |
| `assets/ogp.jpg` | SNS でリンクを貼ったときに出る画像（1200×630） |
| `.nojekyll` | GitHub Pages に「そのまま配信して」と伝えるための空ファイル |
| `docs/screenshots/` | 表示確認用のスクリーンショット置き場（`.gitignore` 済み・公開されない） |

## 文面の直し方（index.html のどこを直すか）

`index.html` の中に、セクションごとに次のようなコメント行があります。直したい場所をこのコメントで探してください。

```
<!-- ============================================================
     これは何？
     ============================================================ -->
```

| 直したい場所 | 探すコメント | 目印になる要素 |
|---|---|---|
| ファーストビュー（見出し・リード文・ボタン①） | `ファーストビュー` | `<header class="hero">` |
| これは何？ | `これは何？` | `<section id="what">` |
| ジャービスにできること | `ジャービスにできること` | `<section id="can">` |
| なぜ発信するのか | `なぜ発信するのか` | `<section id="why">` |
| LINE登録の特典（PDF の5項目・ボタン②） | `LINE登録の特典` | `<section id="gift">` |
| こんな人に／向きません | `こんな人に` | `<section id="who">` |
| 発信している人（プロフィール・ボタン③） | `発信している人` | `<section id="profile">` |
| フッター | `フッター` | `<footer>` |

書き換えるときのルール：

- 文章は `<p>〜</p>` の中、箇条書きは `<li>〜</li>` の中を書き換える。タグ（`<p>` や `</li>`）は消さない
- 見出しは `<h1>` `<h2>` `<h3>` の中を書き換える
- 文の途中で改行したいときは `<br>` を入れる
- ボタンの文字は `<a class="btn-line" ...>` の中にある `<span>〜</span>` の中を書き換える
- LINE の URL を変えるときは、`https://lin.ee/yuBrECZ5` を3か所すべて置き換える（ボタン①②③）

その他：

- **配色**：`<style>` の先頭にある `:root { ... }` の色コードを変える（差し色は `--accent`、LINE ボタンは `--line-green`）
- **文字サイズ**：`body { font-size: 18px; }`（スマホ）と `@media (min-width: 700px)` の中の `font-size: 19px`（PC）
- **OGP（SNS で貼ったときの見出し・説明・画像）**：`<head>` 内の `og:title` `og:description` `og:image` などの `content="..."` を変える
- **アイコンを差し替える**：`assets/icon.jpg` を置き換え、`assets/icon-480.jpg`（480×480）と `assets/ogp.jpg`（1200×630）も作り直す

## 更新の手順（コミット → push で自動反映）

```bash
cd ~/dev/ai-jvhiro-lp
# 1. index.html などを編集して保存
# 2. ブラウザでローカルの index.html を開いて表示を確認（ダブルクリックで開ける）
git add -A
git commit -m "文面を修正"
git push origin main
```

push すると GitHub Pages が自動で再配信します。反映まで通常 1〜2 分です。
公開ページを開いて古いままのときは、ブラウザをスーパーリロード（Mac: Cmd+Shift+R）してください。

## GitHub Pages の設定

- Source：`main` ブランチの `/`（ルート）
- 設定確認：`gh api repos/9mackeiri/ai-jvhiro-lp/pages`
- 配信状況：`gh api repos/9mackeiri/ai-jvhiro-lp/pages/builds/latest`

## 登録特典PDF（50代がAIを始めるときに最初にやる5つ）

| ファイル | 役割 |
|---|---|
| `pdf/index.html` | PDF の元（文面・配色はここ。1つの `<section class="page">` が1ページ） |
| `pdf/build.sh` | PDF を再生成するスクリプト（Google Chrome で PDF 化し、iCloud にもコピー） |
| `pdf/fonts/` | 埋め込み用フォント Noto Sans JP（git 管理外・build.sh が自動取得） |
| `assets/pdf/ai-first5-<ランダム8文字>.pdf` | 公開されている PDF 本体（URL は LINE 登録者にだけ渡す） |
| `robots.txt` | `assets/pdf/` を検索エンジンのクロール対象外にする |

- LP（index.html）から PDF へのリンクは置かない（LINE 登録後にだけ渡すため）
- 文面を直したら `zsh pdf/build.sh` で再生成し、`git add -A && git commit && git push` で公開に反映
- 再生成しても PDF のファイル名（URL）は変わらない。URL を変えたいときは `assets/pdf/` の PDF を削除してから再生成する
- iCloud の保存先：`Cursor/インスタ投稿/50代がAIを始めるときに最初にやる5つ.pdf`（再生成のたびに上書き）

## マーケティング担当（sns-marketer）

- `.claude/agents/sns-marketer.md`：リール／TikTokの傾向調査、インサイトの数字の分析、次の Day N のつかみ・カバー見出し・キャプション・ハッシュタグ案を出す担当（調査とレポート作成のみ。コード・動画・設定には触れない）
- 呼び方の例：「sns-marketerに今週の調査をさせて」「sns-marketerにこのインサイトを分析させて」＋スクショのパス
- レポートの置き場：正本 `marketing/reports/YYYY-MM-DD_テーマ.md`、コピー iCloud `Cursor/インスタ投稿/マーケ調査/`（同じファイル名）

## 毎日の流れ（リール 1 本）

1. 撮影前に `/satsuei`（撮影メモ。Day 番号・テーマ・質問文・カバー見出し候補を 7 行以内。iCloud `Cursor/インスタ投稿/動画/撮影メモ/YYYY-MM-DD_DayN.md` に保存）
2. 撮影 → `/telop`（テロップ・カバー・書き出し）→ `/caption`（キャプション 2 本）→ 投稿
3. 週 1 回、インサイトのスクショを iCloud `Cursor/インスタ投稿/インサイト/日付/` に置き、sns-marketer に分析させる（重い調査・分析はここに寄せる）
- 3 つのコマンドは `marketing/reports/` の最新レポート（インサイト分析・投稿前チェック・採用した変更の各 1 本）の「今回の結論」「次の回への具体案」を読んでから案を出す。レポートが更新されると、読む内容も新しくなる
- 撮影メモ・レポートは提案。README・`docs/caption_template.md`・各コマンドの既存ルールが優先で、その日の木田の判断を上書きしない
