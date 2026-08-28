# DESIGN.md — YAAAC クラフト案（craft-rail）の意匠の正本

**この文書が意匠の正本です。** `index.html` と食い違ったら、**直すのは実装の側**。
意匠を変えたいときは、先にこの文書を書き換え、`design_spec_lint.py` を通してから実装する。

- revision: 11
- status: 施主承認待ち（公開判断は人間）
- owner: lp-factory-12（このディレクトリの所有者。触る前に確認する）
- updated: 2026-08-28
- brief: briefs/yaaac.md
- canonical: yes   ← 2026-08-28 施主が公開する案として選定（山吹案は no）
- 配信先（正）: **https://around30.yamanashifund.org/**（エックスサーバー・静的ファイル）。
  `<link rel="canonical">` と `og:url` でこのURLを名乗る。GitHub Pages は検査つきの組み立て場と控えとして残す
- 対象: `output/yaaac-stamp-dial-craft/index.html` ＋ `assets/`（主催ロゴ1点。**画像を持つので単一HTMLでは完結しない**。配置の前に `assets/MANIFEST.json` を読む）
- 文言の正本: `briefs/yaaac.md`（確定コピー60件。`verify.py --fixed` で機械照合）
- 方向: `design-directions.md` の `typographic` × `chic-muted`（クラフト紙の地に文字組み）
- 復活: `output/_archive/2026-08-27/yaaac-stamp-dial-craft/` から 2026-08-27 に戻した
- 最終実測日: 2026-08-28

> **これは山吹の案（`output/yaaac-stamp-dial/`）とは別の案。**
> 同じ文言・同じ応募先を持つが、意匠は独立している。**2案は混ぜない。**
> どちらを公開するかは施主が決める（`decisions.md` の Decision Authority）。

---

## 1. 一行で言うと

**クラフト紙の地に、墨の文字組みだけで立てる。** 左に巨大なキャッチ、右に細い罫線で
情報の帯（頭字語・日程・CTA）。図案を1つも置かず、**級数と余白と罫線だけで階層を作る。**

---

## 2. トークン（実測値）

| 変数 | 値 | 役割 |
| :--- | :--- | :--- |
| `--paper` | `#F0CC9C` | クラフト紙の地（基準） |
| `--paper-lt` | `#F7DFB4` | 地の明るい側（左上のグラデーション） |
| `--paper-dk` | `#E4C08A` | 地の暗い側（右下） |
| `--cream` | `#F7E1B7` | 反転面の文字 |
| `--ink` | `#00404F` | 墨（藍寄り）。本文・見出し・罫線・CTAの地 |
| `--ink-soft` | `#0C5460` | 補助（説明文・ラベル） |
| `--green` | `#14682A` | 緑。頭字語と名称だけ。**クラフト紙上で 4.5:1 を満たす下限** |
| `--green-fill` | `#187830` | 塗り・フォーカスリング用の緑（文字には使わない） |
| `--gut` | `clamp(20px,5vw,64px)` | 左右の余白 |

**地はグラデーション＋粒（`feTurbulence`）で作る。** 画像を使わない。
**緑を本文に使わない。** `#187830` は紙の上で 3.7:1 しか出ない（`#14682A` で 4.5:1）。

## 3. 書体

| 役割 | 書体 | ウェイト | 使う場所 |
| :--- | :--- | :--- | :--- |
| 掲げる | Zen Kaku Gothic New（`--kaku`） | 900 | キャッチ（h1）・章見出し |
| 支える | Zen Maru Gothic（`--maru`） | 700 / 900 | 名称・頭字語・日程・ボタン・箇条・語の造形 |

**丸ゴシックが地の質感を作る。** 明朝に替えると紙の手触りが消える。
`display=swap` とフォールバックを必ず書く。

## 4. 型のスケール

| 要素 | 級数 |
| :--- | :--- |
| キャッチ（h1） | `clamp(31px,7.6vw,68px)` / 900 / line-height 1.26 / letter-spacing -.02em |
| 名称 | `clamp(12px,2.8vw,15px)` / 700 / 緑 |
| ヒーローの4項目（`.lead`） | `clamp(13.5px,3.2vw,16px)` / 丸ゴ 700 / 墨 / 幅 26em / 1項目ずつ `1.5px` の細罫で切る（**枠にしない**。I-13 でヒーローは線） |
| 日程の数字 | `clamp(23px,5.6vw,33px)` / 900 |
| 6語（造形） | `clamp(21px,5.6vw,34px)` / 900 / 緑と墨の交替 |
| 4行（造形） | `clamp(16.5px,4vw,23px)` / 700 / 行頭に緑の丸 |
| 要項の箇条 | `clamp(15.5px,3.7vw,20px)` / 700 |
| 枠の中の本文 | 行長 `38em`（枠の外は `34em`）。枠の右に大きな空きを残さない |
| 本文（3章） | `clamp(14.5px,3.3vw,16.5px)` / line-height 2.05 |

ジャンプ率（キャッチ ÷ 3章本文）= 68 ÷ 16.5 ≒ **4.1**

## 5. 骨格

| # | 区画 | 中身 |
| ---: | :--- | :--- |
| 1 | `.topmark` | 主催ロゴ「山梨もしも財団」（白い札の上・I-14）。**文字の主催表記は置かない**。**紙の左上に固定値（20px）で留める。ここだけ `--gut` を使わない**（I-16） |
| 2 | `.hero` | **2カラム**。左 `.hero-main`（名称→キャッチ→罫線→4項目）／右 `.rail` |
| 3 | `.rail` | 頭字語（縦読み・罫線で区切る）→ 募集期間 → 採択者決定 → CTA |
| 4 | `#about` | 導入文（小さく組む） |
| 5 | `#why` | 3章（なんでアラサー？ / なんで３０日？ / なんで３０万？）。既定は「なんで３０日？」 |
| 6 | `#guidelines` | 募集要項（対象・資格・審査基準・流れ・方法） |
| 7 | `footer` | Follow US / 財団のSNS / 問い合わせ先 / 主催ロゴ（天と同じ・大きめ） |
| 8 | `.cta-fix` | **常時右下に出るエントリー導線**（I-15）。`footer` の後ろに置く |

- ヒーローは `max-width:1160px`、区画は `900px`、本文は `24em`〜`34em` で止める
- 2カラムは **940px 以上**でだけ。狭い画面は縦積み（左→右の順）
- 罫線は `2.5px` の墨と `1.5px` の緑
- **区切り方は紙面の上下で変える（revision 3・I-13）**
  - `.topmark` `.hero` `.rail` … **線で区切る**（罫線だけ。枠を置かない）
  - `#about` 以降 … **枠で区切る**（`.card`。中身の始まりと終わりが目で分かる）

> **revision 3 で「面で区切らず線で区切る」を撤回した理由。**
> 施主の指摘（2026-08-28「WHYとかからしたが枠がなさすぎてみにくいので視認性を高める方向性で」）。
> `#about` 以降は罫線も持たない素の文字組みで、区画の切れ目・見出しと本文の差が
> 実測のスクリーンショットで判別できなかった。**ヒーローは線のままにする**（そこは
> 罫線が効いており、全面を枠で埋めると紙の余白が死ぬ）。上下で区切り方を変えることが
> 意匠の骨格になる。

## 6. 部品の規則

| 部品 | 規則 |
| :--- | :--- |
| **主催ロゴ（`.logo`）** | `<a>` で `https://yamanashifund.org/` へ送る（別タブ・`rel="noopener noreferrer"`・確定文言の外に視覚非表示の注記＝I-10）。中身は `<picture>` で webp 2段（200/400）＋ **png** フォールバック（**jpg は透過を持てない**）。**背景を敷かず、紙に直に載せる。** 上下 `10px` の余白は見た目ではなく、たたく領域を 44px 以上にするため（透過なので見えない）。`width`/`height` を必ず書く（レイアウトシフト防止）。天は幅 `132px`（実寸 ≒55px）、フッターは `176px`。天のロゴだけ `loading="eager"` ＋ `fetchpriority="high"`。比 3.74 を崩さない |
| **地の粒（`.grain`）** | `position:fixed` の SVG 1枚。`feTurbulence` を紙色で薄く。`opacity:.5` |
| **右の帯（`.rail`）** | 940px 以上で左に `2px` の境界線。`align-content:start`（天寄せ） |
| **頭字語（`.mark`）** | Y/A/A/A/C を縦に並べ、各行を `1.5px` の緑罫線で切る。**横1行に並べない** |
| **日程（`.sched`）** | ラベル（字間 .22em）＋西暦＋数字。上に `2.5px` の墨罫線 |
| **3章（`.tabs`）** | `<button aria-expanded aria-controls>` ＋ JS。器は `max-height` で瞬時に切替 |
| **6語（`.words`）** | 横に流し、緑と墨を交替させる。段落にしない |
| **4行（`.deeds`）** | 行頭に緑の丸。段落にしない |
| **年齢（`.h3row .age`）** | 「エントリー資格」の見出し脇に枠付きで置く。**ヒーローには出さない** |
| **CTA（`.cta`）** | 墨地・`min-height:60px`・角丸 999px。hover で 3px 持ち上げ |
| **枠（`.card`）** | `#about` 以降の区画の器。`2.5px` の墨・角丸 `18px`・地は `--cream` を `.55` で敷く・**静止した版ずれの影**（`3px 3px 0` の墨 14%）。影は動かさない（reflow を伴うため） |
| **区画の見出し（`.eyebrow`）** | 枠付きの札にする（`2px` の墨・角丸 999px）。区画の始まりを枠の外に立てる。**`#about` と `#why` では `h2`**（この2区画には他に見出しが無く、`h1`→`h3` と階層が飛ぶため）、`#guidelines` では `p`（そこは「募集要項」が `h2`） |
| **区画の見出し（`h2`）** | 全幅の下罫（`2.5px` の墨）。下に並ぶ枠が**その子**だと読めるようにする |
| **小見出し（`h3`）** | 枠の中で下罫（`2px` の墨 25%）を持つ。**本文との差を級数だけに頼らない** |
| **応募導線の枠** | `#guidelines` の最後の枠だけ罫を `3.5px`・地を `.8` にして一段強くする（Quality Standards の優先順位1位。`:last-of-type` で当てるので、要項の最後は常に「エントリー方法」に保つ） |
| **箇条（`.plain` / `.numbered`）** | 行ごとに下罫を引く（`.plain` は破線 25%、`.numbered` は実線 16%）。最終行は引かない |
| **追従のCTA（`.cta-fix`）** | 右下に `position:fixed`。`min-height:56px`・紙色の縁取り `2.5px`・影で紙面から浮かせる。**ヒーローの CTA が画面から出たら現れる**（I-15）。消し方は `opacity` と `pointer-events` と `inert`。`display:none` / `visibility:hidden` は使わない（確定コピー照合が `innerText` を見るため）。フッターの下端に逃げ場（`padding-bottom`）を確保し、最後の行を隠さない。DOM 上は `footer` の後ろに置き、タブ順の最後にする |

### ロゴのコントラスト実測（2026-08-28）

紙（`#F0CC9C`／明 `#F7DFB4`／暗 `#E4C08A`）に対するロゴ各色のコントラスト比:

| ロゴの色 | 紙 | 紙の明 | 紙の暗 |
| :--- | ---: | ---: | ---: |
| 濃い青 `#0969a0`（山梨・財団） | 3.90 | 4.57 | 3.45 |
| 青 `#2E9BE6` | 1.99 | 2.33 | 1.76 |
| 水 `#47c9cf` | 1.31 | 1.54 | 1.16 |
| 緑 `#50D0A0`（「も」の末尾） | 1.27 | 1.49 | 1.12 |

**「もしも」の水〜緑側は地とほぼ同じ明るさになる。** revision 9 まではこれを理由に
白い札に載せていたが、施主の指示で透過に戻した（2026-08-28）。
ロゴタイプに WCAG のコントラスト要件は掛からないので、規則違反ではない。
**ただし縮めると緑側が沈む。** 天 132px / フッター 176px より小さくしない。
白い札を戻したくなったときは、この実測が根拠になる（判断をやり直さないこと）。

## 7. モーション

**キーフレームを1つも持たない。** 動きは操作への応答だけ。

| 対象 | 値 |
| :--- | :--- |
| CTA / タブのホバー | `transform` ＋ `opacity` を 200〜220ms / `cubic-bezier(.2,.7,.3,1)` |
| 3章の開閉 | 瞬時（`max-height` に transition を書かない） |
| 追従CTAの出現 | `opacity` ＋ `transform` を 200ms / `cubic-bezier(.2,.7,.3,1)`。**位置ではなく「ヒーローの CTA が見えているか」で決める**（スクロール駆動アニメーションを置かない） |

- `prefers-reduced-motion: reduce` で全停止。停止しても全情報が読める
- **動かすのは `transform` と `opacity` だけ**
- 出現アニメーション・ループ・スクロール駆動は**置かない**（この案は静止で成立させる）

### Metric exception（2026-08-28 実測）

`motion_metrics.py` の実測（`review/motion-r1.json`）:

| 軸 | 値 | 帯 | 判定 |
| :--- | ---: | :--- | :--- |
| `motion_applied` | 1.0 | 1〜1 | PASS |
| `impact_change` | 0.1 | 12〜9999 | **帯外** |
| `scroll_change` | 0.08 | 0〜9999 | PASS |
| `reduced_motion_stopped` | 1.0 | 1〜1 | PASS |
| `non_composited_props` | 0.0 | 0〜0 | PASS |

- **Metric exception: `impact_change` — この案は §7 のとおり出現アニメーションを1つも持たない。**
  帯（12〜）は「スクロールで画面が変わる案」を前提に引かれており、
  静止で成立させる設計にはそのまま当たらない。**動きを足して帯に入れる改修はしない**
  （I-2「止まらない動きを置かない」と衝突する）。この逸脱は施主・審査に明示して残す

## 7.5 JS を1行持つ判断（山吹案との違い）

**この案は 3章の開閉に inline JS を使う。** 山吹案（`output/yaaac-stamp-dial/`）は
`input[type=radio]` ＋ CSS のみで JS ゼロ、CSP を `script-src 'none'` にしている。

| | この案（craft-rail） | 山吹案（flyer） |
| :--- | :--- | :--- |
| 開閉の実装 | `<button aria-expanded>` ＋ JS | `input[type=radio]` ＋ CSS |
| 読み上げ | **開閉状態が `aria-expanded` で正しく伝わる** | 状態は伝わらない（3章ぶん読まれる） |
| CSP | `script-src` にこのスクリプトのハッシュが必要 | `script-src 'none'` が使える |

**開示の意味論は JS 側が正しい。** そのぶん公開設定が重くなる。
公開する案が決まったら、CSP をその案に合わせて書く（両方に同じ設定は使えない）。

- 畳んだ章に**リンク・ボタンを置かない**（見えない領域にフォーカスが落ちる）
- 畳んだ章を `display:none` にしない（確定コピー照合が `innerText` を見るため落ちる）
- `.tabs` に `role="group"`＋`aria-labelledby`、各章に `role="region"`＋`aria-labelledby`

## 7.6 狭い画面の合格条件

`verify.py` が 320 / 375 / 414px で見る。

- 横スクロール **0**
- **器より内容が広い要素 0**（`scrollWidth > clientWidth` かつ祖先が `overflow:hidden|clip`）
- 操作要素の実寸 44px 以上（`.tab` は 52px、`.cta` は 60px）
- 主要CTA（エントリーはこちら）が縦積みの1画面目〜2画面目に入る

**級数の下限と固定の左右余白を同時に持たせない**（`decisions.md` v6.1・I-11）。

## 8. 不変条件（施主の指示・変更には施主の承認が必要）

| # | 不変条件 | 出どころ |
| ---: | :--- | :--- |
| I-1 | 円環の版（八角形のダイヤル・26〜34の数字・弧に沿う文字）を置かない | 2026-08-27「版26→34は消しちゃってよかった」 |
| I-2 | 回転など、止まらない動きを置かない | 2026-08-27「グルグルまわるやつは撤去して」 |
| I-3 | **ヒーローに年齢（25〜34歳）を出さない。** 確定表記は「エントリー資格」の見出し脇 | 2026-08-27「メインページの25〜34歳も削除して」 |
| I-4 | 頭字語 Y/A/A/A/C は縦に読める形にする（横1行に並べない） | 概要書 §2 |
| I-5 | 「なんで３０日？」「なんで３０万？」の「３０」は全角、本文の「30日」「30万円」は半角 | 概要書 §8 |
| I-6 | 30万円の性質・使途条件、30日の起算・実施条件、必要書類を書かない。寄付を募る導線を作らない | 概要書 §7 |
| I-7 | 応募先は `https://forms.gle/VYF6okc9epGaPC1D6` のみ。URLをベタ貼りしない | 概要書 §5-5 |
| I-8 | Instagram はロゴ意匠を模倣せず文字で表す | 概要書 §6 |
| I-9 | 3章は操作要素に本文が名前で結び付くこと（`role="group"`／`role="region"`＋`aria-labelledby`）。畳んだ章に操作要素を置かない | 相互監査 2026-08-27 |
| I-10 | 外部リンクは確定文言の**外**に視覚非表示の注記を置き、`rel="noopener noreferrer"` | Codex 監査 2026-08-27 |
| I-11 | 狭い画面で器より広い内容を作らない | 実測 2026-08-27 |
| I-12 | 確定コピーを CSS で視覚変形しない（`text-transform` / `font-feature-settings`） | Codex 監査 2026-08-27 |
| I-13 | **`#about` 以降の区画は枠（`.card`）を持つ。** 素の文字組みを地に直置きしない（ヒーローと右の帯は罫線のまま） | 2026-08-28「WHYとかからしたが枠がなさすぎてみにくいので視認性を高める方向性で」 |
| I-14 | **主催は支給されたロゴ「山梨もしも財団」で表す**（天とフッターの2か所）。「河原部社」を出さない。**背景を敷かず透過のまま紙に載せる**（施主 2026-08-28「ロゴが透過されていないので透過処理をおこなって」） | 2026-08-28「団体名が河原部社になっているけどアラサー基金に名前変えておいて」→ 同日「アラサー基金って文言でかいてあるところにこの画像を差し替えて。メインページとページ下部のところね」 |
| I-15 | **申し込み導線が途切れない。** ヒーローの CTA が画面から出たら、右下の `.cta-fix` が現れる。ヒーローの CTA が見えている間は出さない（同じボタンを2つ並べない）。**JS が動かないときは出したままにする**（消えるより出ている方が安全） | 2026-08-28「エントリーボタンはどこに遷移しても右下にある状態に変更」→ 同日改訂「メインページには申し込みボタンがあるのでスクロールしたら[表示]されるようにして」 |

| I-16 | **主催ロゴは紙の左上から動かさない。** 窓幅を変えても位置が変わらないよう、`--gut`（`5vw` を含む）ではなく固定値で留める。ロゴをたたくと `https://yamanashifund.org/` へ送る | 2026-08-28「がぞうがぺーじのさいずへんこうでいちがかわるのでひだりうえこていでいいよ」「画像をタップしたらリンクに変移 https://yamanashifund.org/」 |

**I-9〜I-12 は意匠が変わっても残る**（`references/common.spec` が I-10・I-12 を持つ）。

## 9. 機械照合（`design_spec_lint.py` が読む）

<!-- spec:begin -->
```spec
# ---- この正本が支配するファイル ----
target index.html
require-spec-meta
invariant-coverage

# ---- 案件をまたぐ不変条件（I-10 / I-12 / 複製禁止 / ストレージ） ----
# 中身は references/common.spec（I-10 / I-12 / 複製禁止 / ストレージ）。**ここへコピペしない**
include ../../references/common.spec

# ---- トークン ----
token --paper #F0CC9C
token --cream #F7E1B7
token --ink #00404F
token --green #14682A
token --gut clamp(20px,5vw,64px)

# ---- 書体 ----
font Zen Kaku Gothic New
font Zen Maru Gothic

# ---- 骨格（この順）。I-4: 頭字語の縦読みは目視（機械照合なし） ----
order .topmark .hero .rail #about #why #guidelines footer .cta-fix

# ---- 必須の部品 ----
require-selector .grain
require-selector .rail
require-selector .mark
require-selector .sched
require-selector .words
require-selector .deeds
require-selector .cta

# ---- I-14 / I-16: 主催は支給されたロゴ。たたくと財団のサイトへ ----
# 天とフッターの2か所。class="logo" の実形で数える
require-count class="logo" 2
require-count https://yamanashifund.org/ 2
# 配信URLを1つ名乗る（同じ頁が2つのURLで出ても、正はこちらだと示す）
require-raw rel="canonical" href="https://around30.yamanashifund.org/"
# I-16 の「左上に固定値で留める」は目視（--gut を使っていないことの機械照合はしない）
forbid-regex 河原部社
forbid-regex アラサー基金

# ---- I-15: エントリー導線が常時右下にある ----
# 「JS で出し入れしない」は機械照合なし（目視と §7 のキーフレーム禁止で担保）
require-selector .cta-fix
require-count エントリーはこちら 3

# ---- I-13: #about 以降は枠で区切る（素の文字組みを地に直置きしない） ----
# 枠の数（about 1 + 3章 3 + 要項 5 = 9）。区画を増減したらここも直す。
# Codex 監査 2026-08-28: `card"` の生文字列を9回数えるだけでは、無関係な属性でも
# 水増しできる。class 属性の実形で数え、どの区画の枠かまで縛る
require-selector .card
require-count class="card" 1
require-count class="panel-inner card" 3
require-count class="block card" 5

# ---- I-5: 確定コピーの主要どころ（全60件は verify.py --fixed が見る） ----
require-text アラサーってちょうどいいスタートライン。
require-text エントリーはこちら
require-text 25〜34歳
require-text 一次審査　書類選考
require-text なんでアラサー？
require-text なんで３０日？
require-text なんで３０万？
forbid-regex なんで30日？
forbid-regex なんで30万？

# ---- I-1 / I-2: 版と止まらない動きを置かない ----
forbid-regex textPath
forbid-regex clip-rule="evenodd"
forbid-regex animation:[^;]*infinite
# この案はキーフレームを持たない（動きは操作への応答だけ）
forbid-regex @keyframes

# ---- I-3: ヒーローに年齢を出さない ----
forbid-in-hero 25〜34歳
require-near エントリー資格 25〜34歳 1200

# ---- I-9 / I-10: 3章の読み上げと外部リンクの注記 ----
require-raw role="group"
require-count role="region" 3
require-count class="sr" 2
require-count aria-expanded 3
require-count aria-controls 3
forbid-regex display:\s*none
forbid-regex visibility:\s*hidden

# ---- I-6: 書いてはいけないこと（I-8 Instagram の文字表記は verify.py の外部リソース検査で担保。ここでは照合なし） ----
forbid-regex 返済不要
forbid-regex 使途自由
forbid-regex この基金を応援

# ---- I-7: 応募先は1つ ----
require-raw https://forms.gle/VYF6okc9epGaPC1D6

# ---- 意匠の下限。I-11（狭幅の器あふれ）は verify.py の「器より広い内容」が見る ----
max-animation-ms 400
min-tap-px 44
```
<!-- spec:end -->

## 10. ゼロから組む手順

1. `briefs/yaaac.md` の確定文言60件を先に流し込む（**装飾より文言が先**）
2. `:root` に §2 のトークン。**色を増やさない**（紙・墨・緑だけ）
3. Google Fonts で Zen Kaku Gothic New（500/700/900）と Zen Maru Gothic（400/700/900）
4. 地を作る: `radial-gradient` ＋ `position:fixed` の粒 SVG（`opacity:.5`）
5. `.topmark` → `.hero`（左 `.hero-main` / 右 `.rail`）の2カラム。940px 未満は縦積み
6. 右の帯に 頭字語（縦読み）→ 日程2件 → CTA。**年齢は入れない（I-3）**
7. `#about` の導入文は小さく、`#why` の3章は `<button aria-expanded>`＋JS
8. `#guidelines` を罫線で区切る。「・」は文字として出す。区切りは全角スペース
9. §7 のとおり、キーフレームを置かない。`prefers-reduced-motion` で全停止
10. §11 の検証を全部通す。1つでも FAIL なら公開しない

## 11. 検証

```powershell
.\.venv\Scripts\python.exe scripts\verify.py output\yaaac-stamp-dial-craft\index.html --fixed briefs\yaaac.md
.\.venv\Scripts\python.exe scripts\interface_lint.py output\yaaac-stamp-dial-craft\
.\.venv\Scripts\python.exe scripts\design_spec_lint.py output\yaaac-stamp-dial-craft\
.\.venv\Scripts\python.exe scripts\shots.py output\yaaac-stamp-dial-craft\index.html --desktop
```

## 12. この検査が見ていないもの

`design_spec_lint.py` はソースを読む。computed style・DOM の実構造・実寸のコントラスト・
フォント読込の成否は見えない（`verify.py` の担当）。詳細は
`output/yaaac-stamp-dial/DESIGN.md` §12 と同じ。

## 12.5 未確定（施主に確認が必要）

- **2案のどちらを公開するか**（この案 / 山吹案）。公開する案の CSP は §7.5 のとおり別物
- 「25〜34歳」の表記（「歳」か「才」か）
- OGP 画像（公開URL確定後に絶対URL化）
- 個人情報の取り扱い表示（フォーム側にあるか）
