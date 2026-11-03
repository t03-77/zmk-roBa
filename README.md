# roBa ZMK config — 普段どおりの QWERTY / 日本語配列のPCでそのまま使える

roBa（Bluetooth版 keyball39 互換・Seeeduino XIAO BLE）用の ZMK 設定です。

- ZMK **v0.3**（最新の安定リリース）に固定。トラックボールドライバもコミット固定
- 文字の並びは普段のキーボードと同じ QWERTY。左下は Ctrl・Win・Alt の順
- PC の設定は日本語配列のまま。記号はキーボード側で日本語配列向けに直してある（`config/keys_jp.h`）
- 記号は「Shift+数字」と同じ並び、Fキーは数字の真下。覚えやすさ優先
- 以前の大西配列版は `archive/roBa-onishi.keymap` に保存（ビルドには使われない）
- 8レイヤー：Base / Symbol / Number / Nav / Mouse / Scroll / System / Snipe
- トラックボール：自動マウスレイヤー（J K L がクリック、打鍵直後は反応しない誤爆防止付き）・スクロール・スクロール固定・精密モード・横スクロール抑制
- ZMK Studio 対応（右手をUSB接続して GUI でキー変更）
- キー配置オーバーレイアプリ付き → [`tools/overlay`](tools/overlay/README.md)
- 練習アプリ付き → `tools/practice/roBa-practice.html`（ブラウザで開く。オーバーレイから Ctrl+Alt+Shift+P でも開ける）。ショートカット・記号・数字・矢印・クリック・スクロール・ドラッグ・精密・英数かな・設定クイズを、苦手と間隔に合わせて毎日出題。キーの変え方ガイド付き
- キーマップを変えたら `python tools/make_practice.py` と `python tools/make_keymap_sheet.py` で練習アプリと配置図を作り直す（オーバーレイは自動で追従）

## 書き込み手順

ファームは `firmware/` に入っています（GitHub Actions でビルドした場合は Actions の Artifacts）。

**旧ファームからの移行なので、最初の1回は設定リセットから**行ってください。古いZMKのペアリング情報やZMK Studioで保存した配置が残っていると、新しい配置にならなかったり左右がつながらなかったりします。

1. 右手をUSBでPCにつなぎ、XIAOのリセットボタンを**素早く2回**押す → `XIAO-SENSE` ドライブが出る
2. `settings_reset-seeeduino_xiao_ble-zmk.uf2` をドライブにコピー（自動で切断される）
3. 左手も同じく 1〜2
4. 右手に `roBa_R-seeeduino_xiao_ble-zmk.uf2`、左手に `roBa_L-seeeduino_xiao_ble-zmk.uf2` を同じ方法でコピー
5. 左右の電源を入れ直すと左右が自動で再接続
6. Windows の「設定 → Bluetooth とデバイス」で古い roBa を削除してから、もう一度ペアリング

2回目以降（キー配置だけ変えたとき）は、**右手に roBa_R を書くだけ**でOKです。

## IME（日本語入力）

設定変更は不要です。英数キーは LANG2、かなキーは LANG1 を送り、Windows 標準の Microsoft IME はこれをそのまま「IME オフ」「IME オン」として扱います。トグルではないので、英数を押せば必ず英字、かなを押せば必ず日本語になります。

Google 日本語入力を使っている場合は、動かなければ Google 日本語入力のキー設定で「Hiragana」「Eisu」キーに IME の有効化・無効化を割り当ててください。

## よく触る調整

| やりたいこと | 場所 |
|---|---|
| カーソル速度 | `boards/shields/roBa/roBa_R.conf` の `CONFIG_PMW3610_CPI`（200刻み） |
| スクロール速度 | `config/roBa.keymap` の `zip_scroll_scaler 1 16`（16を大きく→遅く） |
| スクロール方向を逆に | `config/roBa.keymap` の `zip_scroll_transform INPUT_TRANSFORM_Y_INVERT` の行を消す |
| 横スクロールの効き | `zip_hwheel_damp 1 2`（2を大きく→弱く） |
| 精密モードの遅さ | `zip_xy_scaler 1 4` |
| マウスレイヤーの持続時間 | `zip_temp_layer MOUSE 600`（ms。長くするとクリックしやすいが、直後に打った T/N/S がクリックになりやすい） |
| 打鍵直後にマウスを無視する時間 | `require-prior-idle-ms = <200>` |

キーの入れ替えだけなら、ZMK Studio（https://zmk.studio）で右手をUSB接続すれば書き込み不要で変更できます。ただし Studio で保存した内容は、新しいファームを書いても残ります（keymap ファイルの変更が反映されないときは Studio の「Restore Stock Settings」）。

## 自分でビルドする（GitHub Actions）

このフォルダの中身を自分の GitHub リポジトリに push すると、Actions が自動でビルドし、Artifacts に `firmware.zip` ができます。`firmware/` と `tools/` はビルドには使われません。

## なぜ v0.3 固定なのか

ZMK の `main` は Zephyr 4.1 への移行中の開発版で、トラックボールドライバ（kumamuk-git/zmk-pmw3610-driver、2025年2月が最終更新）が追従していません。以前ビルドが壊れたのは、開発用ブランチ（petejohanson/feat/pointers-move-scroll）を参照していたためです。今後 v0.4 が出たら、`config/west.yml` と `.github/workflows/build.yml` の `v0.3-branch` を書き換えて上げます。
