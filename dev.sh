#!/usr/bin/env bash
# Run the backend and native Android app entirely from a WSL terminal.
set -euo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
API_PID=""
OPEN_PID=""

cleanup() {
  # Stop only processes started by this script, never an existing backend.
  if [[ -n "$OPEN_PID" ]]; then kill "$OPEN_PID" 2>/dev/null || true; fi
  if [[ -n "$API_PID" ]]; then
    kill "$API_PID" 2>/dev/null || true
    wait "$API_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

fail() { printf '\n%s\n' "$*" >&2; exit 1; }
for tool in node curl wslpath; do
  command -v "$tool" >/dev/null || fail "Missing $tool. Run this command in your Ubuntu/WSL terminal."
done
[[ -f "$PROJECT_ROOT/mobile/node_modules/expo/bin/cli" ]] || fail "Install mobile dependencies first: cd '$PROJECT_ROOT/mobile' && npm install"
[[ -f "$PROJECT_ROOT/mobile/node_modules/expo-secure-store/package.json" ]] || fail "Owner login needs the new secure storage dependency. Run: cd '$PROJECT_ROOT/mobile' && npm install"

# ADB_EXE can override the SDK location using a Linux/WSL path.
if [[ -n "${ADB_EXE:-}" ]]; then
  WINDOWS_ADB="$ADB_EXE"
else
  command -v powershell.exe >/dev/null || fail "Windows integration is unavailable. Ensure powershell.exe is accessible from WSL, or set ADB_EXE to the WSL path of Windows adb.exe."
  ADB_WINDOWS_PATH="$(powershell.exe -NoProfile -NonInteractive -Command '[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new(); [Console]::Write((Join-Path $env:LOCALAPPDATA "Android\Sdk\platform-tools\adb.exe"))' | tr -d '\r')"
  WINDOWS_ADB="$(wslpath -u "$ADB_WINDOWS_PATH")"
fi
[[ -f "$WINDOWS_ADB" ]] || fail "Windows adb.exe was not found. Set ADB_EXE to its WSL path if you installed Android Studio's SDK in a custom location."

DEVICES_OUTPUT="$("$WINDOWS_ADB" devices | tr -d '\r')"
mapfile -t CONNECTED_DEVICES < <(printf '%s\n' "$DEVICES_OUTPUT" | awk '$2 == "device" { print $1 }')
if [[ -n "${ANDROID_SERIAL:-}" ]]; then
  DEVICE=""
  for candidate in "${CONNECTED_DEVICES[@]}"; do
    if [[ "$candidate" == "$ANDROID_SERIAL" ]]; then DEVICE="$candidate"; fi
  done
  [[ -n "$DEVICE" ]] || fail "ANDROID_SERIAL is not an online device. Start your virtual phone in Android Studio's Device Manager."
elif [[ "${#CONNECTED_DEVICES[@]}" == 1 ]]; then
  DEVICE="${CONNECTED_DEVICES[0]}"
elif [[ "${#CONNECTED_DEVICES[@]}" == 0 ]]; then
  fail "Start your virtual phone in Android Studio's Device Manager, then run this command again."
else
  fail "More than one device is connected. Choose one with ANDROID_SERIAL=emulator-5554 bash dev.sh"
fi

adb() { "$WINDOWS_ADB" -s "$DEVICE" "$@"; }
[[ "$(adb shell pm path host.exp.exponent | tr -d '\r')" == package:* ]] || fail "Install Expo Go on the virtual phone first: https://expo.dev/go?device=false&platform=android&sdkVersion=57"

if curl -fsS --max-time 1 http://127.0.0.1:8081/status 2>/dev/null | grep -q 'packager-status:running'; then
  fail "Expo is already running on port 8081. Stop that Expo terminal with Ctrl+C, then run this command again."
fi

if curl -fsS --max-time 1 http://127.0.0.1:8000/health >/dev/null 2>&1; then
  printf 'Using your running backend on port 8000.\n'
else
  [[ -x "$PROJECT_ROOT/.venv/bin/python" ]] || fail "Backend virtual environment missing. Install the backend dependencies first."
  printf 'Starting FastAPI on port 8000…\n'
  (cd "$PROJECT_ROOT" && exec .venv/bin/python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload) &
  API_PID=$!
  API_READY=false
  for ((attempt=0; attempt<30; attempt++)); do
    if curl -fsS --max-time 1 http://127.0.0.1:8000/health >/dev/null 2>&1; then API_READY=true; break; fi
    kill -0 "$API_PID" 2>/dev/null || fail "The backend could not start. Check the error above."
    sleep 1
  done
  [[ "$API_READY" == true ]] || fail "The backend did not become ready on port 8000."
fi

# Both services cross the same Windows localhost -> WSL bridge that already
# works for the emulator. The phone uses localhost through these ADB mappings.
printf 'Connecting %s to the app and API…\n' "$DEVICE"
# Replace old mappings so connections from an earlier Expo session do not linger.
adb reverse --remove tcp:8081 >/dev/null 2>&1 || true
adb reverse --remove tcp:8000 >/dev/null 2>&1 || true
adb reverse tcp:8081 tcp:8081
adb reverse tcp:8000 tcp:8000

# Wait for Metro before opening Expo Go; no second terminal is needed.
(
  trap - EXIT INT TERM
  for ((attempt=0; attempt<90; attempt++)); do
    if curl -fsS --max-time 1 http://127.0.0.1:8081/status 2>/dev/null | grep -q 'packager-status:running'; then
      printf '\nOpening Detailflow on your virtual phone…\n'
      # An intent delivered to an already-running Expo Go activity may retain
      # the old bundle/HMR socket. Reopen it only after the new Metro is ready.
      adb reverse tcp:8081 tcp:8081
      adb reverse tcp:8000 tcp:8000
      adb shell am force-stop host.exp.exponent
      adb shell am start -a android.intent.action.VIEW -d 'exp://127.0.0.1:8081' -p host.exp.exponent
      exit 0
    fi
    sleep 1
  done
  printf '\nExpo did not become ready. Check its output above.\n' >&2
) &
OPEN_PID=$!

printf 'Starting Expo. Keep this WSL terminal open; Ctrl+C stops this session.\n'
cd "$PROJECT_ROOT/mobile"
EXPO_PUBLIC_API_URL=http://127.0.0.1:8000 node node_modules/expo/bin/cli start --go --localhost --port 8081
