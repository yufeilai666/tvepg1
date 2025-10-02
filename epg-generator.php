<?php
/**
从数组sources获取链接，下载xml文件并编辑，如果channel id的值不等于display-name的属性，则把display-name的属性赋值给channel id，然后把channel id的值用“ ()”拼接sources[id_suffix]得到新的channel id，例如：龍華電影 (51zmt)，最后把对应的programme节点的channel的值修改为相对应的新channel id的值。处理完了，使用数组中的key作为文件名保存为标准的xml文件。
*/

// 待处理的EPG源
$sources = [
    "epgshanghai.xml" => [
        "url" => "https://epg.deny.vip/sh/tel-epg.xml",
        "id_suffix" => "shanghai"  // 用于拼接channel ID的后缀
    ],
    "epgdifang.xml" => [
        "url" => "https://epg.51zmt.top:8001/difang.xml.gz",
        "id_suffix" => "51zmt"     // 用于拼接channel ID的后缀
    ],
    "epgerw.xml" => [
        "url" => "https://raw.githubusercontent.com/kuke31/xmlgz/main/e.xml.gz",
        # "url" => "http://e.erw.cc/e.xml.gz",
        "id_suffix" => "erw"     // 用于拼接channel ID的后缀
    ],
    "epgunifi.xml" => [         // 没有后缀的情况
        "url" => "https://raw.githubusercontent.com/AqFad2811/epg/refs/heads/main/unifitv.xml",
        // 没有 id_suffix 字段
    ],
    "epghebei.xml" => [         // 没有后缀的情况
        "url" => "https://epg.mb6.top/heiptv.xml",
        // 没有 id_suffix 字段
    ],
    "singtel.xml" => [         // 没有后缀的情况
        "url" => "https://raw.githubusercontent.com/dbghelp/Singtel-TV-EPG/refs/heads/main/singtel.xml",
        // 没有 id_suffix 字段
    ]
];

// 设置错误报告级别
error_reporting(E_ALL);
ini_set('display_errors', 1);
ini_set('log_errors', 1);

// 创建日志文件
$logFile = __DIR__ . '/epg_generator.log';

// 初始化日志
file_put_contents($logFile, "[" . date('Y-m-d H:i:s') . "] 开始处理EPG源\n", FILE_APPEND);

// 简单的日志函数
function log_message($message, $isError = false) {
    global $logFile;
    $prefix = $isError ? "错误: " : "信息: ";
    $logEntry = "[" . date('Y-m-d H:i:s') . "] " . $prefix . $message . "\n";
    file_put_contents($logFile, $logEntry, FILE_APPEND);
    echo $isError ? "错误: $message\n" : "$message\n";
}

// 检查环境
log_message("检查PHP环境...");
log_message("PHP版本: " . PHP_VERSION);
log_message("运行模式: " . PHP_SAPI);
log_message("内存限制: " . ini_get('memory_limit'));

// 检查必要扩展
$required_extensions = ['curl', 'dom', 'libxml'];
foreach ($required_extensions as $ext) {
    if (extension_loaded($ext)) {
        log_message("扩展 $ext: 已加载");
    } else {
        log_message("扩展 $ext: 未加载", true);
        exit(1);
    }
}

// 检查当前目录是否可写
if (!is_writable('.')) {
    log_message("当前目录不可写", true);
    exit(1);
}

/**
 * 获取频道显示名称（优先中文）
 */
function get_display_name($channel) {
    // 查找中文名称
    $xpath = new DOMXPath($channel->ownerDocument);
    $zhName = $xpath->query(".//display-name[@lang='zh']", $channel);
    if ($zhName->length > 0 && trim($zhName->item(0)->nodeValue) !== '') {
        return trim($zhName->item(0)->nodeValue);
    }
    
    // 查找任意语言名称
    $allNames = $xpath->query(".//display-name", $channel);
    foreach ($allNames as $node) {
        if (trim($node->nodeValue) !== '') {
            return trim($node->nodeValue);
        }
    }
    
    // 尝试从channel id获取
    if ($channel->hasAttribute('id') && $channel->getAttribute('id') !== '') {
        return $channel->getAttribute('id');
    }
    
    return "未知频道";
}

/**
 * 处理XML内容
 */
function process_xml($xmlContent, $idSuffix) {
    if (empty($xmlContent)) {
        log_message("XML内容为空", true);
        return null;
    }
    
    try {
        $dom = new DOMDocument();
        $dom->preserveWhiteSpace = false;
        $dom->formatOutput = true;
        
        // 尝试加载XML内容
        $loaded = @$dom->loadXML($xmlContent, LIBXML_NOERROR | LIBXML_NOWARNING);
        if (!$loaded) {
            log_message("无法加载XML内容", true);
            return null;
        }
        
        $channelMap = [];
        $xpath = new DOMXPath($dom);
        
        // 处理所有channel节点
        $channels = $xpath->query('//channel');
        foreach ($channels as $channel) {
            $oldId = $channel->getAttribute('id');
            $displayName = get_display_name($channel);
            
            // 检查是否需要添加后缀
            if (!empty($idSuffix)) {
                // 使用id_suffix拼接新的channel ID
                $newId = ($oldId !== $displayName) 
                    ? "{$displayName} ({$idSuffix})"
                    : "{$oldId} ({$idSuffix})";
            } else {
                // 不添加后缀
                $newId = ($oldId !== $displayName) 
                    ? $displayName
                    : $oldId;
            }
            
            $channel->setAttribute('id', $newId);
            $channelMap[$oldId] = $newId;
        }
        
        // 处理所有programme节点
        $programmes = $xpath->query('//programme');
        foreach ($programmes as $programme) {
            $oldChannel = $programme->getAttribute('channel');
            if (isset($channelMap[$oldChannel])) {
                $programme->setAttribute('channel', $channelMap[$oldChannel]);
            }
        }
        
        return $dom->saveXML();
    } catch (Exception $e) {
        log_message("处理XML时出错: " . $e->getMessage(), true);
        return null;
    }
}

/**
 * 下载文件
 */
function download_file($url) {
    log_message("下载URL: $url");
    
    $ch = curl_init();
    curl_setopt_array($ch, [
        CURLOPT_URL => $url,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT => 120,
        CURLOPT_SSL_VERIFYPEER => false,
        CURLOPT_FOLLOWLOCATION => true,
        CURLOPT_USERAGENT => 'AptvPlayer/1.3.2',
        CURLOPT_FAILONERROR => true,
    ]);
    
    $response = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $error = curl_error($ch);
    curl_close($ch);
    
    if ($error) {
        log_message("cURL错误: $error", true);
        return false;
    }
    
    if ($httpCode !== 200 || empty($response)) {
        log_message("下载失败: HTTP $httpCode", true);
        return false;
    }
    
    log_message("下载成功: " . strlen($response) . " 字节");
    return $response;
}

/**
 * 处理单个源
 */
function process_source($filename, $source) {
    $url = $source['url'];
    $idSuffix = isset($source['id_suffix']) ? $source['id_suffix'] : '';
    
    log_message("开始处理源: $filename" . ($idSuffix ? " (ID后缀: $idSuffix)" : " (无ID后缀)"));
    
    // 下载XML内容
    $response = download_file($url);
    if ($response === false) {
        log_message("下载失败: $url", true);
        return false;
    }
    
    // 检查响应是否有效
    if (empty($response)) {
        log_message("下载内容为空", true);
        return false;
    }
    
    // 检查是否是gzip压缩内容
    $xmlContent = $response;
    if (substr($response, 0, 2) === "\x1f\x8b") { // gzip魔数
        log_message("检测到gzip压缩内容，正在解压...");
        if (function_exists('gzdecode')) {
            $xmlContent = gzdecode($response);
            if ($xmlContent === false) {
                log_message("解压失败", true);
                return false;
            }
            log_message("解压成功: " . strlen($xmlContent) . " 字节");
        } else {
            log_message("zlib扩展未加载，无法解压gzip内容", true);
            return false;
        }
    }
    
    // 检查XML内容是否有效
    if (empty($xmlContent)) {
        log_message("XML内容为空", true);
        return false;
    }
    
    // 尝试解析XML
    libxml_use_internal_errors(true);
    $dom = new DOMDocument();
    if (!$dom->loadXML($xmlContent)) {
        $errors = libxml_get_errors();
        foreach ($errors as $error) {
            log_message("XML解析错误: " . $error->message, true);
        }
        libxml_clear_errors();
        return false;
    }
    
    // 处理XML
    log_message("开始处理XML内容...");
    $processedXml = process_xml($xmlContent, $idSuffix);
    if (!$processedXml) {
        log_message("处理失败", true);
        return false;
    }
    
    // 保存文件
    log_message("保存文件: $filename");
    // 在保存文件时使用当前工作目录
$bytesWritten = file_put_contents(__DIR__ . '/' . $filename, $processedXml);
    if ($bytesWritten === false) {
        log_message("保存失败", true);
        return false;
    }
    
    log_message("成功保存: " . number_format($bytesWritten) . " 字节");
    return true;
}

/**
 * 主处理函数
 */
function main() {
    global $sources;
    
    $results = [];
    
    // 逐个处理源
    foreach ($sources as $filename => $source) {
        log_message("========================================");
        $result = process_source($filename, $source);
        $results[$filename] = $result;
        log_message("========================================");
        
        // 每次处理完后休息一下，避免请求过于频繁
        sleep(1);
    }
    
    // 输出结果
    $successCount = count(array_filter($results));
    $total = count($sources);
    log_message("处理完成! 成功: $successCount/$total");
    
    // 列出所有生成的文件
    log_message("生成的文件:");
    foreach (array_keys($sources) as $filename) {
        $status = isset($results[$filename]) && $results[$filename] ? "✓" : "✗";
        $size = file_exists($filename) ? number_format(filesize($filename)) . " 字节" : "不存在";
        log_message(" - {$status} {$filename} ({$size})");
    }
    
    return $successCount === $total;
}

// 执行主程序
try {
    // 增加内存限制
    ini_set('memory_limit', '512M');
    
    // 设置超时时间
    set_time_limit(300);
    
    // 运行主程序
    $success = main();
    exit($success ? 0 : 1);
} catch (Exception $e) {
    log_message("未捕获的异常: " . $e->getMessage(), true);
    exit(1);
}
