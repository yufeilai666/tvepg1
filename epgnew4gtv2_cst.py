from lxml import etree
from collections import defaultdict
import os

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

if __name__ == "__main__":
    # 默认输入输出文件配置
    input_file = "epg4gtv2_cst.xml"
    output_file = "epgnew4gtv2_cst.xml"
    
    # 检查输入文件是否存在
    if not os.path.exists(input_file):
        print(f"错误：输入文件 '{input_file}' 不存在")
        exit(1)
    
    # 处理EPG文件
    process_epg_file(input_file, output_file)
    print(f"处理完成！输出文件: {output_file}")