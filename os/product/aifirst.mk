# This file is inherited only by the pinned tegu device product.
# Keep upstream Launcher3/Quickstep, Settings, Dialer, Messaging and Clock intact.
PRODUCT_SOONG_NAMESPACES += vendor/adevtool/config/mk/aifirst

PRODUCT_PACKAGES += AIHome

# Static product overlays supply the initial HOME role and app routing defaults.
# Subsequent user HOME-role and AI Home toggle choices remain authoritative.
PRODUCT_PACKAGE_OVERLAYS += vendor/adevtool/config/mk/aifirst/overlay
