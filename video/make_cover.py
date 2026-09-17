#!/usr/bin/env python3
"""リールのカバー画像（Instagram のプロフィール一覧に出るサムネイル）を 1 枚作る。

  python3 video/make_cover.py --input 入力.MOV --cover-txt 名前.cover.txt --font-bold Bold.ttf --out 名前_cover.png
  python3 video/make_cover.py --input 入力.MOV --day 4 --line1 "100万超えの朝" --line2 "大口が1件入った日" ...

  --input       元の動画（動画から 1 コマを取り出して背景にする。make.sh と同じ 9:16 の切り出し）
  --frame       代わりに背景の画像ファイルを直接指定する（--input の代わり）
  --at 秒       取り出す時刻。省略時は --highlight の最初の q（質問）の中間、それも無ければ 5 秒
  --crop        横動画のとき 9:16 に切る位置（left / center / right。既定 center）
  --cover-txt   見出しファイル。1 行目が Day 番号（「4」でも「Day 4」でも可）、2〜3 行目が見出し。# で始まる行は無視
  --day/--line1/--line2   ファイルの代わりに直接指定（両方あれば直接指定が優先）
  --preview-out 一覧で見える範囲（中央 1080×1350）だけを切り抜いた確認用 PNG の出力先

できあがり: 1080×1920 の PNG。文字はすべて中央の 1080×1350（4:5）の範囲に収める（一覧ではそこだけが見える）
  上: 「Day N」の小さなバッジ（LP の差し色の丸角・白文字）
  中央: 見出し 2 行（太字・白と薄いシアン・黒縁＋影）
  下: 「50代・非エンジニアが自作したAI相棒」「コメント『最初の一歩』で無料PDF」
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

W, H = 1080, 1920
SAFE_H = 1350                      # 一覧で見える高さ（4:5）。文字はこの範囲に収める
SAFE_TOP = (H - SAFE_H) // 2       # = 285
SAFE_BOTTOM = SAFE_TOP + SAFE_H    # = 1635

# ===== 見た目の設定 =====
DARKEN = 0.6                        # 背景の明度（1.0 = そのまま）
ACCENT = (2, 132, 199, 255)         # LP の --accent（#0284c7）
WHITE = (255, 255, 255, 255)
CYAN = (190, 240, 255, 255)         # 動画の a テロップと同じ薄いシアン（2 行目）
OUTLINE = (0, 0, 0, 255)

BADGE_FONT_SIZE = 52
BADGE_PAD_X, BADGE_PAD_Y = 34, 14
BADGE_RADIUS = 22
BADGE_CENTER_Y = SAFE_TOP + 130

HEAD_FONT_MAX = 112                 # 見出しの最大サイズ。幅に収まるまで小さくする
HEAD_FONT_MIN = 72
HEAD_MAX_WIDTH = 980
HEAD_CENTER_Y = H // 2 + 20
HEAD_LINE_GAP = 26
HEAD_OUTLINE_W = 8
HEAD_SHADOW = (8, 8)                # 影のずれ（px）
HEAD_SHADOW_BLUR = 10

FOOT_LINES = ["50代・非エンジニアが自作したAI相棒", "コメント『最初の一歩』で無料PDF"]
FOOT_FONT_SIZE = 40
FOOT_LINE_GAP = 14
FOOT_OUTLINE_W = 4
FOOT_BOTTOM_Y = SAFE_BOTTOM - 110   # 下段 2 行の下端

MISSING_TITLE = "見出し未設定"


def die(msg):
    print(msg, file=sys.stderr)
    sys.exit(1)


# ---------- 見出しファイル ----------
def read_cover_txt(path):
    """1 行目 Day 番号、2〜3 行目 見出し。# 行は無視。無い・足りないときは (None, None, None) を返す。"""
    if not path or not os.path.isfile(path):
        return None, None, None
    lines = []
    with open(path, encoding="utf-8") as f:
        for raw in f:
            s = raw.strip()
            if s and not s.startswith("#"):
                lines.append(s)
    if not lines:
        return None, None, None
    m = re.fullmatch(r"(?:Day\s*)?(\d+)", lines[0], re.IGNORECASE)
    if m:
        day, heads = m.group(1), lines[1:]
    else:
        day, heads = None, lines          # 1 行目が Day 番号でなければ全部を見出しとして扱う
    l1 = heads[0] if len(heads) > 0 else None
    l2 = heads[1] if len(heads) > 1 else None
    return day, l1, l2


def first_q_mid(highlight_path):
    """highlight.txt の最初の q キューの中間時刻。無ければ None。"""
    if not highlight_path or not os.path.isfile(highlight_path):
        return None
    with open(highlight_path, encoding="utf-8") as f:
        for raw in f:
            s = raw.strip()
            if not s or s.startswith("#"):
                continue
            parts = [p.strip() for p in s.split("|")]
            if len(parts) < 3 or parts[1] != "q":
                continue
            m = re.match(r"([\d.]+)\s*-\s*([\d.]+)", parts[0])
            if m:
                a, b = float(m.group(1)), float(m.group(2))
                return round((a + b) / 2, 2)
    return None


# ---------- 背景 ----------
def grab_frame(video, at, crop):
    """動画から 1 コマを 1080×1920 で取り出す（make.sh と同じ切り出し）。"""
    cx = {"left": "0", "center": "(iw-1080)/2", "right": "iw-1080"}[crop]
    vf = f"scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:1920:{cx}:(ih-1920)/2"
    fd, tmp = tempfile.mkstemp(suffix=".png", prefix="cover_frame_")
    os.close(fd)
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(at), "-i", video, "-frames:v", "1", "-vf", vf, tmp],
                       capture_output=True, text=True)
    if r.returncode != 0 or not os.path.getsize(tmp):
        os.unlink(tmp)
        die(f"動画から 1 コマを取り出せませんでした（{at} 秒）:\n{r.stderr.strip()}")
    img = Image.open(tmp).convert("RGB")
    img.load()
    os.unlink(tmp)
    return img


def make_background(src):
    """1080×1920 に合わせ、明度を落とす。"""
    if src.size != (W, H):
        # 比率を保って覆うように拡大し中央を切る
        sw, sh = src.size
        k = max(W / sw, H / sh)
        src = src.resize((round(sw * k), round(sh * k)), Image.LANCZOS)
        left, top = (src.width - W) // 2, (src.height - H) // 2
        src = src.crop((left, top, left + W, top + H))
    dark = ImageEnhance.Brightness(src.convert("RGB")).enhance(DARKEN)
    return dark.convert("RGBA")


# ---------- 文字 ----------
def text_size(font, text):
    l, t, r, b = font.getbbox(text)
    return r - l, b - t


def fit_font(font_path, text, max_width, size_max, size_min):
    size = size_max
    while size > size_min:
        f = ImageFont.truetype(font_path, size)
        if text_size(f, text)[0] <= max_width:
            return f
        size -= 2
    return ImageFont.truetype(font_path, size_min)


def draw_outlined(draw, xy, text, font, fill, outline_w):
    draw.text(xy, text, font=font, fill=fill, stroke_width=outline_w, stroke_fill=OUTLINE)


def draw_shadow_layer(base, items):
    """items = [(xy, text, font, outline_w)] を黒でずらして描き、ぼかして重ねる。"""
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for (x, y), text, font, ow in items:
        d.text((x + HEAD_SHADOW[0], y + HEAD_SHADOW[1]), text, font=font, fill=(0, 0, 0, 200),
               stroke_width=ow, stroke_fill=(0, 0, 0, 200))
    layer = layer.filter(ImageFilter.GaussianBlur(HEAD_SHADOW_BLUR))
    base.alpha_composite(layer)


def render(bg, day, line1, line2, font_path):
    img = bg.copy()
    draw = ImageDraw.Draw(img)

    # --- 上: Day バッジ ---
    if day:
        bf = ImageFont.truetype(font_path, BADGE_FONT_SIZE)
        label = f"Day {day}"
        tw, th = text_size(bf, label)
        bw, bh = tw + BADGE_PAD_X * 2, BADGE_FONT_SIZE + BADGE_PAD_Y * 2
        bx, by = (W - bw) // 2, BADGE_CENTER_Y - bh // 2
        draw.rounded_rectangle((bx, by, bx + bw, by + bh), radius=BADGE_RADIUS, fill=ACCENT)
        # 文字の縦位置は bbox の上端を差し引いて中央に
        l, t, r, b = bf.getbbox(label)
        draw.text((bx + BADGE_PAD_X - l, by + (bh - (b - t)) // 2 - t), label, font=bf, fill=WHITE)

    # --- 中央: 見出し 2 行 ---
    lines = [s for s in (line1, line2) if s]
    if not lines:
        lines = [MISSING_TITLE]
    # 2 行とも同じサイズにする（長い方に合わせる）
    longest = max(lines, key=lambda s: text_size(ImageFont.truetype(font_path, HEAD_FONT_MAX), s)[0])
    hf = fit_font(font_path, longest, HEAD_MAX_WIDTH, HEAD_FONT_MAX, HEAD_FONT_MIN)
    line_h = hf.size
    total_h = line_h * len(lines) + HEAD_LINE_GAP * (len(lines) - 1)
    y = HEAD_CENTER_Y - total_h // 2
    items = []
    for i, s in enumerate(lines):
        tw, _ = text_size(hf, s)
        l, t, r, b = hf.getbbox(s)
        x = (W - tw) // 2 - l
        items.append(((x, y - t + (line_h - (b - t)) // 2), s, hf, HEAD_OUTLINE_W, CYAN if (i == 1) else WHITE))
        y += line_h + HEAD_LINE_GAP
    draw_shadow_layer(img, [(xy, s, f, ow) for xy, s, f, ow, _ in items])
    draw = ImageDraw.Draw(img)
    for xy, s, f, ow, color in items:
        draw_outlined(draw, xy, s, f, color, ow)

    # --- 下: 小さく 2 行 ---
    ff = ImageFont.truetype(font_path, FOOT_FONT_SIZE)
    fh = FOOT_FONT_SIZE
    y = FOOT_BOTTOM_Y - (fh * len(FOOT_LINES) + FOOT_LINE_GAP * (len(FOOT_LINES) - 1))
    for s in FOOT_LINES:
        tw, _ = text_size(ff, s)
        l, t, r, b = ff.getbbox(s)
        draw_outlined(draw, ((W - tw) // 2 - l, y - t + (fh - (b - t)) // 2), s, ff, WHITE, FOOT_OUTLINE_W)
        y += fh + FOOT_LINE_GAP
    return img


def main():
    ap = argparse.ArgumentParser(description="リールのカバー画像を作る")
    ap.add_argument("--input", help="元の動画")
    ap.add_argument("--frame", help="背景の画像ファイル（--input の代わり）")
    ap.add_argument("--at", type=float, help="動画から取り出す時刻（秒）")
    ap.add_argument("--highlight", help="時刻を決めるための highlight.txt（最初の q の中間を使う）")
    ap.add_argument("--crop", default="center", choices=["left", "center", "right"])
    ap.add_argument("--cover-txt", help="見出しファイル（Day 番号・見出し 2 行）")
    ap.add_argument("--day")
    ap.add_argument("--line1")
    ap.add_argument("--line2")
    ap.add_argument("--font-bold", required=True)
    ap.add_argument("--out", required=True, help="出力 PNG（1080×1920）")
    ap.add_argument("--preview-out", help="中央 1080×1350 を切り抜いた確認用 PNG")
    a = ap.parse_args()

    if not a.input and not a.frame:
        die("--input か --frame のどちらかを指定してください")
    if not os.path.isfile(a.font_bold):
        die(f"フォントがありません: {a.font_bold}")

    day, l1, l2 = read_cover_txt(a.cover_txt)
    day = a.day or day
    l1 = a.line1 or l1
    l2 = a.line2 or l2
    if not l1 and not l2:
        print(f"  見出しが未設定です（{a.cover_txt or '--line1/--line2 なし'}）。「{MISSING_TITLE}」で作ります", file=sys.stderr)
    if not day:
        print("  Day 番号が未設定のためバッジは出しません", file=sys.stderr)

    if a.frame:
        src = Image.open(a.frame).convert("RGB")
    else:
        if not os.path.isfile(a.input):
            die(f"入力が見つかりません: {a.input}")
        at = a.at if a.at is not None else (first_q_mid(a.highlight) or 5.0)
        src = grab_frame(a.input, at, a.crop)
        print(f"  背景: {os.path.basename(a.input)} の {at} 秒")

    img = render(make_background(src), day, l1, l2, a.font_bold)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    img.convert("RGB").save(a.out, "PNG", optimize=True)
    print(f"  カバー: {a.out}")
    if a.preview_out:
        os.makedirs(os.path.dirname(os.path.abspath(a.preview_out)), exist_ok=True)
        img.crop((0, SAFE_TOP, W, SAFE_BOTTOM)).convert("RGB").save(a.preview_out, "PNG", optimize=True)
        print(f"  確認用（4:5）: {a.preview_out}")


if __name__ == "__main__":
    main()
