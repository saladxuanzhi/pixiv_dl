"""小说下载模块（收藏夹小说及系列作品）"""
import os
import time
from typing import Dict, List, Optional, Union

from . import store, ui
from .client import PixivClient


class NovelDownloader:
    def __init__(self, client: PixivClient, config: dict):
        self.client = client
        self.config = config

    # ------------------------------------------------------------------
    # 列表与信息
    # ------------------------------------------------------------------

    def get_bookmark_novels(self) -> List[str]:
        """获取收藏夹中的小说 ID 列表"""
        novels = []
        page, total = 1, None
        per_page = 30
        uid = self.client.user_id
        while True:
            url = (f"{self.client.BASE_URL}/ajax/user/{uid}/novels/bookmarks"
                   f"?tag=&offset={(page - 1) * per_page}&limit={per_page}&rest=show&lang=zh")
            resp = self.client.make_request(url)
            if not resp:
                break
            body = (resp.json().get("body") or {})
            batch = body.get("works") or []
            if not batch:
                break
            novels.extend(str(w["id"]) for w in batch if w.get("id"))
            if total is None and body.get("total"):
                total = body["total"]
            if total and len(novels) >= total:
                break
            page += 1
            time.sleep(self.config.get("SLEEP_TIME", 0.2))

        # 去重且保持顺序
        seen, result = set(), []
        for nid in novels:
            if nid not in seen:
                seen.add(nid)
                result.append(nid)
        return result

    def get_novel_info(self, novel_id: Union[str, int]) -> Optional[Dict]:
        """获取小说元数据与正文"""
        url = f"{self.client.BASE_URL}/ajax/novel/{novel_id}"
        resp = self.client.make_request(url)
        if not resp:
            return None
        novel = (resp.json().get("body") or None)
        if not novel:
            ui.error(f"{novel_id}  无法获取小说信息（未登录或 Cookie 已过期）")
            return None

        content = novel.get("content") or ""
        if not content:
            ui.error(f"{novel_id}  无法获取小说正文")
            return None

        if self.config.get("REMOVE_EMPTY_LINES", True):
            content = self._parse_content(content)

        series_info = None
        if novel.get("seriesNavData"):
            series = novel["seriesNavData"]
            series_info = {"id": series["seriesId"], "title": series["title"]}

        tags = []
        raw_tags = novel.get("tags")
        if isinstance(raw_tags, list):
            tags = [t["tag"] for t in raw_tags]
        elif isinstance(raw_tags, dict) and raw_tags.get("tags"):
            tags = [t["tag"] for t in raw_tags["tags"]]

        return {
            "id": str(novel_id),
            "title": novel["title"],
            "author": novel["userName"],
            "content": content,
            "series_info": series_info,
            "create_date": novel.get("createDate", ""),
            "tags": tags,
        }

    @staticmethod
    def _parse_content(content: str) -> str:
        content = content.replace("[newpage]", "\n\n")
        content = content.replace("[[rb:", "[")
        content = content.replace("]]", "]")
        paragraphs = [p.strip() for p in content.split("\n") if p.strip()]
        return "\n".join(paragraphs)

    def get_series_novels(self, series_id: Union[str, int]) -> List[str]:
        """获取系列全部可用章节 ID"""
        url = (f"{self.client.BASE_URL}/ajax/novel/series/{series_id}/content_titles")
        resp = self.client.make_request(url)
        if not resp:
            return []
        items = resp.json().get("body") or []
        return [str(item["id"]) for item in items
                if item.get("id") and item.get("available")]

    # ------------------------------------------------------------------
    # 下载
    # ------------------------------------------------------------------

    def download(self, novel_id: Union[str, int], output_dir: str) -> bool:
        """下载单篇小说（若属于系列则下载整个系列）"""
        novel_info = self.get_novel_info(novel_id)
        if not novel_info:
            store.write_failed_log(output_dir, novel_id=novel_id)
            return False

        series_info = novel_info["series_info"]
        if not series_info:
            filepath = store.save_novel(novel_info, output_dir, prefix=True)
            if filepath:
                if self.config.get("SAVE_METADATA", True):
                    store.write_novel_metadata(novel_info, output_dir)
                store.mark_novel_completed(output_dir, novel_id)
                ui.success(f"{novel_id}  {novel_info['title']}")
                return True
            ui.error(f"{novel_id}  保存失败")
            store.write_failed_log(output_dir, novel_id=novel_id)
            return False

        return self._download_series(novel_info, output_dir)

    def _download_series(self, first_info: Dict, output_dir: str) -> bool:
        series = first_info["series_info"]
        series_id, series_title = str(series["id"]), series["title"]
        ui.info(f"{first_info['id']}  系列作品: {series_title}")

        series_novels = self.get_series_novels(series_id)
        if not series_novels:
            ui.warn(f"系列 {series_id}  无法获取章节列表")
            store.write_failed_log(output_dir, series_id=series_id)
            return True

        downloaded = store.get_downloaded_series_ids(output_dir, series_id)
        to_download = [nid for nid in series_novels if nid not in downloaded]
        if not to_download:
            ui.skip(f"系列 {series_id}  全部章节已下载")
            return True

        bar = ui.ProgressBar(len(to_download), desc=f"  系列 {series_title[:16]}")
        prefix_flag = not downloaded
        ok = True
        for idx, nid in enumerate(to_download):
            info = self.get_novel_info(nid)
            if not info:
                store.write_failed_log(output_dir, novel_id=nid, series_id=series_id)
                ok = False
            else:
                filepath = store.save_novel(
                    info, output_dir, prefix=(idx == 0 and prefix_flag))
                if filepath:
                    if self.config.get("SAVE_METADATA", True):
                        store.write_novel_metadata(info, output_dir)
                    store.mark_series_completed(output_dir, series_id, nid)
                else:
                    store.write_failed_log(output_dir, novel_id=nid, series_id=series_id)
                    ok = False
            bar.update()
            time.sleep(self.config.get("SLEEP_TIME", 0.2))
        bar.finish()
        ui.success(f"系列 {series_id}  {series_title}（本次 {len(to_download)} 章）")
        return ok
