from lxml import etree
from collections import defaultdict
import os
import json
import requests
import tempfile
import sys
import gzip
import shutil

def process_epg_file(input_file, output_file):
    """
    处理EPG(电子节目指南)XML文件，解决重复channel id问题并更新programme引用
    
    功能描述：
    1. 解析输入的XML文件，保留所有空白文本、CDATA块和注释
    2. 检测并重命名重复的channel id（不区分大小写）：
       - 首次出现的channel id保持不变
       - 后续重复出现的channel id添加数字后缀【" (2)", " (3)"，" (4)"...】
    3. 更新所有programme元素的channel引用，使其指向正确的重命名后channel
    4. 保持XML文档结构和原始格式不变（包括缩进、注释等）
    5. 将处理后的XML写入输出文件
    
    处理策略：
    - 使用两阶段处理确保正确性：
      第一阶段：扫描并重命名所有channel元素
      第二阶段：按文档顺序更新programme的channel引用
    
    :param input_file: 输入XML文件路径
    :param output_file: 输出XML文件路径
    """
    
    # 创建XML解析器：保留空白文本、CDATA块和注释
    parser = etree.XMLParser(
        remove_blank_text=False,  # 保留空白文本
        strip_cdata=False,        # 保留CDATA部分
        remove_comments=False     # 保留注释
    )
    
    try:
        # 解析输入的XML文件
        tree = etree.parse(input_file, parser)
        root = tree.getroot()
        
        # 计数器：记录每个小写channel id出现的次数
        channel_id_counter = defaultdict(int)
        # 映射表：存储原始id -> 最新生成的新id（用于programme引用）
        channel_id_map = {}
        # 完整映射：存储每个小写id生成的所有新id列表（调试用）
        all_channel_mappings = defaultdict(list)
        # 小写到原始id的映射
        lowercase_to_original = {}
        
        # === 第一阶段：处理所有channel元素 ===
        # 目标：识别重复的channel id并重命名（不区分大小写）
        channel_elements = root.findall("channel")
        for elem in channel_elements:
            old_id = elem.get("id")
            lower_id = old_id.lower()  # 转换为小写进行比较
            
            # 更新当前小写id的计数（首次出现为1）
            count = channel_id_counter[lower_id] + 1
            channel_id_counter[lower_id] = count
            
            # 记录小写到原始id的映射（保留第一次出现的原始形式）
            if lower_id not in lowercase_to_original:
                lowercase_to_original[lower_id] = old_id
            
            # 生成新id规则：
            # 首次出现的id保持原样
            # 后续重复出现的id添加后缀【" (2)", " (3)", " (4)"...
            new_id = old_id if count == 1 else f"{old_id} ({count})"  # 修改后缀格式
            # 修改当前channel元素的id属性
            elem.set("id", new_id)
            # 更新映射关系（覆盖式存储，记录最后一次生成的新id）
            channel_id_map[old_id] = new_id
            # 记录该小写id对应的所有新id（完整记录）
            all_channel_mappings[lower_id].append(new_id)
        
        # === 第二阶段：处理programme元素的channel引用 ===
        # 目标：更新所有programme的channel属性，指向正确的重命名后channel
        # 使用文档顺序遍历，动态维护channel映射关系
        current_mapping = {}  # 存储当前上下文的最新channel映射
        
        # 按XML文档顺序遍历所有节点
        for elem in root.iter():
            if elem.tag == "channel":
                # 遇到channel元素时更新当前映射
                current_id = elem.get("id")
                # 提取小写id以更新映射
                lower_id = None
                for base_lower_id, new_ids in all_channel_mappings.items():
                    if current_id in new_ids:
                        lower_id = base_lower_id
                        break
                if lower_id is not None:
                    # 使用第一次出现的原始id作为映射键
                    original_id = lowercase_to_original[lower_id]
                    current_mapping[original_id] = current_id
            elif elem.tag == "programme":
                # 处理programme元素的channel属性
                old_channel = elem.get("channel")
                # 将引用转换为小写形式查找映射
                lower_channel = old_channel.lower()
                original_id = lowercase_to_original.get(lower_channel, old_channel)
                
                # 映射优先级策略：
                # 1. 优先使用当前上下文的最新映射（current_mapping）
                #    - 适用于同一原始id多次出现的情况
                # 2. 若无上下文映射，使用最后一次生成的映射（channel_id_map）
                #    - 兜底策略，确保所有引用都能更新
                if original_id in current_mapping:
                    elem.set("channel", current_mapping[original_id])
                elif original_id in channel_id_map:
                    elem.set("channel", channel_id_map[original_id])
        # 注意：原始逻辑假设所有channel引用都有对应映射
        
        # === 输出处理结果 ===
        # 美化输出XML并保留原始格式
        xml_str = etree.tostring(
            root,
            pretty_print=True,       # 格式化输出
            encoding="UTF-8",        # 使用UTF-8编码
            xml_declaration=True,    # 保留XML声明
            doctype=tree.docinfo.doctype  # 保留DOCTYPE声明
        )
        
        # 将处理后的XML写入输出文件
        with open(output_file, "wb") as f:
            f.write(xml_str)
        
        return True, "成功处理"
    
    except etree.XMLSyntaxError as e:
        return False, f"XML语法错误: {e}"
    except Exception as e:
        return False, f"处理XML文件时出错: {e}"

def download_file(url, local_path):
    """从URL下载文件到本地路径，支持gzip压缩文件和普通XML文件"""
    try:
        # 从URL中提取文件名
        from urllib.parse import urlparse
        parsed_url = urlparse(url)
        url_filename = os.path.basename(parsed_url.path) or "unknown_file"
        
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()  # 检查请求是否成功
        
        # 检查是否为gzip压缩文件
        content_encoding = response.headers.get('Content-Encoding', '').lower()
        is_gzip = 'gzip' in content_encoding or url.lower().endswith('.gz')
        
        # 如果不是明确的gzip文件，检查文件内容的前几个字节
        if not is_gzip:
            # 预读前几个字节来判断文件类型
            first_chunk = next(response.iter_content(chunk_size=10))
            response = requests.get(url, stream=True, timeout=30)  # 重新获取响应
            
            # 检查是否为gzip文件 (前两个字节应该是 0x1f 0x8b)
            if len(first_chunk) >= 2 and first_chunk[0] == 0x1f and first_chunk[1] == 0x8b:
                is_gzip = True
            # 检查是否为XML文件 (通常以 <?xml 或 UTF-8 BOM 开头)
            elif len(first_chunk) >= 5 and first_chunk[:5] == b'<?xml':
                is_gzip = False
            elif len(first_chunk) >= 3 and first_chunk[:3] == b'\xef\xbb\xbf':  # UTF-8 BOM
                is_gzip = False
        
        if is_gzip:
            # 如果是gzip文件，先下载压缩文件，然后解压
            gzip_path = local_path + '.gz'
            with open(gzip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            # 解压gzip文件
            try:
                with gzip.open(gzip_path, 'rb') as f_in:
                    with open(local_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                print(f"下载并解压: {url_filename}")
            except Exception as e:
                # 如果解压失败，尝试直接使用文件内容
                print(f"解压失败，尝试直接使用文件: {e}")
                shutil.move(gzip_path, local_path)
            finally:
                # 删除临时压缩文件（如果存在）
                if os.path.exists(gzip_path):
                    os.remove(gzip_path)
        else:
            # 如果不是压缩文件，直接下载
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            print(f"下载: {url_filename}")
        
        return True, "下载成功"
    except requests.exceptions.RequestException as e:
        return False, f"下载文件失败: {e}"
    except Exception as e:
        return False, f"处理文件失败: {e}"

def get_config_from_env():
    """
    从环境变量中获取配置信息
    
    支持两种方式：
    1. 从 JSON_FILE 环境变量中读取配置文件路径
    2. 从 EPG_CONFIG 环境变量中直接读取JSON配置字符串
    
    :return: 配置字典
    """
    # 方式1：从环境变量中读取配置文件路径
    config_file_path = os.environ.get('JSON_FILE')
    if config_file_path and os.path.exists(config_file_path):
        try:
            with open(config_file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            print(f"配置文件格式错误: {e}")
            return None
    
    # 方式2：从环境变量中直接读取JSON配置字符串
    config_json = os.environ.get('EPG_CONFIG')
    if config_json:
        try:
            return json.loads(config_json)
        except json.JSONDecodeError as e:
            print(f"环境变量中的JSON配置格式错误: {e}")
            return None
    
    # 方式3：默认配置文件
    default_config_file = "epg_config.json"
    if os.path.exists(default_config_file):
        try:
            with open(default_config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            print(f"默认配置文件格式错误: {e}")
            return None
    
    print("错误：未找到有效的配置文件或配置环境变量")
    print("请设置 JSON_FILE 环境变量指定配置文件路径")
    print("或设置 EPG_CONFIG 环境变量包含JSON配置字符串")
    return None

def process_multiple_files():
    """
    从环境变量或配置文件中读取多个XML文件配置，并处理每个文件
    
    每个文件的处理都是独立的，一个文件的错误不会影响其他文件的处理
    """
    # 获取配置
    config = get_config_from_env()
    if not config:
        return False
    
    # 创建临时目录用于存储下载的XML文件
    temp_dir = tempfile.mkdtemp()
    print(f"临时目录: {temp_dir}")
    
    success_count = 0
    total_count = len(config)
    
    # 处理每个XML文件
    for output_file, url in config.items():
        # 从URL中提取输入文件名
        from urllib.parse import urlparse
        parsed_url = urlparse(url)
        input_filename = os.path.basename(parsed_url.path) or "unknown_file.xml"
        
        print(f"\n开始处理: {input_filename} -> {output_file}")
        
        # 为每个文件创建独立的临时文件
        temp_file = os.path.join(temp_dir, f"temp_{os.path.basename(url).replace('.gz', '')}")
        
        # 下载XML文件
        download_success, download_message = download_file(url, temp_file)
        if not download_success:
            print(f"下载失败: {download_message}")
            continue
        
        # 处理XML文件
        process_success, process_message = process_epg_file(temp_file, output_file)
        if process_success:
            print(f"成功处理: {output_file}")
            success_count += 1
        else:
            print(f"处理失败: {process_message}")
        
        # 清理当前文件的临时文件
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        except Exception as e:
            print(f"清理临时文件失败: {e}")
    
    # 清理临时目录
    try:
        shutil.rmtree(temp_dir)
        print(f"\n已清理临时目录: {temp_dir}")
    except Exception as e:
        print(f"清理临时目录失败: {e}")
    
    print(f"\n处理完成: {success_count}/{total_count} 个文件成功")
    return success_count > 0

if __name__ == "__main__":
    # 处理多个XML文件
    success = process_multiple_files()
    
    if success:
        print("所有文件处理完成！")
        sys.exit(0)
    else:
        print("处理过程中出现错误！")
        sys.exit(1)