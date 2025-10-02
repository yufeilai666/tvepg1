<?php
header('Content-Type: text/plain; charset=UTF-8');
ini_set("max_execution_time", "900000000");
//htaccess php_value max_execution_time 0;
ini_set('date.timezone','Asia/Shanghai');
$fp="epgguangxi.xml";//压缩版本的扩展名后加.gz
$dt1=date('Ymd');//獲取當前日期
$dt2=date('Ymd',time()+24*3600);//第二天日期
$dt21=date('Ymd',time()+48*3600);//第三天日期
$dt22=date('Ymd',time()-24*3600);//前天日期
$dt3=date('Ymd',time()+7*24*3600);
$dt4=date("Y/n/j");//獲取當前日期
$dt5=date('Y/n/j',time()+24*3600);//第二天日期
$dt7=date('Y');//獲取當前日期
$dt6=date('YmdHi',time());
$dt11=date('Y-m-d');
$time111=strtotime(date('Y-m-d',time()))*1000;
$dt12=date('Y-m-d',time()+24*3600);
$dt10=date('Y-m-d',time()-24*3600);
$w1=date("w");//當前第幾周
if ($w1<'1') {$w1=7;}
$w2=$w1+1;
function match_string($matches)
{
    return  iconv('UCS-2', 'UTF-8', pack('H4', $matches[1]));
    //return  iconv('UCS-2BE', 'UTF-8', pack('H4', $matches[1]));
    //return  iconv('UCS-2LE', 'UTF-8', pack('H4', $matches[1]));
}
function convertMillisToDateTime($millis, $timezone = 'Asia/Shanghai') {
    // 将毫秒转换为秒（取整数部分）
    $seconds = floor($millis / 1000);
    
    // 创建DateTime对象（基于UTC时间）
    $date = new DateTime("@$seconds", new DateTimeZone('UTC'));
    
    // 设置目标时区
    $date->setTimezone(new DateTimeZone($timezone));
    
    // 返回格式化后的日期时间字符串
    return $date->format('YmdHis');
}


function compress_html($string) {
    $string = str_replace("\r", '', $string); //清除换行符
    $string = str_replace("\n", '', $string); //清除换行符
    $string = str_replace("\t", '', $string); //清除制表符
    return $string;
}

function escape($str) 
{ 
preg_match_all("/[\x80-\xff].|[\x01-\x7f]+/",$str,$r); 
$ar = $r[0]; 
foreach($ar as $k=>$v) 
{ 
if(ord($v[0]) < 128) 
$ar[$k] = rawurlencode($v); 
else 
$ar[$k] = "%u".bin2hex(iconv("UTF-8","UCS-2",$v)); 
} 
return join("",$ar); 
} 




//適合php7以上
function replace_unicode_escape_sequence($match)
{       
		return mb_convert_encoding(pack('H*', $match[1]), 'UTF-8', 'UCS-2BE');     
}          



$chn="<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<!DOCTYPE tv SYSTEM \"http://api.torrent-tv.ru/xmltv.dtd\">\n<tv generator-info-name=\"秋哥綜合\" generator-info-url=\"https://www.tdm.com.mo/c_tv/?ch=Satellite\">\n";
$id26=101070;//起始节目编号
$cid26=array(
 
 array('广西卫视','广西卫视'),

 array('综艺旅游频道','广西综艺旅游频道'),
 array('都市频道','广西都市频道'),
 array('新闻频道','广西新闻频道'),
 array('影视频道','广西影视频道'),
 array('国际频道','广西国际频道'),
 array('乐思购频道','广西乐思购频道'),



);

$nid26=sizeof($cid26);
for ($idm26 = 1; $idm26 <= $nid26; $idm26++){
 $idd26=$id26+$idm26;
   $chn.="<channel id=\"".$cid26[$idm26-1][1]."\"><display-name lang=\"zh\">".$cid26[$idm26-1][1]."</display-name></channel>\n";
         
}

for ($idm26 = 1; $idm26 <= $nid26; $idm26++){

          
$url26='https://api2019.gxtv.cn/memberApi/programList/selectListByChannelId';
$idd26=$id26+$idm26;
$postfile26='channelName='.$cid26[$idm26-1][0].'&dateStr='.$dt11.'&programName=&deptId=0a509685ba1a11e884e55cf3fc49331c&platformId=bd7d620a502d43c09b35469b3cd8c211';

$ch26 = curl_init ();
curl_setopt ( $ch26, CURLOPT_URL, $url26 );
//curl_setopt ( $ch26, CURLOPT_HEADER, $hea );
curl_setopt($ch26,CURLOPT_SSL_VERIFYPEER,false);
curl_setopt($ch26,CURLOPT_SSL_VERIFYHOST,false);
curl_setopt ( $ch26, CURLOPT_RETURNTRANSFER, 1 );
curl_setopt ( $ch26, CURLOPT_POST, 1 );
curl_setopt ( $ch26, CURLOPT_POSTFIELDS, $postfile26 );

curl_setopt($ch26, CURLOPT_HTTPHEADER, array(
'Host: api2019.gxtv.cn',
'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:142.0) Gecko/20100101 Firefox/142.0',

'Accept-Language: zh-TW,zh;q=0.8,en-US;q=0.5,en;q=0.3',
'Accept-Encoding: gzip, deflate, br, zstd',
'Content-Type: application/x-www-form-urlencoded; charset=UTF-8',
'Authorization: ',
//Content-Length: 164
'Origin: https://program.gxtv.cn',
'Connection: keep-alive',
'Referer: https://program.gxtv.cn/',

'Priority: u=0',
)
);
curl_setopt($ch26,CURLOPT_ENCODING,'Vary: Accept-Encoding');
    $re26 = curl_exec($ch26);
    $re26=str_replace('&','&amp;',$re26);
   curl_close($ch26);

//print $re26;
//}

preg_match_all('|"programName":"(.*?)",|i',$re26,$um26,PREG_SET_ORDER);//播放節目

preg_match_all('|"programTime":"(.*?)"|i',$re26,$un26,PREG_SET_ORDER);//播放時間

//print_r($um26);
//print_r($un26);


$trm26=count($um26);
  for ($k26 = 1; $k26 <=$trm26-2 ; $k26++) {  

   $chn.="<programme start=\"".str_replace(' ','',str_replace(':','',str_replace('-','',$un26[$k26-1][1]))).' +0800'."\" stop=\"".str_replace(' ','',str_replace(':','',str_replace('-','',$un26[$k26][1]))).' +0800'."\" channel=\"".$cid26[$idm26-1][1]."\">\n<title lang=\"zh\">".$um26[$k26][1]."</title>\n<desc lang=\"zh\"> </desc>\n</programme>\n";
                 
}
  
   //$chn.="<programme start=\"".str_replace(' ','',str_replace(':','',str_replace('-','',$un26[$trm26-1][1]))).' +0800'."\" stop=\"".str_replace(' ','',str_replace(':','',str_replace('-','',$un26[$k26][1]))).' +0800'."\" channel=\"".$cid26[$idm26-1][1]."\">\n<title lang=\"zh\">".$um26[$k26][1]."</title>\n<desc lang=\"zh\"> </desc>\n</programme>\n";




$postfile261='channelName='.$cid26[$idm26-1][0].'&dateStr='.$dt12.'&programName=&deptId=0a509685ba1a11e884e55cf3fc49331c&platformId=bd7d620a502d43c09b35469b3cd8c211';

$ch261 = curl_init ();
curl_setopt ( $ch261, CURLOPT_URL, $url26 );
//curl_setopt ( $ch261, CURLOPT_HEADER, $hea );
curl_setopt($ch261,CURLOPT_SSL_VERIFYPEER,false);
curl_setopt($ch261,CURLOPT_SSL_VERIFYHOST,false);
curl_setopt ( $ch261, CURLOPT_RETURNTRANSFER, 1 );
curl_setopt ( $ch261, CURLOPT_POST, 1 );
curl_setopt ( $ch261, CURLOPT_POSTFIELDS, $postfile261 );

curl_setopt($ch261, CURLOPT_HTTPHEADER, array(
'Host: api2019.gxtv.cn',
'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:142.0) Gecko/20100101 Firefox/142.0',

'Accept-Language: zh-TW,zh;q=0.8,en-US;q=0.5,en;q=0.3',
'Accept-Encoding: gzip, deflate, br, zstd',
'Content-Type: application/x-www-form-urlencoded; charset=UTF-8',
'Authorization: ',
//Content-Length: 164
'Origin: https://program.gxtv.cn',
'Connection: keep-alive',
'Referer: https://program.gxtv.cn/',

'Priority: u=0',
)
);
curl_setopt($ch261,CURLOPT_ENCODING,'Vary: Accept-Encoding');
    $re261 = curl_exec($ch261);
    $re261=str_replace('&','&amp;',$re261);
   curl_close($ch261);

//print $re26;
//}

preg_match_all('|"programName":"(.*?)",|i',$re261,$um261,PREG_SET_ORDER);//播放節目

preg_match_all('|"programTime":"(.*?)"|i',$re261,$un261,PREG_SET_ORDER);//播放時間

//print_r($um26);
//print_r($un26);


$trm261=count($um261);


$chn.="<programme start=\"".str_replace(' ','',str_replace(':','',str_replace('-','',$un26[$trm26-1][1]))).' +0800'."\" stop=\"".str_replace(' ','',str_replace(':','',str_replace('-','',$un261[0][1]))).' +0800'."\" channel=\"".$cid26[$idm26-1][1]."\">\n<title lang=\"zh\">".$um26[$trm26-1][1]."</title>\n<desc lang=\"zh\"> </desc>\n</programme>\n";

  for ($k261 = 1; $k261 <=$trm261-2 ; $k261++) {  

   $chn.="<programme start=\"".str_replace(' ','',str_replace(':','',str_replace('-','',$un261[$k261-1][1]))).' +0800'."\" stop=\"".str_replace(' ','',str_replace(':','',str_replace('-','',$un261[$k261][1]))).' +0800'."\" channel=\"".$cid26[$idm26-1][1]."\">\n<title lang=\"zh\">".$um261[$k261-1][1]."</title>\n<desc lang=\"zh\"> </desc>\n</programme>\n";
                 
}

  $chn.="<programme start=\"".str_replace(' ','',str_replace(':','',str_replace('-','',$un261[$trm261-1][1]))).' +0800'."\" stop=\"".$dt2.'235900 +0800'."\" channel=\"".$cid26[$idm26-1][1]."\">\n<title lang=\"zh\">".$um261[$k261][1]."</title>\n<desc lang=\"zh\"> </desc>\n</programme>\n";

}
$chn.="</tv>\n";
//写入文件。这里一次性写入，可以自己分次写入操作
file_put_contents($fp, $chn);
?>
