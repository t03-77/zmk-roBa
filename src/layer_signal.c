/*
 * Layer signal for the roBa keymap overlay app.
 *
 * Whenever the active layers change, tap F13 + <highest layer index> to the host
 * (layer 0 -> F13, 1 -> F14, ... 11 -> F24). The overlay app on the PC listens
 * for these keys, switches its display, and swallows them so other apps never
 * see them.
 *
 * The key is written straight into the HID report instead of being raised as a
 * keycode event, so it does not count as a "typed key" for hold-tap
 * require-prior-idle or the auto-mouse layer's idle timer.
 *
 * Enable with CONFIG_ROBA_LAYER_SIGNAL=y (central / right half only).
 */

#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

#include <zmk/event_manager.h>
#include <zmk/events/layer_state_changed.h>
#include <zmk/endpoints.h>
#include <zmk/hid.h>
#include <zmk/keymap.h>
#include <dt-bindings/zmk/hid_usage.h>
#include <dt-bindings/zmk/hid_usage_pages.h>

LOG_MODULE_DECLARE(zmk, CONFIG_ZMK_LOG_LEVEL);

#define SIGNAL_LAYERS 12 /* F13..F24 */

static void layer_signal_work_cb(struct k_work *work) {
    uint8_t layer = zmk_keymap_highest_layer_active();

    if (layer >= SIGNAL_LAYERS) {
        return;
    }

    /* Always send (no de-duplication): an overlay started late, or a host that
     * missed a report while reconnecting, catches up on the next change. */
    zmk_key_t key = HID_USAGE_KEY_KEYBOARD_F13 + layer;
    zmk_hid_keyboard_press(key);
    zmk_endpoints_send_report(HID_USAGE_KEY);
    zmk_hid_keyboard_release(key);
    zmk_endpoints_send_report(HID_USAGE_KEY);
    LOG_DBG("layer signal: layer %d", layer);
}

static K_WORK_DELAYABLE_DEFINE(layer_signal_work, layer_signal_work_cb);

static int layer_signal_listener(const zmk_event_t *eh) {
    /* Coalesce quick flips (hold-tap resolution, tri-layer) into one signal. */
    k_work_reschedule(&layer_signal_work, K_MSEC(CONFIG_ROBA_LAYER_SIGNAL_DELAY_MS));
    return ZMK_EV_EVENT_BUBBLE;
}

ZMK_LISTENER(roba_layer_signal, layer_signal_listener);
ZMK_SUBSCRIPTION(roba_layer_signal, zmk_layer_state_changed);
