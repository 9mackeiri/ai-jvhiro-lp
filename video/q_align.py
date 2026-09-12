#!/usr/bin/env python3
"""q（質問テロップ）の開始時刻を「文言の最初の語を言い始めた時刻」に合わせる。

whisper.cpp を単語単位（-ml 1）で、指定した区間だけ再認識し、
q の文言の先頭 2 文字（例:「在庫と仕入れの…」→「在庫」）が最初に出てくるトークンの開始時刻を返す。

使い方（単体）:
  python3 video/q_align.py <動画または音声> <開始秒> <終了秒> "<q の文言>" [--model パス]
  例: python3 video/q_align.py 入力/IMG_8948.MOV 0.0 10.0 "在庫と仕入れのタイミングは？"

highlight_draft.py からも呼ばれる（q 行の開始時刻の自動調整）。
語が見つからないときは None を返し、呼び出し側はキュー開始のままにする。
"""
import codecs
import os
import re
import subprocess
import sys
import tempfile

DEFAULT_MODEL = os.path.expanduser("~/.cache/whisper-cpp/ggml-large-v3-turbo.bin")
PUNCT_RE = re.compile(r"[\s、。！？!?「」『』（）()・|,.\-−:：]+")
TS_RE = re.compile(rb"\[(\d+):(\d+):(\d+\.\d+) --> (\d+):(\d+):(\d+\.\d+)\]\s*(.*)")


def _norm(s):
    return PUNCT_RE.sub("", s)


def word_timings(media, start, end, model=DEFAULT_MODEL, prompt=None):
    """[(開始秒, 終了秒, トークン)] を返す。時刻は動画全体の秒。
    whisper.cpp の -ml 1 は 1 文字の UTF-8 バイト列を 2 トークンに割ることがあるため、
    バイト列のまま受け取り、_tokens_to_text() で結合しながら復号する。トークン文字列は表示用（欠けた字は「?」）。"""
    if not os.path.isfile(model):
        raise FileNotFoundError(f"文字起こしモデルがありません: {model}")
    with tempfile.TemporaryDirectory(prefix="qalign") as td:
        wav = os.path.join(td, "seg.wav")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", media,
                        "-map", "0:a:0", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", wav], check=True)
        cmd = ["whisper-cli", "-m", model, "-l", "ja", "-f", wav, "-t", "8", "-bs", "5", "-ml", "1", "-np"]
        if prompt:
            cmd += ["--prompt", prompt]
        out = subprocess.run(cmd, capture_output=True, check=True).stdout
    toks = []
    for line in out.splitlines():
        m = TS_RE.match(line.strip())
        if not m:
            continue
        h1, m1, s1, h2, m2, s2, raw = m.groups()
        t0 = int(h1) * 3600 + int(m1) * 60 + float(s1) + start
        t1 = int(h2) * 3600 + int(m2) * 60 + float(s2) + start
        raw = raw.strip()
        if raw:
            toks.append((t0, t1, raw))
    return toks


def _tokens_to_text(toks):
    """バイト列トークンを結合しながら復号し、(文字, その文字が始まったトークン番号) の列を返す。"""
    dec = codecs.getincrementaldecoder("utf-8")(errors="replace")
    chars, pending = [], None
    for i, (_t0, _t1, raw) in enumerate(toks):
        buffered = bool(dec.getstate()[0])
        for k, ch in enumerate(dec.decode(raw)):
            chars.append((ch, pending if (k == 0 and buffered and pending is not None) else i))
        pending = i if dec.getstate()[0] else None
    for ch in dec.decode(b"", final=True):
        chars.append((ch, pending if pending is not None else len(toks) - 1))
    return chars


def _tok_str(raw):
    return raw.decode("utf-8", errors="replace")


def align_start(media, start, end, text, model=DEFAULT_MODEL):
    """q の文言の先頭 2 文字が最初に出てくるトークンの開始秒を返す。見つからなければ None。
    戻り値: (開始秒 or None, 説明文)"""
    text = re.sub(r"^\s*[JjＪｊ][:：]\s*", "", text)
    target = _norm(text)[:2]
    if not target:
        return None, "文言が空"
    try:
        toks = word_timings(media, start, min(end + 0.5, end + 0.5), model, prompt=text)
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        return None, f"単語時刻を取れませんでした（{e}）"
    # トークンをつないだ文字列の中で target を探し、その文字が始まったトークンの開始時刻を返す
    pairs = [(ch, i) for ch, i in _tokens_to_text(toks) if not PUNCT_RE.fullmatch(ch)]
    concat = "".join(ch for ch, _i in pairs)
    pos = concat.find(target)
    if pos < 0:
        return None, f"「{target}」が単語時刻の中に見つかりません（認識: {concat[:40]}…）"
    i = pairs[pos][1]
    t0 = toks[i][0]
    if not (start - 0.05 <= t0 < end):
        return None, f"「{target}」の時刻 {t0:.2f}s が区間外"
    return round(t0, 2), f"「{target}」= {_tok_str(toks[i][2])} {toks[i][0]:.2f}s-{toks[i][1]:.2f}s"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--model")]
    model = DEFAULT_MODEL
    for a in sys.argv[1:]:
        if a.startswith("--model="):
            model = a.split("=", 1)[1]
    if len(args) != 4:
        print(__doc__, file=sys.stderr)
        return 2
    media, start, end, text = args[0], float(args[1]), float(args[2]), args[3]
    t, why = align_start(media, start, end, text, model)
    print(f"開始時刻: {t if t is not None else 'なし（キュー開始のまま）'}  {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
