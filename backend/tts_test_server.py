# TTS 音色测试服务
# 运行: .venv/bin/python tts_test_server.py
# 访问: http://localhost:8891

import base64
import json
import os

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from volcenginesdkarkruntime import AsyncArk

from app.clients.tts import tts
from app.constants import LLM_ENDPOINT_ID

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 所有可用音色（官方中文音色完整列表）
ALL_TONES = [
    # 豆包语音合成模型2.0 - 通用场景
    {"id": "zh_female_vv_uranus_bigtts", "name": "Vivi 2.0", "tag": "通用，情感变化"},
    {"id": "zh_female_xiaohe_uranus_bigtts", "name": "小何 2.0", "tag": "通用，情感变化"},
    {"id": "zh_male_m191_uranus_bigtts", "name": "云舟 2.0", "tag": "通用，情感变化"},
    {"id": "zh_male_taocheng_uranus_bigtts", "name": "小天 2.0", "tag": "通用，情感变化"},
    # 豆包语音合成模型2.0 - 视频配音
    {"id": "zh_female_xueayi_saturn_bigtts", "name": "儿童绘本", "tag": "女童/旁白，绘本"},
    {"id": "zh_male_dayi_saturn_bigtts", "name": "大壹", "tag": "男，视频配音"},
    {"id": "zh_female_mizai_saturn_bigtts", "name": "黑猫侦探社咪", "tag": "女，视频配音"},
    {"id": "zh_female_jitangnv_saturn_bigtts", "name": "鸡汤女", "tag": "女，视频配音"},
    {"id": "zh_female_meilinvyou_saturn_bigtts", "name": "魅力女友", "tag": "女，视频配音"},
    {"id": "zh_female_santongyongns_saturn_bigtts", "name": "流畅女声", "tag": "女，视频配音"},
    {"id": "zh_male_ruyayichen_saturn_bigtts", "name": "儒雅逸辰", "tag": "男，视频配音"},
    # 豆包语音合成模型2.0 - 角色扮演
    {"id": "saturn_zh_female_keainvsheng_tob", "name": "可爱女生", "tag": "女，角色扮演"},
    {"id": "saturn_zh_female_tiaopigongzhu_tob", "name": "调皮公主", "tag": "少女，调皮任性"},
    {"id": "saturn_zh_male_shuanglangshaonian_tob", "name": "爽朗少年", "tag": "少年男，开朗阳光"},
    {"id": "saturn_zh_male_tiancaitongzhuo_tob", "name": "天才同桌", "tag": "少年男，机灵好学"},
    {"id": "saturn_zh_female_cancan_tob", "name": "知性灿灿", "tag": "女，知性"},
    # 豆包语音合成模型2.0 - 客服场景
    {"id": "saturn_zh_female_qingyingduoduo_cs_tob", "name": "轻盈朵朵 2.0", "tag": "女，客服"},
    {"id": "saturn_zh_female_wenwanshanshan_cs_tob", "name": "温婉珊珊 2.0", "tag": "女，客服"},
    {"id": "saturn_zh_female_reqingaina_cs_tob", "name": "热情艾娜 2.0", "tag": "女，客服"},
    # 豆包语音合成模型1.0 - 多情感
    {"id": "zh_male_lengkugege_emo_v2_mars_bigtts", "name": "冷酷哥哥", "tag": "男，冷酷多情感"},
    {"id": "zh_female_tianxinxiaomei_emo_v2_mars_bigtts", "name": "甜心小美", "tag": "女，甜美多情感"},
    {"id": "zh_female_gaolengyujie_emo_v2_mars_bigtts", "name": "高冷御姐", "tag": "女，高冷多情感"},
    {"id": "zh_male_aojiaobazong_emo_v2_mars_bigtts", "name": "傲娇霸总", "tag": "男，傲娇多情感"},
    {"id": "zh_female_linjuayi_emo_v2_mars_bigtts", "name": "邻居阿姨", "tag": "中年女，亲切多情感"},
    {"id": "zh_male_yourougongzi_emo_v2_mars_bigtts", "name": "优柔公子", "tag": "男，优柔多情感"},
    {"id": "zh_male_ruyayichen_emo_v2_mars_bigtts", "name": "儒雅男友", "tag": "男，儒雅多情感"},
    {"id": "zh_male_junlangnanyou_emo_v2_mars_bigtts", "name": "俊朗男友", "tag": "男，俊朗多情感"},
    {"id": "zh_male_beijingxiaoye_emo_v2_mars_bigtts", "name": "北京小爷", "tag": "男，北京腔多情感"},
    {"id": "zh_female_roumeinvyou_emo_v2_mars_bigtts", "name": "柔美女友", "tag": "女，柔美多情感"},
    {"id": "zh_male_yangguangqingnian_emo_v2_mars_bigtts", "name": "阳光青年（多情感）", "tag": "男，阳光多情感"},
    {"id": "zh_female_meilinvyou_emo_v2_mars_bigtts", "name": "魅力女友（多情感）", "tag": "女，魅力多情感"},
    {"id": "zh_female_shuangkuaisisi_emo_v2_mars_bigtts", "name": "爽快思思（多情感）", "tag": "女，爽快多情感"},
    {"id": "zh_male_shenyeboke_emo_v2_mars_bigtts", "name": "深夜播客", "tag": "男，深夜播客多情感"},
    # 豆包语音合成模型1.0 - 通用场景
    {"id": "zh_female_vv_mars_bigtts", "name": "Vivi", "tag": "女，通用"},
    {"id": "zh_female_qinqienvsheng_moon_bigtts", "name": "亲切女声", "tag": "女，亲切"},
    {"id": "zh_male_qingyiyuxuan_mars_bigtts", "name": "阳光阿辰", "tag": "男，阳光"},
    {"id": "zh_male_xudong_conversation_wvae_bigtts", "name": "快乐小东", "tag": "男，活泼热情"},
    {"id": "zh_male_yuanboxiaoshu_moon_bigtts", "name": "渊博小叔", "tag": "成年男，智慧稳重"},
    {"id": "zh_female_tianmeitaozi_mars_bigtts", "name": "甜美桃子", "tag": "女，甜美"},
    {"id": "zh_female_qingxinnvsheng_mars_bigtts", "name": "清新女声", "tag": "女，清新自然"},
    {"id": "zh_female_zhixingnvsheng_mars_bigtts", "name": "知性女声", "tag": "女，知性成熟"},
    {"id": "zh_male_qingshuangnanda_mars_bigtts", "name": "清爽男大", "tag": "男，清爽"},
    {"id": "zh_female_linjianvhai_moon_bigtts", "name": "邻家女孩", "tag": "女，邻家"},
    {"id": "zh_male_yangguangqingnian_moon_bigtts", "name": "阳光青年", "tag": "男，阳光开朗"},
    {"id": "zh_female_tianmeixiaoyuan_moon_bigtts", "name": "甜美小源", "tag": "女，甜美"},
    {"id": "zh_female_qingchezizi_moon_bigtts", "name": "清澈梓梓", "tag": "女，清澈"},
    {"id": "zh_male_jieshuoxiaoming_moon_bigtts", "name": "解说小明", "tag": "男，沉稳解说"},
    {"id": "zh_female_kailangjiejie_moon_bigtts", "name": "开朗姐姐", "tag": "女，开朗活泼"},
    {"id": "zh_male_linjiananhai_moon_bigtts", "name": "邻家男孩", "tag": "男，邻家"},
    {"id": "zh_female_tianmeiyueyue_moon_bigtts", "name": "甜美悦悦", "tag": "女，甜美"},
    {"id": "zh_female_xinlingjitang_moon_bigtts", "name": "心灵鸡汤", "tag": "女，温暖治愈"},
    {"id": "zh_male_wenrouxiaoge_mars_bigtts", "name": "温柔小哥", "tag": "男，温柔"},
    {"id": "zh_female_cancan_mars_bigtts", "name": "灿灿/Shiny", "tag": "女，通用"},
    {"id": "zh_female_shuangkuaisisi_moon_bigtts", "name": "爽快思思/Skye", "tag": "女，爽朗干练"},
    {"id": "zh_male_wennuanahu_moon_bigtts", "name": "温暖阿虎/Alvin", "tag": "男，温和成熟"},
    {"id": "zh_male_shaonianzixin_moon_bigtts", "name": "少年梓辛/Brayan", "tag": "少年男"},
    {"id": "zh_female_wenrouxiaoya_moon_bigtts", "name": "温柔小雅", "tag": "女，温柔成熟"},
    {"id": "zh_female_tiexinnvsheng_mars_bigtts", "name": "贴心女声/Candy", "tag": "女，亲切稳重"},
    {"id": "zh_female_mengyatou_mars_bigtts", "name": "萌丫头/Cutey", "tag": "女童，活泼可爱"},
    # 豆包语音合成模型1.0 - 角色扮演
    {"id": "ICL_zh_male_shuanglangshaonian_tob", "name": "爽朗少年", "tag": "少年男，开朗"},
    {"id": "ICL_zh_male_tiancaitongzhuo_tob", "name": "天才同桌", "tag": "少年男，机灵"},
    {"id": "ICL_zh_male_hanhoudunshi_tob", "name": "憨厚敦实", "tag": "成年男，朴实憨厚"},
    {"id": "ICL_zh_male_youmodaye_tob", "name": "幽默大爷", "tag": "老年男，幽默慈祥"},
    {"id": "ICL_zh_female_wuxi_tob", "name": "元气甜妹", "tag": "少女，元气甜美"},
    {"id": "ICL_zh_male_badaozongcai_v1_tob", "name": "霸道总裁", "tag": "男，霸道"},
    {"id": "ICL_zh_male_guaogongzi_v1_tob", "name": "孤傲公子", "tag": "男，孤傲"},
    {"id": "ICL_zh_male_aomanqingnian_tob", "name": "傲慢青年", "tag": "男，傲慢"},
    {"id": "ICL_zh_male_cujingnansheng_tob", "name": "醋精男生", "tag": "男，爱吃醋"},
    {"id": "ICL_zh_male_sajiaonanyou_tob", "name": "撒娇男友", "tag": "男，撒娇"},
    {"id": "ICL_zh_male_wenrounanyou_tob", "name": "温柔男友", "tag": "男，温柔"},
    {"id": "ICL_zh_male_wenshunshaonian_tob", "name": "温顺少年", "tag": "少年男，温顺"},
    {"id": "ICL_zh_male_naigounanyou_tob", "name": "粘人男友", "tag": "男，粘人"},
    {"id": "ICL_zh_male_huoponanyou_tob", "name": "活泼男友", "tag": "男，活泼"},
    {"id": "ICL_zh_male_tianxinanyou_tob", "name": "甜系男友", "tag": "男，甜系"},
    {"id": "ICL_zh_male_huoliqingnian_tob", "name": "活力青年", "tag": "男，活力"},
    {"id": "ICL_zh_male_kailangqingnian_tob", "name": "开朗青年", "tag": "男，开朗"},
    {"id": "ICL_zh_male_lengmoxiongzhang_tob", "name": "冷漠兄长", "tag": "男，冷漠"},
    {"id": "ICL_zh_male_pianpiangongzi_tob", "name": "翩翩公子", "tag": "男，翩翩"},
    {"id": "ICL_zh_male_mengdongqingnian_tob", "name": "懵懂青年", "tag": "男，懵懂"},
    {"id": "ICL_zh_male_bingjiaoshaonian_tob", "name": "病娇少年", "tag": "少年男，病娇"},
    {"id": "ICL_zh_male_bingjiaonanyou_tob", "name": "病娇男友", "tag": "男，病娇"},
    {"id": "ICL_zh_male_bingruoshaonian_tob", "name": "病弱少年", "tag": "少年男，病弱"},
    {"id": "ICL_zh_male_yiqishaonian_tob", "name": "意气少年", "tag": "少年男，意气"},
    {"id": "ICL_zh_male_ganjingshaonian_tob", "name": "干净少年", "tag": "少年男，干净"},
    {"id": "ICL_zh_male_lengmonanyou_tob", "name": "冷漠男友", "tag": "男，冷漠"},
    {"id": "ICL_zh_male_jingyingqingnian_tob", "name": "精英青年", "tag": "男，精英"},
    {"id": "ICL_zh_male_rexueshaonian_tob", "name": "热血少年", "tag": "少年男，热血"},
    {"id": "ICL_zh_male_qingshuangshaonian_tob", "name": "清爽少年", "tag": "少年男，清爽"},
    {"id": "ICL_zh_male_zhongerqingnian_tob", "name": "中二青年", "tag": "男，中二"},
    {"id": "ICL_zh_male_lingyunqingnian_tob", "name": "凌云青年", "tag": "男，凌云"},
    {"id": "ICL_zh_male_zifuqingnian_tob", "name": "自负青年", "tag": "男，自负"},
    {"id": "ICL_zh_male_bujiqingnian_tob", "name": "不羁青年", "tag": "男，不羁"},
    {"id": "ICL_zh_male_ruyajunzi_tob", "name": "儒雅君子", "tag": "男，儒雅"},
    {"id": "ICL_zh_male_diyinchenyu_tob", "name": "低音沉郁", "tag": "男，低沉"},
    {"id": "ICL_zh_male_lenglianxueba_tob", "name": "冷脸学霸", "tag": "男，冷酷学霸"},
    {"id": "ICL_zh_male_ruyazongcai_tob", "name": "儒雅总裁", "tag": "男，儒雅总裁"},
    {"id": "ICL_zh_male_shenchenzongcai_tob", "name": "深沉总裁", "tag": "男，深沉总裁"},
    {"id": "ICL_zh_male_xiaohouye_tob", "name": "小侯爷", "tag": "男，古风侯爷"},
    {"id": "ICL_zh_male_gugaogongzi_tob", "name": "孤高公子", "tag": "男，孤高"},
    {"id": "ICL_zh_male_zhangjianjunzi_tob", "name": "仗剑君子", "tag": "男，仗剑"},
    {"id": "ICL_zh_male_wenrunxuezhe_tob", "name": "温润学者", "tag": "男，温润"},
    {"id": "ICL_zh_male_qinqieqingnian_tob", "name": "亲切青年", "tag": "男，亲切"},
    {"id": "ICL_zh_male_wenrouxuezhang_tob", "name": "温柔学长", "tag": "男，温柔学长"},
    {"id": "ICL_zh_male_gaolengzongcai_tob", "name": "高冷总裁", "tag": "男，高冷总裁"},
    {"id": "ICL_zh_male_lengjungaozhi_tob", "name": "冷峻高智", "tag": "男，冷峻"},
    {"id": "ICL_zh_male_chanruoshaoye_tob", "name": "孱弱少爷", "tag": "男，孱弱"},
    {"id": "ICL_zh_male_zixinqingnian_tob", "name": "自信青年", "tag": "男，自信"},
    {"id": "ICL_zh_male_qingseqingnian_tob", "name": "青涩青年", "tag": "男，青涩"},
    {"id": "ICL_zh_male_xuebatongzhuo_tob", "name": "学霸同桌", "tag": "男，学霸"},
    {"id": "ICL_zh_male_lengaozongcai_tob", "name": "冷傲总裁", "tag": "男，冷傲"},
    {"id": "ICL_zh_male_yuanqishaonian_tob", "name": "元气少年", "tag": "少年男，元气"},
    {"id": "ICL_zh_male_satuoqingnian_tob", "name": "洒脱青年", "tag": "男，洒脱"},
    {"id": "ICL_zh_male_zhishuaiqingnian_tob", "name": "直率青年", "tag": "男，直率"},
    {"id": "ICL_zh_male_siwenqingnian_tob", "name": "斯文青年", "tag": "男，斯文"},
    {"id": "ICL_zh_male_junyigongzi_tob", "name": "俊逸公子", "tag": "男，俊逸"},
    {"id": "ICL_zh_male_zhangjianxiake_tob", "name": "仗剑侠客", "tag": "男，侠客"},
    {"id": "ICL_zh_male_jijiaozhineng_tob", "name": "机甲智能", "tag": "男，机甲"},
    {"id": "zh_male_naiqimengwa_mars_bigtts", "name": "奶气萌娃", "tag": "男童，幼小可爱"},
    {"id": "zh_female_gaolengyujie_moon_bigtts", "name": "高冷御姐", "tag": "女，成熟冷静"},
    {"id": "zh_male_aojiaobazong_moon_bigtts", "name": "傲娇霸总", "tag": "男，傲娇"},
    {"id": "zh_female_meilinvyou_moon_bigtts", "name": "魅力女友", "tag": "女，魅力"},
    {"id": "zh_male_shenyeboke_moon_bigtts", "name": "深夜播客", "tag": "男，深夜播客"},
    {"id": "zh_female_sajiaonvyou_moon_bigtts", "name": "柔美女友", "tag": "女，柔美撒娇"},
    {"id": "zh_female_yuanqinvyou_moon_bigtts", "name": "撒娇学妹", "tag": "女，撒娇"},
    {"id": "ICL_zh_female_bingruoshaonv_tob", "name": "病弱少女", "tag": "少女，病弱"},
    {"id": "ICL_zh_female_huoponvhai_tob", "name": "活泼女孩", "tag": "女孩，活泼"},
    {"id": "zh_male_dongfanghaoran_moon_bigtts", "name": "东方浩然", "tag": "男，成熟深沉"},
    {"id": "ICL_zh_male_lvchaxiaoge_tob", "name": "绿茶小哥", "tag": "男，绿茶"},
    {"id": "ICL_zh_female_jiaoruoluoli_tob", "name": "娇弱萝莉", "tag": "女，娇弱"},
    {"id": "ICL_zh_male_lengdanshuli_tob", "name": "冷淡疏离", "tag": "男，冷淡"},
    {"id": "ICL_zh_female_huopodiaoman_tob", "name": "活泼刁蛮", "tag": "女，活泼刁蛮"},
    {"id": "ICL_zh_male_guzhibingjiao_tob", "name": "固执病娇", "tag": "男，固执病娇"},
    {"id": "ICL_zh_male_sajiaonianren_tob", "name": "撒娇粘人", "tag": "男，撒娇粘人"},
    {"id": "ICL_zh_female_aomanjiaosheng_tob", "name": "傲慢娇声", "tag": "女，傲慢娇声"},
    {"id": "ICL_zh_male_xiaosasuixing_tob", "name": "潇洒随性", "tag": "男，潇洒"},
    {"id": "ICL_zh_male_guiyishenmi_tob", "name": "诡异神秘", "tag": "男，神秘"},
    {"id": "ICL_zh_male_ruyacaijun_tob", "name": "儒雅才俊", "tag": "男，儒雅才俊"},
    {"id": "ICL_zh_male_zhengzhiqingnian_tob", "name": "正直青年", "tag": "男，正直"},
    {"id": "ICL_zh_female_jiaohannvwang_tob", "name": "娇憨女王", "tag": "女，娇憨"},
    {"id": "ICL_zh_female_bingjiaomengmei_tob", "name": "病娇萌妹", "tag": "女，病娇"},
    {"id": "ICL_zh_male_qingsenaigou_tob", "name": "青涩小生", "tag": "男，青涩"},
    {"id": "ICL_zh_male_chunzhenxuedi_tob", "name": "纯真学弟", "tag": "男，纯真"},
    {"id": "ICL_zh_male_youroubangzhu_tob", "name": "优柔帮主", "tag": "男，优柔"},
    {"id": "ICL_zh_male_yourougongzi_tob", "name": "优柔公子", "tag": "男，优柔"},
    {"id": "ICL_zh_female_tiaopigongzhu_tob", "name": "调皮公主", "tag": "少女，调皮任性"},
    {"id": "ICL_zh_male_tiexinnanyou_tob", "name": "贴心男友", "tag": "男，贴心"},
    {"id": "ICL_zh_male_shaonianjiangjun_tob", "name": "少年将军", "tag": "少年男，将军"},
    {"id": "ICL_zh_male_bingjiaogege_tob", "name": "病娇哥哥", "tag": "男，病娇"},
    {"id": "ICL_zh_male_xuebanantongzhuo_tob", "name": "学霸男同桌", "tag": "男，学霸"},
    {"id": "ICL_zh_male_youmoshushu_tob", "name": "幽默叔叔", "tag": "男，幽默叔叔"},
    {"id": "ICL_zh_female_jiaxiaozi_tob", "name": "假小子", "tag": "女，假小子"},
    {"id": "ICL_zh_male_wenrounantongzhuo_tob", "name": "温柔男同桌", "tag": "男，温柔"},
    {"id": "ICL_zh_male_lengjunshangsi_tob", "name": "冷峻上司", "tag": "男，冷峻上司"},
    {"id": "ICL_zh_female_nuanxinxuejie_tob", "name": "暖心学姐", "tag": "女，暖心"},
    {"id": "ICL_zh_female_keainvsheng_tob", "name": "可爱女生", "tag": "女，可爱"},
    {"id": "ICL_zh_female_chengshujiejie_tob", "name": "成熟姐姐", "tag": "女，成熟"},
    {"id": "ICL_zh_female_bingjiaojiejie_tob", "name": "病娇姐姐", "tag": "女，病娇"},
    {"id": "ICL_zh_female_wumeiyujie_tob", "name": "妩媚御姐", "tag": "女，妩媚"},
    {"id": "ICL_zh_female_aojiaonvyou_tob", "name": "傲娇女友", "tag": "女，傲娇"},
    {"id": "ICL_zh_female_tiexinnvyou_tob", "name": "贴心女友", "tag": "女，贴心"},
    {"id": "ICL_zh_female_xingganyujie_tob", "name": "性感御姐", "tag": "女，性感"},
    {"id": "ICL_zh_male_bingjiaodidi_tob", "name": "病娇弟弟", "tag": "男，病娇弟弟"},
    {"id": "ICL_zh_male_aomanshaoye_tob", "name": "傲慢少爷", "tag": "男，傲慢少爷"},
    {"id": "ICL_zh_male_cujingnanyou_tob", "name": "醋精男友", "tag": "男，爱吃醋"},
    {"id": "ICL_zh_male_fengfashaonian_tob", "name": "风发少年", "tag": "少年男，意气风发"},
    {"id": "ICL_zh_male_cixingnansang_tob", "name": "磁性男嗓", "tag": "男，磁性"},
    {"id": "ICL_zh_male_chengshuzongcai_tob", "name": "成熟总裁", "tag": "男，成熟总裁"},
    {"id": "ICL_zh_male_aojiaojingying_tob", "name": "傲娇精英", "tag": "男，傲娇精英"},
    {"id": "ICL_zh_male_aojiaogongzi_tob", "name": "傲娇公子", "tag": "男，傲娇公子"},
    {"id": "ICL_zh_male_badaoshaoye_tob", "name": "霸道少爷", "tag": "男，霸道少爷"},
    {"id": "ICL_zh_male_fuheigongzi_tob", "name": "腹黑公子", "tag": "男，腹黑"},
    # 豆包语音合成模型1.0 - IP仿音
    {"id": "zh_female_popo_mars_bigtts", "name": "婆婆", "tag": "老年女，慈祥温暖"},
    {"id": "zh_male_tiancaitongsheng_mars_bigtts", "name": "天才童声", "tag": "男童，聪明活泼"},
    {"id": "zh_male_xionger_mars_bigtts", "name": "熊二", "tag": "卡通男，憨厚搞笑"},
    {"id": "zh_female_peiqi_mars_bigtts", "name": "佩奇猪", "tag": "卡通女，天真烂漫"},
    {"id": "zh_female_yingtaowanzi_mars_bigtts", "name": "樱桃丸子", "tag": "女童，俏皮可爱"},
    {"id": "zh_male_sunwukong_mars_bigtts", "name": "猴哥", "tag": "卡通男，神通广大"},
    # 豆包语音合成模型1.0 - 有声阅读
    {"id": "zh_male_ruyaqingnian_mars_bigtts", "name": "儒雅青年", "tag": "男，儒雅知性"},
    {"id": "zh_male_baqiqingshu_mars_bigtts", "name": "霸气青叔", "tag": "成年男，霸气威严"},
    {"id": "zh_male_qingcang_mars_bigtts", "name": "擎苍", "tag": "男，有声阅读"},
    {"id": "zh_male_yangguangqingnian_mars_bigtts", "name": "活力小哥", "tag": "男，活力"},
    {"id": "zh_female_gufengshaoyu_mars_bigtts", "name": "古风少御", "tag": "女，古风"},
    {"id": "zh_female_wenroushunv_mars_bigtts", "name": "温柔淑女", "tag": "女，温婉成熟"},
    {"id": "zh_male_fanjuanqingnian_mars_bigtts", "name": "反卷青年", "tag": "男，反卷"},
    # 豆包语音合成模型1.0 - 视频配音
    {"id": "zh_female_shaoergushi_mars_bigtts", "name": "少儿故事", "tag": "女，故事旁白"},
    {"id": "zh_female_qiaopinvsheng_mars_bigtts", "name": "俏皮女声", "tag": "女，俏皮"},
    {"id": "zh_female_jitangmeimei_mars_bigtts", "name": "鸡汤妹妹/Hope", "tag": "女，鸡汤"},
    {"id": "ICL_zh_female_heainainai_tob", "name": "和蔼奶奶", "tag": "老年女，和蔼"},
    {"id": "ICL_zh_female_linjuayi_tob", "name": "邻居阿姨", "tag": "中年女，亲切温和"},
    # 豆包语音合成模型1.0 - 客服场景
    {"id": "ICL_zh_female_lixingyuanzi_cs_tob", "name": "理性圆子", "tag": "女，客服理性"},
    {"id": "ICL_zh_female_qingtiantaotao_cs_tob", "name": "清甜桃桃", "tag": "女，客服清甜"},
    {"id": "ICL_zh_female_qingxixiaoxue_cs_tob", "name": "清晰小雪", "tag": "女，客服清晰"},
    {"id": "ICL_zh_female_qingtianmeimei_cs_tob", "name": "清甜莓莓", "tag": "女，客服清甜"},
    {"id": "ICL_zh_female_kailangtingting_cs_tob", "name": "开朗婷婷", "tag": "女，客服开朗"},
    {"id": "ICL_zh_male_qingxinmumu_cs_tob", "name": "清新沐沐", "tag": "男，客服清新"},
    {"id": "ICL_zh_male_shuanglangxiaoyang_cs_tob", "name": "爽朗小阳", "tag": "男，客服爽朗"},
    {"id": "ICL_zh_male_qingxinbobo_cs_tob", "name": "清新波波", "tag": "男，客服清新"},
    {"id": "ICL_zh_female_wenwanshanshan_cs_tob", "name": "温婉珊珊", "tag": "女，客服温婉"},
    {"id": "ICL_zh_female_tianmeixiaoyu_cs_tob", "name": "甜美小雨", "tag": "女，客服甜美"},
    {"id": "ICL_zh_female_reqingaina_cs_tob", "name": "热情艾娜", "tag": "女，客服热情"},
    {"id": "ICL_zh_female_tianmeixiaoju_cs_tob", "name": "甜美小橘", "tag": "女，客服甜美"},
    {"id": "ICL_zh_male_chenwenmingzai_cs_tob", "name": "沉稳明仔", "tag": "男，客服沉稳"},
    {"id": "ICL_zh_male_qinqiexiaozhuo_cs_tob", "name": "亲切小卓", "tag": "男，客服亲切"},
    {"id": "ICL_zh_female_lingdongxinxin_cs_tob", "name": "灵动欣欣", "tag": "女，客服灵动"},
    {"id": "ICL_zh_female_guaiqiaokeer_cs_tob", "name": "乖巧可儿", "tag": "女，客服乖巧"},
    {"id": "ICL_zh_female_nuanxinqianqian_cs_tob", "name": "暖心茜茜", "tag": "女，客服暖心"},
    {"id": "ICL_zh_female_ruanmengtuanzi_cs_tob", "name": "软萌团子", "tag": "女，客服软萌"},
    {"id": "ICL_zh_male_yangguangyangyang_cs_tob", "name": "阳光洋洋", "tag": "男，客服阳光"},
    {"id": "ICL_zh_female_ruanmengtangtang_cs_tob", "name": "软萌糖糖", "tag": "女，客服软萌"},
    {"id": "ICL_zh_female_xiuliqianqian_cs_tob", "name": "秀丽倩倩", "tag": "女，客服秀丽"},
    {"id": "ICL_zh_female_kaixinxiaohong_cs_tob", "name": "开心小鸿", "tag": "女，客服开心"},
    {"id": "ICL_zh_female_qingyingduoduo_cs_tob", "name": "轻盈朵朵", "tag": "女，客服轻盈"},
]

TONE_SELECT_PROMPT = """你是音色选择专家，根据用户提供的文案内容和角色/场景特点，从给定音色列表中选择最合适的音色ID。

# 音色列表
{tone_list}

# 要求
- 只返回音色ID，不要任何解释
- 必须从列表中选择

# 文案
{text}

# 特点
{description}"""


class SelectToneRequest(BaseModel):
    text: str
    description: str


class TTSRequest(BaseModel):
    text: str
    tone: str


@app.get("/tones")
async def get_tones():
    return ALL_TONES


@app.post("/select-tone")
async def select_tone(req: SelectToneRequest):
    tone_list = "\n".join([f"{t['id']}  {t['name']}（{t['tag']}）" for t in ALL_TONES])
    prompt = TONE_SELECT_PROMPT.format(
        tone_list=tone_list,
        text=req.text,
        description=req.description,
    )
    client = AsyncArk(api_key=os.getenv("ARK_API_KEY"))
    resp = await client.chat.completions.create(
        model=LLM_ENDPOINT_ID,
        messages=[{"role": "user", "content": prompt}],
    )
    tone_id = resp.choices[0].message.content.strip()
    # 查找音色名称
    tone_info = next((t for t in ALL_TONES if t["id"] == tone_id), None)
    return {"tone": tone_id, "info": tone_info}


@app.post("/tts")
async def synthesize(req: TTSRequest):
    audio_bytes = await tts(req.text, params={}, speaker=req.tone)
    audio_b64 = base64.b64encode(audio_bytes).decode()
    return {"audio": audio_b64}


@app.get("/", response_class=HTMLResponse)
async def index():
    with open(os.path.join(os.path.dirname(__file__), "tts_test.html"), encoding="utf-8") as f:
        return f.read()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8891)
