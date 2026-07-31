from config import DENO_EXE_PATH, YOUTUBE_COOKIES_PATH


def with_common_ytdlp_options(options: dict) -> dict:
    configured = dict(options)
    if YOUTUBE_COOKIES_PATH.exists():
        configured["cookiefile"] = str(YOUTUBE_COOKIES_PATH)
    if DENO_EXE_PATH.exists():
        configured["js_runtimes"] = {"deno": {"path": str(DENO_EXE_PATH)}}
    return configured
