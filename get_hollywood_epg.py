import re
import os
import time
import random
from datetime import datetime, timedelta
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom
import requests
from bs4 import BeautifulSoup

# TMDB配置
TMDB_API_KEY = os.environ.get('TMDB_API_KEY')

def clean_movie_title(title):
    """
    清理电影标题，移除括号及其内容，用于TMDB搜索
    """
    # 移除中文括号及其内容
    cleaned_title = re.sub(r'（[^）]*）', '', title)
    # 移除英文括号及其内容
    cleaned_title = re.sub(r'\([^)]*\)', '', cleaned_title)
    # 移除方括号及其内容
    cleaned_title = re.sub(r'\[[^\]]*\]', '', cleaned_title)
    # 移除多余空格
    cleaned_title = cleaned_title.strip()
    
    print(f"清理标题: '{title}' -> '{cleaned_title}'")
    return cleaned_title

def format_description(description):
    """
    格式化描述文本：处理各种换行符，按段落处理，去除空白行，每个段首添加两个全角空格
    """
    if not description:
        return ""
    
    # 1. 统一换行符：将 \r\n、\r 和多个连续换行符统一为单个 \n
    description = re.sub(r'\r\n|\r|\n+', '\n', description)
    
    # 2. 按换行符分割成段落
    paragraphs = description.split('\n')
    
    # 3. 清理每个段落：移除首尾空白，过滤空段落
    cleaned_paragraphs = []
    for para in paragraphs:
        para = para.strip()
        if para:  # 只保留非空段落
            # 4. 在每个段落开始添加两个全角空格
            para = '　　' + para
            cleaned_paragraphs.append(para)
    
    # 5. 用换行符连接所有段落
    formatted_description = '\n'.join(cleaned_paragraphs)
    
    return formatted_description

def search_tmdb_movie_direct(original_title):
    """
    直接使用TMDB API搜索电影信息，避免第三方库的问题
    """
    if not TMDB_API_KEY:
        return None
    
    # 清理标题 - 用于搜索
    clean_title = clean_movie_title(original_title)
    
    # 如果清理后标题为空，使用原始标题
    if not clean_title:
        clean_title = original_title
    
    # 地区搜索顺序
    regions = ['zh-TW', 'zh-HK', 'zh-CN']
    
    for region in regions:
        try:
            # 构建搜索URL
            search_url = "https://api.themoviedb.org/3/search/movie"
            params = {
                'api_key': TMDB_API_KEY,
                'language': region,
                'query': clean_title,  # 使用净化后的标题进行搜索
                'page': 1
            }
            
            print(f"在 {region} 地区搜索电影: '{clean_title}' (原始标题: '{original_title}')")
            
            # 发送搜索请求
            response = requests.get(search_url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                
                if results:
                    # 取第一个结果
                    movie_id = results[0]['id']
                    
                    # 获取电影详情
                    details_url = f"https://api.themoviedb.org/3/movie/{movie_id}"
                    details_params = {
                        'api_key': TMDB_API_KEY,
                        'language': region
                    }
                    
                    details_response = requests.get(details_url, params=details_params, timeout=10)
                    
                    if details_response.status_code == 200:
                        movie_details = details_response.json()
                        
                        # 检查是否有描述信息
                        overview = movie_details.get('overview', '')
                        if overview:
                            print(f"在 {region} 找到电影信息: {movie_details.get('title', '未知标题')}")
                            
                            # 使用改进的格式化函数处理TMDB的描述信息
                            formatted_overview = format_description(overview)
                            
                            return {
                                'title': original_title,  # 使用原始标题显示
                                'overview': formatted_overview,
                                'release_date': movie_details.get('release_date', ''),
                                'vote_average': movie_details.get('vote_average', 0),
                                'id': movie_id
                            }
                        else:
                            print(f"在 {region} 找到电影但无描述信息，继续搜索其他地区")
                    else:
                        print(f"获取电影详情失败: {details_response.status_code}")
                else:
                    print(f"在 {region} 未找到电影: {clean_title}")
            else:
                print(f"TMDB搜索请求失败: {response.status_code}")
            
            # 避免请求过快
            time.sleep(random.uniform(0.5, 1.5))
            
        except Exception as e:
            print(f"TMDB搜索错误 ({region}): {e}")
            continue
    
    print(f"在所有地区均未找到电影描述信息: {clean_title}")
    return None

def parse_hollywood_schedule_html(html_content):
    """
    从Hollywood频道HTML内容中解析节目信息
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    schedule_data = []
    
    # 查找所有包含日期的div
    date_divs = soup.find_all('div', class_='wixui-rich-text')
    
    # 收集所有日期和对应的节目列表
    date_program_map = {}
    current_date = None
    
    for div in date_divs:
        h6_tag = div.find('h6', class_='font_6')
        if not h6_tag:
            continue
            
        text_content = h6_tag.get_text(strip=True)
        
        # 检查是否为日期行 (格式: MM/DD 星期X)
        date_match = re.search(r'(\d{1,2}/\d{1,2})\s+(星期[一二三四五六日])', text_content)
        if date_match:
            current_date = date_match.group(1)  # 获取 MM/DD 格式的日期
            print(f"找到日期: {current_date}")
            continue
        
        # 检查是否为节目列表 (包含时间格式 XX:XX)
        if re.search(r'\d{1,2}:\d{2}', text_content) and current_date:
            # 获取所有文本内容，包括<br>分隔的节目
            full_text = h6_tag.get_text()
            
            # 按行分割节目
            lines = full_text.split('\n')
            
            # 解析节目列表
            programs = []
            current_program_date = None
            has_crossed_midnight = False
            
            for i, line in enumerate(lines):
                # 清理行，移除特殊字符
                line = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', line.strip())
                if not line:
                    continue
                    
                # 匹配时间、标题和分级
                match = re.match(r'(\d{1,2}:\d{2})\s*\&nbsp;\s*\&nbsp;\s*([^(]+)(?:\(([^)]+)\))?', line)
                if not match:
                    # 尝试其他可能的时间格式
                    match = re.match(r'(\d{1,2}:\d{2})\s+([^(]+)(?:\(([^)]+)\))?', line)
                
                if match:
                    time_str = match.group(1)
                    title = match.group(2).strip()
                    rating = match.group(3) if match.group(3) else ''
                    
                    # 构建完整的原始标题（包含分级信息）
                    original_title = f"{title}({rating})" if rating else title
                    
                    # 确定节目日期
                    if i == 0:
                        # 第一个节目属于当前日期
                        month, day = current_date.split('/')
                        current_year = datetime.now().year
                        current_program_date = datetime(current_year, int(month), int(day))
                    else:
                        # 检测是否跨天
                        prev_line = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', lines[i-1].strip())
                        if prev_line:
                            prev_match = re.match(r'(\d{1,2}:\d{2})', prev_line)
                            if prev_match:
                                prev_time_str = prev_match.group(1)
                                try:
                                    prev_hour = int(prev_time_str.split(':')[0])
                                    current_hour = int(time_str.split(':')[0])
                                    
                                    # 如果当前时间小于前一个时间，说明跨天了
                                    if current_hour < prev_hour and not has_crossed_midnight:
                                        has_crossed_midnight = True
                                        current_program_date = current_program_date + timedelta(days=1)
                                except ValueError:
                                    # 如果时间解析失败，跳过跨天检测
                                    pass
                    
                    program_info = {
                        'time': time_str,
                        'title': original_title,
                        'rating': rating,
                        'link': None,
                        'date_obj': current_program_date
                    }
                    programs.append(program_info)
                    print(f"  找到节目: {current_program_date.strftime('%m/%d')} {time_str} - {original_title}")
            
            # 将节目列表添加到对应的日期
            if current_date not in date_program_map:
                date_program_map[current_date] = []
            
            date_program_map[current_date].extend(programs)
    
    # 将节目数据转换为需要的格式
    for date_str, programs in date_program_map.items():
        # 创建日期对象
        month, day = date_str.split('/')
        current_year = datetime.now().year
        date_obj = datetime(current_year, int(month), int(day))
        
        schedule_data.append({
            'date': date_str,
            'date_obj': date_obj,
            'programs': programs
        })
    
    print(f"成功解析 {len(schedule_data)} 天的节目数据")
    
    # 重新组织数据，按实际日期分组
    reorganized_data = reorganize_schedule_by_date(schedule_data)
    
    return reorganized_data

def reorganize_schedule_by_date(schedule_data):
    """
    重新组织节目数据，按实际日期分组
    """
    date_dict = {}
    
    for day_info in schedule_data:
        for program in day_info['programs']:
            date_key = program['date_obj'].strftime('%m/%d')
            
            if date_key not in date_dict:
                date_dict[date_key] = {
                    'date': date_key,
                    'date_obj': program['date_obj'],
                    'programs': []
                }
            
            # 复制节目信息，但移除date_obj字段
            program_copy = program.copy()
            program_copy.pop('date_obj', None)
            date_dict[date_key]['programs'].append(program_copy)
    
    # 按日期排序
    sorted_dates = sorted(date_dict.keys(), key=lambda x: datetime.strptime(x, '%m/%d'))
    reorganized_data = [date_dict[date] for date in sorted_dates]
    
    # 打印重新组织后的数据
    for day in reorganized_data:
        print(f"日期: {day['date']}, 节目数量: {len(day['programs'])}")
        for program in day['programs']:
            print(f"  - {program['time']} {program['title']}")
    
    return reorganized_data

def generate_xmltv_epg(schedule_data):
    """
    生成XMLTV格式的EPG节目单
    """
    # 创建根元素
    root = Element('tv')
    root.set('generator-info-name', 'yufeilai666')
    root.set('generator-info-url', 'https://github.com/yufeilai666/tvepg')
    root.set('source-info-name', 'hollywood.com.tw')
    root.set('source-info-url', 'https://www.hollywood.com.tw')
    
    # 添加频道信息
    channel_elem = SubElement(root, 'channel', id='HOLLYWOOD')
    display_name = SubElement(channel_elem, 'display-name')
    display_name.text = '好莱坞电影台'
    display_name.set('lang', 'zh')
    
    # 缓存电影信息，避免重复查询
    movie_cache = {}
    
    # 只处理前7天的数据
    days_to_process = min(7, len(schedule_data))
    
    # 处理前7天的节目
    for day_idx in range(days_to_process):
        day_info = schedule_data[day_idx]
        date_parts = day_info['date'].split('/')
        if len(date_parts) != 2:
            continue
            
        month, day = date_parts
        programs = day_info['programs']
        
        # 为每个节目计算结束时间
        for i in range(len(programs)):
            program = programs[i]
            
            # 解析开始时间
            start_time_parts = program['time'].split(':')
            if len(start_time_parts) != 2:
                continue
                
            start_hour, start_minute = start_time_parts
            
            # 创建开始时间
            current_year = datetime.now().year
            start_dt = datetime(current_year, int(month), int(day), int(start_hour), int(start_minute))
            start_time = start_dt.strftime("%Y%m%d%H%M00")
            
            # 计算结束时间
            if i < len(programs) - 1:
                # 下一个节目的开始时间作为当前节目的结束时间
                next_program = programs[i + 1]
                next_time_parts = next_program['time'].split(':')
                if len(next_time_parts) == 2:
                    next_hour, next_minute = next_time_parts
                    end_dt = datetime(current_year, int(month), int(day), int(next_hour), int(next_minute))
                else:
                    # 如果无法解析下一个节目时间，使用默认2小时
                    end_dt = start_dt + timedelta(hours=2)
            else:
                # 当天最后一个节目
                if day_idx < len(schedule_data) - 1:
                    # 使用下一天的第一个节目的开始时间
                    next_day_info = schedule_data[day_idx + 1]
                    if next_day_info['programs']:
                        next_day_program = next_day_info['programs'][0]
                        next_time_parts = next_day_program['time'].split(':')
                        if len(next_time_parts) == 2:
                            next_day_date_parts = next_day_info['date'].split('/')
                            if len(next_day_date_parts) == 2:
                                next_month, next_day = next_day_date_parts
                                next_hour, next_minute = next_time_parts
                                end_dt = datetime(current_year, int(next_month), int(next_day), int(next_hour), int(next_minute))
                            else:
                                # 使用第二天的0点
                                end_dt = start_dt + timedelta(days=1)
                        else:
                            # 使用第二天的0点
                            end_dt = start_dt + timedelta(days=1)
                    else:
                        # 使用第二天的0点
                        end_dt = start_dt + timedelta(days=1)
                else:
                    # 最后一天，使用第二天的0点
                    end_dt = start_dt + timedelta(days=1)
            
            end_time = end_dt.strftime("%Y%m%d%H%M00")
            
            # 创建programme元素
            programme_elem = SubElement(root, 'programme')
            programme_elem.set('start', start_time + ' +0800')  # 台北时区
            programme_elem.set('stop', end_time + ' +0800')
            programme_elem.set('channel', 'HOLLYWOOD')
            
            # 添加标题 - 使用原始标题（包含分级信息）
            title_elem = SubElement(programme_elem, 'title')
            title_elem.text = program['title']  # 这里使用包含分级的完整标题
            title_elem.set('lang', 'zh')
            
            # 添加描述 - 直接从TMDB API获取
            desc_text = ""
            
            # 检查缓存中是否有电影信息
            # 使用净化后的标题作为缓存键
            clean_title = clean_movie_title(program['title'])
            cache_key = clean_title
            
            if cache_key in movie_cache:
                movie_info = movie_cache[cache_key]
                desc_text = movie_info.get('description', '')
                print(f"使用缓存中的描述信息: {program['title']}")
            else:
                # 直接从TMDB获取描述，使用净化后的标题进行搜索
                if TMDB_API_KEY:
                    movie_info = search_tmdb_movie_direct(program['title'])  # 这个函数内部会净化标题
                    if movie_info and movie_info.get('overview'):
                        desc_text = movie_info['overview']
                        # 缓存结果，使用净化后的标题作为键
                        movie_cache[cache_key] = {'description': desc_text, 'source': 'tmdb'}
                else:
                    print("未设置TMDB_API_KEY，跳过TMDB搜索")
            
            desc_elem = SubElement(programme_elem, 'desc')
            desc_elem.text = desc_text
            desc_elem.set('lang', 'zh')
            
            # 添加分类
            category_elem = SubElement(programme_elem, 'category')
            category_elem.text = '电影'
            category_elem.set('lang', 'zh')
            
            # 添加分级信息
            if program['rating']:
                rating_elem = SubElement(programme_elem, 'rating')
                rating_system = SubElement(rating_elem, 'system')
                rating_system.text = 'TW'
                rating_value = SubElement(rating_elem, 'value')
                rating_value.text = program['rating']
    
    return root

def prettify_xml(elem):
    """
    美化XML输出
    """
    rough_string = tostring(elem, encoding='utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ", encoding='utf-8')

def main():
    """
    主函数 - 从Hollywood网站获取数据并生成XMLTV EPG
    """
    try:
        # 获取TMDB API Key
        if not TMDB_API_KEY:
            print("警告: 未找到TMDB_API_KEY环境变量，将无法获取电影描述信息")
        
        # 获取网页内容
        url = "https://www.hollywood.com.tw/schedule"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        print("正在获取Hollywood节目表数据...")
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        
        if response.status_code == 200:
            # 解析HTML
            schedule_data = parse_hollywood_schedule_html(response.text)
            
            if schedule_data:
                # 生成XMLTV EPG
                xml_root = generate_xmltv_epg(schedule_data)
                
                # 美化XML并保存
                pretty_xml = prettify_xml(xml_root)
                
                # 保存到文件
                with open('hollywood_epg.xml', 'wb') as f:
                    f.write(pretty_xml)
                
                print("Hollywood EPG文件已生成: hollywood_epg.xml")
            else:
                print("未解析到节目数据")
        else:
            print(f"获取网页失败，状态码: {response.status_code}")
            
    except Exception as e:
        print(f"发生错误: {e}")

if __name__ == "__main__":
    main()