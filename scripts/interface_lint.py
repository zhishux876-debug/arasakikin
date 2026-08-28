#!/usr/bin/env python3
"""Web Interface Guidelines のうち、単一HTMLのLPで機械検査できる行だけを検査する.

出自は Vercel の Web Interface Guidelines（MIT）。原文と各行の扱いは
`references/web-interface-guidelines.md` に固定してある。上流スキルのように
実行のたびに raw URL を取りに行かない。ネットに出られない環境でも通り、
上流が変わっても過去の合格が再現するようにするため。

`verify.py` との住み分け:

  verify.py         ブラウザで開いて「実際にどう描かれたか」を見る（横スクロール・
                    タップ領域・隠れたテキスト・[FIX]照合）。playwright が要る
  interface_lint.py ソースを読んで「書かれ方」を見る（focus・aria・アンカーの行き先・
                    transition の中身・画像の寸法）。標準ライブラリだけで動く

つまりこれは verify.py の代わりではない。**両方通して初めて Gate 3 が埋まる。**

使い方:
  .\\.venv\\Scripts\\python.exe scripts/interface_lint.py output/<案件名>/
  .\\.venv\\Scripts\\python.exe scripts/interface_lint.py output/<案件名>/lp-a.html --json

FAIL が1件でもあれば終了コード 1。WARN と note は 0 のまま返す（判断は人間に残す）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# レイアウトの再計算（reflow）を伴うプロパティ。
# **`classify()` は完全一致で照合する。** だから `height` を入れても `max-height` は
# 当たらない。実際にすり抜けた: yaaac の D案は `transition: max-height .24s` を
# 書いていて、この検査器は FAIL 0 / WARN 0 と報告していた（v6 で判明）。
# 接頭辞照合に変える案は採らなかった。`background-position` のように
# 「height を含むが別物」を巻き込むほうが害が大きい。**列挙を厚くする。**
REFLOW_PROPS = (
    "width", "height", "top", "left", "right", "bottom",
    "max-width", "max-height", "min-width", "min-height",
    "block-size", "inline-size", "max-block-size", "max-inline-size",
    "min-block-size", "min-inline-size",
    "inset", "inset-block", "inset-inline",
    "margin", "margin-top", "margin-left", "margin-right", "margin-bottom",
    "padding", "padding-top", "padding-left", "padding-right", "padding-bottom",
    "border-width", "border-top-width", "border-right-width",
    "border-bottom-width", "border-left-width",
    "font-size", "line-height", "letter-spacing", "word-spacing",
    "gap", "row-gap", "column-gap", "flex-basis",
    "grid-template-rows", "grid-template-columns",
)
# 対になる値が `none` / `auto` になりがちで、**補間できないので遷移が黙って死ぬ**
# プロパティ。yaaac の D案は `max-height: 0` と `max-height: none` を行き来していて、
# 押した直後のフレームで offsetHeight が 0 -> 471 に飛んでいた（.24s は効いていない）
NON_INTERPOLATABLE_RISK = (
    "max-height", "max-width", "height", "width",
    "grid-template-rows", "grid-template-columns", "flex-basis",
)
# reflow は起きないが合成だけでは済まず、面の再描画が走るプロパティ。
# 色（color / background-color / border-color）は入れない。hover の小さな
# フィードバックに使うのが普通で、verify.py も同じ理由で対象外にしている。
REPAINT_PROPS = ("box-shadow", "filter")
LAYOUT_PROPS = REFLOW_PROPS + REPAINT_PROPS


def classify(props):
    """CLAUDE.md はどちらも禁止。ただし直し方が違うので言い分ける."""
    reflow = sorted({p for p in props if p in REFLOW_PROPS})
    repaint = sorted({p for p in props if p in REPAINT_PROPS})
    return reflow, repaint


def strip_noise(css: str) -> str:
    """data: URI と @font-face を落とす.

    サブセットフォントを base64 で同梱すると <style> に数百KBの1トークンができ、
    素朴な正規表現が破滅的バックトラックで固まる（CLAUDE.md「既知の罠」）。
    """
    css = re.sub(r"url\(\s*['\"]?data:[^)]*\)", "url()", css, flags=re.S)
    css = re.sub(r"@font-face\s*\{[^}]*\}", "", css, flags=re.S)
    return css


def line_of(src: str, idx: int) -> int:
    return src.count("\n", 0, idx) + 1


class Collector(HTMLParser):
    """要素の素朴な収集. 単一HTMLのLPを想定しており、厳密なDOMは作らない."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: set[str] = set()
        self.styles: list[str] = []
        self.imgs: list[dict] = []
        self.inputs: list[dict] = []
        self.metas: list[dict] = []
        self.links: list[dict] = []
        self.selects: int = 0
        self.html_attrs: dict = {}
        self._in_style = False

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if "id" in a:
            self.ids.add(a["id"])
        if tag == "style":
            self._in_style = True
        elif tag == "html":
            self.html_attrs = a
        elif tag == "img":
            self.imgs.append(a)
        elif tag in ("input", "textarea"):
            self.inputs.append({"tag": tag, **a})
        elif tag == "select":
            self.selects += 1
        elif tag == "meta":
            self.metas.append(a)
        elif tag == "link":
            self.links.append(a)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag == "style":
            self._in_style = False

    def handle_data(self, data):
        if self._in_style:
            self.styles.append(data)


def inner_text(fragment: str) -> str:
    return re.sub(r"<[^>]+>", "", fragment).strip()


def lint(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8", errors="replace")
    src = re.sub(r"<!--.*?-->", "", raw, flags=re.S)  # コメント内の記述で誤検知しない

    col = Collector()
    try:
        col.feed(src)
    except Exception:  # 壊れたHTMLでも検査は続ける
        pass
    css = strip_noise("\n".join(col.styles))

    fails: list[str] = []
    warns: list[str] = []
    notes: list[str] = []

    def fail(msg):
        fails.append(msg)

    def warn(msg):
        warns.append(msg)

    def note(msg):
        notes.append(msg)

    # ---- フォーカス ---------------------------------------------------
    outline_off = list(re.finditer(r"outline\s*:\s*(?:none|0)\b", css))
    if outline_off and ":focus-visible" not in css:
        fail(f"outline を消しているのに :focus-visible の可視表現が無い"
             f"（{len(outline_off)}箇所、最初は style 内 {line_of(css, outline_off[0].start())} 行目）")
    if ":focus" not in css:
        warn("フォーカス時のスタイルが1つも無い。キーボードで辿ると今どこにいるか分からない")

    # ---- ズーム禁止 ---------------------------------------------------
    for m in col.metas:
        if m.get("name", "").lower() == "viewport":
            c = m.get("content", "").replace(" ", "")
            if "user-scalable=no" in c or "maximum-scale=1" in c:
                fail(f"viewport がブラウザのズームを禁止している: {m.get('content')}")

    # ---- モーション ---------------------------------------------------
    for m in re.finditer(r"transition\s*:\s*([^;}]+)", css):
        if re.search(r"\ball\b", m.group(1)):
            fail(f"transition: all を使っている（style 内 {line_of(css, m.start())} 行目）。"
                 "変えるプロパティを明示する")
    for m in re.finditer(r"transition(?:-property)?\s*:\s*([^;}]+)", css):
        hit = [p for p in LAYOUT_PROPS
               if re.search(rf"(?<![-\w]){re.escape(p)}(?![-\w])", m.group(1))]
        reflow, repaint = classify(hit)
        ln = line_of(css, m.start())
        if reflow:
            fail(f"transition がレイアウトを動かしている: {', '.join(reflow)}"
                 f"（style 内 {ln} 行目）。transform に置き換える")
        if repaint:
            # transition は一過性なので WARN。連続で回る @keyframes は下で FAIL にする
            warn(f"transition が面の再描画を伴うプロパティを動かしている: "
                 f"{', '.join(repaint)}（style 内 {ln} 行目）。"
                 "hover の一瞬なら許容範囲。影は疑似要素の opacity で作ると軽い")
        # **書いてあるのに効かない遷移**を名指しする。reflow の FAIL とは別の欠陥で、
        # 「transform に置き換えろ」だけでは、なぜ動かなかったのかが分からない
        dead = sorted({p for p in hit if p in NON_INTERPOLATABLE_RISK
                       and re.search(rf"(?<![-\w]){re.escape(p)}\s*:\s*(?:none|auto)\b", css)})
        if dead:
            fail(f"transition に {', '.join(dead)} を宣言しているが、同じ CSS 内で "
                 f"{dead[0]}: none または auto を代入している（style 内 {ln} 行目）。"
                 "none と auto は補間できないので、**この遷移は書いてあるだけで効かない。**"
                 "器の寸法は瞬時に切り替え、中身を opacity / transform で出す")
    for name, body in iter_keyframes(css):
        hit = {d.group(1) for d in re.finditer(r"(?:^|[{;\s])([a-z-]+)\s*:", body)
               if d.group(1) in LAYOUT_PROPS}
        reflow, repaint = classify(hit)
        if reflow:
            fail(f"@keyframes {name} がレイアウトを動かしている: {', '.join(reflow)}。"
                 "transform に置き換える")
        if repaint:
            fail(f"@keyframes {name} が面の再描画を伴うプロパティを毎フレーム動かしている: "
                 f"{', '.join(repaint)}。影は疑似要素を重ねて opacity で出す")
    loops = re.findall(r"animation\s*:[^;}]*\binfinite\b", css)
    if loops:
        warn(f"無限ループのアニメーションが {len(loops)} 件ある。5秒を超えて動き続けるなら"
             "停止手段が要る（reduced-motion での停止で足りるなら契約に例外を書く）")
    if re.search(r"<svg", src, re.I) and re.search(r"transform\s*:", css) and "transform-box" not in css:
        note("SVG を変形させているなら <g> に当て、transform-box: fill-box を付ける")

    # ---- ページ内アンカー ---------------------------------------------
    anchors = list(re.finditer(r"<a\b[^>]*href\s*=\s*[\"'](#[^\"']*)[\"'][^>]*>(.*?)</a>",
                               src, flags=re.S | re.I))
    for m in anchors:
        target = m.group(1)[1:]
        if not target or target == "top":
            continue
        if target not in col.ids:
            fail(f'href="#{target}" の行き先 id がページに無い（{line_of(src, m.start())} 行目）')
    # 自分自身の中にあるアンカー（応募セクションの中の #apply など）
    for sec in re.finditer(r"<(section|div|footer)\b[^>]*id\s*=\s*[\"']([^\"']+)[\"']", src, re.I):
        sid = sec.group(2)
        seg = src[sec.start():]
        close = seg.find(f"</{sec.group(1)}>")
        seg = seg[:close] if close > 0 else seg[:4000]
        if re.search(rf'href\s*=\s*["\']#{re.escape(sid)}["\']', seg):
            warn(f"#{sid} の中に #{sid} 自身へ飛ぶリンクがある。押しても何も起きない")
    if anchors and re.search(r"position\s*:\s*(sticky|fixed)", css) and "scroll-margin-top" not in css:
        warn("追従ヘッダがあるのにアンカー先へ scroll-margin-top が無い。"
             "飛んだ先で見出しがヘッダの下に隠れる")

    # ---- 既知の罠（CLAUDE.md 由来。上流ルールセットには無い） ----------
    if re.search(r"position\s*:\s*sticky", css):
        root_hidden = re.search(
            r"(?:^|[},])\s*(?:[^{},]*\b(?:html|body)\b[^{}]*)\{[^}]*overflow-x\s*:\s*hidden", css)
        if root_hidden:
            fail("html/body の overflow-x: hidden と position: sticky が同居している。"
                 "スクロールコンテナができて追従が効かない。overflow-x: clip にする")
        elif re.search(r"overflow-x\s*:\s*hidden", css):
            warn("overflow-x: hidden と position: sticky が同じファイルにある。"
                 "hidden を書いた要素が sticky の先祖なら追従が死ぬ。経路を確認する")
    for m in re.finditer(r"<span\b[^>]*style\s*=\s*[\"']([^\"']*)[\"']", src, re.I):
        st = m.group(1)
        if re.search(r"\b(width|height)\s*:", st) and not re.search(
                r"display\s*:\s*(block|inline-block|flex|grid)", st):
            fail(f"<span> に width/height を指定しているが display が無い"
                 f"（{line_of(src, m.start())} 行目）。inline 要素には効かない")

    # ---- 名前のない操作要素 --------------------------------------------
    for m in re.finditer(r"<(a|button)\b([^>]*)>(.*?)</\1>", src, flags=re.S | re.I):
        tag, attrs, body = m.group(1), m.group(2), m.group(3)
        if inner_text(body):
            continue
        if not re.search(r"<(svg|img|i)\b", body, re.I):
            continue
        if re.search(r"aria-label(?:ledby)?\s*=|title\s*=", attrs, re.I):
            continue
        if re.search(r'alt\s*=\s*["\'][^"\']+["\']', body, re.I):
            continue
        fail(f"アイコンだけの <{tag}> にアクセシブルな名前が無い（{line_of(src, m.start())} 行目）")
    for m in re.finditer(r"<div\b[^>]*\bonclick\s*=\s*[\"']([^\"']*)[\"']", src, re.I):
        if re.search(r"location|href|open\(", m.group(1)):
            fail(f"<div onclick> でページ遷移している（{line_of(src, m.start())} 行目）。<a> を使う")

    # ---- タッチ -------------------------------------------------------
    if "touch-action" not in css:
        warn("touch-action: manipulation が無い。モバイルでダブルタップズームの遅延が出る")
    if "-webkit-tap-highlight-color" not in css:
        note("-webkit-tap-highlight-color が無い。タップ時に既定の灰色が出る")
    if re.search(r"position\s*:\s*fixed[^}]*bottom\s*:", css) and "safe-area-inset" not in css:
        note("画面下に固定した要素がある。env(safe-area-inset-bottom) を足さないと"
             "iPhone のホームバーに重なる")
    if re.search(r"(modal|drawer|overlay|dialog)", css, re.I) and "overscroll-behavior" not in css:
        note("モーダル/ドロワーらしき指定がある。overscroll-behavior: contain を検討する")

    # ---- フォーム -----------------------------------------------------
    if re.search(r"onpaste\s*=\s*[\"'][^\"']*return\s+false", src, re.I):
        fail("入力欄の貼り付けを禁止している")
    for f in col.inputs:
        t = f.get("type", "text").lower()
        if t in ("hidden", "submit", "button", "checkbox", "radio"):
            continue
        if "autocomplete" not in f:
            warn(f'<{f["tag"]} type="{t}"> に autocomplete が無い（name={f.get("name", "?")}）')
        if t == "email" and f.get("inputmode", "") != "email":
            note('<input type="email"> に inputmode="email" を足すとモバイルのキーが変わる')
        if t == "tel" and "inputmode" not in f:
            note('<input type="tel"> に inputmode="tel" を足す')
    for m in re.finditer(r"([^{}]*)\{([^}]*)\}", css):
        sel, body = m.group(1), m.group(2)
        if not re.search(r"\b(input|textarea|select)\b", sel):
            continue
        fs = re.search(r"font-size\s*:\s*([\d.]+)(px|rem|em)", body)
        if fs:
            v = float(fs.group(1))
            px = v if fs.group(2) == "px" else v * 16
            if px < 16:
                fail(f"入力欄の font-size が {fs.group(1)}{fs.group(2)}（≒{px:.0f}px）。"
                     "16px 未満だと iOS がフォーカス時に勝手にズームする")
    if col.selects and not re.search(r"select[^{}]*\{[^}]*background-color", css):
        note("<select> に background-color と color を明示する（Windows で黒背景に黒文字になる）")

    # ---- 画像 ---------------------------------------------------------
    for i, img in enumerate(col.imgs):
        s = img.get("src", "?")
        if not ("width" in img and "height" in img):
            fail(f'<img src="{s}"> に width/height 属性が無い。読み込み時にレイアウトがずれる')
        if i == 0:
            if img.get("loading") == "lazy":
                warn(f'先頭の画像 {s} が loading="lazy"。ファーストビューは eager にする')
            if img.get("fetchpriority") != "high":
                note(f'先頭の画像 {s} に fetchpriority="high" を付けると LCP が縮む')
        elif img.get("loading") != "lazy":
            warn(f'{s} に loading="lazy" が無い（先頭以外は遅延させる）')
        if "alt" not in img:
            fail(f'<img src="{s}"> に alt が無い')
        elif img["alt"].strip() in ("画像", "写真", "イメージ"):
            fail(f'{s} の alt が「{img["alt"]}」。何が写っているかを書く')

    # ---- フォント -----------------------------------------------------
    gfont = [l for l in col.links
             if "fonts.googleapis.com" in l.get("href", "")
             and "stylesheet" in l.get("rel", "").lower()]
    for l in gfont:
        if "display=swap" not in l["href"]:
            fail(f"Google Fonts の URL に display=swap が無い（{l['href'][:70]}）。"
                 "読み込み中に文字が消える")
    if gfont and not any(l.get("rel", "") == "preconnect" and "gstatic" in l.get("href", "")
                         for l in col.links):
        warn("fonts.gstatic.com への preconnect が無い。フォント取得が1往復ぶん遅れる")
    if gfont:
        fams = re.findall(r"font-family\s*:\s*([^;}]+)", css)
        if fams and not any("," in f for f in fams):
            warn("font-family にフォールバックが1つも無い。Webフォントが落ちると既定書体になる")

    # ---- テーマ -------------------------------------------------------
    bg = re.search(r"(?:^|[{;\s])body\s*\{[^}]*background(?:-color)?\s*:\s*(#[0-9a-fA-F]{3,6})", css)
    dark = False
    if bg:
        h = bg.group(1).lstrip("#")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        try:
            r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
            dark = (0.299 * r + 0.587 * g + 0.114 * b) < 96
        except ValueError:
            pass
    if dark and "color-scheme" not in css and "color-scheme" not in src:
        warn("暗い背景なのに color-scheme: dark が無い。スクロールバーと入力欄が白いまま浮く")
    if not any(m.get("name", "").lower() == "theme-color" for m in col.metas):
        note('<meta name="theme-color"> が無い。モバイルのブラウザUIが背景と繋がらない')

    # ---- 文字づかい ---------------------------------------------------
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", "", src)
    text = re.sub(r"<[^>]+>", " ", text)
    if "..." in text:
        warn("本文に「...」がある。三点リーダは「…」を使う。"
             "ただし [FIX] 文言の中なら直さず、完了報告で指摘する")
    if not re.search(r'href\s*=\s*["\']#(main|content|body)', src, re.I):
        note("「本文へスキップ」リンクが無い。ナビが長い案では入れる")

    return {"file": str(path), "fail": fails, "warn": warns, "note": notes}



def iter_keyframes(css: str):
    """@keyframes の中身を、**波括弧を数えて**取り出す.

    前は `@keyframes\s+([\w-]+)\s*\{(.*?)
\s*\}` で切っていた。
    改行の入った書き方なら当たるが、**1行に畳んだ @keyframes には終端が無い。**
    次の `
}` まで走って後続のルールを丸ごと飲み込み、
    そこにあった `width` や `filter` を「毎フレーム動かしている」と報告していた。
    実際には keyframes には transform しか無い、という誤検出が出る。

    行の書き方で結果が変わる検査は、検査ではない。
    """
    for m in re.finditer(r"@keyframes\s+([\w-]+)\s*\{", css):
        i = m.end()
        depth, n = 1, len(css)
        while i < n and depth:
            c = css[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            i += 1
        yield m.group(1), css[m.end():i - 1]


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Web Interface Guidelines のうち機械検査できる行を静的に検査する")
    ap.add_argument("paths", nargs="+", type=Path)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    files: list[Path] = []
    for p in args.paths:
        files.extend(sorted(p.glob("*.html")) if p.is_dir() else [p])

    results = [lint(f) for f in files if f.exists()]

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 1 if any(r["fail"] for r in results) else 0

    failed = 0
    for r in results:
        print(f"\n=== {Path(r['file']).name} ===")
        for m in r["fail"]:
            print(f"  [FAIL ] {m}")
        for m in r["warn"]:
            print(f"  [WARN ] {m}")
        for m in r["note"]:
            print(f"  [note ] {m}")
        if r["fail"]:
            failed += 1
        else:
            print("  → FAIL なし")
    print(f"\n{len(results)}件を検査、FAIL のあるファイル {failed}件。")
    print("WARN と note は不合格ではない。直さない判断をしたら理由を contract か完了報告に残す。")
    print("これはソースの検査であって、実際の描画は verify.py が別に見る。")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
