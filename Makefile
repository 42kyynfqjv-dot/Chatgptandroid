PYTHON ?= python3

.PHONY: test test-bridge test-os test-android apk environment

test: test-os test-bridge test-android

test-os:
	$(PYTHON) -m unittest discover -s tests -v

test-bridge:
	cd bridge && $(PYTHON) -m unittest discover -s tests -v

test-android:
	bash android/test-core.sh

apk:
	cd android && ./gradlew --no-daemon assembleDebug lintDebug

environment:
	$(PYTHON) scripts/environment-report.py
