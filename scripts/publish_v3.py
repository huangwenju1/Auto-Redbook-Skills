#!/usr/bin/env python3
"""
小红书笔记发布脚本 - 修复版
解决 xhs 库 0.2.13 版本的签名问题

使用方法:
    python scripts/publish_v3.py --title "标题" --desc "描述" --images cover.png card_1.png

环境变量:
    在 .env 文件中配置 XHS_COOKIE

依赖:
    pip install xhs python-dotenv requests
"""

import argparse
import os
import sys
import json
from pathlib import Path
from typing import List

try:
    from dotenv import load_dotenv
    from xhs import XhsClient
    from xhs.help import sign as local_sign
except ImportError as e:
    print(f"缺少依赖: {e}")
    print("请运行: pip install xhs python-dotenv requests")
    sys.exit(1)


def load_cookie() -> str:
    """从 .env 文件加载 Cookie"""
    # 切换到脚本所在目录
    script_dir = Path(__file__).parent
    env_paths = [
        script_dir / '.env',
        script_dir.parent / '.env',
    ]
    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(dotenv_path=str(env_path))
            break

    cookie = os.getenv('XHS_COOKIE')
    if not cookie:
        print("错误: 未找到 XHS_COOKIE，请在 .env 文件中配置")
        sys.exit(1)
    return cookie


def resolve_image_path(image_path: str) -> str:
    """解析图片路径"""
    # 先标准化路径
    import os
    path_str = os.path.normpath(image_path)
    path = Path(path_str)

    # 如果是绝对路径
    if path.is_absolute():
        if path.exists():
            return path_str
        return path_str

    # 尝试多个基准目录
    base_dirs = [
        Path(__file__).parent,  # 脚本目录
        Path(__file__).parent.parent,  # Auto-Redbook-Skills
        Path.cwd(),  # 当前目录
    ]

    for base in base_dirs:
        resolved = base / path
        if resolved.exists():
            return os.path.normpath(str(resolved.absolute()))

    return path_str


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
    """创建签名函数，兼容 xhs 库的调用方式"""
    def my_sign(url, data=None, **kwargs):
        # xhs 库可能传入任意参数，使用 a1 或 kwargs 中的值
        a1_value = kwargs.get('a1', '') or a1
        return local_sign(url, data, a1=a1_value, b1='')
    return my_sign


def main():
    parser = argparse.ArgumentParser(description='小红书笔记发布脚本 - 修复版')
    parser.add_argument('--title', '-t', required=True, help='笔记标题')
    parser.add_argument('--desc', '-d', default='', help='笔记正文')
    parser.add_argument('--images', '-i', nargs='+', required=True, help='图片文件')
    parser.add_argument('--public', action='store_true', help='公开发布（默认私密）')
    parser.add_argument('--dry-run', action='store_true', help='仅验证不发布')
    args = parser.parse_args()

    # 验证标题
    if len(args.title) > 20:
        print(f"警告: 标题超过20字，已截断")
        args.title = args.title[:20]

    # 加载 Cookie
    cookie = load_cookie()

    # 解析 a1
    cookies = parse_cookie(cookie)
    a1 = cookies.get('a1', '')

    print(f"标题: {args.title}")
    print(f"图片: {args.images}")
    print(f"公开: {args.public}")

    # 解析图片路径
    args.images = [resolve_image_path(img) for img in args.images]

    if args.dry_run:
        print("Dry run 模式，不实际发布")
        return

    # 创建签名函数
    sign_func = create_sign_func(a1)

    # 创建客户端
    print("创建 XhsClient...")
    client = XhsClient(cookie=cookie, sign=sign_func)
    print("客户端创建成功!")

    # 发布笔记
    print("发布笔记...")
    result = client.create_image_note(
        title=args.title,
        desc=args.desc,
        files=args.images,
        is_private=not args.public
    )

    # 输出结果
    if result.get('success'):
        note_id = result.get('id')
        share_link = result.get('share_link', '')
        print(f"\n发布成功!")
        print(f"笔记ID: {note_id}")
        print(f"链接: {share_link}")
    else:
        print(f"发布失败: {json.dumps(result, ensure_ascii=False)}")


if __name__ == '__main__':
    main()