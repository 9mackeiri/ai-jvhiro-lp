#!/usr/bin/env python3
"""字幕（SRT）または要点テロップ（highlight.txt）と冒頭見出しを、動画に重ねる透明 PNG の列にする。

出力先フォルダに PNG を書き、ffmpeg の concat デマルチプレクサ用リスト（list.txt）も書く。
make.sh から呼ばれる。

  全文モード:  python3 render_overlays.py --srt 字幕.srt --duration 33.6 --out-dir 作業 --font-bold Bold.ttf --title "見出し"
  要点モード:  python3 render_overlays.py --highlight 名前.highlight.txt --duration 33.6 --out-dir 作業 --font-bold Bold.ttf --title "見出し"

SRT（全文モード）の書き方:
  - 普通の行 …………… 白い字幕（ひろき）
  - 「J:」で始まる行 … 薄いシアンの字幕（ジャービス）。J: は表示されない

highlight.txt（要点モード）の書き方: 1 行 1 テロップ、「開始秒-終了秒 | 種類 | 文字」。# で始まる行は無視
  q … 質問。白・大きめ・黒縁。画面中央やや上
  a … 答えの要点。薄いシアン。画面下の帯
  n … 数字の強調。白・特大・黒縁。画面中央やや下
  例:
    0.0-4.5 | q | 今日の売上は？
    9.8-18.4 | n | 149,947円
    9.8-18.4 | a | 乳酸菌サプリ24個・病院から1件
"""
import argparse
import math
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920

# ===== 見た目の設定（ここを変えると字幕・テロップの見た目が変わる） =====
# --- 全文モードの字幕（画面下の帯） ---
SUB_FONT_SIZE = 56
TEXT_MAX_WIDTH = 960         # 文字の最大幅（px）。これを超えると自動改行（帯の余白込みで画面幅 1080 に収まる）
SUB_BOTTOM_RATIO = 0.20      # 帯の下端 = 画面の下から 20% の位置
SUB_COLOR_HIROKI = (255, 255, 255, 255)
SUB_COLOR_JARVIS = (190, 240, 255, 255)   # 薄いシアン
OUTLINE = (0, 0, 0, 255)
SUB_OUTLINE_W = 3
BOX_COLOR = (0, 0, 0, 140)                # 半透明の黒い帯
BOX_PAD_X, BOX_PAD_Y = 28, 18
BOX_RADIUS = 18
LINE_GAP = 10

# --- 要点モード ---
Q_FONT_SIZE = 64             # q: 質問（白・黒縁・帯なし・画面中央やや上）
Q_CENTER_RATIO = 0.42
Q_OUTLINE_W = 6
A_FONT_SIZE = 64             # a: 答えの要点（薄いシアン・画面下の帯）
A_OUTLINE_W = 4
N_FONT_SIZE = 120            # n: 数字の強調（白・特大・黒縁・帯なし・画面中央やや下）
N_CENTER_RATIO = 0.60
N_OUTLINE_W = 10

# --- 冒頭の見出し ---
TITLE_FONT_SIZE = 76
TITLE_MAX_WIDTH = 900        # 見出しの最大幅（px）。「|」で手動改行もできる
TITLE_CENTER_RATIO = 0.22
TITLE_SECONDS = 2.0          # 見出しを出す秒数の既定（--title-seconds で変更可）。この間 q は出さない
TITLE_OUTLINE_W = 6
TITLE_SUB_FONT_SIZE = 44
TITLE_SUB_COLOR = (190, 240, 255, 255)
TITLE_BOX_COLOR = (0, 0, 0, 120)
TITLE_BOX_PAD_X, TITLE_BOX_PAD_Y = 40, 26
TITLE_BOX_RADIUS = 24

WHITE = (255, 255, 255, 255)
CYAN = (190, 240, 255, 255)


# ---------- 入力の読み込み ----------
def parse_srt(path):
    """SRT を [(start, end, kind, text)] にする。kind は sub_h（ひろき）/ sub_j（ジャービス）。"""
    text = open(path, encoding="utf-8-sig").read()
    events = []
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
        if not body or end <= start:
            continue
        is_j = bool(re.match(r"^\s*[JjＪｊ][:：]", body[0]))
        body[0] = re.sub(r"^\s*[JjＪｊ][:：]\s*", "", body[0])
        events.append((start, end, "sub_j" if is_j else "sub_h", "\n".join(b for b in body if b)))
    events.sort(key=lambda e: e[0])
    for i in range(len(events) - 1):  # 字幕どうしの重なりは前を詰める
        s, e, k, t = events[i]
        if e > events[i + 1][0]:
            events[i] = (s, events[i + 1][0], k, t)
    return events


def parse_highlight(path):
    """highlight.txt を [(start, end, kind, text)] にする。kind は q / a / n。"""
    events = []
    for ln, raw in enumerate(open(path, encoding="utf-8-sig"), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != 3:
            print(f"警告 {ln} 行目: 「開始-終了 | 種類 | 文字」の形ではないので飛ばします: {line!r}", file=sys.stderr)
            continue
        m = re.fullmatch(r"([\d.]+)\s*-\s*([\d.]+)", parts[0])
        if not m:
            print(f"警告 {ln} 行目: 時刻が読めません: {parts[0]!r}", file=sys.stderr)
            continue
        try:
            start, end = float(m.group(1)), float(m.group(2))
        except ValueError:
            print(f"警告 {ln} 行目: 時刻が数値として読めません: {parts[0]!r}", file=sys.stderr)
            continue
        kind = parts[1].lower()
        if kind not in ("q", "a", "n"):
            print(f"警告 {ln} 行目: 種類は q / a / n のどれか: {parts[1]!r}", file=sys.stderr)
            continue
        if end <= start or not parts[2]:
            print(f"警告 {ln} 行目: 時刻の順序か文字が不正です: {line!r}", file=sys.stderr)
            continue
        events.append((start, end, kind, parts[2]))
    events.sort(key=lambda e: e[0])
    return events


# ---------- 文字の折り返し ----------
KINSOKU_TAIL = "、。！？!?」）)"          # 行頭に来てはいけない文字
BREAK_AFTER = "、。！？!?」）)・／/ "      # ここの直後なら折り返してよい（読点・中黒・スペース）
NUM_UNIT_RE = re.compile(r"[+\-−＋]?[\d,\.]+\s*(?:%|％|円|個|件|万円|倍|人|日|か月|ヶ月|分|秒|時間|回|kg|g|ml|L)?")


def _protected_spans(text):
    """途中で折ってはいけない範囲（数字＋単位）を [(start, end)] で返す。"""
    return [(m.start(), m.end()) for m in NUM_UNIT_RE.finditer(text) if re.search(r"\d", m.group(0))]


def _inside_protected(pos, spans):
    return any(a < pos < b for a, b in spans)


def wrap_px(text, font, max_width):
    """描画幅（px）で折り返す。
    優先順位: (1) 読点・中黒・スペースの直後 → (2) 数字＋単位の途中でない位置。行頭に句読点は置かない。「|」は手動改行。"""
    text = text.replace("|", "\n")
    out = []
    for para in text.split("\n"):
        para = para.strip()
        while para and font.getlength(para) > max_width:
            spans = _protected_spans(para)
            # max_width に収まる最大の文字数
            fit = 1
            while fit < len(para) and font.getlength(para[:fit + 1]) <= max_width:
                fit += 1
            # (1) 収まる範囲で最も後ろにある「折ってよい文字」の直後
            cut = 0
            for k in range(fit, 0, -1):
                if para[k - 1] in BREAK_AFTER and not _inside_protected(k, spans):
                    cut = k
                    break
            # (2) 無ければ、数字＋単位を割らない最も後ろの位置
            if cut == 0:
                cut = fit
                while cut > 1 and _inside_protected(cut, spans):
                    cut -= 1
            while cut < len(para) and para[cut] in KINSOKU_TAIL:  # 行頭の句読点を避ける
                cut += 1
            out.append(para[:cut].rstrip())
            para = para[cut:].lstrip()
        if para:
            out.append(para)
    return out


# ---------- 描画 ----------
def measure(draw, lines, font, outline_w):
    sizes = [draw.textbbox((0, 0), l, font=font, stroke_width=outline_w) for l in lines]
    widths = [b[2] - b[0] for b in sizes]
    line_h = max(b[3] - b[1] for b in sizes)
    return widths, line_h


def draw_lines(draw, lines, font, color, outline_w, top_y, line_h, widths):
    y = top_y
    for l, w in zip(lines, widths):
        draw.text(((W - w) // 2, y), l, font=font, fill=color, stroke_width=outline_w, stroke_fill=OUTLINE, anchor="la")
        y += line_h + LINE_GAP


def draw_banded_bottom(img, text, font, color, outline_w):
    """画面下の帯付きテキスト（全文字幕と a で共用）。帯の上端 y を返す。"""
    lines = wrap_px(text, font, TEXT_MAX_WIDTH)
    if not lines:
        return H
    draw = ImageDraw.Draw(img)
    widths, line_h = measure(draw, lines, font, outline_w)
    total_h = line_h * len(lines) + LINE_GAP * (len(lines) - 1)
    box_w, box_h = max(widths) + BOX_PAD_X * 2, total_h + BOX_PAD_Y * 2
    bottom = int(H * (1 - SUB_BOTTOM_RATIO))
    x0, y0 = (W - box_w) // 2, bottom - box_h
    draw.rounded_rectangle((x0, y0, x0 + box_w, bottom), radius=BOX_RADIUS, fill=BOX_COLOR)
    draw_lines(draw, lines, font, color, outline_w, y0 + BOX_PAD_Y, line_h, widths)
    return y0


def draw_centered(img, text, font, color, outline_w, center_ratio, max_bottom=None):
    """帯なし・黒縁のテキストを、指定の高さを中心に置く（q と n で共用）。max_bottom より下にはみ出すなら上へずらす。"""
    lines = wrap_px(text, font, TEXT_MAX_WIDTH)
    if not lines:
        return
    draw = ImageDraw.Draw(img)
    widths, line_h = measure(draw, lines, font, outline_w)
    total_h = line_h * len(lines) + LINE_GAP * (len(lines) - 1)
    top = int(H * center_ratio) - total_h // 2
    if max_bottom is not None and top + total_h > max_bottom:
        top = max(0, max_bottom - total_h)
    draw_lines(draw, lines, font, color, outline_w, top, line_h, widths)


def draw_title(img, title, sub, font, sub_font):
    draw = ImageDraw.Draw(img)
    lines = wrap_px(title, font, TITLE_MAX_WIDTH)
    widths, line_h = measure(draw, lines, font, TITLE_OUTLINE_W)
    gap = 12
    block_h = line_h * len(lines) + gap * (len(lines) - 1)
    sub_bb = draw.textbbox((0, 0), sub, font=sub_font, stroke_width=3) if sub else (0, 0, 0, 0)
    sub_h = (sub_bb[3] - sub_bb[1]) if sub else 0
    total_h = block_h + (gap + 8 + sub_h if sub else 0)
    box_w = max(max(widths), sub_bb[2] - sub_bb[0]) + TITLE_BOX_PAD_X * 2
    box_h = total_h + TITLE_BOX_PAD_Y * 2
    cy = int(H * TITLE_CENTER_RATIO)
    x0, y0 = (W - box_w) // 2, cy - box_h // 2
    draw.rounded_rectangle((x0, y0, x0 + box_w, y0 + box_h), radius=TITLE_BOX_RADIUS, fill=TITLE_BOX_COLOR)
    y = y0 + TITLE_BOX_PAD_Y
    for l, w in zip(lines, widths):
        draw.text(((W - w) // 2, y), l, font=font, fill=WHITE, stroke_width=TITLE_OUTLINE_W, stroke_fill=OUTLINE, anchor="la")
        y += line_h + gap
    if sub:
        w = sub_bb[2] - sub_bb[0]
        draw.text(((W - w) // 2, y + 8), sub, font=sub_font, fill=TITLE_SUB_COLOR, stroke_width=3, stroke_fill=OUTLINE, anchor="la")


def visible_events(active):
    """同時に出ているイベントのうち実際に描くもの（種類ごとに先に始まった 1 つ）。"""
    seen, out = set(), []
    for ev in active:
        if ev[2] not in seen:
            seen.add(ev[2])
            out.append(ev)
    return out


def render_events(img, active, fonts):
    """同時に出ているイベントを描く。帯（字幕・a）を先に描き、n はその帯と重ならない位置に置く。"""
    by_kind = {k: t for _s, _e, k, t in visible_events(active)}
    band_top = H
    if "sub_h" in by_kind:
        band_top = draw_banded_bottom(img, by_kind["sub_h"], fonts["sub"], SUB_COLOR_HIROKI, SUB_OUTLINE_W)
    if "sub_j" in by_kind:
        band_top = draw_banded_bottom(img, by_kind["sub_j"], fonts["sub"], SUB_COLOR_JARVIS, SUB_OUTLINE_W)
    if "a" in by_kind:
        band_top = draw_banded_bottom(img, by_kind["a"], fonts["a"], CYAN, A_OUTLINE_W)
    if "q" in by_kind:
        draw_centered(img, by_kind["q"], fonts["q"], WHITE, Q_OUTLINE_W, Q_CENTER_RATIO)
    if "n" in by_kind:
        draw_centered(img, by_kind["n"], fonts["n"], WHITE, N_OUTLINE_W, N_CENTER_RATIO, max_bottom=band_top - 24)


def main():
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--srt", help="全文モード: SRT 字幕")
    src.add_argument("--highlight", help="要点モード: highlight.txt")
    ap.add_argument("--duration", type=float, required=True, help="動画の長さ（秒）")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--font-bold", required=True)
    ap.add_argument("--title", default="")
    ap.add_argument("--title-sub", default="#ジャービス")
    ap.add_argument("--no-title", action="store_true")
    ap.add_argument("--title-seconds", type=float, default=TITLE_SECONDS, help="見出しを出す秒数（既定 2）")
    a = ap.parse_args()

    os.makedirs(a.out_dir, exist_ok=True)
    fonts = {
        "sub": ImageFont.truetype(a.font_bold, SUB_FONT_SIZE),
        "q": ImageFont.truetype(a.font_bold, Q_FONT_SIZE),
        "a": ImageFont.truetype(a.font_bold, A_FONT_SIZE),
        "n": ImageFont.truetype(a.font_bold, N_FONT_SIZE),
    }
    tfont = ImageFont.truetype(a.font_bold, TITLE_FONT_SIZE)
    sfont = ImageFont.truetype(a.font_bold, TITLE_SUB_FONT_SIZE)

    if a.srt:
        events = parse_srt(a.srt) if os.path.exists(a.srt) else []
    else:
        events = parse_highlight(a.highlight)
    events = [(s, min(e, a.duration), k, t) for s, e, k, t in events if s < a.duration]

    show_title = bool(a.title) and not a.no_title
    if not math.isfinite(a.title_seconds) or a.title_seconds < 0:
        sys.exit("--title-seconds は 0 以上の秒数を指定してください")
    title_end = min(a.title_seconds, a.duration) if show_title else 0.0
    # 見出しが出ている間は q（質問）を出さない。開始を見出しの終了直後に遅らせる（終了時刻はそのまま）
    events = [(max(s, title_end) if k == "q" else s, e, k, t) for s, e, k, t in events]
    events = [ev for ev in events if ev[1] > ev[0]]

    marks = {0.0, a.duration}
    if show_title:
        marks.add(title_end)
    for s, e, _k, _t in events:
        marks.add(s)
        marks.add(e)
    marks = sorted(m for m in marks if 0.0 <= m <= a.duration)

    cache, entries = {}, []
    for t0, t1 in zip(marks, marks[1:]):
        if t1 - t0 < 0.001:
            continue
        mid = (t0 + t1) / 2
        active = [ev for ev in events if ev[0] <= mid < ev[1]]
        has_title = show_title and mid < title_end
        key = (has_title, tuple((k, t) for _s, _e, k, t in visible_events(active)))
        if key not in cache:
            img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            if has_title:
                draw_title(img, a.title, a.title_sub, tfont, sfont)
            render_events(img, active, fonts)
            name = f"ov_{len(cache):04d}.png"
            img.save(os.path.join(a.out_dir, name), optimize=True)
            cache[key] = name
        entries.append((cache[key], t1 - t0))

    with open(os.path.join(a.out_dir, "list.txt"), "w", encoding="utf-8") as f:
        f.write("ffconcat version 1.0\n")
        for name, d in entries:
            f.write(f"file '{name}'\nduration {d:.3f}\n")
        if entries:
            f.write(f"file '{entries[-1][0]}'\n")
    print(f"テロップ {len(events)} 件、画像 {len(cache)} 枚、区間 {len(entries)} 個")


if __name__ == "__main__":
    main()
