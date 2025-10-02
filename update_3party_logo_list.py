import os
import glob
from pathlib import Path
import sys
import tempfile
import argparse
import re
import requests
from urllib.parse import urlparse
import time
import base64
import json  # 添加json模块导入

def parse_github_url(url):
    """
    解析GitHub URL，提取用户名、仓库名、分支和目录路径
    
    Args:
        url (str): GitHub URL
        
    Returns:
        dict: 包含解析信息的字典
    """
    # 移除末尾的斜杠
    url = url.rstrip('/')
    
    # 匹配GitHub tree URL模式
    pattern = r'https://github\.com/([^/]+)/([^/]+)/tree/([^/]+)/(.+)'
    match = re.match(pattern, url)
    
    if not match:
        raise ValueError(f"无效的GitHub URL: {url}")
    
    username, repo_name, branch, path = match.groups()
    
    return {
        'username': username,
        'repo_name': repo_name,
        'branch': branch,
        'path': path
    }

def get_branch_sha(username, repo_name, branch, github_token=None):
    """
    获取分支的SHA
    
    Args:
        username (str): GitHub用户名
        repo_name (str): 仓库名称
        branch (str): 分支名称
        github_token (str): GitHub个人访问令牌（可选）
        
    Returns:
        str: 分支的SHA
    """
    api_url = f"https://api.github.com/repos/{username}/{repo_name}/branches/{branch}"
    
    headers = {
        'User-Agent': 'Logo-List-Generator/1.0',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    if github_token:
        headers['Authorization'] = f'token {github_token}'
    
    response = requests.get(api_url, headers=headers)
    response.raise_for_status()
    
    branch_data = response.json()
    return branch_data['commit']['sha']

def get_tree_recursive(username, repo_name, tree_sha, github_token=None):
    """
    递归获取Git树中的所有文件
    
    Args:
        username (str): GitHub用户名
        repo_name (str): 仓库名称
        tree_sha (str): 树的SHA
        github_token (str): GitHub个人访问令牌（可选）
        
    Returns:
        list: 包含所有文件信息的列表
    """
    api_url = f"https://api.github.com/repos/{username}/{repo_name}/git/trees/{tree_sha}?recursive=1"
    
    headers = {
        'User-Agent': 'Logo-List-Generator/1.0',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    if github_token:
        headers['Authorization'] = f'token {github_token}'
    
    response = requests.get(api_url, headers=headers)
    response.raise_for_status()
    
    tree_data = response.json()
    return tree_data['tree']

def get_remote_logo_info(url, github_token=None):
    """
    从远程GitHub仓库获取logo信息（使用Git Trees API）
    
    Args:
        url (str): GitHub仓库的logo目录URL
        github_token (str): GitHub个人访问令牌（可选）
        
    Returns:
        list: 包含图片名称和链接的字典列表
    """
    logo_info = []
    
    try:
        # 解析URL
        url_info = parse_github_url(url)
        username = url_info['username']
        repo_name = url_info['repo_name']
        branch = url_info['branch']
        path = url_info['path']
        
        print(f"获取分支 {branch} 的SHA...")
        branch_sha = get_branch_sha(username, repo_name, branch, github_token)
        
        print(f"获取仓库的完整文件树...")
        all_files = get_tree_recursive(username, repo_name, branch_sha, github_token)
        
        # 支持的图片格式
        image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.webp']
        
        # 过滤出指定路径下的图片文件
        print(f"过滤 {path} 目录下的图片文件...")
        for file_info in all_files:
            if (file_info['type'] == 'blob' and 
                file_info['path'].startswith(path) and
                any(file_info['path'].endswith(ext) for ext in image_extensions)):
                
                # 获取文件名（不带扩展名）
                file_name = os.path.splitext(os.path.basename(file_info['path']))[0]
                
                # 生成raw.githubusercontent.com的绝对路径
                file_link = f"<https://raw.githubusercontent.com/{username}/{repo_name}/{branch}/{file_info['path']}>"
                
                logo_info.append({
                    "name": file_name,
                    "link": file_link,
                    "size": file_info.get('size', 0),
                    # Git Trees API不提供修改时间，使用当前时间作为占位符
                    "mtime": 0
                })
        
        print(f"找到 {len(logo_info)} 个图片文件")
    
    except Exception as e:
        print(f"获取远程logo信息时出错: {e}")
        import traceback
        traceback.print_exc()
    
    return logo_info

def sort_logo_info(logo_info, sort_method="name"):
    """
    根据指定的排序方法对logo信息进行排序
    
    Args:
        logo_info (list): logo信息列表
        sort_method (str): 排序方法，可选值: 
            "name" - 按名称自然排序 (默认，支持中文)
            "ascii" - ASCII码排序
            "size" - 按文件大小排序
            "time" - 按修改时间排序
    
    Returns:
        list: 排序后的logo信息列表
    """
    if not logo_info:
        return logo_info
        
    if sort_method == "name":
        # 按名称自然排序 (支持中文)
        try:
            from pypinyin import pinyin, Style
            # 为每个logo名称生成拼音
            for item in logo_info:
                # 将中文转换为拼音，使用带声调的拼音
                pinyin_list = pinyin(item['name'], style=Style.TONE)
                # 将拼音列表转换为字符串
                item['pinyin'] = ''.join([p[0] for p in pinyin_list])
            
            # 按拼音排序
            logo_info.sort(key=lambda x: x['pinyin'])
            
            # 移除临时添加的拼音字段
            for item in logo_info:
                del item['pinyin']
        except ImportError:
            print("警告: 未安装pypinyin库，使用ASCII排序")
            logo_info.sort(key=lambda x: x['name'])
    elif sort_method == "ascii":
        # ASCII码排序
        logo_info.sort(key=lambda x: x['name'])
    elif sort_method == "size":
        # 按文件大小排序 (从小到大)
        logo_info.sort(key=lambda x: x['size'])
    elif sort_method == "time":
        # 按修改时间排序 (从新到旧)
        logo_info.sort(key=lambda x: x['mtime'], reverse=True)
    else:
        # 默认使用名称自然排序
        logo_info.sort(key=lambda x: x['name'])
    
    return logo_info

def generate_markdown_table(logo_info, source_url):
    """
    生成Markdown表格
    
    Args:
        logo_info (list): 图片信息列表
        source_url (str): 数据源URL
    
    Returns:
        str: Markdown格式的表格
    """
    if not logo_info:
        return f"# Logo文件列表\n\n源: {source_url}\n\n暂无Logo文件"
    
    # 创建表头
    markdown = f"# Logo文件列表\n\n源: {source_url}\n\n"
    markdown += f"共找到 {len(logo_info)} 个Logo文件\n\n"
    markdown += "| logo名称 | logo链接 |\n"
    markdown += "|----------|----------|\n"
    
    # 添加表格行
    for info in logo_info:
        markdown += f"| {info['name']} | {info['link']} |\n"
    
    return markdown

def generate_json_content(logo_info):
    """
    生成JSON格式的内容
    
    Args:
        logo_info (list): 图片信息列表
        
    Returns:
        str: JSON格式的字符串
    """
    json_data = []
    
    for info in logo_info:
        # 移除链接中的尖括号
        clean_link = info['link'].strip('<>')
        json_data.append({
            "logo_name": info['name'],
            "logo_url": clean_link
        })
    
    return json.dumps(json_data, ensure_ascii=False, indent=2)

def write_to_file(content, filename):
    """
    将内容写入文件
    
    Args:
        content (str): 要写入的内容
        filename (str): 文件名
    """
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"成功生成文件: {filename}")
    except Exception as e:
        print(f"写入文件时出错: {e}")
        sys.exit(1)

def main():
    """主函数"""
    # 设置命令行参数
    parser = argparse.ArgumentParser(description='生成Logo列表')
    parser.add_argument('--url', type=str, required=True, help='GitHub仓库的logo目录URL')
    parser.add_argument('--output', type=str, default='README1.md', help='输出文件名')
    parser.add_argument('--token', type=str, help='GitHub个人访问令牌（可选）')
    
    args = parser.parse_args()
    
    # 从环境变量获取排序方法
    sort_method = os.environ.get('SORT_METHOD', 'name')  # 排序方法
    
    # 获取远程logo信息
    logo_info = get_remote_logo_info(args.url, args.token)
    
    # 根据指定的排序方法排序
    logo_info = sort_logo_info(logo_info, sort_method)
    
    # 生成Markdown表格
    markdown_content = generate_markdown_table(logo_info, args.url)
    
    # 生成JSON内容
    json_content = generate_json_content(logo_info)
    
    # 创建临时目录
    temp_dir = "/tmp/logo_list"
    os.makedirs(temp_dir, exist_ok=True)
    
    # 写入Markdown文件到临时位置
    output_file = os.path.join(temp_dir, args.output)
    write_to_file(markdown_content, output_file)
    
    # 生成对应的JSON文件名
    json_filename = os.path.splitext(args.output)[0] + '.json'
    json_output_file = os.path.join(temp_dir, json_filename)
    
    # 写入JSON文件
    write_to_file(json_content, json_output_file)
    
    print(f"处理完成，共找到 {len(logo_info)} 个Logo文件")
    print(f"使用的排序方法: {sort_method}")
    print(f"Markdown文件已生成到: {output_file}")
    print(f"JSON文件已生成到: {json_output_file}")

if __name__ == "__main__":
    main()
