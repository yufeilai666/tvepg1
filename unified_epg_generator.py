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

作者：GitHub Action
版本：1.5
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
        
        # 设置超时时间为5分钟
        stdout, stderr = process.communicate(timeout=300)
        
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


def analyze_xml_content(xml_content, script_name):
    """
    分析XML内容，统计频道和节目数量
    
    参数:
        xml_content (str): XML内容
        script_name (str): 脚本名称
        
    返回:
        dict: 包含频道和节目统计信息的字典
    """
    try:
        root = fromstring(xml_content)
        
        # 统计频道和节目
        channels = root.findall('channel')
        programmes = root.findall('programme')
        
        # 打印频道详情
        print(f"\n{script_name} 生成的XML内容分析:")
        print(f"  频道数量: {len(channels)}")
        for channel in channels:
            channel_id = channel.get('id', '未知ID')
            display_name_elem = channel.find('display-name')
            display_name = display_name_elem.text if display_name_elem is not None else '未知名称'
            print(f"    - 频道ID: {channel_id}, 名称: {display_name}")
        
        print(f"  节目数量: {len(programmes)}")
        
        # 打印节目中的频道引用
        programme_channels = set()
        for programme in programmes:
            channel_ref = programme.get('channel', '未知频道')
            programme_channels.add(channel_ref)
            if len(programme_channels) > 5:  # 限制输出数量
                break
        
        print(f"  节目中引用的频道: {list(programme_channels)[:5]}...")
        
        return {
            'channels': channels,
            'programmes': programmes,
            'channel_count': len(channels),
            'programme_count': len(programmes),
            'root': root
        }
    except Exception as e:
        print(f"分析 {script_name} 的XML内容失败: {e}")
        return None


def merge_xml_contents(xml_contents, script_names):
    """
    合并多个XML内容到一个统一的XML结构中
    
    参数:
        xml_contents (list): XML内容字符串列表
        script_names (list): 对应的脚本名称列表
        
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
    total_channels = 0
    total_programmes = 0
    
    for i, (xml_content, script_name) in enumerate(zip(xml_contents, script_names)):
        if xml_content:
            try:
                # 分析XML内容
                analysis = analyze_xml_content(xml_content, script_name)
                if analysis:
                    total_channels += analysis['channel_count']
                    total_programmes += analysis['programme_count']
                    
                    # 添加所有子元素到新的根元素
                    for child in analysis['root']:
                        new_root.append(child)
                else:
                    print(f"警告: 无法分析 {script_name} 的XML内容")
                    
            except Exception as e:
                print(f"解析第 {i+1} 个XML内容失败: {e}")
                continue
    
    print(f"\n合并统计:")
    print(f"  总频道数量: {total_channels}")
    print(f"  总节目数量: {total_programmes}")
    
    return new_root


def custom_prettify_xml(elem):
    """
    自定义美化XML输出，避免minidom添加额外空行
    
    参数:
        elem (Element): XML元素
        
    返回:
        bytes: 格式化后的XML字节内容
    """
    # 使用tostring获取XML内容，不添加额外格式
    rough_string = tostring(elem, encoding='utf-8')
    
    # 使用minidom解析
    reparsed = minidom.parseString(rough_string)
    
    # 获取美化后的XML，但minidom会添加额外空行
    pretty_xml = reparsed.toprettyxml(indent="  ", encoding='utf-8')
    
    # 解码为字符串，处理多余空行
    xml_str = pretty_xml.decode('utf-8')
    
    # 移除多余空行 - 保留标签间的缩进但移除空行
    lines = xml_str.split('\n')
    cleaned_lines = []
    
    for line in lines:
        # 保留非空行，或者只包含空格但有关键内容的行
        stripped = line.strip()
        if stripped or line.endswith('>') or line.lstrip().startswith('<'):
            cleaned_lines.append(line)
    
    # 重新组合
    cleaned_xml = '\n'.join(cleaned_lines)
    
    return cleaned_xml.encode('utf-8')


def prettify_xml(elem):
    """
    美化XML输出，添加缩进和格式化
    
    参数:
        elem (Element): XML元素
        
    返回:
        bytes: 格式化后的XML字节内容
    """
    return custom_prettify_xml(elem)


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


def save_debug_xml(xml_content, filename):
    """
    保存XML内容到调试文件
    
    参数:
        xml_content (str): XML内容
        filename (str): 文件名
    """
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(xml_content)
        print(f"已保存调试文件: {filename}")
    except Exception as e:
        print(f"保存调试文件失败: {e}")


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
    all_script_names = []
    
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
                        all_script_names.append(script)
                        print(f"✓ 成功从 {script} 获取XML内容")
                        
                        # 保存原始XML文件用于调试
                        debug_filename = f"debug_{script.replace('.py', '')}.xml"
                        save_debug_xml(xml_content, debug_filename)
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
        merged_xml = merge_xml_contents(all_xml_contents, all_script_names)
        
        # 保存到统一的XML文件
        pretty_xml = prettify_xml(merged_xml)
        
        output_file = 'person.xml'
        with open(output_file, 'wb') as f:
            f.write(pretty_xml)
        
        print(f"\n✓ 统一EPG文件已生成: {output_file}")
        
        # 统计最终合并后的节目数量
        programme_count = len(merged_xml.findall('programme'))
        channel_count = len(merged_xml.findall('channel'))
        print(f"   最终频道数量: {channel_count}")
        print(f"   最终节目数量: {programme_count}")
        
        # 打印最终合并后的频道详情
        print("\n最终合并后的频道详情:")
        for channel in merged_xml.findall('channel'):
            channel_id = channel.get('id', '未知ID')
            display_name_elem = channel.find('display-name')
            display_name = display_name_elem.text if display_name_elem is not None else '未知名称'
            print(f"  - 频道ID: {channel_id}, 名称: {display_name}")
        
        # 检查节目中的频道引用
        programme_channels = set()
        for programme in merged_xml.findall('programme'):
            channel_ref = programme.get('channel', '未知频道')
            programme_channels.add(channel_ref)
        
        print(f"\n节目中引用的所有频道ID: {list(programme_channels)}")
        
        # 检查是否有节目引用了不存在的频道
        defined_channels = {channel.get('id') for channel in merged_xml.findall('channel')}
        undefined_channels = programme_channels - defined_channels
        if undefined_channels:
            print(f"警告: 以下频道在节目中被引用但未定义: {list(undefined_channels)}")
        
        print("\n处理完成！")


if __name__ == "__main__":
    main()