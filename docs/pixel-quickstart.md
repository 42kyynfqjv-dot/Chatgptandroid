# Try AI Home on the dev Pixel

This installs a small app on the Pixel's existing Android. It does not replace
Android or change the bootloader. The MacBook is used for USB installation;
the cloud server only builds the APK.

## Get and install the APK

Download **android-debug-and-lint** from the latest successful
[GitHub Actions run](https://github.com/42kyynfqjv-dot/Chatgptandroid/actions/workflows/components.yml).
Unzip it and locate `app-debug.apk`. A GitHub sign-in may be needed to download
the artifact. It expires after seven days; rerun the workflow if necessary.

On the local MacBook, with Android platform-tools installed and USB debugging
enabled on the dev Pixel, connect it by USB and run:

```sh
adb devices
adb -s PIXEL_SERIAL install -r /absolute/path/to/app-debug.apk
```

Replace `PIXEL_SERIAL` with the dev Pixel serial shown by `adb devices`, and use
the actual APK path. Accept the Pixel's USB debugging prompt if shown. The
explicit serial prevents accidentally installing on another connected device.

Debug builds use development signing keys. GitHub's ephemeral runners may sign
different runs with different keys. If Android reports
`INSTALL_FAILED_UPDATE_INCOMPATIBLE`, switch the Home app back to Pixel Launcher,
uninstall only **AI Home** through Settings, then install the new APK. This
resets AI Home's preferences; it does not require removing ChatGPT or phone data.

## Set up

1. Open **AI Home** as a normal app. Test **Open ChatGPT**, **Phone**,
   **Messages**, and **Settings**. Install or update the official ChatGPT app
   through its Play link if needed.
2. Use **Add Phone controls tile** and accept Android's tile prompt. If it is
   unavailable, expand Quick Settings, tap its edit button, and add **Phone
   controls** manually. Place it near the top for easy access.
3. Enable **ChatGPT on Home**, then use the default-home button to select
   **AI Home**. Press Home to open ChatGPT.

While ChatGPT is open, swipe down for notifications and Quick Settings. Tap
**Phone controls** to reach Phone, Messages, Settings, and All apps. The AI Home
app icon also opens controls. Phone calls and message notifications keep using
their normal Android UI. The shortcuts open the native apps; they do not make
ChatGPT place calls or send messages.

## Check on the Pixel

- Home opens ChatGPT; opening controls does not immediately bounce back to it.
- Phone opens the dialer, Messages opens the messaging app, and Settings works.
- Incoming calls and message notifications appear normally while ChatGPT is
  foreground. Check a normal test call; do not place an emergency test call.
- Lock/unlock, volume, quick settings, and returning from native apps remain
  usable. Test both gesture navigation and button navigation if used.
- Opening AI Home from its icon or tile works after rotation and app restart.
- The Play link opens the official ChatGPT listing, and All apps remains usable.
- With **ChatGPT on Home** off, Home shows controls. If ChatGPT cannot launch,
  controls remain available rather than repeatedly retrying.

Record the tested APK/commit, Android build, ChatGPT version, and failures.
These physical checks have not been run by cloud compilation or lint.

## Return to Pixel Launcher

Open normal **Settings → Apps → Default apps → Home app → Pixel Launcher**.
The AI Home controls screen also links to the Home-app chooser. You can turn
off **ChatGPT on Home** or uninstall AI Home after selecting Pixel Launcher.
