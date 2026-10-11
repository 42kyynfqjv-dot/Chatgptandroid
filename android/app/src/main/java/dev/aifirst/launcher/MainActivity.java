package dev.aifirst.launcher;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.app.AlertDialog;
import android.app.KeyguardManager;
import android.content.ActivityNotFoundException;
import android.content.ComponentName;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.ResolveInfo;
import android.graphics.Color;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Bundle;
import android.provider.AlarmClock;
import android.provider.Settings;
import android.system.ErrnoException;
import android.system.Os;
import android.system.OsConstants;
import android.text.InputType;
import android.view.View;
import android.view.MotionEvent;
import android.view.WindowInsets;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.io.File;
import java.io.FileDescriptor;
import java.io.FileOutputStream;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Optional HOME application. All external side effects require a visible, explicit user tap. */
public final class MainActivity extends Activity {
    private static final String CHATGPT = "com.openai.chatgpt";
    private static final String CHATGPT_STORE = "https://play.google.com/store/apps/details?id=com.openai.chatgpt&referrer=downloadWebPage&pli=1";
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private SharedPreferences preferences;
    private RequestJournal journal;
    private TextView status;
    private Button pollButton;
    private Button pairButton;
    private BridgeClient client;
    private BridgeAction pending;
    private AlertDialog confirmation;
    private AlertDialog pairing;
    private boolean visible;
    private boolean busy;
    private boolean journalHealthy = true;
    private int generation;
    private int pollConflicts;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        // Pairing secrets and request contents should not enter screenshots or recents previews.
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);
        preferences = getSharedPreferences("private_pairing", MODE_PRIVATE);
        File journalFile = new File(getNoBackupFilesDir(), "requests-v1.journal");
        journal = new RequestJournal(journalFile);
        buildHome();
        try {
            initializeJournalFile(journalFile);
            int recovered = journal.recoverInterrupted();
            if (recovered > 0) {
                setStatus("Recovered " + recovered + " interrupted request(s) as unknown. They will never be replayed.");
            }
        } catch (IOException exception) {
            blockJournal();
        }
    }

    @Override protected void onResume() {
        super.onResume();
        visible = true;
        refreshButtons();
    }

    @Override protected void onPause() {
        visible = false;
        generation++;
        if (client != null) { client.cancel(); }
        busy = false;
        if (pending != null) {
            finishPending("rejected", "Launcher left the foreground before approval.");
        }
        if (confirmation != null) {
            confirmation.dismiss();
            confirmation = null;
        }
        if (pairing != null) { pairing.dismiss(); pairing = null; }
        super.onPause();
    }

    @Override protected void onDestroy() {
        if (client != null) { client.cancel(); }
        worker.shutdownNow();
        super.onDestroy();
    }

    private void buildHome() {
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(24), dp(24), dp(24), dp(30));
        root.setBackgroundColor(Color.rgb(16, 27, 34));
        scroll.addView(root);
        scroll.setOnApplyWindowInsetsListener((view, insets) -> {
            android.graphics.Insets bars = insets.getInsets(WindowInsets.Type.systemBars());
            view.setPadding(bars.left, bars.top, bars.right, bars.bottom);
            return insets;
        });
        TextView eyebrow = text("YOUR PHONE, WITH YOU IN CONTROL", 12);
        eyebrow.setTextColor(Color.rgb(147, 220, 194));
        root.addView(eyebrow);
        TextView title = text("AI Home", 38);
        title.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        root.addView(title);
        root.addView(text("Start with ChatGPT. Keep your apps close.", 17));
        Button chat = button(root, "Open ChatGPT", () -> launchApp("chatgpt"));
        chat.setTextSize(22);
        chat.setMinHeight(dp(88));
        root.addView(text("Use the official ChatGPT app for chat and Voice. Voice starts inside ChatGPT when you choose it.", 14));
        button(root, "All apps", this::showApps);
        button(root, "Clock", () -> launchApp("clock"));
        button(root, "Browser", () -> launchApp("browser"));
        root.addView(text("Settings / app updates", 20));
        button(root, "Settings", () -> launchApp("settings"));
        button(root, "Default home / choose launcher", () -> launchLocal(new Intent(Settings.ACTION_HOME_SETTINGS)));
        button(root, "Install / update ChatGPT", () -> launchLocal(new Intent(Intent.ACTION_VIEW, Uri.parse(CHATGPT_STORE))));

        TextView bridgeTitle = text("Device bridge", 24);
        bridgeTitle.setPadding(0, dp(28), 0, dp(8));
        root.addView(bridgeTitle);
        root.addView(text("Optional. While this screen is open, connect to your relay and review one request at a time. Every action needs your approval here.", 15));
        pairButton = button(root, "Pair / change relay", this::showPairing);
        pollButton = button(root, "Connect and poll once", this::pollOnce);
        button(root, "Request history", this::showHistory);
        button(root, "Disconnect / forget token", this::forgetPairing);
        status = text("Not connected. Polling is manual and stops when you leave this screen.", 14);
        status.setPadding(0, dp(12), 0, dp(18));
        status.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
        root.addView(status);
        root.addView(text("AI Home is a launcher prototype, not an operating system or an OpenAI product. It cannot read your ChatGPT conversations or control Voice.", 12));
        setContentView(scroll);
    }

    private TextView text(String value, int size) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(size);
        view.setTextColor(Color.rgb(230, 239, 241));
        view.setPadding(0, dp(8), 0, dp(8));
        return view;
    }

    private Button button(LinearLayout parent, String label, Runnable click) {
        Button button = new Button(this);
        button.setText(label);
        button.setAllCaps(false);
        button.setMinHeight(dp(52));
        button.setOnClickListener(view -> click.run());
        parent.addView(button, new LinearLayout.LayoutParams(-1, -2));
        return button;
    }

    private int dp(int value) { return Math.round(value * getResources().getDisplayMetrics().density); }

    private void showPairing() {
        if (busy || pending != null) { return; }
        LinearLayout fields = new LinearLayout(this);
        fields.setOrientation(LinearLayout.VERTICAL);
        fields.setPadding(dp(24), dp(8), dp(24), dp(8));
        fields.addView(text("Enter your relay HTTPS origin and its device token. The token grants device access to that relay. Use a relay you control.", 15));
        EditText endpoint = new EditText(this);
        endpoint.setHint("https://relay.example.com");
        endpoint.setSingleLine(true);
        endpoint.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        endpoint.setText(preferences.getString("origin", ""));
        endpoint.setContentDescription("Relay HTTPS origin");
        endpoint.setSaveEnabled(false);
        fields.addView(endpoint);
        EditText token = new EditText(this);
        token.setHint("Device bearer token");
        token.setSingleLine(true);
        token.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        token.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO_EXCLUDE_DESCENDANTS);
        token.setSaveEnabled(false);
        token.setContentDescription("Device bearer token");
        fields.addView(token);
        AlertDialog dialog = new AlertDialog.Builder(this).setTitle("Pair your relay")
                .setView(fields).setNegativeButton("Cancel", null).setPositiveButton("Save", null).create();
        pairing = dialog;
        secure(dialog);
        dialog.setOnDismissListener(ignored -> {
            token.setText("");
            pairing = null;
        });
        dialog.setOnShowListener(ignored -> dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(view -> {
            try {
                String safeOrigin = SafetyPolicy.origin(endpoint.getText().toString());
                String safeToken = SafetyPolicy.token(token.getText().toString());
                if (!preferences.edit().putString("origin", safeOrigin).putString("token", safeToken).commit()) {
                    throw new IllegalArgumentException("Could not save pairing privately.");
                }
                token.setText("");
                dialog.dismiss();
                setStatus("Paired locally with " + safeOrigin + ". Tap Connect and poll once to contact it.");
                refreshButtons();
            } catch (IllegalArgumentException exception) {
                token.setError(exception.getMessage());
            }
        }));
        dialog.show();
    }

    private void forgetPairing() {
        generation++;
        if (client != null) { client.cancel(); }
        busy = false;
        if (pending != null) { finishPending("rejected", "Device disconnected before approval."); }
        if (confirmation != null) { confirmation.dismiss(); confirmation = null; }
        if (preferences.edit().clear().commit()) {
            setStatus("Disconnected. Token removed; replay-protection history retained. Revoke the device token on your relay too.");
        } else {
            setStatus("Could not remove the stored pairing. Use Android app storage settings to clear it and revoke the relay token.");
        }
        refreshButtons();
    }

    private void pollOnce() {
        if (!visible || busy || pending != null || !journalHealthy) { return; }
        String origin = preferences.getString("origin", "");
        String token = preferences.getString("token", "");
        final BridgeClient connection;
        try {
            connection = new BridgeClient(origin, token);
        } catch (IllegalArgumentException exception) {
            setStatus("Pair a relay and device token first.");
            return;
        }
        client = connection;
        final int requestGeneration = ++generation;
        final String scope = SafetyPolicy.scope(origin);
        busy = true;
        pollConflicts = 0;
        refreshButtons();
        setStatus("Sending saved results, then polling once…");
        worker.execute(() -> {
            int conflicts = 0;
            try {
                for (RequestJournal.Entry report : localJournal(() -> journal.pendingReports(scope))) {
                    BridgeClient.ReportResult receipt = connection.report(report);
                    if (receipt == BridgeClient.ReportResult.CONFLICT) { conflicts++; }
                    localJournal(() -> {
                        if (receipt == BridgeClient.ReportResult.ACKNOWLEDGED) { journal.acknowledge(report.id); }
                        else { journal.reportConflict(report.id); }
                        return null;
                    });
                }
                BridgeAction next = connection.next();
                // Journal before posting to the UI: process death after this point cannot replay it.
                boolean reserved = next != null && localJournal(() -> journal.reserve(next.id, scope));
                final int finalConflicts = conflicts;
                runOnUiThread(() -> {
                    if (requestGeneration == generation) { pollConflicts = finalConflicts; }
                    receive(next, reserved, requestGeneration);
                });
            } catch (Exception exception) {
                final int finalConflicts = conflicts;
                runOnUiThread(() -> {
                    if (requestGeneration != generation || !visible) { return; }
                    pollConflicts = finalConflicts;
                    busy = false;
                    if (exception instanceof JournalFailure) { blockJournal(); return; }
                    setStatus("Could not finish this poll. Saved results are retained. Check relay/TLS/token, then poll manually. No automatic retry.");
                    refreshButtons();
                });
            }
        });
    }

    private void receive(BridgeAction action, boolean reserved, int requestGeneration) {
        if (requestGeneration != generation || !visible) {
            if (reserved) {
                finish(action.id, "unknown", "Poll interrupted before review. No automatic retry.");
            }
            return;
        }
        busy = false;
        if (action == null) {
            setStatus("Connected. No pending request. Poll again when you want to check.");
        } else if (!reserved) {
            setStatus("Duplicate request blocked by the device journal. No action launched.");
        } else if (action.expired()) {
            finish(action.id, "unknown", "Request expired before device confirmation.");
            setStatus("Request expired. No action launched; report saved locally.");
        } else {
            pending = action;
            showConfirmation(action);
        }
        refreshButtons();
    }

    private void showConfirmation(BridgeAction action) {
        String conflictWarning = pollConflicts > 0 ? "The relay did not acknowledge " + pollConflicts
                + " earlier result(s). Check history before repeating an action.\n\n" : "";
        String message = conflictWarning + action.summary() + "\n\nRequest: " + action.id
                + "\n\nApprove only if you intended this request. An alarm still needs review in Clock; the relay can only learn that it was handed off.";
        confirmation = new AlertDialog.Builder(this).setTitle("Approve phone action?").setMessage(message)
                .setNegativeButton("Reject", (dialog, which) -> finishPending("rejected", "Rejected on device."))
                .setPositiveButton("Approve", (dialog, which) -> approve(action)).create();
        confirmation.setCancelable(false);
        secure(confirmation);
        confirmation.show();
        rejectObscuredApprovalTouches(confirmation.getButton(AlertDialog.BUTTON_POSITIVE));
        setStatus("Waiting for your approval on this device.");
    }

    private void approve(BridgeAction action) {
        if (!visible || pending != action) { return; }
        KeyguardManager keyguard = getSystemService(KeyguardManager.class);
        if (keyguard == null || keyguard.isDeviceLocked() || confirmation == null
                || confirmation.getWindow() == null
                || !confirmation.getWindow().getDecorView().hasWindowFocus()) {
            finishPending("rejected", "Device locked or confirmation lost focus before approval.");
            return;
        }
        if (action.expired()) {
            finishPending("unknown", "Request expired before device confirmation.");
            return;
        }
        try {
            journal.dispatching(action.id); // Must be durable BEFORE the Android side effect.
        } catch (IOException exception) {
            pending = null;
            blockJournal();
            return;
        }
        pending = null;
        confirmation = null;
        try {
            Intent intent;
            if ("set_alarm".equals(action.action)) {
                intent = new Intent(AlarmClock.ACTION_SET_ALARM)
                        .putExtra(AlarmClock.EXTRA_HOUR, action.hour)
                        .putExtra(AlarmClock.EXTRA_MINUTES, action.minute)
                        .putExtra(AlarmClock.EXTRA_MESSAGE, action.label)
                        .putExtra(AlarmClock.EXTRA_SKIP_UI, false);
            } else {
                intent = appIntent(action.app);
            }
            if (intent == null) { throw new ActivityNotFoundException(); }
            startActivity(intent);
            finish(action.id, "handed_off", "Android accepted the intent. Outcome not verified.");
            setStatus("Handed off to Android. Return and poll to send the saved result. Check Clock yourself for any alarm.");
        } catch (ActivityNotFoundException | SecurityException exception) {
            finish(action.id, "failed", "No available or permitted activity accepted the intent.");
            setStatus("Could not open that app. Failure saved; poll to report it.");
        }
        refreshButtons();
    }

    private void finishPending(String result, String detail) {
        BridgeAction action = pending;
        pending = null;
        if (action != null) {
            finish(action.id, result, detail);
            setStatus("Result saved: " + result + ". Poll to send it to your relay.");
        }
        refreshButtons();
    }

    private void finish(String id, String result, String detail) {
        try { journal.finish(id, result, detail); }
        catch (IOException exception) { blockJournal(); }
    }

    private void blockJournal() {
        journalHealthy = false;
        setStatus("Device journal is unavailable. Remote actions are blocked to prevent replay. Keep the journal; inspect the relay before changing app storage.");
        refreshButtons();
    }

    private void refreshButtons() {
        if (pollButton == null) { return; }
        pollButton.setEnabled(visible && !busy && pending == null && journalHealthy && preferences.contains("token"));
        pairButton.setEnabled(!busy && pending == null);
    }

    private void setStatus(String value) {
        if (status != null) {
            String conflicts = pollConflicts > 0 ? "Relay did not acknowledge " + pollConflicts
                    + " saved result(s). Check Request history; do not assume the action failed or repeat it.\n\n" : "";
            status.setText(journalHealthy ? conflicts + value : "Device journal is unavailable. Remote actions are blocked to prevent replay. Keep the journal; inspect the relay before changing app storage.");
        }
    }

    private static final class JournalFailure extends Exception {
        JournalFailure(IOException cause) { super(cause); }
    }

    private void initializeJournalFile(File file) throws IOException {
        // Persist the first directory entry before any request can be approved, as well as file data.
        try (FileOutputStream output = new FileOutputStream(file, true)) { output.getFD().sync(); }
        FileDescriptor directory = null;
        try {
            directory = Os.open(getNoBackupFilesDir().getAbsolutePath(), OsConstants.O_RDONLY, 0);
            Os.fsync(directory);
        } catch (ErrnoException exception) {
            throw new IOException("Could not durably initialize the journal.", exception);
        } finally {
            if (directory != null) {
                try { Os.close(directory); }
                catch (ErrnoException exception) { throw new IOException("Could not close journal directory.", exception); }
            }
        }
    }

    private interface JournalCall<T> { T run() throws IOException; }

    private static <T> T localJournal(JournalCall<T> call) throws JournalFailure {
        try { return call.run(); }
        catch (IOException exception) { throw new JournalFailure(exception); }
    }

    private void secure(AlertDialog dialog) {
        if (dialog.getWindow() != null) {
            dialog.getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);
        }
    }

    @SuppressLint("ClickableViewAccessibility")
    private void rejectObscuredApprovalTouches(Button button) {
        button.setFilterTouchesWhenObscured(true);
        // Only security-rejected events are consumed. All normal touches return false to the
        // framework Button, retaining its performClick and accessibility click behavior.
        button.setOnTouchListener((view, event) ->
                (event.getFlags() & (MotionEvent.FLAG_WINDOW_IS_OBSCURED
                        | MotionEvent.FLAG_WINDOW_IS_PARTIALLY_OBSCURED)) != 0);
    }

    private Intent appIntent(String app) {
        switch (SafetyPolicy.app(app)) {
            case "chatgpt": return getPackageManager().getLaunchIntentForPackage(CHATGPT);
            case "settings": return new Intent(Settings.ACTION_SETTINGS);
            case "clock": return new Intent(AlarmClock.ACTION_SHOW_ALARMS);
            case "browser": return Intent.makeMainSelectorActivity(Intent.ACTION_MAIN, Intent.CATEGORY_APP_BROWSER);
            default: throw new IllegalArgumentException("Unsupported app.");
        }
    }

    private void launchApp(String app) {
        Intent intent = appIntent(app);
        if (intent == null) {
            setStatus("ChatGPT is not installed or available in this profile. Use Install / update ChatGPT.");
            new AlertDialog.Builder(this).setTitle("Install official ChatGPT")
                    .setMessage("Open the official ChatGPT listing on Google Play in this profile.")
                    .setPositiveButton("Open listing", (dialog, which) -> launchLocal(new Intent(Intent.ACTION_VIEW, Uri.parse(CHATGPT_STORE))))
                    .setNegativeButton("Cancel", null).show();
            return;
        }
        launchLocal(intent);
    }

    private void launchLocal(Intent intent) {
        try { startActivity(intent); }
        catch (ActivityNotFoundException | SecurityException exception) {
            setStatus("No available app can open this. Use Settings or install the required app in this profile.");
        }
    }

    private void showApps() {
        Intent launcher = new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER);
        List<ResolveInfo> apps = new ArrayList<>(getPackageManager().queryIntentActivities(launcher, 0));
        apps.removeIf(info -> getPackageName().equals(info.activityInfo.packageName));
        apps.sort(Comparator.comparing(info -> info.loadLabel(getPackageManager()).toString().toLowerCase(Locale.ROOT)));
        String[] labels = new String[apps.size()];
        for (int i = 0; i < apps.size(); i++) { labels[i] = apps.get(i).loadLabel(getPackageManager()).toString(); }
        new AlertDialog.Builder(this).setTitle("All apps").setItems(labels, (dialog, which) -> {
            ResolveInfo target = apps.get(which);
            Intent intent = new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
                    .setComponent(new ComponentName(target.activityInfo.packageName, target.activityInfo.name))
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_RESET_TASK_IF_NEEDED);
            launchLocal(intent);
        }).setNegativeButton("Close", null).show();
    }

    private void showHistory() {
        try {
            List<RequestJournal.Entry> entries = journal.entries();
            StringBuilder message = new StringBuilder();
            int start = Math.max(0, entries.size() - 30);
            for (int i = entries.size() - 1; i >= start; i--) {
                RequestJournal.Entry entry = entries.get(i);
                message.append(entry.id).append('\n').append(entry.status)
                        .append(entry.conflict ? " · relay conflict; not acknowledged" : entry.acknowledged ? " · reported" : " · report pending")
                        .append('\n').append(entry.detail).append("\n\n");
            }
            if (message.length() == 0) { message.append("No device requests yet."); }
            AlertDialog history = new AlertDialog.Builder(this).setTitle("Recent requests (up to 30)").setMessage(message)
                    .setPositiveButton("Close", null).create();
            secure(history);
            history.show();
        } catch (IOException exception) { blockJournal(); }
    }
}
