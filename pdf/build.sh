#!/bin/zsh
# 登録特典PDFを pdf/index.html から再生成する
#
# 使い方:
#   cd ~/dev/ai-jvhiro-lp && zsh pdf/build.sh
#
# 出力:
#   assets/pdf/ai-first5-<ランダム8文字>.pdf  （既存のPDFがあればそのファイル名を使う）
#   iCloud の「Cursor/インスタ投稿」に「50代がAIを始めるときに最初にやる5つ.pdf」としてコピー
#
# 必要なもの: Google Chrome（/Applications）、curl、file、python3（macOS標準）
# フォント (pdf/fonts/*.woff) は無ければ自動で取得する（git管理外・約6MB）

set -eu
setopt null_glob
cd "$(dirname "$0")/.."   # リポジトリのルートへ

CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
# Google Fonts が配信している静的フォント（Regular/Bold）。古いUA向けに返される .woff を使う
FONT_DIR="pdf/fonts"
FONT_REG_URL="https://fonts.gstatic.com/s/notosansjp/v56/-F6jfjtqLzI2JPCgQBnw7HFyzSD-AsregP8VFBEj75g.woff"
FONT_BOLD_URL="https://fonts.gstatic.com/s/notosansjp/v56/-F6jfjtqLzI2JPCgQBnw7HFyzSD-AsregP8VFPYk75g.woff"
OUT_DIR="assets/pdf"
ICLOUD_DIR="$HOME/Library/Mobile Documents/com~apple~CloudDocs/Cursor/インスタ投稿"
ICLOUD_NAME="50代がAIを始めるときに最初にやる5つ.pdf"

[ -x "$CHROME" ] || { echo "Google Chrome が見つかりません: $CHROME" >&2; exit 1; }
for cmd in curl file python3; do
  command -v "$cmd" >/dev/null || { echo "$cmd が見つかりません" >&2; exit 1; }
done

# フォントが無ければ取得（URLが変わったときは pdf/fonts/ に手動で置けばよい）
mkdir -p "$FONT_DIR"
for pair in "NotoSansJP-Regular.woff|$FONT_REG_URL" "NotoSansJP-Bold.woff|$FONT_BOLD_URL"; do
  name="${pair%%|*}"; url="${pair#*|}"
  if [ ! -s "$FONT_DIR/$name" ]; then
    echo "フォントを取得します: $name"
    tmp="$FONT_DIR/$name.download"
    # -f: HTTPエラー時は失敗扱い。一時ファイルに落として中身を確認してから正式名に置く
    if ! curl -fsSL -o "$tmp" "$url" || ! file "$tmp" | grep -q "Web Open Font Format"; then
      rm -f "$tmp"
      echo "フォントの取得に失敗しました（$name）。$FONT_DIR/ に手動で置いてください" >&2
      exit 1
    fi
    mv "$tmp" "$FONT_DIR/$name"
  fi
done

# 出力ファイル名（既存があればそれを使い、無ければランダム8文字で作る）
mkdir -p "$OUT_DIR"
EXISTING=("$OUT_DIR"/ai-first5-*.pdf)
if [ ${#EXISTING[@]} -gt 1 ]; then
  echo "assets/pdf/ に PDF が複数あります。1つだけ残してから再実行してください:" >&2
  printf '  %s\n' "${EXISTING[@]}" >&2
  exit 1
elif [ ${#EXISTING[@]} -eq 1 ]; then
  OUT="${EXISTING[1]}"
else
  OUT="$OUT_DIR/ai-first5-$(python3 -c 'import secrets; print(secrets.token_hex(4))').pdf"
fi

# PDF化（ヘッダー・フッターなし、背景色あり）。Chrome の出力はログに残し、失敗時だけ表示する
LOG=$(mktemp -t ai-first5-build)
if ! "$CHROME" --headless=new --disable-gpu --no-pdf-header-footer \
     --print-to-pdf="$PWD/$OUT" "file://$PWD/pdf/index.html" >"$LOG" 2>&1 || [ ! -s "$OUT" ]; then
  echo "PDFの生成に失敗しました。Chrome の出力（$LOG）:" >&2
  tail -n 20 "$LOG" >&2
  exit 1
fi
rm -f "$LOG"
echo "生成: $OUT ($(du -h "$OUT" | cut -f1))"

# iCloud にコピー
if [ -d "$ICLOUD_DIR" ]; then
  cp "$OUT" "$ICLOUD_DIR/$ICLOUD_NAME"
  echo "コピー: $ICLOUD_DIR/$ICLOUD_NAME"
else
  echo "iCloud フォルダが見つからないためコピーは省略: $ICLOUD_DIR" >&2
fi
