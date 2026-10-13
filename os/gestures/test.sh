#!/bin/sh
# No Android SDK, network, or third-party test dependency is required.
set -eu
gesture_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
test_out=$(mktemp -d)
trap 'rm -rf "$test_out"' EXIT HUP INT TERM
java_command=java
if [ -n "${JAVA_HOME:-}" ]; then java_command="$JAVA_HOME/bin/java"; fi
"$java_command" -m jdk.compiler/com.sun.tools.javac.Main --release 17 -encoding UTF-8 \
    -d "$test_out" "$gesture_dir"/src/dev/aifirst/gestures/*.java \
    "$gesture_dir"/tests/dev/aifirst/gestures/*.java
"$java_command" -cp "$test_out" dev.aifirst.gestures.ShapeRecognizerTests
