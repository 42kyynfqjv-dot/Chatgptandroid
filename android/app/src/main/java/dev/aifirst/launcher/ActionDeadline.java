package dev.aifirst.launcher;

/** A local clock rollback cannot extend a request's original confirmation window. */
public final class ActionDeadline {
    private final long elapsedDeadline;

    public ActionDeadline(double expiresAt, long wallNowMillis, long elapsedNowMillis) {
        double remaining = expiresAt * 1000.0 - wallNowMillis;
        long bounded = Double.isFinite(remaining) ? (long) Math.max(0, Math.min(300000, remaining)) : 0;
        elapsedDeadline = elapsedNowMillis + bounded;
    }

    public boolean expired(double expiresAt, long wallNowMillis, long elapsedNowMillis) {
        return SafetyPolicy.expired(expiresAt, wallNowMillis) || elapsedNowMillis >= elapsedDeadline;
    }
}
