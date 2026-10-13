/* SPDX-License-Identifier: Apache-2.0 */
package com.android.server.wm;

import java.util.ArrayList;
import java.util.List;

import dev.aifirst.gestures.ShapeRecognizer;

/** Bounded, dependency-free stroke lifetime. This class never launches or consumes input. */
final class AiFirstGestureSession {
    enum Phase { DOWN, MOVE, UP, CANCEL }

    static final class Context {
        final Object window;
        final long focusEpoch;
        final long environmentEpoch;
        final int userId;
        final int displayId;
        final int width;
        final int height;
        final int rotation;
        final double density;
        final int left;
        final int top;
        final int right;
        final int bottom;

        Context(Object window, long focusEpoch, long environmentEpoch, int userId, int displayId,
                int width, int height, int rotation, double density,
                int left, int top, int right, int bottom) {
            this.window = window;
            this.focusEpoch = focusEpoch;
            this.environmentEpoch = environmentEpoch;
            this.userId = userId;
            this.displayId = displayId;
            this.width = width;
            this.height = height;
            this.rotation = rotation;
            this.density = density;
            this.left = left;
            this.top = top;
            this.right = right;
            this.bottom = bottom;
        }

        Context withEnvironmentEpoch(long epoch) {
            return new Context(window, focusEpoch, epoch, userId, displayId, width, height,
                    rotation, density, left, top, right, bottom);
        }

        boolean valid() {
            return window != null && userId == 0 && displayId == 0 && width > 0 && height > 0
                    && rotation >= 0 && rotation <= 3 && Double.isFinite(density) && density > 0
                    && left >= 0 && top >= 0 && right <= width && bottom <= height
                    && left < right && top < bottom;
        }

        boolean same(Context other) {
            return other != null && window == other.window && focusEpoch == other.focusEpoch
                    && environmentEpoch == other.environmentEpoch && userId == other.userId
                    && displayId == other.displayId && width == other.width && height == other.height
                    && rotation == other.rotation && Double.compare(density, other.density) == 0
                    && left == other.left && top == other.top
                    && right == other.right && bottom == other.bottom;
        }

        boolean contains(double x, double y) {
            return Double.isFinite(x) && Double.isFinite(y)
                    && x >= left && x < right && y >= top && y < bottom;
        }
    }

    static final class Stroke {
        final Context context;
        final List<ShapeRecognizer.Point> points;
        final long durationMillis;
        final long finishedAtMillis;

        Stroke(Context context, List<ShapeRecognizer.Point> points, long durationMillis,
                long finishedAtMillis) {
            this.context = context;
            this.points = List.copyOf(points);
            this.durationMillis = durationMillis;
            this.finishedAtMillis = finishedAtMillis;
        }

        boolean isFreshAt(long nowMillis, long maximumAgeMillis) {
            return maximumAgeMillis >= 0 && nowMillis >= finishedAtMillis
                    && nowMillis - finishedAtMillis <= maximumAgeMillis;
        }
    }

    private final ArrayList<ShapeRecognizer.Point> points = new ArrayList<>();
    private Context context;
    private int pointerId;
    private int deviceId;
    private long downTime;
    private long lastTime;

    /** Pass CANCEL for non-finger, multiple-pointer, canceled, or otherwise invalid streams. */
    Stroke accept(Phase phase, Context now, int pointer, int device, long down, long time,
            double x, double y) {
        if (phase == Phase.CANCEL || now == null || !now.valid() || !now.contains(x, y)) {
            reset();
            return null;
        }
        if (phase == Phase.DOWN) {
            reset();
            if (down < 0 || time < down || time - down > ShapeRecognizer.MAX_DURATION_MILLIS) {
                return null;
            }
            context = now;
            pointerId = pointer;
            deviceId = device;
            downTime = down;
            lastTime = time;
        } else if (context == null || !context.same(now) || pointer != pointerId
                || device != deviceId || down != downTime || time < lastTime
                || time < downTime || time - downTime > ShapeRecognizer.MAX_DURATION_MILLIS) {
            reset();
            return null;
        }
        if (points.size() >= ShapeRecognizer.MAX_POINTS) {
            reset();
            return null;
        }
        lastTime = time;
        points.add(new ShapeRecognizer.Point(x, y));
        if (phase != Phase.UP) {
            return null;
        }
        Stroke result = time - downTime >= ShapeRecognizer.MIN_DURATION_MILLIS
                ? new Stroke(context, points, time - downTime, time) : null;
        reset();
        return result;
    }

    void reset() {
        context = null;
        points.clear();
    }
}
