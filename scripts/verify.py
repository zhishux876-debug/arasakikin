#!/usr/bin/env python3
"""LP 実機検証スクリプト.

使い方:
    python3 scripts/verify.py output/案件名/          # ディレクトリ内の全HTMLを検証
    python3 scripts/verify.py a.html b.html           # ファイル指定
    python3 scripts/verify.py --diagnose a.html       # 横スクロールの原因要素を列挙
    python3 scripts/verify.py output/案件名/ --json    # JSON で出力

    # ブリーフの [FIX] 文言がレンダリング結果に一字一句あるか照合する（v2.2）
    python3 scripts/verify.py output/案件名/ --fixed briefs/案件名.md

    # ドット絵アイコン規約をチェックする（pixel / win95 / gameui / terminal / y2k）
    python3 scripts/verify.py output/案件名/ --pixel-icons

全項目 PASS なら終了コード 0、1件でも FAIL があれば 1 を返す。
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Windows の日本語コンソール(cp932)で日本語を print すると落ちるため、UTF-8 に切り替える
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit("playwright が入っていません:  pip install playwright && playwright install chromium")

WIDTHS = [320, 375, 414]
PLACEHOLDER_PAT = re.compile(
    r"TODO[-_ ]?REPLACE|FORM_URL_HERE|#TODO|TODO:|XXX_|__[A-Z_]{4,}__", re.I
)
EXTERNAL_PAT = re.compile(
    r"""(?:src|href)\s*=\s*["'](https?://[^"']+)|url\(\s*["']?(https?://[^"')]+)""", re.I
)
# v2: 外部依存は許可リスト方式。Webフォントは許可する
ALLOWED_HOSTS = ("fonts.googleapis.com", "fonts.gstatic.com", "cdnjs.cloudflare.com")
STORAGE_PAT = re.compile(r"\b(?:local|session)Storage\b")

# v2.2: ブリーフの確定文言。行内の [FIX] 以降を1件として拾う。
# バッククォートで囲まれた `[FIX]`（記法の説明文）は拾わない
FIX_PAT = re.compile(r"(?<!`)\[FIX\](?!`)\s*(.+?)\s*$", re.M)
# 未記入のまま残っているプレースホルダは照合対象から外す
FIX_SKIP_PAT = re.compile(r"\{\{|｛｛|［要提供］|\[要提供\]|^[-—―…\s]*$")


def norm(s):
    """照合用の正規化: 空白と、改行位置指定の半角スラッシュを落とす."""
    return re.sub(r"[\s/]+", "", s)


def load_fixed(brief_path):
    """ブリーフから [FIX] 文言を抽出する."""
    src = Path(brief_path).read_text(encoding="utf-8", errors="replace")
    out = []
    for m in FIX_PAT.finditer(src):
        t = m.group(1).strip()
        # 行頭の記法ノイズと、Markdown の強調記号を除く
        t = re.sub(r"^[…\-–—:：]+\s*", "", t).strip("*`　 ")
        if not t or FIX_SKIP_PAT.search(t):
            continue
        out.append(t)
    return out


def collect(paths):
    files = []
    for p in paths:
        path = Path(p)
        if path.is_dir():
            files.extend(sorted(path.glob("*.html")))
        elif path.is_file():
            files.append(path)
    return files


def static_checks(path):
    """ブラウザを使わない、ソース上のチェック."""
    src = path.read_text(encoding="utf-8", errors="replace")
    out = {}

    # 外部リソース: <link href> と url() のみを見る。<a href> のリンク先は対象外
    urls = []
    for m in EXTERNAL_PAT.finditer(src):
        u = m.group(1) or m.group(2)
        if not u:
            continue
        # <a href="..."> は除外（CTAリンクは外部で当然）
        head = src[max(0, m.start() - 60):m.start()]
        if re.search(r"<a\b[^>]*$", head, re.I):
            continue
        urls.append(u)
    disallowed = [u for u in urls if not any(h in u for h in ALLOWED_HOSTS)]
    out["外部リソース参照"] = (
        len(disallowed) == 0,
        "OK（許可ドメインのみ）" if not disallowed else f"{len(disallowed)}件: " + ", ".join(disallowed[:2]),
    )

    # v2: Webフォントを使っているか（システムフォント任せは質が出ない）
    has_webfont = ("fonts.googleapis.com" in src) or ("@font-face" in src)
    out["Webフォント"] = (has_webfont, "使用" if has_webfont else "未使用（システムフォント任せ）")

    storage = STORAGE_PAT.findall(src)
    out["ストレージAPI"] = (len(storage) == 0, f"{len(storage)}件")

    todos = PLACEHOLDER_PAT.findall(src)
    out["未差し替えプレースホルダ"] = (len(todos) == 0, f"{len(todos)}件")

    return out


SCROLL_THROUGH_JS = """async()=>{
    const step = Math.max(200, window.innerHeight * 0.8);
    for (let y = 0; y < document.body.scrollHeight; y += step) {
        window.scrollTo(0, y);
        await new Promise(r => setTimeout(r, 80));
    }
    window.scrollTo(0, 0);
    await new Promise(r => setTimeout(r, 250));
}"""

# ページを最後まで送っても読めないままのテキストを探す。
# IntersectionObserver 依存の出現演出が発火しないと、ここに引っかかる
#
# 2周方式にしている理由（v5.5）:
# スクロール駆動の出現（`animation-timeline: view()`）は進行が**位置**で決まるため、
# 末尾まで送って y=0 へ戻すと、画面外の要素は opacity:0 へ**戻る**。
# 1周目の位置だけで判定すると、位置駆動を使った案が必ず FAIL する（誤検出）。
# 読者はその要素が画面に入ったときに読むのだから、**画面内へ入れてから測り直す**。
# それでも 0 のままなら、本当に読めない（IO が発火しない・打ち消し忘れ）。
# v6.1: 器より内容が広い要素（overflow:hidden / clip の裏で切れている文字）を拾う。
# 折り返せる器（overflow-x:auto/scroll）と、意図的に画面外へ出す装飾は対象にしない。
CLIPPED_TEXT_JS = r"""() => {
  const out = [];
  const seen = new Set();
  document.querySelectorAll('body *').forEach(el => {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') return;
    if (cs.overflowX === 'auto' || cs.overflowX === 'scroll') return;
    if (parseFloat(cs.opacity) === 0) return;
    // 自分が持つ文字だけを見る（親の入れ子で同じ文字を二重に数えない）
    const own = [...el.childNodes].filter(n => n.nodeType === 3)
                 .map(n => n.textContent.trim()).join('');
    if (own.length < 2) return;
    // 視覚非表示（sr-only 系）は読み上げ用なので除く
    if (el.clientWidth <= 1 || el.clientHeight <= 1) return;
    const over = el.scrollWidth - el.clientWidth;
    if (over <= 1) return;
    // 器のどれかが overflow を隠しているときだけ「切れている」と言える
    let hidden = false;
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      const c = getComputedStyle(n).overflowX;
      if (c === 'hidden' || c === 'clip') { hidden = true; break; }
    }
    if (!hidden) return;
    const key = own.slice(0, 12) + over;
    if (seen.has(key)) return;
    seen.add(key);
    out.push(`${over}px 切れ「${own.slice(0, 14)}」`);
  });
  return out.slice(0, 6);
}"""

HIDDEN_TEXT_JS = r"""async()=>{
    function effOpacity(el){
        let o = 1, n = el;
        while (n && n.nodeType === 1) {
            const c = getComputedStyle(n);
            // display:none / visibility:hidden は意図的な非表示（sr-only 等）とみなして対象外
            if (c.display === 'none' || c.visibility === 'hidden') return -1;
            o *= parseFloat(c.opacity);
            n = n.parentElement;
        }
        return o;
    }
    // SVG の <title> / <desc> は描画されない。読み上げのための名前なので、
    // 「サイズ0の読めないテキスト」ではない。ここを除かないと、
    // アクセシブルな SVG を書くほど FAIL が増える（interface_lint とは逆向きの圧力になる）
    const SKIP = new Set(['title','desc','metadata','script','style']);
    const cand = [];
    document.querySelectorAll('body *').forEach(el => {
        const tag = (el.tagName || '').toLowerCase();
        if (SKIP.has(tag)) return;
        if (el.closest && el.closest('svg') && (tag === 'title' || tag === 'desc')) return;
        const own = [...el.childNodes].filter(n => n.nodeType === 3)
                     .map(n => n.textContent.trim()).join('');
        if (own.length < 2) return;
        const o = effOpacity(el);
        if (o < 0) return;
        const r = el.getBoundingClientRect();
        if (o === 0 || r.width === 0 || r.height === 0) cand.push({el, own});
    });
    // 2周目: 疑わしい要素だけを画面中央へ入れて測り直す。
    // 上限を付けるのは、候補が数百件ある壊れた頁で撮影が終わらなくなるのを防ぐため
    const suspect = [];
    for (const c of cand.slice(0, 60)) {
        try { c.el.scrollIntoView({block: 'center', behavior: 'instant'}); } catch (e) {}
        await new Promise(r => requestAnimationFrame(() => setTimeout(r, 180)));
        const o = effOpacity(c.el);
        if (o < 0) continue;
        const r2 = c.el.getBoundingClientRect();
        if (o === 0) suspect.push({el: c.el, own: c.own, why: 'opacity:0'});
        else if (r2.width === 0 || r2.height === 0) suspect.push({el: c.el, own: c.own, why: 'サイズ0'});
    }
    // 3周目: **画面に固定された要素は「要素を画面へ入れる」では状態が変わらない。**
    // position:fixed の追従要素は scrollIntoView が効かず、出現の条件は
    // 「ページのスクロール位置」そのものになる。位置を数か所へ送って測り直さないと、
    // スクロールで現れる追従CTAが「隠れたままのテキスト」に化ける（2026-08-28）。
    // どの位置でも隠れたままなら、それは本当に読めないテキスト
    const bad = [];
    const span = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
    for (const s of suspect.slice(0, 12)) {
        let shown = false;
        for (const f of [0, 0.25, 0.5, 0.75, 1]) {
            window.scrollTo(0, Math.round(span * f));
            await new Promise(r => requestAnimationFrame(() => setTimeout(r, 160)));
            const o = effOpacity(s.el);
            if (o < 0) { shown = true; break; }   // 意図的な非表示（sr-only 等）
            const r3 = s.el.getBoundingClientRect();
            if (o > 0 && r3.width > 0 && r3.height > 0) { shown = true; break; }
        }
        if (!shown) bad.push(s.why + ' → ' + s.own.slice(0, 20));
    }
    window.scrollTo(0, 0);
    if (cand.length > 60) bad.push('候補が60件を超えたため以降は未検査（' + cand.length + '件）');
    if (suspect.length > 12) bad.push('隠れた候補が多いため一部未検査（' + suspect.length + '件）');
    return [...new Set(bad)].slice(0, 5);
}"""

# v2.3: prefers-reduced-motion 有効時に CSS アニメーションが止まっているか。
# transition は色変化などの小さなフィードバックにも使われるため対象外にし、
# @keyframes による animation（出現演出・ループ演出）だけを見る
REDUCED_MOTION_JS = r"""()=>{
    const bad = [];
    document.querySelectorAll('body *').forEach(el=>{
        const cs = getComputedStyle(el);
        if (cs.animationName && cs.animationName !== 'none') {
            const dur = parseFloat(cs.animationDuration) || 0;
            const paused = cs.animationPlayState === 'paused';
            if (dur > 0.05 && !paused) {
                bad.push((el.tagName || '').toLowerCase() + '.' +
                         (el.className || '').toString().slice(0, 30) +
                         ': animation=' + cs.animationName + ' ' + cs.animationDuration);
            }
        }
    });
    return [...new Set(bad)].slice(0, 5);
}"""

# ドット絵アイコン規約（pixel / win95 / gameui / terminal / y2k）
PIXEL_ICON_JS = r"""()=>{
    const bad = [];
    const syms = [...document.querySelectorAll('symbol')];
    if (!syms.length) bad.push('symbol が1つも無い（SVGスプライト未定義）');
    syms.forEach(s => {
        const id = s.id || '(id なし)';
        if (s.getAttribute('viewBox') !== '0 0 16 16')
            bad.push(id + ': viewBox=' + s.getAttribute('viewBox'));
        if (s.getAttribute('shape-rendering') !== 'crispEdges')
            bad.push(id + ': shape-rendering="crispEdges" なし');
        s.querySelectorAll('*').forEach(el => {
            const tn = el.tagName.toLowerCase();
            if (tn === 'circle' || tn === 'ellipse') bad.push(id + ': <' + tn + '> を使用');
            for (const a of el.attributes) {
                if (/\d+\.\d+/.test(a.value)) bad.push(id + ': 小数座標 ' + a.name + '="' + a.value + '"');
                if (a.name === 'd' && /[CcSsAaQqTt]/.test(a.value)) bad.push(id + ': 曲線コマンド');
                if (a.name === 'stroke') bad.push(id + ': stroke を使用（面で描く）');
            }
        });
    });
    const emoji = document.body.innerText.match(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/gu) || [];
    if (emoji.length) bad.push('絵文字 ' + emoji.length + '件: ' + emoji.slice(0, 3).join(''));
    return [...new Set(bad)].slice(0, 8);
}"""


def browser_checks(page, path, fixed=None, pixel_icons=False, browser=None):
    out = {}
    errors = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))

    scrolls = {}
    clipped: list[str] = []
    for w in WIDTHS:
        page.set_viewport_size({"width": w, "height": 800})
        page.goto(path.resolve().as_uri(), wait_until="networkidle")
        page.wait_for_timeout(400)
        x = page.evaluate(
            "()=>{window.scrollTo(9999,0);const x=window.scrollX;window.scrollTo(0,0);return x;}"
        )
        scrolls[w] = x
        # v6.1: 横スクロールが 0 でも、overflow:hidden / clip の裏で文字が切れていることがある。
        # 実測で見つけた例: 320px で「このままでいいのだろうか。」の閉じ括弧が 8px 切れていた
        # （禁則で行が折れず、親の overflow:hidden に飲まれていた）。
        for hit in page.evaluate(CLIPPED_TEXT_JS):
            clipped.append(f"{w}px {hit}")

    bad = {w: x for w, x in scrolls.items() if x > 0}
    out["横スクロール"] = (
        not bad,
        "OK" if not bad else ", ".join(f"{w}px:{x}px超過" for w, x in bad.items()),
    )
    out["器より広い内容"] = (
        not clipped,
        "OK" if not clipped else "; ".join(clipped[:3]),
    )
    out["コンソールエラー"] = (len(errors) == 0, f"{len(errors)}件")

    meta = page.evaluate(
        """()=>({
        lang: document.documentElement.lang || '',
        title: (document.title||'').trim(),
        desc: (document.querySelector('meta[name="description"]')||{}).content || '',
        ogt: !!document.querySelector('meta[property="og:title"]'),
        ogd: !!document.querySelector('meta[property="og:description"]'),
        h1: document.querySelectorAll('h1').length,
    })"""
    )
    out["lang属性"] = (meta["lang"].startswith("ja"), meta["lang"] or "なし")
    out["title"] = (bool(meta["title"]), meta["title"][:24] or "なし")
    title_len = len(meta["title"])
    out["title文字数"] = (
        0 < title_len <= 40,
        f"{title_len}字" + ("（0字）" if title_len == 0 else "（40字超・検索結果で切れる想定）" if title_len > 40 else ""),
    )
    out["description"] = (bool(meta["desc"]), "あり" if meta["desc"] else "なし")
    desc_len = len(meta["desc"])
    out["description文字数"] = (
        0 < desc_len <= 160,
        f"{desc_len}字" + ("（0字）" if desc_len == 0 else "（160字超・検索結果で切れる想定）" if desc_len > 160 else ""),
    )
    out["OGPメタ"] = (meta["ogt"] and meta["ogd"], "あり" if meta["ogt"] and meta["ogd"] else "なし")
    out["h1が1つ"] = (meta["h1"] == 1, f"{meta['h1']}個")

    page.set_viewport_size({"width": 375, "height": 800})
    page.goto(path.resolve().as_uri(), wait_until="networkidle")
    page.wait_for_timeout(600)

    # v2.2: 以降のチェックの前に、一度ページを最後まで送る。
    # スクロールインで出現する演出を発火させるため（「隠れたままのテキスト」の判定に必要）
    page.evaluate(SCROLL_THROUGH_JS)

    # 画像チェック（v2.1 / 読み込み判定を v2.2 で修正）
    # loading="lazy" の画像は、プログラムによる高速スクロールでは Chrome が
    # 読み込みを開始しないことがある。「画像が読めるか」を判定したいので、
    # 一度 eager に倒して実際に読み込ませてから見る
    imgs = page.evaluate(
        """async()=>{
        const list=[...document.images];
        list.forEach(i=>{ if(i.loading==='lazy') i.loading='eager'; });
        await Promise.all(list.map(i=> i.complete ? null : new Promise(res=>{
          i.addEventListener('load',res,{once:true});
          i.addEventListener('error',res,{once:true});
          setTimeout(res,3000);
        })));
        const out=[];
        document.querySelectorAll('img').forEach(el=>{
          out.push({
            src: (el.getAttribute('src')||'').slice(0,60),
            loaded: el.complete && el.naturalWidth > 0,
            hasAlt: el.hasAttribute('alt'),
            decorative: el.getAttribute('alt') === '' ,
            hasDim: el.hasAttribute('width') && el.hasAttribute('height'),
            natural: el.naturalWidth + 'x' + el.naturalHeight,
            rendered: Math.round(el.getBoundingClientRect().width) + 'x' + Math.round(el.getBoundingClientRect().height),
            lazy: el.getAttribute('loading') === 'lazy',
          });
        });
        return out;}"""
    )
    if imgs:
        broken = [i for i in imgs if not i["loaded"]]
        out["画像の読み込み"] = (not broken, "OK" if not broken else
                            f"{len(broken)}件が読めない: " + ", ".join(i["src"] for i in broken[:2]))
        noalt = [i for i in imgs if not i["hasAlt"]]
        out["alt属性"] = (not noalt, "OK" if not noalt else f"{len(noalt)}件に alt が無い")
        nodim = [i for i in imgs if not i["hasDim"]]
        out["width/height属性"] = (not nodim, "OK" if not nodim else
                              f"{len(nodim)}件に未指定（レイアウトシフトの原因）")
        out["画像枚数"] = (True, f"{len(imgs)}枚")

    small = page.evaluate(
        """()=>{const bad=[];
        document.querySelectorAll('a,button').forEach(el=>{
          const r=el.getBoundingClientRect();
          const cs=getComputedStyle(el);
          if(cs.display==='none'||cs.visibility==='hidden'||r.height===0) return;
          if(cs.display==='inline') return;              // 本文中のインラインリンクは対象外
          if(r.height<44) bad.push((el.textContent||'').trim().slice(0,20)+' ('+Math.round(r.height)+'px)');
        });
        return bad.slice(0,5);}"""
    )
    out["タップ領域44px"] = (len(small) == 0, "OK" if not small else "; ".join(small))

    # v2.2: 読めないままのテキストが残っていないか（既にページ末尾まで送ってある）
    stuck = page.evaluate(HIDDEN_TEXT_JS)
    out["隠れたままのテキスト"] = (
        len(stuck) == 0,
        "OK" if not stuck else "; ".join(stuck),
    )

    # v2.2: 確定コピー（ブリーフの [FIX]）の一字一句照合
    if fixed:
        rendered = norm(page.evaluate("()=>document.body.innerText"))
        missing = [s for s in fixed if norm(s) not in rendered]
        out["確定コピー照合"] = (
            not missing,
            f"{len(fixed)}件すべて一致" if not missing
            else f"{len(missing)}/{len(fixed)}件が不一致: " + " / ".join(m[:18] for m in missing[:3]),
        )

    # v2.2: ドット絵アイコン規約
    if pixel_icons:
        viol = page.evaluate(PIXEL_ICON_JS)
        out["ドット絵アイコン規約"] = (len(viol) == 0, "OK" if not viol else "; ".join(viol))

    # v2.3: prefers-reduced-motion 時にアニメーションが止まっているか。
    # 専用コンテキストで開き直して確認する（既存 page の設定は変えない）
    if browser is not None:
        rm_ctx = browser.new_context(
            viewport={"width": 375, "height": 800}, reduced_motion="reduce"
        )
        rm_page = rm_ctx.new_page()
        rm_page.goto(path.resolve().as_uri(), wait_until="networkidle")
        rm_page.wait_for_timeout(500)
        still = rm_page.evaluate(REDUCED_MOTION_JS)
        out["reduced-motion時の停止"] = (
            len(still) == 0, "OK" if not still else "; ".join(still)
        )
        rm_ctx.close()

    return out


def diagnose(path):
    """横スクロールの原因になっている要素を列挙する."""
    with sync_playwright() as p:
        b = p.chromium.launch()
        for w in WIDTHS:
            pg = b.new_page(viewport={"width": w, "height": 800})
            pg.goto(path.resolve().as_uri(), wait_until="networkidle")
            pg.wait_for_timeout(500)
            x = pg.evaluate(
                "()=>{window.scrollTo(9999,0);const x=window.scrollX;window.scrollTo(0,0);return x;}"
            )
            if x == 0:
                print(f"[{w}px] 横スクロールなし")
                pg.close()
                continue
            print(f"[{w}px] {x}px の横スクロール。原因候補:")
            bad = pg.evaluate(
                """(vw)=>{const out=[];
                document.querySelectorAll('*').forEach(el=>{
                  const cs=getComputedStyle(el);
                  const over = el.offsetWidth>vw+1 || el.getBoundingClientRect().right>vw+1;
                  if(!over) return;
                  let par=el.parentElement, clipped=false;
                  while(par){const pc=getComputedStyle(par);
                    if(pc.overflowX!=='visible'||pc.overflow!=='visible'){clipped=true;break;}
                    par=par.parentElement;}
                  if(clipped) return;
                  out.push({tag:el.tagName, cls:(el.className||'').toString().slice(0,40),
                            w:el.offsetWidth, right:Math.round(el.getBoundingClientRect().right),
                            pos:cs.position, nowrap:cs.whiteSpace, minw:cs.minWidth});
                });
                return out.slice(0,12);}""",
                w,
            )
            for o in bad:
                print("   ", o)
            if not bad:
                print("    (clip されていない要素は見つからず。祖先の position/overflow の"
                      "組み合わせを疑う。特に position:absolute の親に position:relative があるか)")
            pg.close()
        b.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--diagnose", action="store_true", help="横スクロールの原因要素を列挙")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--fixed", metavar="BRIEF",
                    help="ブリーフの [FIX] 文言がレンダリング結果に一字一句あるか照合する")
    ap.add_argument("--pixel-icons", action="store_true",
                    help="ドット絵アイコン規約をチェックする（pixel / win95 / gameui / terminal / y2k）")
    args = ap.parse_args()

    files = collect(args.paths)
    if not files:
        sys.exit("HTMLファイルが見つかりません")

    if args.diagnose:
        for f in files:
            print(f"\n=== {f.name} ===")
            diagnose(f)
        return

    fixed = None
    if args.fixed:
        fixed = load_fixed(args.fixed)
        if not fixed:
            print(f"注意: {args.fixed} に [FIX] の印が1つも無い。確定コピー照合は行われない。\n"
                  f"      先に /lp-brief で確定文言に [FIX] を付ける（記法は CLAUDE.md）")
        else:
            print(f"確定コピー {len(fixed)}件を {args.fixed} から読み込んだ")

    results = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        for f in files:
            pg = b.new_page(viewport={"width": 375, "height": 800})
            res = static_checks(f)
            res.update(browser_checks(pg, f, fixed=fixed, pixel_icons=args.pixel_icons, browser=b))
            results[f.name] = res
            pg.close()
        b.close()

    if args.json:
        print(json.dumps({k: {n: {"pass": v[0], "detail": v[1]} for n, v in r.items()}
                          for k, r in results.items()}, ensure_ascii=False, indent=2))
    else:
        for name, res in results.items():
            print(f"\n=== {name} ===")
            for check, (ok, detail) in res.items():
                mark = "PASS" if ok else "FAIL"
                print(f"  [{mark}] {check:<24} {detail}")

    failed = sum(1 for r in results.values() for ok, _ in r.values() if not ok)
    print(f"\nFAIL: {failed} 件 / {len(files)} ファイル")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
