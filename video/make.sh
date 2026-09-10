#!/bin/zsh
# 動画1本にテロップを入れて縦型（1080×1920・30fps）で書き出す
#
# 使い方:
#   cd ~/dev/ai-jvhiro-lp
#   zsh video/make.sh <入力ファイル名> [--mode highlight|full] [--title "見出し"] [--title-seconds 2] [--crop left|center|right] [--skip-transcribe] [--no-title]
#   見出しが出ている間（--title-seconds 秒、既定 2）は q（質問）のテロップを出さず、消えた直後から出す
#
#   入力ファイル名は iCloud の「Cursor/インスタ投稿/動画/入力」に置いたファイル名（例: IMG_8930.MOV）
#
# 流れ:
#   1. 音声を取り出し、whisper.cpp（Mac 内・外部送信なし）で日本語の字幕 SRT を作る
#      → 「動画/字幕/<名前>.srt」に保存（既にあれば .bak-日時 を残してから上書き）
#   2. テロップの画像を作る（video/render_overlays.py）
#      --mode highlight（既定）: 「動画/字幕/<名前>.highlight.txt」の要点テロップ（質問・答えの要点・数字）だけを出す
#        このファイルが無ければ SRT から下書きを作って保存し、そこで止まる（直してから再実行）
#      --mode full: SRT の全文字幕を出す
#   3. 9:16 に切り出し → 字幕を重ねる → 音量を標準化 → H.264/AAC で書き出し
#      → 「動画/出力/<名前>_reel.mp4」（前回の出力は「出力/前回/」に 1 世代だけ残す）
#      確認用の静止画3枚を「動画/出力/確認用/」に置く
#
# テロップを直すとき: 字幕/<名前>.highlight.txt（要点）か 字幕/<名前>.srt（全文）を編集して、
#   --skip-transcribe を付けて同じコマンドを実行する
#   SRT の行の先頭に「J:」を付けると、その字幕は薄いシアン（ジャービス）になる（全文モード）
#
# 必要なもの: ffmpeg, whisper-cli（brew install ffmpeg whisper-cpp）, python3 + Pillow
# 文字起こしモデル ggml-large-v3-turbo.bin（約1.6GB）は無ければ ~/.cache/whisper-cpp/ に自動取得

set -eu
setopt null_glob
cd "$(dirname "$0")/.."   # リポジトリのルートへ
REPO="$PWD"

BASE="$HOME/Library/Mobile Documents/com~apple~CloudDocs/Cursor/インスタ投稿/動画"
IN_DIR="$BASE/入力"; SRT_DIR="$BASE/字幕"; OUT_DIR="$BASE/出力"; STILL_DIR="$OUT_DIR/確認用"
MODEL_DIR="$HOME/.cache/whisper-cpp"
MODEL="$MODEL_DIR/ggml-large-v3-turbo.bin"
MODEL_URL="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin"
FONT_DIR="$REPO/video/fonts"
FONT_BOLD="$FONT_DIR/NotoSansJP-Bold.ttf"
WOFF_BOLD="$REPO/pdf/fonts/NotoSansJP-Bold.woff"
WOFF_BOLD_URL="https://fonts.gstatic.com/s/notosansjp/v56/-F6jfjtqLzI2JPCgQBnw7HFyzSD-AsregP8VFPYk75g.woff"
WHISPER_PROMPT="ジャービス、売上、在庫、取引先、Excel、AI、相棒。"

# ---------- 引数 ----------
usage() { sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }
[ $# -ge 1 ] || usage
INPUT_NAME="$1"; shift
ORIG_OPTS=()   # 下書き後の再実行案内に引き継ぐオプション（--skip-transcribe 以外）
for arg in "$@"; do [ "$arg" != "--skip-transcribe" ] && ORIG_OPTS+=("$arg"); done
case "$INPUT_NAME" in
  */*|.*|"") echo "入力ファイル名はフォルダを含まない名前だけを指定してください（例: IMG_8930.MOV）" >&2; exit 2 ;;
esac
TITLE="50代・非エンジニア|が作ったAI相棒"   # 「|」は改行位置（表示されない）
CROP="center"; SKIP_TRANSCRIBE=0; NO_TITLE=0; MODE="highlight"; TITLE_SECONDS="2"
while [ $# -gt 0 ]; do
  case "$1" in
    --mode) [ $# -ge 2 ] || usage; MODE="$2"; shift 2 ;;
    --title) [ $# -ge 2 ] || usage; TITLE="$2"; shift 2 ;;
    --title-seconds) [ $# -ge 2 ] || usage; TITLE_SECONDS="$2"; shift 2 ;;
    --crop) [ $# -ge 2 ] || usage; CROP="$2"; shift 2 ;;
    --skip-transcribe) SKIP_TRANSCRIBE=1; shift ;;
    --no-title) NO_TITLE=1; shift ;;
    *) echo "不明な引数: $1" >&2; usage ;;
  esac
done
case "$CROP" in left|center|right) ;; *) echo "--crop は left / center / right のどれか" >&2; exit 2 ;; esac
case "$MODE" in highlight|full) ;; *) echo "--mode は highlight / full のどちらか" >&2; exit 2 ;; esac
[[ "$TITLE_SECONDS" =~ ^[0-9]+(\.[0-9]+)?$ ]] || { echo "--title-seconds は秒数（例: 2 や 1.5）を指定してください" >&2; exit 2; }

INPUT="$IN_DIR/$INPUT_NAME"
NAME="${INPUT_NAME%.*}"
SRT="$SRT_DIR/$NAME.srt"
HL="$SRT_DIR/$NAME.highlight.txt"
OUT="$OUT_DIR/${NAME}_reel.mp4"

# ---------- 事前チェック ----------
for cmd in ffmpeg ffprobe whisper-cli python3 curl; do
  command -v "$cmd" >/dev/null || { echo "$cmd が見つかりません（brew install ffmpeg whisper-cpp）" >&2; exit 1; }
done
python3 -c "import PIL" 2>/dev/null || { echo "python3 に Pillow が入っていません（pip3 install pillow）" >&2; exit 1; }
[ -f "$INPUT" ] || { echo "入力が見つかりません: $INPUT" >&2; ls "$IN_DIR" >&2 2>/dev/null; exit 1; }
if [ ! -s "$INPUT" ] || [ -e "$IN_DIR/.$INPUT_NAME.icloud" ]; then
  echo "iCloud から未取得です。取得します（最大 10 分待ちます）..."
  brctl download "$INPUT" || { echo "brctl download に失敗しました" >&2; exit 1; }
  for i in $(seq 1 120); do
    [ -s "$INPUT" ] && [ ! -e "$IN_DIR/.$INPUT_NAME.icloud" ] && break
    sleep 5
  done
  [ -s "$INPUT" ] || { echo "iCloud からの取得が終わりません: $INPUT" >&2; exit 1; }
fi
mkdir -p "$SRT_DIR" "$OUT_DIR" "$STILL_DIR" "$FONT_DIR" "$MODEL_DIR"

# フォント（Pillow 用の TTF）。pdf/fonts の woff を変換して作る
if [ ! -s "$FONT_BOLD" ]; then
  if [ ! -s "$WOFF_BOLD" ]; then
    echo "フォント（woff）を取得します..."
    mkdir -p "$(dirname "$WOFF_BOLD")"
    curl -fsSL -o "$WOFF_BOLD.download" "$WOFF_BOLD_URL"
    file "$WOFF_BOLD.download" | grep -q "Web Open Font Format" || { rm -f "$WOFF_BOLD.download"; echo "フォントの取得に失敗しました（中身が WOFF ではない）" >&2; exit 1; }
    mv "$WOFF_BOLD.download" "$WOFF_BOLD"
  fi
  python3 "$REPO/video/woff2ttf.py" "$WOFF_BOLD" "$FONT_BOLD"
fi

# 文字起こしモデル
if [ "$SKIP_TRANSCRIBE" -eq 0 ] && [ ! -s "$MODEL" ]; then
  echo "文字起こしモデル（約1.6GB）を取得します..."
  curl -fL --progress-bar -o "$MODEL.download" "$MODEL_URL"
  # 中身の検査: ggml のマジック（先頭 4 バイト "lmgg"）と大きさ（1.5GB 以上）
  if [ "$(head -c 4 "$MODEL.download")" != "lmgg" ] || [ "$(stat -f %z "$MODEL.download")" -lt 1500000000 ]; then
    rm -f "$MODEL.download"; echo "モデルの取得に失敗しました（中身が想定と違う）" >&2; exit 1
  fi
  mv "$MODEL.download" "$MODEL"
fi

WORK=$(mktemp -d -t reel)
trap 'rm -rf "$WORK"' EXIT
T0=$(date +%s)

# ---------- 1. 文字起こし ----------
if [ "$SKIP_TRANSCRIBE" -eq 0 ]; then
  echo "[1/3] 文字起こし（whisper.cpp / large-v3-turbo）..."
  ffmpeg -y -v error -i "$INPUT" -map 0:a:0 -ac 1 -ar 16000 -c:a pcm_s16le "$WORK/audio.wav"
  whisper-cli -m "$MODEL" -l ja -f "$WORK/audio.wav" -t 8 -bs 5 -ml 28 \
    --prompt "$WHISPER_PROMPT" -osrt -of "$WORK/sub" -np >"$WORK/whisper.log" 2>&1 \
    || { echo "文字起こしに失敗しました:" >&2; tail -n 20 "$WORK/whisper.log" >&2; exit 1; }
  [ -s "$WORK/sub.srt" ] || { echo "字幕が空でした（音声が無い？）" >&2; exit 1; }
  if [ -s "$SRT" ]; then
    BAK="$SRT.bak-$(date +%Y%m%d-%H%M%S)"
    cp "$SRT" "$BAK"; echo "  既存の字幕を控えました: $BAK"
  fi
  cp "$WORK/sub.srt" "$SRT"
  echo "  字幕を保存: $SRT"
else
  echo "[1/3] 文字起こしを省略（--skip-transcribe）。字幕: $SRT"
  [ -s "$SRT" ] || { echo "字幕ファイルがありません: $SRT" >&2; exit 1; }
fi
T1=$(date +%s)

# ---------- 2. テロップ・見出しの画像 ----------
DURATION=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$INPUT")
TITLE_ARGS=(--title "$TITLE" --title-seconds "$TITLE_SECONDS"); [ "$NO_TITLE" -eq 1 ] && TITLE_ARGS+=(--no-title)
if [ "$MODE" = "highlight" ]; then
  if [ ! -s "$HL" ]; then
    [ -s "$SRT" ] || { echo "字幕（SRT）がありません: $SRT — --skip-transcribe を外して文字起こしから実行してください" >&2; exit 1; }
    python3 "$REPO/video/highlight_draft.py" "$SRT" "$HL"
    RERUN="zsh video/make.sh \"$INPUT_NAME\" --skip-transcribe"
    for o in "${ORIG_OPTS[@]}"; do RERUN="$RERUN \"$o\""; done
    echo
    echo "要点テロップの下書きを作りました。文を短く直してから、次のコマンドで書き出してください:"
    echo "  $RERUN"
    echo "  （全文字幕にしたいときは --mode full）"
    exit 0
  fi
  echo "[2/3] 要点テロップと見出しの画像を作成（$HL）..."
  python3 "$REPO/video/render_overlays.py" --highlight "$HL" --duration "$DURATION" \
    --out-dir "$WORK/ov" --font-bold "$FONT_BOLD" "${TITLE_ARGS[@]}"
else
  echo "[2/3] 全文字幕と見出しの画像を作成（$SRT）..."
  python3 "$REPO/video/render_overlays.py" --srt "$SRT" --duration "$DURATION" \
    --out-dir "$WORK/ov" --font-bold "$FONT_BOLD" "${TITLE_ARGS[@]}"
fi

# ---------- 3. 切り出し・合成・書き出し ----------
echo "[3/3] 9:16 に切り出して字幕を重ね、音量を整えて書き出し（--crop $CROP）..."
# 音量の標準化は 2 パス（1 回目で測り、2 回目でその値を使って正確に -14 LUFS に合わせる）
LN_TARGET="I=-14:TP=-1.5:LRA=11"
ffprobe -v error -select_streams a:0 -show_entries stream=codec_type -of csv=p=0 "$INPUT" | grep -q audio \
  || { echo "入力に音声がありません: $INPUT" >&2; exit 1; }
if ! ffmpeg -v info -i "$INPUT" -map 0:a:0 -af "loudnorm=$LN_TARGET:print_format=json" -f null - 2>"$WORK/ln.log"; then
  echo "  音量の測定でエラー（1 パスで続行）:" >&2; tail -n 5 "$WORK/ln.log" >&2
fi
LN_MEASURED=$(python3 - "$WORK/ln.log" <<'EOF'
import json, re, sys
log = open(sys.argv[1], encoding="utf-8", errors="replace").read()
m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", log, re.S)
if not m:
    sys.exit(0)  # 測定できなければ 1 パスにフォールバック
d = json.loads(m.group(0))
print(f"measured_I={d['input_i']}:measured_TP={d['input_tp']}:measured_LRA={d['input_lra']}:measured_thresh={d['input_thresh']}:offset={d['target_offset']}:linear=true")
EOF
)
if [ -n "$LN_MEASURED" ]; then AF="loudnorm=$LN_TARGET:$LN_MEASURED"; else AF="loudnorm=$LN_TARGET"; echo "  （音量の測定に失敗したため 1 パスで処理）"; fi
case "$CROP" in
  left)   CX="0" ;;
  center) CX="(iw-1080)/2" ;;
  right)  CX="iw-1080" ;;
esac
VF="scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:1920:${CX}:(ih-1920)/2,fps=30,format=yuv420p[base];[1:v]format=rgba[ov];[base][ov]overlay=0:0:eof_action=pass:format=auto,format=yuv420p"
ffmpeg -y -v error -stats -i "$INPUT" -f concat -safe 0 -i "$WORK/ov/list.txt" \
  -filter_complex "[0:v]$VF" \
  -map 0:a:0 -af "$AF" \
  -c:v libx264 -preset medium -crf 20 -profile:v high -level 4.1 -pix_fmt yuv420p -r 30 \
  -c:a aac -b:a 192k -ar 48000 -ac 2 -movflags +faststart -shortest \
  "$WORK/out.mp4"
if [ -s "$OUT" ]; then
  mkdir -p "$OUT_DIR/前回"; mv "$OUT" "$OUT_DIR/前回/${NAME}_reel.mp4"
  echo "  前回の完成動画を控えました: $OUT_DIR/前回/${NAME}_reel.mp4（1 世代のみ）"
fi
mv "$WORK/out.mp4" "$OUT"
T2=$(date +%s)

# 確認用の静止画（冒頭・中盤・終盤）
for pair in "冒頭:1" "中盤:$(python3 -c "print(round($DURATION/2,2))")" "終盤:$(python3 -c "print(max(0, round($DURATION-2,2)))")"; do
  label="${pair%%:*}"; at="${pair#*:}"
  ffmpeg -y -v error -ss "$at" -i "$OUT" -frames:v 1 -q:v 3 "$STILL_DIR/${NAME}_${label}.jpg"
done

echo
echo "完了: $OUT ($(du -h "$OUT" | cut -f1))"
echo "字幕:  $SRT"
[ "$MODE" = "highlight" ] && echo "要点:  $HL"
echo "静止画: $STILL_DIR/${NAME}_{冒頭,中盤,終盤}.jpg"
echo "所要時間: 文字起こし $((T1-T0)) 秒 / 書き出し $((T2-T1)) 秒 / 合計 $((T2-T0)) 秒"
