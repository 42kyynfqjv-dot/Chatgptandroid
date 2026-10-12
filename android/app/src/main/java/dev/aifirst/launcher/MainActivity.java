package dev.aifirst.launcher;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.KeyguardManager;
import android.app.StatusBarManager;
import android.content.ActivityNotFoundException;
import android.content.ComponentName;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.ResolveInfo;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.Icon;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.provider.Telephony;
import android.view.View;
import android.view.WindowInsets;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Switch;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;

/** Native phone controls and an optional, explicit Home-to-ChatGPT route. */
public final class MainActivity extends Activity {
    private static final String CHATGPT = "com.openai.chatgpt";
    private static final String CHATGPT_STORE = "https://play.google.com/store/apps/details?id=com.openai.chatgpt&referrer=downloadWebPage&pli=1";
    private static final String HOME_CHATGPT = "open_chatgpt_on_home";
    private final HomeRoutingPolicy routing = new HomeRoutingPolicy();
    private SharedPreferences preferences;
    private TextView status;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        preferences = getSharedPreferences("home_preferences", MODE_PRIVATE);
        // The 0.1 relay experiment is retired. Remove old credentials on upgrade;
        // retain its no-backup journal as historical evidence, with no runtime consumer.
        getSharedPreferences("private_pairing", MODE_PRIVATE).edit().clear().apply();
        buildControls();
        routeIntent(getIntent(), state != null);
    }

    @Override protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        routeIntent(intent, false);
    }

    // Deliberately no onResume/onStart routing: returning from an app must leave controls usable.
    private void routeIntent(Intent intent, boolean restoring) {
        KeyguardManager keyguard = getSystemService(KeyguardManager.class);
        routing.acceptIntent(intent == null ? null : intent.getAction(),
                intent != null && intent.hasCategory(Intent.CATEGORY_HOME),
                preferences.getBoolean(HOME_CHATGPT, false), restoring,
                keyguard != null && !keyguard.isDeviceLocked());
        if (routing.consumeChatgptLaunch()) { openChatgpt(); }
    }

    static Intent controlsIntent(android.content.Context context) {
        return new Intent(context, MainActivity.class)
                .setAction(HomeRoutingPolicy.OPEN_CONTROLS)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
    }

    private void buildControls() {
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
        root.addView(text("ChatGPT up front. Your phone within reach.", 17));
        Button chat = button(root, "Open ChatGPT", this::openChatgpt);
        chat.setTextSize(22);
        chat.setMinHeight(dp(88));
        root.addView(text("Use the official ChatGPT app for chat and Voice. Start Voice inside ChatGPT when you choose it.", 14));
        button(root, "Phone", () -> launch(new Intent(Intent.ACTION_DIAL), "No dialer is available in this profile."));
        button(root, "Messages", this::openMessages);
        button(root, "All apps", this::showApps);
        button(root, "Android Settings", () -> launch(new Intent(Settings.ACTION_SETTINGS), "Android Settings is unavailable."));

        root.addView(text("Keep controls close", 22));
        root.addView(text("Add Phone controls to Quick Settings. Swipe down while using ChatGPT and tap the tile to return here. The AI Home app icon also opens these controls.", 15));
        button(root, "Add Phone controls tile", this::addControlsTile);
        Switch home = new Switch(this);
        home.setText(R.string.chatgpt_on_home);
        home.setTextColor(Color.rgb(230, 239, 241));
        home.setMinHeight(dp(56));
        home.setChecked(preferences.getBoolean(HOME_CHATGPT, false));
        home.setOnCheckedChangeListener((button, enabled) -> {
            preferences.edit().putBoolean(HOME_CHATGPT, enabled).apply();
            setStatus(enabled
                    ? "Choose AI Home as your default home app in Android Settings. Home will then open ChatGPT; the tile and AI Home icon still open controls."
                    : "Home opens AI Home controls. You can also choose your previous launcher below.");
        });
        root.addView(home);
        button(root, "Default home / choose launcher", () -> launch(new Intent(Settings.ACTION_HOME_SETTINGS), "Open Android Settings → Apps → Default apps → Home app."));

        root.addView(text("App updates", 22));
        button(root, "Install / update ChatGPT", () -> launch(new Intent(Intent.ACTION_VIEW, Uri.parse(CHATGPT_STORE)), "No app can open the official Google Play listing."));
        root.addView(text("Updates come from the official Google Play listing. Play may show its normal store interface.", 13));
        status = text("Phone calls, notifications, and the lock screen remain under Android's control.", 14);
        status.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
        root.addView(status);
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

    private void setStatus(String value) { status.setText(value); }

    private void openChatgpt() {
        Intent chat = getPackageManager().getLaunchIntentForPackage(CHATGPT);
        if (chat == null) {
            setStatus("ChatGPT is not installed or available in this profile. These controls remain available; use Install / update ChatGPT below.");
            return;
        }
        launch(chat, "ChatGPT could not open. Phone controls remain available here.");
    }

    private void openMessages() {
        String smsPackage = Telephony.Sms.getDefaultSmsPackage(this);
        Intent messages = smsPackage == null ? null : getPackageManager().getLaunchIntentForPackage(smsPackage);
        if (messages == null) {
            messages = Intent.makeMainSelectorActivity(Intent.ACTION_MAIN, Intent.CATEGORY_APP_MESSAGING);
        }
        launch(messages, "No messaging app is available. Choose or install one through Android Settings.");
    }

    private void launch(Intent intent, String failure) {
        // A launcher must not put the dialer, Settings, or another app in its own task.
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        try { startActivity(intent); }
        catch (ActivityNotFoundException | SecurityException exception) { setStatus(failure); }
    }

    private void addControlsTile() {
        if (Build.VERSION.SDK_INT < 33) {
            setStatus("Swipe down twice to open Quick Settings, tap Edit, and drag Phone controls into your active tiles.");
            return;
        }
        StatusBarManager manager = getSystemService(StatusBarManager.class);
        if (manager == null) {
            setStatus("Open Quick Settings → Edit and add Phone controls manually.");
            return;
        }
        try {
            manager.requestAddTileService(new ComponentName(this, ControlsTileService.class),
                    getString(R.string.controls_tile), Icon.createWithResource(this, R.drawable.ic_controls),
                    getMainExecutor(), result -> {
                        if (isDestroyed()) { return; }
                        if (result == StatusBarManager.TILE_ADD_REQUEST_RESULT_TILE_ADDED
                                || result == StatusBarManager.TILE_ADD_REQUEST_RESULT_TILE_ALREADY_ADDED) {
                            setStatus("Phone controls is in Quick Settings. Swipe down from ChatGPT and tap it to return here.");
                        } else {
                            setStatus("The tile was not added. You can add Phone controls in Quick Settings → Edit.");
                        }
                    });
        } catch (IllegalArgumentException | SecurityException exception) {
            setStatus("Open Quick Settings → Edit and add Phone controls manually.");
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
            launch(intent, "That app could not open. It may be unavailable in this profile.");
        }).setNegativeButton("Close", null).show();
    }
}
