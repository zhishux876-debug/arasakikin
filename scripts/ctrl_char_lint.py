#!/usr/bin/env python3
r"""テキストファイルに潰れた制御文字が混じっていないかを検査する.

この docstring は **raw 文字列**（先頭に `r` を付けたもの）である。そうしないと、
ここに書いた `\b` や `\1` が**この検査が探しているまさにその制御文字になる。**

## なぜ専用の検査が要るか

2026-08-27〜28 に、この作業場で**同じ欠陥が3回**起きた。

| 回 | 潰れたもの | 何が起きたか |
| :--- | :--- | :--- |
| 1 | `scripts\verify.py` などの `\v` `\r` `\a` | `scripts/README.md` の表でスクリプト名が壊れた（表示だけの害） |
| 2 | 正規表現の `\b`（単語境界）→ 0x08 | `interface_lint.py` の「overflow-x:hidden が sticky を壊す」検査が**一度も発火しない状態**になっていた |
| 3 | 正規表現の `\1`（後方参照）→ 0x01 | `design_spec_lint.py` の `hero_of()` が常に空を返し、**検査が黙って無効化**されていた |

原因は共通で、**ヒアドキュメント経由でファイルを書くとバックスラッシュが1段落ちる**。
`cat > f <<'EOF'` のように引用しても落ちる経路がある。

害の質が悪い。**壊れた正規表現は例外を出さない。** 何にもマッチしないだけなので、
検査は「FAIL 0」を報告し続ける。書いた本人も、次に読む人も気づけない。
3回目は「1回目・2回目の記録を書いている最中」に起きた。

そして**その場かぎりの走査では取りこぼす。** 実際に、両セッションが「0件」と報告した後に
2件（`decisions.md` の 0x01 ×3、`yaaac-stamp-dial-craft/README.md` の 0x0b）が残っていた。
走査した範囲と、走査した時点の問題である。だから検査に落とす。

## 直し方の候補まで出す

0x08 なら `\b`、0x0b なら `\v` と分かる。ただし 0x01〜0x07 は
後方参照（`\1`〜`\7`）とも読めるため、候補を並べて人間に選ばせる。
**自動修復はしない。** `\7` と `\a` はどちらも 0x07 で、機械には決められない。

## 使い方

    .\.venv\Scripts\python.exe scripts/ctrl_char_lint.py
    .\.venv\Scripts\python.exe scripts/ctrl_char_lint.py output/ scripts/

FAIL が1件でもあれば終了コード 1。パイプラインのゲートに入れられる。
"""
from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]

# 検査する拡張子。バイナリは見ない
SUFFIXES = {".py", ".md", ".html", ".htm", ".json", ".spec", ".toml", ".txt",
            ".css", ".js", ".mjs", ".yml", ".yaml", ".ps1", ".sh", ".csv"}

# 入らないディレクトリ
SKIP_DIRS = {".venv", ".venv-broken-python312", "node_modules", "__pycache__",
             ".git", "Takeout", ".gemini"}

# 許す制御文字。**`\r` は CRLF の一部としてだけ許す**（単独の CR は落とす）
ALLOWED = {0x09, 0x0A}

# 潰れる前の姿の候補。0x01〜0x07 は後方参照とも読めるので両方出す
ORIGIN = {
    0x00: ["\\0"],
    0x07: ["\\a", "\\7"],
    0x08: ["\\b", "\\10(8進)"],
    0x0B: ["\\v"],
    0x0C: ["\\f"],
    0x0D: ["\\r"],
    0x1B: ["\\e", "\\033"],
}
for d in range(1, 8):
    ORIGIN.setdefault(d, []).insert(0, f"\\{d}")


def scan(text: str) -> list[tuple[int, int, int]]:
    """(行, 桁, コード) を返す. CRLF は先に落とす."""
    text = text.replace("\r\n", "\n")
    out: list[tuple[int, int, int]] = []
    line, col = 1, 1
    for ch in text:
        code = ord(ch)
        if code == 0x0A:
            line, col = line + 1, 1
            continue
        if (code < 0x20 and code not in ALLOWED) or code == 0x7F:
            out.append((line, col, code))
        col += 1
    return out


def targets(paths: list[Path]):
    for base in paths:
        if base.is_file():
            if base.suffix.lower() in SUFFIXES:
                yield base
            continue
        for p in sorted(base.rglob("*")):
            if not p.is_file() or p.suffix.lower() not in SUFFIXES:
                continue
            if any(part in SKIP_DIRS for part in p.parts):
                continue
            yield p


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    paths = [Path(a) for a in args] if args else [ROOT]
    bad = 0
    checked = 0
    for p in targets(paths):
        checked += 1
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        hits = scan(text)
        if not hits:
            continue
        bad += 1
        try:
            shown = p.relative_to(ROOT)
        except ValueError:
            shown = p
        print(f"[FAIL] {shown}")
        for line, col, code in hits[:12]:
            cand = " または ".join(ORIGIN.get(code, ["?"]))
            print(f"         {line}行{col}桁  {hex(code)}  <- おそらく {cand} が潰れたもの")
        if len(hits) > 12:
            print(f"         ... 他 {len(hits) - 12} 件")

    print(f"\n{checked} ファイルを検査、問題のあるファイル {bad} 件。")
    if bad:
        print("**壊れた正規表現は例外を出さない。** 検査が黙って無効化されている可能性がある。")
        print("直したら、意図的に壊した複製でその検査が発火することを必ず確かめる。")
        print("ヒアドキュメントではなく Write ツールか、バックスラッシュを "
              "chr(92) で組み立てる方法で書き直す。")
        sys.exit(1)
    print("潰れた制御文字は無い。")


if __name__ == "__main__":
    main()
