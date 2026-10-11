"""Pixiv Downloader - 统一入口

整合插画收藏夹 / 画师作品 / 小说收藏夹下载。
执行 python main.py 后按 config.py 中启用的任务直接开始下载。
"""
import os
import sys
import time

from pixiv_dl import ui, store
from pixiv_dl.client import PixivClient, RateLimitError
from pixiv_dl.artworks import Artwork, ArtworkDownloader
from pixiv_dl.novels import NovelDownloader

APP_NAME = "Pixiv Downloader"
APP_VERSION = "2.0"


def load_config() -> dict:
    """加载 config.py；不存在时由 config_template.py 自动生成"""
    import importlib.util

    if not os.path.exists("config.py"):
        template = "config_template.py"
        if os.path.exists(template):
            ui.warn("未找到 config.py，正在从 config_template.py 生成...")
            with open(template, "r", encoding="utf-8") as src, \
                 open("config.py", "w", encoding="utf-8") as dst:
                dst.write(src.read())
        else:
            ui.error("未找到 config.py 与 config_template.py")
            sys.exit(1)

    spec = importlib.util.spec_from_file_location("config", "config.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return vars(module)


def run_artwork_tasks(client: PixivClient, config: dict) -> None:
    downloader = ArtworkDownloader(client, config)

    if config.get("DOWNLOAD_FAVORITES", False):
        ui.section("插画收藏夹")
        path = config.get("DOWNLOAD_PATH", "images")
        os.makedirs(path, exist_ok=True)

        works = downloader.get_bookmark_works()
        done = store.get_downloaded_work_ids(path)
        pending = [w for w in works if str(w.get("id")) not in done]
        ui.info(f"收藏夹共 {len(works)} 个作品，待下载 {len(pending)} 个")
        if not pending:
            ui.skip("没有需要下载的新作品")
            return

        for work in pending:
            artwork = Artwork(work)
            if downloader.download(artwork, path):
                if config.get("SAVE_METADATA", True):
                    store.write_metadata(artwork, path)
                store.write_finished_log(artwork.id, path)
            time.sleep(config.get("SLEEP_TIME", 0.2))

    if config.get("DOWNLOAD_ARTIST_WORKS", False):
        ui.section("画师作品")
        path = config.get("ARTIST_DOWNLOAD_PATH", "artists")
        os.makedirs(path, exist_ok=True)

        # 复用已存在的画师目录
        existing = {}
        for item in os.listdir(path):
            full = os.path.join(path, item)
            if os.path.isdir(full) and item.split("_")[0]:
                existing[item.split("_")[0]] = full

        for artist_id in config.get("ARTIST_IDS", []):
            artist_name = downloader.get_artist_name(artist_id) or "未知画师"
            if artist_id in existing:
                save_path = existing[artist_id]
            else:
                save_path = os.path.join(path, f"{artist_id}_{artist_name}")
                os.makedirs(save_path, exist_ok=True)

            works = downloader.get_artist_works(artist_id)
            done = store.get_downloaded_work_ids(save_path)
            pending = [w for w in works if str(w.get("id")) not in done]
            ui.info(f"画师 {artist_name}({artist_id}) 共 {len(works)} 个作品，待下载 {len(pending)} 个")
            for work in pending:
                artwork = Artwork(work)
                if downloader.download(artwork, save_path):
                    if config.get("SAVE_METADATA", True):
                        store.write_metadata(artwork, save_path)
                    store.write_finished_log(artwork.id, save_path)
                time.sleep(config.get("SLEEP_TIME", 0.2))


def run_novel_task(client: PixivClient, config: dict) -> None:
    ui.section("小说收藏夹")
    downloader = NovelDownloader(client, config)
    path = config.get("NOVEL_DOWNLOAD_PATH", "novels")
    os.makedirs(path, exist_ok=True)

    novel_ids = downloader.get_bookmark_novels()
    done = store.get_downloaded_novel_ids(path)
    pending = [nid for nid in novel_ids if nid not in done]
    ui.info(f"收藏夹共 {len(novel_ids)} 篇小说，待下载 {len(pending)} 篇")
    for novel_id in pending:
        downloader.download(novel_id, path)
        time.sleep(config.get("SLEEP_TIME", 0.2))


def main() -> None:
    ui.banner(APP_NAME, f"v{APP_VERSION}  插画 / 画师作品 / 小说 一站式下载")

    config = load_config()
    ui.kv("用户 ID", str(config.get("USER_ID") or "(从 Cookie 提取)"))
    ui.kv("下载目录", os.path.abspath(config.get("DOWNLOAD_PATH", "images")))
    ui.kv("小说目录", os.path.abspath(config.get("NOVEL_DOWNLOAD_PATH", "novels")))

    tasks = []
    if config.get("DOWNLOAD_FAVORITES", False):
        tasks.append("插画收藏夹")
    if config.get("DOWNLOAD_ARTIST_WORKS", False):
        tasks.append("画师作品")
    if config.get("DOWNLOAD_NOVELS", False):
        tasks.append("小说收藏夹")
    if not tasks:
        ui.warn("未启用任何下载任务，请在 config.py 中开启对应开关")
        return
    ui.kv("启用任务", "、".join(tasks))

    started = time.time()
    try:
        client = PixivClient(config)
        run_artwork_tasks(client, config)
        run_novel_task(client, config)
    except RateLimitError as e:
        ui.error(str(e))
        sys.exit(1)
    except KeyboardInterrupt:
        ui.warn("用户中断，程序已终止")
        sys.exit(130)
    except Exception as e:
        ui.error(f"程序异常: {e}")
        sys.exit(1)

    elapsed = time.time() - started
    ui.section("完成")
    ui.success(f"全部任务结束，用时 {_fmt_elapsed(elapsed)}")
    print()


def _fmt_elapsed(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    if m >= 60:
        h, m = divmod(m, 60)
        return f"{h}小时{m:02d}分{s:02d}秒"
    return f"{m:02d}分{s:02d}秒"


if __name__ == "__main__":
    main()
