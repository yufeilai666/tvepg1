#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
EPG 处理脚本

功能说明：
1. 合并多个 EPG XML 文件（支持普通 XML 和 .gz 压缩文件，以及远程URL）
   - 按原始XML文件的顺序保留所有元素
   - 对每个元素进行格式化处理
   - 最终生成格式化的合并 XML 文件
2. 处理合并后的 EPG XML 文件，解决重复 channel id 的问题（不区分大小写）
   - 为重复的 channel id 添加后缀（如 " (2)", " (3)" 等）
   - 更新节目元素的频道引用以匹配新的频道 ID
3. 生成输出文件：
   - 格式化的 XML 文件
   - 压缩的 XML.gz 文件
   - README.md 文件，包含频道统计信息
   - JSON 文件，包含频道详细信息
4. 保留原始 XML 的结构、格式和内容不变
5. 保留命名空间属性并添加指定属性

使用说明：
1. 确保安装了必要的 Python 库：pip install lxml requests
2. 将要处理的 XML 文件放在同一目录下，或提供远程URL
3. 在脚本中修改 xml_files 列表，添加要处理的文件名或URL
4. 运行脚本：python snow_epg.py
5. 输出文件将保存在当前目录下

注意事项：
- 脚本会自动处理 .gz 压缩文件
- 脚本支持从URL下载文件
- 重复的频道 ID 会自动添加后缀进行区分
- 脚本会生成详细的统计信息和格式化文档
"""

from lxml import etree
from collections import defaultdict
import os
import datetime
import gzip
import json
import tempfile
import time
import sys
import requests
import urllib.parse

# 定义要合并的XML文件列表（支持.gz压缩文件和URL）
xml_files = [
    'epgpw.xml',
    'lstime_epg.xml',
    'epgmytvsuper_new_cst.xml',
    'epganywhere.xml',
    'epgkai.xml',
    'epg4gtv2_cst.xml',
    'epgdifang.xml', 
    'epgshanghai.xml',
    #'epgguangxi.xml',
    'https://raw.githubusercontent.com/zzq12345/tvepg/main/epgnewguangdong.xml',
    'https://raw.githubusercontent.com/zzq12345/tvepg/main/epgnewhebei.xml',
    #'epgofiii.xml',
    #'epgastro.xml',
    #'epgunifi.xml',
]

def download_file(url, local_filename):
    """从URL下载文件到本地"""
    try:
        print(f"正在下载: {url}")
        with requests.get(url, stream=True, timeout=30) as r:
            r.raise_for_status()
            with open(local_filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        return True
    except Exception as e:
        print(f"下载失败: {url} - 错误: {str(e)}")
        return False

def format_bytes(bytes, precision=2):
    """格式化字节大小"""
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    bytes = max(bytes, 0)
    pow = 0
    if bytes:
        pow = int((len(str(bytes)) - 1) / 3)
    pow = min(pow, len(units) - 1)
    bytes /= (1024 ** pow)
    return f"{round(bytes, precision)} {units[pow]}"

def merge_epg_files():
    """
    合并多个EPG XML文件
    
    该函数会：
    1. 遍历所有指定的XML文件（支持普通XML和.gz压缩文件，以及URL）
    2. 按原始XML文件的顺序保留所有元素
    3. 对每个元素进行格式化处理
    4. 最终生成格式化的合并XML文件
    5. 显示处理进度和统计信息
    """
    print("开始合并EPG文件...")
    
    # 创建一个临时文件来存储合并的XML内容
    temp_output_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.xml', encoding='utf-8')
    temp_output_path = temp_output_file.name
    temp_output_file.close()
    
    # 重新以二进制模式打开文件，以便正确处理XML声明
    with open(temp_output_path, 'wb') as temp_handle:
        # 写入XML头部
        temp_handle.write('<?xml version="1.0" encoding="UTF-8"?>\n'.encode('utf-8'))
        temp_handle.write('<tv>\n'.encode('utf-8'))
        
        total_files = len(xml_files)
        success_count = 0
        failed_files = []  # 记录失败的文件和原因
        
        # 按文件顺序合并所有元素
        print("开始合并数据...")
        for current_file, file in enumerate(xml_files, 1):
            start_time = time.time()
            
            # 检查是否是URL
            is_url = file.startswith(('http://', 'https://'))
            
            if is_url:
                # 处理URL
                try:
                    # 创建临时文件
                    url_temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xml')
                    url_temp_file.close()
                    
                    # 下载文件
                    if not download_file(file, url_temp_file.name):
                        failed_files.append((file, "下载失败"))
                        continue
                    
                    file_path = url_temp_file.name
                    display_name = os.path.basename(urllib.parse.urlparse(file).path)
                    is_gz_file = display_name.endswith('.gz')
                except Exception as e:
                    error_msg = f"处理URL出错: {str(e)}"
                    print(f"[{current_file}/{total_files}] {error_msg}")
                    failed_files.append((file, error_msg))
                    continue
            else:
                # 处理本地文件
                file_path = file
                display_name = os.path.basename(file)
                
                # 检查文件是否存在
                if not os.path.exists(file_path):
                    error_msg = "文件不存在"
                    print(f"[{current_file}/{total_files}] 跳过不存在的文件: {display_name}")
                    failed_files.append((file, error_msg))
                    continue
                
                is_gz_file = file.endswith('.gz')
            
            # 处理文件
            try:
                if is_gz_file:
                    # 处理.gz压缩文件
                    with gzip.open(file_path, 'rb') as gz_handle:
                        content = gz_handle.read()
                else:
                    # 处理普通XML文件
                    with open(file_path, 'rb') as f:
                        content = f.read()
                
                # 使用XML解析器处理内容
                parser = etree.XMLParser(recover=True)
                root = etree.fromstring(content, parser)
                
                # 统计频道和节目数量
                channel_count = len(root.xpath('//channel'))
                programme_count = len(root.xpath('//programme'))
                
                # 查找所有直接子元素（channel和programme）
                element_count = 0
                for element in root:
                    # 只处理channel和programme元素
                    if element.tag in ['channel', 'programme']:
                        # 格式化XML
                        element_xml = etree.tostring(element, encoding='unicode', pretty_print=True)
                        # 写入格式化后的XML
                        temp_handle.write(('  ' + element_xml + '\n').encode('utf-8'))
                        element_count += 1
                
                elapsed_time = round(time.time() - start_time, 2)
                file_type = "(.gz压缩)" if is_gz_file else ""
                source_type = "(URL)" if is_url else ""
                print(f"[{current_file}/{total_files}] 处理文件: {display_name} - 找到 {channel_count} 个频道, {programme_count} 个节目, 共 {element_count} 个元素 (耗时: {elapsed_time}s) {file_type} {source_type}")
                
                success_count += 1
                
            except Exception as e:
                error_msg = f"处理文件出错: {str(e)}"
                print(f"[{current_file}/{total_files}] {error_msg}")
                failed_files.append((file, error_msg))
            finally:
                # 清理临时文件
                if is_url and os.path.exists(file_path):
                    os.unlink(file_path)
        
        # 完成XML文档
        temp_handle.write('</tv>'.encode('utf-8'))
    
    # 打印失败的文件信息
    if failed_files:
        print("\n以下文件处理失败:")
        for file, reason in failed_files:
            print(f"  - {file}: {reason}")
    
    print(f"\nXML文件合并完成，成功处理 {success_count}/{total_files} 个文件，正在进行最终格式化...")
    
    # 读取临时文件内容
    with open(temp_output_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 使用lxml进行最终格式化
    try:
        parser = etree.XMLParser(remove_blank_text=True)
        root = etree.fromstring(content.encode('utf-8'), parser)
        
        # 格式化XML
        formatted_xml = etree.tostring(
            root, 
            encoding='utf-8', 
            xml_declaration=True, 
            pretty_print=True
        ).decode('utf-8')
        
        with open('epgziyong.xml', 'w', encoding='utf-8') as f:
            f.write(formatted_xml)
        print("XML文件已成功格式化和保存。")
    except Exception as e:
        print(f"XML解析错误，使用原始内容（未格式化）: {str(e)}")
        with open('epgziyong.xml', 'w', encoding='utf-8') as f:
            f.write(content)
    
    # 清理临时文件
    os.unlink(temp_output_path)
    
    # 显示最终文件大小
    if os.path.exists('epgziyong.xml'):
        output_size = os.path.getsize('epgziyong.xml')
        print(f"合成待下一步处理的文件大小: {format_bytes(output_size)}")
    
    return 'epgziyong.xml'

def process_epg_file(input_file, output_file):
    """
    处理EPG XML文件，解决重复channel id的问题（不区分大小写）
    
    该函数会：
    1. 解析输入的XML文件
    2. 为重复的channel id添加后缀【" (2)"、" (3)"、" (4)"等】，检测时不区分字母大小写
    3. 更新programme元素的channel属性，使其指向对应的新channel id
    4. 保持原始XML的结构、格式和内容不变
    5. 将处理后的XML写入输出文件
    6. 同时生成压缩的XML.gz文件
    7. 在<tv>元素中保留命名空间属性并添加指定属性
    8. 生成README.md文件，包含频道统计信息
    9. 生成同名的JSON文件，包含频道信息
    """
    # 创建XML解析器，保留空白、CDATA和注释
    parser = etree.XMLParser(
        remove_blank_text=False,   # 保留空白文本
        strip_cdata=False,         # 保留CDATA部分
        remove_comments=False      # 保留注释
    )
    
    # 解析XML文件
    tree = etree.parse(input_file, parser)
    root = tree.getroot()
    
    # 初始化计数器，用于统计每个原始channel id出现的次数（不区分大小写）
    channel_id_counter = defaultdict(int)
    # 初始化映射表，存储每个原始id到当前最新后缀id的映射
    current_mapping = {}
    # 初始化频道信息字典
    channel_info = {}
    # 按顺序存储频道ID
    channel_ids_in_order = []
    
    # 按文档顺序遍历所有元素
    for elem in root.iter():
        if elem.tag == "channel":
            # 处理channel元素
            old_id = elem.get("id")
            # 使用小写形式进行计数（实现不区分大小写的检测）
            lower_id = old_id.lower()
            # 更新该id的出现计数
            count = channel_id_counter[lower_id] + 1
            channel_id_counter[lower_id] = count
            
            # 生成新id【第一个不加后缀，后续加" (2)", " (3)", " (4)"等）】
            new_id = old_id if count == 1 else f"{old_id} ({count})"
            # 更新channel元素的id属性
            elem.set("id", new_id)
            # 更新当前映射表
            current_mapping[old_id] = new_id
            
            # 收集频道信息
            display_name = elem.find("display-name")
            channel_name = display_name.text if display_name is not None else "未知频道"
            channel_info[new_id] = {
                'name': channel_name,
                'program_count': 0,
                'min_start': None,
                'max_end': None
            }
            channel_ids_in_order.append(new_id)
        
        elif elem.tag == "programme":
            # 处理programme元素
            channel_ref = elem.get("channel")
            # 检查该引用是否在当前映射表中
            if channel_ref in current_mapping:
                new_id = current_mapping[channel_ref]
                # 更新programme的channel属性为最新的映射id
                elem.set("channel", new_id)
                
                # 收集节目信息
                start_str = elem.get("start")
                end_str = elem.get("stop")  # 注意：属性名是stop，不是end
                
                # 解析时间字符串
                try:
                    # 格式：20250814192500 +0800
                    start_dt = datetime.datetime.strptime(start_str[:14], "%Y%m%d%H%M%S")
                    end_dt = datetime.datetime.strptime(end_str[:14], "%Y%m%d%H%M%S")
                except (ValueError, TypeError):
                    # 如果时间格式错误，跳过该节目
                    continue
                
                # 更新频道信息
                if new_id in channel_info:
                    channel_info[new_id]['program_count'] += 1
                    
                    # 更新最早开始时间
                    if channel_info[new_id]['min_start'] is None or start_dt < channel_info[new_id]['min_start']:
                        channel_info[new_id]['min_start'] = start_dt
                    
                    # 更新最晚结束时间
                    if channel_info[new_id]['max_end'] is None or end_dt > channel_info[new_id]['max_end']:
                        channel_info[new_id]['max_end'] = end_dt
    
    # 保留命名空间属性
    # 获取当前所有属性
    current_attrs = dict(root.attrib)
    
    # 筛选出命名空间属性（以"xmlns"开头的属性）
    ns_attrs = {k: v for k, v in current_attrs.items() if k.startswith("xmlns")}
    
    # 清除所有属性
    root.attrib.clear()
    
    # 重新添加命名空间属性
    for key, value in ns_attrs.items():
        root.set(key, value)
    
    # 添加指定的属性
    beijing_time = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
    time_str = beijing_time.strftime("%Y-%m-%d %H:%M:%S")
    root.set("generator-info-time", f"{time_str}")
    root.set("generator-info-name", "yufeilai666")
    root.set("source-info-name", "秋哥综合、epg.pw、51zmt、AqFad2811、deny")
    root.set("source-info-url", "https://epg.pw、http://epg.51zmt.top:8000、https://github.com/AqFad2811/epg、https://epg.deny.vip")
    
    # 分离频道和节目元素
    channels = []
    programmes = []
    others = []
    
    for elem in root:
        if elem.tag == "channel":
            channels.append(elem)
        elif elem.tag == "programme":
            programmes.append(elem)
        else:
            others.append(elem)
    
    # 清空根元素
    for elem in list(root):
        root.remove(elem)
    
    # 先添加所有频道，再添加所有节目，最后添加其他元素
    for channel in channels:
        root.append(channel)
    for programme in programmes:
        root.append(programme)
    for other in others:
        root.append(other)
    
    # 准备输出XML
    # 获取XML声明和DOCTYPE
    xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>'
    doctype = tree.docinfo.doctype
    
    # 使用lxml的漂亮打印功能重新格式化整个XML树
    # 首先创建一个新的根元素，保留命名空间
    new_root = etree.Element(root.tag, nsmap=root.nsmap)
    
    # 复制所有属性
    for key, value in root.attrib.items():
        new_root.set(key, value)
    
    # 复制所有子元素
    for child in root:
        new_root.append(child)
    
    # 使用漂亮打印格式化XML
    etree.indent(new_root, space="  ")
    
    # 生成XML字符串
    xml_str = etree.tostring(
        new_root,
        encoding="UTF-8",
        xml_declaration=False,
        doctype=None,
        pretty_print=True
    ).decode("UTF-8")
    
    # 创建完整的XML内容
    full_xml_content = xml_declaration + "\n"
    if doctype:
        full_xml_content += doctype + "\n"
    full_xml_content += xml_str
    
    # 写入输出文件（XML格式）
    with open(output_file, "w", encoding="UTF-8") as f:
        f.write(full_xml_content)
    
    # 创建压缩文件名（在原始文件名后加.gz）
    compressed_file = output_file + ".gz"
    
    # 写入压缩文件（XML.gz格式）
    with gzip.open(compressed_file, "wt", encoding="UTF-8") as f:
        f.write(full_xml_content)
    
    # 生成README.md文件（与输出文件同目录）
    output_dir = os.path.dirname(output_file) or "."
    readme_file = os.path.join(output_dir, "README.md")
    
    # 计算频道总数
    total_channels = len(channel_ids_in_order)
    
    # README.md文件头信息
    readme_content = f"""# EPG-电子节目单

## 订阅信息
- **XML订阅**: <https://raw.githubusercontent.com/yufeilai666/tvepg/main/{os.path.basename(output_file)}>
- **GZ压缩包订阅**: <https://raw.githubusercontent.com/yufeilai666/tvepg/main/{os.path.basename(output_file)}.gz>

## 更新信息
- **节目单名称**: {os.path.basename(output_file)}
- **最后更新时间**: {time_str} (UTC+8)
- **频道总数**: {total_channels}

## 频道列表
"""
    
    # 准备JSON数据
    json_data = []
    
    with open(readme_file, "w", encoding="UTF-8") as f:
        # 写入README.md头信息
        f.write(readme_content)
        
        # 写入表格头
        f.write("| 频道id | 频道名称 | 节目数量 | 时间范围 |\n")
        f.write("| --------- | --------- | --------- | --------- |\n")
        
        # 写入每个频道的信息
        for channel_id in channel_ids_in_order:
            info = channel_info.get(channel_id, {})
            name = info.get('name', '未知频道')
            count = info.get('program_count', 0)
            
            # 处理日期范围
            min_start = info.get('min_start')
            max_end = info.get('max_end')
            
            if min_start and max_end:
                # 格式化日期范围
                date_range = f"{min_start.strftime('%Y-%m-%d %H:%M:%S')} 至 {max_end.strftime('%Y-%m-%d %H:%M:%S')}"
                # 为JSON准备日期范围
                json_date_range = {
                    "start": min_start.strftime('%Y-%m-%d %H:%M:%S'),
                    "end": max_end.strftime('%Y-%m-%d %H:%M:%S')
                }
            else:
                date_range = "无节目"
                json_date_range = {"start": None, "end": None}
            
            # 写入表格行
            f.write(f"| {channel_id} | {name} | {count} | {date_range} |\n")
            
            # 添加JSON数据
            json_data.append({
                "channel_id": channel_id,
                "channel_name": name,
                "programme_count": count,
                "date_range": json_date_range,
                "has_programmes": count > 0
            })
    
    # 生成JSON文件（与输出文件同目录，同名但扩展名为.json）
    json_file = os.path.splitext(output_file)[0] + ".json"
    with open(json_file, "w", encoding="UTF-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    
    return output_file, compressed_file, readme_file, json_file

if __name__ == "__main__":
    # 检查是否安装了requests库
    try:
        import requests
    except ImportError:
        print("错误：需要安装requests库，请运行: pip install requests")
        sys.exit(1)
    
    # 第一步：合并所有EPG文件
    merged_file = merge_epg_files()
    
    # 第二步：处理合并后的EPG文件
    # 定义输出文件名
    output_file = "snow_epg.xml"
    
    # 检查输入文件是否存在
    if not os.path.exists(merged_file):
        print(f"错误：输入文件 '{merged_file}' 不存在")
        sys.exit(1)
    
    # 处理EPG文件
    xml_file, gz_file, readme_file, json_file = process_epg_file(merged_file, output_file)
    print(f"\n处理完成！输出文件:")
    print(f"  - XML文件: {xml_file}")
    print(f"  - 压缩文件: {gz_file}")
    print(f"  - README文件: {readme_file}")
    print(f"  - JSON文件: {json_file}")