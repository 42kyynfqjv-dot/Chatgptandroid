#!/bin/sh
# Run current Home routing and retained legacy safety regressions with JDK 17+.
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
test_out=$(mktemp -d)
trap 'rm -rf "$test_out"' EXIT HUP INT TERM
if [ -n "${JAVA_HOME:-}" ]; then
    java_command="$JAVA_HOME/bin/java"
else
    java_command=java
fi
"$java_command" -m jdk.compiler/com.sun.tools.javac.Main -encoding UTF-8 -d "$test_out" \
    "$project_dir/app/src/main/java/dev/aifirst/launcher/SafetyPolicy.java" \
    "$project_dir/app/src/main/java/dev/aifirst/launcher/ActionDeadline.java" \
    "$project_dir/app/src/main/java/dev/aifirst/launcher/RequestJournal.java" \
    "$project_dir/app/src/main/java/dev/aifirst/launcher/HomeRoutingPolicy.java" \
    "$project_dir/safety-tests/dev/aifirst/launcher/SafetyTests.java" \
    "$project_dir/safety-tests/dev/aifirst/launcher/HomeRoutingTests.java"
"$java_command" -cp "$test_out" dev.aifirst.launcher.HomeRoutingTests
"$java_command" -cp "$test_out" dev.aifirst.launcher.SafetyTests
