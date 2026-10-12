package dev.aifirst.launcher;

/** One launch opportunity per newly delivered HOME intent, never per Activity resume. */
public final class HomeRoutingPolicy {
    public static final String OPEN_CONTROLS = "dev.aifirst.launcher.OPEN_CONTROLS";
    private boolean launchPending;

    public void acceptIntent(String action, boolean homeCategory, boolean enabled, boolean restoring, boolean unlocked) {
        launchPending = !restoring && enabled && unlocked && homeCategory
                && "android.intent.action.MAIN".equals(action);
    }

    public boolean consumeChatgptLaunch() {
        boolean launch = launchPending;
        launchPending = false;
        return launch;
    }
}
