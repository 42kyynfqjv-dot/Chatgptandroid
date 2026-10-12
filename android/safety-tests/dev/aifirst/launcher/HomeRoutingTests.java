package dev.aifirst.launcher;

/** Regression scenarios for controls recovery and one-time HOME delivery. */
public final class HomeRoutingTests {
    private static final String MAIN = "android.intent.action.MAIN";
    private static int checks;

    public static void main(String[] args) {
        HomeRoutingPolicy policy = new HomeRoutingPolicy();
        check(!policy.consumeChatgptLaunch(), "No launch without a new intent");

        policy.acceptIntent(MAIN, true, false, false, true);
        check(!policy.consumeChatgptLaunch(), "Home stays in controls until opt-in");
        policy.acceptIntent(MAIN, true, true, false, true);
        check(policy.consumeChatgptLaunch(), "Fresh unlocked Home opens ChatGPT after opt-in");
        check(!policy.consumeChatgptLaunch(), "A launch opportunity is consumed only once");
        check(!policy.consumeChatgptLaunch(), "Returning from ChatGPT cannot launch it again");
        policy.acceptIntent(MAIN, true, true, false, true);
        check(policy.consumeChatgptLaunch(), "A later Home press gets a new launch opportunity");

        policy.acceptIntent(MAIN, false, true, false, true);
        check(!policy.consumeChatgptLaunch(), "App icon opens controls even with Home routing enabled");
        policy.acceptIntent(HomeRoutingPolicy.OPEN_CONTROLS, false, true, false, true);
        check(!policy.consumeChatgptLaunch(), "Quick Settings opens controls");
        policy.acceptIntent(HomeRoutingPolicy.OPEN_CONTROLS, true, true, false, true);
        check(!policy.consumeChatgptLaunch(), "Explicit controls action wins even if HOME category is present");
        policy.acceptIntent("android.intent.action.VIEW", true, true, false, true);
        check(!policy.consumeChatgptLaunch(), "An unrelated action cannot trigger Home routing");
        policy.acceptIntent(null, true, true, false, true);
        check(!policy.consumeChatgptLaunch(), "Missing action remains in controls");

        policy.acceptIntent(MAIN, true, true, true, true);
        check(!policy.consumeChatgptLaunch(), "Recreation after rotation or process death does not replay Home");
        policy.acceptIntent(MAIN, true, true, false, false);
        check(!policy.consumeChatgptLaunch(), "Home never launches over a locked device");
        check(!policy.consumeChatgptLaunch(), "Unlocking/resuming does not revive a skipped locked Home");

        policy.acceptIntent(MAIN, true, true, false, true);
        policy.acceptIntent(HomeRoutingPolicy.OPEN_CONTROLS, false, true, false, true);
        check(!policy.consumeChatgptLaunch(), "Controls cancels an unconsumed Home opportunity");
        policy.acceptIntent(MAIN, true, true, false, true);
        policy.acceptIntent(MAIN, true, false, false, true);
        check(!policy.consumeChatgptLaunch(), "Disabled routing cancels an earlier opportunity");

        System.out.println("PASS: " + checks + " Home-routing assertions (current UI prototype).");
    }

    private static void check(boolean condition, String explanation) {
        if (!condition) { throw new AssertionError(explanation); }
        checks++;
    }
}
