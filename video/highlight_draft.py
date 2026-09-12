#!/usr/bin/env python3
"""SRT 字幕から、要点テロップ（highlight.txt）の下書きを作る。

  python3 highlight_draft.py 入力.srt 出力.highlight.txt [--force] [--media 動画または音声] [--model モデル]
  出力先が既にあるときは --force を付けない限り上書きしない
  --media を渡すと、q 行の開始時刻を「文言の最初の語の言い始め」に自動で合わせる（q_align.py）

振り分けのルール（機械的な下書きなので、木田が文を短く直す前提）:
  - 「？」「教えて」「ですか」を含む字幕 → q（質問）
  - それ以外 → a（答えの要点）
  - 数字（円・個・件・% など）を含む字幕 → その数字だけの n 行も同じ時刻で追加
  - 「かしこまりました」「ありがとう」だけの短い相づちは出さない（コメントとして残す）
"""
import os
import re
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from render_overlays import parse_srt  # noqa: E402
import q_align  # noqa: E402

NUM_RE = re.compile(r"[+\-]?\d[\d,]*(?:\.\d+)?\s*(?:円|個|件|%|％|万円|倍|人|日|か月|ヶ月|分|時間)?")
SKIP_RE = re.compile(r"^(かしこまりました|ありがとう(ございます)?|こちらこそ|はい|了解(しました)?)[、。！!]*$")


def main():
    argv = sys.argv[1:]
    force = "--force" in argv
    media = model = None
    for i, a in enumerate(argv):
        if a == "--media" and i + 1 < len(argv):
            media = argv[i + 1]
        if a == "--model" and i + 1 < len(argv):
            model = argv[i + 1]
    skip = set()
    for i, a in enumerate(argv):
        if a in ("--media", "--model"):
            skip.update({i, i + 1})
    args = [a for i, a in enumerate(argv) if i not in skip and a != "--force"]
    if len(args) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    src, dst = args
    if not os.path.exists(src):
        print(f"字幕（SRT）がありません: {src}\n文字起こしを先に行ってください（--skip-transcribe を外して実行）", file=sys.stderr)
        return 1
    if os.path.exists(dst) and not force:
        print(f"既にあるので上書きしません: {dst}（上書きするなら --force）", file=sys.stderr)
        return 1
    events = parse_srt(src)
    out = [
        "# 要点テロップの下書き（字幕から機械的に作ったもの）。文を短く直してから make.sh を再実行してください",
        "# 書式: 開始秒-終了秒 | 種類 | 文字   種類: q=質問（中央やや上・白） a=答えの要点（下の帯・シアン） n=数字の強調（中央やや下・特大）",
        "# 「#」で始まる行は無視されます。同じ時刻に n と a を並べると数字と一言を同時に出せます",
        "",
    ]
    notes = []
    for s, e, _k, text in events:
        text = text.replace("\n", " ").strip()
        core = re.sub(r"[、。！？!?\s]", "", text)
        if SKIP_RE.match(core):
            out.append(f"# {s:.1f}-{e:.1f} | - | {text}   （相づちなので出さない）")
            continue
        kind = "q" if re.search(r"[？?]|教えて|ですか|でしょうか", text) else "a"
        if kind == "q" and media:
            # q の開始は「文言の最初の語の言い始め」に合わせる（見つからなければキュー開始のまま）
            t0, why = q_align.align_start(media, s, e, text, model or q_align.DEFAULT_MODEL)
            if t0 is not None and round(t0, 1) > round(s, 1):
                notes.append(f"# q の開始時刻を自動調整: {s:.1f} → {t0:.1f}（{why}）")
                s = t0
            elif t0 is None:
                notes.append(f"# q の開始時刻は自動調整できず、キュー開始 {s:.1f} のまま（{why}）")
        t = f"{s:.1f}-{e:.1f}"
        nums = [m.group(0).strip() for m in NUM_RE.finditer(text) if re.search(r"\d", m.group(0))]
        nums = [n for n in nums if len(re.sub(r"\D", "", n)) >= 2]  # 1桁だけの数は強調しない
        if nums:
            out.append(f"{t} | n | {nums[0]}")
        out.append(f"{t} | {kind} | {text}")
    if notes:
        out += [""] + notes
    with open(dst, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print(f"下書きを作成: {dst}（{len(events)} 字幕から）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
