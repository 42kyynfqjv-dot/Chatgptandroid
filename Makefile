PYTHON ?= python3

.PHONY: test test-bridge test-os test-android test-gestures apk environment

test: test-os test-bridge test-android test-gestures

test-os:
	$(PYTHON) -m unittest discover -s tests -v

test-bridge:
	cd bridge && $(PYTHON) -m unittest discover -s tests -v

test-android:
	bash android/test-core.sh

test-gestures:
	bash os/gestures/test.sh
	bash os/framework/test.sh

apk:
	cd android && ./gradlew --no-daemon assembleDebug lintDebug

environment:
	$(PYTHON) scripts/environment-report.py
