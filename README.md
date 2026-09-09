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
