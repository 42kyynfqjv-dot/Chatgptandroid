package dev.aifirst.gestures;

import dev.aifirst.gestures.ShapeRecognizer.Point;
import dev.aifirst.gestures.ShapeRecognizer.Shape;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/** Public-API regression tests. Fixtures are synthetic, not device-validation evidence. */
public final class ShapeRecognizerTests {
    private static int assertions;
    private static final ShapeRecognizer RECOGNIZER = new ShapeRecognizer();

    public static void main(String[] args) {
        assertions += AdversarialGestureCases.run();
        boundsAndInvalidStreams();
        smallShapesDoNotGrowWhenRotated();
        partialRetracingDoesNotBecomeAPolygon();
        samplingAndStationaryPoints();
        System.out.println("PASS: " + assertions + " synthetic gesture assertions (geometry only; no touch interception verified).");
    }

    private static void boundsAndInvalidStreams() {
        List<Point> square = stroke(new double[][] {{0, 0}, {220, 0}, {220, 220}, {0, 220}, {0, 0}}, 25);
        expect("reference square", Shape.SQUARE, square, 1000, 1);
        expect("null path", Shape.NONE, null, 1000, 1);
        List<Point> nullPoint = new ArrayList<>(square);
        nullPoint.set(30, null);
        expect("null inside otherwise valid path", Shape.NONE, nullPoint, 1000, 1);
        for (double value : new double[] {Double.NaN, Double.POSITIVE_INFINITY, Double.NEGATIVE_INFINITY, 1e308}) {
            List<Point> malformed = new ArrayList<>(square);
            malformed.set(30, new Point(value, 50));
            expect("invalid coordinate inside real shape " + value, Shape.NONE, malformed, 1000, 1);
        }
        for (double density : new double[] {0, -1, Double.NaN, Double.POSITIVE_INFINITY}) {
            expect("invalid display density " + density, Shape.NONE, square, 1000, density);
        }
        for (long duration : new long[] {-1000, 0, 30, 15_000, Long.MAX_VALUE}) {
            expect("not a bounded human stroke " + duration, Shape.NONE, square, duration, 1);
        }
        List<Point> excessive = stroke(new double[][] {{0, 0}, {220, 0}, {220, 220}, {0, 220}, {0, 0}}, 140);
        expect("overflow must reject rather than truncate a valid-looking square", Shape.NONE, excessive, 1000, 1);
        expect("physical size uses display density", Shape.NONE, square, 1000, 4);
    }

    private static void smallShapesDoNotGrowWhenRotated() {
        List<Point> smallSquare = stroke(new double[][] {{0, 0}, {70, 0}, {70, 70}, {0, 70}, {0, 0}}, 20);
        List<Point> normalSquare = stroke(new double[][] {{0, 0}, {190, 0}, {190, 190}, {0, 190}, {0, 0}}, 20);
        for (int degrees = 0; degrees < 180; degrees += 15) {
            expect("small square rotated " + degrees, Shape.NONE, rotate(smallSquare, degrees), 900, 1);
            expect("normal square rotated " + degrees, Shape.SQUARE, rotate(normalSquare, degrees), 900, 1);
        }
    }

    private static void partialRetracingDoesNotBecomeAPolygon() {
        expect("visibly open square cannot borrow a long automatic closing segment", Shape.NONE,
                stroke(new double[][] {{0, 0}, {240, 0}, {240, 240}, {0, 240}, {0, 40}}, 20),
                1200, 1);
        expect("small lift-off gap is tolerated", Shape.SQUARE,
                stroke(new double[][] {{0, 0}, {240, 0}, {240, 240}, {0, 240}, {0, 12}}, 20),
                1200, 1);
        expect("square with an edge partially retraced", Shape.NONE,
                stroke(new double[][] {{0, 0}, {180, 0}, {110, 0}, {240, 0}, {240, 240}, {0, 240}, {0, 0}}, 16),
                1200, 1);
        expect("triangle with an edge partially retraced", Shape.NONE,
                stroke(new double[][] {{0, 210}, {140, 210}, {90, 210}, {240, 210}, {120, 0}, {0, 210}}, 16),
                1200, 1);
    }

    private static void samplingAndStationaryPoints() {
        List<Point> square = stroke(new double[][] {{0, 0}, {240, 0}, {240, 240}, {0, 240}, {0, 0}}, 15);
        List<Point> pauses = new ArrayList<>();
        for (Point point : square) { pauses.addAll(Collections.nCopies(3, point)); }
        expect("stationary samples at points do not invent retracing", Shape.SQUARE, pauses, 1300, 1);
        List<Point> reverse = new ArrayList<>(pauses);
        Collections.reverse(reverse);
        expect("stationary samples reversed", Shape.SQUARE, reverse, 1300, 1);
    }

    private static List<Point> stroke(double[][] vertices, int perSegment) {
        List<Point> points = new ArrayList<>();
        for (int segment = 0; segment < vertices.length - 1; segment++) {
            double[] a = vertices[segment], b = vertices[segment + 1];
            for (int sample = 0; sample < perSegment; sample++) {
                double t = (double) sample / perSegment;
                points.add(new Point(400 + a[0] + t * (b[0] - a[0]), 600 + a[1] + t * (b[1] - a[1])));
            }
        }
        double[] end = vertices[vertices.length - 1];
        points.add(new Point(400 + end[0], 600 + end[1]));
        return points;
    }

    private static List<Point> rotate(List<Point> points, double degrees) {
        double angle = Math.toRadians(degrees), cos = Math.cos(angle), sin = Math.sin(angle);
        List<Point> result = new ArrayList<>();
        for (Point point : points) {
            result.add(new Point(point.x() * cos - point.y() * sin, point.x() * sin + point.y() * cos));
        }
        return result;
    }

    private static void expect(String label, Shape expected, List<Point> points, long duration, double density) {
        Shape actual = RECOGNIZER.recognize(points, duration, density);
        if (actual != expected) { throw new AssertionError(label + ": expected " + expected + ", got " + actual); }
        assertions++;
    }
}
