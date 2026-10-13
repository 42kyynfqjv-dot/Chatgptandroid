package dev.aifirst.gestures;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

/**
 * Conservative, geometry-only recognizer for one completed single-finger stroke.
 * This class does not consume touch events or infer whether the user intended a system gesture.
 * The caller must discard cancelled/multitouch streams and must never submit a truncated stream.
 */
public final class ShapeRecognizer {
    public enum Shape { NONE, TRIANGLE, SQUARE }

    public record Point(double x, double y) { }

    public static final int MAX_POINTS = 512;
    public static final long MIN_DURATION_MILLIS = 180;
    public static final long MAX_DURATION_MILLIS = 3000;
    public static final double MIN_SPAN_DP = 96.0;
    public static final double MAX_CLOSURE_GAP_DP = 24.0;
    private static final int RESAMPLED_POINTS = 120;
    private static final double EPSILON = 1e-9;

    /**
     * @param samples completed stroke, including its down and up positions, in screen pixels
     * @param durationMillis elapsed event time from down to up, measured with a monotonic clock
     * @param pixelsPerDp Android display density (not font scale)
     * @return NONE for invalid, out-of-bounds, ambiguous, or unsupported paths
     */
    public Shape recognize(List<Point> samples, long durationMillis, double pixelsPerDp) {
        if (samples == null || samples.size() < 8 || samples.size() > MAX_POINTS
                || durationMillis < MIN_DURATION_MILLIS || durationMillis > MAX_DURATION_MILLIS
                || !Double.isFinite(pixelsPerDp) || pixelsPerDp <= 0 || pixelsPerDp > 10) {
            return Shape.NONE;
        }
        double minX = Double.POSITIVE_INFINITY;
        double minY = Double.POSITIVE_INFINITY;
        double maxX = Double.NEGATIVE_INFINITY;
        double maxY = Double.NEGATIVE_INFINITY;
        for (Point point : samples) {
            if (point == null || !Double.isFinite(point.x) || !Double.isFinite(point.y)
                    || Math.abs(point.x) > 1_000_000 || Math.abs(point.y) > 1_000_000) {
                return Shape.NONE;
            }
            minX = Math.min(minX, point.x);
            minY = Math.min(minY, point.y);
            maxX = Math.max(maxX, point.x);
            maxY = Math.max(maxY, point.y);
        }
        double width = maxX - minX;
        double height = maxY - minY;
        if (Math.min(width, height) < MIN_SPAN_DP * pixelsPerDp) { return Shape.NONE; }
        double diagonal = Math.hypot(width, height);
        if (distance(samples.get(0), samples.get(samples.size() - 1))
                > Math.min(diagonal * 0.08, MAX_CLOSURE_GAP_DP * pixelsPerDp)) {
            return Shape.NONE;
        }

        // Remove stationary sampling jitter in physical display units before equal-distance sampling.
        List<Point> normalized = new ArrayList<>();
        Point previous = null;
        for (Point point : samples) {
            if (previous == null || distance(previous, point) >= pixelsPerDp) {
                normalized.add(new Point((point.x - minX) / diagonal, (point.y - minY) / diagonal));
                previous = point;
            }
        }
        if (normalized.size() < 8) { return Shape.NONE; }
        List<Point> path = smooth(resampleClosed(normalized));
        List<Point> hull = convexHull(path);
        if (hull.size() < 3) { return Shape.NONE; }
        // A rotated small square must not become "large" just because its axis-aligned box grows.
        if (minimumWidth(hull) * diagonal < MIN_SPAN_DP * pixelsPerDp) { return Shape.NONE; }
        double extent = diameter(hull);
        if (extent <= EPSILON || distance(samples.get(0), samples.get(samples.size() - 1))
                > 0.08 * diagonal * extent) {
            return Shape.NONE;
        }
        // Longest hull chord is orientation-independent; polygon error tolerances use this scale.
        path = scale(path, 1 / extent);
        hull = scale(hull, 1 / extent);
        double hullArea = Math.abs(signedArea(hull));
        if (hullArea < 0.12) { return Shape.NONE; }

        // Retracing, multiple laps, crossings and deep concavities are not polygon gestures.
        double hullPerimeter = perimeter(hull);
        double pathPerimeter = perimeter(path);
        double areaRatio = Math.abs(signedArea(path)) / hullArea;
        if (pathPerimeter / hullPerimeter > 1.16 || areaRatio < 0.86 || areaRatio > 1.08
                || hasCrossing(path)) {
            return Shape.NONE;
        }

        List<Point> triangle = simplifyHull(hull, 3);
        if (fitsPolygon(path, triangle, hullArea, 0.86) && isTriangle(triangle)) {
            return Shape.TRIANGLE;
        }
        List<Point> square = simplifyHull(hull, 4);
        if (square.size() == 4 && fitsPolygon(path, square, hullArea, 0.88) && isSquare(square)) {
            return Shape.SQUARE;
        }
        return Shape.NONE;
    }

    private static List<Point> resampleClosed(List<Point> points) {
        double length = perimeter(points);
        List<Point> result = new ArrayList<>(RESAMPLED_POINTS);
        int edge = 0;
        double traversed = 0;
        double edgeLength = distance(points.get(0), points.get(1));
        for (int i = 0; i < RESAMPLED_POINTS; i++) {
            double target = length * i / RESAMPLED_POINTS;
            while (edge < points.size() - 1 && traversed + edgeLength < target) {
                traversed += edgeLength;
                edge++;
                edgeLength = distance(points.get(edge), points.get((edge + 1) % points.size()));
            }
            Point a = points.get(edge);
            Point b = points.get((edge + 1) % points.size());
            double fraction = edgeLength > EPSILON ? (target - traversed) / edgeLength : 0;
            result.add(new Point(a.x + (b.x - a.x) * fraction, a.y + (b.y - a.y) * fraction));
        }
        return result;
    }

    private static List<Point> smooth(List<Point> points) {
        List<Point> result = new ArrayList<>(points.size());
        for (int i = 0; i < points.size(); i++) {
            Point previous = points.get((i + points.size() - 1) % points.size());
            Point point = points.get(i);
            Point next = points.get((i + 1) % points.size());
            result.add(new Point((previous.x + 2 * point.x + next.x) / 4,
                    (previous.y + 2 * point.y + next.y) / 4));
        }
        return result;
    }

    private static List<Point> scale(List<Point> points, double factor) {
        List<Point> result = new ArrayList<>(points.size());
        for (Point point : points) { result.add(new Point(point.x * factor, point.y * factor)); }
        return result;
    }

    private static double diameter(List<Point> points) {
        double longest = 0;
        for (int i = 0; i < points.size(); i++) {
            for (int j = i + 1; j < points.size(); j++) {
                longest = Math.max(longest, distance(points.get(i), points.get(j)));
            }
        }
        return longest;
    }

    private static double minimumWidth(List<Point> hull) {
        double minimum = Double.POSITIVE_INFINITY;
        for (int i = 0; i < hull.size(); i++) {
            Point a = hull.get(i);
            Point b = hull.get((i + 1) % hull.size());
            double edgeLength = distance(a, b);
            if (edgeLength <= EPSILON) { continue; }
            double farthest = 0;
            for (Point point : hull) {
                farthest = Math.max(farthest, Math.abs(cross(a, b, point)) / edgeLength);
            }
            minimum = Math.min(minimum, farthest);
        }
        return minimum;
    }

    private static List<Point> convexHull(List<Point> points) {
        List<Point> sorted = new ArrayList<>(points);
        sorted.sort(Comparator.comparingDouble(Point::x).thenComparingDouble(Point::y));
        List<Point> hull = new ArrayList<>();
        for (Point point : sorted) {
            while (hull.size() >= 2 && cross(hull.get(hull.size() - 2), hull.get(hull.size() - 1), point) <= EPSILON) {
                hull.remove(hull.size() - 1);
            }
            hull.add(point);
        }
        int lowerSize = hull.size();
        for (int i = sorted.size() - 2; i >= 0; i--) {
            Point point = sorted.get(i);
            while (hull.size() > lowerSize && cross(hull.get(hull.size() - 2), hull.get(hull.size() - 1), point) <= EPSILON) {
                hull.remove(hull.size() - 1);
            }
            hull.add(point);
        }
        if (!hull.isEmpty()) { hull.remove(hull.size() - 1); }
        return hull;
    }

    /**
     * Find the largest inscribed polygon instead of greedily deleting rounded corners.
     * For a quadrilateral, each diagonal independently selects the farthest point on each side.
     * At most 120 hull points keep both searches bounded by O(n^3), without allocation per candidate.
     */
    private static List<Point> simplifyHull(List<Point> hull, int count) {
        int size = hull.size();
        if (size <= count) { return new ArrayList<>(hull); }
        int[] best = new int[count];
        double bestArea = -1;
        for (int i = 0; i < size - 2; i++) {
            for (int k = i + 2; k < size; k++) {
                int inside = -1;
                double insideArea = -1;
                for (int j = i + 1; j < k; j++) {
                    double area = cross(hull.get(i), hull.get(j), hull.get(k));
                    if (area > insideArea) { insideArea = area; inside = j; }
                }
                if (count == 3) {
                    if (insideArea > bestArea) {
                        bestArea = insideArea;
                        best[0] = i; best[1] = inside; best[2] = k;
                    }
                    continue;
                }
                int outside = -1;
                double outsideArea = -1;
                for (int offset = k + 1; offset < size + i; offset++) {
                    int j = offset % size;
                    double area = cross(hull.get(i), hull.get(k), hull.get(j));
                    if (area > outsideArea) { outsideArea = area; outside = j; }
                }
                if (outside >= 0 && insideArea + outsideArea > bestArea) {
                    bestArea = insideArea + outsideArea;
                    best[0] = i; best[1] = inside; best[2] = k; best[3] = outside;
                }
            }
        }
        List<Point> result = new ArrayList<>(count);
        for (int index : best) { result.add(hull.get(index)); }
        return result;
    }

    private static boolean fitsPolygon(List<Point> path, List<Point> polygon,
            double hullArea, double minAreaCoverage) {
        if (Math.abs(signedArea(polygon)) / hullArea < minAreaCoverage) { return false; }
        double squaredError = 0;
        for (Point point : path) {
            double nearest = Double.POSITIVE_INFINITY;
            for (int edge = 0; edge < polygon.size(); edge++) {
                nearest = Math.min(nearest, distanceToSegment(point, polygon.get(edge),
                        polygon.get((edge + 1) % polygon.size())));
            }
            if (nearest > 0.075) { return false; }
            squaredError += nearest * nearest;
        }
        return Math.sqrt(squaredError / path.size()) <= 0.032 && followsBoundaryOnce(path, polygon);
    }

    /** A good outline alone must not accept an edge that was drawn forward, backward, then forward. */
    private static boolean followsBoundaryOnce(List<Point> path, List<Point> polygon) {
        double total = perimeter(polygon);
        double[] positions = new double[path.size()];
        for (int i = 0; i < path.size(); i++) {
            Point point = path.get(i);
            double nearest = Double.POSITIVE_INFINITY;
            double edgeStart = 0;
            for (int edge = 0; edge < polygon.size(); edge++) {
                Point a = polygon.get(edge);
                Point b = polygon.get((edge + 1) % polygon.size());
                double length = distance(a, b);
                double fraction = ((point.x - a.x) * (b.x - a.x) + (point.y - a.y) * (b.y - a.y))
                        / (length * length);
                fraction = Math.max(0, Math.min(1, fraction));
                double error = Math.hypot(point.x - a.x - fraction * (b.x - a.x),
                        point.y - a.y - fraction * (b.y - a.y));
                if (error < nearest) {
                    nearest = error;
                    positions[i] = edgeStart + fraction * length;
                }
                edgeStart += length;
            }
        }
        double direction = Math.signum(signedArea(path));
        double backwards = 0;
        double progress = 0;
        for (int i = 0; i < positions.length; i++) {
            double delta = (positions[(i + 1) % positions.length] - positions[i]) * direction;
            if (delta > total / 2) { delta -= total; }
            if (delta < -total / 2) { delta += total; }
            backwards += Math.max(0, -delta);
            progress += delta;
        }
        return backwards / total <= 0.025 && Math.abs(progress / total - 1) <= 0.10;
    }

    private static boolean isTriangle(List<Point> triangle) {
        if (triangle.size() != 3) { return false; }
        for (int i = 0; i < 3; i++) {
            double angle = interiorAngle(triangle, i);
            if (angle < 27 || angle > 120) { return false; }
        }
        return true;
    }

    private static boolean isSquare(List<Point> square) {
        double minEdge = Double.POSITIVE_INFINITY;
        double maxEdge = 0;
        for (int i = 0; i < 4; i++) {
            double angle = interiorAngle(square, i);
            if (angle < 68 || angle > 112) { return false; }
            double edge = distance(square.get(i), square.get((i + 1) % 4));
            minEdge = Math.min(minEdge, edge);
            maxEdge = Math.max(maxEdge, edge);
        }
        // Deliberately conservative: distinctly rectangular scrolling loops are not squares.
        if (maxEdge / minEdge > 1.30) { return false; }
        double firstDiagonal = distance(square.get(0), square.get(2));
        double secondDiagonal = distance(square.get(1), square.get(3));
        if (Math.max(firstDiagonal, secondDiagonal) / Math.min(firstDiagonal, secondDiagonal) > 1.23) {
            return false;
        }
        Point firstMid = midpoint(square.get(0), square.get(2));
        Point secondMid = midpoint(square.get(1), square.get(3));
        return distance(firstMid, secondMid) / Math.max(firstDiagonal, secondDiagonal) <= 0.09;
    }

    private static double interiorAngle(List<Point> polygon, int index) {
        Point a = polygon.get((index + polygon.size() - 1) % polygon.size());
        Point b = polygon.get(index);
        Point c = polygon.get((index + 1) % polygon.size());
        double cosine = ((a.x - b.x) * (c.x - b.x) + (a.y - b.y) * (c.y - b.y))
                / (distance(a, b) * distance(b, c));
        return Math.toDegrees(Math.acos(Math.max(-1, Math.min(1, cosine))));
    }

    private static boolean hasCrossing(List<Point> path) {
        int count = path.size();
        for (int i = 0; i < count; i++) {
            for (int j = i + 4; j < count; j++) {
                if (count - (j - i) < 4) { continue; }
                Point a = path.get(i);
                Point b = path.get((i + 1) % count);
                Point c = path.get(j);
                Point d = path.get((j + 1) % count);
                if (cross(a, b, c) * cross(a, b, d) < -EPSILON
                        && cross(c, d, a) * cross(c, d, b) < -EPSILON) {
                    return true;
                }
            }
        }
        return false;
    }

    private static double distanceToSegment(Point point, Point a, Point b) {
        double dx = b.x - a.x;
        double dy = b.y - a.y;
        double lengthSquared = dx * dx + dy * dy;
        double fraction = lengthSquared > EPSILON
                ? ((point.x - a.x) * dx + (point.y - a.y) * dy) / lengthSquared : 0;
        fraction = Math.max(0, Math.min(1, fraction));
        return Math.hypot(point.x - a.x - fraction * dx, point.y - a.y - fraction * dy);
    }

    private static double perimeter(List<Point> points) {
        double perimeter = 0;
        for (int i = 0; i < points.size(); i++) {
            perimeter += distance(points.get(i), points.get((i + 1) % points.size()));
        }
        return perimeter;
    }

    private static double signedArea(List<Point> polygon) {
        double sum = 0;
        for (int i = 0; i < polygon.size(); i++) {
            Point a = polygon.get(i);
            Point b = polygon.get((i + 1) % polygon.size());
            sum += a.x * b.y - a.y * b.x;
        }
        return sum / 2;
    }

    private static Point midpoint(Point a, Point b) { return new Point((a.x + b.x) / 2, (a.y + b.y) / 2); }

    private static double distance(Point a, Point b) { return Math.hypot(a.x - b.x, a.y - b.y); }

    private static double cross(Point a, Point b, Point c) {
        return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x);
    }
}
