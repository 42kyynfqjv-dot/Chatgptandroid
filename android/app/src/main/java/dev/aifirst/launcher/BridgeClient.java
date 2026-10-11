package dev.aifirst.launcher;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.URL;
import java.nio.charset.StandardCharsets;

import javax.net.ssl.HttpsURLConnection;

/** Outbound, bounded HTTPS. No redirects, cleartext, polling loop, or hidden endpoints. */
final class BridgeClient {
    enum ReportResult { ACKNOWLEDGED, CONFLICT }

    private static final class RelayStatusException extends IOException {
        final int status;
        RelayStatusException(int status) {
            super("Relay rejected the request (HTTP " + status + ").");
            this.status = status;
        }
    }
    private final String origin;
    private final String token;
    private volatile HttpsURLConnection active;
    private volatile boolean cancelled;

    BridgeClient(String origin, String token) {
        this.origin = SafetyPolicy.origin(origin);
        this.token = SafetyPolicy.token(token);
    }

    BridgeAction next() throws IOException, JSONException {
        JSONObject response = request("GET", "/v1/device/next", null);
        if (!response.has("action")) { throw new IOException("Relay response is invalid."); }
        return response.isNull("action") ? null : new BridgeAction(response.getJSONObject("action"));
    }

    ReportResult report(RequestJournal.Entry entry) throws IOException, JSONException {
        JSONObject body = new JSONObject();
        body.put("status", entry.status);
        body.put("detail", entry.detail);
        try {
            JSONObject receipt = request("POST", "/v1/device/actions/" + SafetyPolicy.requestId(entry.id) + "/result", body);
            if (!entry.id.equals(receipt.get("id")) || !entry.status.equals(receipt.get("status"))
                    || !entry.detail.equals(receipt.get("detail"))) {
                throw new IOException("Relay receipt does not match the saved result.");
            }
            return ReportResult.ACKNOWLEDGED;
        } catch (RelayStatusException exception) {
            if (exception.status == 404 || exception.status == 409) { return ReportResult.CONFLICT; }
            throw exception;
        }
    }

    void cancel() {
        cancelled = true;
        HttpsURLConnection connection = active;
        if (connection != null) { connection.disconnect(); }
    }

    private JSONObject request(String method, String path, JSONObject body) throws IOException, JSONException {
        if (cancelled) { throw new IOException("Connection cancelled."); }
        HttpsURLConnection connection = (HttpsURLConnection) new URL(origin + path).openConnection();
        active = connection;
        try {
            if (cancelled) { throw new IOException("Connection cancelled."); }
            connection.setInstanceFollowRedirects(false);
            connection.setConnectTimeout(10000);
            connection.setReadTimeout(10000);
            connection.setRequestMethod(method);
            connection.setRequestProperty("Authorization", "Bearer " + token);
            connection.setRequestProperty("Accept", "application/json");
            connection.setUseCaches(false);
            if (body != null) {
                byte[] bytes = body.toString().getBytes(StandardCharsets.UTF_8);
                connection.setDoOutput(true);
                connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                connection.setFixedLengthStreamingMode(bytes.length);
                try (OutputStream output = connection.getOutputStream()) { output.write(bytes); }
            }
            int status = connection.getResponseCode();
            if (status != 200) {
                // Deliberately do not reflect untrusted bodies or URLs (which may contain secrets).
                throw new RelayStatusException(status);
            }
            try (InputStream input = connection.getInputStream();
                    ByteArrayOutputStream output = new ByteArrayOutputStream()) {
                byte[] buffer = new byte[4096];
                int count;
                while ((count = input.read(buffer)) != -1) {
                    if (cancelled) { throw new IOException("Connection cancelled."); }
                    if (output.size() + count > 65536) { throw new IOException("Relay response is too large."); }
                    output.write(buffer, 0, count);
                }
                return new JSONObject(output.toString(StandardCharsets.UTF_8.name()));
            }
        } finally {
            active = null;
            connection.disconnect();
        }
    }
}
