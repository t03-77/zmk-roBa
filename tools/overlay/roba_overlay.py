#!/usr/bin/env python3
"""
roBa キー配置オーバーレイ（Windows）

画面の隅に roBa のキー配置を半透明で常時表示する。
 - roBa.keymap を読み込んで表示するので、キーマップを変えてもアプリの修正は不要
 - ファームウェアのレイヤー通知（F13〜F24）を受け取り、表示中のレイヤーを自動で切替
 - 押したキーの位置を光らせる。いま押さえているレイヤーキーも色が変わる
 - クリックは下のウィンドウに素通り（操作の邪魔をしない）

必要なもの: Windows + Python 3.10 以上（標準の tkinter だけで動く。追加インストール不要）

起動:  start_overlay.bat をダブルクリック（リポジトリの config/roBa.keymap を読む）
       python roba_overlay.py <roBa.keymap のパス>   … 別の場所のキーマップを使う場合

ショートカット（Ctrl + Alt + Shift + …）
  K  表示/非表示            H  「レイヤー切替中だけ表示」モード切替
  M  移動・調整モード（ドラッグで移動。このモード中は矢印キー単体で ↑↓濃さ ←→大きさ。
     もう一度 Ctrl+Alt+Shift+M か Esc で固定）
  L  表示レイヤーを手動で切替（通知なしのファームで使う）
  P  練習アプリを開く（1日1回、使い始めて10分たつと声かけが出る）
  Q  終了
エラーは同じフォルダの roba_overlay.log に書かれる
"""

from __future__ import annotations

import json
import math
import os
import queue
import re
import sys
import threading
import time

# ---------------------------------------------------------------------------
# 物理配列（roBa.dtsi の physical layout と同じ。1u = 100）
#   (x, y, 回転[度], 回転中心x, 回転中心y)
# ---------------------------------------------------------------------------
KEY_GEOMETRY = [
    # row 0
    (0, 37, 0, 0, 0), (100, 12, 0, 0, 0), (200, 0, 0, 0, 0), (300, 12, 0, 0, 0), (400, 24, 0, 0, 0),
    (800, 24, 0, 0, 0), (900, 12, 0, 0, 0), (1000, 0, 0, 0, 0), (1100, 12, 0, 0, 0), (1200, 37, 0, 0, 0),
    # row 1
    (0, 137, 0, 0, 0), (100, 112, 0, 0, 0), (200, 100, 0, 0, 0), (300, 112, 0, 0, 0), (400, 124, 0, 0, 0), (500, 137, 0, 0, 0),
    (700, 137, 0, 0, 0), (800, 124, 0, 0, 0), (900, 112, 0, 0, 0), (1000, 100, 0, 0, 0), (1100, 112, 0, 0, 0), (1200, 137, 0, 0, 0),
    # row 2
    (0, 237, 0, 0, 0), (100, 212, 0, 0, 0), (200, 200, 0, 0, 0), (300, 212, 0, 0, 0), (400, 224, 0, 0, 0), (500, 237, 0, 0, 0),
    (700, 237, 0, 0, 0), (800, 224, 0, 0, 0), (900, 212, 0, 0, 0), (1000, 200, 0, 0, 0), (1100, 212, 0, 0, 0), (1200, 237, 0, 0, 0),
    # row 3: 左下段3つ + 左親指3つ / 右親指2つ + 右下1つ
    (0, 337, 0, 0, 0), (100, 312, 0, 0, 0), (200, 300, 0, 0, 0),
    (325, 337, 0, 0, 0), (437, 350, 10, 437, 350), (550, 387, 20, 550, 387),
    (650, 387, -20, 750, 387), (763, 350, -10, 863, 350),
    (1200, 337, 0, 0, 0),
]
KEY_COUNT = len(KEY_GEOMETRY)  # 43
TRACKBALL = (1040, 400, 95)    # 中心x, 中心y, 半径（目安の位置）
LAYOUT_W, LAYOUT_H = 1300, 520


def key_polygon(i: int, pad: float = 4.0):
    """キー i の四隅（回転込み）を 1u=100 の座標で返す"""
    x, y, rot, rx, ry = KEY_GEOMETRY[i]
    pts = [(x + pad, y + pad), (x + 100 - pad, y + pad), (x + 100 - pad, y + 100 - pad), (x + pad, y + 100 - pad)]
    if rot:
        a = math.radians(rot)
        ca, sa = math.cos(a), math.sin(a)
        pts = [(rx + (px - rx) * ca - (py - ry) * sa, ry + (px - rx) * sa + (py - ry) * ca) for px, py in pts]
    return pts


def key_center(i: int):
    pts = key_polygon(i, 0)
    return sum(p[0] for p in pts) / 4, sum(p[1] for p in pts) / 4


# ---------------------------------------------------------------------------
# キーマップ解析
# ---------------------------------------------------------------------------
KEY_LABELS = {
    "SPACE": "Space", "SPC": "Space", "RET": "Enter", "RETURN": "Enter", "ENTER": "Enter",
    "BSPC": "BS", "BACKSPACE": "BS", "DEL": "Del", "DELETE": "Del", "ESC": "Esc", "ESCAPE": "Esc",
    "TAB": "Tab", "HOME": "Home", "END": "End", "PG_UP": "PgUp", "PAGE_UP": "PgUp",
    "PG_DN": "PgDn", "PAGE_DOWN": "PgDn", "INS": "Ins", "INSERT": "Ins",
    "LEFT": "←", "LEFT_ARROW": "←", "RIGHT": "→", "RIGHT_ARROW": "→",
    "UP": "↑", "UP_ARROW": "↑", "DOWN": "↓", "DOWN_ARROW": "↓",
    "LCTRL": "Ctrl", "LEFT_CONTROL": "Ctrl", "RCTRL": "Ctrl", "RIGHT_CONTROL": "Ctrl",
    "LSHIFT": "Shift", "LSHFT": "Shift", "LEFT_SHIFT": "Shift", "RSHIFT": "Shift", "RSHFT": "Shift",
    "LALT": "Alt", "LEFT_ALT": "Alt", "RALT": "Alt", "LGUI": "Win", "LEFT_WIN": "Win", "LWIN": "Win",
    "RGUI": "Win", "LEFT_GUI": "Win",
    "INT_MUHENKAN": "英数", "INT5": "英数", "INT_HENKAN": "かな", "INT4": "かな",
    "LANG1": "かな", "LANGUAGE_1": "かな", "LANG2": "英数", "LANGUAGE_2": "英数",
    "INT1": "\\", "INT3": "\\", "NUHS": "]",
    "COMMA": ",", "DOT": ".", "PERIOD": ".", "MINUS": "-", "EQUAL": "=", "SEMI": ";", "SEMICOLON": ";",
    "SQT": "'", "APOS": "'", "SINGLE_QUOTE": "'", "FSLH": "/", "SLASH": "/", "BSLH": "\\", "BACKSLASH": "\\",
    "GRAVE": "`", "LBKT": "[", "LEFT_BRACKET": "[", "RBKT": "]", "RIGHT_BRACKET": "]",
    "LBRC": "{", "LEFT_BRACE": "{", "RBRC": "}", "RIGHT_BRACE": "}",
    "LPAR": "(", "LEFT_PARENTHESIS": "(", "RPAR": ")", "RIGHT_PARENTHESIS": ")",
    "TILDE": "~", "EXCL": "!", "EXCLAMATION": "!", "AT": "@", "AT_SIGN": "@", "HASH": "#", "POUND": "#",
    "DLLR": "$", "DOLLAR": "$", "PRCNT": "%", "PERCENT": "%", "CARET": "^", "AMPS": "&", "AMPERSAND": "&",
    "STAR": "*", "ASTRK": "*", "ASTERISK": "*", "UNDER": "_", "UNDERSCORE": "_", "PLUS": "+",
    "PIPE": "|", "COLON": ":", "DQT": "\"", "DOUBLE_QUOTES": "\"", "LT": "<", "LESS_THAN": "<",
    "GT": ">", "GREATER_THAN": ">", "QMARK": "?", "QUESTION": "?",
    "C_VOL_UP": "Vol+", "C_VOLUME_UP": "Vol+", "C_VOL_DN": "Vol−", "C_VOLUME_DOWN": "Vol−",
    "C_MUTE": "Mute", "C_PP": "再生/停止", "C_PLAY_PAUSE": "再生/停止", "C_NEXT": "次の曲", "C_PREV": "前の曲",
    "PSCRN": "PrtSc", "PRINTSCREEN": "PrtSc", "CAPS": "Caps",
}
BINDING_OVERRIDES = {
    "&kp LC(LS(LEFT))": "単語選択←", "&kp LC(LS(RIGHT))": "単語選択→",
    "&kp LA(LEFT)": "戻る", "&kp LA(RIGHT)": "進む",
    "&kp LC(PG_UP)": "タブ←", "&kp LC(PG_DN)": "タブ→",
    "&kp LG(LS(S))": "スクショ", "&kp LS(LG(S))": "スクショ",
}
MOD_PREFIX = {"LC": "Ctrl+", "RC": "Ctrl+", "LS": "Shift+", "RS": "Shift+", "LA": "Alt+", "RA": "Alt+",
              "LG": "Win+", "RG": "Win+"}
MOUSE_LABELS = {"LCLK": "左クリック", "MB1": "左クリック", "RCLK": "右クリック", "MB2": "右クリック",
                "MCLK": "中クリック", "MB3": "中クリック", "MB4": "戻る", "MB5": "進む"}
LAYER_JA = {"base": "基本", "symbol": "記号", "number": "数字", "nav": "ナビ・F",
            "mouse": "マウス", "scroll": "スクロール", "system": "システム", "snipe": "精密"}


# config/keys_jp.h の別名：(中身, 表示)。日本語配列のPCで出る記号
JP_KEYS = {
    "JP_MINUS": ("MINUS", "-"), "JP_EQUAL": ("LS(MINUS)", "="), "JP_CARET": ("EQUAL", "^"),
    "JP_TILDE": ("LS(EQUAL)", "~"), "JP_YEN": ("INT3", "\\"), "JP_PIPE": ("LS(INT3)", "|"),
    "JP_AT": ("LBKT", "@"), "JP_GRAVE": ("LS(LBKT)", "`"), "JP_LBKT": ("RBKT", "["),
    "JP_LBRC": ("LS(RBKT)", "{"), "JP_RBKT": ("NUHS", "]"), "JP_RBRC": ("LS(NUHS)", "}"),
    "JP_SEMI": ("SEMI", ";"), "JP_PLUS": ("LS(SEMI)", "+"), "JP_COLON": ("SQT", ":"),
    "JP_STAR": ("LS(SQT)", "*"), "JP_BSLH": ("INT1", "\\"), "JP_UNDER": ("LS(INT1)", "_"),
    "JP_EXCL": ("LS(N1)", "!"), "JP_DQT": ("LS(N2)", "\""), "JP_HASH": ("LS(N3)", "#"),
    "JP_DLLR": ("LS(N4)", "$"), "JP_PRCNT": ("LS(N5)", "%"), "JP_AMPS": ("LS(N6)", "&"),
    "JP_SQT": ("LS(N7)", "'"), "JP_LPAR": ("LS(N8)", "("), "JP_RPAR": ("LS(N9)", ")"),
    "JP_LT": ("LS(COMMA)", "<"), "JP_GT": ("LS(DOT)", ">"), "JP_QMARK": ("LS(FSLH)", "?"),
    "JP_EISU": ("LANG2", "英数"), "JP_KANA": ("LANG1", "かな"),
}


def key_label(name: str) -> str:
    name = name.strip()
    if name in JP_KEYS:
        return JP_KEYS[name][1]
    m = re.fullmatch(r"(L[CSAG]|R[CSAG])\((.*)\)", name)
    if m:
        return MOD_PREFIX[m.group(1)] + key_label(m.group(2))
    if name in KEY_LABELS:
        return KEY_LABELS[name]
    m = re.fullmatch(r"(?:N|NUMBER_|KP_N|KP_NUMBER_)([0-9])", name)
    if m:
        return m.group(1)
    if re.fullmatch(r"F[0-9]{1,2}", name):
        return name
    if re.fullmatch(r"[A-Z]", name):
        return name
    return name.replace("_", " ").title()


def strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"//[^\n]*", " ", text)


def find_block(text: str, start: int):
    """text[start] が '{' のとき、対応する '}' の位置を返す"""
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    raise ValueError("unbalanced braces")


def split_bindings(body: str):
    return ["&" + b.strip() for b in body.split("&")[1:]]


class Keymap:
    def __init__(self, text: str):
        global HOST_JIS
        HOST_JIS = bool(re.search(r'#include\s+"keys_jp\.h"', text))
        self.host_jis = HOST_JIS
        text = strip_comments(text)
        self.defines = {k: v for k, v in re.findall(r"^\s*#define\s+(\w+)\s+(\S+)", text, re.M)}
        m = re.search(r"compatible\s*=\s*\"zmk,keymap\"\s*;", text)
        if not m:
            raise ValueError("keymap ノードが見つかりません")
        kstart = text.rfind("{", 0, m.start())
        kbody = text[kstart:find_block(text, kstart) + 1]
        self.layers = []
        node_re = re.compile(r"([\w-]+)\s*\{")
        pos = 1
        while True:
            lm = node_re.search(kbody, pos)
            if not lm:
                break
            s = lm.end() - 1
            e = find_block(kbody, s)
            body = kbody[s:e]
            pos = e + 1
            bm = re.search(r"(?<![-\w])bindings\s*=\s*<(.*?)>\s*;", body, re.S)
            if not bm:
                continue
            dn = re.search(r"display-name\s*=\s*\"([^\"]*)\"", body)
            binds = split_bindings(bm.group(1))
            if len(binds) != KEY_COUNT:
                raise ValueError(f"レイヤー {lm.group(1)} のキー数が {len(binds)} です（{KEY_COUNT} 必要）")
            self.layers.append({"node": lm.group(1), "name": dn.group(1) if dn else lm.group(1),
                                "bindings": binds})
        self.cond = []
        for cm in re.finditer(r"if-layers\s*=\s*<([^>]*)>\s*;\s*then-layer\s*=\s*<([^>]*)>", text):
            ifs = [self.layer_num(t) for t in cm.group(1).split()]
            self.cond.append((ifs, self.layer_num(cm.group(2).strip())))
        self.parents = self._compute_parents()

    def layer_num(self, tok: str) -> int:
        tok = tok.strip()
        tok = self.defines.get(tok, tok)
        return int(tok, 0)

    def _compute_parents(self):
        """&trans の時に下を見に行くレイヤー（ZMK の実際の重なりの近似）"""
        parents = {i: [] for i in range(len(self.layers))}
        for ifs, then in self.cond:
            parents.setdefault(then, [])
            parents[then] += sorted(ifs, reverse=True)
        for li, layer in enumerate(self.layers):
            if li == 0:
                continue
            for b in layer["bindings"]:
                m = re.match(r"&(mo|sl)\s+(\w+)", b)
                if m:
                    target = self.layer_num(m.group(2))
                    if target != li and li not in parents.get(target, []):
                        parents.setdefault(target, []).append(li)
        return parents

    def chain(self, layer: int):
        """layer から下へ辿る順番（最後は 0）"""
        out, todo = [], [layer]
        while todo:
            l = todo.pop(0)
            if l in out or l >= len(self.layers):
                continue
            out.append(l)
            todo += self.parents.get(l, [])
        if 0 not in out:
            out.append(0)
        return out

    def layer_title(self, layer: int) -> str:
        if layer >= len(self.layers):
            return f"Layer {layer}"
        n = self.layers[layer]["name"]
        ja = LAYER_JA.get(n.lower())
        return f"{n}（{ja}）" if ja else n

    def describe(self, binding: str):
        """(メイン表示, サブ表示, 種類) を返す。種類: key/hold/layer/mouse/sys/trans/none"""
        b = " ".join(binding.split())
        if b in BINDING_OVERRIDES:
            return BINDING_OVERRIDES[b], "", "key"
        parts = b.split(" ")
        beh, args = parts[0][1:], parts[1:]
        if beh in ("trans",):
            return "", "", "trans"
        if beh in ("none",):
            return "", "", "none"
        if beh == "kp" and args:
            return key_label(args[0]), "", "key"
        if beh in ("mt", "hm") and len(args) >= 2:
            return key_label(args[1]), "長押し " + key_label(args[0]), "hold"
        if (beh == "lt" or beh.startswith("lt_")) and len(args) >= 2:
            return key_label(args[1]), "長押し " + self.short_layer(args[0]), "hold"
        if beh == "mo" and args:
            return self.short_layer(args[0]), "押す間", "layer"
        if beh == "tog" and args:
            return self.short_layer(args[0]), "ロック", "layer"
        if beh == "to" and args:
            return self.short_layer(args[0]), "へ移動", "layer"
        if beh == "mkp" and args:
            return MOUSE_LABELS.get(args[0], args[0]), "", "mouse"
        if beh == "bt" and args:
            if args[0] == "BT_SEL" and len(args) > 1:
                return f"BT{int(args[1]) + 1}", "接続先", "sys"
            return {"BT_CLR": "BT消去", "BT_CLR_ALL": "BT全消去", "BT_NXT": "BT次", "BT_PRV": "BT前"}.get(args[0], args[0]), "", "sys"
        if beh == "out" and args:
            return {"OUT_USB": "USB", "OUT_BLE": "無線", "OUT_TOG": "USB/無線"}.get(args[0], args[0]), "出力", "sys"
        if beh == "bootloader":
            return "書込", "モード", "sys"
        if beh == "sys_reset":
            return "再起動", "", "sys"
        if beh == "studio_unlock":
            return "Studio", "解除", "sys"
        return beh, " ".join(args), "key"

    def short_layer(self, tok: str) -> str:
        try:
            n = self.layer_num(tok)
        except ValueError:
            return tok
        if n < len(self.layers):
            name = self.layers[n]["name"]
            return LAYER_JA.get(name.lower(), name)
        return tok

    def triggers(self, layer: int):
        """そのレイヤーに入るためのキー位置（ベースや親レイヤー上）"""
        out = set()
        for li, l in enumerate(self.layers):
            for pos, b in enumerate(l["bindings"]):
                m = re.match(r"&(mo|tog|lt|lt_\w+|sl)\s+(\w+)", b)
                if m:
                    try:
                        if self.layer_num(m.group(2)) == layer:
                            out.add(pos)
                    except ValueError:
                        pass
        for ifs, then in self.cond:
            if then == layer:
                for l in ifs:
                    out |= self.triggers(l)
        return out

    def resolved(self, layer: int, pos: int):
        """表示用：(binding, 透過して下の層から来たか)"""
        for depth, l in enumerate(self.chain(layer)):
            b = self.layers[l]["bindings"][pos]
            if not b.startswith("&trans"):
                return b, depth > 0
        return "&none", True


# ---------------------------------------------------------------------------
# Windows 仮想キーコード ⇔ ZMK キー名（押したキーを光らせる用）
# ---------------------------------------------------------------------------
_VK = {"SPACE": 0x20, "RET": 0x0D, "BSPC": 0x08, "TAB": 0x09, "ESC": 0x1B, "DEL": 0x2E,
       "HOME": 0x24, "END": 0x23, "PG_UP": 0x21, "PG_DN": 0x22, "INS": 0x2D,
       "LEFT": 0x25, "UP": 0x26, "RIGHT": 0x27, "DOWN": 0x28,
       "LSHIFT": 0xA0, "RSHIFT": 0xA1, "LCTRL": 0xA2, "RCTRL": 0xA3, "LALT": 0xA4, "RALT": 0xA5,
       "LGUI": 0x5B, "RGUI": 0x5C, "INT_HENKAN": 0x1C, "INT_MUHENKAN": 0x1D,
       "SEMI": 0xBA, "EQUAL": 0xBB, "COMMA": 0xBC, "MINUS": 0xBD, "DOT": 0xBE, "FSLH": 0xBF,
       "GRAVE": 0xC0, "LBKT": 0xDB, "BSLH": 0xDC, "RBKT": 0xDD, "SQT": 0xDE,
       "C_MUTE": 0xAD, "C_VOL_DN": 0xAE, "C_VOL_UP": 0xAF, "C_PP": 0xB3, "PSCRN": 0x2C}
_SHIFTED = {"EXCL": "N1", "AT": "N2", "HASH": "N3", "DLLR": "N4", "PRCNT": "N5", "CARET": "N6",
            "AMPS": "N7", "STAR": "N8", "LPAR": "N9", "RPAR": "N0", "UNDER": "MINUS", "PLUS": "EQUAL",
            "LBRC": "LBKT", "RBRC": "RBKT", "PIPE": "BSLH", "COLON": "SEMI", "DQT": "SQT",
            "TILDE": "GRAVE", "LT": "COMMA", "GT": "DOT", "QMARK": "FSLH"}
_ALIAS = {"SPC": "SPACE", "RETURN": "RET", "ENTER": "RET", "BACKSPACE": "BSPC", "DELETE": "DEL",
          "ESCAPE": "ESC", "PAGE_UP": "PG_UP", "PAGE_DOWN": "PG_DN", "LEFT_ARROW": "LEFT",
          "RIGHT_ARROW": "RIGHT", "UP_ARROW": "UP", "DOWN_ARROW": "DOWN", "LSHFT": "LSHIFT",
          "LEFT_SHIFT": "LSHIFT", "RSHFT": "RSHIFT", "LEFT_CONTROL": "LCTRL", "LEFT_ALT": "LALT",
          "LEFT_WIN": "LGUI", "LWIN": "LGUI", "LEFT_GUI": "LGUI", "SEMICOLON": "SEMI",
          "SLASH": "FSLH", "BACKSLASH": "BSLH", "PERIOD": "DOT", "APOS": "SQT",
          "LEFT_BRACKET": "LBKT", "RIGHT_BRACKET": "RBKT", "INT5": "INT_MUHENKAN", "INT4": "INT_HENKAN",
          "C_VOLUME_UP": "C_VOL_UP", "C_VOLUME_DOWN": "C_VOL_DN", "C_PLAY_PAUSE": "C_PP",
          "PRINTSCREEN": "PSCRN", "LEFT_BRACE": "LBRC", "RIGHT_BRACE": "RBRC",
          "LEFT_PARENTHESIS": "LPAR", "RIGHT_PARENTHESIS": "RPAR", "ASTERISK": "STAR", "ASTRK": "STAR",
          "EXCLAMATION": "EXCL", "AT_SIGN": "AT", "DOLLAR": "DLLR", "PERCENT": "PRCNT",
          "AMPERSAND": "AMPS", "UNDERSCORE": "UNDER", "DOUBLE_QUOTES": "DQT", "QUESTION": "QMARK",
          "LESS_THAN": "LT", "GREATER_THAN": "GT", "POUND": "HASH"}
VK_LAYER_SIGNAL_FIRST = 0x7C  # VK_F13 … F13+layer

# 日本語配列の Windows で、各キー位置が出す仮想キーコード（US とは記号キーが違う）
_VK_JIS = {"MINUS": 0xBD, "EQUAL": 0xDE, "INT3": 0xDC, "LBKT": 0xC0, "RBKT": 0xDB,
           "NUHS": 0xDD, "SEMI": 0xBB, "SQT": 0xBA, "INT1": 0xE2,
           "COMMA": 0xBC, "DOT": 0xBE, "FSLH": 0xBF, "GRAVE": 0xF3}
# 英数/かな（LANG2/LANG1）は IME により届く VK が違うので候補をまとめて見る
_VK_MULTI = {"LANG1": (0x16, 0x15, 0xF2), "LANG2": (0x1A, 0x19, 0xF1, 0xF0)}
HOST_JIS = False   # keymap が keys_jp.h を読み込んでいれば True


def zmk_to_vk(name: str):
    name = name.strip()
    m = re.fullmatch(r"(?:L[CSAG]|R[CSAG])\((.*)\)", name)
    if m:
        return zmk_to_vk(m.group(1))
    name = _ALIAS.get(name, name)
    if HOST_JIS and name in _VK_JIS:
        return _VK_JIS[name]
    name = _SHIFTED.get(name, name)
    if name in _VK:
        return _VK[name]
    m = re.fullmatch(r"(?:N|NUMBER_|KP_N|KP_NUMBER_)([0-9])", name)
    if m:
        return 0x30 + int(m.group(1))
    m = re.fullmatch(r"F([0-9]{1,2})", name)
    if m and 1 <= int(m.group(1)) <= 24:
        return 0x6F + int(m.group(1))
    if re.fullmatch(r"[A-Z]", name):
        return ord(name)
    return None


_MOD_VKS = {"C": {0xA2, 0xA3}, "S": {0xA0, 0xA1}, "A": {0xA4, 0xA5}, "G": {0x5B, 0x5C}}


def _unwrap(name: str):
    """LC(LS(LEFT)) -> ('LEFT', {'C','S'})"""
    mods = set()
    while True:
        m = re.fullmatch(r"[LR]([CSAG])\((.*)\)", name.strip())
        if not m:
            return name.strip(), mods
        mods.add(m.group(1))
        name = m.group(2)


def binding_keys(binding: str):
    """[(vk, 必要な修飾)] を返す"""
    parts = binding.split()
    beh, args = parts[0][1:], parts[1:]
    names = []
    if beh == "kp" and args:
        names = [args[0]]
    elif beh in ("mt", "hm") and len(args) >= 2:
        names = [args[0], args[1]]
    elif (beh == "lt" or beh.startswith("lt_")) and len(args) >= 2:
        names = [args[1]]
    out = []
    for n in names:
        n = JP_KEYS.get(n.strip(), (n,))[0]
        base, mods = _unwrap(n)
        if base in ("LANG1", "LANG2", "LANGUAGE_1", "LANGUAGE_2"):
            out += [(v, mods) for v in _VK_MULTI["LANG1" if base.endswith("1") else "LANG2"]]
            continue
        vk = zmk_to_vk(base)
        if vk is None:
            continue
        for a, b in ((0xA0, 0xA1), (0xA2, 0xA3), (0xA4, 0xA5), (0x5B, 0x5C)):
            if vk in (a, b):           # 左右の修飾キーはどちらでも光らせる
                out += [(a, mods), (b, mods)]
                break
        else:
            out.append((vk, mods))
    return out


def positions_for_vk(km: Keymap, layer: int, vk: int, pressed=frozenset()):
    """押された VK を出しているキー位置。Shift+] で } が出たときは } だけ光らせるよう、
    押されている修飾キーをいちばん多く使う割り当てを優先する"""
    best, hits = -1, set()
    for pos in range(KEY_COUNT):
        b, _ = km.resolved(layer, pos)
        for kvk, mods in binding_keys(b):
            if kvk == vk and all(pressed & _MOD_VKS[m] for m in mods):
                if len(mods) > best:
                    best, hits = len(mods), {pos}
                elif len(mods) == best:
                    hits.add(pos)
    return hits


# ---------------------------------------------------------------------------
# ログ（pyw で起動すると画面に何も出ないので、ファイルとメッセージボックスで知らせる）
# ---------------------------------------------------------------------------
def log(msg: str):
    try:
        with open(os.path.join(APP_DIR, "roba_overlay.log"), "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
    except OSError:
        pass
    if sys.stderr:
        print(msg, file=sys.stderr)


def report_error(msg: str):
    log(msg)
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, msg, "roBa overlay", 0x10)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 設定
# ---------------------------------------------------------------------------
APP_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(APP_DIR, "roba_overlay_settings.json")
DEFAULTS = {"x": None, "y": None, "alpha": 0.55, "scale": 0.62, "visible": True, "only_when_layer": False,
            # 1日1回、使い始めて10分たったら練習の声かけを出す（false で出さない）
            "practice_reminder": True, "practice_prompted": ""}
PRACTICE_FILE = os.path.join(APP_DIR, "..", "practice", "roBa-practice.html")
REMIND_AFTER_SEC = 10 * 60
BANNER_SEC = 90


def load_settings():
    s = dict(DEFAULTS)
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            s.update(json.load(f))
    except (OSError, ValueError):
        pass
    return s


def save_settings(s):
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(s, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


# 色（暗い背景の半透明パネル）
COLORS = {
    "panel": "#15171c", "key": "#2a2e37", "key_edge": "#3c4250", "text": "#eef1f6", "sub": "#9aa3b2",
    "dim": "#6b7280", "hold": "#c9a227", "layer": "#5aa9e6", "mouse": "#5ec28b", "sys": "#e07a5f",
    "press": "#f4f1de", "press_text": "#15171c", "trigger": "#3d5a80", "ball": "#22262e",
}
KIND_COLOR = {"hold": "hold", "layer": "layer", "mouse": "mouse", "sys": "sys"}
TRANSPARENT = "#010203"


# ---------------------------------------------------------------------------
# Windows: キーボードフック（別スレッド）
# ---------------------------------------------------------------------------
class KeyboardHook(threading.Thread):
    """WH_KEYBOARD_LL。イベントを queue に積み、レイヤー通知と自前ショートカットは握りつぶす"""

    # Ctrl+Alt+Shift+文字（エディタやBlenderのCtrl+Alt系とぶつからないよう Shift も必須）
    HOTKEYS = {ord("K"): "toggle", ord("H"): "only_layer", ord("M"): "move", ord("L"): "cycle",
               ord("P"): "practice", ord("Q"): "quit"}
    # 移動・調整モード中だけ、矢印キー単体を握りつぶして調整に使う
    MOVE_KEYS = {0x26: "alpha+", 0x28: "alpha-", 0x27: "scale+", 0x25: "scale-", 0x1B: "move"}

    def __init__(self, events: queue.Queue, signal_count: int):
        super().__init__(daemon=True)
        self.events = events
        self.signal_count = signal_count
        self.move_mode = False      # Tk 側から書き換える（bool の代入なのでスレッド間でも安全）

    def run(self):
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        LRESULT = ctypes.c_ssize_t

        class KBDLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD),
                        ("flags", wintypes.DWORD), ("time", wintypes.DWORD),
                        ("dwExtraInfo", ctypes.c_size_t)]

        HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
        user32.SetWindowsHookExW.restype = wintypes.HHOOK
        user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
        user32.CallNextHookEx.restype = LRESULT
        kernel32.GetModuleHandleW.restype = wintypes.HMODULE
        user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
        user32.GetAsyncKeyState.restype = ctypes.c_short

        def held(vk):
            # 記憶ではなく実際の状態を見る（Ctrl+Alt+Del 等で離した通知を取りこぼしても狂わない）
            return bool(user32.GetAsyncKeyState(vk) & 0x8000)

        first, last = VK_LAYER_SIGNAL_FIRST, VK_LAYER_SIGNAL_FIRST + self.signal_count - 1

        def proc(n_code, w_param, l_param):
            if n_code == 0:
                kb = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                vk = kb.vkCode
                is_down = w_param in (0x100, 0x104)
                if first <= vk <= last:                       # レイヤー通知
                    if is_down:
                        self.events.put(("layer", vk - first))
                    return 1
                if vk in self.HOTKEYS and held(0x11) and held(0x12) and held(0x10):
                    if is_down:                               # 自前ショートカット
                        self.events.put(("cmd", self.HOTKEYS[vk]))
                    return 1
                if self.move_mode and vk in self.MOVE_KEYS:
                    if is_down:
                        self.events.put(("cmd", self.MOVE_KEYS[vk]))
                    return 1
                self.events.put(("down" if is_down else "up", vk))
            return user32.CallNextHookEx(None, n_code, w_param, l_param)

        self._proc = HOOKPROC(proc)  # GC 防止
        hook = user32.SetWindowsHookExW(13, self._proc, kernel32.GetModuleHandleW(None), 0)
        if not hook:
            self.events.put(("error", "キーボードフックを設定できませんでした"))
            return
        self.thread_id = kernel32.GetCurrentThreadId()
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        user32.UnhookWindowsHookEx(hook)


# ---------------------------------------------------------------------------
# オーバーレイ表示
# ---------------------------------------------------------------------------
class Overlay:
    def __init__(self, keymap_path: str):
        import tkinter as tk
        self.tk = tk
        self.keymap_path = keymap_path
        self.km = self.load_keymap()
        self.s = load_settings()
        self.layer = 0
        self.got_signal = False
        self.pressed = set()           # 押下中の VK
        self._last_prune = 0.0
        self.flash = {}                # pos -> 消える時刻
        self.move_mode = False
        self.events = queue.Queue()
        self.mtime = os.path.getmtime(keymap_path)
        self.started = time.time()
        self.banner_until = 0.0

        self.root = tk.Tk()
        self.root.title("roBa overlay")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=TRANSPARENT)
        if sys.platform == "win32":
            self.root.attributes("-transparentcolor", TRANSPARENT)
        self.root.attributes("-alpha", self.s["alpha"])
        self.canvas = tk.Canvas(self.root, bg=TRANSPARENT, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self.on_drag_start)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.place_window()
        self.root.update_idletasks()
        self.set_click_through(True)
        self.redraw()

        self.hook = None
        if sys.platform == "win32":
            self.hook = KeyboardHook(self.events, min(12, len(self.km.layers)))
            self.hook.start()
        self.root.after(15, self.poll)
        self.root.after(2000, self.keepalive)
        self.update_visibility()

    # ---- 準備 ----
    def load_keymap(self):
        with open(self.keymap_path, encoding="utf-8") as f:
            return Keymap(f.read())

    def size(self):
        sc = self.s["scale"]
        return int(LAYOUT_W * sc) + 24, int((LAYOUT_H + 70) * sc) + 24

    def place_window(self):
        w, h = self.size()
        if self.s["x"] is None:
            sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            self.s["x"], self.s["y"] = (sw - w) // 2, sh - h - 60
        self.root.geometry(f"{w}x{h}+{int(self.s['x'])}+{int(self.s['y'])}")

    def set_click_through(self, on: bool):
        if sys.platform != "win32":
            return
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = user32.GetParent(self.root.winfo_id())
        GWL_EXSTYLE, LAYERED, TRANSP, TOOL, NOACT = -20, 0x80000, 0x20, 0x80, 0x08000000
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE) | LAYERED | TOOL | NOACT
        style = style | TRANSP if on else style & ~TRANSP
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)

    # ---- 描画 ----
    def redraw(self):
        c, sc, km = self.canvas, self.s["scale"], self.km
        c.delete("all")
        w, h = self.size()
        ox, oy = 12, 12 + 62 * sc

        def P(pt):
            return ox + pt[0] * sc, oy + pt[1] * sc

        # パネル
        self.round_rect(4, 4, w - 4, h - 4, 18, fill=COLORS["panel"],
                        outline=COLORS["layer"] if self.move_mode else COLORS["panel"], width=2)
        title = km.layer_title(self.layer)
        banner = time.time() < self.banner_until
        if banner:
            title, hint = "今日の練習（5分）", "  →  Ctrl+Alt+Shift+P で開く"
        elif self.move_mode:
            hint = "  ·  ドラッグで移動／↑↓濃さ ←→大きさ／Esc で固定"
        elif self.got_signal or self.layer:
            hint = ""
        else:
            hint = "  ·  レイヤー通知待ち（Ctrl+Alt+Shift+L で手動切替）"
        c.create_text(w / 2, 12 + 26 * sc, text=title + hint, fill=COLORS["hold"] if banner else COLORS["text"],
                      font=("Yu Gothic UI", max(9, int(26 * sc)), "bold"))

        # トラックボール
        bx, by, br = TRACKBALL
        c.create_oval(*P((bx - br, by - br)), *P((bx + br, by + br)), fill=COLORS["ball"], outline=COLORS["key_edge"])

        triggers = km.triggers(self.layer) if self.layer else set()
        now = time.time()
        hot = {p for p, t in self.flash.items() if t > now}
        for vk in self.pressed:
            hot |= positions_for_vk(km, self.layer, vk, self.pressed)

        main_font = ("Yu Gothic UI", max(8, int(25 * sc)), "bold")
        long_font = ("Yu Gothic UI", max(7, int(17 * sc)), "bold")
        sub_font = ("Yu Gothic UI", max(6, int(14 * sc)))
        for pos in range(KEY_COUNT):
            binding, inherited = km.resolved(self.layer, pos)
            main, sub, kind = km.describe(binding)
            pts = [P(p) for p in key_polygon(pos)]
            fill, edge, fg = COLORS["key"], COLORS["key_edge"], COLORS["text"]
            if inherited and self.layer:
                fg = COLORS["dim"]
            if kind in KIND_COLOR and not (inherited and self.layer):
                edge = COLORS[KIND_COLOR[kind]]
            if pos in triggers:
                fill = COLORS["trigger"]
            if pos in hot:
                fill, fg = COLORS["press"], COLORS["press_text"]
            c.create_polygon(*[v for p in pts for v in p], fill=fill, outline=edge, width=max(1, int(2 * sc)))
            cx, cy = P(key_center(pos))
            ang = -KEY_GEOMETRY[pos][2]
            if main:
                c.create_text(cx, cy - (8 * sc if sub else 0), text=main, fill=fg, angle=ang,
                              font=main_font if len(main) <= 3 else long_font)
            if sub:
                c.create_text(cx, cy + 26 * sc, text=sub, angle=ang,
                              fill=COLORS["sub"] if pos not in hot else COLORS["press_text"], font=sub_font)

    def round_rect(self, x1, y1, x2, y2, r, **kw):
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
               x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return self.canvas.create_polygon(pts, smooth=True, **kw)

    # ---- イベント ----
    def poll(self):
        changed = False
        try:
            while True:
                kind, val = self.events.get_nowait()
                if kind == "layer":
                    self.got_signal = True
                    if val != self.layer:
                        self.layer = val
                        self.update_visibility()
                    changed = True
                elif kind == "down":
                    self.pressed.add(val)
                    for p in positions_for_vk(self.km, self.layer, val, self.pressed):
                        self.flash[p] = time.time() + 0.25
                    changed = True
                elif kind == "up":
                    self.pressed.discard(val)
                    changed = True
                elif kind == "cmd":
                    self.command(val)
                    changed = True
                elif kind == "error":
                    report_error(val)
        except queue.Empty:
            pass
        if self.pressed and sys.platform == "win32" and time.time() - self._last_prune > 0.3:
            self._last_prune = time.time()
            import ctypes
            gaks = ctypes.windll.user32.GetAsyncKeyState
            stale = {vk for vk in self.pressed if not gaks(vk) & 0x8000}
            if stale:
                self.pressed -= stale
                changed = True
        if self.flash and min(self.flash.values()) < time.time():
            self.flash = {p: t for p, t in self.flash.items() if t > time.time()}
            changed = True
        if changed:
            self.redraw()
        self.root.after(15, self.poll)

    def keepalive(self):
        # 他の最前面ウィンドウに負けないよう定期的に前へ。キーマップ更新も自動で読み直す
        try:
            self.root.attributes("-topmost", True)
            m = os.path.getmtime(self.keymap_path)
            if m != self.mtime:
                self.mtime = m
                self.km = self.load_keymap()
                self.redraw()
        except (OSError, ValueError) as e:
            log(f"キーマップの読み直しに失敗: {e}")
        self.check_practice_reminder()
        self.root.after(2000, self.keepalive)

    def check_practice_reminder(self):
        now = time.time()
        if self.banner_until and now >= self.banner_until:      # 声かけを消す
            self.banner_until = 0.0
            self.update_visibility()
            self.redraw()
        today = time.strftime("%Y-%m-%d")
        if (self.s.get("practice_reminder", True) and self.s.get("practice_prompted") != today
                and now - self.started >= REMIND_AFTER_SEC and os.path.exists(PRACTICE_FILE)):
            self.s["practice_prompted"] = today
            save_settings(self.s)
            self.banner_until = now + BANNER_SEC
            self.update_visibility()
            self.redraw()

    def open_practice(self):
        self.banner_until = 0.0
        path = os.path.abspath(PRACTICE_FILE)
        if not os.path.exists(path):
            report_error("練習アプリが見つかりません:\n" + path)
            return
        try:
            if sys.platform == "win32":
                os.startfile(path)  # 既定のブラウザで開く
            else:
                import webbrowser
                webbrowser.open("file://" + path)
        except OSError as e:
            report_error(f"練習アプリを開けませんでした: {e}")

    def update_visibility(self):
        if time.time() < self.banner_until:          # 練習の声かけ中は隠していても一時的に出す
            self.root.deiconify()
            self.root.attributes("-topmost", True)
        elif not self.s["visible"]:
            self.root.withdraw()
        elif self.s["only_when_layer"] and self.is_quiet_layer() and not self.move_mode:
            self.root.withdraw()
        else:
            self.root.deiconify()
            self.root.attributes("-topmost", True)

    def is_quiet_layer(self):
        """「レイヤー切替中だけ表示」で隠すレイヤー。ボールに触るたびに出入りする
        マウス系まで表示するとチラつくので、ベースと同じ扱いにする"""
        if self.layer == 0 or self.layer >= len(self.km.layers):
            return True
        return self.km.layers[self.layer]["name"].lower() in ("mouse", "snipe", "scroll")

    def command(self, cmd):
        s = self.s
        if cmd == "toggle":
            s["visible"] = not s["visible"]
        elif cmd == "only_layer":
            s["only_when_layer"] = not s["only_when_layer"]
        elif cmd == "move":
            self.move_mode = not self.move_mode
            if self.hook:
                self.hook.move_mode = self.move_mode
            self.set_click_through(not self.move_mode)
        elif cmd == "cycle":
            self.layer = (self.layer + 1) % len(self.km.layers)
        elif cmd == "practice":
            self.open_practice()
        elif cmd == "quit":
            save_settings(s)
            self.root.destroy()
            os._exit(0)
        elif cmd in ("alpha+", "alpha-"):
            s["alpha"] = min(1.0, max(0.15, s["alpha"] + (0.08 if cmd == "alpha+" else -0.08)))
            self.root.attributes("-alpha", s["alpha"])
        elif cmd in ("scale+", "scale-"):
            s["scale"] = min(1.4, max(0.35, s["scale"] * (1.1 if cmd == "scale+" else 1 / 1.1)))
            self.place_window()
        self.update_visibility()
        save_settings(s)

    def on_drag_start(self, e):
        self._drag = (e.x_root - self.root.winfo_x(), e.y_root - self.root.winfo_y())

    def on_drag(self, e):
        if not self.move_mode:
            return
        dx, dy = self._drag
        self.s["x"], self.s["y"] = e.x_root - dx, e.y_root - dy
        self.root.geometry(f"+{self.s['x']}+{self.s['y']}")

    def run(self):
        self.root.mainloop()
        save_settings(self.s)


def main():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass
    candidates = [sys.argv[1]] if len(sys.argv) > 1 else [
        os.path.join(APP_DIR, "roBa.keymap"),
        os.path.join(APP_DIR, "..", "..", "config", "roBa.keymap"),   # リポジトリ内に置いた場合
    ]
    path = next((p for p in candidates if os.path.exists(p)), None)
    if not path:
        report_error("roBa.keymap が見つかりません。\n"
                     "リポジトリの tools/overlay から起動するか、パスを引数で渡してください。\n\n"
                     + "\n".join(os.path.abspath(c) for c in candidates))
        sys.exit(1)
    path = os.path.abspath(path)
    try:
        Overlay(path).run()
    except Exception as e:  # noqa: BLE001
        import traceback
        log(traceback.format_exc())
        report_error(f"起動できませんでした: {e}\n詳細は roba_overlay.log")
        sys.exit(1)


if __name__ == "__main__":
    main()
