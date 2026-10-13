package dev.aifirst.gestures;

import dev.aifirst.gestures.ShapeRecognizer.Point;
import dev.aifirst.gestures.ShapeRecognizer.Shape;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * Independent synthetic trajectory corpus; no Android runtime or test framework is required.
 * The human-like traces are authored fixtures, not recordings from physical hardware.
 */
public final class AdversarialGestureCases {
    private AdversarialGestureCases() {}

    public static int run() {
        Checks checks = new Checks();
        List<Point> triangle = sampledClosedPolygon(new double[][] {
                {-0.50, 0.43}, {0.51, 0.42}, {0.02, -0.51}
        }, 30, true);
        List<Point> square = sampledClosedPolygon(new double[][] {
                {-0.50, -0.50}, {0.50, -0.51}, {0.51, 0.50}, {-0.51, 0.49}
        }, 24, true);

        // Change device density independently of shape size, and start halfway along edges.
        for (int rotation : new int[] {0, 17, 61, 133}) {
            for (int start : new int[] {0, 17, 43}) {
                for (boolean reverse : new boolean[] {false, true}) {
                    for (double sizeDp : new double[] {180, 240, 320}) {
                        double density = sizeDp == 180 ? 1.0 : sizeDp == 240 ? 2.75 : 3.5;
                        String suffix = " rotation=" + rotation + " start=" + start
                                + " reverse=" + reverse + " sizeDp=" + sizeDp
                                + " density=" + density;
                        checks.expect("jittered triangle" + suffix, Shape.TRIANGLE,
                                transform(cyclic(triangle, start, reverse), rotation,
                                        sizeDp, density), 900, density);
                        checks.expect("jittered square" + suffix, Shape.SQUARE,
                                transform(cyclic(square, start, reverse), rotation,
                                        sizeDp, density), 1100, density);
                    }
                }
            }
        }

        // These anchors describe bowed hand-drawn sides and softly rounded corners.
        List<Point> handTriangle = sampledClosedPolygon(new double[][] {
                {-0.47, 0.43}, {-0.21, 0.44}, {0.04, 0.42}, {0.28, 0.43},
                {0.47, 0.42}, {0.50, 0.39}, {0.39, 0.18}, {0.27, -0.04},
                {0.16, -0.24}, {0.05, -0.44}, {0.02, -0.47}, {-0.01, -0.45},
                {-0.14, -0.22}, {-0.26, 0.02}, {-0.39, 0.24}, {-0.49, 0.40}
        }, 4, false);
        List<Point> handSquare = sampledClosedPolygon(new double[][] {
                {-0.47, -0.50}, {-0.21, -0.51}, {0.04, -0.49}, {0.28, -0.50},
                {0.47, -0.49}, {0.50, -0.46}, {0.51, -0.22}, {0.49, 0.04},
                {0.51, 0.29}, {0.49, 0.47}, {0.46, 0.50}, {0.21, 0.51},
                {-0.03, 0.49}, {-0.29, 0.50}, {-0.47, 0.49}, {-0.50, 0.46},
                {-0.51, 0.22}, {-0.49, -0.04}, {-0.51, -0.29}, {-0.50, -0.46}
        }, 4, false);
        for (int rotation : new int[] {0, 31, 103}) {
            for (boolean reverse : new boolean[] {false, true}) {
                checks.expect("hand-drawn rounded triangle " + rotation + "/" + reverse,
                        Shape.TRIANGLE, transform(cyclic(handTriangle, 11, reverse),
                                rotation, 230, 2.75), 1200, 2.75);
                checks.expect("hand-drawn rounded square " + rotation + "/" + reverse,
                        Shape.SQUARE, transform(cyclic(handSquare, 13, reverse),
                                rotation, 230, 2.75), 1200, 2.75);
            }
        }

        // A user can lift the finger a few pixels from the starting point.
        checks.expect("triangle small closure gap", Shape.TRIANGLE,
                transform(withClosureGap(triangle), 29, 220, 2.75), 950, 2.75);
        checks.expect("square small closure gap", Shape.SQUARE,
                transform(withClosureGap(square), 47, 220, 2.75), 1150, 2.75);

        for (int rotation : new int[] {0, 37, 91}) {
            checks.reject("circle " + rotation,
                    transform(ellipse(1, 1, 2), rotation, 240, 2.75));
            checks.reject("oval " + rotation,
                    transform(ellipse(1, 0.72, 2), rotation, 240, 2.75));
            checks.reject("near-circular superellipse " + rotation,
                    transform(ellipse(1, 1, 2.2), rotation, 240, 2.75));
        }

        checks.reject("open triangle missing last half-edge",
                transform(prefix(triangle, 0.83), 13, 240, 2.75));
        checks.reject("open square missing last half-edge",
                transform(prefix(square, 0.87), 23, 240, 2.75));
        checks.reject("three-sided open square",
                transform(prefix(square, 0.75), 0, 240, 2.75));
        checks.reject("triangle traced twice",
                transform(repeatLoop(triangle), 19, 240, 2.75));
        checks.reject("square traced twice",
                transform(repeatLoop(square), 19, 240, 2.75));
        checks.reject("triangle traced forward then backward",
                transform(retrace(triangle), 13, 240, 2.75));
        checks.reject("square traced forward then backward",
                transform(retrace(square), 13, 240, 2.75));
        checks.reject("bowtie crossing",
                transform(sampledClosedPolygon(new double[][] {
                        {-0.5, -0.5}, {0.5, 0.5}, {-0.5, 0.5}, {0.5, -0.5}
                }, 24, false), 11, 240, 2.75));
        checks.reject("figure eight", transform(figureEight(), 0, 240, 2.75));
        checks.reject("closed oscillating scribble", transform(scribble(), 0, 240, 2.75));
        checks.reject("long narrow rectangular scroll return",
                transform(sampledClosedPolygon(new double[][] {
                        {-0.04, -0.5}, {0.04, -0.5}, {0.04, 0.5}, {-0.04, 0.5}
                }, 24, true), 3, 450, 2.75));
        checks.reject("wide rectangle is not a square",
                transform(sampledClosedPolygon(new double[][] {
                        {-0.8, -0.3}, {0.8, -0.3}, {0.8, 0.3}, {-0.8, 0.3}
                }, 24, false), 19, 240, 2.75));
        checks.reject("five-point star",
                transform(star(), 0, 240, 2.75));
        checks.reject("pentagon",
                transform(regularPolygon(5), 9, 240, 2.75));
        checks.reject("hexagon",
                transform(regularPolygon(6), 9, 240, 2.75));

        checks.reject("empty stroke", Collections.emptyList());
        checks.reject("single tap", List.of(new Point(320, 700)));
        checks.reject("stationary pointer samples",
                Collections.nCopies(80, new Point(320, 700)));
        checks.reject("short swipe", List.of(new Point(320, 700), new Point(335, 703)));
        checks.reject("long scroll", straightStroke());
        checks.reject("tiny triangle", transform(triangle, 0, 3, 2.75));
        checks.reject("tiny square", transform(square, 0, 3, 2.75));
        checks.reject("NaN coordinate", List.of(new Point(Double.NaN, 100),
                new Point(100, 300), new Point(300, 300), new Point(Double.NaN, 100)));
        checks.reject("infinite coordinate", List.of(new Point(100, 100),
                new Point(Double.POSITIVE_INFINITY, 300), new Point(300, 300),
                new Point(100, 100)));
        return checks.count;
    }

    public static void main(String[] args) {
        System.out.println("Adversarial gesture assertions passed: " + run());
    }

    private static List<Point> sampledClosedPolygon(double[][] vertices, int samplesPerSide,
            boolean jitter) {
        List<Point> result = new ArrayList<>();
        for (int side = 0; side < vertices.length; side++) {
            double[] a = vertices[side];
            double[] b = vertices[(side + 1) % vertices.length];
            double dx = b[0] - a[0];
            double dy = b[1] - a[1];
            double length = Math.hypot(dx, dy);
            for (int sample = 0; sample < samplesPerSide; sample++) {
                double fraction = (double) sample / samplesPerSide;
                // Nonuniform velocity and deterministic lateral pen wobble.
                double t = fraction + 0.07 * Math.sin(2 * Math.PI * fraction);
                double wobble = jitter ? 0.007 * Math.sin(Math.PI * t)
                        * Math.sin(7 * Math.PI * t + side * 0.7) : 0;
                result.add(new Point(a[0] + t * dx - wobble * dy / length,
                        a[1] + t * dy + wobble * dx / length));
            }
        }
        result.add(result.get(0));
        return result;
    }

    private static List<Point> cyclic(List<Point> closed, int start, boolean reverse) {
        int size = closed.size() - 1;
        List<Point> result = new ArrayList<>();
        for (int index = 0; index < size; index++) {
            int source = Math.floorMod(start + (reverse ? -index : index), size);
            result.add(closed.get(source));
        }
        result.add(result.get(0));
        return result;
    }

    private static List<Point> transform(List<Point> source, double degrees, double sizeDp,
            double density) {
        double radians = Math.toRadians(degrees);
        double cosine = Math.cos(radians);
        double sine = Math.sin(radians);
        List<Point> result = new ArrayList<>();
        for (Point point : source) {
            result.add(new Point((420 + sizeDp * (point.x() * cosine - point.y() * sine))
                    * density, (620 + sizeDp * (point.x() * sine + point.y() * cosine))
                    * density));
        }
        return result;
    }

    private static List<Point> ellipse(double width, double height, double exponent) {
        List<Point> result = new ArrayList<>();
        for (int index = 0; index < 120; index++) {
            double angle = 2 * Math.PI * index / 120;
            double cosine = Math.cos(angle);
            double sine = Math.sin(angle);
            result.add(new Point(width * Math.copySign(Math.pow(Math.abs(cosine),
                    2 / exponent), cosine) / 2,
                    height * Math.copySign(Math.pow(Math.abs(sine), 2 / exponent), sine) / 2));
        }
        result.add(result.get(0));
        return result;
    }

    private static List<Point> withClosureGap(List<Point> source) {
        List<Point> result = new ArrayList<>(source);
        Point first = source.get(0);
        result.set(result.size() - 1, new Point(first.x() + 0.012, first.y() - 0.009));
        return result;
    }

    private static List<Point> prefix(List<Point> source, double fraction) {
        return new ArrayList<>(source.subList(0, (int) (source.size() * fraction)));
    }

    private static List<Point> repeatLoop(List<Point> source) {
        List<Point> result = new ArrayList<>(source);
        result.addAll(source.subList(1, source.size()));
        return result;
    }

    private static List<Point> retrace(List<Point> source) {
        List<Point> result = new ArrayList<>(source);
        for (int index = source.size() - 2; index >= 0; index--) {
            result.add(source.get(index));
        }
        return result;
    }

    private static List<Point> figureEight() {
        List<Point> result = new ArrayList<>();
        for (int index = 0; index <= 120; index++) {
            double angle = 2 * Math.PI * index / 120;
            result.add(new Point(0.5 * Math.sin(angle), 0.5 * Math.sin(2 * angle)));
        }
        return result;
    }

    private static List<Point> scribble() {
        List<Point> result = new ArrayList<>();
        for (int index = 0; index <= 150; index++) {
            double angle = 2 * Math.PI * index / 150;
            result.add(new Point(0.5 * Math.sin(3 * angle), 0.5 * Math.sin(5 * angle)));
        }
        return result;
    }

    private static List<Point> star() {
        double[][] vertices = new double[5][2];
        for (int index = 0; index < 5; index++) {
            double angle = 4 * Math.PI * index / 5;
            vertices[index] = new double[] {0.5 * Math.cos(angle), 0.5 * Math.sin(angle)};
        }
        return sampledClosedPolygon(vertices, 20, false);
    }

    private static List<Point> regularPolygon(int corners) {
        double[][] vertices = new double[corners][2];
        for (int index = 0; index < corners; index++) {
            double angle = 2 * Math.PI * index / corners;
            vertices[index] = new double[] {0.5 * Math.cos(angle), 0.5 * Math.sin(angle)};
        }
        return sampledClosedPolygon(vertices, 18, false);
    }

    private static List<Point> straightStroke() {
        List<Point> result = new ArrayList<>();
        for (int index = 0; index < 100; index++) {
            result.add(new Point(350 + Math.sin(index * 0.4), 300 + index * 7));
        }
        return result;
    }

    private static final class Checks {
        private final ShapeRecognizer recognizer = new ShapeRecognizer();
        private int count;

        void reject(String label, List<Point> trajectory) {
            expect(label, Shape.NONE, trajectory, 1200, 2.75);
        }

        void expect(String label, Shape expected, List<Point> trajectory, long durationMillis,
                double density) {
            Shape actual = recognizer.recognize(trajectory, durationMillis, density);
            count++;
            if (actual != expected) {
                throw new AssertionError(label + ": expected " + expected + " but got " + actual);
            }
        }
    }
}
