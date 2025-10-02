from lxml import etree
from collections import defaultdict
import os
import datetime
import gzip

def process_epg_file(input_file, output_file):
    """
    处理EPG XML文件，解决重复channel id的问题
    
    该函数会：
    1. 解析输入的XML文件
    2. 为重复的channel id添加后缀【" (2)"、" (3)"、" (4)"等】
    3. 更新programme元素的channel属性，使其指向对应的新channel id
    4. 保持原始XML的结构、格式和内容不变
    5. 将处理后的XML写入输出文件
    6. 同时生成压缩的XML.gz文件
    7. 在<tv>元素中保留命名空间属性并添加指定属性
    8. 生成README_TEST.md文件，包含频道统计信息
    """
    # 创建XML解析器，保留空白、CDATA和注释
    parser = etree.XMLParser(
        remove_blank_text=False,  # 保留空白文本
        strip_cdata=False,         # 保留CDATA部分
        remove_comments=False      # 保留注释
    )
    
    # 解析XML文件
    tree = etree.parse(input_file, parser)
    root = tree.getroot()
    
    # 初始化计数器，用于统计每个原始channel id出现的次数
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
            # 更新该id的出现计数
            count = channel_id_counter[old_id] + 1
            channel_id_counter[old_id] = count
            
            # 生成新id【第一个不加后缀，后续加" (2)", " (3)", " (4)"等】
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
    time_str = beijing_time.strftime("%Y-%m-%d")
    root.set("info-name", f"by yufeilai666 {time_str}")
    root.set("source-info-url", "https://github.com/zzq12345/tvepg/")
    
    # 准备输出XML
    # 获取XML声明和DOCTYPE
    xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>'
    doctype = tree.docinfo.doctype
    
    # 生成XML字符串，保留格式
    xml_str = etree.tostring(
        root,
        pretty_print=True,
        encoding="UTF-8",
        xml_declaration=False,  # 我们手动添加声明以控制格式
        doctype=None            # 不包含DOCTYPE，我们将手动写入
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
    
    # 生成README_TEST.md文件（与输出文件同目录）
    output_dir = os.path.dirname(output_file) or "."
    readme_file = os.path.join(output_dir, "README_TEST.md")
    
    # 计算频道总数
    total_channels = len(channel_ids_in_order)
    
    # README_TEST.md文件头信息
    readme_content = f"""# EPG-电子节目单

## 更新信息
- **节目单名称**: {os.path.basename(output_file)}
- **最后更新时间**: {time_str} (UTC+8)
- **频道总数**: {total_channels}

## 频道列表
"""
    
    with open(readme_file, "w", encoding="UTF-8") as f:
        # 写入README_TEST.md头信息
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
            else:
                date_range = "无节目"
            
            # 写入表格行
            f.write(f"| {channel_id} | {name} | {count} | {date_range} |\n")
    
    return output_file, compressed_file, readme_file

if __name__ == "__main__":
    # 设置输入输出文件路径
    input_file = "epg_test_old.xml"
    output_file = "epg_test.xml"
    
    # 检查输入文件是否存在
    if not os.path.exists(input_file):
        print(f"错误：输入文件 '{input_file}' 不存在")
        exit(1)
    
    # 处理EPG文件
    xml_file, gz_file, readme_file = process_epg_file(input_file, output_file)
    print(f"处理完成！输出文件:")
    print(f"  - XML文件: {xml_file}")
    print(f"  - 压缩文件: {gz_file}")
    print(f"  - README文件: {readme_file}")
