#!/bin/zsh
# 公式LINEのリッチメニュー画像（2500×1686・PNG・1MB以下）を richmenu/index.html から生成する
#
# 使い方:
#   cd ~/dev/ai-jvhiro-lp && zsh richmenu/build.sh
#
# 出力:
#   richmenu/richmenu-2500x1686.png
#   iCloud の「Cursor/インスタ投稿」に「LINEリッチメニュー_2500x1686.png」としてコピー
#   docs/screenshots/richmenu_preview_390.png（390px幅の確認用・git管理外）
#
# 必要なもの: Google Chrome（/Applications）、python3 + Pillow（macOS標準のpython3にPillowが入っていること）
# フォントは pdf/fonts/*.woff を共用する（無ければ pdf/build.sh と同じURLから取得）

set -eu
cd "$(dirname "$0")/.."   # リポジトリのルートへ

CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
OUT="richmenu/richmenu-2500x1686.png"
PREVIEW="docs/screenshots/richmenu_preview_390.png"
ICLOUD_DIR="$HOME/Library/Mobile Documents/com~apple~CloudDocs/Cursor/インスタ投稿"
ICLOUD_NAME="LINEリッチメニュー_2500x1686.png"
FONT_DIR="pdf/fonts"
FONT_REG_URL="https://fonts.gstatic.com/s/notosansjp/v56/-F6jfjtqLzI2JPCgQBnw7HFyzSD-AsregP8VFBEj75g.woff"
FONT_BOLD_URL="https://fonts.gstatic.com/s/notosansjp/v56/-F6jfjtqLzI2JPCgQBnw7HFyzSD-AsregP8VFPYk75g.woff"

[ -x "$CHROME" ] || { echo "Google Chrome が見つかりません: $CHROME" >&2; exit 1; }
for cmd in curl file python3; do
  command -v "$cmd" >/dev/null || { echo "$cmd が見つかりません" >&2; exit 1; }
done
python3 -c "import PIL" 2>/dev/null || { echo "python3 に Pillow が入っていません（pip3 install pillow）" >&2; exit 1; }

# フォントが無ければ取得（pdf/build.sh と同じ）
mkdir -p "$FONT_DIR"
for pair in "NotoSansJP-Regular.woff|$FONT_REG_URL" "NotoSansJP-Bold.woff|$FONT_BOLD_URL"; do
  name="${pair%%|*}"; url="${pair#*|}"
  if [ ! -s "$FONT_DIR/$name" ]; then
    echo "フォントを取得します: $name"
    tmp="$FONT_DIR/$name.download"
    if ! curl -fsSL -o "$tmp" "$url" || ! file "$tmp" | grep -q "Web Open Font Format"; then
      rm -f "$tmp"
      echo "フォントの取得に失敗しました（$name）。$FONT_DIR/ に手動で置いてください" >&2
      exit 1
    fi
    mv "$tmp" "$FONT_DIR/$name"
  fi
done

# 一時ファイル（終了時にまとめて削除）
TMPD=$(mktemp -d -t richmenu)
trap 'rm -rf "$TMPD"' EXIT
RAW="$TMPD/raw.png"
LOG="$TMPD/chrome.log"
CAND="$TMPD/richmenu.png"

# スクリーンショット（原寸 2500×1686、拡大率1）
if ! "$CHROME" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1 \
     --window-size=2500,1686 --screenshot="$RAW" "file://$PWD/richmenu/index.html" >"$LOG" 2>&1 || [ ! -s "$RAW" ]; then
  echo "画像の生成に失敗しました。Chrome の出力:" >&2
  tail -n 20 "$LOG" >&2
  exit 1
fi

# サイズ検証・PNG最適化（256色に減色して1MB以下に収める）・プレビュー作成
# 検証に通るまで既存の成果物（$OUT）には触らない
mkdir -p docs/screenshots
python3 - "$RAW" "$CAND" "$PREVIEW" <<'EOF'
import sys, os
from PIL import Image
raw, out, preview = sys.argv[1:4]
im = Image.open(raw).convert("RGB")
if im.size != (2500, 1686):
    sys.exit(f"サイズが想定と違います: {im.size}（2500x1686 が必要）")
im.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).save(out, optimize=True)
size = os.path.getsize(out)
if size > 1_000_000:
    sys.exit(f"1MB を超えました: {size} bytes")
im.resize((390, round(1686 * 390 / 2500)), Image.LANCZOS).save(preview, optimize=True)
print(f"検証OK: {size//1024} KB, {im.size[0]}x{im.size[1]}")
print(f"プレビュー: {preview}")
EOF
mv "$CAND" "$OUT"
echo "生成: $OUT"

# iCloud にコピー（同じフォルダ内の一時名に書いてから置き換える。途中で失敗しても既存ファイルは残る）
if [ -d "$ICLOUD_DIR" ]; then
  cp "$OUT" "$ICLOUD_DIR/.$ICLOUD_NAME.tmp" && mv "$ICLOUD_DIR/.$ICLOUD_NAME.tmp" "$ICLOUD_DIR/$ICLOUD_NAME"
  echo "コピー: $ICLOUD_DIR/$ICLOUD_NAME"
else
  echo "iCloud フォルダが見つからないためコピーは省略: $ICLOUD_DIR" >&2
fi
