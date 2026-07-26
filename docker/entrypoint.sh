#!/usr/bin/env bash
# Start a virtual X display for headful Chromium (unless YAD2_HEADLESS=1),
# then run the app. Using Xvfb directly avoids xvfb-run, which could hang in
# this image.
set -e

headless="${YAD2_HEADLESS:-0}"
if [ "$headless" = "0" ] || [ "$headless" = "false" ] || [ "$headless" = "no" ]; then
  export DISPLAY=":99"
  rm -f /tmp/.X99-lock 2>/dev/null || true
  Xvfb :99 -screen 0 1360x1020x24 -nolisten tcp >/tmp/xvfb.log 2>&1 &

  # Wait (up to ~10s) for the display socket to appear before continuing.
  for _ in $(seq 1 50); do
    [ -e /tmp/.X11-unix/X99 ] && break
    sleep 0.2
  done
fi

exec python main.py "$@"
