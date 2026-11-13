# FGO-JP-AutoRoute Windows Desktop Monitor

This desktop build is a native Windows window for MuMu Player 12 monitoring.

## Features

- No browser window.
- ADB connection status.
- MuMu screenshot preview.
- Automatic screenshot refresh every 2 seconds.
- Select the MuMu `adb.exe` path if auto-detection fails.
- No Python installation required on the Windows PC that runs the packaged EXE.

## Build

The GitHub Actions workflow builds the EXE on a Windows runner. Python is only used on the cloud build machine.

## Use

1. Start MuMu Player 12 and Fate/Grand Order JP.
2. Run `FGO-JP-AutoRoute.exe`.
3. Use the default ADB address `127.0.0.1:16416`, or enter the port configured by MuMu.
4. Click **連接 MuMu**.
5. The screenshot preview refreshes every two seconds.

If ADB is not detected, click **選擇 ADB** and select the `adb.exe` installed with MuMu.

This build is a desktop monitor. In-game actions remain manual.
