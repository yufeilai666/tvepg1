<?php
/**
 * EPG修复系统 - 增强调试版
 * 
 * 功能：
 * 1. 修复跨日期导致的0点日期错误问题
 * 2. 合并因跨日期被切割的相同节目
 * 3. 保留所有频道信息
 * 4. 提供详细的调试信息
 * 
 * 主要特点：
 * - 精确修复跨午夜节目时间异常
 * - 智能合并被切割的相同节目
 * - 流式XML处理，高效处理大型文件
 * - 详细的调试日志，包含频道和节目信息
 * - 完善的错误处理和重试机制
 * 
 * 使用说明：
 * 1. 支持从环境变量EPG_CONFIG读取EPG源配置
 * 2. 支持直接在$sources中配置其他EPG源
 * 3. 一个源失败不会影响其他源的运行
 * 4. 脚本会自动下载、修复并保存EPG文件
 * 5. 开启调试模式($debug=true)可查看详细处理过程
 * 6. 处理结果会显示在控制台或网页中
 */

// 直接配置的EPG源（除了从环境变量读取的源外，还可以在这里添加其他源）
$directSources = [
    "epgmytvsuper_new.xml" => "https://raw.githubusercontent.com/yufeilai666/tvepg/main/epgmytvsuper.xml"
    // 可以在这里添加更多直接配置的源
];

// 从环境变量读取EPG源配置
$epgConfigJson = getenv('EPG_CONFIG');
$envSources = [];
$envConfigErrors = [];

if ($epgConfigJson) {
    $epgConfig = json_decode($epgConfigJson, true);
    if (json_last_error() !== JSON_ERROR_NONE) {
        $envConfigErrors[] = "无法解析EPG_CONFIG环境变量中的JSON数据";
    } else {
        // 只选择需要的源：chuanliu.xml 和 cqunicom.xml
        if (isset($epgConfig["chuanliu.xml"])) {
            $envSources["chuanliu.xml"] = $epgConfig["chuanliu.xml"];
        } else {
            $envConfigErrors[] = "EPG_CONFIG中未找到chuanliu.xml配置";
        }
        
        if (isset($epgConfig["cqunicom.xml"])) {
            $envSources["cqunicom.xml"] = $epgConfig["cqunicom.xml"];
        } else {
            $envConfigErrors[] = "EPG_CONFIG中未找到cqunicom.xml配置";
        }
    }
} else {
    $envConfigErrors[] = "EPG_CONFIG环境变量未找到需要的配置";
}

// 合并所有源：环境变量源 + 直接配置源
$sources = array_merge($envSources, $directSources);

if (empty($sources)) {
    die("错误：未找到任何有效的EPG源配置");
}

// 错误报告设置
error_reporting(E_ALL);
ini_set('display_errors', 1);
ini_set('memory_limit', '512M'); // 增加内存限制以处理大型XML文件
set_time_limit(0); // 无时间限制

// 检查必要扩展
if (!extension_loaded('dom') || !extension_loaded('xmlreader') || !extension_loaded('zlib')) {
    die("错误：必需扩展未启用。请启用DOM、XMLReader和Zlib扩展");
}

// 检测是否在命令行模式下运行
$isCli = (php_sapi_name() === 'cli');

class EnhancedDebugEPGProcessor {
    /**
     * 源文件配置
     * @var array
     */
    private $sources;
    
    /**
     * 环境变量配置错误
     * @var array
     */
    private $envConfigErrors;
    
    /**
     * 总文件数
     * @var int
     */
    private $totalFiles;
    
    /**
     * 已处理文件数
     * @var int
     */
    private $processedFiles = 0;
    
    /**
     * 处理开始时间
     * @var float
     */
    private $startTime;
    
    /**
     * 是否有错误
     * @var bool
     */
    private $hasErrors = false;
    
    /**
     * 成功下载的文件列表
     * @var array
     */
    private $successfulDownloads = [];
    
    /**
     * 下载失败的文件列表
     * @var array
     */
    private $failedDownloads = [];
    
    /**
     * 是否开启调试模式
     * @var bool
     */
    private $debug = false;
    
    /**
     * 频道信息存储
     * @var array
     */
    private $channels = [];
    
    /**
     * 当前处理的文件名
     * @var string
     */
    private $currentFilename = '';
    
    /**
     * 是否已解压当前文件
     * @var bool
     */
    private $currentFileUnzipped = false;
    
    /**
     * 是否在命令行模式下运行
     * @var bool
     */
    private $isCli;
    
    /**
     * 时间格式错误计数
     * @var int
     */
    private $timeFormatErrorCount = 0;

    /**
     * 构造函数
     * @param array $sources EPG源配置
     * @param array $envConfigErrors 环境变量配置错误
     * @param bool $isCli 是否命令行模式
     */
    public function __construct($sources, $envConfigErrors = [], $isCli = false) {
        $this->sources = $sources;
        $this->envConfigErrors = $envConfigErrors;
        $this->totalFiles = count($sources);
        $this->startTime = microtime(true);
        $this->isCli = $isCli;
    }
    
    /**
     * 获取成功下载的文件列表
     * @return array
     */
    public function getSuccessfulDownloads() {
        return $this->successfulDownloads;
    }
    
    /**
     * 获取失败下载的文件列表
     * @return array
     */
    public function getFailedDownloads() {
        return $this->failedDownloads;
    }
    
    /**
     * 获取环境变量配置错误
     * @return array
     */
    public function getEnvConfigErrors() {
        return $this->envConfigErrors;
    }
    
    /**
     * 检查是否有错误发生
     * @return bool
     */
    public function hasErrors() {
        return $this->hasErrors || !empty($this->envConfigErrors) || !empty($this->failedDownloads);
    }
    
    /**
     * 获取处理的文件总数
     * @return int
     */
    public function getTotalFiles() {
        return $this->totalFiles;
    }
    
    /**
     * 处理所有EPG源
     * @return bool 是否没有错误发生
     */
    public function processAll() {
        if ($this->isCli) {
            echo "开始处理 {$this->totalFiles} 个EPG源...\n";
            
            // 显示环境变量配置错误
            if (!empty($this->envConfigErrors)) {
                echo "环境变量配置警告:\n";
                foreach ($this->envConfigErrors as $error) {
                    echo "  ⚠️  $error\n";
                }
                echo "\n";
            }
            
            echo str_repeat("=", 50) . "\n";
        } else {
            echo "<div style='font-family: Consolas, monospace; background: #1e1e1e; color: #dcdcdc; padding: 20px; border-radius: 8px;'>";
            echo "<h2 style='color: #4ec9b0; border-bottom: 1px solid #3c3c3c; padding-bottom: 10px;'>EPG修复系统</h2>";
            
            // 显示环境变量配置错误
            if (!empty($this->envConfigErrors)) {
                echo "<div style='margin: 10px 0; padding: 10px; background: #4b3e1e; border-radius: 5px; color: #ffd79d;'>";
                echo "<h3 style='color: #ffd79d;'>环境变量配置警告:</h3>";
                echo "<ul>";
                foreach ($this->envConfigErrors as $error) {
                    echo "<li>⚠️ $error</li>";
                }
                echo "</ul>";
                echo "</div>";
            }
        }
        
        foreach ($this->sources as $filename => $url) {
            // 先显示进度信息
            $progress = round(($this->processedFiles / $this->totalFiles) * 100);
            $elapsed = round(microtime(true) - $this->startTime, 2);
            $remaining = $this->totalFiles - $this->processedFiles - 1; // 减去当前正在处理的文件
            
            // 确保剩余文件数不为负数
            if ($remaining < 0) $remaining = 0;
            
            if ($this->isCli) {
                echo "[{$progress}%] 处理中: {$filename} - 已用: {$elapsed}s | 剩余: {$remaining}个文件\n";
            } else {
                echo "<div style='margin: 10px 0; padding: 10px; background: #2d2d30; border-radius: 5px;'>";
                echo "[{$progress}%] 处理中: {$filename} - 已用: {$elapsed}s | 剩余: {$remaining}个文件";
                echo "</div>";
            }
            
            // 然后处理文件（会输出调试信息）
            $this->processFile($filename, $url);
            $this->processedFiles++;
        }
        
        $totalTime = round(microtime(true) - $this->startTime, 2);
        
        // 添加100%进度信息
        $elapsed = round($totalTime, 2);
        if ($this->isCli) {
            echo "[100%] 处理完成: 所有文件已处理 - 总耗时: {$totalTime}s\n";
            
            echo "\n" . str_repeat("=", 50) . "\n";
            echo "处理完成! 耗时: {$totalTime}秒\n";
            
            $successCount = count($this->successfulDownloads);
            $failedCount = count($this->failedDownloads);
            echo "下载统计: 成功 {$successCount} 个, 失败 {$failedCount} 个\n";
            
            if ($successCount > 0) {
                echo "成功处理: " . implode(', ', $this->successfulDownloads) . "\n";
            }
            
            if ($failedCount > 0) {
                echo "处理失败: " . implode(', ', $this->failedDownloads) . "\n";
            }
        }
        
        return !$this->hasErrors && empty($this->failedDownloads);
    }
    
    /**
     * 检查是否有成功下载的文件
     * @return bool
     */
    public function hasSuccessfulDownloads() {
        return count($this->successfulDownloads) > 0;
    }
    
    /**
     * 处理单个文件
     * @param string $filename 保存的文件名
     * @param string $url 源URL
     */
    private function processFile($filename, $url) {
        $this->currentFilename = $filename;
        $this->currentFileUnzipped = false;
        $this->timeFormatErrorCount = 0; // 重置时间格式错误计数
        
        $content = $this->downloadWithRetry($url, 3);
        
        if ($content === false) {
            $this->logError("下载失败");
            $this->failedDownloads[] = $filename;
            $this->currentFilename = '';
            return;
        }
        
        // 下载成功，记录调试信息
        $this->logDebug("下载成功");
        
        // 记录解压情况
        if ($this->currentFileUnzipped) {
            $this->logDebug("  解压状态: 已解压");
        } else {
            $this->logDebug("  解压状态: 无需解压");
        }
        
        $this->processXML($content, $filename);
        
        // 如果有时间格式错误，记录调试信息
        if ($this->timeFormatErrorCount > 0) {
            $this->logDebug("  时间格式错误节目数: {$this->timeFormatErrorCount} (已跳过)");
        }
        
        $this->successfulDownloads[] = $filename;
        $this->currentFilename = '';
    }
    
    /**
     * 带重试的下载
     * @param string $url 下载URL
     * @param int $maxRetries 最大重试次数
     * @return string|false 下载内容或false
     */
    private function downloadWithRetry($url, $maxRetries = 3) {
        $retryCount = 0;
        $retryDelay = 1; // 初始重试延迟(秒)
        
        while ($retryCount <= $maxRetries) {
            $content = $this->downloadEpgData($url);
            
            if ($content !== false) {
                return $content;
            }
            
            if ($retryCount < $maxRetries) {
                $this->logError("下载失败，{$retryDelay}秒后重试... (尝试 {$retryCount}/{$maxRetries})");
                sleep($retryDelay);
                $retryDelay *= 2; // 指数退避
                if ($retryDelay > 30) $retryDelay = 30; // 最大延迟30秒
            }
            
            $retryCount++;
        }
        
        return false;
    }
    
    /**
     * 下载EPG数据
     * @param string $url 下载URL
     * @return string|false 下载内容或false
     */
    private function downloadEpgData($url) {
        $ch = curl_init();
        curl_setopt($ch, CURLOPT_URL, $url);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);
        curl_setopt($ch, CURLOPT_TIMEOUT, 120);
        curl_setopt($ch, CURLOPT_USERAGENT, 'AptvPlayer/1.4.2');
        
        $content = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $error = curl_error($ch);
        curl_close($ch);
        
        if ($httpCode !== 200 || $content === false) {
            $errorMsg = "下载失败 - HTTP代码: {$httpCode}";
            if ($error) $errorMsg .= " - 错误: {$error}";
            $this->logError($errorMsg);
            return false;
        }
        
        // 如果是gzip文件则解压
        $unzipped = false;
        if (substr($url, -3) === '.gz' || $this->isGzipped($content)) {
            $unzippedContent = @gzdecode($content);
            if ($unzippedContent !== false) {
                $content = $unzippedContent;
                $this->currentFileUnzipped = true;
                $unzipped = true;
            } else {
                $this->logError("解压失败");
                return false;
            }
        }
        
        return $content;
    }
    
    /**
     * 检查数据是否为gzip格式
     * @param string $data 数据
     * @return bool
     */
    private function isGzipped($data) {
        if (strlen($data) < 2) return false;
        return (ord($data[0]) == 0x1f && ord($data[1]) == 0x8b);
    }
    
    /**
     * 处理XML内容
     * @param string $xmlContent XML内容
     * @param string $filename 保存的文件名
     */
    private function processXML($xmlContent, $filename) {
        $this->channels = []; // 重置频道存储
        
        // 创建DOM文档并加载原始XML
        $dom = new DOMDocument('1.0', 'UTF-8');
        $dom->preserveWhiteSpace = false;
        $dom->formatOutput = true;
        
        // 直接加载原始XML内容
        if (!$dom->loadXML($xmlContent)) {
            $this->logError("无法解析XML内容");
            $this->hasErrors = true;
            return;
        }
        
        // 获取根元素
        $root = $dom->documentElement;
        
        // 收集所有频道信息
        $this->collectChannels($dom);
        
        // 处理节目节点
        $programmes = $dom->getElementsByTagName('programme');
        $programCount = $programmes->length;
        $mergesCount = 0;
        $midnightFixCount = 0;
        
        // 由于DOM操作会改变节点集合，我们需要先收集所有节目节点
        $programNodes = [];
        foreach ($programmes as $programme) {
            $programNodes[] = $programme;
        }
        
        $programBuffer = []; // 节目缓冲区
        
        // 处理每个节目节点
        foreach ($programNodes as $programNode) {
            // 检查时间格式是否正确
            $start = $programNode->getAttribute('start');
            $stop = $programNode->getAttribute('stop');
            
            // 跳过时间格式错误的节目
            if (!$this->isValidTimeFormat($start) || !$this->isValidTimeFormat($stop)) {
                $this->timeFormatErrorCount++;
                $this->logDebug("跳过时间格式错误的节目: start={$start}, stop={$stop}");
                continue;
            }
            
            // 修复时间异常
            $originalStop = $programNode->getAttribute('stop');
            $this->fixTimeAnomaly($programNode);
            if ($programNode->getAttribute('stop') !== $originalStop) {
                $midnightFixCount++;
            }
            
            // 尝试合并跨午夜节目
            if ($this->mergeSplitMidnightProgram($programBuffer, $programNode, $mergesCount)) {
                // 如果合并成功，从DOM中移除当前节点
                $programNode->parentNode->removeChild($programNode);
                continue;
            }
            
            // 不能合并，将缓冲区中的节目添加到DOM
            foreach ($programBuffer as $bufferedNode) {
                // 缓冲区中的节点已经存在于DOM中，无需再次添加
            }
            $programBuffer = [$programNode];
        }
        
        // 保存处理后的XML
        if ($programCount > 0) {
            if ($dom->save(__DIR__ . '/' . $filename)) {
                $this->logSuccess("保存成功");
                $this->logDebug("  节目数: {$programCount}");
                $this->logDebug("  午夜日期修复数: {$midnightFixCount}");
                $this->logDebug("  合并数: {$mergesCount}");
            } else {
                $this->logError("保存失败");
                $this->hasErrors = true;
            }
        } else {
            $this->logError("无有效节目");
            $this->hasErrors = true;
        }
    }
    
    /**
     * 收集频道信息
     * @param DOMDocument $dom DOM文档
     */
    private function collectChannels($dom) {
        $channels = $dom->getElementsByTagName('channel');
        
        foreach ($channels as $channel) {
            $channelId = $channel->getAttribute('id');
            
            if (!isset($this->channels[$channelId])) {
                $this->channels[$channelId] = [
                    'display-names' => []
                ];
                
                // 收集显示名称
                $displayNames = $channel->getElementsByTagName('display-name');
                foreach ($displayNames as $displayName) {
                    $name = trim($displayName->nodeValue);
                    if (!in_array($name, $this->channels[$channelId]['display-names'])) {
                        $this->channels[$channelId]['display-names'][] = $name;
                    }
                }
            }
        }
    }
    
    /**
     * 检查时间格式是否有效
     * @param string $timeStr 时间字符串
     * @return bool
     */
    private function isValidTimeFormat($timeStr) {
        // 基本检查：长度至少应为14位数字（YmdHis格式）
        if (strlen($timeStr) < 14) {
            return false;
        }
        
        // 检查前14位是否为数字
        $timePart = substr($timeStr, 0, 14);
        if (!ctype_digit($timePart)) {
            return false;
        }
        
        return true;
    }
    
    /**
     * 修复时间异常（跨午夜节目）
     * @param DOMElement $programNode 节目节点
     */
    private function fixTimeAnomaly(&$programNode) {
        $start = $programNode->getAttribute('start');
        $stop = $programNode->getAttribute('stop');
        
        // 尝试多种格式解析时间
        $startDt = $this->parseDateTime($start);
        $stopDt = $this->parseDateTime($stop);
        
        if (!$startDt || !$stopDt) {
            $this->logDebug("时间格式错误: start={$start}, stop={$stop}");
            return;
        }
        
        // 修复类型1：结束时间 < 开始时间（跨午夜但日期未增加）
        if ($stopDt < $startDt) {
            $startTime = $startDt->format('His');
            $stopTime = $stopDt->format('His');
            
            // 仅当时间差在合理范围内才修复（午夜到凌晨）
            if ($stopTime < $startTime && $stopTime >= '000000' && $stopTime < '060000') {
                $channelId = $programNode->getAttribute('channel');
                $channelName = $this->getChannelName($channelId);
                $programTitle = $this->getTitle($programNode);
                
                $stopDt->modify('+1 day');
                $fixedStop = $stopDt->format('YmdHis O');
                $programNode->setAttribute('stop', $fixedStop);
                
                if ($this->debug) {
                    $this->logDebug("修复跨午夜节目日期错误 (类型1)");
                    $this->logDebug("  频道id: {$channelId}");
                    $this->logDebug("  频道名称: {$channelName}");
                    $this->logDebug("  节目标题: {$programTitle}");
                    $this->logDebug("  原始时间: {$start} -> {$stop}");
                    $this->logDebug("  修复为: {$start} -> {$fixedStop}");
                }
            }
        }
        
        // 修复类型2：24:00:00格式的时间（应该转换为第二天的00:00:00）
        $stop = $programNode->getAttribute('stop');
        if (preg_match('/^(\d{8})240000/', $stop, $matches)) {
            $date = $matches[1];
            $nextDay = date('Ymd', strtotime($date . ' +1 day'));
            $fixedStop = $nextDay . '000000' . substr($stop, 14);
            
            $channelId = $programNode->getAttribute('channel');
            $channelName = $this->getChannelName($channelId);
            $programTitle = $this->getTitle($programNode);
            
            $programNode->setAttribute('stop', $fixedStop);
            
            if ($this->debug) {
                $this->logDebug("修复24:00:00格式时间 (类型2)");
                $this->logDebug("  频道id: {$channelId}");
                $this->logDebug("  频道名称: {$channelName}");
                $this->logDebug("  节目标题: {$programTitle}");
                $this->logDebug("  原始时间: {$start} -> {$stop}");
                $this->logDebug("  修复为: {$start} -> {$fixedStop}");
            }
        }
    }
    
    /**
     * 解析日期时间字符串
     * @param string $str 日期时间字符串
     * @return DateTime|false
     */
    private function parseDateTime($str) {
        // 尝试多种格式解析时间
        $formats = [
            'YmdHis O',  // 带时区
            'YmdHis',    // 不带时区
            'YmdHis T',  // 带时区缩写
            'YmdHis P'   // 带时区偏移
        ];
        
        foreach ($formats as $format) {
            $dt = DateTime::createFromFormat($format, $str);
            if ($dt !== false) {
                return $dt;
            }
        }
        
        // 尝试基本格式（14位数字）
        if (preg_match('/^(\d{14})/', $str, $matches)) {
            return DateTime::createFromFormat('YmdHis', $matches[1]);
        }
        
        return false;
    }
    
    /**
     * 合并跨午夜被分割的节目
     * @param array &$buffer 节目缓冲区
     * @param DOMElement $currentNode 当前节目节点
     * @param int &$mergesCount 合并计数
     * @return bool 是否成功合并
     */
    private function mergeSplitMidnightProgram(&$buffer, $currentNode, &$mergesCount) {
        if (empty($buffer)) {
            $buffer[] = $currentNode;
            return false;
        }
        
        $lastNode = end($buffer);
        
        $lastStop = $lastNode->getAttribute('stop');
        $currentStart = $currentNode->getAttribute('start');
        
        // 获取频道信息
        $lastChannelId = $lastNode->getAttribute('channel');
        $currentChannelId = $currentNode->getAttribute('channel');
        $lastChannelName = $this->getChannelName($lastChannelId);
        $currentChannelName = $this->getChannelName($currentChannelId);
        
        // 核心逻辑：直接比较时间字符串是否相同
        if ($lastStop !== $currentStart) {
            if ($this->debug) {
                $this->logDebug("跳过合并: 时间不连续");
                $this->logDebug("  频道id: {$lastChannelId}");
                $this->logDebug("  频道名称: {$lastChannelName}");
                $this->logDebug("  上个节目结束时间: {$lastStop}");
                $this->logDebug("  当前节目开始时间: {$currentStart}");
            }
            return false;
        }
        
        // 检查时间部分是否为午夜（00:00:00）
        $lastStopTime = substr($lastStop, 8, 6); // 提取时间部分HHMMSS
        $currentStartTime = substr($currentStart, 8, 6);
        
        if ($lastStopTime !== '000000' || $currentStartTime !== '000000') {
            if ($this->debug) {
                $this->logDebug("跳过合并: 非午夜边界");
                $this->logDebug("  频道id: {$lastChannelId}");
                $this->logDebug("  频道名称: {$lastChannelName}");
                $this->logDebug("  上个节目结束时间: {$lastStop}");
                $this->logDebug("  当前节目开始时间: {$currentStart}");
            }
            return false;
        }
        
        // 检查频道是否相同
        if ($lastChannelId !== $currentChannelId) {
            if ($this->debug) {
                $this->logDebug("跳过合并: 频道不同");
                $this->logDebug("  上个频道id: {$lastChannelId}");
                $this->logDebug("  上个频道名称: {$lastChannelName}");
                $this->logDebug("  当前频道id: {$currentChannelId}");
                $this->logDebug("  当前频道名称: {$currentChannelName}");
            }
            return false;
        }
        
        // 检查主标题是否相同
        $lastTitle = $this->getTitle($lastNode);
        $currentTitle = $this->getTitle($currentNode);
        
        if ($lastTitle !== $currentTitle) {
            if ($this->debug) {
                $this->logDebug("跳过合并: 主标题不同");
                $this->logDebug("  频道id: {$lastChannelId}");
                $this->logDebug("  频道名称: {$lastChannelName}");
                $this->logDebug("  上个标题: {$lastTitle}");
                $this->logDebug("  当前标题: {$currentTitle}");
            }
            return false;
        }
        
        // 检查副标题是否相同
        $lastSubtitle = $this->getSubtitle($lastNode);
        $currentSubtitle = $this->getSubtitle($currentNode);
        
        if ($lastSubtitle !== $currentSubtitle) {
            if ($this->debug) {
                $this->logDebug("跳过合并: 副标题不同");
                $this->logDebug("  频道id: {$lastChannelId}");
                $this->logDebug("  频道名称: {$lastChannelName}");
                $this->logDebug("  标题: {$lastTitle}");
                $this->logDebug("  上个副标题: {$lastSubtitle}");
                $this->logDebug("  当前副标题: {$currentSubtitle}");
            }
            return false;
        }
        
        // 所有条件满足，执行合并
        $currentStop = $currentNode->getAttribute('stop');
        $lastNode->setAttribute('stop', $currentStop);
        $mergesCount++;
        
        if ($this->debug) {
            $this->logDebug("成功合并跨午夜节目");
            $this->logDebug("  频道id: {$lastChannelId}");
            $this->logDebug("  频道名称: {$lastChannelName}");
            $this->logDebug("  标题: {$lastTitle}");
            if (!empty($lastSubtitle)) {
                $this->logDebug("  副标题: {$lastSubtitle}");
            }
            $lastStart = $lastNode->getAttribute('start');
            $this->logDebug("  上个节目时间范围: {$lastStart} -> {$lastStop}");
            $this->logDebug("  当前节目时间范围: {$currentStart} -> {$currentStop}");
            $this->logDebug("  合并后时间范围: {$lastStart} -> {$currentStop}");
        }
        
        return true;
    }
    
    /**
     * 获取频道名称
     * @param string $channelId 频道ID
     * @return string 频道名称
     */
    private function getChannelName($channelId) {
        if (isset($this->channels[$channelId]) && !empty($this->channels[$channelId]['display-names'])) {
            return $this->channels[$channelId]['display-names'][0];
        }
        return $channelId; // 如果找不到名称，返回ID
    }
    
    /**
     * 获取节目主标题
     * @param DOMElement $node 节目节点
     * @return string 标题
     */
    private function getTitle($node) {
        $titles = $node->getElementsByTagName('title');
        if ($titles->length > 0) {
            return trim($titles->item(0)->nodeValue);
        }
        return '';
    }
    
    /**
     * 获取节目副标题
     * @param DOMElement $node 节目节点
     * @return string 副标题
     */
    private function getSubtitle($node) {
        $subtitles = $node->getElementsByTagName('sub-title');
        if ($subtitles->length > 0) {
            return trim($subtitles->item(0)->nodeValue);
        }
        return '';
    }
    
    /**
     * 记录错误信息
     * @param string $message 错误消息
     */
    private function logError($message) {
        $prefix = $this->currentFilename ? "[{$this->currentFilename}] " : '';
        $fullMessage = $prefix . $message;
        
        if ($this->isCli) {
            file_put_contents('php://stderr', "ERROR: {$fullMessage}\n");
        } else {
            echo "<div style='color: #ff6b6b; font-weight: bold;'>{$fullMessage}</div>";
        }
        error_log($fullMessage);
    }
    
    /**
     * 记录成功信息
     * @param string $message 成功消息
     */
    private function logSuccess($message) {
        $prefix = $this->currentFilename ? "[{$this->currentFilename}] " : '';
        $fullMessage = $prefix . $message;
        
        if ($this->isCli) {
            echo "SUCCESS: {$fullMessage}\n";
        } else {
            echo "<div style='color: #4ec9b0; font-weight: bold;'>{$fullMessage}</div>";
        }
    }
    
    /**
     * 记录调试信息
     * @param string $message 调试消息
     */
    private function logDebug($message) {
        if ($this->debug) {
            $prefix = $this->currentFilename ? "[{$this->currentFilename}] " : '';
            $fullMessage = $prefix . $message;
            
            if ($this->isCli) {
                echo "DEBUG: {$fullMessage}\n";
            } else {
                echo "<div style='color: #d7ba7d;'>{$fullMessage}</div>";
            }
        }
    }
}

// 创建并运行处理器
$processor = new EnhancedDebugEPGProcessor($sources, $envConfigErrors, $isCli);
$success = $processor->processAll();

// 显示处理结果
if (!$isCli) {
    echo "<div style='margin-top: 20px; padding: 15px; background: #2d2d30; border-radius: 5px;'>";
    echo "<h3 style='color: #d7ba7d;'>处理结果:</h3>";
    echo "<ul style='list-style-type: none; padding-left: 0;'>";

    $successCount = count($processor->getSuccessfulDownloads());
    $failedCount = count($processor->getFailedDownloads());
    
    foreach ($sources as $filename => $url) {
        if (in_array($filename, $processor->getSuccessfulDownloads())) {
            $status = "✅ 成功";
            $color = "#4ec9b0";
        } else {
            $status = "❌ 失败";
            $color = "#ff6b6b";
        }
        
        if (file_exists($filename)) {
            $size = filesize($filename);
            $formattedSize = round($size / 1024, 2) . " KB";
            echo "<li style='padding: 5px 0; border-bottom: 1px dashed #3c3c3c;'>";
            echo "<span style='color: #9cdcfe;'>$filename</span> - $formattedSize - <span style='color: $color;'>$status</span>";
            
            // 显示基本文件信息
            if ($xml = simplexml_load_file($filename)) {
                $channels = count($xml->channel);
                $programmes = count($xml->programme);
                echo "<div style='font-size: 12px; color: #888;'>";
                echo "频道: $channels, 节目: $programmes";
                echo "</div>";
            }
            
            echo "</li>";
        } else {
            echo "<li style='padding: 5px 0; border-bottom: 1px dashed #3c3c3c; color: #ff6b6b;'>";
            echo "<span style='color: #ff6b6b;'>$filename</span> - 文件未生成 - <span style='color: #ff6b6b;'>❌ 失败</span>";
            echo "</li>";
        }
    }

    echo "</ul>";
    echo "<div style='margin-top: 10px;'>";
    echo "统计: 成功 {$successCount} 个, 失败 {$failedCount} 个, 总计 " . count($sources) . " 个";
    echo "</div>";
    echo "</div>";

    // 显示总体状态
    $envErrors = $processor->getEnvConfigErrors();
    $hasEnvErrors = !empty($envErrors);
    $hasDownloadErrors = $failedCount > 0;
    $hasProcessingErrors = $processor->hasErrors();
    
    if (($hasEnvErrors || $hasDownloadErrors || $hasProcessingErrors) && $successCount === 0) {
        echo "<div style='margin-top: 20px; padding: 15px; background: #4b1e1e; border-radius: 5px; color: #ff9d9d;'>";
        echo "<h3 style='color: #ff9d9d;'>处理状态: <span style='color: #ff6b6b;'>完全失败</span></h3>";
        echo "<p>所有源处理失败，无有效EPG生成</p>";
        if ($hasEnvErrors) {
            echo "<p>环境变量配置错误: " . count($envErrors) . " 个</p>";
        }
        if ($hasDownloadErrors) {
            echo "<p>下载失败: {$failedCount} 个</p>";
        }
        echo "</div>";
        $exitCode = 1;
    } elseif ($hasEnvErrors || $hasDownloadErrors || $hasProcessingErrors) {
        echo "<div style='margin-top: 20px; padding: 15px; background: #4b3e1e; border-radius: 5px; color: #ffd79d;'>";
        echo "<h3 style='color: #ffd79d;'>处理状态: <span style='color: #ffb86c;'>部分成功</span></h3>";
        echo "<p>部分源处理失败，但成功生成了 {$successCount} 个EPG文件</p>";
        if ($hasEnvErrors) {
            echo "<p>环境变量配置错误: " . count($envErrors) . " 个</p>";
        }
        if ($hasDownloadErrors) {
            echo "<p>下载失败: {$failedCount} 个</p>";
        }
        echo "</div>";
        $exitCode = 0;
    } else {
        echo "<div style='margin-top: 20px; padding: 15px; background: #1e4b1e; border-radius: 5px; color: #9dff9d;'>";
        echo "<h3 style='color: #9dff9d;'>处理状态: <span style='color: #4ec9b0;'>成功</span></h3>";
        echo "<p>所有源已成功处理</p>";
        echo "</div>";
        $exitCode = 0;
    }

    echo "</div>";
} else {
    // 命令行模式下输出简洁结果
    $successCount = count($processor->getSuccessfulDownloads());
    $failedCount = count($processor->getFailedDownloads());
    $totalFiles = $processor->getTotalFiles();
    
    if (($processor->hasErrors() || $failedCount > 0) && $successCount === 0) {
        echo "处理状态: 完全失败\n";
        echo "所有源处理失败，无有效EPG生成\n";
        $exitCode = 1;
    } elseif ($processor->hasErrors() || $failedCount > 0) {
        echo "处理状态: 部分成功\n";
        echo "下载统计: 成功 {$successCount} 个, 失败 {$failedCount} 个\n";
        if ($successCount > 0) {
            echo "成功处理: " . implode(', ', $processor->getSuccessfulDownloads()) . "\n";
        }
        if ($failedCount > 0) {
            echo "处理失败: " . implode(', ', $processor->getFailedDownloads()) . "\n";
        }
        $exitCode = 0;
    } else {
        echo "处理状态: 成功\n";
        echo "下载统计: 成功 {$successCount} 个, 失败 {$failedCount} 个\n";
        if ($successCount > 0) {
            echo "成功处理: " . implode(', ', $processor->getSuccessfulDownloads()) . "\n";
        }
        $exitCode = 0;
    }
}

// 退出并返回状态码
exit($exitCode);