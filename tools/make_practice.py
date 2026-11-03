#!/usr/bin/env python3
"""config/roBa.keymap から練習アプリ（1枚のHTML）を作る。

  python tools/make_practice.py        -> tools/practice/roBa-practice.html

キーマップを変えたら作り直すと、練習のヒント（どのキーを押すか）も追従する。
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "overlay"))
import roba_overlay as ro  # noqa: E402

KEYMAP = os.path.join(HERE, "..", "config", "roBa.keymap")
TEMPLATE = os.path.join(HERE, "practice", "template.html")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "practice", "roBa-practice.html")

km = ro.Keymap(open(KEYMAP, encoding="utf-8").read())
LI = {l["name"].lower(): i for i, l in enumerate(km.layers)}
base = km.layers[0]["bindings"]

# 日本語配列で Shift を押したときに出る文字（基本レイヤーの記号キー）
JIS_SHIFT = {"-": "=", ":": "*", ";": "+", ",": "<", ".": ">", "/": "?"}


def own(li, pos):
    """そのレイヤー自身の割り当て（透過していないもの）"""
    b = km.layers[li]["bindings"][pos]
    return None if b.startswith("&trans") else b


def find(li, pattern):
    for pos, b in enumerate(km.layers[li]["bindings"]):
        if re.match(pattern, " ".join(b.split())):
            return pos
    return None


# ---- 文字 → 押し方 -------------------------------------------------------
routes = {}


def add(ch, layer, pos, shift=False):
    routes.setdefault(ch, [])
    r = {"l": layer, "p": pos, "sh": shift}
    if r not in routes[ch]:
        routes[ch].append(r)


for li in (0, LI.get("symbol"), LI.get("number")):
    if li is None:
        continue
    for pos in range(ro.KEY_COUNT):
        b = own(li, pos)
        if not b or not b.startswith("&kp "):
            continue
        main, _, kind = km.describe(b)
        name = b.split()[1]
        if re.fullmatch(r"[A-Z]", name):
            add(name.lower(), li, pos)
            add(name, li, pos, True)
        elif len(main) == 1 and not re.fullmatch(r"F\d+", main):
            add(main, li, pos)
            if li == 0 and main in JIS_SHIFT:
                add(JIS_SHIFT[main], li, pos, True)

# ---- 特別なキーの位置 ------------------------------------------------------
pos = {
    "shift": find(0, r"&mt LSHIFT"), "ctrl": find(0, r"&kp LCTRL"), "ctrl_r": find(0, r"&mt RCTRL"),
    "alt": find(0, r"&kp LALT"), "win": find(0, r"&kp LGUI"),
    "space": find(0, r"&lt_spc "), "kana": find(0, r"&lt_scr "),
    "bs": find(0, r"&lt NAV "), "enter": find(0, r"&lt SYM "),
    "tab": find(0, r"&kp TAB"), "esc": find(0, r"&kp ESC"),
}
mouse = LI.get("mouse")
if mouse is not None:
    pos.update({"lclk": find(mouse, r"&mkp (LCLK|MB1)"), "mclk": find(mouse, r"&mkp (MCLK|MB3)"),
                "rclk": find(mouse, r"&mkp (RCLK|MB2)"), "snipe": find(mouse, r"&mo SNIPE|&mo 7")})
nav_li = LI.get("nav")
if nav_li is not None:
    pos["scroll_lock"] = find(nav_li, r"&tog SCROLL|&tog 5")

NAV_KEYS = {"UP": "ArrowUp", "DOWN": "ArrowDown", "LEFT": "ArrowLeft", "RIGHT": "ArrowRight",
            "HOME": "Home", "END": "End", "PG_UP": "PageUp", "PG_DN": "PageDown", "DEL": "Delete",
            "LC(LS(LEFT))": "Ctrl+Shift+ArrowLeft", "LC(LS(RIGHT))": "Ctrl+Shift+ArrowRight"}
nav = {}
if nav_li is not None:
    for p in range(ro.KEY_COUNT):
        b = own(nav_li, p)
        if b and b.startswith("&kp "):
            k = NAV_KEYS.get(b.split(" ", 1)[1].strip())
            if k and k not in nav:
                nav[k] = p

fkeys = {}
num_li = LI.get("number")
if num_li is not None:
    for p in range(ro.KEY_COUNT):
        b = own(num_li, p)
        m = re.fullmatch(r"&kp F(\d+)", " ".join(b.split())) if b else None
        if m:
            fkeys["F" + m.group(1)] = p

# ---- レイヤーの表示用データ ---------------------------------------------------
layers = []
for li, layer in enumerate(km.layers):
    keys = []
    for p in range(ro.KEY_COUNT):
        b, inh = km.resolved(li, p)
        main, sub, kind = km.describe(b)
        keys.append({"m": main, "s": sub, "k": kind, "i": bool(inh and li)})
    trig = sorted(km.triggers(li)) if li else []
    # 「押さえて入る」キーだけで説明する（ロック用の &tog は除く）。
    # 条件付きレイヤー（例: 記号+数字 → システム）は、元になるレイヤーのキーで入る
    entry_layers = {li} | {src for srcs, then in km.cond if then == li for src in srcs}
    holds = []
    for t in trig:
        for lj, lay in enumerate(km.layers):
            m = re.match(r"&(mo|lt|lt_\w+)\s+(\w+)", " ".join(lay["bindings"][t].split()))
            if m and km.layer_num(m.group(2)) in entry_layers:
                holds.append((lj, t))
                break
    holds = sorted(set(holds), key=lambda x: x[1])
    how = ""
    if holds:
        pre = "" if all(lj == 0 for lj, _ in holds) else \
            ro.LAYER_JA.get(km.layers[holds[0][0]]["name"].lower(), "") + "中に "
        how = pre + "・".join(km.describe(base[t])[0] for _, t in holds) + " を押さえて"
    trig = [t for _, t in holds] or trig
    layers.append({"name": layer["name"], "ja": ro.LAYER_JA.get(layer["name"].lower(), layer["name"]),
                   "keys": keys, "trig": trig, "how": how})

data = {
    "geo": ro.KEY_GEOMETRY, "ball": ro.TRACKBALL, "W": ro.LAYOUT_W, "H": ro.LAYOUT_H,
    "layers": layers, "routes": routes, "pos": pos, "nav": nav, "fkeys": fkeys,
    "li": LI,
}

tpl = open(TEMPLATE, encoding="utf-8").read()
marker = "/*__ROBA_DATA__*/null"
assert marker in tpl, "template marker missing"
html = tpl.replace(marker, json.dumps(data, ensure_ascii=False))
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    f.write(html)
print("wrote", OUT, f"({len(routes)} chars, {len(nav)} nav keys, {len(fkeys)} F-keys)")
missing = [k for k, v in pos.items() if v is None]
if missing:
    print("WARNING: positions not found:", missing)
