# OS shape gesture observer

This is a source-level framework integration for the development OS build. It is
not an Android application permission, an accessibility service, or a completed
ROM. No framework build or phone test has validated this integration yet.

## Pinned input and build wiring

The hook patch applies to GrapheneOS `platform_frameworks_base` revision
`84183aff99be5e156dc0446a6fa2d4a7150f4bc3`, selected by the `2026100600`
manifest. Its only existing-file target is
`services/core/java/com/android/server/wm/DisplayPolicy.java`, whose unmodified
SHA-256 is
`12ba7ecf65f3a20007294c3cb58d8a35f548f0c213321448ffed9c2e3d2f53b3`.

Apply `patches/0001-aifirst-shape-observer.patch` and copy this directory's
`src/com/android/server/wm/*.java` into the corresponding `services/core/java/`
directory. Copy `../gestures/src/dev/aifirst/gestures/ShapeRecognizer.java` to
`services/core/java/dev/aifirst/gestures/ShapeRecognizer.java`. The repository's
OS patch assembler creates one canonical framework patch from these inputs;
do not apply both the canonical patch and this component patch.

The pinned `services/core/Android.bp` already includes these paths. Its
`services.core-sources-am-wm` group includes `java/com/android/server/wm/**/*.java`
through the existing protolog transform; `services.core-sources` includes other
`java/**/*.java` sources. Both feed `services.core.unboosted`. No separate Soong
module or privileged APK is needed.

The pinned APIs inspected for this integration are:

- `DisplayContent.registerPointerEventListener` and `PointerEventDispatcher`:
  observation runs on the system UI handler and finishes input with
  `handled=false`.
- `DisplayPolicy.focusChangedLw`: maintains an epoch that invalidates a stroke
  even if focus leaves and returns to the same ChatGPT window.
- `WindowState.getOwningUid`, `getEffectiveTouchableRegion`, `getFrame`, and
  `ActivityRecord.packageName`, `info.applicationInfo.uid`, `mUserId`: validate
  actual window/activity ownership rather than a recent-task guess or a
  caller-supplied window title.
- `DisplayContent.getImeWindow`, `getDisplayInfo`, `isSleeping`, and the raw
  insets state: exclude the keyboard, display transitions, cutouts, system
  bars, and system gesture edges.

## Behavior and boundaries

The observer is registered only on the default display. It accepts one finger
from a touchscreen only while the owner user (`0`) has a visible, full-screen
ChatGPT application window focused and the device is awake and unlocked. A
visible IME, notification shade, or another touchable window above ChatGPT that
intersects the safe gesture area prevents recognition. A further 24 dp margin
is removed after system-bar, cutout, and gesture insets.
The entire safe area must belong to the focused window's effective touchable
region. Overlap checks account for touch-modal windows, not just their frames.

Only completed strokes are classified. Cancellation, a second pointer, tool or
device changes, obscured-event flags, focus/context changes, any sample outside
safe bounds, non-monotonic samples, excessive duration, and more than 512 points
discard the whole stroke. Historical samples receive the same checks; they are
not silently truncated. Queued handoffs recheck the original window, focus
epoch, owner, display, density, rotation, bounds, keyguard, IME and shade.
The absolute UP timestamp also expires queued handoffs after one second,
including time spent in external service calls or waiting for the WMS lock.

Protected phone-state, screen-off and user-switch broadcasts invalidate active
and queued strokes. Before handoff the controller also checks Telecom for calls
or ringing, owner-user unlock state, and the current setting. External service
queries, package lookup, and activity launch occur outside the WMS lock. Native
activity dispatch necessarily follows the final locked snapshot; a state change
in that last interval cannot be atomically excluded by these APIs. Device tests
must cover incoming calls and lock/focus transitions under load.

A triangle opens `ACTION_DIAL` without a recipient. A square opens the default
SMS application's normal launcher activity. Missing apps or failed checks leave
the current app in place. Neither path places a call, composes a recipient, or
sends a message. No touch paths, screen contents or coordinates are logged or
persisted.

**Input remains visible to ChatGPT.** This is a passive observer: the app can
scroll, select, or react to the same stroke before the native app opens. This
patch does not implement touch arbitration, touch cancellation, or guaranteed
separation from normal app interactions. It also does not claim zero latency or
an Android runtime test from a source check.

## Development enablement and recovery

The secure setting `aifirst_shape_gestures_enabled` defaults to `0`. In a
deliberately enabled OS integration test, an authorized operator can enable or
disable the observer:

```sh
adb shell settings --user 0 put secure aifirst_shape_gestures_enabled 1
adb shell settings --user 0 put secure aifirst_shape_gestures_enabled 0
```

These commands require the custom OS build containing this framework patch;
setting the value on stock Android adds no gesture behavior. This is a one-time
development gate, not a hold, button, panel, or activation step for each gesture.
Normal Android navigation, Quick Settings, keyguard, Phone, Messages and launcher
recovery remain outside this component's control.

## Validation

Run `./os/framework/test.sh` with a complete JDK 17 or later. The test compiles
the exact production stroke-session and recognizer sources and checks stream
lifetime, focus interruption, profile/display/context mismatch, boundaries,
historical samples, monotonic time, immutable handoffs, cancellation and bounded
memory. It includes one session-to-recognizer integration case. Geometry tests
belong to `../gestures/test.sh`.

These JVM tests do not compile `AiFirstShapeController` against Android or test
`DisplayPolicy`, Binder, SystemUI, actual input dispatch, native-app resolution,
call interruptions, framework permissions, or a Pixel. Exact patch applicability
and the existing Soong source globs are separately checked. A complete OS build
and hardware validation remain required before relying on this behavior.
