# FGO-JP-AutoRoute

**v0.4.0 · Windows 11 + MuMu 12 + 日版 FGO**

這次更新把操作方式改成 **Windows 原生桌面視窗**，並簡化推圖設定。

## v0.4.0 更新

- 雙擊 EXE 直接開啟獨立視窗，不再自動開 Chrome。
- MuMu 即時畫面連線後每 2 秒自動更新。
- 推圖設定提供簡易通關次數欄位。
- JSON 與戰鬥規則等進階設定預設收合。
- 一般使用者不需要安裝 Python。

## 下載 EXE

1. 開啟本 Repository 的 **Actions**。
2. 選擇最新的 **Build Windows Desktop EXE**。
3. 等待執行結果顯示成功。
4. 在 Artifacts 下載 `FGO-JP-AutoRoute-Windows-x64`。
5. 解壓縮並執行 `FGO-JP-AutoRoute.exe`。

Python 只用於 GitHub 雲端編譯。Windows 原生視窗使用 WebView2；Windows 11 通常已內建 WebView2 Runtime。

## 第一次使用

1. 開啟 MuMu 12 和日版 FGO。
2. 執行 EXE，按右上角「連接 MuMu」。
3. 確認即時畫面開始自動更新。
4. 到「推圖設定」載入倫敦示範路線。
5. 到「進階設定 → 畫面模板」依清單擷取必要模板。
6. 回到任務總覽，先勾選「安全預檢」並按開始。

## 目前功能範圍

內建範例為第一部第四特異點「倫敦」第六節。其他章節、特殊關卡與不同隊伍仍需自行建立並校準路線模板；尚不能保證所有主線都能自動推進。首次實際測試請全程監看。

自動化可能涉及遊戲服務條款及帳號風險，請先自行確認相關規範。
