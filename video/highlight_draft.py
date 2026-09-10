#!/usr/bin/env python3
"""SRT 字幕から、要点テロップ（highlight.txt）の下書きを作る。

  python3 highlight_draft.py 入力.srt 出力.highlight.txt [--force]
  出力先が既にあるときは --force を付けない限り上書きしない

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

NUM_RE = re.compile(r"[+\-]?\d[\d,]*(?:\.\d+)?\s*(?:円|個|件|%|％|万円|倍|人|日|か月|ヶ月|分|時間)?")
SKIP_RE = re.compile(r"^(かしこまりました|ありがとう(ございます)?|こちらこそ|はい|了解(しました)?)[、。！!]*$")


def main():
    args = [a for a in sys.argv[1:] if a != "--force"]
    force = "--force" in sys.argv[1:]
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
    for s, e, _k, text in events:
        text = text.replace("\n", " ").strip()
        t = f"{s:.1f}-{e:.1f}"
        core = re.sub(r"[、。！？!?\s]", "", text)
        if SKIP_RE.match(core):
            out.append(f"# {t} | - | {text}   （相づちなので出さない）")
            continue
        kind = "q" if re.search(r"[？?]|教えて|ですか|でしょうか", text) else "a"
        nums = [m.group(0).strip() for m in NUM_RE.finditer(text) if re.search(r"\d", m.group(0))]
        nums = [n for n in nums if len(re.sub(r"\D", "", n)) >= 2]  # 1桁だけの数は強調しない
        if nums:
            out.append(f"{t} | n | {nums[0]}")
        out.append(f"{t} | {kind} | {text}")
    with open(dst, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print(f"下書きを作成: {dst}（{len(events)} 字幕から）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
