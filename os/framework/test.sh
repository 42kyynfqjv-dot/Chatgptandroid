#!/bin/sh
# Executes production session/recognizer code with JDK 17+, without Android substitutes.
set -eu
framework_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
test_out=$(mktemp -d)
trap 'rm -rf "$test_out"' EXIT HUP INT TERM
java_command=java
if [ -n "${JAVA_HOME:-}" ]; then java_command="$JAVA_HOME/bin/java"; fi
"$java_command" -m jdk.compiler/com.sun.tools.javac.Main --release 17 -encoding UTF-8 \
    -d "$test_out" \
    "$framework_dir/../gestures/src/dev/aifirst/gestures/ShapeRecognizer.java" \
    "$framework_dir/src/com/android/server/wm/AiFirstGestureSession.java" \
    "$framework_dir/tests/com/android/server/wm/AiFirstGestureSessionTests.java"
"$java_command" -cp "$test_out" com.android.server.wm.AiFirstGestureSessionTests
