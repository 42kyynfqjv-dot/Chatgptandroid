/* SPDX-License-Identifier: Apache-2.0 */
package com.android.server.wm;

import android.content.ActivityNotFoundException;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.database.ContentObserver;
import android.os.Handler;
import android.os.SystemClock;
import android.os.UserHandle;
import android.os.UserManager;
import android.provider.Settings;
import android.provider.Telephony;
import android.telecom.TelecomManager;
import android.telephony.TelephonyManager;
import android.util.Slog;
import android.view.Display;
import android.view.InputDevice;
import android.view.MotionEvent;
import android.view.WindowManagerPolicyConstants.PointerEventListener;

import dev.aifirst.gestures.ShapeRecognizer;

/**
 * Development-only OS observer. Input continues to ChatGPT unchanged; no pilfering, injection,
 * buffering for arbitration, accessibility service, UI scraping, or coordinate logging.
 */
final class AiFirstShapeController implements PointerEventListener {
    static final String SETTING = "aifirst_shape_gestures_enabled";
    private static final String TAG = "AiFirstShapeController";
    private static final long MAX_EVENT_AGE_MILLIS = 1000;

    interface SnapshotProvider {
        /** Returns null unless the actual focused window and display are eligible, under WMS lock. */
        AiFirstGestureSession.Context snapshot();
    }

    private final Context context;
    private final Handler handler;
    private final SnapshotProvider provider;
    private final AiFirstGestureSession session = new AiFirstGestureSession();
    private final ShapeRecognizer recognizer = new ShapeRecognizer();
    private final ContentObserver settingsObserver;
    private final BroadcastReceiver interruptionReceiver;
    private volatile boolean disposed;
    // All following state is confined to the UI handler used by PointerEventDispatcher.
    private boolean enabled;
    private boolean observerRegistered;
    private boolean receiverRegistered;
    private long environmentEpoch;
    private long dispatchGeneration;

    AiFirstShapeController(Context context, Handler handler, SnapshotProvider provider) {
        this.context = context;
        this.handler = handler;
        this.provider = provider;
        settingsObserver = new ContentObserver(handler) {
            @Override public void onChange(boolean selfChange) {
                invalidate();
                enabled = readEnabled();
            }
        };
        interruptionReceiver = new BroadcastReceiver() {
            @Override public void onReceive(Context ignored, Intent intent) {
                // These protected system broadcasts also invalidate an away-and-back interruption.
                invalidate();
            }
        };
        // DisplayPolicy construction can hold the WMS lock. Register with other services later.
        handler.post(this::start);
    }

    private void start() {
        if (disposed) return;
        try {
            context.getContentResolver().registerContentObserver(
                    Settings.Secure.getUriFor(SETTING), false, settingsObserver, UserHandle.USER_SYSTEM);
            observerRegistered = true;
            IntentFilter interruptions = new IntentFilter(TelephonyManager.ACTION_PHONE_STATE_CHANGED);
            interruptions.addAction(Intent.ACTION_SCREEN_OFF);
            interruptions.addAction(Intent.ACTION_USER_SWITCHED);
            context.registerReceiverAsUser(interruptionReceiver, UserHandle.ALL,
                    interruptions, null, handler);
            receiverRegistered = true;
            enabled = readEnabled();
        } catch (RuntimeException exception) {
            enabled = false;
            Slog.w(TAG, "Gesture observer setup unavailable; shortcuts remain disabled.");
            stop();
        }
    }

    void stop() {
        disposed = true;
        handler.post(() -> {
            invalidate();
            enabled = false;
            if (observerRegistered) {
                try {
                    context.getContentResolver().unregisterContentObserver(settingsObserver);
                } catch (RuntimeException exception) {
                    Slog.w(TAG, "Gesture settings observer cleanup unavailable.");
                }
                observerRegistered = false;
            }
            if (receiverRegistered) {
                try {
                    context.unregisterReceiver(interruptionReceiver);
                } catch (RuntimeException exception) {
                    Slog.w(TAG, "Gesture interruption observer cleanup unavailable.");
                }
                receiverRegistered = false;
            }
        });
    }

    private void invalidate() {
        environmentEpoch++;
        dispatchGeneration++;
        session.reset();
    }

    @Override public void onPointerEvent(MotionEvent event) {
        try {
            observe(event);
        } catch (RuntimeException exception) {
            // Optional input observation must never take down system_server.
            enabled = false;
            invalidate();
            Slog.w(TAG, "Gesture observation failed; shortcuts disabled until settings change.");
        }
    }

    private void observe(MotionEvent event) {
        if (disposed || !enabled) {
            session.reset();
            return;
        }
        int action = event.getActionMasked();
        if (action == MotionEvent.ACTION_DOWN) dispatchGeneration++;
        if (event.getDisplayId() != Display.DEFAULT_DISPLAY
                || !event.isFromSource(InputDevice.SOURCE_TOUCHSCREEN)
                || event.getPointerCount() != 1
                || event.getHistorySize() > ShapeRecognizer.MAX_POINTS
                || event.getToolType(0) != MotionEvent.TOOL_TYPE_FINGER
                || (event.getFlags() & (MotionEvent.FLAG_WINDOW_IS_OBSCURED
                        | MotionEvent.FLAG_WINDOW_IS_PARTIALLY_OBSCURED
                        | MotionEvent.FLAG_CANCELED)) != 0
                || (action != MotionEvent.ACTION_DOWN && action != MotionEvent.ACTION_MOVE
                        && action != MotionEvent.ACTION_UP)) {
            invalidate();
            return;
        }
        long now = SystemClock.uptimeMillis();
        if (event.getEventTime() > now || now - event.getEventTime() > MAX_EVENT_AGE_MILLIS) {
            invalidate();
            return;
        }
        AiFirstGestureSession.Context snapshot = snapshot();
        if (snapshot == null) {
            invalidate();
            return;
        }
        int pointer = event.getPointerId(0);
        int device = event.getDeviceId();
        long down = event.getDownTime();
        if (action != MotionEvent.ACTION_DOWN) {
            // History must pass the same edge/context bounds; checking only the last point is unsafe.
            for (int index = 0; index < event.getHistorySize(); index++) {
                session.accept(AiFirstGestureSession.Phase.MOVE, snapshot, pointer, device, down,
                        event.getHistoricalEventTime(index), event.getHistoricalX(0, index),
                        event.getHistoricalY(0, index));
            }
        }
        AiFirstGestureSession.Phase phase = action == MotionEvent.ACTION_DOWN
                ? AiFirstGestureSession.Phase.DOWN : action == MotionEvent.ACTION_UP
                        ? AiFirstGestureSession.Phase.UP : AiFirstGestureSession.Phase.MOVE;
        AiFirstGestureSession.Stroke stroke = session.accept(phase, snapshot, pointer, device,
                down, event.getEventTime(), event.getX(0), event.getY(0));
        if (stroke != null) {
            long generation = dispatchGeneration;
            handler.post(() -> complete(stroke, generation));
        }
    }

    private AiFirstGestureSession.Context snapshot() {
        AiFirstGestureSession.Context state = provider.snapshot();
        return state == null ? null : state.withEnvironmentEpoch(environmentEpoch);
    }

    private void complete(AiFirstGestureSession.Stroke stroke, long generation) {
        if (disposed || generation != dispatchGeneration || !enabled
                || !stroke.isFreshAt(SystemClock.uptimeMillis(), MAX_EVENT_AGE_MILLIS)) return;
        try {
            ShapeRecognizer.Shape shape = recognizer.recognize(
                    stroke.points, stroke.durationMillis, stroke.context.density);
            if (shape == ShapeRecognizer.Shape.NONE) return;
            Intent intent;
            if (shape == ShapeRecognizer.Shape.TRIANGLE) {
                intent = new Intent(Intent.ACTION_DIAL); // No recipient and no call placement.
            } else if (shape == ShapeRecognizer.Shape.SQUARE) {
                String smsPackage = Telephony.Sms.getDefaultSmsPackage(context);
                if (smsPackage == null) return;
                intent = context.getPackageManager().getLaunchIntentForPackage(smsPackage);
                if (intent == null) return;
            } else {
                return;
            }
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            UserManager users = context.getSystemService(UserManager.class);
            // Calls, settings and package resolution can cross Binder; do none under the WMS lock.
            if (disposed || generation != dispatchGeneration || !readEnabled() || !callIdle()
                    || users == null || !users.isUserUnlocked(UserHandle.SYSTEM)) return;
            // Recheck real focus, focus epoch, user, keyguard, shade, IME, display and safe bounds last.
            if (!stroke.context.same(snapshot())) return;
            // Binder or WMS-lock delay must not turn an old shape into a surprise later launch.
            if (!stroke.isFreshAt(SystemClock.uptimeMillis(), MAX_EVENT_AGE_MILLIS)) return;
            context.startActivityAsUser(intent, UserHandle.SYSTEM);
        } catch (ActivityNotFoundException | SecurityException exception) {
            Slog.w(TAG, "Native app handoff unavailable; no call or message was sent.");
        } catch (RuntimeException exception) {
            // Failure of this optional feature must not crash the system-server input observer.
            Slog.w(TAG, "Native app handoff could not be checked; shortcut canceled.");
        }
    }

    private boolean readEnabled() {
        try {
            return !disposed && Settings.Secure.getIntForUser(context.getContentResolver(),
                    SETTING, 0, UserHandle.USER_SYSTEM) == 1;
        } catch (RuntimeException exception) {
            return false;
        }
    }

    private boolean callIdle() {
        try {
            TelecomManager telecom = context.getSystemService(TelecomManager.class);
            return telecom != null && !telecom.isInCall() && !telecom.isRinging();
        } catch (RuntimeException exception) {
            return false;
        }
    }
}
