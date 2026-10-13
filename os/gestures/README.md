# Single-stroke shape recognition kernel

Pure Java 17 source for an OS input-policy component. This directory does **not** install a gesture interceptor, launch apps, or alter the existing APK. Its neutral `dev.aifirst.gestures` package can be copied into the framework services source set; it needs no Android API, ML model, or third-party library.

```java
ShapeRecognizer recognizer = new ShapeRecognizer();
List<ShapeRecognizer.Point> stroke = /* completed down-to-up pixel samples */;
ShapeRecognizer.Shape shape = recognizer.recognize(stroke, durationMillis, displayDensity);
// Result is NONE, TRIANGLE, or SQUARE. The caller owns any action mapping.
```

The caller must submit only a completed, uncancelled, single-pointer touch stream. It must discard the **entire** stream on multitouch, cancellation, overflow, focus/device/display changes, or loss of eligibility; submitting the retained prefix after dropping later points is unsafe. Use monotonic event time for duration and physical display density, not font scale. No gesture origin, edge hold, extra finger, or arming step is required by the recognizer.

## Recognition and limits

The kernel removes stationary sub-dp jitter, resamples a closed stroke to 120 equal-distance points, smooths it, and constructs its convex hull. It fits maximum-area inscribed triangles/quadrilaterals, then checks boundary error, corner geometry, closure, traversal direction, and retracing. Longest-chord normalization and minimum hull width keep size/error decisions independent of screen orientation; both traversal directions and arbitrary starting points are supported.

Conservative starting thresholds, pending real-device calibration:

| Constraint | Initial value |
| --- | --- |
| Input samples | 8–512; overflow rejects, never truncates |
| Stroke duration | 180–3000 ms |
| Minimum hull width | 96 dp, measured across hull orientations |
| Lift-off gap | At most 24 dp **and** 8% of shape diameter |
| Triangle corner angles | 27°–120° |
| Square edge ratio | Longest/shortest ≤1.30, plus angle/diagonal checks |
| Polygon coverage of hull | ≥86% for triangle; ≥88% for square |
| Boundary error | RMS ≤3.2% and maximum ≤7.5% of diameter |
| Backward boundary travel | ≤2.5% of perimeter, allowing small finger wobble |

Taps, swipes, clearly open paths, circles, substantially rectangular loops, crossed paths, repeated laps, partial edge retracing, and scribbles are rejected by the regression corpus. Slight closure gaps and small hand-drawn deviations are intentionally tolerated. The accepted family is narrower than every mathematical triangle or quadrilateral. These thresholds are a tested prototype, not a measured false-positive rate or a promise of reliable recognition on a phone.

**Recognizing geometry cannot determine intent.** A triangle or square drawn inside ChatGPT can be geometrically identical to a system gesture. This kernel cannot retract touches already delivered to an app, arbitrate scrolling versus drawing, or guarantee clean interception. Any framework integration must state whether the app receives the same stroke and validate that tradeoff on hardware before enabling it by default. The surrounding OS controller must own lockscreen restrictions, foreground eligibility, cancellation, launch policy, and accessibility compatibility.

## Verification

```sh
JAVA_HOME=/path/to/jdk17 os/gestures/test.sh
```

The deterministic suite contains independently authored synthetic trajectories and public-API regressions: noisy and rounded corners, rotations, mid-edge starts, clockwise/counterclockwise traversal, display densities, partial/repeated retracing, physical-size invariance, open paths, malformed coordinates, oversized streams, and timing bounds. Fixtures are **not recordings from people or devices**. Passing these tests establishes only the behavior of this geometry kernel. There is no device/input-dispatch, app-launch, OS-boot, latency, or touch-interception validation here.
