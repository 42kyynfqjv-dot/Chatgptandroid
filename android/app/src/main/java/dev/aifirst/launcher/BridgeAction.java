package dev.aifirst.launcher;

import android.os.SystemClock;

import org.json.JSONException;
import org.json.JSONObject;

import java.util.Iterator;
import java.util.Locale;
import java.util.Set;

final class BridgeAction {
    final String id;
    final String action;
    final String app;
    final int hour;
    final int minute;
    final String label;
    final double expiresAt;
    private final ActionDeadline deadline;

    BridgeAction(JSONObject json) throws JSONException {
        id = SafetyPolicy.requestId(string(json, "id"));
        action = string(json, "action");
        if (!"awaiting_confirmation".equals(string(json, "status"))) {
            throw new IllegalArgumentException("Relay did not claim this request.");
        }
        Object expiry = json.get("expires_at");
        if (!(expiry instanceof Number) || !Double.isFinite(((Number) expiry).doubleValue())) {
            throw new IllegalArgumentException("Invalid request expiry.");
        }
        expiresAt = ((Number) expiry).doubleValue();
        deadline = new ActionDeadline(expiresAt, System.currentTimeMillis(), SystemClock.elapsedRealtime());
        JSONObject params = json.getJSONObject("params");
        if ("open_app".equals(action)) {
            exactKeys(params, Set.of("app"));
            app = SafetyPolicy.app(string(params, "app"));
            hour = 0;
            minute = 0;
            label = "";
        } else if ("set_alarm".equals(action)) {
            exactKeys(params, Set.of("hour", "minute", "label"));
            app = "clock";
            hour = SafetyPolicy.integer(params.get("hour"), 0, 23);
            minute = SafetyPolicy.integer(params.get("minute"), 0, 59);
            label = SafetyPolicy.label(string(params, "label"));
        } else {
            throw new IllegalArgumentException("Unsupported action.");
        }
    }

    boolean expired() {
        return deadline.expired(expiresAt, System.currentTimeMillis(), SystemClock.elapsedRealtime());
    }

    String summary() {
        if ("open_app".equals(action)) { return "Open " + app + "."; }
        return String.format(Locale.ROOT, "Ask Clock to create an alarm at %02d:%02d (phone local time).\nLabel: %s",
                hour, minute, label.isEmpty() ? "(none)" : label);
    }

    private static String string(JSONObject json, String key) throws JSONException {
        Object value = json.get(key);
        if (!(value instanceof String)) { throw new IllegalArgumentException("Invalid text field."); }
        return (String) value;
    }

    private static void exactKeys(JSONObject json, Set<String> expected) {
        if (json.length() != expected.size()) { throw new IllegalArgumentException("Unexpected parameters."); }
        Iterator<String> keys = json.keys();
        while (keys.hasNext()) {
            if (!expected.contains(keys.next())) { throw new IllegalArgumentException("Unexpected parameters."); }
        }
    }
}
