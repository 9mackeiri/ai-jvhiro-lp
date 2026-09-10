#!/usr/bin/env python3
"""WOFF(1.0) を TTF/OTF に変換する（標準ライブラリのみ）。

Pillow は WOFF を読めないため、pdf/fonts/ の Noto Sans JP（woff）を
そのまま使えるように sfnt 形式へ戻す。

使い方: python3 woff2ttf.py 入力.woff 出力.ttf
"""
import os
import struct
import sys
import zlib


def woff_to_sfnt(data: bytes) -> bytes:
    if data[:4] != b"wOFF":
        raise ValueError("WOFF 1.0 ではありません（先頭が wOFF でない）")
    (_sig, flavor, _length, num_tables, _res, _total, _maj, _min,
     _meta_off, _meta_len, _meta_orig, _priv_off, _priv_len) = struct.unpack(">4sIIHHIHHIIIII", data[:44])
    entries = []
    pos = 44
    for _ in range(num_tables):
        tag, offset, comp_len, orig_len, checksum = struct.unpack(">4sIIII", data[pos:pos + 20])
        pos += 20
        raw = data[offset:offset + comp_len]
        table = zlib.decompress(raw) if comp_len < orig_len else raw
        if len(table) != orig_len:
            raise ValueError(f"テーブル {tag!r} の長さが一致しません")
        entries.append((tag, checksum, table))

    entries.sort(key=lambda e: e[0])
    max_pow2 = 1
    while max_pow2 * 2 <= num_tables:
        max_pow2 *= 2
    search_range = max_pow2 * 16
    entry_selector = max_pow2.bit_length() - 1
    range_shift = num_tables * 16 - search_range

    header = struct.pack(">IHHHH", flavor, num_tables, search_range, entry_selector, range_shift)
    directory = b""
    body = b""
    offset = 12 + 16 * num_tables
    for tag, checksum, table in entries:
        directory += struct.pack(">4sIII", tag, checksum, offset, len(table))
        padded = table + b"\0" * ((4 - len(table) % 4) % 4)
        body += padded
        offset += len(padded)
    return header + directory + body


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    src, dst = sys.argv[1], sys.argv[2]
    with open(src, "rb") as f:
        out = woff_to_sfnt(f.read())
    tmp = dst + ".part"
    with open(tmp, "wb") as f:
        f.write(out)
    os.replace(tmp, dst)  # 途中で止まっても壊れたファイルを正式名に残さない
    print(f"変換: {src} -> {dst} ({len(out) // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
