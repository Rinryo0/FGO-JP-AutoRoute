# FGO-JP-AutoRoute

日版 Fate/Grand Order 自動推圖工具，目標環境為 Windows 11 + MuMu Player 12。

## Windows EXE
本專案使用 GitHub Actions 在 Windows runner 上測試並打包單檔 EXE。一般使用者不需要安裝 Python。編譯完成後請到 **Actions → Build Windows EXE** 下載 Artifact；建立 `v0.3.0` 等 `v*` tag 後會建立 GitHub Release。

## 原始碼
完整專案原始碼暫以 `FGO-JP-AutoRoute-v0.3.0-source.zip` 保存，GitHub Actions 會先解壓縮，再執行測試及 PyInstaller 打包。

## 注意
此專案仍需使用者在自己的日版 FGO / MuMu 12 畫面擷取模板並校準路線。未經實機測試，不保證能自動完成所有主線或特殊戰鬥。請先監看測試；自動化可能涉及遊戲服務條款及帳號風險。
