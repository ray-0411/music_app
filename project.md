我要製作一個使用 Python 開發的本地 YouTube 音樂下載與播放程式。

目前先完成「歌手管理」與「歌曲下載」功能。程式不需要打包成 EXE，只需要執行 Python 後開啟一個小型桌面視窗。

請先閱讀完整需求、檢查實作上的問題，列出簡短開發計畫後再開始寫程式。不要一次加入需求以外的複雜功能。

# 一、技術需求

請使用：

* Python
* CustomTkinter 製作桌面 UI
* SQLite 儲存資料
* yt-dlp 取得 YouTube 頻道、影片資料及下載音訊
* FFmpeg 將音訊轉換成 MP3
* Pillow 顯示影片封面
* requests 或 httpx 取得封面圖片

程式不需要打包成 EXE。

請提供：

* requirements.txt
* README.md
* SQLite 初始化功能
* 清楚的專案目錄結構
* 基本錯誤處理
* 可直接執行的 main.py

# 二、功能一：歌手管理

使用者可以在 UI 新增歌手。

必填欄位：

1. 自訂歌手 ID
2. YouTube 頻道連結

需求：

* 歌手 ID 不可重複。
* 建議歌手 ID 只允許英文字母、數字、底線及連字號。
* 歌手 ID 比對時不區分英文大小寫。
* YouTube 頻道連結不可重複。
* 使用 yt-dlp 根據頻道連結自動取得 YouTube 頻道名稱。
* 自動取得的頻道名稱顯示在 UI 中。
* 新增完成後將資料存入 SQLite。
* UI 顯示目前已新增的所有歌手。
* 必須能選擇其中一位歌手，供下一個頁面取得影片。
* 網址無效、無法取得頻道資料或 ID 重複時，要在 UI 顯示明確錯誤訊息。

歌手資料庫欄位現在只是初步設計，之後可能會修改，因此請將所有 SQL 操作集中在獨立的 database 模組中，不要讓 UI 直接執行 SQL。

# 三、功能二：列出歌手的 YouTube 影片

使用者選擇歌手後，可以按下按鈕取得該歌手 YouTube 頻道的影片列表。

第一版先取得頻道一般影片。程式架構需要保留未來加入 Shorts、直播存檔或播放清單的可能性，但現在不用實作。

每部影片至少要記錄及顯示：

* 勾選框
* 影片封面縮圖
* YouTube 影片標題
* YouTube video ID
* 影片網址
* 影片長度
* 上傳日期；若 yt-dlp 沒有取得，可顯示未知
* 是否已經下載
* 目前下載狀態

影片列表需要提供：

* 全選
* 取消全選
* 依影片標題搜尋
* 重新整理影片列表
* 批次下載勾選項目

取得影片列表時不要下載影片本體。

如果頻道影片很多，不要讓 UI 長時間無回應。取得影片資訊及網路請求不能阻塞主 UI 執行緒。

第一版可以先限制顯示最近 50 部影片，但請將數量設為容易修改的設定值。

# 四、影片封面預覽

影片列表需要顯示影片封面。

優先使用 yt-dlp 回傳的 thumbnail 或 thumbnails 網址。

封面處理方式：

1. 使用封面網址取得圖片。
2. 使用 Pillow 將圖片縮放成適合列表顯示的尺寸，例如 160 × 90。
3. 保持圖片比例。
4. 圖片尚未載入時顯示預設封面。
5. 圖片取得失敗時不能使整個程式中斷。
6. 封面載入不可阻塞主 UI。
7. 限制同時載入的封面數量，避免大量請求造成卡頓。

封面不需要永久保存。

可以選擇：

* 直接在記憶體中載入；或
* 暫存在 cache/thumbnails/{youtube_video_id}.jpg。

封面快取刪除後不能影響歌曲及影片資料。

# 五、批次下載 MP3

使用者勾選多部影片後，可以按下批次下載按鈕。

下載流程：

1. 使用 yt-dlp 下載可用的最佳音訊。
2. 使用 FFmpeg 轉換成 MP3。
3. 下載成功後寫入 SQLite。
4. UI 顯示個別影片的下載進度與狀態。
5. 單一影片下載失敗時，繼續處理其他影片。
6. 批次完成後顯示成功數量及失敗數量。
7. 不要阻塞桌面 UI。

MP3 音質先集中放在設定檔或常數中，預設使用 192 kbps，方便之後修改。

下載資料夾結構先使用：

downloads/
歌手ID/
歌手ID_影片標題.mp3

例如：

downloads/
suisei/
suisei_Stellar Stellar.mp3

# 六、檔名與歌曲名稱

歌曲初始名稱使用：

歌手ID_影片標題

實際 MP3 檔名使用：

歌手ID_影片標題.mp3

需要處理 Windows 檔名禁止使用的字元：

\ / : * ? " < > |

還需要：

* 移除檔名前後空白。
* 避免檔名以句點結尾。
* 避免檔名過長。
* 檔名處理請集中成獨立函式。
* 保留原始 YouTube 標題，不要直接覆蓋。

未來使用者可以修改歌曲名稱，因此資料庫中的歌曲顯示名稱與實際檔案路徑要分開儲存。

第一版可以提供簡單的歌曲名稱修改功能：

* 使用者修改歌曲名稱。
* 更新 SQLite 中的歌曲名稱。
* 是否同步修改實體 MP3 檔案請封裝成獨立函式，方便未來調整。

# 七、防止重複下載

請以 YouTube video ID 作為主要的重複判斷依據。

需求：

* 同一部 YouTube 影片不可重複建立歌曲紀錄。
* 已下載的影片在列表中顯示「已下載」。
* 已下載的影片預設不可再次勾選。
* 如果資料庫顯示已下載，但實體 MP3 不存在，要顯示「檔案遺失」，不要直接當作正常完成。
* 下載前再次檢查，避免批次操作產生重複下載。

# 八、SQLite 初步設計

SQL 欄位之後可能修改，所以目前只做容易擴充的基礎版本。

可以先使用類似以下結構：

artists：

* id
* artist_id
* youtube_url
* channel_name
* created_at

songs：

* id
* artist_id
* youtube_video_id
* youtube_url
* original_title
* song_name
* file_name
* file_path
* thumbnail_url
* duration
* upload_date
* download_status
* downloaded_at

請注意：

* artist_id 需要唯一限制。
* youtube_video_id 需要唯一限制。
* YouTube 頻道網址需要唯一限制。
* songs 與 artists 之間需要合理的外鍵關係。
* 請開啟 SQLite foreign key 支援。
* 資料庫操作集中管理。
* 不要在 UI、下載服務及多個檔案中重複撰寫 SQL。
* 請保留未來進行 schema migration 的空間。
* 現在不需要設計完整且最終版本的資料庫。

# 九、建議專案結構

可以使用以下結構，也可以在說明原因後做小幅調整：

project/
main.py
requirements.txt
README.md
config.py

```
ui/
    __init__.py
    app.py
    artist_view.py
    video_view.py
    components/

database/
    __init__.py
    connection.py
    schema.py
    artist_repository.py
    song_repository.py

services/
    __init__.py
    youtube_service.py
    download_service.py
    thumbnail_service.py

models/
    __init__.py
    artist.py
    video.py
    song.py

utils/
    __init__.py
    filename.py

data/
    app.db

downloads/

cache/
    thumbnails/
```

UI 只負責：

* 顯示資料
* 接收使用者操作
* 呼叫 service 或 repository

UI 不應直接：

* 執行 yt-dlp
* 操作 FFmpeg
* 發送封面網路請求
* 撰寫 SQL

# 十、執行緒與 UI 穩定性

以下工作不能直接在 CustomTkinter 主執行緒執行：

* 取得頻道資料
* 取得影片列表
* 載入封面
* 下載音訊
* FFmpeg 轉換

請使用適合的背景執行方式，並安全地將結果更新回 UI。

需要注意：

* 不要從背景執行緒直接不安全地修改 Tkinter 元件。
* 程式關閉時要妥善停止或結束背景工作。
* 避免因一張封面或一部影片失敗而使整個程式崩潰。
* UI 至少要顯示目前正在執行的工作。

# 十一、第一版 UI

第一版可以使用分頁或側邊欄，至少包含：

1. 歌手管理
2. 影片下載

歌手管理頁：

* 歌手 ID 輸入框
* YouTube 頻道網址輸入框
* 新增歌手按鈕
* 狀態及錯誤訊息
* 已新增歌手列表

影片下載頁：

* 歌手選擇欄位
* 取得或重新整理影片按鈕
* 影片搜尋框
* 全選及取消全選
* 可捲動影片列表
* 封面
* 勾選框
* 影片名稱及基本資料
* 下載狀態
* 批次下載按鈕
* 整體進度或文字狀態

# 十二、第一階段的完成標準

請先完成一個可以實際執行的版本，至少做到：

1. main.py 可以啟動桌面視窗。
2. 第一次啟動時自動建立 SQLite 資料庫。
3. 可以輸入歌手 ID 與 YouTube 頻道網址。
4. 可以自動取得頻道名稱。
5. 可以將歌手存入 SQLite。
6. 可以顯示及選擇已新增歌手。
7. 可以取得該頻道的影片列表。
8. 可以顯示影片封面。
9. 可以搜尋、全選及取消全選影片。
10. 可以批次下載勾選的影片為 MP3。
11. 可以顯示每部影片的下載狀態。
12. 可以避免重複下載。
13. 重新開啟程式後，歌手及下載紀錄仍然存在。
14. README 包含安裝、FFmpeg 設定及執行方法。

請在完成後：

* 執行基本測試。
* 檢查 import 是否正確。
* 確認 main.py 可以啟動。
* 說明建立或修改了哪些檔案。
* 說明仍未完成或需要人工測試的部分。
* 不要聲稱已測試實際 YouTube 下載，除非確實執行成功。
