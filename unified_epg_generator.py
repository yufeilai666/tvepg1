#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一EPG生成器 (Unified EPG Generator)

功能描述：
1. 自动发现当前目录中的所有EPG采集脚本（仅匹配 get_*_epg.py 格式）
2. 在临时目录中依次运行这些脚本，避免污染工作目录
3. 收集每个脚本生成的XML内容
4. 将所有XML内容合并到统一的person.xml文件中
5. 保留原始XML的结构和顺序，不做去重处理

使用说明：
1. 将本脚本与各个EPG采集脚本放在同一目录下
2. EPG脚本命名规范：get_*_epg.py
3. 设置环境变量 TMDB_API_KEY（可选，用于获取电影描述）
4. 运行脚本：python unified_epg_generator.py

输出文件：
- person.xml：包含所有频道节目信息的统一XMLTV格式文件

依赖包：
- requests, beautifulsoup4

作者：yufeilai666
版本：1.2
"""

import os
import sys
import time
import shutil
import tempfile
import subprocess
from xml.etree.ElementTree import Element, SubElement, tostring, fromstring
from xml.dom import minidom
from datetime import datetime


def run_epg_script_in_temp_dir(script_path, temp_dir):
    """
    在临时目录中运行单个EPG采集脚本
    
    参数:
        script_path (str): 脚本文件路径
        temp_dir (str): 临时目录路径
        
    返回:
        bool: 脚本是否成功运行
    """
    script_name = os.path.basename(script_path)
    print(f"正在在临时目录中运行 {script_name}...")
    
    try:
        # 复制脚本到临时目录
        temp_script_path = os.path.join(temp_dir, script_name)
        shutil.copy2(script_path, temp_script_path)
        
        # 在临时目录中运行脚本
        process = subprocess.Popen(
            [sys.executable, temp_script_path],
            cwd=temp_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # 设置超时时间为30分钟
        stdout, stderr = process.communicate(timeout=1800)
        
        if process.returncode != 0:
            print(f"脚本 {script_name} 执行失败，返回码: {process.returncode}")
            if stderr:
                stderr_text = stderr.decode('utf-8', errors='ignore')
                print(f"错误输出:\n{stderr_text}")
            return False
        
        print(f"✓ {script_name} 执行完成")
        
        # 输出脚本的标准输出（如果有）
        if stdout:
            stdout_text = stdout.decode('utf-8', errors='ignore')
            print(f"脚本输出:\n{stdout_text}")
            
        return True
        
    except subprocess.TimeoutExpired:
        print(f"脚本 {script_name} 执行超时")
        if 'process' in locals():
            process.kill()
        return False
    except Exception as e:
        print(f"运行脚本 {script_name} 时出错: {e}")
        return False


def find_xml_files_in_temp_dir(temp_dir):
    """
    在临时目录中查找XML文件
    
    参数:
        temp_dir (str): 临时目录路径
        
    返回:
        list: XML文件路径列表
    """
    xml_files = []
    for filename in os.listdir(temp_dir):
        if filename.endswith('.xml'):
            xml_files.append(os.path.join(temp_dir, filename))
    
    return xml_files


def read_xml_content(xml_file):
    """
    读取XML文件内容
    
    参数:
        xml_file (str): XML文件路径
        
    返回:
        str: XML文件内容，失败时返回None
    """
    try:
        with open(xml_file, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"读取XML文件失败: {e}")
        return None


def merge_xml_contents(xml_contents):
    """
    合并多个XML内容到一个统一的XML结构中
    
    参数:
        xml_contents (list): XML内容字符串列表
        
    返回:
        Element: 合并后的XML根元素
    """
    # 创建新的根元素
    new_root = Element('tv')
    new_root.set('generator-info-name', 'unified-epg-generator')
    new_root.set('generator-info-url', 'https://github.com/yufeilai666/tvepg')
    new_root.set('source-info-name', 'multiple-sources')
    new_root.set('created', datetime.now().strftime("%Y%m%d%H%M%S"))
    
    # 合并所有XML内容
    for i, xml_content in enumerate(xml_contents):
        if xml_content:
            try:
                # 使用fromstring从字符串解析XML，而不是parse从文件解析
                root = fromstring(xml_content)
                
                # 添加所有子元素到新的根元素
                for child in root:
                    new_root.append(child)
                    
            except Exception as e:
                print(f"解析第 {i+1} 个XML内容失败: {e}")
                continue
    
    return new_root


def prettify_xml(elem):
    """
    美化XML输出，添加缩进和格式化
    
    参数:
        elem (Element): XML元素
        
    返回:
        bytes: 格式化后的XML字节内容
    """
    rough_string = tostring(elem, encoding='utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ", encoding='utf-8')


def discover_epg_scripts():
    """
    自动发现当前目录中的EPG采集脚本
    
    返回:
        list: EPG脚本文件名列表
    """
    epg_scripts = []
    
    # 只匹配 get_*_epg.py 格式的脚本
    for filename in os.listdir('.'):
        if filename.startswith('get_') and filename.endswith('_epg.py'):
            epg_scripts.append(filename)
    
    return epg_scripts


def main():
    """
    主函数 - 协调整个EPG生成流程
    
    流程:
    1. 发现EPG脚本
    2. 在临时目录中运行每个脚本
    3. 收集生成的XML内容
    4. 合并所有XML内容
    5. 生成统一的person.xml文件
    """
    print("=" * 60)
    print("统一EPG生成器启动")
    print("=" * 60)
    
    # 自动发现EPG脚本
    scripts = discover_epg_scripts()
    
    if not scripts:
        print("未发现任何EPG脚本")
        print("请确保脚本命名符合以下模式：get_*_epg.py")
        return
    
    print("发现的EPG脚本:")
    for script in scripts:
        print(f"  - {script}")
    
    # 检查TMDB API Key
    TMDB_API_KEY = os.environ.get('TMDB_API_KEY')
    if not TMDB_API_KEY:
        print("警告: 未找到TMDB_API_KEY环境变量")
        print("部分脚本可能无法获取电影描述信息")
    
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
                        print(f"✗ 读取 {script} 生成的XML文件失败")
                else:
                    print(f"✗ 未找到 {script} 生成的XML文件")
            else:
                print(f"✗ 运行 {script} 失败")
                print("注意: 单个脚本失败不会影响其他脚本执行")
        
        if not all_xml_contents:
            print("错误: 未能获取任何XML内容")
            print("请检查各个EPG脚本是否正确运行")
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
        
        print("\n处理完成！")


if __name__ == "__main__":
    main()