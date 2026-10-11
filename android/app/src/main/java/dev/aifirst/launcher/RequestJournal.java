package dev.aifirst.launcher;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** Append-only private journal. Every transition is fsynced before success is returned. */
public final class RequestJournal {
    private static final Object IO_LOCK = new Object();
    private static final long MAX_BYTES = 2 * 1024 * 1024;
    private static final Set<String> FINAL = Set.of("rejected", "handed_off", "failed", "unknown");
    private final File file;

    public static final class Entry {
        public final String id;
        public final String scope;
        public final String status;
        public final String detail;
        public final boolean acknowledged;
        public final boolean conflict;

        private Entry(String id, String scope, String status, String detail, boolean acknowledged) {
            this(id, scope, status, detail, acknowledged, false);
        }

        private Entry(String id, String scope, String status, String detail, boolean acknowledged, boolean conflict) {
            this.id = id;
            this.scope = scope;
            this.status = status;
            this.detail = detail;
            this.acknowledged = acknowledged;
            this.conflict = conflict;
        }

        public boolean isFinal() { return FINAL.contains(status); }
    }

    public RequestJournal(File file) { this.file = file; }

    public boolean reserve(String id, String scope) throws IOException {
        synchronized (IO_LOCK) {
            SafetyPolicy.requestId(id);
            if (!scope.matches("[0-9a-f]{64}")) { throw new IOException("Invalid relay scope."); }
            if (read().containsKey(id)) { return false; }
            append(new Entry(id, scope, "claimed", "", false));
            return true;
        }
    }

    public void dispatching(String id) throws IOException {
        synchronized (IO_LOCK) {
            Entry old = require(id);
            if (!"claimed".equals(old.status)) { throw new IOException("Request already handled."); }
            append(new Entry(id, old.scope, "dispatching", "", false));
        }
    }

    public void finish(String id, String status, String detail) throws IOException {
        synchronized (IO_LOCK) {
            Entry old = require(id);
            if (!FINAL.contains(status) || old.isFinal() || detail.length() > 240) {
                throw new IOException("Invalid journal transition.");
            }
            if ("handed_off".equals(status) && !"dispatching".equals(old.status)) {
                throw new IOException("A handoff requires durable dispatch intent.");
            }
            append(new Entry(id, old.scope, status, detail, false));
        }
    }

    public void acknowledge(String id) throws IOException {
        synchronized (IO_LOCK) {
            Entry old = require(id);
            if (!old.isFinal()) { throw new IOException("Cannot acknowledge an unfinished request."); }
            if (!old.acknowledged) {
                append(new Entry(id, old.scope, old.status, old.detail, true));
            }
        }
    }

    public int recoverInterrupted() throws IOException {
        synchronized (IO_LOCK) {
            int recovered = 0;
            for (Entry old : read().values()) {
                if (!old.isFinal()) {
                    append(new Entry(old.id, old.scope, "unknown",
                            "App interrupted; outcome unknown. No automatic retry.", false));
                    recovered++;
                }
            }
            return recovered;
        }
    }

    public void reportConflict(String id) throws IOException {
        synchronized (IO_LOCK) {
            Entry old = require(id);
            if (!old.isFinal()) { throw new IOException("Cannot reconcile an unfinished request."); }
            if (!old.acknowledged && !old.conflict) {
                append(new Entry(id, old.scope, old.status, old.detail, false, true));
            }
        }
    }

    public List<Entry> pendingReports(String scope) throws IOException {
        synchronized (IO_LOCK) {
            List<Entry> pending = new ArrayList<>();
            for (Entry entry : read().values()) {
                if (entry.scope.equals(scope) && entry.isFinal() && !entry.acknowledged && !entry.conflict) {
                    pending.add(entry);
                }
            }
            return pending;
        }
    }

    public List<Entry> entries() throws IOException {
        synchronized (IO_LOCK) { return new ArrayList<>(read().values()); }
    }

    private Entry require(String id) throws IOException {
        Entry entry = read().get(id);
        if (entry == null) { throw new IOException("Request not reserved."); }
        return entry;
    }

    private Map<String, Entry> read() throws IOException {
        Map<String, Entry> entries = new LinkedHashMap<>();
        if (!file.exists()) { return entries; }
        if (file.length() > MAX_BYTES) { throw new IOException("Journal is full; remote actions blocked."); }
        String text = new String(Files.readAllBytes(file.toPath()), StandardCharsets.UTF_8);
        if (!text.isEmpty() && !text.endsWith("\n")) {
            throw new IOException("Interrupted journal write; remote actions blocked.");
        }
        for (String line : text.split("\n")) {
            if (line.isEmpty()) { continue; }
            String[] parts = line.split("\t", -1);
            try {
                if (parts.length != 5 || !parts[1].matches("[0-9a-f]{64}")
                        || !(FINAL.contains(parts[2]) || "claimed".equals(parts[2])
                        || "dispatching".equals(parts[2])) || !parts[4].matches("[012]")) {
                    throw new IllegalArgumentException();
                }
                String id = SafetyPolicy.requestId(parts[0]);
                String detail = new String(Base64.getDecoder().decode(parts[3]), StandardCharsets.UTF_8);
                if (detail.length() > 240) { throw new IllegalArgumentException(); }
                entries.put(id, new Entry(id, parts[1], parts[2], detail, "1".equals(parts[4]), "2".equals(parts[4])));
            } catch (IllegalArgumentException exception) {
                throw new IOException("Journal integrity error; remote actions blocked.");
            }
        }
        return entries;
    }

    private void append(Entry entry) throws IOException {
        String line = entry.id + "\t" + entry.scope + "\t" + entry.status + "\t"
                + Base64.getEncoder().encodeToString(entry.detail.getBytes(StandardCharsets.UTF_8))
                + "\t" + (entry.conflict ? "2" : entry.acknowledged ? "1" : "0") + "\n";
        byte[] bytes = line.getBytes(StandardCharsets.UTF_8);
        if (file.length() + bytes.length > MAX_BYTES) {
            throw new IOException("Journal is full; remote actions blocked.");
        }
        try (FileOutputStream output = new FileOutputStream(file, true)) {
            output.write(bytes);
            output.flush();
            output.getFD().sync();
        }
    }
}
