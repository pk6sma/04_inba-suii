# 第3段階：模式図の位置確定・平常カード再確認待ち

## 現行方針（以下の方法A・地理座標描画の記録より優先）
- 方法A/Bは中止。assets/basemap_schematic.pngを使用。
- 背景の実寸は1402×1122px。pxはこの画像左上を[0,0]とする原寸ピクセル座標。
- stations/facilitiesにpxとpx_statusを追加。地図対象15件はconfirmed、平均値と補助値はnot_applicable。
- lat/lonとその承認状態は記録として保持するが、現行カード描画では使用しない。
- 旧label_offset_pxは記録として保持し、模式図のpxには重ねて加算しない。
- render_check_schematic.pyは仮座標を表示。施設のF番号は修正対象を識別するための確認用。
- render_card.pyも模式図へ切替済み。px_statusがconfirmedでない間は画像生成前に停止。
- 旧basemap・方法A画像・旧確認スクリプトは履歴として保持。現行カードは読み込まない。
- カード出典の地理院タイルを除外し、地図右下は「位置関係模式図」。方位記号・スケールバーなし。
- F3=[1150,350]、F4=[1175,372]へ修正し、ユーザー指示により全15件のpxを確定。
- 承認記録はdata/schematic_approval.json。lat/lonの承認履歴とは独立。
- check_schematic.png再出力・確定コミット後、平常カードsample_regular.pngを再出力して停止。
- event・欠測・Webhook・Actionsは今回進めない。

## 以前の実装記録（現行方針で変更された部分を含む）

- Noto Sans JP Regular / Bold（SubsetOTF）とOFL 1.1 LICENSEをassets/fontsに同梱。
- 公式notofonts/noto-cjkから3ファイルを各1回取得。取得記録・SHA256はassets/fonts/sources.json。
- 同梱フォント以外のネットワークアクセスなし。追加依存なし。
- render_card.pyは平常regularの承認用実装。event/欠測/警戒の描画は未実装で例外停止。
- config.jsonで提供文言・ロゴのパスを指定。docs/sponsor.pngを変更せずassets/sponsor.pngへコピー。
- data/stations.jsonの既存値・座標・番号を保ち、display_orderとlabel_offset_pxのみ追加。
- 背景地図700×560は原寸。現在は方法Aで簡略化したbasemap_simple.pngを使用。全体1200×675、上部65・地図560・下部50px。
- 白背景・紺のタイトルは指示文を優先。見本画像の紺背景・白タイトルとは異なる。
- 表示番号は追加指示によりdisplay_orderの1〜9へ統一。印旛沼平均は一覧4、地図マーカーなし。内部IDと第2段階のmap_numberは変更しない。
- 既存オフセットは地点に紐づけて保持（安食=[0,-22]、長門川=[18,14]、天戸=[-4,-20]）。表示番号変更によるオフセットの移動はしない。施設はunknownのグレー表示。
- 表示9行に対し元JSONは補助値を含む11レコード。県の北・西印旛沼を表示。
- fixtures/latest_regular.jsonは保存済みout/latest.jsonのコピー。値・日時を書き換えていない。
- 日時は2026-10-29 04:04、観測は水文状況図04:00・県03:50の過去データ。現在の観測値ではない。
- 画像はout/cards/sample_regular.png。承認前なので今回の変更は未コミット。

## 検証

既存51件＋平常描画、all_below=null時の正常表現拒否、未確定座標の描画拒否の3件。
計54件合格。画像の寸法・提供枠・ネットワークなしの描画を検証。
施設も含め全座標をconfirmed_card_pixelで検証してから描画。

## 承認後の残作業

1. event・欠測・警戒の描画とfixture、提供枠の全ケース、7日超カード整理、定時固定名の出力。
2. notify.pyのdry-run・ログ・最大1回リトライ。実Webhook送信なし。
3. GitHub Actions、月別history互換対応、requirements.txtへの導入済みPillowの反映。pushなし。

後続仕様で確認すべき点：
- 現行summary.fetchedはok件数、failedはstaleを含む利用不可件数、staleはfailedの内数。
  指示書のfetched-failed-stale / failed+staleをそのまま適用すると二重減算・二重計上になる。
  第1段階の互換を保ちながら、カードの表示9件に対する集計方法を決める必要がある。
- 第1段階のfacility_1等と第2段階の施設IDは未対応。unknown以外の状態を実施設へ適用するには対応表の確認が必要。
- Webhook POSTがcommit/pushより先の場合、その時点で今回のraw画像URLは未公開。
  成果物の公開と通知の順序、およびraw URLに使うリポジトリ・ブランチを確認する。


## 追加修正：番号と地図の方法A
- tools/simplify_basemap.pyで元画像の水域色RGB(190,210,255)に近い画素と白背景との境界色を抽出。
- 5×5 MaxFilterで2px膨張、水域#9CC8F0・その他#FFFFFFの2色。元のbasemap.pngはSHA256で不変確認。
- 検索・新たな地理データ取得・水域形状の推測追加・小成分の任意削除は行わない。
- 元画像の橋・文字等による水路の途切れと、小さな水色の断片は一部残る。滑らかな連続水域を保証しない。
- 目視では道路・鉄道・既存地名の形状は除去できている。抽出の見た目はユーザー判断待ち。
- data/labels.jsonに指定3水域名・7市町名の仮配置座標。coord_status=candidateは文字位置の仮置きで、観測所座標の確定状態とは独立。
- 未承認のためevent/欠測/Webhook/Actionsへは進まない。
