#!/usr/bin/env python3
"""
小红书笔记一键发布脚本
从 CSV 文件中找到最高点赞文章，生成图片并自动发布

使用方法:
    # 基本用法
    python scripts/quick_publish.py --csv 路径/to/文案.csv

    # 指定输出目录
    python scripts/quick_publish.py --csv 路径/to/文案.csv --output ./output

    # 仅生成图片，不发布
    python scripts/quick_publish.py --csv 路径/to/文案.csv --no-publish

    # 仅发布，不重新生成图片
    python scripts/quick_publish.py --csv 路径/to/文案.csv --images ./existing/*.png

依赖:
    pip install xhs python-dotenv requests markdown pyyaml playwright
    npm install (在 Auto-Redbook-Skills 目录下)
"""

import argparse
import os
import sys
import csv
import json
import subprocess
from pathlib import Path
from typing import Optional, List, Tuple

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv
    from xhs import XhsClient
    from xhs.help import sign as local_sign
except ImportError:
    print("缺少依赖，请运行: pip install xhs python-dotenv requests")
    sys.exit(1)


def find_highest_liked_post(csv_file: str) -> dict:
    """从 CSV 中找到点赞最高的文章"""
    print(f"读取 CSV: {csv_file}")

    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # 找到点赞数最高的行
    max_dz = 0
    max_row = None

    for row in rows:
        try:
            dz_str = str(row.get('点赞数', '0'))
            dz = dz_str.replace('万', '0000').replace('.', '')
            dz = int(float(dz))
            if dz > max_dz:
                max_dz = dz
                max_row = row
        except:
            pass

    if not max_row:
        print("未找到有效文章")
        sys.exit(1)

    print(f"最高点赞: {max_dz}")
    print(f"标题: {max_row.get('标题')}")

    # 提取二创内容
    result = {
        'title': max_row.get('二改标题', max_row.get('标题', '')),
        'content': max_row.get('二改内容', max_row.get('内容', '')),
        'image_title': max_row.get('图片标题改写', ''),
        'image_content': max_row.get('图片内容改写', ''),
    }

    return result


def parse_cookie(cookie_str: str) -> dict:
    """解析 Cookie 字符串"""
    items = cookie_str.split(';')
    result = {}
    for item in items:
        item = item.strip()
        if '=' in item:
            key, value = item.split('=', 1)
            result[key.strip()] = value.strip()
    return result


def create_sign_func(a1: str):
    """创建签名函数"""
    def my_sign(url, data=None, a1_param='', web_session=''):
        return local_sign(url, data, a1=a1 or a1_param, b1='')
    return my_sign


def render_images(content: dict, output_dir: str, theme: str = 'xiaohongshu') -> List[str]:
    """渲染图片"""
    # 创建临时 markdown 文件
    md_content = f"""---
emoji: "📣"
title: "{content['title'][:15]}"
subtitle: "🔥"
---

# {content['content'][:500]}
"""

    md_file = Path(output_dir) / 'temp_content.md'
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write(md_content)

    # 使用 Node.js 渲染
    print(f"渲染图片...")
    cmd = [
        'node', 'scripts/render_xhs_v2.js',
        str(md_file),
        '-o', output_dir,
        '-s', theme
    ]

    result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"渲染失败: {result.stderr}")
        # 尝试 Python 版本
        cmd = [
            'python', 'scripts/render_xhs.py',
            str(md_file),
            '-t', theme
        ]
        result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)

    # 删除临时文件
    md_file.unlink(missing_ok=True)

    # 返回生成的图片
    output_path = Path(output_dir)
    images = sorted(output_path.glob('*.png'))
    return [str(img) for img in images]


def publish_note(title: str, desc: str, images: List[str], is_private: bool = False) -> dict:
    """发布笔记"""
    # 加载 Cookie
    load_dotenv(dotenv_path=Path(__file__).parent / '.env')
    cookie = os.getenv('XHS_COOKIE')

    if not cookie:
        print("错误: 未找到 XHS_COOKIE")
        sys.exit(1)

    # 解析 a1
    cookies = parse_cookie(cookie)
    a1 = cookies.get('a1', '')

    # 创建签名函数
    sign_func = create_sign_func(a1)

    # 创建客户端
    print("创建 XhsClient...")
    client = XhsClient(cookie=cookie, sign=sign_func)

    # 发布笔记
    print("发布笔记...")
    result = client.create_image_note(
        title=title,
        desc=desc,
        files=images,
        is_private=is_private
    )

    return result


def main():
    parser = argparse.ArgumentParser(description='小红书笔记一键发布')
    parser.add_argument('--csv', required=True, help='CSV 文件路径')
    parser.add_argument('--output', '-o', default='output', help='输出目录')
    parser.add_argument('--theme', '-t', default='xiaohongshu', help='主题')
    parser.add_argument('--no-publish', action='store_true', help='仅生成图片不发布')
    parser.add_argument('--images', nargs='*', help='指定已有图片（跳过生成）')
    parser.add_argument('--private', action='store_true', help='私密发布')
    args = parser.parse_args()

    # 创建输出目录
    output_dir = Path(args.output)
    output_dir.mkdir(exist_ok=True)

    # 步骤1: 找到最高点赞文章
    print("=" * 50)
    print("步骤1: 分析 CSV 文件")
    print("=" * 50)
    post = find_highest_liked_post(args.csv)

    # 步骤2: 生成图片
    if args.images:
        images = args.images
        print(f"使用已有图片: {images}")
    else:
        print("=" * 50)
        print("步骤2: 渲染图片")
        print("=" * 50)
        images = render_images(post, str(output_dir), args.theme)
        print(f"生成图片: {images}")

    if args.no_publish:
        print("已跳过发布")
        return

    # 步骤3: 发布笔记
    print("=" * 50)
    print("步骤3: 发布笔记")
    print("=" * 50)
    result = publish_note(
        title=post['title'][:20],
        desc=post['content'],
        images=images,
        is_private=not args.private
    )

    # 结果
    if result.get('success'):
        note_id = result.get('id')
        share_link = result.get('share_link', '')
        print(f"\n{'=' * 50}")
        print(f"发布成功!")
        print(f"笔记ID: {note_id}")
        print(f"链接: {share_link}")
        print(f"{'=' * 50}")
    else:
        print(f"发布失败: {json.dumps(result, ensure_ascii=False)}")


if __name__ == '__main__':
    main()