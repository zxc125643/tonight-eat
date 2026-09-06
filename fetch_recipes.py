#!/usr/bin/env python3
"""定期抓取下厨房「王刚 / 厨师长」新菜谱，增量写入 menus.json。
- 搜索关键词：王刚、厨师长教你
- 只保留有完整步骤（steps>=2）的菜谱
- 去重：同 id 不重复添加
- 代理：走 7897（下厨房有时需要）
用法：python3 fetch_recipes.py [--dry-run]
"""
import json
import os
import re
import sys
import urllib.request
import urllib.parse
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MENUS_FILE = os.path.join(BASE_DIR, "menus.json")
LOG_FILE = os.path.join(BASE_DIR, "fetch.log")
PROXY = "http://127.0.0.1:7897"

SEARCHES = [
    # 特定厨师/美食作家
    ("王刚", "https://www.xiachufang.com/search/?keyword=%E7%8E%8B%E5%88%9A"),
    ("厨师长教你", "https://www.xiachufang.com/search/?keyword=%E5%8E%A8%E5%B8%88%E9%95%BF%E6%95%99%E4%BD%A0"),
    ("老饭骨", "https://www.xiachufang.com/search/?keyword=%E8%80%81%E9%A4%90%E9%AA%A8"),
    ("美食作家", "https://www.xiachufang.com/search/?keyword=%E7%BE%8E%E9%A3%9F%E4%BD%9C%E5%AE%B6"),
    # 综合排名/热门
    ("热门菜谱", "https://www.xiachufang.com/search/?keyword=%E7%83%AD%E9%97%A8%E8%8F%9C%E8%B0%B1"),
    ("高分菜谱", "https://www.xiachufang.com/search/?keyword=%E9%AB%98%E5%88%86%E8%8F%9C%E8%B0%B1"),
    ("家常菜谱", "https://www.xiachufang.com/search/?keyword=%E5%AE%B6%E5%B8%B8%E8%8F%9C%E8%B0%B1"),
]


def log(msg):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def http_get(url, timeout=20):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9",
    })
    if PROXY:
        proxy_handler = urllib.request.ProxyHandler({"http": PROXY, "https": PROXY})
        opener = urllib.request.build_opener(proxy_handler)
    else:
        opener = urllib.request.build_opener()
    with opener.open(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="ignore")


def load_menus():
    try:
        with open(MENUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_menus(menus):
    tmp = MENUS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(menus, f, ensure_ascii=False, indent=2)
    os.replace(tmp, MENUS_FILE)


def slugify(name):
    """菜名 → id。
    下厨房菜名常带前缀（如"厨师长教你："）和长描述，
    这里截取核心菜名（去前缀、截断到合理长度）做 id。
    """
    # 去掉常见前缀
    cleaned = re.sub(r"^【?[^：:]{0,12}[：:]", "", name.strip())
    # 去掉引号和括号内容
    cleaned = re.sub(r"[\"“”（(].*$", "", cleaned).strip()
    # 取前 8 个字符做 id（中文），转小写去特殊字符
    short = cleaned[:8]
    slug = re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", short.lower())
    return slug or "dish"


def parse_recipe_page(html_text):
    """从下厨房菜谱页提取：菜名、用料、步骤。
    返回 dict 或 None。
    """
    # 菜名：<title>XXX的做法_...</title>
    m = re.search(r"<title>([^<]+?)的做法", html_text)
    if not m:
        return None
    name = m.group(1).strip()

    # 用料：找 "用料" 区块
    ingredients = []
    ing_block = re.search(r"用料(.*?)步骤", html_text, re.S)
    if ing_block:
        # 提取文本，去掉标签
        txt = re.sub(r"<[^>]+>", " ", ing_block.group(1))
        txt = re.sub(r"\s+", " ", txt).strip()
        # 按行/逗号拆分
        parts = re.split(r"[，,、\n]+", txt)
        for p in parts:
            p = p.strip()
            if p and len(p) < 40:
                ingredients.append(p)

    # 步骤：找 "步骤" 区块
    steps = []
    step_block = re.search(r"做法步骤(.*?)(?:菜谱创建|打开App|$)", html_text, re.S)
    if step_block:
        txt = re.sub(r"<[^>]+>", " ", step_block.group(1))
        txt = re.sub(r"\s+", " ", txt).strip()
        # 按 "步骤 N" 或数字拆分
        step_parts = re.split(r"步骤\s*\d+|(?=\d+\.)", txt)
        for sp in step_parts:
            sp = sp.strip(" .0123456789")
            if sp and len(sp) > 5:
                steps.append(sp)

    if not name or len(steps) < 2:
        return None

    return {
        "name": name,
        "ingredients": ingredients[:15],
        "steps": steps[:10],
    }


def main():
    dry_run = "--dry-run" in sys.argv
    menus = load_menus()
    existing_ids = {m.get("id") for m in menus}
    added = 0

    for i, (label, url) in enumerate(SEARCHES):
        # 每个搜索之间等 2 秒，避免限流
        if i > 0:
            import time
            time.sleep(2)
        try:
            html_text = http_get(url)
        except Exception as e:
            log(f"[{label}] 抓取失败: {e}")
            continue

        # 从搜索结果页提取菜谱链接（兼容单/双引号、可选尾部斜杠）
        links = re.findall(r'''href=["\'](/recipe/\d+)/?["\']''', html_text)
        # 去重保序
        seen = set()
        unique_links = []
        for l in links:
            if l not in seen:
                seen.add(l)
                unique_links.append(l)
        log(f"[{label}] 找到 {len(unique_links)} 个菜谱链接")

        for link in unique_links[:10]:  # 每次最多处理 10 个
            recipe_url = f"https://www.xiachufang.com{link}/"  # 尾斜杠必需
            try:
                recipe_html = http_get(recipe_url)
            except Exception as e:
                log(f"  {link} 抓取失败: {e}")
                continue

            recipe = parse_recipe_page(recipe_html)
            if not recipe:
                continue

            rid = slugify(recipe["name"])
            if rid in existing_ids:
                continue

            # 构建菜单条目
            menu_entry = {
                "id": rid,
                "title": recipe["name"],
                "time": "30 分钟",
                "tags": ["下饭", "家常"],
                "why": f"{recipe['name']}，家常做法，下饭。",
                "shop": recipe["ingredients"][:8],
                "dishes": [
                    {
                        "role": "大菜",
                        "name": recipe["name"],
                        "ing": recipe["ingredients"][:8],
                        "steps": recipe["steps"][:6],
                    }
                ],
            }

            if dry_run:
                log(f"  [dry-run] 新增: {recipe['name']} ({rid})")
            else:
                menus.append(menu_entry)
                existing_ids.add(rid)
                added += 1
                log(f"  新增: {recipe['name']} ({rid})")

    if not dry_run and added > 0:
        save_menus(menus)
        log(f"共新增 {added} 套菜谱，总计 {len(menus)} 套")
    elif dry_run:
        log(f"[dry-run] 完成，未写入")
    else:
        log(f"无新增，总计 {len(menus)} 套")


if __name__ == "__main__":
    main()
