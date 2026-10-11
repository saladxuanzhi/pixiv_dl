# Pixiv Downloader

一站式 Pixiv 下载工具，整合插画收藏夹、画师作品与小说收藏夹下载。

## 功能

- 插画收藏夹下载（单图 / 多图 / 动图，动图自动转换为 WebM）
- 指定画师全部作品下载（插画 + 漫画）
- 小说收藏夹下载（系列作品自动合并为一个文件）
- 增量下载：通过 `completed.json` / `finished.log` 记录，重复执行只下载新内容
- 元数据保存：作品信息以 JSON Lines 追加写入 `metadata.json`
- 失败记录：下载失败的 ID 写入 `failed.txt`

## 目录结构

```
.
├── main.py                 入口：python main.py
├── config.py               实际配置（含 Cookie，不入库）
├── config_template.py      配置模板
├── requirements.txt
└── pixiv_dl/               核心代码
    ├── client.py           会话 / Cookie / 重试
    ├── artworks.py         插画与画师作品下载
    ├── novels.py           小说与系列下载
    ├── store.py            已完成记录 / 元数据 / Ugoira 转换
    └── ui.py               终端输出
```

## 使用

```bash
pip install -r requirements.txt
python main.py
```

首次运行会根据 `config_template.py` 生成 `config.py`（若不存在）。
在 `config.py` 中通过以下开关控制任务：

| 开关 | 说明 |
|------|------|
| `DOWNLOAD_FAVORITES` | 下载插画收藏夹 |
| `DOWNLOAD_ARTIST_WORKS` | 下载 `ARTIST_IDS` 中画师的作品 |
| `DOWNLOAD_NOVELS` | 下载小说收藏夹 |

## 输出目录

- `images/` 插画收藏夹
- `artists/<画师ID>_<画师名>/` 画师作品
- `novels/` 小说正文与元数据
