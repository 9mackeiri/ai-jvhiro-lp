#!/usr/bin/env python3
"""動画の「最後の声の終わり」を無音検出で求め、--end に使う秒数と、それ以降の幻聴キューを表示する。

  python3 video/last_voice.py <動画または音声> [--srt 字幕.srt] [--after 2.0] [--noise -35] [--min-silence 1.0]

  - ffmpeg の silencedetect で「最後の無音区間の開始」= 最後の声の終わりを求める
  - 提案する --end = 最後の声の終わり + --after（既定 2.0 秒）。動画の長さを超えるときは動画の長さ
  - --srt を渡すと、最後の声の終わりより後に始まる字幕（幻聴の疑い）を番号付きで表示する（削除はしない）
  /telop の「末尾の判定」で使う。カメラのブレがある場合は木田の指示で --end をその直前にする
"""
import argparse
import os
import re
import subprocess
import sys


def duration(media):
    if not os.path.isfile(media):
        sys.exit(f"動画が見つかりません: {media}")
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", media],
                         capture_output=True, text=True, check=True).stdout.strip()
    return float(out)


def silences(media, noise, min_silence):
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", media, "-map", "0:a:0", "-af",
                        f"silencedetect=noise={noise}dB:d={min_silence}", "-f", "null", "-"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"無音検出に失敗しました（音声が無い？）:\n{r.stderr.strip()[-500:]}")
    starts = [float(m.group(1)) for m in re.finditer(r"silence_start: ([\d.]+)", r.stderr)]
    ends = [float(m.group(1)) for m in re.finditer(r"silence_end: ([\d.]+)", r.stderr)]
    return starts, ends


def srt_cues(path):
    cues = []
    txt = open(path, encoding="utf-8").read()
    for block in re.split(r"\n\s*\n", txt.strip()):
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue
        m = re.match(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", lines[1])
        if not m:
            continue
        s = int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3]) + int(m[4]) / 1000
        e = int(m[5]) * 3600 + int(m[6]) * 60 + int(m[7]) + int(m[8]) / 1000
        cues.append((lines[0].strip(), s, e, " ".join(lines[2:])))
    return cues


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("media")
    ap.add_argument("--srt")
    ap.add_argument("--after", type=float, default=2.0, help="最後の声の終わりから --end までの秒数（既定 2.0）")
    ap.add_argument("--noise", type=float, default=-35, help="無音とみなす音量 dB（既定 -35）")
    ap.add_argument("--min-silence", type=float, default=1.0, help="無音とみなす最短の長さ 秒（既定 1.0）")
    a = ap.parse_args()

    dur = duration(a.media)
    starts, ends = silences(a.media, a.noise, a.min_silence)
    # 最後の無音が動画の終わりまで続いているなら（silence_end が無い、または動画の終わりとほぼ同じ）、その開始が「最後の声の終わり」
    if starts and (len(ends) < len(starts) or ends[-1] < starts[-1] or ends[-1] >= dur - 0.3):
        last_voice = starts[-1]
    else:
        last_voice = dur  # 末尾まで音がある
    end = min(round(last_voice + a.after, 1), round(dur, 1))
    print(f"動画の長さ: {dur:.2f} 秒")
    print(f"最後の声の終わり: {last_voice:.2f} 秒（無音判定 {a.noise}dB・{a.min_silence}秒以上）")
    print(f"提案する --end: {end}（最後の声の {a.after} 秒後。末尾 0.5 秒はフェード）")
    if a.srt:
        if not os.path.isfile(a.srt):
            sys.exit(f"字幕が見つかりません: {a.srt}")
        ghosts = [c for c in srt_cues(a.srt) if c[1] >= last_voice - 0.3]
        if ghosts:
            print("最後の声より後に始まる字幕（幻聴の疑い。削除するなら .srt.bak に控えてから）:")
            for n, s, e, t in ghosts:
                print(f"  #{n} {s:.2f}-{e:.2f} {t}")
        else:
            print("最後の声より後に始まる字幕: なし")
    return 0


if __name__ == "__main__":
    sys.exit(main())
