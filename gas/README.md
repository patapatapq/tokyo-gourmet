# 状態API（Google Apps Script）セットアップ

「行った」「たぶん行かない」ボタン（ISS-475）の保存先。`Code.gs` を Google Sheets に紐づけて Web App として公開する。
GitHub Pages は静的サイトなので、書き込み口はここにしか置けない。

## なぜ GAS 経由なのか

Python（gspread）から Sheets を直接読む経路もあるが、OAuth トークン `SHEETS_TOKEN_JSON` が
クライアントシークレットの更新で失効している（2026-09-11 の週次ログで `invalid_client`）。
その結果、毎週「Sheets 読み込み失敗」の警告だけ出して除外0件で素通りしていた。
GAS なら合言葉トークン1つで読み書きでき、Google の OAuth を再取得しなくて済む。
週次（`backend/gas_client.py`）もこの Web App から除外リストを読む。

## 初回の手順

1. 管理用スプレッドシート（`config.yaml` の `sheets.spreadsheet_id`）を開く。
2. 「拡張機能」→「Apps Script」。
3. 既定の `コード.gs` の中身を全部消し、このフォルダの `Code.gs` を貼り付けて保存。
4. 左の歯車「プロジェクトの設定」→「スクリプト プロパティ」→ `GATE_TOKEN` を追加する。
   値はサイトの目隠しトークン（GitHub Secret `SITE_GATE_TOKEN` と同じ値。手元の控えは `.secrets/site_gate_token.txt`）。
5. 右上「デプロイ」→「新しいデプロイ」→ 種類「ウェブアプリ」。
   - 次のユーザーとして実行: **自分**
   - アクセスできるユーザー: **全員**（ログイン無しのスマホから押せるようにするため。守りはトークン）
6. 承認画面で自分のアカウントを許可する（「安全ではないページ」は自作スクリプトなので詳細→移動）。
7. 表示された ウェブアプリ URL（`https://script.google.com/macros/s/…/exec`）を、
   リポジトリ直下の `status_api.json` の `url` に書いて commit / push する。
   push すると `deploy_pages.yml` が走り、サイトのボタンが有効になる。

## コードを直したとき

「デプロイ」→「デプロイを管理」→ 既存のデプロイを編集 →「バージョン: 新バージョン」で更新する。
**「新しいデプロイ」を作ると URL が変わる**ので、`status_api.json` も直すことになる。

## シートの形

`visited` シートの列（見出しで探すので順番は問わない。足りない列は GAS が末尾に足す）:

| 列 | 意味 |
|---|---|
| place_id / name / date_recommended | 週次が追記する（既存） |
| visited / visited_date | 旧来の列。GAS が status に合わせて更新する（visited のとき TRUE） |
| status | `visited`（行った）/ `skipped`（たぶん行かない）/ `none` |
| status_date | status を付けた日 |

`status_log` シートに全変更（日時・place_id・店名・変更前・変更後）が残る。いたずらで消されたらここから戻す。

## 確認の仕方

- トークン違い: `{"ok":false,"error":"forbidden"}` が返り、シートは変わらない。
- ブラウザで URL を直接開く（GET）と `{"ok":true,"service":"tokyo-gourmet-status"}` だけ返る（中身は見せない）。
