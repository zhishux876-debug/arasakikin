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
GitHub Pages / Netlify が _site/ を配る
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

## 人がやること（1回だけ）

このリポジトリには**まだリモートがない**（`git remote -v` が空）。次を人間が実行する。

### A. GitHub Pages で出す場合

1. GitHub で空のリポジトリを作る（**private でよい。Pages は public でも private でも設定できる**）
2. リモートを繋いで push する

   ```powershell
   git remote add origin https://github.com/<アカウント>/<リポジトリ>.git
   git push -u origin master
   ```

3. リポジトリの **Settings → Pages → Source を「GitHub Actions」** にする
4. 以後、`master` に push するたびに `publish.yml` が走る

### B. Netlify を Git 連携で使う場合

1. 同じく GitHub にリポジトリを作って push する
2. Netlify で **Add new site → Import an existing project** からそのリポジトリを選ぶ
3. ビルド設定は `netlify.toml`（リポジトリ直下）が持っているので、**画面では何も入力しない**
   - build command: `python3 scripts/publish_target.py --build _site`
   - publish directory: `_site`
4. 以後、push するたびに Netlify がビルドして配る

**AとBを同時に有効にしない。** 同じ内容が2つのURLで出て、どちらが本物か分からなくなる。

## ヘッダ（CSP・noindex）の扱い

`publish_target.py` が `_site/_headers` を生成する。**CSP の `script-src` は、
配信する実物から sha256 を計算して書く。**

- クラフト案は3章の開閉にインライン JS を1つ持つ → そのハッシュを許可する
- 山吹案は JS ゼロ → `script-src 'none'` になる

手で書くと案を差し替えたときに食い違い、**ページが真っ白になるか、逆に緩い CSP のまま出る。**

> **GitHub Pages はレスポンスヘッダを設定できない。** `_headers` は Netlify でだけ効く。
> Pages で出すあいだ、CSP と `X-Frame-Options` は**掛からない**。
> `noindex` は生成される `robots.txt` が受け持つ（ヘッダの `X-Robots-Tag` は効かない）。
> ヘッダまで要るなら B（Netlify）を選ぶ。

`noindex` は `DESIGN.md` の `status` に「承認済」が入るまで自動で付く。
**施主が承認する前に検索結果へ出ない。**

## 決まったこと（2026-08-28・施主）

| 項目 | 決定 |
| :--- | :--- |
| 公開する案 | **`output/yaaac-stamp-dial-craft`（クラフト紙案）**。山吹案は `canonical: no` にし、公開設定を外した |
| 配信先 | **GitHub Pages**（A）。Netlify（B）の設定はリポジトリ直下に残してあるが、繋いでいない |

**まだリモートが無いので、上の「人がやること」A を実行するまで配信は始まらない。**

### 検索結果に出す（noindex を外す）とき

いまは `DESIGN.md` の `status` が「施主承認待ち」なので、`publish_target.py` が
**自動で noindex を付ける**（`robots.txt` に `Disallow: /`）。
公開してよくなったら、正本の1行を書き換えて push する。

```markdown
- status: 施主承認済み（2026-XX-XX）
```

**逆に言うと、うっかり push しても検索結果には出ない。** 出すのは明示的な操作だけ。

## まだ決まっていないこと

- 独自ドメインを使うか（使うなら Pages は `CNAME`、Netlify は管理画面で設定）
- OGP 画像（`og:image`）。**公開 URL が決まってからでないと絶対 URL にできない**
  （`briefs/yaaac.md` の TODO）
