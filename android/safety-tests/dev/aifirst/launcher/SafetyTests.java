package dev.aifirst.launcher;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.atomic.AtomicInteger;

/** Executable contract tests, intentionally independent of Android and external test libraries. */
public final class SafetyTests {
    private static int assertions;
    private static final String SCOPE = SafetyPolicy.scope("https://relay.example.com");

    public static void main(String[] args) throws Exception {
        policyRejectsUntrustedInputs();
        deadlineCannotBeExtendedByClockRollback();
        journalSurvivesCrashWithoutReplaying();
        journalPreservesFinalResultsAcrossRestart();
        reportConflictDoesNotBlockFutureWork();
        journalRejectsCorruptionAndWriteFailure();
        concurrentDuplicateIsReservedOnce();
        System.out.println("PASS: " + assertions + " safety assertions (production Java policy, deadline, journal).");
    }

    private static void policyRejectsUntrustedInputs() throws Exception {
        check(SafetyPolicy.origin("https://Relay.Example.com:443/").equals("https://relay.example.com"));
        check(SafetyPolicy.origin("https://relay.example.com:8443").endsWith(":8443"));
        for (String origin : new String[]{"http://relay.example.com", "https://relay.example.com/path",
                "https://user:pass@relay.example.com", "https://relay.example.com?token=bad",
                "https://relay.example.com#fragment", "https://relay.example.com:0", "https://relay.example.com:65536",
                "https://", "https://relay.example.com\\@other.example.com"}) {
            rejects(() -> SafetyPolicy.origin(origin), IllegalArgumentException.class);
        }
        rejects(() -> SafetyPolicy.token("short"), IllegalArgumentException.class);
        rejects(() -> SafetyPolicy.token("a".repeat(32) + "\r\nInjected: yes"), IllegalArgumentException.class);
        check(SafetyPolicy.token("A_a-1".repeat(8)).length() == 40);
        for (String app : new String[]{"chatgpt", "settings", "clock", "browser"}) { check(SafetyPolicy.app(app).equals(app)); }
        for (String app : new String[]{"com.openai.chatgpt", "dialer", "https://example.com", "shell", "CHATGPT"}) {
            rejects(() -> SafetyPolicy.app(app), IllegalArgumentException.class);
        }
        check(SafetyPolicy.integer(0, 0, 23) == 0);
        check(SafetyPolicy.integer(23L, 0, 23) == 23);
        check(SafetyPolicy.integer(59, 0, 59) == 59);
        for (Object value : new Object[]{-1, 24, 1.0, "5", true, Long.MAX_VALUE}) {
            rejects(() -> SafetyPolicy.integer(value, 0, 23), IllegalArgumentException.class);
        }
        rejects(() -> SafetyPolicy.integer(60, 0, 59), IllegalArgumentException.class);
        check(SafetyPolicy.label("🙂".repeat(80)).codePointCount(0, 160) == 80);
        check(SafetyPolicy.label("").isEmpty());
        for (String label : new String[]{"a".repeat(81), "Wake\nup", "Alarm\u202Eevil", "Bad\u0000", "\uD800", "\u2028"}) {
            rejects(() -> SafetyPolicy.label(label), IllegalArgumentException.class);
        }
        String id = UUID.randomUUID().toString();
        check(SafetyPolicy.requestId(id).equals(id));
        for (String invalid : new String[]{"../result", "1-1-1-1-1", id.toUpperCase(), id + "/result"}) {
            rejects(() -> SafetyPolicy.requestId(invalid), IllegalArgumentException.class);
        }
        check(SafetyPolicy.expired(Double.NaN, 1));
        check(SafetyPolicy.expired(Double.POSITIVE_INFINITY, 1));
        check(SafetyPolicy.expired(100, 100000));
        check(!SafetyPolicy.expired(101, 100000));
    }

    private static void deadlineCannotBeExtendedByClockRollback() {
        ActionDeadline deadline = new ActionDeadline(120, 100000, 5000);
        check(!deadline.expired(120, 110000, 15000));
        check(deadline.expired(120, 90000, 25000)); // Wall clock moved back; monotonic lifetime elapsed.
        check(deadline.expired(120, 121000, 6000)); // Wall clock moved forward; fail closed early.
        ActionDeadline bounded = new ActionDeadline(999999, 100000, 0);
        check(bounded.expired(999999, 100000, 300000)); // Untrusted server cannot grant an endless window.
        ActionDeadline nonfinite = new ActionDeadline(Double.NaN, 100000, 0);
        check(nonfinite.expired(Double.NaN, 100000, 0));
    }

    private static void journalSurvivesCrashWithoutReplaying() throws Exception {
        Path directory = Files.createTempDirectory("aihome-crash-");
        try {
            File file = directory.resolve("journal").toFile();
            RequestJournal journal = new RequestJournal(file);
            String claimed = UUID.randomUUID().toString();
            String dispatching = UUID.randomUUID().toString();
            check(journal.reserve(claimed, SCOPE));
            check(journal.reserve(dispatching, SCOPE));
            journal.dispatching(dispatching);
            RequestJournal afterCrash = new RequestJournal(file);
            check(afterCrash.recoverInterrupted() == 2);
            check(!afterCrash.reserve(claimed, SCOPE));
            check(!afterCrash.reserve(dispatching, SCOPE));
            check(afterCrash.entries().stream().allMatch(entry -> entry.status.equals("unknown")));
            check(afterCrash.pendingReports(SCOPE).size() == 2);
            check(afterCrash.recoverInterrupted() == 0);
            rejects(() -> afterCrash.dispatching(dispatching), IOException.class);
            rejects(() -> afterCrash.finish(dispatching, "handed_off", "late"), IOException.class);
        } finally { delete(directory); }
    }

    private static void journalPreservesFinalResultsAcrossRestart() throws Exception {
        Path directory = Files.createTempDirectory("aihome-final-");
        try {
            File file = directory.resolve("journal").toFile();
            RequestJournal journal = new RequestJournal(file);
            String id = UUID.randomUUID().toString();
            check(journal.reserve(id, SCOPE));
            rejects(() -> journal.finish(id, "handed_off", "bad ordering"), IOException.class);
            rejects(() -> journal.finish(id, "completed", "unverifiable"), IOException.class);
            journal.dispatching(id);
            journal.finish(id, "handed_off", "Android accepted the intent. Outcome not verified.");
            RequestJournal restart = new RequestJournal(file);
            check(restart.recoverInterrupted() == 0);
            check(restart.pendingReports(SCOPE).get(0).status.equals("handed_off"));
            check(restart.pendingReports(SafetyPolicy.scope("https://different.example.com")).isEmpty());
            restart.acknowledge(id);
            check(new RequestJournal(file).pendingReports(SCOPE).isEmpty());
            check(!new RequestJournal(file).reserve(id, SCOPE));
            check(new RequestJournal(file).entries().get(0).acknowledged);
        } finally { delete(directory); }
    }

    private static void reportConflictDoesNotBlockFutureWork() throws Exception {
        Path directory = Files.createTempDirectory("aihome-conflict-");
        try {
            File file = directory.resolve("journal").toFile();
            RequestJournal journal = new RequestJournal(file);
            String id = UUID.randomUUID().toString();
            journal.reserve(id, SCOPE);
            journal.dispatching(id);
            journal.finish(id, "handed_off", "Android accepted the intent. Outcome not verified.");
            journal.reportConflict(id);
            RequestJournal restart = new RequestJournal(file);
            check(restart.pendingReports(SCOPE).isEmpty());
            RequestJournal.Entry result = restart.entries().get(0);
            check(result.conflict && !result.acknowledged && result.status.equals("handed_off"));
            check(!restart.reserve(id, SCOPE));
            check(restart.reserve(UUID.randomUUID().toString(), SCOPE));
        } finally { delete(directory); }
    }

    private static void journalRejectsCorruptionAndWriteFailure() throws Exception {
        Path directory = Files.createTempDirectory("aihome-corrupt-");
        try {
            File file = directory.resolve("journal").toFile();
            Files.writeString(file.toPath(), "partial crash write", StandardCharsets.UTF_8);
            RequestJournal journal = new RequestJournal(file);
            rejects(journal::recoverInterrupted, IOException.class);
            rejects(() -> journal.reserve(UUID.randomUUID().toString(), SCOPE), IOException.class);
            Files.writeString(file.toPath(), "malformed\tline\n", StandardCharsets.UTF_8);
            rejects(journal::entries, IOException.class);
            File missingParent = directory.resolve("absent/journal").toFile();
            rejects(() -> new RequestJournal(missingParent).reserve(UUID.randomUUID().toString(), SCOPE), IOException.class);
        } finally { delete(directory); }
    }

    private static void concurrentDuplicateIsReservedOnce() throws Exception {
        Path directory = Files.createTempDirectory("aihome-concurrent-");
        try {
            File file = directory.resolve("journal").toFile();
            String id = UUID.randomUUID().toString();
            CountDownLatch start = new CountDownLatch(1);
            AtomicInteger wins = new AtomicInteger();
            List<Throwable> failures = Collections.synchronizedList(new ArrayList<>());
            Runnable contender = () -> {
                try {
                    start.await();
                    if (new RequestJournal(file).reserve(id, SCOPE)) { wins.incrementAndGet(); }
                } catch (Exception exception) { failures.add(exception); }
            };
            Thread one = new Thread(contender);
            Thread two = new Thread(contender);
            one.start(); two.start(); start.countDown(); one.join(); two.join();
            check(failures.isEmpty());
            check(wins.get() == 1);
        } finally { delete(directory); }
    }

    private interface Checked { void run() throws Exception; }

    private static void rejects(Checked action, Class<? extends Exception> type) throws Exception {
        try { action.run(); }
        catch (Exception exception) {
            if (!type.isInstance(exception)) { throw exception; }
            assertions++;
            return;
        }
        throw new AssertionError("Expected " + type.getSimpleName());
    }

    private static void check(boolean condition) {
        if (!condition) { throw new AssertionError("Safety assertion failed"); }
        assertions++;
    }

    private static void delete(Path directory) throws IOException {
        try (var paths = Files.walk(directory)) {
            for (Path path : paths.sorted(java.util.Comparator.reverseOrder()).toList()) { Files.delete(path); }
        }
    }
}
