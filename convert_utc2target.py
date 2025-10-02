from datetime import datetime, timedelta
from lxml import etree
import gzip
import os
import re
import sys
from io import BytesIO

def convert_utc2target(input_file, output_file, target_timezone, direct_set_timezone=False):
    """
    将XML文件中+0000时区的节目时间转换为指定时区的时间
    
    功能说明：
    1. 解析输入的XML文件（支持普通XML和gzip压缩的XML）
    2. 查找所有<programme>元素
    3. 仅处理包含'+0000'时区标记的start和stop属性
    4. 将UTC时间转换为目标时区时间或直接替换时区
    5. 保存修改后的XML文件
    
    参数：
    input_file (str): 输入的XML文件路径
    output_file (str): 输出的XML文件路径
    target_timezone (str): 目标时区，格式如"UTC+8"或"UTC-5"
    direct_set_timezone (bool): 是否直接替换时区而不转换时间
    """
    # 获取当前工作目录和文件的绝对路径
    current_dir = os.getcwd()
    abs_input_path = os.path.abspath(input_file)
    
    print(f"当前工作目录: {current_dir}")
    print(f"输入文件绝对路径: {abs_input_path}")
    
    # 检查输入文件是否存在
    if not os.path.exists(input_file):
        print(f"错误: 输入文件 '{input_file}' 不存在")
        print(f"绝对路径: {abs_input_path}")
        
        # 列出当前目录下的文件，帮助用户诊断问题
        print("\n当前目录下的文件:")
        for file in os.listdir(current_dir):
            if file.endswith('.xml') or file.endswith('.gz'):
                print(f"  - {file}")
        
        return False
    
    # 检查文件是否可读
    if not os.access(input_file, os.R_OK):
        print(f"错误: 没有读取文件 '{input_file}' 的权限")
        return False
    
    # 解析目标时区
    if target_timezone.upper().startswith("UTC+"):
        hours_offset = int(target_timezone[4:])
    elif target_timezone.upper().startswith("UTC-"):
        hours_offset = -int(target_timezone[4:])
    else:
        print(f"错误: 不支持的时区格式: {target_timezone}")
        return False
    
    # 生成目标时区标记
    tz_sign = "+" if hours_offset >= 0 else "-"
    tz_hours = abs(hours_offset)
    target_tz_str = f"{tz_sign}{tz_hours:02d}00"
    
    # 检查输入文件是否为gzip压缩
    is_gzipped = input_file.endswith('.gz')
    
    # 创建XML解析器并保留空白格式
    parser = etree.XMLParser(remove_blank_text=True)
    
    try:
        # 读取并修复XML文件中的实体引用错误
        if is_gzipped:
            # 处理gzip压缩文件
            with gzip.open(input_file, 'rb') as f:
                content = f.read()
        else:
            # 处理普通XML文件
            with open(input_file, 'rb') as f:
                content = f.read()
    except Exception as e:
        print(f"错误: 无法读取文件 '{input_file}': {e}")
        print(f"文件大小: {os.path.getsize(input_file) if os.path.exists(input_file) else 'N/A'} 字节")
        return False
    
    # 将内容解码为字符串并修复XML
    xml_content = content.decode('utf-8')
    
    # 记录修复信息
    repair_info = []
    
    # 按行分割内容以便记录行号
    lines = xml_content.split('\n')
    for i, line in enumerate(lines, 1):
        # 查找未转义的&符号
        matches = list(re.finditer(r'&(?!amp;|lt;|gt;|quot;|apos;)', line))
        if matches:
            for match in matches:
                start_pos = match.start()
                context = line[max(0, start_pos-10):min(len(line), start_pos+10)]
                repair_info.append(f"第{i}行第{start_pos+1}列: '{context}'")
    
    # 修复未转义的&符号
    xml_content = re.sub(r'&(?!amp;|lt;|gt;|quot;|apos;)', '&amp;', xml_content)
    
    # 打印修复信息
    if repair_info:
        print(f"在文件 {input_file} 中发现并修复了 {len(repair_info)} 处未转义的&符号:")
        for info in repair_info:
            print(f"  - {info}")
    else:
        print(f"文件 {input_file} 中没有发现需要修复的&符号")
    
    # 将修复后的内容重新编码为字节串
    xml_bytes = xml_content.encode('utf-8')
    
    # 使用BytesIO创建文件对象
    xml_file = BytesIO(xml_bytes)
    
    try:
        # 解析XML内容
        tree = etree.parse(xml_file, parser)
        root = tree.getroot()
    except Exception as e:
        print(f"错误: 无法解析XML文件 '{input_file}': {e}")
        return False
    
    # 记录时间转换信息
    time_conversions = []
    
    # 遍历所有programme元素
    for programme in root.findall('.//programme'):
        for attr in ['start', 'stop']:
            value = programme.get(attr)
            if not value:
                continue
            
            # 分割时间值和时区
            parts = value.split()
            if len(parts) != 2:
                continue
                
            time_str, tz = parts
            
            # 只处理+0000时区
            if tz == '+0000':
                if direct_set_timezone:
                    # 直接替换时区而不转换时间
                    programme.set(attr, f"{time_str} {target_tz_str}")
                    time_conversions.append(f"将 {attr} 从 {value} 替换为 {time_str} {target_tz_str}")
                else:
                    # 解析时间
                    dt = datetime.strptime(time_str, '%Y%m%d%H%M%S')
                    # 转换为目标时区
                    dt_target = dt + timedelta(hours=hours_offset)
                    # 格式化为新时间字符串
                    new_time_str = dt_target.strftime('%Y%m%d%H%M%S')
                    # 更新属性值
                    programme.set(attr, f"{new_time_str} {target_tz_str}")
                    
                    # 记录转换信息
                    time_conversions.append(f"将 {attr} 从 {value} 转换为 {new_time_str} {target_tz_str}")
    
    # 打印时间转换信息
    if time_conversions:
        operation_type = "直接替换时区" if direct_set_timezone else "转换时间"
        print(f"在文件 {input_file} 中成功处理了 {len(time_conversions)} 个时间 ({operation_type}):")
        for info in time_conversions[:10]:  # 只显示前10个转换，避免输出过多
            print(f"  - {info}")
        if len(time_conversions) > 10:
            print(f"  - ... 还有 {len(time_conversions)-10} 个处理未显示")
    else:
        operation_type = "直接替换时区" if direct_set_timezone else "转换时间"
        print(f"文件 {input_file} 中没有需要{operation_type}的时间")
    
    try:
        # 确保输出目录存在
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # 保存修改后的XML
        if output_file.endswith('.gz'):
            # 如果需要输出为gzip压缩文件
            with gzip.open(output_file, 'wb') as f:
                tree.write(f, encoding='UTF-8', 
                           xml_declaration=True, 
                           pretty_print=True, 
                           doctype=tree.docinfo.doctype)
        else:
            # 输出为普通XML文件
            tree.write(output_file, encoding='UTF-8', 
                       xml_declaration=True, 
                       pretty_print=True, 
                       doctype=tree.docinfo.doctype)
        print(f"成功保存文件: {output_file}")
        return True
    except Exception as e:
        print(f"错误: 无法保存文件 '{output_file}': {e}")
        return False

def process_sources(sources):
    """
    处理多个源文件
    
    参数：
    sources (list): 包含字典的列表，每个字典包含input_file, output_file, target_timezone和direct_set_timezone
    """
    success_count = 0
    total_count = len(sources)
    
    for source in sources:
        input_file = source["input_file"]
        output_file = source["output_file"]
        target_timezone = source["target_timezone"]
        direct_set_timezone = source.get("direct_set_timezone", False)
        
        print(f"\n{'='*60}")
        print(f"处理文件: {input_file} -> {output_file} ({target_timezone}, 直接替换时区: {direct_set_timezone})")
        if convert_utc2target(input_file, output_file, target_timezone, direct_set_timezone):
            success_count += 1
        print(f"{'='*60}")
    
    print(f"\n处理总结: 成功处理 {success_count}/{total_count} 个文件")
    return success_count == total_count

if __name__ == "__main__":
    # 定义要处理的源文件列表
    sources = [
        {
            "input_file": "epgmytvsuper_new.xml",
            "output_file": "epgmytvsuper_new_cst.xml",
            "target_timezone": "UTC+8",
            "direct_set_timezone": False
        },
        {
            "input_file": "epgastro.xml",
            "output_file": "epgastro_mst.xml",
            "target_timezone": "UTC+8",
            "direct_set_timezone": False
        },
        {
            "input_file": "epgsooka.xml",
            "output_file": "epgsooka_mst.xml",
            "target_timezone": "UTC+8",
            "direct_set_timezone": False
        },
        {
            "input_file": "epg4gtv2.xml",
            "output_file": "epg4gtv2_cst.xml",
            "target_timezone": "UTC+8",
            "direct_set_timezone": False
        }
    ]
    
    # 处理所有源文件
    success = process_sources(sources)
    
    # 根据处理结果返回适当的退出代码
    sys.exit(0 if success else 1)