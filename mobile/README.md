# Detailflow mobile app

An Expo / React Native app for iPhone and Android. The setup screen uses native
text inputs, keyboard handling, safe areas, switches, a unit-selection sheet and
a native catalog list. It keeps the cream/green design from the original preview.
There is no WebView and the app does not open a browser to create services.

## Windows + Ubuntu/WSL shortcut

After the initial setup, keep your Windows Android Emulator open and run this
from the project root in **Ubuntu/WSL**:

```bash
bash dev.sh
```

Or, from `mobile/`, run `npm run android:wsl`. Stop any old Expo process with
Ctrl+C first. PostgreSQL should already be running.

The launcher finds Windows ADB, connects both the API and Metro to the emulator,
starts FastAPI if it is not already running, starts Expo in WSL, and opens
Detailflow automatically. All commands and logs stay in the WSL terminal. No
Windows copy of the mobile folder or PowerShell commands are needed.

The shortcut refreshes port forwarding and restarts Expo Go once Metro is ready,
so an old app session does not retain a connection to a stopped Expo server.
Keep the WSL terminal running while testing; stopping it disconnects live reload.

The launcher overrides the mobile API URL for this session with
`http://127.0.0.1:8000`, which reaches the backend through ADB reverse forwarding
and Windows/WSL localhost forwarding. It does not edit your `.env` files. Ctrl+C
stops the session and any backend it started; an existing backend is left running.

If multiple devices are running, use
`ANDROID_SERIAL=emulator-5554 bash dev.sh`. For a nonstandard Android SDK location,
set `ADB_EXE` to the WSL path of Windows `adb.exe`. If WSL cannot launch Windows
executables, enable WSL interoperability before using this shortcut.

## 1. Start the backend

From the repository root:

```bash
source .venv/bin/activate
fastapi dev backend/app/main.py --host 0.0.0.0
```

The root `.env` still holds `DATABASE_URL` and `DEV_BUSINESS_ID`. Keep those values
on the server. The current development business context is shared by requests;
use a trusted local network while authentication is being implemented.

## 2. Configure the phone's API address

Keep your computer and phone on the same Wi-Fi. Find your computer's local IPv4
address with `hostname -I` on Linux, `ipconfig getifaddr en0` on macOS (Wi-Fi), or
`ipconfig` on Windows. If multiple addresses are listed, use the Wi-Fi/LAN address
reachable from the phone.

From `mobile/`:

```bash
cp .env.example .env
```

Edit **mobile/.env**, replacing the example address with your computer's address:

```dotenv
EXPO_PUBLIC_API_URL=http://192.168.1.20:8000
```

This is an HTTP API address, not a database URL. `localhost` on a physical phone
means the phone itself. The Android emulator can use `http://10.0.2.2:8000`;
the iOS Simulator on the backend's Mac can use `http://127.0.0.1:8000`.

If the setting is omitted, the app attempts to infer your computer from Expo's
LAN server address. An explicit address is more predictable, especially with
tunnels, virtual machines or WSL. An Expo tunnel only tunnels Metro; it does not
make FastAPI reachable. Use a separately reachable API URL in that case.

`EXPO_PUBLIC_` values are included in the app bundle. Never put database passwords
or other secrets in them. Restart Metro after changing `mobile/.env`.

## 3. Install and run the native app

Use Node.js 22.13 or newer:

```bash
cd mobile
npm install
npm start
```

Install a compatible **Expo Go** build on your phone using the
[official device selector](https://expo.dev/go?device=true&sdkVersion=57).
This project follows the
[SDK 57 template](https://github.com/expo/expo/blob/sdk-57/templates/expo-template-blank-typescript/package.json),
which the [Expo project guide](https://docs.expo.dev/get-started/create-a-project/)
currently selects for physical-device Expo Go development. The Expo Go SDK and
the project's SDK must match. Then scan the QR code printed by `npm start` to
open **Detailflow inside Expo Go**, not in a browser.

For Android, use the scanner in Expo Go. For iPhone, follow the current
[Expo iOS device setup](https://docs.expo.dev/get-started/set-up-your-environment/?device=physical&platform=ios).
Expo CLI and Expo Go may require the same Expo account (`npx expo login`).
Current iOS distribution for newer SDKs may require a provisioned Expo Go build
and an Apple Developer membership; check the linked selector/setup instead of
assuming the App Store build supports this SDK.

For local emulators/simulators, use `npm run android` or `npm run ios` (iOS
Simulator requires macOS and Xcode).

## Development build alternative

If Expo Go is unavailable/incompatible, the project includes `expo-dev-client`
and a development profile in `eas.json`:

```bash
npx eas-cli@latest build --profile development --platform android
# For iPhone, use --platform ios and follow signing/device registration.
npx expo start --dev-client --lan
```

This builds an installable development app. EAS builds use your Expo account;
physical iOS builds require Apple's signing setup. For local native builds,
`npx expo run:android --device` requires Android tooling, and
`npx expo run:ios --device` requires macOS/Xcode and signing.

The app configuration permits HTTP for local development. Use an HTTPS API and
remove the broad HTTP transport exceptions before preparing a release build.

## Test persistence

1. Open Detailflow in Expo Go or the installed development app.
2. Enter a name, description, starting price or custom pricing, optional duration,
   pricing unit and availability.
3. Tap **Create service**. Success appears only after the existing API returns
   the database-created record.
4. Open **My services** to fetch the real catalog. Close/reopen the app and check
   the catalog again to confirm persistence. Pull down to refresh it.

The native app uses `POST /api/v1/services` and `GET /api/v1/services`. Prices are
currently shown as USD, matching the default business currency. Dollar amounts
are converted to exact integer cents; custom prices and blank durations become
null. Saving disables the form and guards repeated taps. Failed saves retain
input; interrupted requests offer a catalog check before another attempt.

If the API cannot be reached, check FastAPI is bound to `0.0.0.0`, the address in
`mobile/.env`, firewall access to port 8000, and Wi-Fi isolation/VPN settings.
The backend connection checker can verify database credentials separately:

```bash
# From the repository root, with the backend virtual environment active:
python -m backend.app.db.check_connection
```

## Files

- `App.tsx`, `index.ts`: native app entry point and safe-area/status-bar setup.
- `src/screens/ServiceSetupScreen.tsx`: native onboarding form and saved state.
- `src/components/CatalogSheet.tsx`: native modal/list, refresh and pagination.
- `src/components/ServiceCard.tsx`: shared native preview/saved service card.
- `src/api/services.mjs`: absolute API addressing for devices and emulators.
- `src/connection.ts`: Expo environment/Metro connection settings.
- `src/theme.ts`: cream, forest green and serif design styles.
- `public/service-client.mjs`: validation and API transport shared with the
  original browser preview. It has no DOM dependencies.
- `public/`: retained browser preview at `/onboarding/`, independent of the
  native app; useful as a design reference, not needed for phone testing.

## Checks

```bash
cd mobile
npm run typecheck
npm run check:client
npm test
npx expo install --check
```

The API/validation tests require no dependency installation and can also be run
directly with `node tests/native-api.test.mjs` and
`node tests/service-client.test.mjs`. Typechecking, Metro bundling and native
device testing require installed dependencies. No package lockfile is committed
until npm installation succeeds.
