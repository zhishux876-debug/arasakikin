# 案件をまたぐ不変条件（design_spec_lint.py が読む共有の規則）
#
# 各案件の DESIGN.md から `include ../../references/common.spec` で取り込む。
# **毎案件へコピペしない。** 写しを配ると、直したときに古い写しが残る。
#
# ここに置く条件は2つを満たすものだけ:
#   1. この作業場の全案件に効く（CLAUDE.md か decisions.md の恒久ルールに根拠がある）
#   2. verify.py / interface_lint.py が見ていない（責務を二重に持たない）
#
# 案件固有の値（配色・書体・骨格・級数）はここに書かない。各 DESIGN.md が持つ。

# ---- 確定コピーを CSS で視覚変形しない（I-12 相当） ----
# 文字列は変えずに見た目だけ大文字化・異体字化されると、確定コピー照合を素通りする。
# verify.py は innerText を見るので、この改変は捕まえられない
forbid-regex text-transform:\s*(?!none)
forbid-regex font-feature-settings

# ---- 外部リンクの rel（I-10 相当） ----
# target="_blank" に noopener だけ付けて noreferrer を忘れている状態を止める
forbid-regex target="_blank"[^>]*rel="noopener"(?!\s+noreferrer)

# ---- 同じ頁の古い複製をリポジトリに残さない ----
# 2026-08-27 に3回起きた事故。複製が公開経路（deploy/ など）に残り、
# 施主指示が巻き戻った版が公開される。_archive/ は意図した複製なので除外される
forbid-stale-copy output/**/*.html

# ---- ストレージ API（CLAUDE.md 技術要件） ----
# verify.py も見ているが、こちらはソースの段階で止める。編集中に気づける
forbid-regex \b(?:local|session)Storage\b
