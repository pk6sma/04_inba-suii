# 印旛沼水位bot

現行のカード・Webhook・GitHub Actionsの実行方法、設定手順、検証結果は [第3段階の運用](docs/operations.md) を参照してください。
以下は第1段階の取得・判定の検証記録です。

## 第1段階の記録

公開2ページから水位・施設アイコンを読み取り、ローカルのJSON・追記ログを生成します。
投稿、画像、Webhook、GitHub Actions、座標推定は実装していません。
既存の「佐倉水位bot 設計書（Grok Bot運用）.md」は変更・コミットしていません。
このREADMEと今回の依頼が第1段階の実装範囲です。

## 実行方法（Windows / Python 3.11以上）

作業ルート：
`C:\Users\bufsa\Project\21_Sakura_Goyomi\04_inba-suii`

この環境では既存のPython 3.12.14からルート内に .venv を作成しました。
通常のPATH上のPythonは3.10.6だったため、以下の仮想環境のPythonを使用してください。
グローバル環境の変更はありません。直接依存は requirements.txt の3つだけです。
requests / beautifulsoup4 / pytest の実行に必要な間接依存はpipが解決します。

PowerShellでルートに移動して実行：

```powershell
.\.venv\Scripts\python.exe inba_watch.py --once
.\.venv\Scripts\python.exe -m pytest -q
```

仮想環境を有効化済みなら `python inba_watch.py --once` で同じ処理です。
再構築時はPython 3.11以上で `python -m venv .venv`、
続けて `..venvScriptspython.exe -m pip install -r requirements.txt` を使用します。
既存仮想環境を上書きする用途ではありません。

- 1実行につき各ページ1リクエスト。リトライなし・リダイレクト追跡なし。
- 接続タイムアウト10秒、読み取りタイムアウト30秒。
- User-Agent：`inba-suii-bot (contact: TBD)`（今回承認された暫定値）。
- 県ページはHTTPのまま。HTTPS化しません。
- 終了コード：0＝全件利用可、2＝取得失敗またはstaleあり（JSONは生成）、1＝設定・状態・出力等のエラー。
- テストはrequestsの送信処理を禁止し、保存fixtureだけを使用します。
- テストの一時出力もルート内に置く場合は未使用のパスを `--basetemp=.local/pytest-任意の新しい名前` で指定してください。既存basetempの再利用はpytestによる清掃を伴うので避けてください。

## 構成と出力

- inba_watch.py：一度だけ取得・判定・保存し、latest.jsonと同じJSONを標準出力。
- sources/common.py：宣言された文字コードの厳密な復号、単発HTTP取得。
- sources/mizukan.py / chiba_suibo.py：ソース別の静的HTML解析。
- judge.py：レベル・境界イベント・集計・1時間前比。ネットワークやファイル操作なし。
- data/stations.json：文書順・表示名・出典URL・不一致比較ペア。座標はnull。
- data/thresholds.json：ユーザー指定値。避難情報の目安は独立したevac_guide。
- data/facility_codes.json：空のまま。
- out/latest.json：今回取得の値。古い値で取得失敗を埋めません。
- out/state.json：地点ごとの前回利用可能レベル・値・観測時刻・境界別の最終イベント発行時刻。
- out/history/YYYY-MM-DD.jsonl：毎実行のスナップショットを1行追記。失敗行も記録するが差分計算から除外。
- out/facility_log.csv：観測時刻、文書順、ファイル名。追記のみ。
- out/mismatch.log：県値と補助値の差の絶対値が0.05mを**超えた**ときにJSON行を追記。
- out/stale_suspect.log：県と水文状況図の観測時刻差が30分を**超えた**ときにJSON行を追記。
- 条件に該当しないログファイルは作成しません。
- out、.venv、.local、キャッシュはGit対象外。リポジトリの外には成果物を作りません。

latest/stateはそれぞれ一時ファイルに書き切ってから置換します。
2ファイルをまとめたトランザクションではありません。同時実行は対象外です。
壊れたJSON状態・履歴を黙って初期化せず、エラーで停止します。

## 取得したHTMLと文字コード

初回取得日時はJSTです。HTTPヘッダと保存日時はfixtureと同名の .meta.json に保存しています。
HTML原本は変更していません。記載した数値は保存HTMLの表示テキストから確認したものです。
ブラウザのスクリーンショットによる照合は行っていません。

| ソース | 初回取得日時 | Content-Type | meta宣言 | 採用文字コード | 応答本文サイズ |
|---|---|---|---|---|---:|
| mizukan | 2026-10-29 03:52:31.723593 +09:00 | text/html（charsetなし） | shift-jis | shift_jis | 4,129 bytes |
| chiba_suibo | 2026-10-29 03:52:31.810952 +09:00 | text/html（charsetなし） | SHIFT_JIS / Shift_JIS | shift_jis | 2,414 bytes |

両方HTTP 200。metaの宣言をPythonのcodec名として正規化し、Shift_JISでstrict復号成功。
推定エンコーディングや置換文字による救済は行いません。ヘッダとmetaの矛盾も取得失敗です。
サイズは取得したHTML本文のバイト数で、ヘッダ・画像・CSS・JSは含みません。
Last-Modified、nw=パラメータは観測日の推定に使用しません。

ソース：
- https://mizukan.sakura.ne.jp/suii/no010121.html
- http://suibo.bousai.pref.chiba.lg.jp/mobile/river/status_3_1_0.html

common.js はページ内にあるが数値はHTML静的部分にあり未使用。
common.js、画像、CSSの追加取得・実行は行っていません。

## 地点順と保存HTMLの値

水文状況図の8地点の対応は、ユーザーが2026-10-29に画面と突き合わせて確認した文書順に基づきます。
順序はstations.jsonだけに保持し、解析コードに地点名との対応を埋め込んでいません。
水位は管理上の表示値のままで、単位・基準面を変換しません。

初回fixtureの水文状況図観測日時：2026-10-29 03:40 JST。

| 文書順 | 地点 | 表示値 |
|---|---|---:|
| 1 | 利根川(安食) | 0.91 |
| 2 | 長門川 | 0.98 |
| 3 | 鹿島川(羽鳥) | 2.15 |
| 4 | 花見川(天戸) | 4.25 |
| 5 | 花見川(検見川) | 0.32 |
| 6 | 印旛沼平均 | 2.01 |
| 7 | 北印旛沼(吉高)・補助値 | 2.00 |
| 8 | 西印旛沼(臼井)・補助値 | 2.03 |

県fixtureの本文時刻は3地点とも03:40。日付は承認された取得時刻基準で2026-10-29と推定。

| 県の観測所 | 表示値 |
|---|---:|
| 高崎川(鏑木橋) | 2.21 |
| 北印旛沼 | 2.00 |
| 西印旛沼 | 2.03 |

このfixtureでは北印旛沼2.00・西印旛沼2.03が水文状況図の補助値と一致しました。
一度の一致は基準面が同一であることの証明ではありません。判定には県値だけを使います。
本実装は「県の3件＋水文状況図の8件」の11レコードです。重複する補助値を含み、11の独立地点を意味しません。

## 日付・鮮度

- 県は本文のHH:MMを取得時刻（JST）の日付に組み合わせます。
- その結果が取得時刻＋5分より後なら前日に戻します。
- ソースと各地点に observed_date_inferred: true、fetched_at を記録します。
- 取得時刻から90分以上前の観測はstale。前回レベルを保持し、判定・イベント・前回比・1時間前比に使いません。
- 日付が明記された水文状況図にも同じ90分の鮮度チェックを適用します。
- 水文状況図の時刻が取得時刻＋5分より未来ならfetch_failedにします。
- 県と水文状況図の観測時刻差が30分超ならstale_suspectを付けてログに記録します。このフラグだけでは判定を止めません。
- 県の各行は独立に判定します。行ごとに時刻が違う場合はソースのobserved_atがnullとなり、地点別時刻を参照します。
- ソースのstatusは1行でもfetch_failedならfetch_failed、それ以外でstaleがあればstale。それでも正常な行は独立に利用します。

**限界：** 県ページには観測日がないため、前日以前から止まったHH:MMが今日の取得時刻に近ければ、
この日付推定と90分チェックを通過し得ます。長期停止を完全に検出できる方式ではありません。
stale_suspectも「ログのみ」であり、この限界を解消しません。

## 基準・イベント・集計

基準値は本タスクでユーザーが指定・修正した値をそのまま採用しています。
この実装作業では別の公式基準ページへの追加アクセスや、将来の基準改定の監視はしていません。

| 判定用県地点 | standby | caution | danger | design |
|---|---:|---:|---:|---:|
| 鏑木橋 | 3.50 | 4.00 | 4.80 | 4.80 |
| 北印旛沼 | 2.80 | 3.40 | null | 4.25 |
| 西印旛沼 | 2.80 | 3.40 | null | 4.25 |

- 境界値ちょうどで上位レベルになります（>=）。
- 鏑木橋の4.80mは同値のうち上位のdesign。dangerを単独で取る区間はありません。
- 北印旛沼のevac_guideはlevel4=2.65、level5=2.80、basis=Y.P.、source=千葉県報道資料 2026-09-28。判定に不使用。
- 印旛沼平均2.30は参考値だけ。補助値を含む他の8件はno_threshold。
- 初回の正常取得は比較元がないためイベントを出しません。trendはnull。
- 前回の利用可能値との大小からtrendをup/down/flatとします。画像の矢印コードは意味づけしません。
- 同一地点のレベル変更は最大1イベント。跨いだ基準はcrossed_thresholdsに配列で保持します。
- 同一地点・同一境界は上下方向共通で、最後に発行したイベントから30分以内（ちょうど30分も含む）は抑止。
- 複数境界を跨ぐ場合は抑止対象だけsuppressed_thresholdsへ分離し、残りを1イベントにします。
- 抑止中も今回レベルは更新します。抑止だけでは境界の最終イベント時刻を延長しません。
- fetch_failed / stale の地点の前回状態は更新しません。
- 1時間前比は**観測時刻**を基準に55〜65分前の有効値から60分に最も近い値を選びます。
  距離が同じなら新しい観測を採用。該当なしはnull。同じ観測を何度取得しても取得時刻で1時間前値を偽装しません。
- with_thresholdは設定上の3地点。all_belowは全3件の利用可能値がnormalならtrue、
  1件でも基準以上を確認できればfalse、超過が未確認かつ欠測があればnull。
- fetchedはstatus=okのレコード数。failedはfetch_failedとstaleの合計、staleはその内数です。
- 不一致比較は両方status=okの場合だけ。観測時刻が違っても差を記録し、両方の時刻をログに残します。
  差だけを基準面相違の証拠とはしません。浮動小数誤差で0.05mを誤って超過扱いしないようDecimalを使用します。

## 施設アイコン

文書順の番号をIDに使用します。実施設名への対応はこの段階では確定しません。
コード表は空なので、すべてunknownです。水位アイコンのX_Yも文字列記録のみです。

```text
1 ico_010121_kijou_0_1.gif
2 ico_010121_kijou_2_2.gif
3 ico_010121_kijou_0_0.gif
4 ico_010121_kijou_2_1.gif
5 ico_010121_kijou_0_1.gif
6 ico_010121_kijou_1_1.gif
7 ico_010121_kijou_1_1.gif
```

初回fixtureと実行時の7個は同じでした。facility_log.csvは観測時刻・順番・ファイル名を追記します。

## 検証記録（2026-10-29）

| ステップ | pytest -q | コミット |
|---|---|---|
| 1: リポジトリ・設定 | 1 passed | 08d9987 |
| 2: fixture・解析 | 14 passed | 611e709 |
| 3: judge・エントリ | 39 passed | 63d4b04 |
| 4: README・最終検証 | 39 passed | このREADMEのコミット |

テストには、8値/7施設/時刻、1値を削ったHTMLで8地点全失敗、県3地点、
Shift_JIS宣言・不正文字、日付またぎ・5分許容・90分境界、4.00/3.99/4.01、
上下イベント、30分ちょうどの再跨越抑止、失敗時の状態保持、3地点集計、
1時間前窓・最も近い値、0.05mの厳密な閾値、時刻差フラグ、追記出力、
壊れたstateで取得前停止、HTTP維持・リダイレクト不追跡を含みます。

実際の --once は仮想環境のPythonで1回実行し、終了コード0。
生成日時：2026-10-29T04:04:54.639362+09:00。
水文状況図の観測は04:00、県は03:50（日付推定）。
summaryはwith_threshold=3、all_below=true、fetched=11、failed=0、stale=0。
初回のためevents=[]、trend/delta_1hは全件null。
県と補助値は北が2.00/2.00、西が2.03/2.07（差0.04）。
mismatch.log、stale_suspect.logの発生条件には該当しませんでした。
施設ログ7行、history1行、latest/stateを生成しました。

サイトへのアクセスはfixture取得1回＋実行1回＝各ソース合計2回（上限3回以内）。
テストからのネットワークアクセスは0回。画像・JS等へのアクセスも0回。
生成物はローカルout内で、Gitに追加・外部公開していません。

## 設計との差分・次の段階へのメモ

- 追加回答に基づき、9件の例から県3件＋水文状況図8件の11レコードに変更。
- 県観測日は確定情報ではなく推定であることを明示。
- 施設名は実名を推測せず文書順の仮ID・表示名。状態コードの意味づけは保留。
- all_belowは欠測時にnull、初回trendはnull。古い値で正常を装いません。
- common.jsは存在するが未使用。
- 公開運用前にUser-Agentの実連絡先を確定する必要があります。
- 日付のある県の一次データが別途利用可能かを確認すれば、日付推定の限界を減らせます。
- 実運用前には同時実行の排他、latest/state/history間の障害復旧、履歴の肥大化対策、
  基準値改定の確認方法、同時刻での継続比較を検討できます。
- 現在は履歴全体を読むため、長期運用の性能最適化は未実施です。
- 投稿・画像・Webhook・GitHub Actionsは次の段階で明示的に依頼された場合のみ扱います。

## 今回の --once 標準出力（latest.json全文）

以下は検証時のスナップショットです。次回実行後の最新値は out/latest.json を参照してください。

```json
{
  "generated_at": "2026-10-29T04:04:54.639362+09:00",
  "sources": {
    "mizukan": {
      "observed_at": "2026-10-29T04:00:00+09:00",
      "fetched_at": "2026-10-29T04:04:54.325807+09:00",
      "status": "ok",
      "encoding": "shift_jis",
      "response_bytes": 4129,
      "http_status": 200
    },
    "chiba_suibo": {
      "observed_at": "2026-10-29T03:50:00+09:00",
      "observed_date_inferred": true,
      "fetched_at": "2026-10-29T04:04:54.622339+09:00",
      "status": "ok",
      "encoding": "shift_jis",
      "response_bytes": 2414,
      "http_status": 200,
      "stale_suspect": false
    }
  },
  "stations": [
    {
      "id": "ajiki",
      "name": "利根川｜安食",
      "source": "mizukan",
      "level_m": 0.9,
      "status": "ok",
      "observed_at": "2026-10-29T04:00:00+09:00",
      "water_icon": "ico_010121_suii_1_1.gif",
      "water_icon_code": "1_1",
      "level": "no_threshold",
      "trend": null,
      "delta_1h": null
    },
    {
      "id": "nagato",
      "name": "長門川",
      "source": "mizukan",
      "level_m": 0.96,
      "status": "ok",
      "observed_at": "2026-10-29T04:00:00+09:00",
      "water_icon": "ico_010121_suii_1_1.gif",
      "water_icon_code": "1_1",
      "level": "no_threshold",
      "trend": null,
      "delta_1h": null
    },
    {
      "id": "hatori",
      "name": "鹿島川｜羽鳥",
      "source": "mizukan",
      "level_m": 2.15,
      "status": "ok",
      "observed_at": "2026-10-29T04:00:00+09:00",
      "water_icon": "ico_010121_suii_1_2.gif",
      "water_icon_code": "1_2",
      "level": "no_threshold",
      "trend": null,
      "delta_1h": null
    },
    {
      "id": "amado",
      "name": "花見川｜天戸",
      "source": "mizukan",
      "level_m": 4.25,
      "status": "ok",
      "observed_at": "2026-10-29T04:00:00+09:00",
      "water_icon": "ico_010121_suii_1_2.gif",
      "water_icon_code": "1_2",
      "level": "no_threshold",
      "trend": null,
      "delta_1h": null
    },
    {
      "id": "kemigawa",
      "name": "花見川｜検見川",
      "source": "mizukan",
      "level_m": 0.53,
      "status": "ok",
      "observed_at": "2026-10-29T04:00:00+09:00",
      "water_icon": "ico_010121_suii_1_2.gif",
      "water_icon_code": "1_2",
      "level": "no_threshold",
      "trend": null,
      "delta_1h": null
    },
    {
      "id": "inba_average",
      "name": "印旛沼平均",
      "source": "mizukan",
      "level_m": 2.03,
      "status": "ok",
      "observed_at": "2026-10-29T04:00:00+09:00",
      "water_icon": "ico_010121_suii_0_1.gif",
      "water_icon_code": "0_1",
      "level": "no_threshold",
      "trend": null,
      "delta_1h": null
    },
    {
      "id": "yoshitaka_aux",
      "name": "北印旛沼｜吉高（補助値）",
      "source": "mizukan",
      "level_m": 2.0,
      "status": "ok",
      "observed_at": "2026-10-29T04:00:00+09:00",
      "water_icon": "ico_010121_suii_1_2.gif",
      "water_icon_code": "1_2",
      "level": "no_threshold",
      "trend": null,
      "delta_1h": null
    },
    {
      "id": "usui_aux",
      "name": "西印旛沼｜臼井（補助値）",
      "source": "mizukan",
      "level_m": 2.07,
      "status": "ok",
      "observed_at": "2026-10-29T04:00:00+09:00",
      "water_icon": "ico_010121_suii_1_2.gif",
      "water_icon_code": "1_2",
      "level": "no_threshold",
      "trend": null,
      "delta_1h": null
    },
    {
      "id": "kaburagi",
      "name": "高崎川｜鏑木橋",
      "source": "chiba_suibo",
      "level_m": 2.21,
      "status": "ok",
      "observed_at": "2026-10-29T03:50:00+09:00",
      "observed_date_inferred": true,
      "fetched_at": "2026-10-29T04:04:54.622339+09:00",
      "stale_suspect": false,
      "level": "normal",
      "trend": null,
      "delta_1h": null
    },
    {
      "id": "kitainba",
      "name": "北印旛沼",
      "source": "chiba_suibo",
      "level_m": 2.0,
      "status": "ok",
      "observed_at": "2026-10-29T03:50:00+09:00",
      "observed_date_inferred": true,
      "fetched_at": "2026-10-29T04:04:54.622339+09:00",
      "stale_suspect": false,
      "level": "normal",
      "trend": null,
      "delta_1h": null
    },
    {
      "id": "nishiinba",
      "name": "西印旛沼",
      "source": "chiba_suibo",
      "level_m": 2.03,
      "status": "ok",
      "observed_at": "2026-10-29T03:50:00+09:00",
      "observed_date_inferred": true,
      "fetched_at": "2026-10-29T04:04:54.622339+09:00",
      "stale_suspect": false,
      "level": "normal",
      "trend": null,
      "delta_1h": null
    }
  ],
  "facilities": [
    {
      "id": "facility_1",
      "name": "施設1（文書順）",
      "order": 1,
      "icon": "ico_010121_kijou_0_1.gif",
      "state": "unknown"
    },
    {
      "id": "facility_2",
      "name": "施設2（文書順）",
      "order": 2,
      "icon": "ico_010121_kijou_2_2.gif",
      "state": "unknown"
    },
    {
      "id": "facility_3",
      "name": "施設3（文書順）",
      "order": 3,
      "icon": "ico_010121_kijou_0_0.gif",
      "state": "unknown"
    },
    {
      "id": "facility_4",
      "name": "施設4（文書順）",
      "order": 4,
      "icon": "ico_010121_kijou_2_1.gif",
      "state": "unknown"
    },
    {
      "id": "facility_5",
      "name": "施設5（文書順）",
      "order": 5,
      "icon": "ico_010121_kijou_0_1.gif",
      "state": "unknown"
    },
    {
      "id": "facility_6",
      "name": "施設6（文書順）",
      "order": 6,
      "icon": "ico_010121_kijou_1_1.gif",
      "state": "unknown"
    },
    {
      "id": "facility_7",
      "name": "施設7（文書順）",
      "order": 7,
      "icon": "ico_010121_kijou_1_1.gif",
      "state": "unknown"
    }
  ],
  "summary": {
    "with_threshold": 3,
    "all_below": true,
    "fetched": 11,
    "failed": 0,
    "stale": 0

  },
  "events": []
}
```
