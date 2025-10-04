import os
import glob
from pathlib import Path
import sys
import tempfile
import json  # 添加json模块

def get_logo_info(logo_dir="logo", username="yufeilai666", repo_name="tvepg", branch="main"):
    """
    获取logo目录下所有图片文件的信息
    
    Args:
        logo_dir (str): logo目录路径，默认为'logo'
        username (str): GitHub用户名
        repo_name (str): 仓库名称
        branch (str): 分支名称，默认为'main'
    
    Returns:
        list: 包含图片名称和链接的字典列表
    """
    logo_info = []
    
    # 支持的图片格式
    image_extensions = ['*.png', '*.jpg', '*.jpeg', '*.gif', '*.bmp', '*.svg', '*.webp']
    
    # 检查logo目录是否存在
    if not os.path.exists(logo_dir):
        print(f"错误: 目录 '{logo_dir}' 不存在")
        return logo_info
    
    # 查找所有图片文件
    image_files = []
    for ext in image_extensions:
        image_files.extend(glob.glob(os.path.join(logo_dir, ext)))
        image_files.extend(glob.glob(os.path.join(logo_dir, ext.upper())))
    
    if not image_files:
        print(f"警告: 在目录 '{logo_dir}' 中未找到图片文件")
        return logo_info
    
    # 获取图片信息
    for image_path in image_files:
        if os.path.isfile(image_path):
            # 获取文件名（不带扩展名）
            file_name = os.path.splitext(os.path.basename(image_path))[0]
            
            # 生成raw.githubusercontent.com的绝对路径，保留中文字符
            # 修复路径计算：直接构建相对于仓库根目录的路径
            # 假设logo目录就在仓库根目录下，避免复杂的相对路径计算
            logo_dir_name = os.path.basename(logo_dir.rstrip('/'))
            file_name_in_logo = os.path.basename(image_path)
            rel_path = f"{logo_dir_name}/{file_name_in_logo}"
            
            # 调试信息：打印路径计算过程
            print(f"处理文件: {image_path}")
            print(f"计算的相对路径: {rel_path}")
            
            # 使用<>包裹链接，保留中文字符
            file_link = f"<https://raw.githubusercontent.com/{username}/{repo_name}/{branch}/{rel_path}>"
            
            # 调试信息：打印生成的链接
            print(f"生成的链接: {file_link}")
            
            logo_info.append({
                "name": file_name,
                "link": file_link,
                "full_path": image_path,
                "size": os.path.getsize(image_path),
                "mtime": os.path.getmtime(image_path)
            })
    
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

def generate_markdown_table(logo_info):
    """
    生成Markdown表格
    
    Args:
        logo_info (list): 图片信息列表
    
    Returns:
        str: Markdown格式的表格
    """
    if not logo_info:
        return "# Logo文件列表\n\n暂无Logo文件"
    
    # 创建表头
    markdown = "# Logo文件列表\n\n"
    markdown += """- **第三方logo列表**: 
  - [112114](./logo_112114.md)
  - [fanmingming](./logo_fanmingming.md)
  - [taksssss](./logo_taksssss.md)\n\n"""
    markdown += "| logo名称 | logo链接 |\n"
    markdown += "|----------|----------|\n"
    
    # 添加表格行
    for info in logo_info:
        markdown += f"| {info['name']} | {info['link']} |\n"
    
    return markdown

def generate_json_content(logo_info):
    """
    生成JSON格式的logo信息
    
    Args:
        logo_info (list): 图片信息列表
    
    Returns:
        str: JSON格式的字符串
    """
    json_data = []
    for info in logo_info:
        # 移除Markdown链接的尖括号
        logo_url = info['link'].strip('<>')
        json_data.append({
            "logo_name": info['name'],
            "logo_url": logo_url
        })
    
    return json.dumps(json_data, ensure_ascii=False, indent=2)

def write_to_file(content, filename="README.md"):
    """
    将内容写入文件
    
    Args:
        content (str): 要写入的内容
        filename (str): 文件名，默认为README.md
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
    # 从环境变量获取参数，如果没有则使用默认值
    username = os.environ.get('GITHUB_ACTOR', 'yufeilai666')
    repo_name = os.environ.get('GITHUB_REPOSITORY', 'yufeilai666/tvepg').split('/')[-1]
    branch = os.environ.get('GITHUB_REF', 'refs/heads/logo_info').split('/')[-1]
    sort_method = os.environ.get('SORT_METHOD', 'name')  # 排序方法
    
    # 获取logo目录路径，优先使用环境变量
    logo_dir = os.environ.get('LOGO_DIR', 'logo')
    
    # 获取logo信息
    logo_info = get_logo_info(
        logo_dir=logo_dir,
        username=username,
        repo_name=repo_name,
        branch=branch
    )
    
    # 根据指定的排序方法排序
    logo_info = sort_logo_info(logo_info, sort_method)
    
    # 生成Markdown表格
    markdown_content = generate_markdown_table(logo_info)
    
    # 生成JSON内容
    json_content = generate_json_content(logo_info)
    
    # 创建临时目录并写入文件
    temp_dir = "/tmp/logo_list"
    output_md_file = os.path.join(temp_dir, "README.md")
    output_json_file = os.path.join(temp_dir, "logo.json")
    
    # 写入Markdown文件到临时位置
    write_to_file(markdown_content, output_md_file)
    
    # 写入JSON文件到临时位置
    write_to_file(json_content, output_json_file)
    
    print(f"处理完成，共找到 {len(logo_info)} 个Logo文件")
    print(f"使用的排序方法: {sort_method}")
    print(f"Markdown文件已生成到: {output_md_file}")
    print(f"JSON文件已生成到: {output_json_file}")

if __name__ == "__main__":
    main()
