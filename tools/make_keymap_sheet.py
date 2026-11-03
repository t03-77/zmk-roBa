#!/usr/bin/env python3
"""config/roBa.keymap から、全レイヤー図とシール用の統合図をまとめた HTML を作る。

  python tools/make_keymap_sheet.py            -> tools/roBa-keymap.html
"""
import html
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "overlay"))
import roba_overlay as ro  # noqa: E402

KEYMAP = os.path.join(HERE, "..", "config", "roBa.keymap")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "roBa-keymap.html")

km = ro.Keymap(open(KEYMAP, encoding="utf-8").read())
L = {n["name"].lower(): i for i, n in enumerate(km.layers)}

HOW = {
    "base": "いつも", "symbol": "Enter を長押し", "number": "Space を長押し",
    "nav": "BS を長押し", "mouse": "ボールを動かすと自動（止めて0.6秒で戻る）",
    "scroll": "かな を長押し／ナビの Tab 位置で固定", "system": "Space と Enter を両方長押し",
    "snipe": "マウス中に ; を長押し",
}
NOTE = {
    "base": "文字の並びは普段のキーボードと同じ。左下は普段と同じ Ctrl・Win・Alt の順で、Ctrl+C は左小指＋中指。Ctrl+Z / Ctrl+A のように左小指が重なるときは、右下の Del を長押しすると Ctrl になります。英数・かなは押すだけで IME がオフ・オンになり、今どちらかを気にしなくて済みます。",
    "symbol": "上の段は、普段のキーボードで Shift を押しながら数字を押したときと同じ並び（Q が ! 、I が ( ）。- と : は普段どおり Shift を押すと = と * になります。",
    "number": "上の段が数字の段、その真下が F キー（F1 は 1 の下）。Space を押さえたまま左手で 1〜5、右手で 6〜0。",
    "nav": "左手の E S D F が ↑←↓→。Home / End はその両側。単語選択は Ctrl+Shift+←/→ を1キーで。スクロール固定はもう一度押すか、かなを長押しして離すと解除。",
    "mouse": "J・K・L が左・中・右クリック（roBa の初期配置と同じ）。打鍵直後 0.2 秒はボールに触れても入らないので、タイプ中の誤クリックを防ぎます。ほかのキーを押すと即解除されて文字が打てます。ボールを止めて 0.6 秒以内に J・K・L を打つとクリックになる点だけ注意。",
    "scroll": "ボールがホイールになります。奥へ転がすと上へスクロール。横スクロールは弱めにしてあります。キーは全部素通りなので、固定中も普通に文字が打てます。",
    "system": "BT1〜5 で接続先を切替。書込モード（ブートローダー）は左右それぞれ、その側のキーで入ります。",
    "snipe": "カーソルが 1/4 の速さに。Blender の頂点選択や DAW の細かい編集に。",
}


def legend_class(kind, inherited):
    if inherited:
        return "k-dim"
    return {"hold": "k-hold", "layer": "k-layer", "mouse": "k-mouse", "sys": "k-sys"}.get(kind, "")


def text_size(s):
    n = len(s)
    return 34 if n <= 1 else 30 if n <= 3 else 22 if n <= 4 else 18 if n <= 6 else 15


def key_group(pos, inner):
    x, y, rot, rx, ry = ro.KEY_GEOMETRY[pos]
    tf = f' transform="rotate({rot} {rx} {ry})"' if rot else ""
    return f'<g{tf}><g transform="translate({x} {y})">{inner}</g></g>'


def svg_frame(body, label):
    bx, by, br = ro.TRACKBALL
    return (f'<svg viewBox="-8 -8 {ro.LAYOUT_W + 16} {ro.LAYOUT_H + 4}" role="img" aria-label="{html.escape(label)}">'
            f'<circle class="ball" cx="{bx}" cy="{by}" r="{br}"/>'
            f'<text class="ball-t" x="{bx}" y="{by + 6}" text-anchor="middle">ボール</text>'
            f'{body}</svg>')


def layer_svg(li):
    triggers = km.triggers(li) if li else set()
    parts = []
    for pos in range(ro.KEY_COUNT):
        b, inh = km.resolved(li, pos)
        inh = inh and li != 0
        main, sub, kind = km.describe(b)
        cls = "cap" + (" trig" if pos in triggers else "") + (" " + legend_class(kind, inh) if legend_class(kind, inh) else "")
        inner = f'<rect class="{cls}" x="4" y="4" width="92" height="92" rx="12"/>'
        if main:
            yy = 44 if sub else 54
            inner += f'<text class="m {legend_class(kind, inh)}" x="50" y="{yy}" font-size="{text_size(main)}" text-anchor="middle">{html.escape(main)}</text>'
        if sub:
            inner += f'<text class="s" x="50" y="78" font-size="12.5" text-anchor="middle">{html.escape(sub)}</text>'
        parts.append(key_group(pos, inner))
    return svg_frame("".join(parts), km.layers[li]["name"])


STICKER_SHORT = {"スクロール": "ｽｸ固定", "単語選択←": "単語←", "単語選択→": "単語→",
                 "再生/停止": "再生", "スクショ": "ｽｸｼｮ"}


def short(main):
    main = STICKER_SHORT.get(main, main)
    return main if len(main) <= 5 else main[:5]


def sticker_svg():
    sym, num, nav = L.get("symbol"), L.get("number"), L.get("nav")
    parts = []
    for pos in range(ro.KEY_COUNT):
        b0 = km.layers[0]["bindings"][pos]
        main, sub, kind = km.describe(b0)
        inner = '<rect class="cap" x="4" y="4" width="92" height="92" rx="12"/>'
        inner += f'<text class="m" x="50" y="{50 if sub else 58}" font-size="{min(30, text_size(main))}" text-anchor="middle">{html.escape(main)}</text>'
        if sub:
            inner += f'<text class="s" x="50" y="70" font-size="11" text-anchor="middle">{html.escape(sub)}</text>'
        for li, cls, x, y, anchor in ((sym, "st-sym", 90, 24, "end"), (num, "st-num", 90, 90, "end"), (nav, "st-nav", 10, 90, "start")):
            if li is None:
                continue
            b = km.layers[li]["bindings"][pos]
            if b.startswith("&trans"):
                continue
            m, _, _ = km.describe(b)
            if m:
                inner += f'<text class="st {cls}" x="{x}" y="{y}" text-anchor="{anchor}">{html.escape(short(m))}</text>'
        parts.append(key_group(pos, inner))
    return svg_frame("".join(parts), "シール用の統合図")


layers_html = []
for li, layer in enumerate(km.layers):
    key = layer["name"].lower()
    title = ro.LAYER_JA.get(key, layer["name"])
    layers_html.append(f"""
<section class="layer" id="layer-{key}">
  <header class="lh">
    <span class="ln">L{li}</span>
    <h3>{html.escape(title)} <span class="en">{html.escape(layer['name'])}</span></h3>
    <span class="how">{html.escape(HOW.get(key, ''))}</span>
  </header>
  <div class="board">{layer_svg(li)}</div>
  <p class="note">{html.escape(NOTE.get(key, ''))}</p>
</section>""")

nav_chips = "".join(
    f'<a href="#layer-{l["name"].lower()}">L{i} {html.escape(ro.LAYER_JA.get(l["name"].lower(), l["name"]))}</a>'
    for i, l in enumerate(km.layers))

page = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>roBa キーマップ</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Zen+Kaku+Gothic+New:wght@400;700;900&family=JetBrains+Mono:wght@500;700&display=swap">
<style>
/* layout: 一列の読み物。各レイヤーは実寸比のキーボード図 + 一行の使い方 */
:root {{
  --bg: #eef0f3; --panel: #ffffff; --fg: #1d2230; --muted: #5d6576; --line: #d3d8e0;
  --cap: #f7f8fa; --cap-edge: #c3c9d3; --dim: #a3aab7; --ball: #dde1e8;
  --hold: #b07d10; --layer: #2f6fb3; --mouse: #2d8a5a; --sys: #c0472f; --trig: #d6e6f8;
  --sym: #d1495b; --num: #2f6fb3; --nav: #2d8a5a;
  --font: "Zen Kaku Gothic New", "Yu Gothic", "Hiragino Sans", system-ui, sans-serif;
  --mono: "JetBrains Mono", ui-monospace, Consolas, monospace;
}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --bg: #14171d; --panel: #1c2028; --fg: #e8ebf1; --muted: #9aa2b1; --line: #2e3440;
  --cap: #262b35; --cap-edge: #3b4251; --dim: #636b7a; --ball: #2a303b;
  --hold: #e0b04a; --layer: #6fa8e8; --mouse: #5ec28b; --sys: #ec8467; --trig: #22385a;
  --sym: #ef7a8a; --num: #6fa8e8; --nav: #5ec28b; color-scheme: dark; }} }}
:root[data-theme="dark"] {{
  --bg: #14171d; --panel: #1c2028; --fg: #e8ebf1; --muted: #9aa2b1; --line: #2e3440;
  --cap: #262b35; --cap-edge: #3b4251; --dim: #636b7a; --ball: #2a303b;
  --hold: #e0b04a; --layer: #6fa8e8; --mouse: #5ec28b; --sys: #ec8467; --trig: #22385a;
  --sym: #ef7a8a; --num: #6fa8e8; --nav: #5ec28b; color-scheme: dark; }}
body {{ background: var(--bg); color: var(--fg); font-family: var(--font); font-size: 15px; line-height: 1.75; }}
.wrap {{ max-width: 980px; margin: 0 auto; padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); padding-block: 40px 72px; display: grid; gap: 28px; }}
h1 {{ font-size: clamp(28px, 5vw, 42px); font-weight: 900; line-height: 1.15; margin: 0; text-wrap: balance; letter-spacing: .01em; }}
h2 {{ font-size: 21px; font-weight: 900; margin: 0 0 4px; text-wrap: balance; }}
h3 {{ font-size: 18px; font-weight: 700; margin: 0; }}
p {{ margin: 0; max-width: 65ch; }}
.meta {{ display: flex; flex-wrap: wrap; gap: 6px 16px; color: var(--muted); font-family: var(--mono); font-size: 12.5px; margin-top: 10px; }}
.chips {{ display: flex; flex-wrap: wrap; gap: 6px; }}
.chips a {{ font-size: 13px; text-decoration: none; color: var(--fg); background: var(--panel); border: 1px solid var(--line); border-radius: 999px; padding: 3px 12px; }}
.chips a:hover, .chips a:focus-visible {{ border-color: var(--layer); outline: none; }}
.changes {{ background: var(--panel); border: 1px solid var(--line); border-radius: 14px; padding: 18px 20px; display: grid; gap: 8px; }}
.changes ul {{ margin: 0; padding-left: 1.2em; display: grid; gap: 4px; max-width: 70ch; }}
.layer {{ display: grid; gap: 10px; }}
.lh {{ display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 12px; }}
.ln {{ font-family: var(--mono); font-weight: 700; font-size: 13px; color: var(--layer); }}
.en {{ font-family: var(--mono); font-size: 12px; font-weight: 500; color: var(--muted); margin-left: 4px; }}
.how {{ font-size: 13px; color: var(--muted); }}
.board {{ background: var(--panel); border: 1px solid var(--line); border-radius: 16px; padding: 12px; overflow-x: auto; }}
.board svg {{ display: block; width: 100%; min-width: 560px; height: auto; }}
.note {{ font-size: 13.5px; color: var(--muted); }}
svg text {{ font-family: var(--font); }}
.cap {{ fill: var(--cap); stroke: var(--cap-edge); stroke-width: 2; }}
.cap.trig {{ fill: var(--trig); }}
.cap.k-hold {{ stroke: var(--hold); }} .cap.k-layer {{ stroke: var(--layer); }}
.cap.k-mouse {{ stroke: var(--mouse); stroke-width: 3; }} .cap.k-sys {{ stroke: var(--sys); }}
.m {{ fill: var(--fg); font-weight: 700; }}
.m.k-dim {{ fill: var(--dim); font-weight: 400; }}
.m.k-mouse {{ fill: var(--mouse); }} .m.k-sys {{ fill: var(--sys); }} .m.k-layer {{ fill: var(--layer); }}
.s {{ fill: var(--muted); }}
.ball {{ fill: var(--ball); stroke: var(--cap-edge); stroke-width: 2; }}
.ball-t {{ fill: var(--muted); font-size: 18px; }}
.st {{ font-size: 15px; font-weight: 700; }}
.st-sym {{ fill: var(--sym); }} .st-num {{ fill: var(--num); }} .st-nav {{ fill: var(--nav); }}
.legend {{ display: flex; flex-wrap: wrap; gap: 6px 18px; font-size: 13px; color: var(--muted); }}
.legend b {{ font-weight: 700; }}
table {{ border-collapse: collapse; width: 100%; font-size: 14px; }}
th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--line); vertical-align: top; }}
th {{ font-size: 12px; letter-spacing: .06em; color: var(--muted); font-weight: 700; }}
.tbl {{ overflow-x: auto; background: var(--panel); border: 1px solid var(--line); border-radius: 14px; padding: 4px 10px; }}
ol {{ margin: 0; padding-left: 1.3em; display: grid; gap: 6px; max-width: 70ch; }}
code {{ font-family: var(--mono); font-size: .88em; background: var(--cap); border: 1px solid var(--line); border-radius: 5px; padding: 0 5px; }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>roBa キーマップ</h1>
    <div class="meta"><span>ZMK v0.3</span><span>43キー + トラックボール</span><span>Windows / 日本語配列のまま</span><span>QWERTY</span></div>
  </header>

  <nav class="chips" aria-label="レイヤー">{nav_chips}<a href="#shortcuts">ショートカット</a><a href="#stickers">シール用</a><a href="#trackball">ボール操作</a></nav>

  <section class="changes">
    <h2>覚えることは3つだけ</h2>
    <ul>
      <li>文字の並びと Ctrl・Win・Alt の位置は、いま使っているキーボードと同じです。</li>
      <li>Enter を押さえると記号、Space を押さえると数字とFキー、BS を押さえると矢印。</li>
      <li>ボールを動かすと J・K・L がクリックになり、止めれば元の文字に戻ります。</li>
    </ul>
    <p class="note">PC の設定はそのまま（日本語配列）で使えます。記号はキーボード側で日本語配列向けに直してあります。</p>
  </section>

  {''.join(layers_html)}

  <section class="layer" id="stickers">
    <header class="lh"><h3>シール用の統合図</h3><span class="how">1キーに最大4つ</span></header>
    <div class="legend"><span><b>中央</b> 文字（普段と同じ）</span><span><b style="color:var(--sym)">右上</b> 記号（Enter長押し）</span><span><b style="color:var(--num)">右下</b> 数字（Space長押し）</span><span><b style="color:var(--nav)">左下</b> ナビ・F（BS長押し）</span></div>
    <div class="board">{sticker_svg()}</div>
    <p class="note">文字は普段と同じなので、シールは右上の記号だけで足ります。数字は上の段にそのまま並び、Fキーはその真下、矢印は左手の E S D F なので、書かなくても辿れます。マウス・スクロール・システムはシール不要です。</p>
  </section>

  <section class="layer" id="shortcuts">
    <h2>よく使うショートカットの押し方</h2>
    <div class="tbl"><table>
      <thead><tr><th>操作</th><th>押し方</th></tr></thead>
      <tbody>
        <tr><td>Ctrl+C / V / X / S / F</td><td>左下の Ctrl（小指）＋ 文字。普段と同じ</td></tr>
        <tr><td>Ctrl+Z / A / Q（左小指が重なるもの）</td><td>右下の Del を長押し（右小指）＋ 文字</td></tr>
        <tr><td>Shift+文字</td><td>英数を長押し（左親指）＋ 文字</td></tr>
        <tr><td>Ctrl+Shift+Z（やり直し）</td><td>右下 Del 長押し ＋ 英数長押し ＋ Z</td></tr>
        <tr><td>Alt+Tab / Ctrl+Tab</td><td>左下の Alt か Ctrl ＋ G の右の Tab</td></tr>
        <tr><td>Ctrl+Space（補完・Blender の画面最大化）</td><td>Ctrl ＋ Space をすばやく押す</td></tr>
        <tr><td>Blender の G R S E X、Shift+A</td><td>普段と同じ位置。Shift+A は 英数長押し＋A</td></tr>
        <tr><td>Blender の 1 / 2 / 3（頂点・辺・面）</td><td>Space を押さえて Q / W / E</td></tr>
        <tr><td>Blender のテンキー視点（1・3・7）</td><td>Blender の設定「テンキーを模倣」を ON にすると、Space＋Q/E/U で正面・右・上</td></tr>
        <tr><td>Win+Shift+S（画面の切り取り）</td><td>BS を押さえて Y</td></tr>
      </tbody>
    </table></div>
  </section>

  <section class="layer" id="trackball">
    <h2>トラックボールの使い方</h2>
    <div class="tbl"><table>
      <thead><tr><th>やりたいこと</th><th>操作</th></tr></thead>
      <tbody>
        <tr><td>クリック</td><td>ボールを動かすとマウスレイヤーに入る → J・K・L が左・中・右クリック</td></tr>
        <tr><td>スクロール</td><td>左親指で「かな」を長押ししながらボール（カーソルは動かない）</td></tr>
        <tr><td>スクロールしっぱなし</td><td>BS長押し＋Tab の位置で固定。もう一度同じ操作か、かなを長押しして離すと解除</td></tr>
        <tr><td>細かい位置合わせ</td><td>マウス中に ; を押さえたまま操作 → 1/4 の速さ</td></tr>
        <tr><td>Ctrl+クリック、Shift+中ドラッグ</td><td>Ctrl / 英数(Shift) を押してもマウスレイヤーは切れないので、そのままクリック・ドラッグ</td></tr>
        <tr><td>Blender でクリック → Tab</td><td>Tab と Esc もマウスレイヤーを切らないので、クリック・Tab・クリックが続けてできる</td></tr>
        <tr><td>ズーム（Ctrl+ホイール）</td><td>Ctrl を押しながら「かな」長押し＋ボール</td></tr>
        <tr><td>エンコーダー（付いている場合）</td><td>普段はホイール、ナビ中はタブ切替、システム中は音量</td></tr>
      </tbody>
    </table></div>
  </section>

  <section class="layer">
    <h2>書き込み手順（初回）</h2>
    <ol>
      <li>右手をUSBでつなぎ、XIAO のリセットを素早く2回 → <code>XIAO-SENSE</code> ドライブに <code>settings_reset</code> をコピー。左手も同じ</li>
      <li>右手に <code>roBa_R</code>、左手に <code>roBa_L</code> を同じ方法でコピー</li>
      <li>Windows の Bluetooth 設定で古い roBa を削除して、もう一度ペアリング</li>
      <li>PC の設定変更は不要。英数・かなは Microsoft IME でそのまま効きます（Google 日本語入力の場合は動作を確認）</li>
    </ol>
    <p class="note">2回目以降、配置だけ変えたときは右手に roBa_R を書くだけです。この図は <code>tools/make_keymap_sheet.py</code> でキーマップから作り直せます。</p>
  </section>
</div>
</body>
</html>
"""

with open(OUT, "w", encoding="utf-8") as f:
    f.write(page)
print("wrote", OUT)
