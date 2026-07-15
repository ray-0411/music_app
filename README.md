# YouTube Music Downloader

本專案是本地桌面版 YouTube 音樂下載工具。第一版支援歌手管理、取得 YouTube 頻道影片列表、顯示封面、批次下載 MP3，並用 SQLite 保存歌手與下載紀錄。

## 安裝

建議使用 Python 3.11 或更新版本。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## FFmpeg

下載 MP3 需要 FFmpeg。請先安裝 FFmpeg，並確認 `ffmpeg.exe` 可以從命令列執行。

```powershell
ffmpeg -version
```

Windows 可以使用其中一種方式安裝：

```powershell
winget install Gyan.FFmpeg
```

或手動下載 FFmpeg，將 `bin` 目錄加入系統 `PATH`。

## VLC

音樂播放器使用 `python-vlc` 控制本機 MP3 播放。除了 Python 套件外，也需要安裝 VLC 桌面版。

```powershell
winget install VideoLAN.VLC
```

如果播放器頁顯示找不到 VLC，請確認 VLC 已安裝，並重新開啟程式。

## 執行

```powershell
python main.py
```

第一次啟動會自動建立 `data/app.db`。

如果啟動時出現 `Can't find a usable init.tcl`，代表目前 Python 的 Tcl/Tk 安裝不完整。請重新安裝官方 Python，安裝時確認包含 `tcl/tk and IDLE`，或改用一個 Tkinter 可正常啟動的 Python 環境。

## 目前功能

- 新增歌手：輸入自訂歌手 ID 與 YouTube 頻道網址。
- 新增歌手前可以先預覽頻道頭像、頻道名稱、channel ID 與影片總數。
- 使用 yt-dlp 取得頻道名稱與 channel ID。
- 資料庫保存 `channel_id`，同一 YouTube 頻道不可重複新增。
- 資料庫保存歌手頭像 URL，頭像保存到 `assets/artists/`。
- 歌手 ID 大小寫不敏感且不可重複。
- 可以修改 YouTube 頻道顯示名稱；自訂歌手 ID 目前不可修改。
- 歌手管理列表會顯示歌手頭像。
- 取得所選歌手的一般影片列表，先抓 100 部。
- 影片列表每頁 20 部，進入接近最後一頁時會自動抓下一批 100 部。
- 如果 yt-dlp 有取得頻道影片總數，UI 會顯示約略總數。
- 影片列表會背景補抓目前頁面的詳細資料，用來更新上傳日期與觀看人數。
- 觀看人數使用千分位格式，例如 `1,234,567`。
- 顯示影片封面並快取到 `cache/thumbnails/`。
- 下載歌曲時會同步保存歌曲縮圖到 `assets/songs/`。
- 搜尋、全選、取消全選影片。
- 批次下載勾選影片為 MP3。
- 下載後寫入 SQLite，重新開啟後仍保留紀錄。
- 已下載影片預設不能再次勾選。
- 如果資料庫記錄已下載但 MP3 檔案不存在，UI 顯示「檔案遺失」。
- 新增「歌曲管理」分頁，顯示所有下載紀錄。
- 歌曲管理列表會顯示歌曲縮圖。
- 歌曲管理與歌手管理採用列表加「編輯」按鈕，按下後才進入該筆資料的編輯區。
- 可以修改歌曲名稱，並同步改 MP3 檔名。
- 改名後 MP3 檔名維持 `歌手ID_歌曲名稱.mp3`。
- 若改名後檔名重複，會阻止並顯示錯誤。
- 新增「標籤管理」分頁，可新增歌手標籤的上層分類與下層選項。
- 歌手標籤支援雙層結構，例如 `性別 -> 女`。
- 歌手編輯頁可以對每個分類多選下層標籤。
- 停用標籤採假刪除，資料會保留在 SQLite 中。
- 新增「音樂播放器」首頁，可順序播放已下載 MP3。
- 播放器支援播放/暫停、上一首、下一首與拖曳時間條跳轉。
- 播放器左側顯示上一首、本首、下一首。
- 播放器預留標籤偏好設定區與評分區。

## 專案結構

```text
main.py
config.py
requirements.txt
README.md
PROJECT_PROGRESS.md
database/
models/
services/
ui/
utils/
data/
downloads/
cache/thumbnails/
assets/artists/
assets/songs/
```

## 注意事項

- 目前使用 yt-dlp 作為 YouTube metadata 與下載來源。
- Shorts、直播存檔、播放清單尚未實作。
- 內建播放器需要 VLC 桌面版與 `python-vlc`。
- 自訂歌手 ID 暫時不可修改。
- 字體預設使用微軟正黑體。
- `cache/` 可刪除；刪除後只會讓影片列表暫存圖片重新下載，不影響 SQLite、MP3 或已保存的歌手/歌曲圖片。
- `assets/` 是本機持久圖片資料，包含已新增歌手頭像與已下載歌曲縮圖。
- 實際下載是否成功取決於 yt-dlp、YouTube 狀態、網路與 FFmpeg 設定。
- 若 yt-dlp 取得頻道資訊不穩，未來可以只替換 `services/youtube_service.py`，UI 與資料庫不需要大改。

## 已執行檢查

- `python -m compileall .`：通過。
- `python -c "from database.schema import initialize_database; initialize_database()"`：通過。
- 依賴 import 檢查：通過。
- App 建立檢查：目前被本機 Python/Tcl 安裝問題阻擋，錯誤為 `Can't find a usable init.tcl`。
