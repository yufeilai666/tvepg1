<?php
// 要刪除的頻道 ID 列表
$channelsToRemove = ['浙江卫视','家家购物', '好享购物','央广购物','风云足球','央视台球','兵器科技','世界地理','女性时尚','高尔夫网球','怀旧剧场','风云剧场','第一剧场','风云音乐','央视文化精品','CCTV-1','东方购物-1','东方购物-2','CCTV-4K','CCTV-4K']; // 替換為你要刪除的頻道 ID

// 讀取 XML 文件
$xmlFile = 'epgshanghai.xml';


if (!file_exists($xmlFile)) {
    die("文件不存在：$xmlFile");
}

// 載入 XML
$xml = simplexml_load_file($xmlFile);
if (!$xml) {
    die("無法載入 XML 文件。");
}

// 使用 DOM 操作以便於刪除節點
$dom = new DOMDocument();
$dom->preserveWhiteSpace = false;
$dom->formatOutput = true;
$dom->load($xmlFile);

// 刪除 <channel> 節點
$xpath = new DOMXPath($dom);
foreach ($channelsToRemove as $channelId) {
    // 刪除 <channel> 節點
    foreach ($xpath->query("//channel[@id='$channelId']") as $node) {
        $node->parentNode->removeChild($node);
    }

    // 刪除 <programme> 節點
    foreach ($xpath->query("//programme[@channel='$channelId']") as $node) {
        $node->parentNode->removeChild($node);
    }
}

// 保存為新文件
$newFile = 'epgnewshanghai.xml';
if ($dom->save($newFile)) {
    echo "處理完成，新文件已保存為：$newFile";
} else {
    echo "保存文件時出錯。";
}
?>
