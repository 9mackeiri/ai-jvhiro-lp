# 公式LINE リッチメニュー（手動アップロード用）

LINE公式アカウント「50代からのAI相棒｜ひろき」のリッチメニュー画像と、管理画面で設定するための座標表。

| ファイル | 役割 |
|---|---|
| `richmenu-2500x1686.png` | アップロードする画像（大サイズ 2500×1686、PNG、1MB 以下） |
| `index.html` | 画像の元（文言・配色はここ） |
| `build.sh` | 画像を再生成するスクリプト（`zsh richmenu/build.sh`）。iCloud にもコピーする |
| `logos/` | 各社の公式ロゴ素材（下の「ロゴの取得元」参照。無加工・縮小のみ） |

iCloud のコピー先：`Cursor/インスタ投稿/LINEリッチメニュー_2500x1686.png`

## 画像の構成

- 白地。画像全体を 2×2 に 4 等分（1つのボタンは 1250×843px。LINE の「2×2」テンプレートと同じ分割）
- 区切りは中央の縦横 2 本、薄い灰色（#d9d9d9・2px）
- 各セルの中央に大きなロゴ（見た目の高さ 370px＝セル高の約 44%。3社のアイコンでそろえている）、その下に太字の名前、必要なら小さく一言

```
  0        1250       2500
  ┌──────────┬──────────┐  y=0
  │ Instagram│  TikTok  │
  ├──────────┼──────────┤  y=843
  │  note(n) │ 質問する │
  └──────────┴──────────┘  y=1686
```

## タップ領域と動作（管理画面に入力する値）

| 領域 | 表示 | x | y | 幅 | 高さ | アクション | 設定する値 |
|---|---|---|---|---|---|---|---|
| 1（左上） | Instagram | 0 | 0 | 1250 | 843 | リンク | https://www.instagram.com/ai_jvhiro/ |
| 2（右上） | TikTok／準備中 | 1250 | 0 | 1250 | 843 | テキスト（当面） | TikTokは準備中です |
| 3（左下） | note／準備中 | 0 | 843 | 1250 | 843 | テキスト（当面） | noteは準備中です |
| 4（右下） | 質問する／そのまま送ってOK | 1250 | 843 | 1250 | 843 | テキスト | 質問があります |

- 領域 2・3 は、TikTok / note の URL が決まったら「リンク」に差し替える。画像の「準備中」の文字も
  `index.html` から消して `zsh richmenu/build.sh` で再生成し、画像を上げ直す
- 「テキスト」は、タップした人のトーク画面にその文が送信されるアクション。応答メッセージ（キーワード応答）で
  「質問があります」「TikTokは準備中です」「noteは準備中です」への返事を用意しておくと自然

## ロゴの取得元（公式ブランド素材）

| ロゴ | 使ったファイル | 取得元 |
|---|---|---|
| Instagram | `logos/Instagram_Glyph_Gradient.png`（公式 PNG 5000px を 1000px に縮小） | Meta Brand Resource Center「Instagram」 https://www.meta.com/brand/resources/instagram/instagram-brand/ の Logo pack（IG_brand_asset_pack_2023.zip）内 `01 Static Glyph/01 Gradient Glyph/Instagram_Glyph_Gradient.png` |
| TikTok | `logos/TikTok_Icon_Black_Circle.png`（無加工） | TikTok for Developers「Design Guidelines」 https://developers.tiktok.com/doc/getting-started-design-guidelines の Logo pack（logo-pack.zip）内 `TikTok Logo Pack/TikTok – Icons/TikTok_Icon_Black_Circle.png` |
| note | `logos/note_icon.svg`（角丸の「n」アイコン・無加工） | noteヘルプセンター「ブランドガイドライン（ロゴデータ・カラー）」 https://www.help-note.com/hc/ja/articles/360000235582 の `note Visual Identity.zip` 内 `app/icon.svg`。同梱のガイドライン PDF を `logos/note_Visual_Identity.pdf` として保存。ワードマーク `logos/note_logo.svg`（同 zip の `main/logo.svg`）は旧版で使ったもので、現在は未使用 |

各社の主な利用条件（取得時点の要約。最新は各ページで確認）：

- Instagram（Meta）：Brand Resource Center の素材をそのまま使う。色・比率の変更不可。提携や公認を示唆する使い方は不可。「Instagram」は大文字始まりで表記
- TikTok：ロゴの色・比率・効果の変更不可。周囲に十分な余白を取る。TikTok for Developers のページには「事前の書面許可なくロゴを使えない」との記載がある（アプリ開発者向けの規定。SNS 導線としての表示が問題になる場合は差し替える）
- note：基本色は黒（#000000）、サブカラーは白。影・装飾・変形・アウトライン化は不可。ヘルプページの「ソーシャルアイコンと並列に並ぶ場合」「小さく表示する場合は n のアイコンを正方形（角丸含む）・正円でのみ使用可」に沿い、角丸の「n」アイコン（app/icon.svg）を使用している

## 管理画面での設定手順（LINE Official Account Manager）

1. https://manager.line.biz/ を開き、アカウント「50代からのAI相棒｜ひろき」を選ぶ
2. 左メニュー「トークルーム管理」→「リッチメニュー」→「作成」
3. 表示設定：タイトル（管理用。例：メインメニュー）、表示期間（開始日だけ入れて終了日は空欄でよい）、メニューバーのテキスト（例：メニュー）、デフォルト表示「表示する」
4. コンテンツ設定：「テンプレートを選択」→ 大サイズの「2×2（4分割）」を選ぶ
5. 「画像をアップロード」→ `richmenu-2500x1686.png` を選ぶ
6. 領域 A〜D に、上の表の 1〜4 の順で「アクション」を設定する（A=左上、B=右上、C=左下、D=右下）
   - 1 は「リンク」を選んで URL を貼る
   - 2・3・4 は「テキスト」を選んで、表の文をそのまま入力する
7. 「保存」→ 一覧で「公開」にする
8. 自分のスマホの LINE でトーク画面を開き、4つのボタンがそれぞれ正しく動くことを確認する

補足：画像の分割は「2×2」テンプレート（4 等分）と完全に一致させてあるので、テンプレートを選ぶだけで
上の表の座標どおりになります。Messaging API 等で座標を直接指定する場合も、上の表の x, y, 幅, 高さをそのまま使えます。

## 再生成

```bash
cd ~/dev/ai-jvhiro-lp
zsh richmenu/build.sh
```

`index.html` の文言や配色を直してから実行すると、PNG・iCloud のコピー・`docs/screenshots/richmenu_preview_390.png` が更新されます。
