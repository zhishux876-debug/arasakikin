# 配信（Git に push したら更新される形にする）

これまでは Netlify に**手でドラッグ&ドロップ**していた。更新のたびに人が正しい
フォルダを選ぶ必要があり、**古い案を出しても応募フォームは動くので事故が見えない**
（2026-08-27 に複製が3つ並んだ事故）。ここでは push を起点にする。

## 決定の在りかは1箇所だけ

**どの案を配信するかを、配信設定に書かない。**

```
output/<案件名>/DESIGN.md  の  canonical: yes     ← ここだけが宣言
        ↓
scripts/publish_target.py  が読んで _site/ を組み立てる
        ↓
GitHub Pages が _site/ を配る
```

固定のディレクトリを配信設定に書くと、案を変えるたびに DESIGN.md と設定の両方を
直すことになり、必ず食い違う。**`canonical: yes` を1行動かせば配信先が変わる。**

`canonical: yes` がまだ無いあいだ、ビルドは**何も配信せずに終わる**（exit 2）。
公開する案を決めるのは人間で、CI ではない（`CLAUDE.md` Decision Authority）。

手元で確かめる:

```powershell
.\.venv\Scripts\python.exe scripts\publish_target.py                 # 解決だけ
.\.venv\Scripts\python.exe scripts\publish_target.py --build _site   # 組み立てまで
```

## 配信前に通るゲート

`.github/workflows/publish.yml` が push のたびに走る。**1つでも落ちたら配信しない。**

| 順 | 検査 | 見るもの |
| ---: | :--- | :--- |
| -2 | `ctrl_char_lint.py` | 潰れた制御文字（他の検査を黙って無効化するので最初） |
| 1.5 | `design_spec_lint.py <案>` | 意匠の正本 `DESIGN.md` からの逸脱 |
| 1.6 | `design_spec_lint.py --canonical-audit` | 公開してよい案が案件で1つか |
| 3 | `interface_lint.py <案>` | ソースの静的検査（どう書かれているか） |
| 1 | `verify.py <案>/index.html --fixed <正本>` | **実機レンダリング**（どう描かれたか）・確定コピー照合 |

`verify.py` はブラウザを入れるぶん遅い。それでも外さない
（`CLAUDE.md` 原則3「ここを飛ばした案は納品しない」）。

## 配信リポジトリは別に立ててある（2026-08-28）

**この工房リポジトリを直接 push しない。**

配信先 `https://github.com/zhishux876-debug/arasakikin` は **public** で、
工房には施主提供の写真（`assets/30kikin/` の20点。YAAAC 名義での使用可否が未確認）、
他案件の成果物、参照サイトの実測、採否の記録が入っている。
**git の履歴に一度でも載せると取り消せない**ので、配信に必要なものだけを
別リポジトリへ新しい履歴で出している。

```
C:\Users\zhish\lp-factory        工房（ローカルのまま。push しない）
        │  scripts\sync_publish.py   ← ホワイトリストに書いたファイルだけを一方通行でコピー
        ▼
C:\Users\zhish\arasakikin-publish 配信リポジトリ（public・push する）
```

更新するときは工房で直してから:

```powershell
.\.venv\Scripts\python.exe scripts\sync_publish.py           # 何が出るか見るだけ
.\.venv\Scripts\python.exe scripts\sync_publish.py --push    # 同期して commit & push
```

- **ホワイトリスト方式**。除外リスト方式だと、新しく増えたファイルが既定で公開側へ漏れる。
  出すものが増えたら `scripts/sync_publish.py` の `WHITELIST` に書き足す
- **配信リポジトリ側を編集しない。** 直しても工房に戻らず、次の同期で上書きされる
- コミットの著者は `zhishux876-debug@users.noreply.github.com`。
  公開リポジトリに業務用メールを残さないため

## 人がやること（1回だけ）

以下は 2026-08-28 に実施済み（`arasakikin-publish` からの初回 push まで）。
別の案件で同じことをするときの手順として残す。

### A. GitHub Pages で出す場合

1. GitHub で空のリポジトリを作る。**無料プランで Pages を使うなら public にする**
   （private からの Pages は Pro 以上）。public にする以上、**何を push するかを絞る**必要がある
   — その仕組みが下の `sync_publish.py`
2. リモートを繋いで push する

   ```powershell
   git remote add origin https://github.com/<アカウント>/<リポジトリ>.git
   git push -u origin main
   ```

3. リポジトリの **Settings → Pages → Source を「GitHub Actions」** にする
4. 以後、`main` に push するたびに `publish.yml` が走る

### B. Netlify — **使わない**（2026-08-28 施主の判断「netlify は一旦よくて Git だけで公開させて」）

`netlify.toml` は削除した。**配信経路は GitHub Pages の1本だけ。**
2つ有効にすると同じ内容が2つの URL で出て、どちらが本物か分からなくなる。

戻したくなったときに要るのは設定ファイルだけで、仕組みは変えなくてよい。
`scripts/publish_target.py` は配信先を知らない（`canonical: yes` から `_site/` を作るだけ）ので、
リポジトリ直下に次の3行を置けば Netlify の Git 連携でそのまま動く。

```toml
[build]
  command = "python3 scripts/publish_target.py --build _site"
  publish = "_site"
```

## ヘッダ（CSP・noindex）の扱い

`publish_target.py` が `_site/_headers` を生成する。**CSP の `script-src` は、
配信する実物から sha256 を計算して書く。**

- クラフト案は3章の開閉にインライン JS を1つ持つ → そのハッシュを許可する
- 山吹案は JS ゼロ → `script-src 'none'` になる

手で書くと案を差し替えたときに食い違い、**ページが真っ白になるか、逆に緩い CSP のまま出る。**

> **GitHub Pages はレスポンスヘッダを設定できない。** 生成した `_headers` は Pages では読まれない。
> したがって **CSP と `X-Frame-Options` は掛からない**（Pages の制約であって、この案の欠陥ではない）。
> `noindex` は生成される `robots.txt` が受け持つので、そちらは効く。
> **それでも `_headers` を作り続ける**のは、配信先を替えたときに手で書き直さないため。
> このページは入力欄も外部スクリプトも持たないので、ヘッダが無いことの実害は小さい。

`noindex` は `DESIGN.md` の `status` に「承認済」が入るまで自動で付く。
**施主が承認する前に検索結果へ出ない。**

## 決まったこと（2026-08-28・施主）

| 項目 | 決定 |
| :--- | :--- |
| 公開する案 | **`output/yaaac-stamp-dial-craft`（クラフト紙案）**。山吹案は `canonical: no` にし、公開設定を外した |
| 配信先 | **GitHub Pages だけ**。Netlify は使わない（2026-08-28「netlify は一旦よくて Git だけで公開させて」）。`netlify.toml` は削除済み |

**残っているのは A-3 だけ。** 初回 push は済んでおり、GitHub の runner 上で
ctrl_char / design_spec / canonical-audit / interface_lint / verify.py（実機 Chromium・
確定コピー60件照合）まで全部 success、`deploy-pages` だけが失敗している。
**原因はリポジトリの Pages が未有効**（Pages API が 404）。
Settings → Pages → Source を「GitHub Actions」にして、失敗した実行を Re-run すれば出る。

### 検索結果に出す（noindex を外す）とき

いまは `DESIGN.md` の `status` が「施主承認待ち」なので、`publish_target.py` が
**自動で noindex を付ける**（`robots.txt` に `Disallow: /`）。
公開してよくなったら、正本の1行を書き換えて push する。

```markdown
- status: 施主承認済み（2026-XX-XX）
```

**逆に言うと、うっかり push しても検索結果には出ない。** 出すのは明示的な操作だけ。

## 本番の配信先は around30.yamanashifund.org（エックスサーバー・2026-08-28 決定）

施主の指示「以前実施した yamanashifund への導入と同じ形式で行いたい」。
本体 `yamanashifund.org` と同じ形式＝**静的ファイルをサーバーへ置く**。

調べたこと（2026-08-28）:

| 調べた先 | 分かったこと |
| :--- | :--- |
| `around30.yamanashifund.org` | **すでに HTTPS で 200**。「エックスサーバー サーバー初期ページ」が出ている＝**サブドメインは作成済み・証明書も有効** |
| `yamanashifund.org` | 素の静的HTML（外部依存は Google Fonts のみ）。正式名称は**一般財団法人山梨もしも財団** |
| サーバー | Apache（`Server: nginx` は前段）。**`.htaccess` が効く** |

**GitHub Pages の独自ドメイン（CNAME）は使わない。** DNS を GitHub へ向けると、
いまサーバーで動いているサブドメインを奪うことになる。`CNAME` は削除した。
`publish_target.py` の CNAME を配る仕組みは残してあるが、ファイルが無いので何もしない。

### アップロードするもの

```powershell
.\.venv\Scripts\python.exe scripts\publish_target.py --build C:\Users\zhish\around30-upload --apache
```

`C:\Users\zhish\around30-upload\` の**中身をそのまま**、エックスサーバーの
`around30.yamanashifund.org` の公開領域（`.../around30.yamanashifund.org/public_html/`）へ置く。
FTP でも、サーバーパネルのファイルマネージャでもよい。

```
.htaccess                              ヘッダ（CSP・noindex・キャッシュ）と 404 の設定
index.html                             応募ページ本体
404.html
robots.txt                             承認前は Disallow: /
assets/logo-yamanashi-moshimo-200.webp
assets/logo-yamanashi-moshimo-400.webp
assets/logo-yamanashi-moshimo.png
```

- **初期ページ（`index.html` や `default_page.png` 等）を先に消す。** 残すと入れ替わらない
- `.htaccess` は**ドットで始まるので FTP クライアントによっては見えない**。隠しファイルを表示する設定にする
- **`MANIFEST.json` は配らない**（寸法・輝度・実測メモという制作の記録で、公開領域に置くと誰でも読める）。
  `publish_target.py` が自動で外す

### GitHub Pages はどうするか

**残す。** 役割が違う。

| | 役割 |
| :--- | :--- |
| GitHub（`arasakikin`） | 検査つきの組み立て場・履歴・控え。push のたびに verify.py まで通る |
| エックスサーバー（`around30`） | **本番。読者が来る場所** |

同じ内容が2つのURLで出るので、`index.html` に
`<link rel="canonical" href="https://around30.yamanashifund.org/">` と `og:url` を入れて
**正はサーバー側だと名乗らせている**（`design_spec_lint` が消えていないか見る）。

### 更新のたびにやること

1. 工房で直す
2. `scripts\publish_target.py --build C:\Users\zhish\around30-upload --apache` で作り直す
3. その中身をサーバーへ上書きアップロード
4. （控えも合わせるなら）`scripts\sync_publish.py --push`

**手でサーバー上のファイルを編集しない。** 次の作り直しで上書きされ、
工房と食い違ったまま気づけなくなる。

## まだ決まっていないこと

- 独自ドメインを使うか（使うなら `CNAME` を配信リポジトリの直下に置く）
- OGP 画像（`og:image`）。**公開 URL が決まってからでないと絶対 URL にできない**
  （`briefs/yaaac.md` の TODO）
