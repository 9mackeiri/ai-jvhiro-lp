#!/usr/bin/env python3
"""リールのカバー画像（Instagram のプロフィール一覧に出るサムネイル）を 1 枚作る。

  python3 video/make_cover.py --input 入力.MOV --cover-txt 名前.cover.txt --font-bold Bold.ttf --out 名前_cover.png
  python3 video/make_cover.py --input 入力.MOV --day 4 --line1 "100万超えの朝" --line2 "大口が1件入った日" ...

  --input       元の動画（動画から 1 コマを取り出して背景にする。make.sh と同じ 9:16 の切り出し）
  --frame       代わりに背景の画像ファイルを直接指定する（--input の代わり）
  --at 秒       取り出す時刻。省略時は --highlight の最初の q（質問）の中間、それも無ければ 5 秒
  --crop        横動画のとき 9:16 に切る位置（left / center / right。既定 center）
  --cover-txt   見出しファイル。1 行目が Day 番号（「4」でも「Day 4」でも可）、2〜3 行目が見出し。「y: 0.9」の行で見出し位置。# で始まる行は無視
  --day/--line1/--line2   ファイルの代わりに直接指定（両方あれば直接指定が優先）
  --title-y 0.9  見出し 2 行の下端の位置（4:5 範囲の割合。モニターに重なる回だけ下げる。cover.txt に「y: 0.9」と書いても同じ）
  --badge / --badge-text / --accent   バッジの色・バッジ文字の色（省略時は自動）・見出し 2 行目の色（例: --badge "#FFD400" --accent "#FFD400"）
  --preview-out 一覧で見える範囲（中央 1080×1350）だけを切り抜いた確認用 PNG の出力先

できあがり: 1080×1920 の PNG。文字はすべて中央の 1080×1350（4:5）の範囲に収める（一覧ではそこだけが見える）
  上: 「Day N」の大きなバッジ（LP の差し色の丸角・白文字。一覧のサムネ（幅 360px 相当）でも読める大きさ）
  中央やや下: 見出し 2 行（太字・白と薄いシアン・太い黒縁＋影）
  ※ 一覧では文字が 1/3 に縮むため、小さな文字（下段の説明）は置かない
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
BADGE_COLOR = (255, 212, 0, 255)    # バッジの色（#FFD400 黄。木田決定 2026-09-17）
WHITE = (255, 255, 255, 255)
ACCENT = (255, 212, 0, 255)         # 見出し 2 行目の色（#FFD400 黄。1 行目は白）
OUTLINE = (0, 0, 0, 255)

# 一覧（3 列）のサムネは幅 360px ほど＝この画像の 1/3。そこで読める大きさにしてある
BADGE_FONT_SIZE = 130               # 「Day N」の文字サイズ（一覧では約 43px）
BADGE_PAD_X, BADGE_PAD_Y = 44, 18
BADGE_RADIUS = 34
BADGE_TOP_RATIO = 0.09              # バッジの上端 = 4:5 範囲の上端から高さの 9%（= SAFE_TOP + 122）
BADGE_TOP_Y = SAFE_TOP + round(SAFE_H * BADGE_TOP_RATIO)

HEAD_FONT_MAX = 146                 # 見出しの最大サイズ。幅に収まるまで小さくする
HEAD_FONT_MIN = 60                  # ここまで縮めても収まらなければ、この大きさで描く（13 文字なら 72px 前後になる）
HEAD_MAX_WIDTH = 1000
HEAD_BOTTOM_RATIO = 0.85            # 見出し 2 行の下端 = 4:5 範囲の上端から高さの 85%（下端から余白 15%。モニターの下あたり）
                                    # --title-y や cover.txt の「y: 0.9」で回ごとに変えられる（1.0 = 4:5 範囲の下端）
HEAD_LINE_GAP = 30
HEAD_OUTLINE_W = 12                 # 縁取りは太めにして背景に負けないようにする
HEAD_SHADOW = (10, 10)              # 影のずれ（px）
HEAD_SHADOW_BLUR = 14

MISSING_TITLE = "見出し未設定"


def parse_color(text, name):
    """'#RRGGBB' / 'RRGGBB' / 'white' などを (r, g, b, 255) にする。"""
    from PIL import ImageColor
    try:
        r, g, b = ImageColor.getrgb(text)[:3]
    except ValueError:
        die(f"{name} の色が読めません: {text}（例: #FFD400）")
    return (r, g, b, 255)


def auto_text_color(bg):
    """背景色の明るさから、文字を黒にするか白にするか決める（明るい背景なら黒）。"""
    r, g, b = bg[:3]
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    return (0, 0, 0, 255) if lum > 160 else WHITE


def die(msg):
    print(msg, file=sys.stderr)
    sys.exit(1)


# ---------- 見出しファイル ----------
def read_cover_txt(path):
    """1 行目 Day 番号、2〜3 行目 見出し。「y: 0.9」の行があれば見出しの下端位置。# 行は無視。返り値 (day, l1, l2, title_y)。"""
    if not path or not os.path.isfile(path):
        return None, None, None, None
    lines = []
    with open(path, encoding="utf-8") as f:
        for raw in f:
            s = raw.strip()
            if s and not s.startswith("#"):
                lines.append(s)
    title_y = None
    rest = []
    for s in lines:
        m = re.fullmatch(r"y\s*[:：]\s*([\d.]+)", s, re.IGNORECASE)
        if m:
            try:
                title_y = float(m.group(1))
            except ValueError:
                die(f"{path} の位置指定が読めません: {s}（例: y: 0.9）")
        else:
            rest.append(s)
    lines = rest
    if not lines:
        return None, None, None, title_y
    m = re.fullmatch(r"(?:Day\s*)?(\d+)", lines[0], re.IGNORECASE)
    if m:
        day, heads = m.group(1), lines[1:]
    else:
        day, heads = None, lines          # 1 行目が Day 番号でなければ全部を見出しとして扱う
    l1 = heads[0] if len(heads) > 0 else None
    l2 = heads[1] if len(heads) > 1 else None
    return day, l1, l2, title_y


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


def fit_font(font_path, text, max_width, size_max, size_min, outline_w=0):
    """幅（縁取り込み）が max_width に収まる最大のサイズを返す。size_min まで下げても収まらなければ size_min。"""
    size = size_max
    while size > size_min:
        f = ImageFont.truetype(font_path, size)
        if text_size(f, text)[0] + outline_w * 2 <= max_width:
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


def render(bg, day, line1, line2, font_path, badge=BADGE_COLOR, badge_text=None, accent=ACCENT, title_y=HEAD_BOTTOM_RATIO):
    """badge=バッジの色、badge_text=バッジ文字の色（None なら明るさで自動）、accent=見出し 2 行目の色、title_y=見出しの下端（4:5 範囲の割合）"""
    img = bg.copy()
    draw = ImageDraw.Draw(img)

    # --- 上: Day バッジ ---
    if day:
        bf = ImageFont.truetype(font_path, BADGE_FONT_SIZE)
        label = f"Day {day}"
        tw, th = text_size(bf, label)
        bw, bh = tw + BADGE_PAD_X * 2, BADGE_FONT_SIZE + BADGE_PAD_Y * 2
        bx, by = (W - bw) // 2, BADGE_TOP_Y
        draw.rounded_rectangle((bx, by, bx + bw, by + bh), radius=BADGE_RADIUS, fill=badge)
        # 文字の縦位置は bbox の上端を差し引いて中央に
        l, t, r, b = bf.getbbox(label)
        draw.text((bx + BADGE_PAD_X - l, by + (bh - (b - t)) // 2 - t), label, font=bf, fill=badge_text or auto_text_color(badge))

    # --- 中央: 見出し 2 行 ---
    lines = [s for s in (line1, line2) if s]
    if not lines:
        lines = [MISSING_TITLE]
    # 2 行とも同じサイズにする（長い方に合わせる）
    longest = max(lines, key=lambda s: text_size(ImageFont.truetype(font_path, HEAD_FONT_MAX), s)[0])
    hf = fit_font(font_path, longest, HEAD_MAX_WIDTH, HEAD_FONT_MAX, HEAD_FONT_MIN, HEAD_OUTLINE_W)
    line_h = hf.size
    total_h = line_h * len(lines) + HEAD_LINE_GAP * (len(lines) - 1)
    y = SAFE_TOP + round(SAFE_H * title_y) - total_h   # 下端を合わせる
    items = []
    for i, s in enumerate(lines):
        tw, _ = text_size(hf, s)
        l, t, r, b = hf.getbbox(s)
        x = (W - tw) // 2 - l
        items.append(((x, y - t + (line_h - (b - t)) // 2), s, hf, HEAD_OUTLINE_W, accent if (i == 1) else WHITE))
        y += line_h + HEAD_LINE_GAP
    draw_shadow_layer(img, [(xy, s, f, ow) for xy, s, f, ow, _ in items])
    draw = ImageDraw.Draw(img)
    for xy, s, f, ow, color in items:
        draw_outlined(draw, xy, s, f, color, ow)
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
    ap.add_argument("--title-y", type=float, help=f"見出し 2 行の下端の位置（4:5 範囲の上端 0 〜 下端 1.0 の割合。既定 {HEAD_BOTTOM_RATIO}。cover.txt の「y: 0.9」でも指定可。引数が優先）")
    ap.add_argument("--badge", default="#FFD400", help="Day バッジの色（既定 #FFD400 黄）")
    ap.add_argument("--badge-text", help="バッジ文字の色（省略時はバッジが明るければ黒、暗ければ白）")
    ap.add_argument("--accent", default="#FFD400", help="見出し 2 行目の色（既定 #FFD400 黄。1 行目は常に白）")
    a = ap.parse_args()

    if not a.input and not a.frame:
        die("--input か --frame のどちらかを指定してください")
    if not os.path.isfile(a.font_bold):
        die(f"フォントがありません: {a.font_bold}")

    day, l1, l2, txt_y = read_cover_txt(a.cover_txt)
    title_y = a.title_y if a.title_y is not None else (txt_y if txt_y is not None else HEAD_BOTTOM_RATIO)
    if not (0.3 <= title_y <= 1.0):
        die(f"--title-y は 0.3〜1.0 の割合で指定してください: {title_y}")
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

    img = render(make_background(src), day, l1, l2, a.font_bold,
                 badge=parse_color(a.badge, "--badge"),
                 badge_text=parse_color(a.badge_text, "--badge-text") if a.badge_text else None,
                 accent=parse_color(a.accent, "--accent"), title_y=title_y)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    img.convert("RGB").save(a.out, "PNG", optimize=True)
    print(f"  カバー: {a.out}")
    if a.preview_out:
        os.makedirs(os.path.dirname(os.path.abspath(a.preview_out)), exist_ok=True)
        img.crop((0, SAFE_TOP, W, SAFE_BOTTOM)).convert("RGB").save(a.preview_out, "PNG", optimize=True)
        print(f"  確認用（4:5）: {a.preview_out}")


if __name__ == "__main__":
    main()
