<?php
/**
 * EPG 源处理器
 * 
 * 功能概述：
 * 1. 从多个EPG源下载XML文件，部分敏感源URL从环境变量获取
 * 2. 处理频道ID和显示名称的映射关系
 * 3. 根据配置添加频道ID后缀
 * 4. 更新节目单中的频道引用
 * 5. 保存处理后的标准XML文件
 * 
 * 安全特性：
 * - 敏感源URL完全从环境变量 EPG_CONFIG 获取，代码中不保留
 * - 日志中不记录任何URL信息
 * - 自动处理gzip压缩内容
 * - 完善的错误处理和日志记录
 * - 一个源失败不影响其他源处理
 */

// 从环境变量获取所有配置
$envConfig = [];
if (getenv('EPG_CONFIG')) {
    $envConfig = json_decode(getenv('EPG_CONFIG'), true);
    if (json_last_error() !== JSON_ERROR_NONE) {
        log_message("环境变量EPG_CONFIG格式错误", true);
        $envConfig = [];
    }
}

/**
 * EPG源配置说明：
 * - url: EPG源地址（敏感源从环境变量获取）
 * - id_suffix: 频道ID后缀（可选），用于区分不同源的相同频道
 * - required_env: 标记URL是否必须从环境变量获取
 */
$sources = [
    "epgshanghai.xml" => [
        "url" => $envConfig['epgshanghai.xml'] ?? null,
        "id_suffix" => "shanghai",
        "required_env" => true  // 必须从环境变量获取
    ],
    "epgdifang.xml" => [
        "url" => "https://epg.51zmt.top:8001/difang.xml.gz",
        "id_suffix" => "51zmt"
    ],
    "epgerw.xml" => [
        "url" => "https://raw.githubusercontent.com/kuke31/xmlgz/main/e.xml.gz",
        "id_suffix" => "erw"
    ],
    "epgunifi.xml" => [
        "url" => "https://raw.githubusercontent.com/AqFad2811/epg/refs/heads/main/unifitv.xml"
    ],
    "epghebei.xml" => [
        "url" => $envConfig['epghebei.xml'] ?? null,
        "required_env" => true  // 必须从环境变量获取
    ],
    "singtel.xml" => [
        "url" => "https://raw.githubusercontent.com/dbghelp/Singtel-TV-EPG/refs/heads/main/singtel.xml"
    ]
];

// 添加环境变量中定义的其他源
foreach ($envConfig as $filename => $url) {
    if (!isset($sources[$filename])) {
        $sources[$filename] = [
            "url" => $url,
            "from_env" => true
        ];
    }
}

// 环境配置
error_reporting(E_ALL);
ini_set('display_errors', 1);
ini_set('log_errors', 1);
ini_set('memory_limit', '512M');
set_time_limit(300);

// 日志文件配置
$logFile = __DIR__ . '/epg_generator.log';

// 初始化日志
file_put_contents($logFile, "[" . date('Y-m-d H:i:s') . "] EPG处理任务开始\n", FILE_APPEND);

/**
 * 日志记录函数
 */
function log_message($message, $isError = false) {
    global $logFile;
    $prefix = $isError ? "错误: " : "信息: ";
    $logEntry = "[" . date('Y-m-d H:i:s') . "] " . $prefix . $message . "\n";
    file_put_contents($logFile, $logEntry, FILE_APPEND);
    echo $isError ? "错误: $message\n" : "$message\n";
}

// 立即检查环境
log_message("开始环境检查...");
log_message("PHP版本: " . PHP_VERSION);
log_message("运行模式: " . PHP_SAPI);
log_message("内存限制: " . ini_get('memory_limit'));

/**
 * 环境检查函数
 */
function check_environment() {
    $required_extensions = ['curl', 'dom', 'libxml'];
    foreach ($required_extensions as $ext) {
        if (!extension_loaded($ext)) {
            log_message("必需扩展 $ext 未加载", true);
            return false;
        }
        log_message("扩展 $ext: 已加载");
    }
    
    if (!is_writable('.')) {
        log_message("当前目录不可写，无法保存文件", true);
        return false;
    }
    
    log_message("环境检查通过");
    return true;
}

/**
 * 获取频道显示名称
 */
function get_display_name($channel) {
    $xpath = new DOMXPath($channel->ownerDocument);
    
    $zhName = $xpath->query(".//display-name[@lang='zh']", $channel);
    if ($zhName->length > 0 && trim($zhName->item(0)->nodeValue) !== '') {
        return trim($zhName->item(0)->nodeValue);
    }
    
    $allNames = $xpath->query(".//display-name", $channel);
    foreach ($allNames as $node) {
        if (trim($node->nodeValue) !== '') {
            return trim($node->nodeValue);
        }
    }
    
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
        
        $loaded = @$dom->loadXML($xmlContent, LIBXML_NOERROR | LIBXML_NOWARNING);
        if (!$loaded) {
            log_message("XML内容格式错误，无法解析", true);
            return null;
        }
        
        $channelMap = [];
        $xpath = new DOMXPath($dom);
        
        $channels = $xpath->query('//channel');
        log_message("找到 " . $channels->length . " 个频道节点");
        
        foreach ($channels as $channel) {
            $oldId = $channel->getAttribute('id');
            $displayName = get_display_name($channel);
            
            if (!empty($idSuffix)) {
                $newId = ($oldId !== $displayName) 
                    ? "{$displayName} ({$idSuffix})"
                    : "{$oldId} ({$idSuffix})";
            } else {
                $newId = ($oldId !== $displayName) 
                    ? $displayName
                    : $oldId;
            }
            
            $channel->setAttribute('id', $newId);
            $channelMap[$oldId] = $newId;
        }
        
        $programmes = $xpath->query('//programme');
        log_message("找到 " . $programmes->length . " 个节目单节点");
        
        $updatedCount = 0;
        foreach ($programmes as $programme) {
            $oldChannel = $programme->getAttribute('channel');
            if (isset($channelMap[$oldChannel])) {
                $programme->setAttribute('channel', $channelMap[$oldChannel]);
                $updatedCount++;
            }
        }
        
        log_message("更新了 " . $updatedCount . " 个节目单的频道引用");
        return $dom->saveXML();
        
    } catch (Exception $e) {
        log_message("XML处理异常: " . $e->getMessage(), true);
        return null;
    }
}

/**
 * 下载文件内容
 */
function download_file($url, $filename) {
    log_message("开始下载: $filename");
    
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
        log_message("下载失败 [$filename]: $error", true);
        return false;
    }
    
    if ($httpCode !== 200) {
        log_message("下载失败 [$filename]: HTTP $httpCode", true);
        return false;
    }
    
    if (empty($response)) {
        log_message("下载内容为空 [$filename]", true);
        return false;
    }
    
    log_message("下载成功 [$filename]: " . strlen($response) . " 字节");
    return $response;
}

/**
 * 处理单个EPG源
 */
function process_source($filename, $source) {
    $url = $source['url'] ?? null;
    $idSuffix = $source['id_suffix'] ?? '';
    $requiredEnv = $source['required_env'] ?? false;
    $fromEnv = $source['from_env'] ?? false;
    
    // 检查必须从环境变量获取的源
    if ($requiredEnv && empty($url)) {
        log_message("处理失败 [$filename]: 必须从环境变量获取URL但未配置", true);
        return false;
    }
    
    // 检查URL是否有效
    if (empty($url)) {
        log_message("处理失败 [$filename]: URL未配置", true);
        return false;
    }
    
    // 构造源标识（不暴露URL）
    $sourceInfo = $filename;
    if ($fromEnv) {
        $sourceInfo .= " [环境变量]";
    } elseif ($requiredEnv) {
        $sourceInfo .= " [必需环境变量]";
    }
    if ($idSuffix) {
        $sourceInfo .= " (后缀:$idSuffix)";
    }
    
    log_message("开始处理: $sourceInfo");
    
    // 下载文件
    $response = download_file($url, $filename);
    if ($response === false) {
        return false;
    }
    
    // 处理gzip压缩
    $xmlContent = $response;
    if (substr($response, 0, 2) === "\x1f\x8b") {
        log_message("检测到gzip压缩内容 [$filename]");
        if (!function_exists('gzdecode')) {
            log_message("zlib扩展未加载，无法解压 [$filename]", true);
            return false;
        }
        
        $xmlContent = gzdecode($response);
        if ($xmlContent === false) {
            log_message("gzip解压失败 [$filename]", true);
            return false;
        }
        log_message("解压成功 [$filename]: " . strlen($xmlContent) . " 字节");
    }
    
    // 验证XML格式
    libxml_use_internal_errors(true);
    $dom = new DOMDocument();
    if (!$dom->loadXML($xmlContent)) {
        $errors = libxml_get_errors();
        foreach ($errors as $error) {
            log_message("XML格式错误 [$filename]: " . $error->message, true);
        }
        libxml_clear_errors();
        return false;
    }
    libxml_clear_errors();
    
    // 处理XML内容
    log_message("开始XML处理 [$filename]");
    $processedXml = process_xml($xmlContent, $idSuffix);
    if ($processedXml === null) {
        log_message("XML处理失败 [$filename]", true);
        return false;
    }
    
    // 保存文件
    $outputPath = __DIR__ . '/' . $filename;
    $bytesWritten = file_put_contents($outputPath, $processedXml);
    if ($bytesWritten === false) {
        log_message("文件保存失败 [$filename]", true);
        return false;
    }
    
    log_message("保存成功 [$filename]: " . number_format($bytesWritten) . " 字节");
    return true;
}

/**
 * 主处理函数
 */
function main() {
    global $sources;
    
    // 环境检查
    if (!check_environment()) {
        log_message("环境检查失败，程序终止", true);
        return false;
    }
    
    $results = [];
    $successFiles = [];
    $failedFiles = [];
    
    log_message("开始处理 " . count($sources) . " 个EPG源");
    
    // 逐个处理EPG源
    foreach ($sources as $filename => $source) {
        log_message("----------------------------------------");
        
        $result = process_source($filename, $source);
        $results[$filename] = $result;
        
        if ($result) {
            $successFiles[] = $filename;
            log_message("✓ 处理成功: $filename");
        } else {
            $failedFiles[] = $filename;
            log_message("✗ 处理失败: $filename", true);
        }
        
        log_message("----------------------------------------");
        
        sleep(1);
    }
    
    // 生成处理报告
    $successCount = count($successFiles);
    $failedCount = count($failedFiles);
    $total = count($sources);
    
    log_message("EPG处理任务完成");
    log_message("总体结果: 成功 $successCount/$total, 失败 $failedCount/$total");
    
    if (!empty($successFiles)) {
        log_message("成功文件列表:");
        foreach ($successFiles as $file) {
            $size = file_exists($file) ? number_format(filesize($file)) . " 字节" : "文件丢失";
            log_message("  ✓ $file ($size)");
        }
    }
    
    if (!empty($failedFiles)) {
        log_message("失败文件列表:");
        foreach ($failedFiles as $file) {
            log_message("  ✗ $file", true);
        }
    }
    
    return $failedCount === 0;
}

// 程序入口点
try {
    $success = main();
    $exitCode = $success ? 0 : 1;
    log_message("程序退出，代码: $exitCode");
    exit($exitCode);
} catch (Exception $e) {
    log_message("未处理的异常: " . $e->getMessage(), true);
    exit(1);
}