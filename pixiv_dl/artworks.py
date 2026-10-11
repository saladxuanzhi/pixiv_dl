"""插画/漫画下载模块"""
import os
import time
from typing import Dict, List, Optional, Union

from . import store, ui
from .client import PixivClient


class Artwork:
    def __init__(self, data: dict):
        self.id = data.get("id")
        self.title = data.get("title")
        self.description = data.get("description")
        self.illustType = data.get("illustType")
        self.tags = data.get("tags")
        self.userId = data.get("userId")
        self.userName = data.get("userName")
        self.width = data.get("width")
        self.height = data.get("height")
        self.pageCount = data.get("pageCount")
        self.bookmarkData = data.get("bookmarkData")

    def __str__(self):
        return f"Artwork(id={self.id}, title='{self.title}')"

    def to_dict(self) -> dict:
        return self.__dict__.copy()


class ArtworkDownloader:
    def __init__(self, client: PixivClient, config: dict):
        self.client = client
        self.config = config

    # ------------------------------------------------------------------
    # 列表获取
    # ------------------------------------------------------------------

    def get_bookmark_works(self) -> List[Dict]:
        """获取收藏夹作品列表"""
        works, page, total = [], 1, None
        per_page = 48
        uid = self.client.user_id
        while True:
            url = (f"{self.client.BASE_URL}/ajax/user/{uid}/illusts/bookmarks"
                   f"?tag=&offset={(page - 1) * per_page}&limit={per_page}&rest=show&lang=zh")
            resp = self.client.make_request(url)
            if not resp:
                break
            data = resp.json()
            body = data.get("body") or {}
            batch = body.get("works") or []
            if not batch:
                break
            works.extend(batch)
            if total is None and body.get("total"):
                total = body["total"]
            if len(works) >= total:
                break
            max_pages = self.config.get("MAX_PAGES", 0)
            if max_pages and page >= max_pages:
                break
            page += 1
            time.sleep(self.config.get("SLEEP_TIME", 0.2))
        return works

    def get_artist_name(self, artist_id: Union[str, int]) -> Optional[str]:
        url = f"{self.client.BASE_URL}/ajax/user/{artist_id}?full=1&lang=zh"
        resp = self.client.make_request(url)
        if not resp:
            return None
        body = resp.json().get("body") or {}
        return body.get("name")

    def get_artist_works(self, artist_id: Union[str, int]) -> List[Dict]:
        """获取画师全部作品列表（插画 + 漫画）"""
        all_works = []
        url = (f"{self.client.BASE_URL}/ajax/user/{artist_id}/profile/all"
               f"?sensitiveFilterMode=userSetting&lang=zh")
        resp = self.client.make_request(url)
        if not resp:
            return []
        body = resp.json().get("body") or {}
        id_dict = dict(body.get("illusts") or {}, **(body.get("manga") or {}))
        ids = list(id_dict.keys())

        limit = 48
        pages = [ids[i:i + limit] for i in range(0, len(ids), limit)]
        for index, group in enumerate(pages):
            ajax_url = f"{self.client.BASE_URL}/ajax/user/{artist_id}/profile/illusts?"
            for work_id in group:
                ajax_url += f"ids%5B%5D={work_id}&"
            ajax_url += ("work_category=illustManga&sensitiveFilterMode=userSetting"
                         f"&lang=zh&is_first_page={'1' if index == 0 else '0'}")
            resp = self.client.make_request(ajax_url)
            if not resp:
                continue
            works = (resp.json().get("body") or {}).get("works") or {}
            all_works.extend(works.values())
            max_pages = self.config.get("MAX_PAGES", 0)
            if max_pages and index + 1 >= max_pages:
                break
            time.sleep(self.config.get("SLEEP_TIME", 0.2))
        return all_works

    # ------------------------------------------------------------------
    # 下载
    # ------------------------------------------------------------------

    def get_img_urls(self, pid: Union[str, int]) -> List[str]:
        """获取作品原始图片 URL 列表（多页/动图）"""
        url = f"{self.client.BASE_URL}/ajax/illust/{pid}"
        resp = self.client.make_request(url)
        if not resp:
            return []
        body = resp.json().get("body") or {}
        original = (body.get("urls") or {}).get("original")
        if not original:
            return []
        count = body.get("pageCount", 1)
        if count > 1:
            return [original.replace("_p0", f"_p{i}") for i in range(count)]
        return [original]

    def download(self, artwork: Artwork, root_path: str) -> bool:
        """下载单个作品，返回是否成功"""
        if artwork.title == "-----":
            ui.skip(f"{artwork.id}  作品已失效")
            return False

        try:
            img_urls = self.get_img_urls(artwork.id)
            if not img_urls:
                ui.warn(f"{artwork.id}  无法获取图片地址")
                store.write_failed_log(artwork.id, root_path)
                return False

            if artwork.pageCount and artwork.pageCount > 1 or artwork.illustType == 2:
                save_dir = os.path.join(root_path, str(artwork.id))
            else:
                save_dir = root_path
            os.makedirs(save_dir, exist_ok=True)

            pending = []
            for img_url in img_urls:
                filename = img_url.split("/")[-1]
                filepath = os.path.join(save_dir, filename)
                if os.path.exists(filepath):
                    continue
                pending.append((img_url, filepath))

            if not pending:
                ui.skip(f"{artwork.id}  {artwork.title}（文件已存在）")
                return False

            multi = len(img_urls) > 1
            bar = None
            if multi:
                bar = ui.ProgressBar(len(img_urls), desc=f"  {artwork.id} 页")
            else:
                ui.info(f"{artwork.id}  {artwork.title}")

            for img_url, filepath in pending:
                resp = self.client.make_request(img_url, stream=True)
                if not resp:
                    raise ValueError(f"下载失败: {img_url}")
                with open(filepath, "wb") as f:
                    for chunk in resp.iter_content(65536):
                        f.write(chunk)
                if bar:
                    bar.update()

            if artwork.illustType == 2:
                self._download_ugoira(artwork.id, save_dir)

            if bar:
                bar.finish()
                ui.success(f"{artwork.id}  {artwork.title}（{len(img_urls)} 页）")
            else:
                ui.success(f"{artwork.id}  {artwork.title}")
            return True

        except Exception as e:
            ui.error(f"{artwork.id}  下载失败: {e}")
            store.write_failed_log(artwork.id, root_path)
            return False

    def _download_ugoira(self, pid: Union[str, int], save_dir: str) -> None:
        resp = self.client.make_request(
            f"{self.client.BASE_URL}/ajax/illust/{pid}/ugoira_meta?lang=zh")
        if not resp:
            return
        body = resp.json().get("body") or {}
        src = body.get("originalSrc")
        if not src:
            return
        zip_path = os.path.join(save_dir, f"{pid}.zip")
        resp = self.client.make_request(src, stream=True)
        if not resp:
            return
        with open(zip_path, "wb") as f:
            f.write(resp.content)
        if store.convert_ugoira(zip_path):
            ui.detail(f"动图已转换: {pid}.webm")
        else:
            ui.warn(f"动图转换失败，保留原始 ZIP: {pid}")
