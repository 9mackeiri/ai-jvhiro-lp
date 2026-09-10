#!/usr/bin/env python3
"""SRT 字幕と冒頭見出しを、動画に重ねる透明 PNG の列にする（Pillow 使用）。

出力先フォルダに PNG を書き、ffmpeg の concat デマルチプレクサ用リスト
（list.txt）も書く。make.sh から呼ばれる。

  python3 render_overlays.py --srt 字幕.srt --duration 33.6 --out-dir 作業フォルダ \
      --font-bold NotoSansJP-Bold.ttf --title "見出し" [--title-sub "#ジャービス"] [--no-title]

SRT の各行の書き方:
  - 普通の行 …………… 白い字幕（ひろき）
  - 「J:」で始まる行 … 薄いシアンの字幕（ジャービス）。J: は表示されない
  - 空行で区切られた 1 つの字幕（キュー）に複数行あれば、そのまま複数行として出す
"""
import argparse
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920

# ===== 見た目の設定（ここを変えると字幕・見出しの見た目が変わる） =====
SUB_FONT_SIZE = 56           # 字幕の文字サイズ（px）
SUB_MAX_CHARS = 16           # 字幕 1 行の最大文字数（自動改行）
SUB_BOTTOM_RATIO = 0.20      # 字幕の帯の下端 = 画面の下から 20% の位置
SUB_COLOR_HIROKI = (255, 255, 255, 255)
SUB_COLOR_JARVIS = (190, 240, 255, 255)   # 薄いシアン
SUB_OUTLINE = (0, 0, 0, 255)
SUB_OUTLINE_W = 3
SUB_BOX_COLOR = (0, 0, 0, 140)            # 半透明の黒い帯
SUB_BOX_PAD_X, SUB_BOX_PAD_Y = 28, 18
SUB_BOX_RADIUS = 18
SUB_LINE_GAP = 10

TITLE_FONT_SIZE = 76
TITLE_MAX_CHARS = 10         # 見出し 1 行の最大文字数（「|」で手動改行もできる）
TITLE_CENTER_RATIO = 0.22    # 見出しの中心 = 画面の上から 22% の位置
TITLE_SECONDS = 2.0
TITLE_COLOR = (255, 255, 255, 255)
TITLE_OUTLINE_W = 6
TITLE_SUB_FONT_SIZE = 44
TITLE_SUB_COLOR = (190, 240, 255, 255)
TITLE_BOX_COLOR = (0, 0, 0, 120)
TITLE_BOX_PAD_X, TITLE_BOX_PAD_Y = 40, 26
TITLE_BOX_RADIUS = 24


def parse_srt(path):
    """SRT を [(start, end, [lines]), ...] にする。時刻は秒。"""
    text = open(path, encoding="utf-8-sig").read()
    cues = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [l.rstrip("\r") for l in block.splitlines() if l.strip() != ""]
        if not lines:
            continue
        if re.fullmatch(r"\d+", lines[0].strip()):
            lines = lines[1:]
        if not lines:
            continue
        m = re.match(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", lines[0])
        if not m:
            print(f"警告: 時刻行として読めないので飛ばします: {lines[0]!r}", file=sys.stderr)
            continue
        h1, m1, s1, ms1, h2, m2, s2, ms2 = (int(x) for x in m.groups())
        start = h1 * 3600 + m1 * 60 + s1 + ms1 / 1000
        end = h2 * 3600 + m2 * 60 + s2 + ms2 / 1000
        body = [l.strip() for l in lines[1:] if l.strip()]
        if body and end > start:
            cues.append((start, end, body))
    cues.sort(key=lambda c: c[0])
    # 重なりは前のキューを詰めて解消
    for i in range(len(cues) - 1):
        s, e, b = cues[i]
        if e > cues[i + 1][0]:
            cues[i] = (s, cues[i + 1][0], b)
    return cues


def wrap_jp(text, max_chars):
    """日本語向けの簡易改行。max_chars ごとに切るが、直前の句読点の後で切れるならそこで切る。"""
    text = text.replace("|", "\n")
    out = []
    for para in text.split("\n"):
        para = para.strip()
        while len(para) > max_chars:
            cut = max_chars
            for k in range(max_chars, max(max_chars - 5, 1), -1):
                if para[k - 1] in "、。！？!?」）)":
                    cut = k
                    break
            # 禁則処理: 次の行が句読点・閉じ括弧で始まらないよう、その分は前の行に含める
            while cut < len(para) and para[cut] in "、。！？!?」）)、":
                cut += 1
            out.append(para[:cut])
            para = para[cut:].lstrip()
        if para:
            out.append(para)
    return out


def speaker_and_lines(body):
    """先頭の J: を見てジャービスかどうかを判定し、表示行を返す。"""
    first = body[0]
    is_jarvis = bool(re.match(r"^\s*[JjＪｊ][:：]", first))
    body = [re.sub(r"^\s*[JjＪｊ][:：]\s*", "", first)] + list(body[1:])
    lines = []
    for l in body:  # SRT の 1 行を 1 段落として扱う（空白では分けない）
        lines.extend(wrap_jp(l, SUB_MAX_CHARS))
    return is_jarvis, [l for l in lines if l]


def rounded_box(draw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def draw_subtitle(img, lines, is_jarvis, font):
    draw = ImageDraw.Draw(img)
    widths, heights = [], []
    for l in lines:
        bb = draw.textbbox((0, 0), l, font=font, stroke_width=SUB_OUTLINE_W)
        widths.append(bb[2] - bb[0])
        heights.append(bb[3] - bb[1])
    line_h = max(heights) if heights else SUB_FONT_SIZE
    total_h = line_h * len(lines) + SUB_LINE_GAP * (len(lines) - 1)
    box_w = max(widths) + SUB_BOX_PAD_X * 2
    box_h = total_h + SUB_BOX_PAD_Y * 2
    bottom = int(H * (1 - SUB_BOTTOM_RATIO))
    x0 = (W - box_w) // 2
    y0 = bottom - box_h
    rounded_box(draw, (x0, y0, x0 + box_w, bottom), SUB_BOX_RADIUS, SUB_BOX_COLOR)
    color = SUB_COLOR_JARVIS if is_jarvis else SUB_COLOR_HIROKI
    y = y0 + SUB_BOX_PAD_Y
    for l, w in zip(lines, widths):
        draw.text(((W - w) // 2, y), l, font=font, fill=color,
                  stroke_width=SUB_OUTLINE_W, stroke_fill=SUB_OUTLINE, anchor="la")
        y += line_h + SUB_LINE_GAP


def draw_title(img, title, sub, font, sub_font):
    draw = ImageDraw.Draw(img)
    lines = wrap_jp(title, TITLE_MAX_CHARS)
    sizes = [draw.textbbox((0, 0), l, font=font, stroke_width=TITLE_OUTLINE_W) for l in lines]
    line_h = max(b[3] - b[1] for b in sizes)
    gap = 12
    block_h = line_h * len(lines) + gap * (len(lines) - 1)
    sub_bb = draw.textbbox((0, 0), sub, font=sub_font, stroke_width=3) if sub else (0, 0, 0, 0)
    sub_h = (sub_bb[3] - sub_bb[1]) if sub else 0
    total_h = block_h + (gap + 8 + sub_h if sub else 0)
    box_w = max(max(b[2] - b[0] for b in sizes), sub_bb[2] - sub_bb[0]) + TITLE_BOX_PAD_X * 2
    box_h = total_h + TITLE_BOX_PAD_Y * 2
    cy = int(H * TITLE_CENTER_RATIO)
    x0, y0 = (W - box_w) // 2, cy - box_h // 2
    rounded_box(draw, (x0, y0, x0 + box_w, y0 + box_h), TITLE_BOX_RADIUS, TITLE_BOX_COLOR)
    y = y0 + TITLE_BOX_PAD_Y
    for l, b in zip(lines, sizes):
        w = b[2] - b[0]
        draw.text(((W - w) // 2, y), l, font=font, fill=TITLE_COLOR,
                  stroke_width=TITLE_OUTLINE_W, stroke_fill=SUB_OUTLINE, anchor="la")
        y += line_h + gap
    if sub:
        w = sub_bb[2] - sub_bb[0]
        draw.text(((W - w) // 2, y + 8), sub, font=sub_font, fill=TITLE_SUB_COLOR,
                  stroke_width=3, stroke_fill=SUB_OUTLINE, anchor="la")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--srt", required=True)
    ap.add_argument("--duration", type=float, required=True, help="動画の長さ（秒）")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--font-bold", required=True)
    ap.add_argument("--title", default="")
    ap.add_argument("--title-sub", default="#ジャービス")
    ap.add_argument("--no-title", action="store_true")
    a = ap.parse_args()

    os.makedirs(a.out_dir, exist_ok=True)
    font = ImageFont.truetype(a.font_bold, SUB_FONT_SIZE)
    tfont = ImageFont.truetype(a.font_bold, TITLE_FONT_SIZE)
    sfont = ImageFont.truetype(a.font_bold, TITLE_SUB_FONT_SIZE)
    cues = parse_srt(a.srt) if os.path.exists(a.srt) else []
    show_title = bool(a.title) and not a.no_title
    title_end = min(TITLE_SECONDS, a.duration) if show_title else 0.0

    # 状態が変わる時刻を集める
    marks = {0.0, a.duration}
    if show_title:
        marks.add(title_end)
    for s, e, _ in cues:
        marks.add(min(s, a.duration))
        marks.add(min(e, a.duration))
    marks = sorted(m for m in marks if 0.0 <= m <= a.duration)

    cache = {}
    entries = []
    for t0, t1 in zip(marks, marks[1:]):
        if t1 - t0 < 0.001:
            continue
        mid = (t0 + t1) / 2
        cue = next(((s, e, b) for s, e, b in cues if s <= mid < e), None)
        has_title = show_title and mid < title_end
        key = (has_title, tuple(cue[2]) if cue else None)
        if key not in cache:
            img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            if has_title:
                draw_title(img, a.title, a.title_sub, tfont, sfont)
            if cue:
                is_j, lines = speaker_and_lines(cue[2])
                if lines:
                    draw_subtitle(img, lines, is_j, font)
            name = f"ov_{len(cache):04d}.png"
            img.save(os.path.join(a.out_dir, name), optimize=True)
            cache[key] = name
        entries.append((cache[key], t1 - t0))

    with open(os.path.join(a.out_dir, "list.txt"), "w", encoding="utf-8") as f:
        f.write("ffconcat version 1.0\n")
        for name, d in entries:
            f.write(f"file '{name}'\nduration {d:.3f}\n")
        if entries:  # concat の仕様で最後のファイルをもう一度書くと最後の duration が効く
            f.write(f"file '{entries[-1][0]}'\n")
    print(f"字幕キュー {len(cues)} 件、画像 {len(cache)} 枚、区間 {len(entries)} 個")


if __name__ == "__main__":
    main()
