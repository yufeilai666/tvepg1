<?php
header('Content-Type: text/plain; charset=UTF-8');
ini_set("max_execution_time", "30000000");
ini_set('date.timezone', 'Asia/Shanghai');

// 定义文件路径 - 使用当前目录
$fp = __DIR__ . "/epgkai.xml";

// 日期变量定义
$dt1 = date('Ymd');
$dt2 = date('Ymd', strtotime('+1 day'));
$dt21 = date('Ymd', strtotime('+2 day'));
$dt22 = date('Ymd', strtotime('-1 day'));
$dt3 = date('Ymd', strtotime('+7 day'));
$dt11 = date('Y-m-d');
$dt12 = date('Y-m-d', strtotime('+1 day'));
$dt13 = date('Y-m-d', strtotime('+1 day'));
$targetDates = [$dt11, $dt12]; // 统一目标日期数组

$w1 = date("w");//当前第几周
if ($w1 < '1') {$w1 = 7;}
$w2 = $w1 + 1;

// 工具函数
function compress_html($string) {
    $string = str_replace(["\r", "\n", "\t"], '', $string);
    return $string;
}

function escape($str) { 
    preg_match_all("/[\x80-\xff].|[\x01-\x7f]+/", $str, $r); 
    $ar = $r[0]; 
    foreach ($ar as $k => $v) { 
        $ar[$k] = ord($v[0]) < 128 ? rawurlencode($v) : "%u" . bin2hex(iconv("UTF-8", "UCS-2", $v)); 
    } 
    return join("", $ar); 
} 

function replace_unicode_escape_sequence($match) {       
    return mb_convert_encoding(pack('H*', $match[1]), 'UTF-8', 'UCS-2BE');     
}

function fix_channel_name($name) {
    // 修复 "Travel &amp; Food TV" 为 "Travel And Food TV"
    if ($name === "Travel &amp; Food TV") {
        return "Travel And Food TV";
    }
    return $name;
}

// XML头部结构
$chn = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<!DOCTYPE tv SYSTEM \"http://api.torrent-tv.ru/xmltv.dtd\">\n<tv generator-info-name=\"秋哥綜合\" generator-info-url=\"https://www.tdm.com.mo/c_tv/?ch=Satellite\">\n";

// ==================== 第一部分：HOY频道 ====================
$id30 = 101951;
$cid30 = [
    ['76','HOY國際財經台'],
    ['77','HOY TV'],
    ['78','HOY資訊台'],
];
$nid30 = sizeof($cid30);

// 生成HOY频道节点
for ($idm30 = 1; $idm30 <= $nid30; $idm30++){
    $idd30 = $id30 + $idm30;
    $chn .= "<channel id=\"".$cid30[$idm30-1][1]."\"><display-name lang=\"zh\">".$cid30[$idm30-1][1]."</display-name></channel>\n";
}

// 获取并解析HOY频道的EPG数据
for ($idm30 = 1; $idm30 <= $nid30; $idm30++){
    $channelCode = $cid30[$idm30-1][0];
    $channelName = $cid30[$idm30-1][1];
    $url30 = "https://epg-file.hoy.tv/hoy/OTT{$channelCode}{$dt1}.xml";

    // CURL请求
    $ch30 = curl_init();
    curl_setopt_array($ch30, [
        CURLOPT_URL => $url30,
        CURLOPT_RETURNTRANSFER => 1,
        CURLOPT_SSL_VERIFYPEER => FALSE,
        CURLOPT_SSL_VERIFYHOST => FALSE,
        CURLOPT_ENCODING => 'Vary: Accept-Encoding',
        CURLOPT_CONNECTTIMEOUT => 10,
        CURLOPT_TIMEOUT => 20,
    ]);
    $xmlContent = curl_exec($ch30);

    // 检查CURL错误
    if (curl_errno($ch30)) {
        $curlErr = curl_error($ch30);
        error_log("✗ 频道【{$channelName}】CURL请求失败: {$curlErr}（URL: {$url30}）");
        curl_close($ch30);
        continue;
    }
    curl_close($ch30);

    // XML解析
    $xml = simplexml_load_string($xmlContent);
    if (!$xml) {
        $xmlErrors = libxml_get_errors();
        $errorMsg = [];
        foreach ($xmlErrors as $err) {
            $errorMsg[] = "行{$err->line}：{$err->message}";
        }
        libxml_clear_errors();
        error_log("✗ 频道【{$channelName}】XML解析失败: " . implode(' | ', $errorMsg));
        continue;
    }

    // 遍历EPG数据
    $epgItems = $xml->Channel->EpgItem;
    if (empty($epgItems)) {
        error_log("✗ 频道【{$channelName}】未找到EpgItem节点（XML结构可能异常）");
        continue;
    }

    foreach ($epgItems as $item) {
        $startTime = (string)$item->EpgStartDateTime;
        $date = substr($startTime, 0, 10);

        // 只保留目标日期的节目
        if (in_array($date, $targetDates)) {
            $title = (string)$item->EpisodeInfo->EpisodeShortDescription;
            $endTime = (string)$item->EpgEndDateTime;

            // 格式化时间
            $formatTime = function($timeStr) {
                return str_replace(['-', ':', ' '], '', $timeStr);
            };
            $startFormatted = $formatTime($startTime);
            $endFormatted = $formatTime($endTime);

            // 拼接节目节点
            $chn .= "<programme start=\"{$startFormatted} +0800\" stop=\"{$endFormatted} +0800\" channel=\"{$channelName}\">\n";
            $chn .= "<title lang=\"zh\">" . htmlspecialchars($title, ENT_XML1) . "</title>\n";
            $chn .= "<desc lang=\"zh\"> </desc>\n</programme>\n";
        }
    }
}

// ==================== 第二部分：API获取的频道 ====================
$url = 'https://api2.hoy.tv/api/v3/a/channel';
$ch = curl_init();
curl_setopt($ch, CURLOPT_URL, $url);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);
curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, FALSE);
curl_setopt($ch, CURLOPT_SSL_VERIFYHOST, FALSE);
curl_setopt($ch, CURLOPT_ENCODING, 'Vary: Accept-Encoding');
$re = curl_exec($ch);
$re = str_replace('&', '&amp;', $re);	
curl_close($ch);

$nid = count(json_decode($re)->data);
$name = [];

// 生成API频道的频道节点
for ($idm = 3; $idm <= $nid-1; $idm++) {
    $channelName = json_decode($re)->data[$idm]->name->zh_hk;
    $fixedChannelName = fix_channel_name($channelName);
    $name[$idm] = $fixedChannelName;
    $chn .= "<channel id=\"" . $fixedChannelName . "\"><display-name lang=\"zh\">" . $fixedChannelName . "</display-name></channel>\n";
}

// 获取API频道的EPG数据
for ($idm = 3; $idm <= $nid-1; $idm++) {
    $ch30 = curl_init();
    curl_setopt($ch30, CURLOPT_URL, json_decode($re)->data[$idm]->epg);
    curl_setopt($ch30, CURLOPT_RETURNTRANSFER, 1);
    curl_setopt($ch30, CURLOPT_SSL_VERIFYPEER, FALSE);
    curl_setopt($ch30, CURLOPT_SSL_VERIFYHOST, FALSE);
    $re30 = curl_exec($ch30);
    curl_close($ch30);

    // 使用正则表达式解析EPG数据
    preg_match_all('|<EpgStartDateTime>(.*?)</EpgStartDateTime>|i', $re30, $um30, PREG_SET_ORDER);//播放开始时间
    preg_match_all('|<EpgEndDateTime>(.*?)</EpgEndDateTime>|i', $re30, $un30, PREG_SET_ORDER);//播放结束时间
    preg_match_all('|<EpisodeShortDescription>(.*?)</EpisodeShortDescription>|i', $re30, $uk30, PREG_SET_ORDER);//播放内容

    $trm30 = count($um30);
    $channelName = $name[$idm]; // 使用修复后的频道名称
    
    for ($k30 = 0; $k30 <= $trm30-1; $k30++) {  
        $startTime = str_replace([' ', ':', '-'], '', $um30[$k30][1]);
        $endTime = str_replace([' ', ':', '-'], '', $un30[$k30][1]);
        $title = $uk30[$k30][1];
        
        $chn .= "<programme start=\"{$startTime} +0800\" stop=\"{$endTime} +0800\" channel=\"{$channelName}\">\n";
        $chn .= "<title lang=\"zh\">{$title}</title>\n";
        $chn .= "<desc lang=\"zh\"> </desc>\n</programme>\n";
    }
}

// 闭合XML标签并写入文件
$chn .= "</tv>\n";
file_put_contents($fp, $chn);

echo "✓ EPG文件生成完成！路径：{$fp}\n";
?>