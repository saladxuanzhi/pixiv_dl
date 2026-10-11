"""本地存储：已完成记录、元数据、失败日志、Ugoira 转换"""
import json
import os
import re
import shutil
import zipfile
from datetime import datetime
from typing import Optional, Set, Union


def clean_filename(filename: str) -> str:
    """清理文件名中的非法字符"""
    return "".join(x for x in filename if x not in ("\\", "/", ":", "*", "?", '"', "<", ">", "|"))


# ---------------------------------------------------------------------------
# completed.json：记录已下载内容，格式 {"series": {sid: [ids]}, "novels": [ids]}
# ---------------------------------------------------------------------------

def _completed_path(directory: str) -> str:
    return os.path.join(directory, "completed.json")


def load_completed(directory: str) -> dict:
    path = _completed_path(directory)
    if not os.path.exists(path):
        return {"series": {}, "novels": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if not content:
            return {"series": {}, "novels": []}
        data = json.loads(content)
        data.setdefault("series", {})
        data.setdefault("novels", [])
        return data
    except (json.JSONDecodeError, OSError):
        return {"series": {}, "novels": []}


def save_completed(directory: str, data: dict) -> None:
    os.makedirs(directory, exist_ok=True)
    with open(_completed_path(directory), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def get_downloaded_novel_ids(directory: str) -> Set[str]:
    return set(load_completed(directory)["novels"])


def get_downloaded_series_ids(directory: str, series_id: Union[str, int]) -> Set[str]:
    return set(load_completed(directory)["series"].get(str(series_id), []))


def mark_novel_completed(directory: str, novel_id: Union[str, int]) -> None:
    data = load_completed(directory)
    nid = str(novel_id)
    if nid not in data["novels"]:
        data["novels"].append(nid)
        save_completed(directory, data)


def mark_series_completed(directory: str, series_id: Union[str, int],
                          novel_id: Union[str, int]) -> None:
    data = load_completed(directory)
    sid = str(series_id)
    nid = str(novel_id)
    if sid not in data["series"]:
        data["series"][sid] = []
    if nid not in data["series"][sid]:
        data["series"][sid].append(nid)
        save_completed(directory, data)


# ---------------------------------------------------------------------------
# finished.log / failed.txt
# ---------------------------------------------------------------------------

def get_downloaded_work_ids(directory: str) -> Set[str]:
    """读取 finished.log 中的已下载作品 ID"""
    path = os.path.join(directory, "finished.log")
    if not os.path.exists(path):
        return set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            return {line.strip() for line in f if line.strip()}
    except OSError:
        return set()


def write_finished_log(work_id: Union[str, int], directory: str) -> None:
    with open(os.path.join(directory, "finished.log"), "a", encoding="utf-8") as f:
        f.write(f"{work_id}\n")


def write_failed_log(directory: str, novel_id: Optional[Union[str, int]] = None,
                     series_id: Optional[Union[str, int]] = None) -> None:
    """记录下载失败的 ID，前缀 n- 表示小说，s- 表示系列"""
    with open(os.path.join(directory, "failed.txt"), "a", encoding="utf-8") as f:
        if series_id and novel_id:
            f.write(f"{series_id}-{novel_id}\n")
        elif novel_id:
            f.write(f"n-{novel_id}\n")
        elif series_id:
            f.write(f"s-{series_id}\n")


# ---------------------------------------------------------------------------
# 元数据
# ---------------------------------------------------------------------------

def write_metadata(artwork, directory: str) -> None:
    """以 JSON Lines 追加方式保存作品元数据"""
    path = os.path.join(directory, "metadata.json")
    with open(path, "a", encoding="utf-8") as f:
        json.dump(artwork.to_dict(), f, ensure_ascii=False, indent=4)
        f.write(",\n")


def write_novel_metadata(novel_info: dict, directory: str) -> None:
    path = os.path.join(directory, "metadata.json")
    record = {
        "id": novel_info["id"],
        "title": novel_info["title"],
        "author": novel_info["author"],
        "create_date": novel_info["create_date"],
        "tags": novel_info["tags"],
        "series": novel_info["series_info"],
        "saved_at": datetime.now().isoformat(timespec="seconds"),
    }
    with open(path, "a", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=4)
        f.write(",\n")


# ---------------------------------------------------------------------------
# 小说保存
# ---------------------------------------------------------------------------

def save_novel(novel_info: dict, output_dir: str, prefix: bool = True) -> Optional[str]:
    """保存小说正文，系列作品合并为同一文件"""
    try:
        mode = "w" if prefix else "a"
        if novel_info["series_info"]:
            sid = novel_info["series_info"]["id"]
            title = novel_info["series_info"]["title"]
            filename = f"{clean_filename(title)}-s-{sid}.txt"
        else:
            nid = novel_info["id"]
            title = novel_info["title"]
            filename = f"{clean_filename(title)}-{nid}.txt"

        os.makedirs(output_dir, exist_ok=True)
        for existing in os.listdir(output_dir):
            if existing.endswith(".txt"):
                m = re.search(r"-(\d+)\.txt$", existing)
                if m and novel_info["series_info"] is None and m.group(1) == str(novel_info["id"]):
                    filename, mode = existing, "a"
                    break
                if m and novel_info["series_info"] and m.group(1) == str(novel_info["series_info"]["id"]):
                    filename, mode = existing, "a"
                    break

        filepath = os.path.join(output_dir, filename)
        with open(filepath, mode, encoding="utf-8") as f:
            if prefix:
                f.write(f"标题：{title}\n")
                f.write(f"作者：{novel_info['author']}\n")
                f.write(f"创建时间：{novel_info['create_date']}\n")
                f.write(f"标签：{', '.join(novel_info['tags'])}\n")
                f.write("\n" + "=" * 50 + "\n\n")
            else:
                f.write("\n\n")
            f.write(f"{novel_info['title']}-{novel_info['id']}\n")
            f.write(novel_info["content"])
        return filepath
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Ugoira 转换
# ---------------------------------------------------------------------------

def convert_ugoira(zip_path: str) -> bool:
    """将 Ugoira ZIP 帧序列转换为 WebM"""
    try:
        import imageio
    except ImportError:
        return False

    pid = os.path.splitext(os.path.basename(zip_path))[0]
    work_dir = os.path.dirname(zip_path)
    extract_path = os.path.join(work_dir, "temp_ugoira")
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            os.makedirs(extract_path, exist_ok=True)
            zf.extractall(extract_path)
        frames = [os.path.join(extract_path, name)
                  for name in sorted(os.listdir(extract_path))]
        writer = imageio.get_writer(
            os.path.join(work_dir, f"{pid}.webm"),
            fps=24, codec="libvpx-vp9", macro_block_size=None,
            output_params=["-crf", "32"],
        )
        for frame in frames:
            writer.append_data(imageio.imread(frame))
        writer.close()
        return True
    except Exception:
        return False
    finally:
        shutil.rmtree(extract_path, ignore_errors=True)
