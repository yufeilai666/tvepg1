# unified_epg_generator.py
import os
import sys
import time
import shutil
import tempfile
import subprocess
from xml.etree.ElementTree import Element, SubElement, tostring, parse
from xml.dom import minidom
# from datetime import datetime

def run_epg_script_in_temp_dir(script_path, temp_dir):
    """
    在临时目录中运行EPG脚本
    """
    print(f"正在在临时目录中运行 {script_path}...")
    
    try:
        # 复制脚本到临时目录
        script_name = os.path.basename(script_path)
        temp_script_path = os.path.join(temp_dir, script_name)
        shutil.copy2(script_path, temp_script_path)
        
        # 在临时目录中运行脚本
        process = subprocess.Popen(
            [sys.executable, temp_script_path],
            cwd=temp_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        stdout, stderr = process.communicate(timeout=1800)  # 30分钟超时
        
        if process.returncode != 0:
            print(f"脚本 {script_path} 执行失败，返回码: {process.returncode}")
            if stderr:
                print(f"错误输出: {stderr.decode('utf-8', errors='ignore')}")
            return None
        
        print(f"✓ {script_path} 执行完成")
        
        # 输出脚本的标准输出（如果有）
        if stdout:
            print(f"脚本输出: {stdout.decode('utf-8', errors='ignore')}")
            
        return True
        
    except subprocess.TimeoutExpired:
        print(f"脚本 {script_path} 执行超时")
        process.kill()
        return None
    except Exception as e:
        print(f"运行脚本 {script_path} 时出错: {e}")
        return None

def find_xml_files_in_temp_dir(temp_dir):
    """
    在临时目录中查找XML文件
    """
    xml_files = []
    for filename in os.listdir(temp_dir):
        if filename.endswith('.xml'):
            xml_files.append(os.path.join(temp_dir, filename))
    
    return xml_files

def read_xml_content(xml_file):
    """
    读取XML文件内容
    """
    try:
        with open(xml_file, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"读取XML文件 {xml_file} 失败: {e}")
        return None

def merge_xml_contents(xml_contents):
    """
    合并多个XML内容，保留原结构和顺序
    """
    # 创建新的根元素
    new_root = Element('tv')
    new_root.set('generator-info-name', 'unified-epg-generator')
    new_root.set('generator-info-url', 'https://github.com/yufeilai666/tvepg')
    new_root.set('source-info-name', 'multiple-sources')
    
    # 合并所有XML内容
    for xml_content in xml_contents:
        if xml_content:
            try:
                # 解析XML内容
                root = parse(xml_content).getroot()
                
                # 添加所有子元素到新的根元素
                for child in root:
                    new_root.append(child)
                    
            except Exception as e:
                print(f"解析XML内容失败: {e}")
                continue
    
    return new_root

def prettify_xml(elem):
    """
    美化XML输出
    """
    rough_string = tostring(elem, encoding='utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ", encoding='utf-8')

def discover_epg_scripts():
    """
    自动发现目录中的EPG脚本
    """
    epg_scripts = []
    
    # 查找所有可能的EPG脚本
    for filename in os.listdir('.'):
        if (filename.startswith('get_') and filename.endswith('.py')) or \
           (filename.endswith('_epg.py')):
            epg_scripts.append(filename)
    
    return epg_scripts

def main():
    """
    主函数 - 在临时目录中运行所有EPG脚本并合并结果
    """
    # 自动发现EPG脚本
    scripts = discover_epg_scripts()
    
    if not scripts:
        print("未发现任何EPG脚本")
        return
    
    print("发现的EPG脚本:")
    for script in scripts:
        print(f"  - {script}")
    
    # 检查TMDB API Key
    TMDB_API_KEY = os.environ.get('TMDB_API_KEY')
    if not TMDB_API_KEY:
        print("警告: 未找到TMDB_API_KEY环境变量，部分脚本可能无法获取电影描述信息")
    
    all_xml_contents = []
    
    # 为所有脚本创建一个临时目录
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"\n使用临时目录: {temp_dir}")
        
        # 运行每个脚本
        for script in scripts:
            print(f"\n{'='*50}")
            print(f"处理: {script}")
            print(f"{'='*50}")
            
            # 在临时目录中运行脚本
            if run_epg_script_in_temp_dir(script, temp_dir):
                # 等待一下，确保文件已生成
                time.sleep(2)
                
                # 查找临时目录中的XML文件
                xml_files = find_xml_files_in_temp_dir(temp_dir)
                if xml_files:
                    # 读取第一个XML文件的内容
                    xml_content = read_xml_content(xml_files[0])
                    if xml_content:
                        all_xml_contents.append(xml_content)
                        print(f"✓ 成功从 {script} 获取XML内容")
                    else:
                        print(f"✗ 读取 {xml_files[0]} 失败")
                else:
                    print(f"✗ 未找到 {script} 生成的XML文件")
            else:
                print(f"✗ 运行 {script} 失败")
        
        if not all_xml_contents:
            print("错误: 未能获取任何XML内容")
            return
        
        # 合并所有XML内容
        print(f"\n正在合并 {len(all_xml_contents)} 个XML内容...")
        merged_xml = merge_xml_contents(all_xml_contents)
        
        # 保存到统一的XML文件
        pretty_xml = prettify_xml(merged_xml)
        
        output_file = 'person.xml'
        with open(output_file, 'wb') as f:
            f.write(pretty_xml)
        
        print(f"\n✓ 统一EPG文件已生成: {output_file}")
        
        # 统计节目数量
        programme_count = len(merged_xml.findall('programme'))
        channel_count = len(merged_xml.findall('channel'))
        print(f"   频道数量: {channel_count}")
        print(f"   节目数量: {programme_count}")

if __name__ == "__main__":
    main()