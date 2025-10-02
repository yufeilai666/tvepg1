<?php
// 定义要合并的XML文件列表（支持.gz压缩文件）
// 要合并的XML文件在主分区的根目录下，但在工作流中会被复制到临时目录
$xmlFiles = [
    'epgpw.xml',
    'epgmytvsuper_cst.xml',
    'epganywhere.xml',
    'epgkai.xml',
    'epgnew4gtv2_cst.xml',
    'epg51zmt.xml', 
    'epgshanghai.xml',
    //'epgofiii.xml',
    //'epgastro.xml',
    //'epgunifi.xml',
];

// 检查是否支持zlib扩展
if (!extension_loaded('zlib')) {
    die("错误: 需要启用zlib扩展以支持.gz文件处理。请修改php.ini启用zlib扩展。\n");
}

// 创建一个临时文件来存储合并的XML内容
$tempOutputFile = tempnam(sys_get_temp_dir(), 'epg_merge_');
$tempHandle = fopen($tempOutputFile, 'w');
if (!$tempHandle) {
    die("无法创建临时输出文件\n");
}

// 写入XML头部
fwrite($tempHandle, '<?xml version="1.0" encoding="UTF-8"?>' . "\n");
fwrite($tempHandle, '<tv>' . "\n");

$totalFiles = count($xmlFiles);
$currentFile = 0;

// 第一步：合并所有频道
echo "开始合并频道数据...\n";
foreach ($xmlFiles as $file) {
    $currentFile++;
    $startTime = microtime(true);
    
    // 检查文件是否存在
    if (!file_exists($file)) {
        error_log("跳过不存在的文件: $file");
        echo "[{$currentFile}/{$totalFiles}] 跳过不存在的文件: " . basename($file) . "\n";
        continue;
    }

    // 判断文件类型并创建适当的读取器
    $isGzFile = (substr($file, -3) === '.gz');
    $displayName = basename($file);
    
    if ($isGzFile) {
        // 处理.gz压缩文件
        $gzHandle = gzopen($file, 'r');
        if (!$gzHandle) {
            error_log("无法打开.gz文件: $file");
            echo "[{$currentFile}/{$totalFiles}] 无法打开.gz文件: " . $displayName . "\n";
            continue;
        }
        
        // 创建临时文件来存储解压后的内容
        $tempFile = tempnam(sys_get_temp_dir(), 'epg_');
        $tempHandle2 = fopen($tempFile, 'w');
        
        if (!$tempHandle2) {
            error_log("无法创建临时文件");
            echo "[{$currentFile}/{$totalFiles}] 无法创建临时文件处理: " . $displayName . "\n";
            gzclose($gzHandle);
            continue;
        }
        
        // 解压内容到临时文件
        while (!gzeof($gzHandle)) {
            fwrite($tempHandle2, gzread($gzHandle, 8192));
        }
        
        fclose($tempHandle2);
        gzclose($gzHandle);
        
        $sourceFile = $tempFile;
    } else {
        $sourceFile = $file;
    }

    $channelCount = 0;
    echo "[{$currentFile}/{$totalFiles}] 处理文件: " . $displayName . " - ";
    
    // 使用XMLReader处理文件，确保正确处理XML结构
    $reader = new XMLReader();
    if (!$reader->open($sourceFile)) {
        error_log("无法打开文件: $sourceFile");
        echo "[{$currentFile}/{$totalFiles}] 无法打开文件: " . $displayName . "\n";
        if ($isGzFile) unlink($sourceFile);
        continue;
    }
    
    // 查找channel元素
    while ($reader->read()) {
        if ($reader->nodeType === XMLReader::ELEMENT && $reader->name === 'channel') {
            // 获取完整的channel XML
            $channelXml = $reader->readOuterXml();
            
            // 使用DOMDocument格式化XML
            $dom = new DOMDocument();
            $dom->preserveWhiteSpace = false;
            $dom->formatOutput = true;
            
            // 加载XML片段
            if ($dom->loadXML($channelXml)) {
                // 保存格式化后的XML
                $formattedXml = $dom->saveXML($dom->documentElement);
                // 写入格式化后的XML
                fwrite($tempHandle, "  " . $formattedXml . "\n");
                $channelCount++;
            }
        }
    }
    
    $reader->close();
    
    // 清理临时文件
    if ($isGzFile) {
        unlink($sourceFile);
    }
    
    $elapsedTime = round(microtime(true) - $startTime, 2);
    $fileType = $isGzFile ? "(.gz压缩)" : "";
    echo "找到 {$channelCount} 个频道 (耗时: {$elapsedTime}s) {$fileType}\n";
}

// 第二步：合并所有节目
echo "\n开始合并节目数据...\n";
$currentFile = 0;
foreach ($xmlFiles as $file) {
    $currentFile++;
    $startTime = microtime(true);
    
    // 检查文件是否存在
    if (!file_exists($file)) {
        error_log("跳过不存在的文件: $file");
        echo "[{$currentFile}/{$totalFiles}] 跳过不存在的文件: " . basename($file) . "\n";
        continue;
    }

    // 判断文件类型并创建适当的读取器
    $isGzFile = (substr($file, -3) === '.gz');
    $displayName = basename($file);
    
    if ($isGzFile) {
        // 处理.gz压缩文件
        $gzHandle = gzopen($file, 'r');
        if (!$gzHandle) {
            error_log("无法打开.gz文件: $file");
            echo "[{$currentFile}/{$totalFiles}] 无法打开.gz文件: " . $displayName . "\n";
            continue;
        }
        
        // 创建临时文件来存储解压后的内容
        $tempFile = tempnam(sys_get_temp_dir(), 'epg_');
        $tempHandle2 = fopen($tempFile, 'w');
        
        if (!$tempHandle2) {
            error_log("无法创建临时文件");
            echo "[{$currentFile}/{$totalFiles}] 无法创建临时文件处理: " . $displayName . "\n";
            gzclose($gzHandle);
            continue;
        }
        
        // 解压内容到临时文件
        while (!gzeof($gzHandle)) {
            fwrite($tempHandle2, gzread($gzHandle, 8192));
        }
        
        fclose($tempHandle2);
        gzclose($gzHandle);
        
        $sourceFile = $tempFile;
    } else {
        $sourceFile = $file;
    }

    $programmeCount = 0;
    echo "[{$currentFile}/{$totalFiles}] 处理文件: " . $displayName . " - ";
    
    // 使用XMLReader处理文件，确保正确处理XML结构
    $reader = new XMLReader();
    if (!$reader->open($sourceFile)) {
        error_log("无法打开文件: $sourceFile");
        echo "[{$currentFile}/{$totalFiles}] 无法打开文件: " . $displayName . "\n";
        if ($isGzFile) unlink($sourceFile);
        continue;
    }
    
    // 查找programme元素
    while ($reader->read()) {
        if ($reader->nodeType === XMLReader::ELEMENT && $reader->name === 'programme') {
            // 获取完整的programme XML
            $programmeXml = $reader->readOuterXml();
            
            // 使用DOMDocument格式化XML
            $dom = new DOMDocument();
            $dom->preserveWhiteSpace = false;
            $dom->formatOutput = true;
            
            // 加载XML片段
            if ($dom->loadXML($programmeXml)) {
                // 保存格式化后的XML
                $formattedXml = $dom->saveXML($dom->documentElement);
                // 写入格式化后的XML
                fwrite($tempHandle, "  " . $formattedXml . "\n");
                $programmeCount++;
            }
        }
    }
    
    $reader->close();
    
    // 清理临时文件
    if ($isGzFile) {
        unlink($sourceFile);
    }
    
    $elapsedTime = round(microtime(true) - $startTime, 2);
    $fileType = $isGzFile ? "(.gz压缩)" : "";
    echo "找到 {$programmeCount} 个节目 (耗时: {$elapsedTime}s) {$fileType}\n";
}

// 完成XML文档
fwrite($tempHandle, '</tv>');
fclose($tempHandle);

// 读取临时文件内容
echo "\nXML文件合并完成，正在进行最终格式化...\n";
$content = file_get_contents($tempOutputFile);

// 使用DOMDocument进行最终格式化
$dom = new DOMDocument();
$dom->preserveWhiteSpace = false;
$dom->formatOutput = true;

// 尝试加载XML内容
if ($dom->loadXML($content, LIBXML_NOENT | LIBXML_NOCDATA)) {
    $formattedXml = $dom->saveXML();
    file_put_contents('epgziyong.xml', $formattedXml);
    echo "XML文件已成功格式化和保存。\n";
} else {
    echo "XML解析错误，使用原始内容（未格式化）\n";
    file_put_contents('epgziyong.xml', $content);
}

// 清理临时文件
unlink($tempOutputFile);

echo "总计处理了 " . count($xmlFiles) . " 个文件\n";

// 显示最终文件大小
$outputSize = filesize('epgziyong.xml');
echo "输出文件大小: " . formatBytes($outputSize) . "\n";

// 辅助函数：格式化字节大小
function formatBytes($bytes, $precision = 2) {
    $units = ['B', 'KB', 'MB', 'GB', 'TB'];
    $bytes = max($bytes, 0);
    $pow = floor(($bytes ? log($bytes) : 0) / log(1024));
    $pow = min($pow, count($units) - 1);
    $bytes /= pow(1024, $pow);
    return round($bytes, $precision) . ' ' . $units[$pow];
}
?>
