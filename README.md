# FGO-JP-AutoRoute

**Windows 11 · MuMu Player 12 · 日版 FGO**

## v0.4.0 Windows 原生桌面版

這個版本改為獨立 Windows 視窗，不會自動開啟 Chrome。

### 功能

- MuMu ADB 連線狀態。
- 顯示 MuMu 即時遊戲畫面。
- 每 2 秒自動更新截圖。
- 可手動指定 MuMu 的 `adb.exe` 路徑。
- Windows 使用者執行 EXE 不需要另外安裝 Python。

### 下載 EXE

1. 開啟本 Repository 的 **Actions**。
2. 選擇最新的 **Build Windows Desktop EXE**。
3. 等待工作顯示綠色成功。
4. 在 Artifacts 下載 `FGO-JP-AutoRoute-Windows-x64`。
5. 解壓縮後執行 `FGO-JP-AutoRoute.exe`。

Python 只會在 GitHub 雲端 Windows 編譯機使用，不需要安裝在你的電腦。

### 第一次使用

1. 開啟 MuMu 12 和日版 FGO。
2. 執行 EXE。
3. ADB 位址預設為 `127.0.0.1:16416)。若你的 MuMu 使用不同連接埠，請修改此欄位。
4. 按「連接 MuMu」。
5. 連線成功後，右側狀態會顯示已連線，遊戲畫面每 2 秒自動更新。

若程式找不到 ADB，按「選擇 ADB」，指定 MuMu 安裝資料夾中的 `adb.exe`。

## 版本範圍

v0.4.0 先提供 Windows 原生視窗、ADB 連線及自動截圖監看；遊戲內操作仍由使用者自行完成。此版本不會自動選關、戰鬥或刷關。
