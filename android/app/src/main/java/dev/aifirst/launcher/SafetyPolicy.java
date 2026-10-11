package dev.aifirst.launcher;

import java.net.URI;
import java.net.URISyntaxException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Locale;
import java.util.Set;
import java.util.UUID;

/** Pure Java policy shared by the phone client and dependency-free safety tests. */
public final class SafetyPolicy {
    private static final Set<String> APPS = Set.of("chatgpt", "settings", "clock", "browser");

    private SafetyPolicy() { }

    public static String origin(String raw) {
        try {
            URI uri = new URI(raw.trim());
            if (!"https".equalsIgnoreCase(uri.getScheme()) || uri.getHost() == null
                    || uri.getRawUserInfo() != null || uri.getRawQuery() != null
                    || uri.getRawFragment() != null || uri.getPort() == 0
                    || uri.getPort() > 65535
                    || !(uri.getRawPath().isEmpty() || "/".equals(uri.getRawPath()))) {
                throw new IllegalArgumentException("Use an HTTPS origin, without a path, login, query, or fragment.");
            }
            return new URI("https", null, uri.getHost().toLowerCase(Locale.ROOT),
                    uri.getPort() == 443 ? -1 : uri.getPort(), null, null, null).toString();
        } catch (URISyntaxException exception) {
            throw new IllegalArgumentException("Invalid HTTPS relay origin.");
        }
    }

    public static String token(String raw) {
        if (raw == null || raw.length() < 32 || raw.length() > 512
                || !raw.matches("[A-Za-z0-9_.~+/-]+={0,2}")) {
            throw new IllegalArgumentException("Enter a device bearer token of 32–512 safe ASCII characters.");
        }
        return raw;
    }

    public static String requestId(String id) {
        if (id == null || !id.matches("[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
                || !UUID.fromString(id).toString().equals(id)) {
            throw new IllegalArgumentException("Invalid request identifier.");
        }
        return id;
    }

    public static String app(String app) {
        if (app == null || !APPS.contains(app)) {
            throw new IllegalArgumentException("This app is not allowed.");
        }
        return app;
    }

    public static int integer(Object value, int min, int max) {
        if (!(value instanceof Integer) && !(value instanceof Long)) {
            throw new IllegalArgumentException("An integer is required.");
        }
        long number = ((Number) value).longValue();
        if (number < min || number > max) {
            throw new IllegalArgumentException("Number outside the allowed range.");
        }
        return (int) number;
    }

    public static String label(String label) {
        if (label == null || label.codePointCount(0, label.length()) > 80) {
            throw new IllegalArgumentException("Alarm labels must have at most 80 characters.");
        }
        for (int offset = 0; offset < label.length();) {
            int cp = label.codePointAt(offset);
            int kind = Character.getType(cp);
            if (Character.isISOControl(cp) || kind == Character.FORMAT
                    || kind == Character.SURROGATE || kind == Character.LINE_SEPARATOR
                    || kind == Character.PARAGRAPH_SEPARATOR) {
                throw new IllegalArgumentException("Alarm label contains an unsafe control character.");
            }
            offset += Character.charCount(cp);
        }
        return label;
    }

    public static boolean expired(double expiresAt, long nowMillis) {
        return !Double.isFinite(expiresAt) || expiresAt <= nowMillis / 1000.0;
    }

    public static String scope(String origin) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(origin.getBytes(StandardCharsets.UTF_8));
            StringBuilder result = new StringBuilder();
            for (byte value : digest) {
                result.append(String.format(Locale.ROOT, "%02x", value & 0xff));
            }
            return result.toString();
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException("SHA-256 unavailable.", exception);
        }
    }
}
