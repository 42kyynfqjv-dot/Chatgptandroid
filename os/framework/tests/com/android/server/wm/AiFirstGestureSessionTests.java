/* SPDX-License-Identifier: Apache-2.0 */
package com.android.server.wm;

import dev.aifirst.gestures.ShapeRecognizer;

/** Tests production stroke lifetime; Android window/telecom integration still needs a device. */
public final class AiFirstGestureSessionTests {
    private static final Object WINDOW = new Object();
    private static final AiFirstGestureSession.Context BASE = context(WINDOW, 5, 7, 0, 0, 0);
    private static int assertions;

    public static void main(String[] args) {
        completesOnceAndKeepsAnImmutableSnapshot();
        rejectsOrphanCanceledAndMultiPointerContinuations();
        rejectsFocusUserDisplayAndEnvironmentChanges();
        rejectsCrossingAnEdgeIncludingHistoricalSamples();
        rejectsClockPointerDeviceAndLengthChanges();
        rejectsIneligibleAndInvalidContexts();
        feedsTheProductionRecognizer();
        System.out.println("PASS: " + assertions + " OS gesture session assertions.");
    }

    private static AiFirstGestureSession.Context context(Object window, long focus, long environment,
            int user, int display, int rotation) {
        return new AiFirstGestureSession.Context(window, focus, environment, user, display,
                1000, 2000, rotation, 1.0, 50, 100, 950, 1900);
    }

    private static AiFirstGestureSession.Stroke event(AiFirstGestureSession session,
            AiFirstGestureSession.Phase phase, AiFirstGestureSession.Context context,
            long time, double x, double y) {
        return session.accept(phase, context, 3, 8, 1000, time, x, y);
    }

    private static void begin(AiFirstGestureSession session) {
        check(event(session, AiFirstGestureSession.Phase.DOWN, BASE, 1000, 200, 200) == null,
                "A down event alone cannot emit a shortcut");
    }

    private static AiFirstGestureSession.Stroke up(AiFirstGestureSession session,
            AiFirstGestureSession.Context context) {
        return event(session, AiFirstGestureSession.Phase.UP, context, 1600, 200, 200);
    }

    private static void completesOnceAndKeepsAnImmutableSnapshot() {
        AiFirstGestureSession session = new AiFirstGestureSession();
        begin(session);
        event(session, AiFirstGestureSession.Phase.MOVE, BASE, 1200, 400, 200);
        AiFirstGestureSession.Stroke stroke = up(session, BASE);
        check(stroke != null && stroke.context.same(BASE) && stroke.durationMillis == 600,
                "Only up returns the captured context and monotonic duration");
        check(stroke.points.size() == 3, "Stroke keeps all admitted samples");
        check(stroke.finishedAtMillis == 1600 && stroke.isFreshAt(1600, 1000),
                "Queued completion retains the absolute UP time");
        check(stroke.isFreshAt(2600, 1000) && !stroke.isFreshAt(2601, 1000),
                "A delayed callback or Binder call cannot launch an expired stroke");
        check(!stroke.isFreshAt(1599, 1000), "A future UP time is not eligible for launch");
        check(up(session, BASE) == null, "Duplicate up cannot dispatch twice");
        begin(session);
        check(stroke.points.size() == 3, "A new stroke cannot mutate a queued stroke");
        try {
            stroke.points.clear();
            throw new AssertionError("Stroke snapshot must be immutable");
        } catch (UnsupportedOperationException expected) {
            assertions++;
        }
    }

    private static void rejectsOrphanCanceledAndMultiPointerContinuations() {
        AiFirstGestureSession session = new AiFirstGestureSession();
        event(session, AiFirstGestureSession.Phase.MOVE, BASE, 1200, 400, 200);
        check(up(session, BASE) == null, "Orphan movement cannot begin a stroke");
        for (String reason : new String[]{"CANCEL", "second finger", "stylus", "obscured input"}) {
            begin(session);
            event(session, AiFirstGestureSession.Phase.CANCEL, BASE, 1200, 400, 200);
            event(session, AiFirstGestureSession.Phase.MOVE, BASE, 1300, 300, 300);
            check(up(session, BASE) == null, reason + " disarms until a fresh down");
        }
    }

    private static void rejectsFocusUserDisplayAndEnvironmentChanges() {
        AiFirstGestureSession.Context[] changed = {
            context(new Object(), 5, 7, 0, 0, 0),
            context(WINDOW, 6, 7, 0, 0, 0),
            context(WINDOW, 5, 8, 0, 0, 0),
            context(WINDOW, 5, 7, 10, 0, 0),
            context(WINDOW, 5, 7, 0, 1, 0),
            context(WINDOW, 5, 7, 0, 0, 1),
            new AiFirstGestureSession.Context(WINDOW, 5, 7, 0, 0, 1100, 2000, 0,
                    1, 50, 100, 950, 1900),
            new AiFirstGestureSession.Context(WINDOW, 5, 7, 0, 0, 1000, 2000, 0,
                    2, 50, 100, 950, 1900),
            new AiFirstGestureSession.Context(WINDOW, 5, 7, 0, 0, 1000, 2000, 0,
                    1, 51, 100, 950, 1900),
            null
        };
        for (AiFirstGestureSession.Context change : changed) {
            AiFirstGestureSession session = new AiFirstGestureSession();
            begin(session);
            event(session, AiFirstGestureSession.Phase.MOVE, change, 1200, 400, 200);
            check(up(session, BASE) == null, "An interruption cannot be repaired by returning to ChatGPT");
            check(!BASE.same(change), "Queued launch recheck rejects a changed eligibility snapshot");
        }
        AiFirstGestureSession session = new AiFirstGestureSession();
        begin(session);
        check(up(session, context(WINDOW, 6, 7, 0, 0, 0)) == null,
                "Focus away and back to the identical window still changes the focus epoch");
    }

    private static void rejectsCrossingAnEdgeIncludingHistoricalSamples() {
        for (double[] point : new double[][]{{49, 200}, {950, 200}, {200, 99}, {200, 1900},
                {Double.NaN, 200}, {200, Double.POSITIVE_INFINITY}}) {
            AiFirstGestureSession session = new AiFirstGestureSession();
            begin(session);
            event(session, AiFirstGestureSession.Phase.MOVE, BASE, 1100, point[0], point[1]);
            // The controller forwards each historical MOVE before the current UP.
            event(session, AiFirstGestureSession.Phase.MOVE, BASE, 1200, 300, 300);
            check(up(session, BASE) == null, "Leaving safe bounds invalidates the whole stroke");
        }
    }

    private static void rejectsClockPointerDeviceAndLengthChanges() {
        long[][] bad = {{4, 8, 1000, 1200}, {3, 9, 1000, 1200}, {3, 8, 999, 1200},
                {3, 8, 1000, 999}, {3, 8, 1000, 4001}};
        for (long[] values : bad) {
            AiFirstGestureSession session = new AiFirstGestureSession();
            begin(session);
            session.accept(AiFirstGestureSession.Phase.MOVE, BASE, (int) values[0],
                    (int) values[1], values[2], values[3], 400, 200);
            check(up(session, BASE) == null, "Pointer, device, down time and monotonic lifetime remain fixed");
        }
        AiFirstGestureSession session = new AiFirstGestureSession();
        begin(session);
        event(session, AiFirstGestureSession.Phase.MOVE, BASE, 1400, 400, 200);
        event(session, AiFirstGestureSession.Phase.MOVE, BASE, 1300, 300, 200);
        check(up(session, BASE) == null, "Historical sample order cannot run backwards");
        begin(session);
        check(event(session, AiFirstGestureSession.Phase.UP, BASE, 1179, 200, 200) == null,
                "A brief tap cannot become a shortcut");
        begin(session);
        for (int i = 1; i <= ShapeRecognizer.MAX_POINTS; i++) {
            event(session, AiFirstGestureSession.Phase.MOVE, BASE, 1000 + i, 200 + i % 10, 200);
        }
        check(up(session, BASE) == null, "Over-capacity strokes are rejected, never truncated");
    }

    private static void rejectsIneligibleAndInvalidContexts() {
        AiFirstGestureSession.Context[] invalid = {
            null, context(null, 5, 7, 0, 0, 0), context(WINDOW, 5, 7, 10, 0, 0),
            context(WINDOW, 5, 7, 0, 1, 0), context(WINDOW, 5, 7, 0, 0, -1),
            new AiFirstGestureSession.Context(WINDOW, 5, 7, 0, 0, 1000, 2000, 0,
                    Double.NaN, 50, 100, 950, 1900),
            new AiFirstGestureSession.Context(WINDOW, 5, 7, 0, 0, 1000, 2000, 0,
                    1, 950, 100, 50, 1900)
        };
        for (AiFirstGestureSession.Context context : invalid) {
            AiFirstGestureSession session = new AiFirstGestureSession();
            event(session, AiFirstGestureSession.Phase.DOWN, context, 1000, 200, 200);
            check(up(session, BASE) == null, "An ineligible or invalid down cannot arm later");
        }
    }

    private static void feedsTheProductionRecognizer() {
        AiFirstGestureSession session = new AiFirstGestureSession();
        begin(session);
        double[][] vertices = {{200, 200}, {500, 200}, {500, 500}, {200, 500}, {200, 200}};
        int sample = 0;
        AiFirstGestureSession.Stroke stroke = null;
        for (int edge = 0; edge < 4; edge++) {
            for (int step = 1; step <= 12; step++) {
                double f = step / 12.0;
                sample++;
                stroke = event(session, sample == 48 ? AiFirstGestureSession.Phase.UP
                        : AiFirstGestureSession.Phase.MOVE, BASE, 1000 + sample * 15,
                        vertices[edge][0] + f * (vertices[edge + 1][0] - vertices[edge][0]),
                        vertices[edge][1] + f * (vertices[edge + 1][1] - vertices[edge][1]));
            }
        }
        check(stroke != null && new ShapeRecognizer().recognize(stroke.points,
                stroke.durationMillis, stroke.context.density) == ShapeRecognizer.Shape.SQUARE,
                "The production observer session supplies a completed stroke to the actual classifier");
    }

    private static void check(boolean condition, String explanation) {
        if (!condition) throw new AssertionError(explanation);
        assertions++;
    }
}
