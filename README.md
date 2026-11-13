# FGO-JP-AutoRoute

日版 Fate/Grand Order 自動推圖工具，目標環境為 Windows 11 + MuMu Player 12。

## Windows EXE（使用者不需要安裝 Python）

本 Repository 已設定 GitHub Actions Windows x64 編譯流程。Python 只會在 GitHub 的雲端編譯機器上使用；下載 EXE 的 Windows 使用者不需要安裝 Python 或 pip。

### 首次上傳原始碼

請將專案原始碼 ZIP 上傳到 Repository 根目錄，檔名可使用：

`FGO-JP-AutoRoute-v0.3.0-source.zip`

或 `FGO-JP-AutoRoute-v0.3.0-source(1).zip`。

上傳完成並 Commit 到 `main` 後，`.github/workflows/build-exe.yml` 會自動解壓縮、安裝建置依賴、執行測試並打包單檔 `FGO-JP-AutoRoute.exe`。

### 下載編譯結果

1. 開啟 GitHub Repository 的 **Actions**。
2. 選擇 **Build Windows EXE** 最新一次成功的執行紀錄。
3. 在頁面下方 **Artifacts** 下載 `FGO-JP-AutoRoute-Windows-x64`。
4. 解壓縮後執行 `FGO-JP-AutoRoute.exe`。

之後更新原始碼 ZIP 並推送到 `main)，會再次自動編譯。推送 `v*` 標籤則會建立 GitHub Release。

## 注意

這是持續開發中的自動化輔助工具。使用者仍需在自己的日版 FGO / MuMu 12 畫面擷取模板並校準路線。尚未在所有章節與特殊戰鬥實機驗證，不保證能自動完成所有主線。首次測試請全程監看。自動化可能涉及遊戲服務條款及帳號風險，請先自行確認相關規範。
