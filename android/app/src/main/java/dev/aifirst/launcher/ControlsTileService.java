package dev.aifirst.launcher;

import android.annotation.SuppressLint;
import android.app.PendingIntent;
import android.content.Intent;
import android.os.Build;
import android.service.quicksettings.Tile;
import android.service.quicksettings.TileService;

/** Android binds this only as a Quick Settings tile; no worker, polling, or overlay. */
public final class ControlsTileService extends TileService {
    @Override public void onStartListening() {
        super.onStartListening();
        Tile tile = getQsTile();
        if (tile != null) {
            tile.setState(Tile.STATE_INACTIVE);
            tile.setLabel(getString(R.string.controls_tile));
            tile.setContentDescription(getString(R.string.controls_tile_description));
            tile.updateTile();
        }
    }

    @Override public void onClick() {
        super.onClick();
        if (isLocked()) { unlockAndRun(this::openControls); }
        else { openControls(); }
    }

    private void openControls() {
        Intent intent = MainActivity.controlsIntent(this);
        if (Build.VERSION.SDK_INT >= 34) {
            PendingIntent controls = PendingIntent.getActivity(this, 0, intent,
                    PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
            startActivityAndCollapse(controls);
        } else {
            openControlsBeforeAndroid14(intent);
        }
    }

    @SuppressLint("StartActivityAndCollapseDeprecated")
    @SuppressWarnings("deprecation")
    private void openControlsBeforeAndroid14(Intent intent) {
        // PendingIntent overload exists only on API 34+. This compatibility call is
        // unreachable on Android 14+, where the deprecated overload would throw.
        if (Build.VERSION.SDK_INT < 34) { startActivityAndCollapse(intent); }
    }
}
