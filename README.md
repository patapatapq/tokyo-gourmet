# 東京ぱたしーグルメ（tokyo-gourmet）

毎週金曜 12:00 JST に GitHub Actions が店を選び、メールを送り、GitHub Pages に写真付きの一覧を出す。

- 公開サイト: https://patapatapq.github.io/tokyo-gourmet/
- リポジトリ: GitHub `patapatapq/tokyo-gourmet`（Actions と Pages を使うので GitHub が正・ISS-289）

## 構成

| 場所 | 役割 |
|---|---|
| `backend/` | 週次パイプライン（`python -m backend.run_weekly`）。Places API で検索→除外→選定→JSON生成→メール |
| `frontend/` | Astro の静的サイト。`public/data/*.json` をビルド時に読む |
| `gas/` | 「行った/たぶん行かない」を Sheets に読み書きする Apps Script（手順は `gas/README.md`） |
| `status_api.json` | GAS Web App の URL。バックエンドとフロントの両方がこの1ファイルを読む |
| `config.yaml` | 検索条件・予算・メール・サイトURL |

## ワークフロー（ISS-478）

| ファイル | 起動 | やること |
|---|---|---|
| `.github/workflows/weekly_recommend.yml` | 毎週金曜 / 手動 | API を叩いてデータを作り commit → `deploy_pages.yml` を呼んで公開 |
| `.github/workflows/deploy_pages.yml` | `frontend/**` への push / 手動 / 週次からの呼び出し | ビルドして Pages へ出すだけ。API は呼ばない |

- フロントだけ直したら push するだけで公開される。手で出し直すなら `gh workflow run deploy_pages.yml`。
- 週次のデータ commit は `GITHUB_TOKEN` で push されるため、**push トリガーでは deploy_pages.yml が起動しない**（GitHub の仕様）。
  そのため週次は `workflow_call` で明示的に呼んでいる。ここを「push で出るはず」と消すと、週次の更新が黙って公開されなくなる。
- Pages のデプロイは `concurrency: pages` で直列にしてある。

## 目隠し（ISS-518）

**これは目隠しであって鍵ではない。**
週次メールのリンク（末尾に `#t=トークン`）から1回開いた端末だけに本文を見せ、それ以外の端末には
「メールのリンクから開いてください」とだけ出す。静的サイトなので判定はブラウザの中でしかできず、次の経路は防がない:

- ソース表示・開発者ツール（localStorage に印を書けば見える）
- `https://patapatapq.github.io/tokyo-gourmet/data/*.json` の直接取得
- 公開リポジトリそのもの

仕組み:

- トークンは GitHub Secret `SITE_GATE_TOKEN`。ビルド時に SHA-256 のハッシュだけをページに埋め込む（平文は公開HTMLに出ない）。
- メールのリンクは `?t=` ではなく `#t=`。フラグメントはサーバーへ送られないのでアクセスログ・リファラに残らない。
- 一致したら localStorage に印（ハッシュ）とトークンを保存し、URL から `#t=…` を消す。
- 検索に出ないよう `noindex`。CI で `SITE_GATE_TOKEN` が空だとビルドを落とす（目隠し無しで公開しないため）。
- 手元の控え: `.secrets/site_gate_token.txt`（Git 管理外）。

### トークンを変えるとき

**変えると全端末の印が無効になり、全員がメールのリンクから入り直すことになる。**

```bash
python -c "import secrets; print(secrets.token_hex(16))"
```

1. 出た値を `.secrets/site_gate_token.txt` に保存する。
2. `gh secret set SITE_GATE_TOKEN < .secrets/site_gate_token.txt`
3. Apps Script のスクリプトプロパティ `GATE_TOKEN` も同じ値にする（ボタンの合言葉を兼ねているため。忘れると保存が「合言葉が一致しません」で失敗する）。
4. `gh workflow run deploy_pages.yml` でサイトを出し直す。
5. 次の週次メールを待つか、`https://patapatapq.github.io/tokyo-gourmet/#t=<新トークン>` を自分で開く。

### ローカル開発

`frontend/start-dev.bat`（`npm run dev`）。`SITE_GATE_TOKEN` が無いローカルではトークンが `dev` になるので、
`http://localhost:4321/tokyo-gourmet/#t=dev` を1回開けば以後は見える。

## 行った / たぶん行かない（ISS-475）

トップとアーカイブの各カード、管理画面に2ボタンがある。どちらかを押した店は**次の週次から**推薦に出なくなる。
同じボタンをもう一度押すと解除。

- 保存先は Google Sheets（GAS 経由）。合言葉は目隠しトークンと同じ値で、目隠しを通った端末だけが持つ。
- 画面を開くと GAS から全店の状態を取り直すので、別の端末で押した分も反映される。
- 失敗したら画面下に赤いメッセージが出て、ボタンの見た目は元に戻る。
- 週次の除外は `data/visited.json`・状態API・gspread 直読み の和集合（`backend/sheets_client.py` の `merge_visited_sources`）。

## テスト

```bash
python -X utf8 -m pytest tests -q
```
