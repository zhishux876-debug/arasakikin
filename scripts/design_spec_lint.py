#!/usr/bin/env python3
"""意匠の正本（DESIGN.md）と実装（HTML）を機械照合する。

この作業場には検査が3つある。役割は重ならない。

  verify.py            実際にどう描かれたか（実機レンダリング・確定コピー照合）
  interface_lint.py    どう書かれているか（ソースの静的検査）
  design_spec_lint.py  **決めた意匠から外れていないか**（正本との照合）

なぜ要るか: この案件では、施主の指示（ヒーローから年齢を外す）が別セッションの
書き直しで巻き戻り、成果物ファイルそのものが一度削除された。
`decisions.md` の法則「決めた禁止は、検査に落ちるまで守られない」を意匠の層にも当てる。

**この検査はソースを見る。** DOM・computed style・実測は verify.py の担当で、
ここでは「書かれ方」しか見られない。見えない穴は DESIGN.md §12 に列挙してある。

DESIGN.md の `<!-- spec:begin -->` … `<!-- spec:end -->` の間にある ```spec ブロックを読む。
1行1規則。行頭の `#`、および空白に続く `#` から行末はコメント（`#F2B705` は壊さない）。

  target FILENAME               この正本が支配するファイル（宣言は必須）
  token NAME VALUE              :root が NAME: VALUE を定義している（完全一致）
  font FAMILY                   Google Fonts の指定と font-family の両方に現れる
  order SEL...                  その順序で HTML に現れる（.class / #id / タグ名）
  require-selector SEL          CSS にそのセレクタがある
  require-text STR              本文テキストに現れる（タグで分断されていてもよい）
  require-raw STR               HTML のどこかに現れる（href などの属性値を見るとき）
  require-count STR N           HTML に N 回以上現れる
  require-near A B N            A の後 N 文字以内に B が現れる
  forbid-regex PATTERN          どこにも一致しない
  forbid-in-hero STR            <header class="hero"> … </header> の中に現れない
  include PATH                  別の spec ファイルを取り込む（案件をまたぐ不変条件）
  forbid-stale-copy GLOB        同じ頁の複製が他所に残っていない（古い版の公開を止める）
  require-file-contains F STR   同じディレクトリの別ファイル F に STR がある
  forbid-file-contains F STR    同じディレクトリの別ファイル F に STR が無い
  max-animation-ms N            すべての animation の duration が N ms 以下
  min-tap-px N                  操作要素の min-height が N px 以上（0件ならFAIL）

**壊れた正規表現・未知の規則・正本の不在は FAIL。** 規則名のタイプミスで検査が
無効化されると、通っていることの意味が消える（Codex 監査 2026-08-27 の指摘）。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RE_HERO = '<%s[^>]*class="[^"]*hero[^"]*"[^>]*>(.*?)</%s>'
SPEC_BLOCK = re.compile(r"<!--\s*spec:begin\s*-->(.*?)<!--\s*spec:end\s*-->", re.S)
FENCE = re.compile(r"```spec\s*(.*?)```", re.S)
# 操作要素の判定はセレクタを字句で切って一致させる（`.apply` が "a" に化けないように）
TAP_TOKENS = {"a", "button", "label", ".btn", ".cta", ".tab", ".tablist"}
KNOWN = {
    "target", "token", "font", "order", "require-selector", "require-text", "require-raw",
    "require-count", "require-near", "forbid-regex", "forbid-in-hero",
    "require-file-contains", "forbid-file-contains", "max-animation-ms", "min-tap-px",
    "include", "forbid-stale-copy",
    "brief", "canonical", "require-spec-meta", "invariant-coverage",
}
# 正本の見出しメタ（改訂の手続き。Codex 監査 2026-08-27「正本を先に直す以外の手続きが無い」）
META_KEYS = ("revision", "status", "owner", "updated", "brief", "canonical")


def norm(s: str) -> str:
    """照合用: 空白と改行位置指定のスラッシュを落とす（verify.py と同じ規則）."""
    return re.sub(r"[\s/]+", "", s)


def load_rules(spec_path: Path, _depth: int = 0) -> list[tuple[int, str, list[str]]]:
    if _depth > 3:
        raise ValueError(f"{spec_path}: include が深すぎる（循環の疑い）")
    text = spec_path.read_text(encoding="utf-8")
    if spec_path.suffix == ".spec":
        # 共有の規則ファイルは全体が規則。マーカーを要求しない
        body = text
    else:
        block = SPEC_BLOCK.search(text)
        if not block:
            raise ValueError(f"{spec_path} に <!-- spec:begin --> … <!-- spec:end --> が無い")
        fenced = FENCE.search(block.group(1))
        body = fenced.group(1) if fenced else block.group(1)
    rules: list[tuple[int, str, list[str]]] = []
    for i, raw in enumerate(body.splitlines(), 1):
        if raw.strip().startswith("#"):
            continue
        line = re.sub(r"\s+#\s.*$", "", raw).strip()
        if not line:
            continue
        parts = line.split()
        if parts[0] == "include" and len(parts) >= 2:
            # 案件をまたぐ不変条件（references/common.spec など）を取り込む。
            # 毎案件へコピペすると、直したときに古い写しが残る
            inc = (spec_path.parent / parts[1]).resolve()
            if not inc.exists():
                raise ValueError(f"{spec_path}: include 先が無い → {parts[1]}")
            rules.extend(load_rules(inc, _depth + 1))
            continue
        rules.append((i, parts[0], parts[1:]))
    return rules


def targets_of(rules) -> list[str]:
    return [a[0] for _, kind, a in rules if kind == "target" and a]


def declared(rules, kind: str) -> str:
    """spec の宣言行（brief / canonical）を1つ取り出す."""
    for _, k, a in rules:
        if k == kind and a:
            return " ".join(a)
    return ""


def spec_meta(spec_path: Path) -> dict:
    """正本の冒頭メタ（`- revision: 3` の形）を読む."""
    out = {}
    head = spec_path.read_text(encoding="utf-8").split("---", 1)[0]
    for key in META_KEYS:
        m = re.search(rf"(?mi)^[-*]?\s*{key}\s*[:：]\s*(.+)$", head)
        if m:
            # 値のあとに書かれた説明（← … / # … / 全角空白以降）は落とす
            val = re.split(r"\s*(?:←|#|　)", m.group(1).strip())[0]
            out[key] = val.strip()
    return out


def invariant_ids(spec_path: Path) -> list[str]:
    """本文の不変条件表から I-番号を集める（`| I-9 | … |`）."""
    text = spec_path.read_text(encoding="utf-8")
    return sorted(set(re.findall(r"\|\s*(I-\d+)\s*\|", text)), key=lambda s: int(s[2:]))


def css_of(html: str) -> str:
    return "\n".join(m.group(1) for m in re.finditer(r"<style[^>]*>(.*?)</style>", html, re.S))


def strip_css_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", " ", css, flags=re.S)


def hero_of(html: str) -> str:
    # hero は案によって header / section / div のどれでもよい
    # （山吹案は header、クラフト案は section）
    for tag in ("header", "section", "div"):
        m = re.search(RE_HERO % (tag, tag), html, re.S)
        if m:
            return m.group(1)
    return ""


def plain_text(html: str) -> str:
    body = re.sub(r"(?s)<(script|style)[^>]*>.*?</\1>", " ", html)
    body = re.sub(r"(?s)<!--.*?-->", " ", body)
    return re.sub(r"<[^>]+>", " ", body)


def selector_tokens(sel: str) -> set[str]:
    """`.tablist label:hover` → {'.tablist', 'label'}"""
    out = set()
    for part in re.split(r"[\s>+~,]+", sel.strip()):
        part = re.sub(r"::?[\w-]+(\([^)]*\))?", "", part)  # 疑似クラス/要素を落とす
        part = re.sub(r"\[[^\]]*\]", "", part)
        if part:
            out.add(part)
    return out


def check(html_path: Path, spec_path: Path, rules) -> int:
    raw = html_path.read_text(encoding="utf-8")
    # コメントは出荷される記述ではない。禁止語も必須語もコメントでは数えない
    # （Codex 監査 2026-08-27 の指摘。実際に自分のコメントで誤報を出した）
    html = re.sub(r"(?s)<!--.*?-->", " ", raw)
    css = strip_css_comments(css_of(html))
    hero = hero_of(html)
    ntext = norm(plain_text(html))
    root = ""
    m = re.search(r":root\s*\{(.*?)\}", css, re.S)
    if m:
        root = m.group(1)

    fails: list[str] = []
    notes: list[str] = []
    passed = 0

    for line_no, kind, args in rules:
        label = f"{kind} {' '.join(args)}"[:88]
        problems: list[str] = []

        def fail(msg: str) -> None:
            problems.append(msg)

        if kind == "target":
            passed += 1

        elif kind == "token" and len(args) >= 2:
            name, want = args[0], " ".join(args[1:])
            got = re.search(rf"{re.escape(name)}\s*:\s*([^;}}]+)", root)
            if not got:
                fail(f":root に {name} が無い")
            elif got.group(1).strip() != want:
                fail(f"{name} が {got.group(1).strip()}（正本は {want}）")

        elif kind == "font":
            fam = " ".join(args)
            if fam.replace(" ", "+") not in html:
                fail(f"Google Fonts の指定に {fam} が無い")
            elif fam not in css:
                fail(f"font-family に {fam} が無い（読み込んでいるが使っていない）")

        elif kind == "order":
            pos = -1
            for sel in args:
                # class は語単位で探す（class="band band-tight intro" のような複数指定に当てる）
                if sel.startswith("."):
                    pat = rf"<[a-z]+[^>]*class=\"[^\"]*(?<![\w-]){re.escape(sel[1:])}(?![\w-])"
                elif sel.startswith("#"):
                    pat = rf"<[a-z]+[^>]*id=\"{re.escape(sel[1:])}\""
                else:
                    pat = rf"<{re.escape(sel)}\b"
                hit = re.search(pat, html[pos + 1:])
                if not hit:
                    fail(f"{sel} が（要素として）この順序で見つからない")
                    break
                pos = pos + 1 + hit.start()

        elif kind == "require-selector":
            sel = " ".join(args)
            found = any(sel in selector_tokens(r.group(1)) or sel in r.group(1)
                        for r in re.finditer(r"([^{}]+)\{[^}]*\}", css))
            if not found:
                fail(f"CSS に {sel} が無い（コメントは除外して探した）")

        elif kind == "require-text":
            if norm(" ".join(args)) not in ntext:
                fail("本文に現れない")

        elif kind == "require-raw":
            if " ".join(args) not in html:
                fail("HTML に現れない（属性・スクリプトも含めて探した）")

        elif kind == "require-count" and len(args) >= 2:
            want, n = " ".join(args[:-1]), int(args[-1])
            got = html.count(want)
            if got < n:
                fail(f"{n} 回以上のはずが {got} 回")

        elif kind == "require-near" and len(args) >= 3:
            a, b, span = args[0], args[1], int(args[2])
            i = ntext.find(norm(a))
            if i < 0:
                fail(f"{a} が本文に無い")
            elif norm(b) not in ntext[i:i + span]:
                fail(f"{a} の後 {span} 文字以内に {b} が無い")

        elif kind == "forbid-regex":
            pat = " ".join(args)
            try:
                hit = re.search(pat, html)
            except re.error as e:
                fail(f"正規表現が壊れている（検査が無効になる）: {e}")
                hit = None
            if hit:
                fail("禁止に一致した: …" + html[max(0, hit.start() - 30):hit.end() + 30].replace("\n", " ") + "…")

        elif kind == "forbid-in-hero":
            want = " ".join(args)
            if not hero:
                fail('hero 区画（class="hero" の header）が見つからない')
            elif norm(want) in norm(plain_text(hero)):
                fail("ヒーローの中に現れている")

        elif kind in ("require-file-contains", "forbid-file-contains") and len(args) >= 2:
            fname, want = args[0], " ".join(args[1:])
            sib = html_path.parent / fname
            if not sib.exists():
                fail(f"{fname} が無い")
            else:
                body = sib.read_text(encoding="utf-8", errors="replace")
                if kind == "require-file-contains" and want not in body:
                    fail(f"{fname} に「{want}」が無い")
                if kind == "forbid-file-contains" and want in body:
                    fail(f"{fname} に「{want}」が残っている")

        elif kind in ("brief", "canonical"):
            passed += 1  # 宣言。--canonical-audit が使う

        elif kind == "require-spec-meta":
            meta = spec_meta(spec_path)
            missing = [k for k in META_KEYS if not meta.get(k)]
            if missing:
                fail("正本の冒頭メタが足りない: " + ", ".join(missing)
                     + "（改訂の手続きが追えないと、古い正本を忠実に実装して品質が下がる）")
            elif meta.get("canonical") not in ("yes", "no", "pending"):
                fail(f"canonical が yes/no/pending でない: {meta.get('canonical')}")

        elif kind == "invariant-coverage":
            ids = invariant_ids(spec_path)
            body = spec_path.read_text(encoding="utf-8")
            block = SPEC_BLOCK.search(body)
            spec_text = block.group(1) if block else ""
            missing = [i for i in ids if i not in spec_text]
            notes.append(f"[L{line_no}] invariant-coverage: 不変条件 {len(ids)} 件を照合した")
            if not ids:
                fail("不変条件の表（| I-1 | … |）が本文に無い")
            elif missing:
                fail("本文にあるが spec に規則が無い不変条件: " + ", ".join(missing)
                     + "（本文だけ直して規則を書き忘れた状態）")

        elif kind == "forbid-stale-copy" and args:
            # 今日3回起きた事故: 同じ頁の複製が別の場所に残り、古いまま公開経路に載る。
            # 文言ではなくソース全体で比べる（同じ文言の別意匠を誤検出しないため）
            import difflib
            def flat(t: str) -> str:
                return re.sub(r"\s+", " ", t)
            me = flat(raw)
            hits = []
            for other in sorted(Path().glob(args[0])):
                if other.resolve() == html_path.resolve():
                    continue
                if "_archive" in other.parts:   # アーカイブは意図した複製
                    continue
                try:
                    o = flat(other.read_text(encoding="utf-8", errors="replace"))
                except OSError:
                    continue
                if len(o) < 400:
                    continue
                # quick_ratio は文字の出現数だけを見るため、**同じ文言の別意匠**を
                # 誤検出する（実測: 別案 0.92-0.93 / 古い複製 0.97 で区別できない）。
                # 順序を見る ratio なら分離する。
                # ただし**別案の上限は測る対象で変わる。** 山吹案から見た他案は 0.06-0.41 だが、
                # output 配下を総当たりすると別案どうしが最大 0.804（lp-a <> lp-b が 0.798）。
                # 複製は 0.958 なので閾値 0.90 の余裕は 0.096。
                # **別案の上限が 0.85 を超えたら閾値を見直す**（f7 の実測 v6.3）
                if difflib.SequenceMatcher(None, me, o).quick_ratio() < 0.70:
                    continue
                ratio = difflib.SequenceMatcher(None, me, o).ratio()
                if ratio >= 0.90:
                    state = "バイト同一" if o == me else "**差分あり（古い複製）**"
                    hits.append(f"{other.as_posix()} 類似{ratio:.0%} {state}")
            notes.append(f"[L{line_no}] forbid-stale-copy: {args[0]} を走査した")
            if hits:
                fail("同じ頁の複製がある（公開経路に古い版が載る）: " + " / ".join(hits[:4]))

        elif kind == "max-animation-ms" and args:
            cap = float(args[0])
            seen, over = 0, []
            for decl in re.findall(r"animation(?:-duration)?\s*:\s*([^;}]+)", css):
                for t in re.findall(r"(\d*\.?\d+)\s*(ms|s)\b", decl):
                    seen += 1
                    ms = float(t[0]) if t[1] == "ms" else float(t[0]) * 1000
                    if ms > cap:
                        over.append(f"{decl.strip()[:34]} = {ms:.0f}ms")
            notes.append(f"[L{line_no}] max-animation-ms: 時間値 {seen} 件を測った")
            if over:
                fail(f"{cap:.0f}ms 超: " + " / ".join(over[:3]))

        elif kind == "min-tap-px" and args:
            need = float(args[0])
            seen, bad = 0, []
            for rule in re.finditer(r"([^{}]+)\{([^}]*)\}", css):
                sel, decls = rule.group(1), rule.group(2)
                if not (selector_tokens(sel) & TAP_TOKENS):
                    continue
                mh = re.search(r"min-height\s*:\s*(\d*\.?\d+)px", decls)
                if not mh:
                    continue
                seen += 1
                if float(mh.group(1)) < need:
                    bad.append(f"{sel.strip()[:30]} = {mh.group(1)}px")
            notes.append(f"[L{line_no}] min-tap-px: 操作要素の min-height {seen} 件を測った")
            if seen == 0:
                fail("操作要素に min-height の宣言が1件も無い（検査できていない＝通ったことにしない）")
            if bad:
                fail(f"{need:.0f}px 未満: " + " / ".join(bad[:3]))

        else:
            fail(f"未知の規則（タイプミスで検査が無効になる）: {kind}")

        if problems:
            for msg in problems:
                fails.append(f"[L{line_no}] {label}\n        → {msg}")
        elif kind != "target":
            passed += 1

    print(f"=== {html_path.name} ← {spec_path.name} ===")
    print(f"  規則 {len(rules)} 件のうち PASS {passed} 件 / FAIL {len(fails)} 件")
    for n in notes:
        print(f"  [計測 ] {n}")
    for f in fails:
        print(f"  [FAIL ] {f}")
    if not fails:
        print("  正本どおり。意匠の逸脱は無い。")
    else:
        print("\n  **直すのは実装の側。** 意匠を変えるなら DESIGN.md を先に書き換える。")
    return 1 if fails else 0


def canonical_audit(root: Path = Path("output")) -> int:
    """案件ごとに「公開してよい案」が1つに絞られているかを見る.

    2026-08-27 の事故: 同じ文言・同じ応募URLを持つ案が3つ並び、
    そのうち古い複製が公開経路（deploy/）に残っていた。
    **応募自体は成功するので、間違った案を配信しても気づけない。**
    """
    rows = []
    for spec in sorted(root.glob("*/DESIGN.md")):
        try:
            rules = load_rules(spec)
        except ValueError as e:
            print(f"[FAIL ] {e}")
            return 1
        meta = spec_meta(spec)
        rows.append({
            "dir": spec.parent,
            "brief": meta.get("brief") or declared(rules, "brief") or "(未宣言)",
            "canonical": meta.get("canonical") or declared(rules, "canonical") or "(未宣言)",
            "owner": meta.get("owner") or "(未宣言)",
            "revision": meta.get("revision") or "-",
            "deploy": (spec.parent / "netlify.toml").exists(),
        })

    if not rows:
        print("[SKIP ] output/*/DESIGN.md が無い")
        return 0

    print("=== 公開候補の点検（案件ごとに canonical は1つ） ===")
    for r in rows:
        print(f"  {r['dir'].as_posix():<34} canonical={r['canonical']:<8} "
              f"deploy設定={'あり' if r['deploy'] else 'なし'}  brief={r['brief']}  owner={r['owner']}")

    fails = []
    briefs = {}
    for r in rows:
        briefs.setdefault(r["brief"], []).append(r)
    for brief, group in briefs.items():
        yes = [g for g in group if g["canonical"] == "yes"]
        deploys = [g for g in group if g["deploy"]]
        if len(yes) > 1:
            fails.append(f"{brief}: canonical=yes が {len(yes)} 件（" +
                         ", ".join(g["dir"].name for g in yes) + "）。公開してよい案は1つ")
        if len(deploys) > 1:
            fails.append(f"{brief}: 公開設定（netlify.toml）を持つ案が {len(deploys)} 件。"
                         "どれを配信するか機械が決められない")
        for g in group:
            if g["canonical"] == "no" and g["deploy"]:
                fails.append(f"{g['dir'].as_posix()}: canonical=no なのに公開設定がある")
        if not yes and all(g["canonical"] == "pending" for g in group):
            print(f"  [HOLD ] {brief}: どの案を公開するか未決（施主の判断待ち）。"
                  "公開設定を持つ案は1つに保たれている" if len(deploys) <= 1 else "")

    for f in fails:
        print(f"  [FAIL ] {f}")
    print(f"\nFAIL: {len(fails)} 件 / 案 {len(rows)} 件")
    return 1 if fails else 0


def duplicate_audit(root: Path = Path("output"), threshold: float = 0.90) -> int:
    """DESIGN.md の有無に関係なく、output 配下の頁どうしの複製を探す.

    `forbid-stale-copy` は正本を持つ案件の頁しか見ない。
    **正本を持たない案（比較用の A/B/C など）は網の外にいた**（lp-factory-f7 の指摘 v6.3）。
    案間距離のゲートは章の識別子が無いと FAIL を出せないため、そこも当てにできない。

    判定はソース全体の順序つき比較。実測（output 配下 9件・36ペアの総当たり）:
      本物の別案 **最大 0.804**（lp-a <> lp-b が 0.798）/ 古い複製 **0.958**。
      閾値 0.90 の余裕は **0.096**。`quick_ratio` では 0.92-0.93 対 0.97 で分離しない。
      **別案の上限が 0.85 を超えたら閾値を見直す。**
    """
    import difflib

    def flat(t: str) -> str:
        return re.sub(r"\s+", " ", t)

    files = [f for f in sorted(root.rglob("*.html"))
             if "_archive" not in f.parts and f.name != "404.html"]
    texts = {}
    for f in files:
        try:
            t = flat(f.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        if len(t) >= 400:
            texts[f] = t

    print(f"=== 頁どうしの複製の点検（{len(texts)} 件・閾値 {threshold:.2f}） ===")
    hits = []
    keys = list(texts)
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            if difflib.SequenceMatcher(None, texts[a], texts[b]).quick_ratio() < 0.70:
                continue
            r = difflib.SequenceMatcher(None, texts[a], texts[b]).ratio()
            if r >= threshold:
                state = "バイト同一" if texts[a] == texts[b] else "**差分あり（古い複製）**"
                hits.append(f"{a.as_posix()} <> {b.as_posix()} 類似{r:.0%} {state}")
    for h in hits:
        print(f"  [FAIL ] {h}")
    if not hits:
        print("  複製は無い。")
    print(f"\nFAIL: {len(hits)} 件")
    return 1 if hits else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="意匠の正本（DESIGN.md）と実装の照合")
    ap.add_argument("html", nargs="*", type=Path)
    ap.add_argument("--spec", type=Path, help="既定は HTML と同じディレクトリの DESIGN.md")
    ap.add_argument("--canonical-audit", action="store_true",
                    help="output/*/DESIGN.md を横断して、公開してよい案が1つかを見る")
    ap.add_argument("--duplicate-audit", action="store_true",
                    help="output 配下の頁どうしの複製を探す（正本の有無に関係なく走る）")
    args = ap.parse_args()

    if args.duplicate_audit:
        return duplicate_audit()
    if args.canonical_audit:
        return canonical_audit()
    if not args.html:
        ap.error("検査する HTML を指定するか --canonical-audit を使う")

    rc, checked = 0, 0
    for path in args.html:
        files = sorted(path.glob("*.html")) if path.is_dir() else [path]
        for html in files:
            spec = args.spec or html.parent / "DESIGN.md"
            if not spec.exists():
                print(f"[FAIL ] {html}: 意匠の正本 {spec} が無い（正本の不在は合格にしない）")
                rc = 1
                continue
            try:
                rules = load_rules(spec)
            except ValueError as e:
                print(f"[FAIL ] {e}")
                rc = 1
                continue
            if not rules:
                print(f"[FAIL ] {spec}: 規則が0件（空の正本は合格にしない）")
                rc = 1
                continue
            declared = targets_of(rules)
            if not declared:
                print(f"[FAIL ] {spec}: target 宣言が無い（どのファイルを支配するのか不明）")
                rc = 1
                continue
            if html.name not in declared:
                # ディレクトリ指定なら黙って飛ばし、直接指定なら誤った当て方として落とす
                if path.is_dir():
                    print(f"[SKIP ] {html.name}: {spec.name} の target ではない（{', '.join(declared)}）")
                else:
                    print(f"[FAIL ] {html.name} は {spec.name} の target ではない（{', '.join(declared)}）")
                    rc = 1
                continue
            rc |= check(html, spec, rules)
            checked += 1

    if checked == 0:
        print("[FAIL ] 検査した対象が0件（当て方が間違っている。合格にしない）")
        rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
