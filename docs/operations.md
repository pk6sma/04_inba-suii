# 印旛沼水位bot：第3段階の運用

## 実装済みの範囲

- 2ソースの取得、レベル判定、イベント検出、履歴保存。
- 1200×675の平常・イベント・欠測カード。背景は模式図、位置は承認済みpxのみ。
- ⑦鏑木橋のlabel_offset_px=[0,-14]。カードの表示px単位で適用し、この範囲は引き出し線なし。
- イベント限定Webhook、dry-run、最大1回の再試行、秘密を含まない通知ログ。
- GitHub Actionsの10分間隔実行設定。Buffer/Xへの投稿処理はない。
- 本作業ではpush・実Webhook送信・GitHub Actionsの起動・サイト再取得を行っていない。

## ローカル実行

Python 3.12を推奨。直接依存はrequests、beautifulsoup4、pytest、導入済みPillowだけ。
Noto Sans JP Regular/BoldとOFLライセンスはassets/fontsに同梱済み。

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe inba_watch.py --once
.\.venv\Scripts\python.exe render_card.py
.\.venv\Scripts\python.exe notify.py
```

inba_watch.pyの終了コード2は欠測/staleを含むlatest.json生成済みを意味する。
Actionsは2を許容して欠測カードまで進め、他のエラーは停止する。

notify.pyは必要な環境変数がどちらか未設定なら送信せずdry-run。
環境変数が設定済みの場合は実送信されるので、ローカルの動作確認では設定しないこと。
テストでは環境変数を明示的に空にし、requestsをモックしている。

## サンプル画像

- out/cards/sample_regular.png：保存済みの初回実測fixture。
- out/cards/sample_event.png：鏑木橋4.05m・caution・1時間前比+0.62mを仮定したテストfixture。
- out/cards/sample_missing.png：鏑木橋fetch_failed・北印旛沼staleを仮定したテストfixture。

イベント/欠測サンプルは実際に発生した状況の報告ではない。日時はfixtureの保存日時を引き継ぐ。
サンプルファイルは保存期間による削除対象外。

```powershell
.\.venv\Scripts\python.exe render_card.py --kind regular --latest tests/fixtures/latest_regular.json --output out/cards/sample_regular.png
.\.venv\Scripts\python.exe render_card.py --kind event --latest tests/fixtures/latest_event.json --output out/cards/sample_event.png
.\.venv\Scripts\python.exe render_card.py --kind regular --latest tests/fixtures/latest_missing.json --output out/cards/sample_missing.png
```

## カードの判断

- 表示9地点の番号はdisplay_order。④印旛沼平均は一覧のみ。
- 北・西印旛沼は県の値を表示。補助値2件は描かない。
- レベルのある正常取得地点で最上位の地点を状況バッジに出す。
  caution/standbyは黄、danger/designは赤。複数なら「ほかN地点」。
- 警戒と欠測が同時にある場合は警戒を優先し、バッジ詳細に未取得件数も併記する。
- 欠測だけの場合は表示9地点から成功数・未取得数を計算する。
  現行summary.fetched=成功数、failed=staleを含む失敗数、stale=failedの内数という仕様を維持した。
  指示書の引き算・足し算をそのまま適用すると二重計上になるため、カード用に9行から数える。
- all_below=nullでは「すべて基準未満」を出さない。
- fetch_failed/staleの古い数値は描かず「未取得」とする。
- イベントカードは対象地点の丸を大きくし、該当行を強調する。解除イベントは青の強調。
- 提供枠はregular、イベントなし、全取得正常、基準未満のときだけ。
- config.jsonのsponsor.textとsponsor.logo_pathで提供枠を変更できる。
- 施設のsource_idは保存済みmizukan.htmlの直前コメントで施設名と照合して追加した。
  アイコンコード自体の意味は推定していない。facility_codes.jsonは空のまま。
  unknownはグレー。対応表で排水中/停止/揚水中/故障・欠測が確定した場合に色を変える。

## 定時・履歴・保存期間

render_card.pyを引数なしで呼ぶと、out/latest.jsonから必要なカードを選び、
out/card_manifest.jsonに今回生成したファイルを記録する。

- JST 06:50〜07:00台、18:50〜19:00台の実行ではregularを生成する。
- イベントがあれば同じ回でもeventを別に生成する。
- regular生成時はout/cards/latest_regular.pngにもコピーする。
- Actions遅延で指定枠を逃した場合、朝は12:00前、夕方は24:00前までの最初の実行で補完生成する。
  out/card_schedule.jsonで同じ日・枠の補完重複を防ぐ。
- GitHubのcronは厳密な定刻実行を保証しない。7時/19時ちょうどの更新保証はこの構成ではできない。
- 7日を超えたYYYYMMDD-HHMM-regular/event.pngだけを削除する。
  latest_regular.png、sample_*.png、任意名のファイル、シンボリックリンクは削除しない。
  Git履歴内の過去画像までは削除しないので、リポジトリ全体の容量が一定になるわけではない。
- 新規履歴はout/history/YYYY-MM.jsonlへ追記する。
- 既存日別履歴は月別へまとめ、元ファイルをout/history_archiveへ移動して保存する。
  月別と日別で完全に同じ行が重複していた場合は1行にする（移行中断からの再実行対策）。
- 月別化はファイル数を抑える処理であり、履歴の総データ量を減らすものではない。

## Webhook

環境変数はGROK_WEBHOOK_URL、GROK_WEBHOOK_KEY。実値はソースや文書へ書かない。
ヘッダ名の初期値はX-Webhook-Key。必要な場合のみconfig.jsonへ
webhook.header_nameを追加して変更する（キーの実値は引き続き環境変数）。

- events空なら送信せず終了。
- どちらかの環境変数なしならdry-runをout/notify_log.csvへ追記。
- ペイロードはkind、generated_at、events、全11レコードのname/level_m/level/delta_1h/status、
  summary、card_url、sources。文面は生成しない。
- card_urlは今回画像を含む公開済みコミットのraw URL。ActionsのGITHUB_REPOSITORYとCARD_REVISIONから構成。
- 送信前にlatestとcard_manifestのgenerated_atが一致し、画像が存在することを確認。
- 1回失敗したら再試行は1回まで。リダイレクトは追跡しない。
- HTTP 2xxを成功とする。接続/読み取りタイムアウトは10秒/30秒。
- ログには日時、イベント識別子、成否、試行回数、HTTP状態、例外型のみを記録。
  Webhook URL、キー、例外メッセージ、応答本文は記録しない。
- 同じgenerated_at/eventsの成功ログがある場合、同じ通知を再送しない。
- タイムアウト時に相手が受信済みだったかは判別できないので、再試行による重複受信はあり得る。
- 2回失敗したらActionsを失敗扱いにし、ログを保存。永続的な再送キューは未実装。
  judgeの状態はすでに公開済みなので、次の監視回に同じイベントが自動再通知されるとは限らない。
  必要な再送は該当コミットのlatest/card_manifestを用いて手動確認する。

## GitHub側でユーザーが行うこと

1. リポジトリを用意し、今回のコミットをユーザー自身でpushする。
   この作業時点ではgit remoteは未設定。Codexはremote追加・push・公開を行っていない。
   外部からraw画像を読ませる構成なので、公開リポジトリが前提。
   非公開リポジトリの場合は別途、画像配信先/認証方法の設計が必要。
2. デフォルトブランチに.github/workflows/watch.ymlがあることを確認する。
   定期実行はデフォルトブランチ上のworkflowが対象。
3. Settings → Secrets and variables → Actions → New repository secretで、
   GROK_WEBHOOK_URLとGROK_WEBHOOK_KEYの2つを登録する。値はGitHubの入力欄にだけ設定する。
4. Settings → Actions → General → Workflow permissionsで
   Read and write permissionsを選んで保存する。組織ポリシーで禁止されている場合は管理者に確認する。
   デフォルトブランチの保護設定も、Actionsによるこの出力コミットを許可する必要がある。
5. ActionsタブでInba water watchを選び、まずRun workflowで手動実行する。
   初回が正常・無イベントならWebhookは送らない。Secrets未登録ならイベント時でもdry-run。
   out/latest.json、カード、notify_log.csv、実行結果を確認してから定期運用する。
6. 固定画像URLはリポジトリのデフォルトブランチのout/cards/latest_regular.png。
   event画像URLは通知ペイロードのcard_urlを使用する。

定期処理の順序は「取得 → 描画 → outをcommit/push → 通知 → 通知ログをcommit/push」。
元の指定順（通知してからpush）だと通知時のraw画像が存在しないため、この順に変更した。
変更がないときはコミットしない。push失敗なら通知へ進まない。force pushは行わない。
通知失敗でもログ保存を試み、Actionsの結果を失敗にする。
本worktreeでこれらのGitHub操作を実行したわけではない。

## 検証と限界

- pytest：92件合格。すべてネットワーク禁止。
- 3種の画像、全レベル、欠測、提供枠、定時/遅延補完、7日保持、px未承認拒否、
  Webhook無イベント/dry-run/再試行/機密非出力、月別移行を検証。
- 保存HTML → 取得解析 → 前回レベル比較 → cautionイベント → regular/event描画 →
  固定名保存 → notify dry-runの一連の統合テストも合格。
- YAMLパースとBash構文検証も成功。既存のシステムツールで行い、プロジェクト依存は追加していない。
- GitHub Actions本番実行、実Webhook受信側の認証仕様、外部raw URLの到達確認は未実施。
- 県観測日の推定・90分チェック等の第1段階の制約は引き続き適用される。

## watch.yml 全文

```yaml
name: Inba water watch

on:
  schedule:
    - cron: '*/10 * * * *'
  workflow_dispatch:

permissions:
  contents: write

concurrency:
  group: watch
  cancel-in-progress: false

env:
  TZ: Asia/Tokyo
  PYTHONIOENCODING: utf-8

jobs:
  watch:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - name: Checkout default branch
        uses: actions/checkout@v4
        with:
          ref: ${{ github.event.repository.default_branch }}
          fetch-depth: 1

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: pip

      - name: Install dependencies
        run: python -m pip install -r requirements.txt

      - name: Fetch once
        shell: bash
        run: |
          code=0
          python inba_watch.py --once || code=$?
          # Exit 2 means latest.json was written with missing/stale stations.
          if [[ "$code" -ne 0 && "$code" -ne 2 ]]; then
            exit "$code"
          fi

      - name: Render scheduled and event cards
        run: python render_card.py

      - name: Publish output before notifying
        id: publish
        shell: bash
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add -f -- out/
          if ! git diff --cached --quiet; then
            git commit -m "Update water observations and cards"
            git push origin "HEAD:${{ github.event.repository.default_branch }}"
          fi
          echo "revision=$(git rev-parse HEAD)" >> "$GITHUB_OUTPUT"

      - name: Notify event webhook
        id: notify
        continue-on-error: true
        env:
          GROK_WEBHOOK_URL: ${{ secrets.GROK_WEBHOOK_URL }}
          GROK_WEBHOOK_KEY: ${{ secrets.GROK_WEBHOOK_KEY }}
          CARD_REVISION: ${{ steps.publish.outputs.revision }}
        run: python notify.py

      - name: Save notification log
        if: ${{ always() && steps.publish.outcome == 'success' }}
        shell: bash
        run: |
          if [[ -f out/notify_log.csv ]]; then
            git add -f -- out/notify_log.csv
            if ! git diff --cached --quiet; then
              git commit -m "Record webhook delivery outcome"
              git push origin "HEAD:${{ github.event.repository.default_branch }}"
            fi
          fi

      - name: Report notification failure
        if: ${{ always() && steps.notify.outcome == 'failure' }}
        run: exit 1

```
