from datetime import datetime, timedelta
from lxml import etree

def convert_utc2cst(input_file, output_file):
    """
    将XML文件中+0000时区的节目时间转换为+0800时区（北京时间）
    
    功能说明：
    1. 解析输入的XML文件
    2. 查找所有<programme>元素
    3. 仅处理包含'+0000'时区标记的start和stop属性
    4. 将UTC时间转换为北京时间（UTC+8）
    5. 保存修改后的XML文件
    
    参数：
    input_file (str): 输入的XML文件路径
    output_file (str): 输出的XML文件路径
    
    处理逻辑：
    - 使用lxml库解析XML并保留原始格式
    - 仅转换时区标记为'+0000'的时间
    - 时间转换：原始时间 + 8小时 = 北京时间
    - 保持其他所有内容和结构不变
    - 输出文件包含XML声明和原始DOCTYPE
    
    示例转换：
    输入：20250816160000 +0000
    输出：20250817000000 +0800
    """
    # 创建XML解析器并保留空白格式
    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(input_file, parser)
    root = tree.getroot()
    
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
                # 解析时间
                dt = datetime.strptime(time_str, '%Y%m%d%H%M%S')
                # 转换为UTC+8
                dt_cst = dt + timedelta(hours=8)
                # 格式化为新时间字符串
                new_time_str = dt_cst.strftime('%Y%m%d%H%M%S')
                # 更新属性值
                programme.set(attr, f"{new_time_str} +0800")
    
    # 保存修改后的XML
    tree.write(output_file, encoding='UTF-8', 
               xml_declaration=True, 
               pretty_print=True, 
               doctype='<!DOCTYPE tv SYSTEM "http://api.torrent-tv.ru/xmltv.dtd">')

if __name__ == "__main__":
    input_file = "epgziyong.xml"
    out_file = "epgziyong_cst.xml"
    convert_utc2cst(input_file, out_file)
