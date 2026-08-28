"""公開する案を1つに解決し、配信用の _site/ を組み立てる。

**この道具は「どの案を公開するか」を決めない。** 決めるのは人間で、
その決定は `output/<案件名>/DESIGN.md` の `canonical: yes` として1箇所にだけ書かれる
（`CLAUDE.md` 2.6「公開してよい案は、案件で1つ」）。ここはその宣言を読むだけ。

    canonical: yes が 1件  → その案を _site/ へ組み立てて exit 0
    canonical: yes が 0件  → 何も作らず exit 2（未決。**公開しないのが正しい**）
    canonical: yes が 2件超 → exit 1（事故。design_spec_lint --canonical-audit と同じ判定）

Netlify の Git 連携でも GitHub Pages でも、同じ1本を使う:

    python scripts/publish_target.py --build _site

なぜディレクトリを固定で書かないか。固定で書くと、公開する案を変えるたびに
配信設定を書き換えることになり、**「決定の在りか」が DESIGN.md と設定ファイルの
2箇所に増える。** 2箇所あると必ず食い違い、古い案が配信される（2026-08-27 の事故）。
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import re
import shutil
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 配信するもの。DESIGN.md / README.md / shots / motion / review は**配信しない**
# （制作の記録であって、読者に配るものではない）
PUBLISH_FILES = ("index.html", "404.html", "robots.txt", "_headers", "_redirects")
PUBLISH_DIRS = ("assets",)

META = re.compile(r"(?mi)^[-*]?\s*(canonical|status|brief|owner|revision)\s*[:：]\s*(.+)$")


def spec_meta(path: Path) -> dict[str, str]:
    head = path.read_text(encoding="utf-8").split("---", 1)[0]
    out: dict[str, str] = {}
    for m in META.finditer(head):
        # 値のあとの説明（← … / # … / 全角空白以降）は落とす（design_spec_lint と同じ規則）
        out[m.group(1).lower()] = re.split(r"\s*(?:←|#|　)", m.group(2).strip())[0].strip()
    return out


def candidates(root: Path) -> list[tuple[Path, dict[str, str]]]:
    found = []
    for spec in sorted(root.glob("output/*/DESIGN.md")):
        found.append((spec.parent, spec_meta(spec)))
    return found


def resolve(root: Path) -> tuple[Path, dict[str, str]]:
    rows = candidates(root)
    if not rows:
        print("FAIL: output/*/DESIGN.md が1つも無い。意匠の正本が無い案は公開できない")
        raise SystemExit(1)

    print("=== 公開候補 ===")
    for d, m in rows:
        print(f"  {str(d):<44} canonical={m.get('canonical','(無し)'):<8} status={m.get('status','')}")

    yes = [(d, m) for d, m in rows if m.get("canonical") == "yes"]
    if len(yes) == 1:
        print(f"\n公開する案: {yes[0][0]}")
        return yes[0]
    if not yes:
        print("\nHOLD: canonical: yes の案が無い。**公開する案が未決**なので何も配信しない。\n"
              "      公開すると決めたら、その案の DESIGN.md に canonical: yes と書く\n"
              "      （採否は人間が単独で行う。この道具は決めない）")
        raise SystemExit(2)
    print(f"\nFAIL: canonical: yes が {len(yes)} 件ある。1つに絞るまで配信しない\n  "
          + "\n  ".join(str(d) for d, _ in yes))
    raise SystemExit(1)


def csp_for(html: str) -> str:
    """その案の実物から CSP を組む。

    インラインの <script> があればその sha256 を許可し、無ければ script-src 'none'。
    **手で書くと案を差し替えたときに食い違う**（DESIGN.md §7.5 が心配していた点）。
    """
    scripts = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.S)
    if scripts:
        hashes = " ".join(
            "'sha256-" + base64.b64encode(hashlib.sha256(s.encode("utf-8")).digest()).decode() + "'"
            for s in scripts
        )
        script_src = hashes
    else:
        script_src = "'none'"
    return (
        "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; "
        f"script-src {script_src}; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; img-src 'self' data:; "
        "connect-src 'none'; manifest-src 'self'"
    )


def write_headers(out: Path, html: str, noindex: bool) -> None:
    """Netlify の _headers を書く（publish ディレクトリに置けば効く）。

    **GitHub Pages はヘッダを設定できない。** Pages で配信するときは
    このファイルは無視され、noindex は robots.txt と <meta name="robots"> に頼ることになる。
    DEPLOY.md にその差を書いてある。
    """
    lines = ["/*"]
    if noindex:
        lines.append("  X-Robots-Tag: noindex, nofollow")
    lines += [
        "  X-Content-Type-Options: nosniff",
        "  X-Frame-Options: DENY",
        "  Referrer-Policy: strict-origin-when-cross-origin",
        "  Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=()",
        f"  Content-Security-Policy: {csp_for(html)}",
        "",
        "/*.html",
        "  Cache-Control: public, max-age=0, must-revalidate",
        "",
        "/assets/*",
        "  Cache-Control: public, max-age=31536000, immutable",
        "",
    ]
    (out / "_headers").write_text("\n".join(lines), encoding="utf-8")


def build(src: Path, out: Path, meta: dict[str, str]) -> None:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    copied = []
    for name in PUBLISH_FILES:
        f = src / name
        if f.exists():
            shutil.copy2(f, out / name)
            copied.append(name)
    for name in PUBLISH_DIRS:
        d = src / name
        if d.is_dir():
            shutil.copytree(d, out / name)
            copied.append(name + "/")

    if not (out / "index.html").exists():
        print(f"FAIL: {src} に index.html が無い")
        raise SystemExit(1)

    # **改行を変換せずに読む。** read_text() は CRLF を LF に潰すため、
    # そのまま sha256 を取ると「配信される中身」と1バイトずれ、CSP が全ブロックする
    html = (out / "index.html").read_bytes().decode("utf-8")

    # 施主が承認するまでは検索結果に出さない。承認は DESIGN.md の status に書かれる
    approved = "承認済" in meta.get("status", "")
    noindex = not approved
    write_headers(out, html, noindex)
    if noindex and not (out / "robots.txt").exists():
        # ヘッダを設定できない配信先（GitHub Pages）でも、これだけは効く
        (out / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
        copied.append("robots.txt（下書き用に生成）")

    print(f"\n配信物を {out} に組み立てた: " + ", ".join(copied) + ", _headers")
    print(f"  noindex: {'あり（status が承認済みでない）' if noindex else 'なし（施主承認済み）'}")
    print(f"  CSP    : {csp_for(html)[:90]}…")


def main() -> None:
    ap = argparse.ArgumentParser(description="公開する案を解決して配信物を組み立てる")
    ap.add_argument("--root", default=".", help="リポジトリの根（既定: カレント）")
    ap.add_argument("--build", metavar="DIR", help="配信物を組み立てる先。省略すると解決だけ")
    ap.add_argument("--github-output", metavar="FILE",
                    help="解決結果（target / brief）を GitHub Actions の出力ファイルへ書く")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    target, meta = resolve(root)

    if args.github_output:
        brief = meta.get("brief", "")
        # brief はリポジトリ根からの相対で書かれている（例 briefs/yaaac.md）。
        # 別セッションが退避すると消えることがあるので、実在を確かめてから渡す
        brief_ok = brief and (root / brief).exists()
        if brief and not brief_ok:
            print(f"注意: 正本 {brief} が見つからない。確定コピー照合は行われない")
        with open(args.github_output, "a", encoding="utf-8") as fh:
            fh.write(f"target={target.relative_to(root).as_posix()}\n")
            fh.write(f"brief={brief if brief_ok else ''}\n")

    if args.build:
        build(target, Path(args.build), meta)


if __name__ == "__main__":
    main()
