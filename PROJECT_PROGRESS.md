# Project Progress

更新日期：2026-07-13

## 專案摘要

本專案是使用 Python 開發的本地 YouTube 音樂下載與播放程式。第一階段先完成桌面版 UI，可以管理歌手、取得歌手 YouTube 頻道影片列表、顯示封面、批次下載勾選影片為 MP3，並使用 SQLite 保存歌手與下載紀錄。

## 技術選型

- Python
- CustomTkinter
- SQLite
- yt-dlp
- FFmpeg
- Pillow
- requests 或 httpx

## 第一階段完成標準

- [ ] `main.py` 可以啟動桌面視窗。
- [ ] 第一次啟動時自動建立 SQLite 資料庫。
- [ ] 可以輸入歌手 ID 與 YouTube 頻道網址。
- [ ] 可以自動取得頻道名稱。
- [ ] 可以將歌手存入 SQLite。
- [ ] 可以顯示及選擇已新增歌手。
- [ ] 可以取得該頻道的影片列表。
- [ ] 可以顯示影片封面。
- [ ] 可以搜尋影片。
- [ ] 可以全選及取消全選影片。
- [ ] 可以批次下載勾選影片為 MP3。
- [ ] 可以顯示每部影片的下載狀態。
- [ ] 可以避免重複下載。
- [ ] 重新開啟程式後，歌手及下載紀錄仍然存在。
- [ ] `README.md` 包含安裝、FFmpeg 設定及執行方法。
- [x] 執行基本測試。
- [x] 檢查 import 是否正確。
- [ ] 確認 `main.py` 可以啟動。

## 建議開發順序

1. 建立專案目錄與基礎檔案：`main.py`、`requirements.txt`、`README.md`、`config.py`。
2. 建立 SQLite 連線、schema 初始化、repository 層。
3. 建立資料模型與檔名清理工具。
4. 建立 YouTube service，先支援取得頻道名稱與最近影片列表。
5. 建立 CustomTkinter 主視窗與歌手管理頁。
6. 建立影片下載頁與可捲動影片列表。
7. 加入背景執行緒，避免 UI 被 yt-dlp、網路請求與下載流程阻塞。
8. 加入封面載入與快取或記憶體縮圖處理。
9. 加入批次下載、狀態更新與重複下載保護。
10. 補上 README 與基本啟動測試。

## 目前狀態

- [x] 已讀取 `project.md`。
- [x] 已建立進度追蹤檔。
- [x] 已確認第一版使用 `yt-dlp`。
- [x] 已確認封面使用 `cache/thumbnails/{youtube_video_id}.jpg` 快取。
- [x] 已確認第一版影片列表上限為 50，超過時在 UI 顯示提醒。
- [x] 已確認歌曲名稱修改功能延後到第二階段。
- [x] 已確認資料庫保存 YouTube `channel_id` 並用它避免同頻道重複新增。
- [x] 已建立程式碼結構。
- [x] 已實作 SQLite 初始化與 repository。
- [x] 已實作基礎 CustomTkinter UI。
- [x] 已實作 yt-dlp 頻道資訊、影片列表與下載 service。
- [x] 第二階段：已設定 UI 字體為微軟正黑體。
- [x] 第二階段：影片列表改成每頁 20 筆。
- [x] 第二階段：影片列表改成先抓 100 筆，接近最後一頁時抓下一批 100 筆。
- [x] 第二階段：新增歌曲管理分頁。
- [x] 第二階段：支援修改歌曲名稱並同步改 MP3 檔名。
- [x] 第二階段：改名時若檔名重複會阻止。
- [x] 第二階段：支援修改 channel name，artist_id 仍不可修改。
- [ ] 尚未實際人工測試 YouTube 下載。
- [ ] 目前環境的 Python/Tcl 安裝不完整，App 建立檢查被 `Can't find a usable init.tcl` 阻擋。

## 需要注意的問題

- yt-dlp 取得頻道資料與影片列表可能受網路、YouTube 版面變動、地區或頻道型態影響，需要 UI 顯示明確錯誤。
- FFmpeg 必須存在於系統 PATH，或在 README 中清楚說明如何設定。
- Tkinter 元件不能直接從背景執行緒更新，需要透過主執行緒排程更新 UI。
- 下載前後都要檢查 `youtube_video_id`，避免批次下載造成重複紀錄。
- SQLite 連線若跨執行緒使用要小心，建議每個 repository 操作建立短生命週期連線或集中封裝。
- 歌手 ID 要做大小寫不敏感的唯一判斷，實作時需要明確規則，例如儲存 normalized key 或建立 case-insensitive unique index。
- 頻道 URL 的唯一判斷可能需要正規化，否則同一頻道不同 URL 形式可能繞過重複檢查。
- 影片標題可能包含 Windows 禁止字元、很長的字串或結尾句點，檔名必須集中清理。

## 已決定事項

- 第一版使用 `yt-dlp`，不要改用 `ytjs.dev`。
- 使用 `requests` 下載封面。
- 封面快取到 `cache/thumbnails/`。
- 影片列表上限設為 `MAX_VIDEOS_PER_CHANNEL = 50`。
- 超過 50 部影片時，UI 顯示「只顯示最近 50 部」提醒。
- 歌曲名稱修改功能排到第二階段。
- 使用者輸入 YouTube 頻道後，程式透過 yt-dlp 取得 `channel_id`，資料庫保存並用 `channel_id` 判斷同一頻道是否已存在。
- 第二階段先不做全曲播放器。
- 第二階段先不允許修改自訂 `artist_id`。
- 歌曲改名後 MP3 檔名維持 `歌手ID_歌曲名稱.mp3`。
- 歌曲改名造成檔名重複時，直接阻止並提示錯誤。
