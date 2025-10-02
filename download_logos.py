import os
import re
import requests
from urllib.parse import unquote, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import subprocess
import time
import sys
import hashlib

# 配置参数 - 通过环境变量获取
M3U_FILE = os.getenv('INPUT_M3U_FILE', 'playlist.m3u')  # 默认值
LOGOS_DIR = os.getenv('INPUT_LOGOS_DIR', 'logo')        # 存储目录
MAX_WORKERS = int(os.getenv('INPUT_MAX_WORKERS', '15'))  # 并发线程数
RETRY_COUNT = int(os.getenv('INPUT_RETRY_COUNT', '5'))   # 重试次数
GIT_USER = os.getenv('GITHUB_ACTOR')                     # GitHub用户名
GIT_EMAIL = f"{os.getenv('GITHUB_ACTOR')}@users.noreply.github.com"  # GitHub邮箱

def extract_logo_links(m3u_file):
    """从M3U文件中提取所有唯一的tvg-logo链接"""
    logo_links = set()
    tvg_logo_pattern = re.compile(r'tvg-logo="([^"]+)"')
    
    try:
        with open(m3u_file, 'r', encoding='utf-8') as f:
            for line in f:
                match = tvg_logo_pattern.search(line)
                if match:
                    logo_url = unquote(match.group(1)).strip()
                    logo_links.add(logo_url)
        print(f"发现 {len(logo_links)} 个唯一Logo链接")
        return list(logo_links)
    except Exception as e:
        print(f"::error::解析M3U文件失败: {str(e)}")
        sys.exit(1)

def get_filename_from_url(url):
    """从URL中提取安全的文件名，保留-和_"""
    parsed = urlparse(url)
    filename = os.path.basename(parsed.path)
    
    # 保留所有安全字符：字母、数字、-、_、. 
    # 只替换其他特殊字符
    filename = re.sub(r"[^\w\.\-]", "_", filename)
    
    # 如果文件名为空（如以/结尾的URL），使用哈希值
    if not filename.strip():
        url_hash = hashlib.md5(url.encode()).hexdigest()
        filename = f"logo_{url_hash[:8]}"
    
    # 如果文件名过长则截断
    if len(filename) > 120:
        name, ext = os.path.splitext(filename)
        filename = name[:100] + ext
    
    return filename

def download_logo(url, dest_dir):
    """下载单个Logo到指定目录"""
    filename = get_filename_from_url(url)
    filepath = os.path.join(dest_dir, filename)
    
    # 跳过已存在文件
    if os.path.exists(filepath):
        return (url, filename, "已存在", None)
    
    # 下载文件（带重试机制）
    for attempt in range(RETRY_COUNT):
        try:
            headers = {
                'User-Agent': 'AptvPlayer/2.4.3',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                'Referer': 'https://www.google.com/'
            }
            response = requests.get(url, headers=headers, timeout=20, allow_redirects=True)
            response.raise_for_status()
            
            # 验证图片内容
            content_type = response.headers.get('Content-Type', '')
            if not content_type.startswith('image/'):
                return (url, filename, f"无效内容类型: {content_type}", None)
            
            # 保存文件
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            # 获取文件大小
            size = os.path.getsize(filepath)
            return (url, filename, "下载成功", size)
        except Exception as e:
            if attempt < RETRY_COUNT - 1:
                time.sleep(2)
            else:
                return (url, filename, f"失败: {str(e)}", None)

def git_operations():
    """执行Git操作：添加、提交和推送"""
    try:
        # 配置Git用户
        subprocess.run(['git', 'config', '--global', 'user.name', GIT_USER], check=True)
        subprocess.run(['git', 'config', '--global', 'user.email', GIT_EMAIL], check=True)
        
        # 添加所有文件
        subprocess.run(['git', 'add', LOGOS_DIR], check=True)
        
        # 检查是否有变更
        status = subprocess.run(['git', 'status', '--porcelain'], 
                               capture_output=True, text=True, check=True)
        if not status.stdout.strip():
            print("::notice::无变更需要提交")
            return
        
        # 提交和推送
        commit_message = f"自动更新Logo {time.strftime('%Y-%m-%d %H:%M:%S')}"
        subprocess.run(['git', 'commit', '-m', commit_message], check=True)
        subprocess.run(['git', 'pull', '--rebase', 'origin', 'HEAD'], check=True)
        subprocess.run(['git', 'push'], check=True)
        print("::notice::成功推送到GitHub仓库")
    except subprocess.CalledProcessError as e:
        print(f"::error::Git操作失败: {e.stderr}")
        sys.exit(1)

def main():
    # 创建存储目录
    os.makedirs(LOGOS_DIR, exist_ok=True)
    
    # 步骤1: 提取Logo链接
    print("::group::步骤1/4: 解析M3U文件")
    logo_urls = extract_logo_links(M3U_FILE)
    print("::endgroup::")
    
    # 步骤2: 并行下载
    print(f"::group::步骤2/4: 下载Logo (使用 {MAX_WORKERS} 线程)")
    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(download_logo, url, LOGOS_DIR): url for url in logo_urls}
        
        for future in as_completed(futures):
            url = futures[future]
            result = future.result()
            results.append(result)
            status = result[2]
            filename = result[1]
            
            if "成功" in status:
                size = result[3]
                size_mb = size / (1024 * 1024) if size else 0
                print(f"✅ {filename} - {size_mb:.2f}MB")
            elif "已存在" in status:
                print(f"⏩ {filename}")
            else:
                print(f"❌ {filename} - {status}")
    print("::endgroup::")
    
    # 统计结果
    success = sum(1 for r in results if "成功" in r[2])
    skipped = sum(1 for r in results if "已存在" in r[2])
    failed = len(logo_urls) - success - skipped
    
    print(f"::notice::下载完成: 成功 {success}, 跳过 {skipped}, 失败 {failed}")
    
    # 步骤3: Git推送
    if success > 0 or skipped > 0:
        print("::group::步骤3/4: 推送到GitHub")
        git_operations()
        print("::endgroup::")
    
    # 步骤4: 生成报告
    print("::group::步骤4/4: 下载报告")
    if failed > 0:
        print(f"::warning::有{failed}个文件下载失败")
        print("\n失败的URL列表:")
        for r in results:
            if "失败" in r[2] or "无效" in r[2]:
                print(f"- {r[0]}")
    
    print(f"::set-output name=success::{success}")
    print(f"::set-output name=skipped::{skipped}")
    print(f"::set-output name=failed::{failed}")
    print("::endgroup::")
    
    print("::notice::所有操作完成！")

if __name__ == "__main__":
    main()