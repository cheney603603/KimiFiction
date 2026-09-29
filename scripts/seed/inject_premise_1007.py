"""
《修真大佬重返都市》前50章·番茄文风版 —— 注入 workflow_state + 数据库（小说1007）
用法: cd backend && python _inject_premise_v2.py
"""
import asyncio, io, json, os, sys

os.chdir(r"D:\119selfy\KimiFiction\backend")
sys.path.insert(0, r"D:\119selfy\KimiFiction\backend")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

NOVEL_ID = 1007

WORLD_SETTING = {
    "world_name": "昆仑都市",
    "overview": (
        "灵气复苏初年的华夏都市。表面高楼林立，暗地里武道世家、古武门派与隐世仙道并存，"
        "国家以镇国龙碑维系秩序，各大世家组成天元协会代行管理，元婴就是现实的天花板。"
        "主角林霄携前世返虚境的记忆、修为尽失地回到高考后的故城，靠归墟戒连通两界、"
        "靠前世的眼光在灵气大潮里抢先落子，悄然改写整个时代的牌桌。"
    ),
    "genre_type": "都市修真",
    "power_systems": [
        {"name": "武道体系", "description": "明劲、暗劲、化劲、宗师、大宗师，都市主流路径。"},
        {"name": "仙道境界", "description": "炼气、筑基、金丹、元婴、化神、炼虚、合体、大乘、渡劫。元婴即当代峰顶，化神以上受龙碑压制。"},
        {"name": "归墟戒", "description": "主角的空间项链，连通地球与修真界，可双向储物、兑换灵材；现实一日，修真界一月。"},
        {"name": "灵力与法则", "description": "灵气复苏为百年大势，主角无境界瓶颈，灵力够即可破境。"},
    ],
    "social_structure": {
        "阶层": ["普通市民", "武馆弟子", "世家子弟", "协会长老", "顶尖强者"],
        "main_factions": [
            {"name": "天元协会", "type": "faction", "leader": "盟主·沈惊鸿", "territory": "华夏全域，分东南西北四大分部",
             "ideology": "镇国龙碑下维持秩序，平衡世家与散修", "enemies": ["星罗门"], "allies": ["朱雀阁"]},
            {"name": "星罗门", "type": "faction", "leader": "阴无咎", "territory": "西南深山",
             "ideology": "夺灵气为大业，视法规为桎梏", "enemies": ["天元协会"]},
            {"name": "北方武家", "type": "faction", "leader": "武镇岳", "territory": "燕北武城",
             "ideology": "武道世家至上，打压散修"},
            {"name": "朱雀阁", "type": "faction", "leader": "温道玄", "territory": "南都伏龙山",
             "ideology": "隐世传承，执掌诸多灵脉秘藏", "allies": ["天元协会"]},
            {"name": "海晏武馆联盟", "type": "faction", "leader": "霍青山", "territory": "江海市",
             "ideology": "草根武者抱团，被主角一手扶起", "allies": ["林霄"]},
        ],
    },
    "geography": {
        "regions": [
            {"name": "江海市", "type": "城市", "atmosphere": "灵气复苏最早的灵脉节点之一", "significance": "主角生活之地，故事主舞台",
             "connected_locations": "海晏武馆, 坠星湖, 临江大宅", "territory": "海晏武馆联盟"},
            {"name": "海晏武馆", "type": "武馆", "significance": "主角收服的第一股势力", "connected_locations": "江海市"},
            {"name": "坠星湖", "type": "秘境浅层", "significance": "第一处灵气矿脉，多方角力导火索", "connected_locations": "江海市"},
            {"name": "临江大宅", "type": "住宅", "significance": "世交陆子昂让主角一家入住的别墅", "connected_locations": "江海市"},
            {"name": "燕北武城", "type": "世家城邦", "significance": "北方武家盘踞之地", "connected_locations": "江海市"},
            {"name": "南都伏龙山", "type": "仙山", "significance": "朱雀阁祖山", "connected_locations": "江海市, 坠星湖"},
        ],
    },
    "history": {"origin": "千年前灵气隐退，仙门遁世；今朝灵气复苏，灵材频现。",
                "major_events": ["百年前镇国龙碑分立", "十年前星罗门暗杀宗师", "如今主角携前世重返暗改格局"]},
    "culture": {"beliefs": [], "customs": ["世家春祭斗武", "协会冬狩试炼"]},
    "key_rules": [
        {"rule": "现实一日，修真界一月", "consequence": "两界互为资源跳板"},
        {"rule": "元婴为现实天花板，化神入镜遭龙碑压制", "consequence": "主角步步为营"},
        {"rule": "归墟戒只能由主魂持有，可借他人口中存活", "consequence": "萧墨成为戒中传人"},
    ],
    "conflicts": [
        {"name": "灵气复苏分食", "type": "world", "description": "世家圈地、协会维稳、散修求生、星罗门欲独吞"},
        {"name": "两界抉择", "type": "fate", "description": "留现实陪家人，还是回修真界救师门"},
    ],
    "unique_features": ["归墟戒双主双界", "无瓶颈破境", "时间流速差·双线叙事"],
}


def _ch(name, role_type, **kw):
    base = {"age": 18, "gender": "male", "appearance": "", "personality": "", "mbti": "",
            "background": "", "goals": [], "fears": [], "skills": [], "relationships": {}}
    base.update(kw)
    return {"name": name, "role_type": role_type, "profile": base}


CHARACTERS = [
    _ch("林霄", "protagonist", age=18, gender="male",
        appearance="黑发清隽，常在角落，话少，眼神深不见底",
        personality="社恐高冷，话少；有修真大佬的傲气与心机，不惹事但不怕事，出手利落",
        mbti="INTJ",
        background="前世孤儿，穿越修真界后受清虚真人收留，修炼数百年成返虚霸主，师门被灭后携归墟戒穿越回高考后的现实，决心护住家人、查明真相并重返巅峰。",
        goals=["陪爸妈和妹妹过安稳日子", "尽快重登元婴，回修真界救师门", "在灵气时代立规矩"],
        fears=["再失去家人", "重演师门之劫"],
        skills=["前世眼界：一眼看穿套路与人心", "阵法与炼丹悟性", "归墟戒两界通道"],
        relationships={"父母": "父母", "林瑶": "妹妹", "苏晚晴": "青梅竹马", "陆子昂": "世交", "沈言卿": "学姐", "温梦瑶": "圣女", "萧墨": "戒中传人", "清虚真人": "前世恩师"}),
    _ch("苏晚晴", "supporting", age=18, gender="female",
        appearance="明媚张扬，校花级", personality="刀子嘴豆腐心，前期嫌主角穷，后期打脸后被折服却嘴硬",
        background="苏家独女，与林家世交，儿时玩伴。", mbti="ESFP"),
    _ch("陆子昂", "supporting", age=19, gender="male",
        appearance="富贵闲散", personality="纨绔重义气，是全剧少数不势利的人", background="陆家独子，让林家入住临江大宅。", mbti="ENFP"),
    _ch("沈言卿", "supporting", age=17, gender="female",
        appearance="清冷高马尾", personality="天才傲气，被主角点醒后转为崇拜", background="海晏高中天才，测试断层第一，沈家子弟。", mbti="INTP"),
    _ch("温梦瑶", "supporting", age=20, gender="female",
        appearance="红衣圣女，出尘矜贵", personality="外表冷傲内里清醒，不势利，被主角气度折服",
        background="朱雀阁圣女，家族联姻筹码，后主动站到主角一方。", mbti="INFJ"),
    _ch("萧墨", "supporting", age=14, gender="male",
        appearance="瘦削少年，眼神发亮", personality="倔强、命硬、讲义气", background="修真界小城乞儿，捡到归墟戒认主，被主角指点修行。", mbti="ISFJ"),
    _ch("清虚真人", "supporting", age=0, gender="female",
        appearance="遗世独立", personality="慈悲有锋芒，护短", background="主角前世恩师，师门灭门案亲历者，残魂存于归墟戒深处。", mbti="INFJ"),
    _ch("林瑶", "supporting", age=12, gender="female",
        appearance="机灵可爱", personality="黏人鬼机灵", background="主角妹妹，后被卷入灵异事件成为破局关键。", mbti="ENFJ"),
]

PLOT_SETTING = {
    "core_conflicts": [
        {"name": "灵气复苏分食", "type": "world", "description": "世家圈地、协会维稳、散修求生、星罗门欲独吞"},
        {"name": "两界双线", "type": "fate", "description": "现实家人与修真界师门，必须两全"},
        {"name": "当年灭门真相", "type": "mystery", "description": "师门因何被灭？归墟戒为何回到高中时代？"},
    ],
    "foreshadowing_plan": [
        {"title": "归墟戒双主", "setup": "戒中另一端萧墨结契", "payoff": "两界资源互为倚仗"},
        {"title": "清虚残魂", "setup": "戒指深处有絮语", "payoff": "师门真相关键"},
        {"title": "父亲的铜环", "setup": "老宅翻出与归墟戒同源的信物", "payoff": "回修真界之路其实一直在身上"},
    ],
    "mystery_system": [
        {"title": "灵气为何骤变", "question": "灵气复苏背后是降临还是归位？"},
        {"title": "灭门令", "question": "谁下了灭门令？"},
    ],
    "chapter_hooks": [],
    "plot_rhythm": {
        "opening": "回到高中的第三天",
        "development": "一鸣再鸣，打脸不息",
        "climax": "百城试炼·名传华夏",
        "ending": "开放式连载，悬念不断",
    },
    "character_arcs": [],
}

OUTLINE = {"volumes": [
    {"volume": 1, "title": "归来", "arcs": [{"arc_id": "arc1", "title": "第一记耳光", "start_chapter": 1, "end_chapter": 10,
        "description": "重生归来，先打脸身边人，惊动协会。"}]},
    {"volume": 2, "title": "初露锋芒", "arcs": [{"arc_id": "arc2", "title": "谁惹得起", "start_chapter": 11, "end_chapter": 20,
        "description": "灵脉之争、燕北之约，主角名动一方。"}]},
    {"volume": 3, "title": "燕北之锋", "arcs": [{"arc_id": "arc3", "title": "兴风起浪", "start_chapter": 21, "end_chapter": 30,
        "description": "斗武立威、圣女结盟，格局初成。"}]},
    {"volume": 4, "title": "圣女与盟约", "arcs": [{"arc_id": "arc4", "title": "盟与刃", "start_chapter": 31, "end_chapter": 40,
        "description": "祖山补阵、两界双线、生日宴打脸。"}]},
    {"volume": 5, "title": "暗流涌起", "arcs": [{"arc_id": "arc5", "title": "湖底星光", "start_chapter": 41, "end_chapter": 50,
        "description": "旧事浮出、百城试炼、灭门令初现。"}]},
]}

# (章号, 标题, 爽点情节, 章末钩子)
_raw = [
 (1, "回来就好", "爽点：重生第一幕就撞见校门口混混勒索同学，林霄随手扇翻，全场看呆。", "钩子：戒中传来一声苍老的叹息。"),
 (2, "这一拳，值三百万", "爽点：苏晚晴当众奚落林家穷，林霄在海晏武馆测试随手打出满分拳劲，镇住全场。", "钩子：协会的人找上门了。"),
 (3, "戒里的少年", "爽点：萧墨在异界点燃第一缕灵火，主角隔界指点，少年当场进阶当场拜师。", "钩子：现实一天，异界一月。"),
 (4, "穷小子？", "爽点：餐厅里富二代当众羞辱，林霄一句话点破对方祖传功法破绽，对方当众喷血打脸。", "钩子：父亲的公司被人做局了。"),
 (5, "一块玉，还一笔债", "爽点：收债的上门嚣张，林霄一块灵玉抵三百万，收债头子吓得跪了。", "钩子：有人盯上了这块玉。"),
 (6, "沈家天才的请求", "爽点：沈言卿卡境界上门求教，林霄一句口诀，她当场破境，惊动整个沈家。", "钩子：眼神在人群中锁定了林霄。"),
 (7, "地下拳场", "爽点：为查灵气网络进黑拳场，压轴的宗师被林霄一拳轰飞，全场鸦雀无声。", "钩子：拳场老板背后，站着天元协会的人。"),
 (8, "协会执事", "爽点：协会有眼无珠摆谱，林霄列出的名单让执事冷汗直冒，当场改口喊老师。", "钩子：名单里有三个字——灭门令。"),
 (9, "陆子昂的面子", "爽点：饭局上有人刁难陆家，林霄随手解了无解的残局，一桌人惊掉下巴。", "钩子：苏晚晴第一次主动给他倒了杯茶。"),
 (10, "坠星湖的消息", "爽点：坠星湖灵脉消息外泄，林霄以阵法知识当众截胡三大家族，气得会长拍桌。", "钩子：入夜，湖底亮了。"),
 (11, "三家的下马威", "爽点：三大家族代表齐至想压价，林霄后发制人，逐条点破对方底细，反转收走最优分成。", "钩子：武家少主在门外冷笑。"),
 (12, "没人敢要的东西", "爽点：拍卖会上一件烫手灵物人人避之不及，林霄捡漏，事后各房悔青肠子。", "钩子：灵物里藏着一份旧信。"),
 (13, "武家少主登门", "爽点：武擎当众叫阵，林霄一记化劲将他打飞出院，燕北武城颜面扫地。", "钩子：武家夜里传令只说了一个字——封。"),
 (14, "苏家的一场病", "爽点：苏家长辈病重无人能医，林霄一片灵草救命，苏晚晴被逼低头求人。", "钩子：她家的病，是被人下的咒。"),
 (15, "进燕北", "爽点：燕北武城关卡处处刁难，林霄一句「我是来收你们武城的」，守将愣住。", "钩子：城门口，武家大军已候。"),
 (16, "燕北斗武", "爽点：比武台上三连碾压，最后一战林霄徒手接下武家宗师一掌，全场死寂。", "钩子：擂台尽头，传来一声老祖叹息。"),
 (17, "一句话废宗师", "爽点：武家老长以地位压人，林霄一句话点破其功法命门，老长当场吐血废修。", "钩子：他丢下的那本残册，是武家的家底。"),
 (18, "沈家的夜", "爽点：沈言卿被家族夺权逼婚，林霄夜入沈家，一句话镇住满堂长老。", "钩子：沈家老祖，居然出来给他作揖。"),
 (19, "星河公司", "爽点：投行把林霄当冤大头，林霄三句话点穿对方局，反手把对方主投人收编。", "钩子：第一桶金，买下的是坠星湖的地。"),
 (20, "名帖", "爽点：各势力递名帖示好，林霄只留下最肆无忌惮的一张，众人不解。", "钩子：那张帖子的落款，是星罗门。"),
 (21, "圣女下山", "爽点：温梦瑶误认林霄是捡漏散修，言语轻视，被林霄一句阵法点破身份，当场怔住。", "钩子：祖山传来钟声。"),
 (22, "催熟的灵植", "爽点：某世家放话盘口看扁林霄的灵植园，林霄以古法催熟，灵果一夜挂满枝头，看客傻眼。", "钩子：有夜行人翻进了灵植园。"),
 (23, "奸细", "爽点：星罗门探子混入协会，林霄当众把人揪出来，一大摞证据砸得协会想捂脸。", "钩子：探子死前说出了一个名字。"),
 (24, "摄魂术反噬", "爽点：反派想用摄魂术控制林霄，被林霄神识反噬，当众满地打滚现原形。", "钩子：背后有人递来一枚魂钉。"),
 (25, "大比资格赛", "爽点：坠星湖大比资格赛，会长亲临，林霄随手夺魁，压得世家子弟抬不起头。", "钩子：规则临时被改，摆明针对他。"),
 (26, "定亲宴上震婚书", "爽点：朱雀阁要把圣女许给武家，林霄在定亲宴上随手一招震碎婚书，全场哗然。", "钩子：温梦瑶低声道：多谢。"),
 (27, "血债血偿", "爽点：武家宗师夜袭江海，林霄持归墟戒中的残剑反杀，燕北再无人敢犯。", "钩子：戒中的萧墨，也在流血。"),
 (28, "龙碑秘卷", "爽点：协会放出龙碑秘卷消息，各方争夺，林霄藏一手最后反转截走最要紧的一页。", "钩子：那一页上，画着归墟戒。"),
 (29, "南都夜宴", "爽点：南都商圈想捧杀林霄，林霄三句话反将，逼得设局之人当众道歉。", "钩子：温梦瑶递上一封朱雀阁的请帖。"),
 (30, "有人在查归墟戒", "爽点：林霄借祖山之名放出金钩，钓出暗中追查归墟戒线的人，对方一败涂地。", "钩子：那人逃走时喊了一个字——回。"),
 (31, "萧墨结丹", "爽点：异界萧墨结丹引动雷云，主角隔界指点硬抗天劫，两界同时侧目。", "钩子：灵材一船船入现实。"),
 (32, "祖山补阵", "爽点：朱雀阁祖山大阵裂开，各方束手无策，林霄千步布阵修好，老祖当场欲拜师。", "钩子：阵眼里藏着一枚旧令牌。"),
 (33, "结盟", "爽点：朱雀阁阁主当众宣布与林霄结盟，反对声四起，林霄一句「有异议的可以站到我面前」震场。", "钩子：星罗门的车停在了朱雀阁山门前。"),
 (34, "收徒", "爽点：沈言卿当众执拜师礼，林霄点拨三句，她又破一境，在场天才眼红到发疯。", "钩子：林霄对她说：你以后的路，别让人替你走。"),
 (35, "黑市截胡", "爽点：星罗门在黑市高价扫货要断林霄的材，林霄反向操作把价砸穿，星罗门赔得吐血。", "钩子：阴无咎亲自出山了。"),
 (36, "单刀赴会", "爽点：阴无咎设宴请君入瓮，林霄一人赴宴，当面点破其野心与破绽，拂袖而去。", "钩子：宴席地底，血煞阵起。"),
 (37, "妹妹的灵觉", "爽点：林瑶天赋曝光被天元协会盯上，林霄一句话护下，协会会长都买这个面子。", "钩子：夜里，有手伸向临江大宅。"),
 (38, "生日宴·一记王炸", "爽点：苏晚晴生日宴上有人借机羞辱林家，林霄一记王炸拳法当场镇住全城权贵。", "钩子：苏晚晴站在他身后，第一次没敢开口。"),
 (39, "一夜一月", "爽点：现实一夜，修真界一月，萧墨遇险，林霄跨界救援，两界名声同爆。", "钩子：修真界那边，有人认出了他。"),
 (40, "旧卷现世", "爽点：一卷指向当年师门的旧卷现世，林霄以一卷破尽各方野心，顺手封存。", "钩子：卷上的宗门印，是清虚的。"),
 (41, "老宅的铜环", "爽点：林霄回老宅翻出父亲遗物，一枚与归墟戒同源的铜环，专家开出天价他也一笑了之。", "钩子：铜环背面刻着半句古字。"),
 (42, "协会点他的名", "爽点：灵气复苏清洗异己，林霄被点名审问，当众对簿，几条证据被他逐一拆穿。", "钩子：审问席上，坐着一个不该在场的人。"),
 (43, "含冤与证伪", "爽点：被诬私藏灵脉，林霄当众证伪，反手把诬陷者按进土里，协会公开道歉。", "钩子：诬陷者的供词里，出现了灭门令。"),
 (44, "湖底血蜕", "爽点：星罗门献祭灵脉引出血蜕暴走，林霄以阵心反制，救下整城修士，一战封神。", "钩子：血蜕核心上的纹路，他见过。"),
 (45, "圣女之冤", "爽点：温梦瑶被构陷叛阁，林霄以身入局三个时辰揪出真凶，朱雀阁欠他一个大人情。", "钩子：真凶留给林霄一句话。"),
 (46, "老祖拜谒", "爽点：一位宗门老祖登门，当众被林霄一句口诀点得破境，老泪纵横要执弟子礼。", "钩子：门外，又排起长长的求见队伍。"),
 (47, "百城试炼", "爽点：天元协会联龙碑办百城试炼，林霄一路低调被嘲讽，最后一场才展露冰山一角。", "钩子：主办方改了他的编号，故意排最难。"),
 (48, "万人面前", "爽点：试炼总决赛，林霄以元婴残威一掌镇场，万名武者集体沉默，华夏震动。", "钩子：龙碑发出了只有他能听到的声音。"),
 (49, "钓鱼", "爽点：试炼中放线钓鱼，林霄当众钓出私下传递灭门令的线人，真凶线索指向高层。", "钩子：线人随身带的东西，让他瞳孔一缩。"),
 (50, "回去的路", "爽点：林霄捏着铜环站在临江大宅天台，全城灯火浮在脚下，他淡淡开口：回去的路，原来一直在我身上。", "钩子：铜环发烫，戒中的萧墨传来急讯——师父，你当年所在的宗门，有人在找。"),
]
CHAPTER_OUTLINES = [
    {"chapter_number": i, "title": t, "summary": s + " " + h,
     "key_points": [s.replace("爽点：", "")], "scenes": [],
     "word_count_target": 2200}
    for i, t, s, h in _raw
]


async def main():
    from app.core.redis_client import SessionManager
    from app.models.character import Character, RoleType
    from app.models.outline import Outline
    from app.models.entity import Entity, EntityRelationship
    from app.core.database import get_session
    from sqlalchemy import delete

    key = f"workflow_{NOVEL_ID}"
    state = await SessionManager.get_state(key)
    if not state:
        # 引擎状态尚未创建：构造最小状态（其余字段用 dataclass 默认值）
        print("未找到 workflow_1007 状态，正在创建初始状态...")
        state = {
            "workflow_id": f"wf_{NOVEL_ID}_v2",
            "novel_id": NOVEL_ID,
            "project_path": "",
            "completed_chapters": [],
            "confirmed_chapters": [],
        }
    state["world_setting"] = WORLD_SETTING
    state["characters"] = CHARACTERS
    state["plot_setting"] = PLOT_SETTING
    state["outline"] = OUTLINE
    state["chapter_outlines"] = CHAPTER_OUTLINES
    state["target_chapters"] = 1000
    for _k in ("waiting_for_user", "progress", "can_proceed", "messages", "current_state"):
        state.pop(_k, None)
    await SessionManager.save_state(key, state)
    print(f"[1] workflow_{NOVEL_ID} 已注入 50 章细纲（番茄文风·每章爽点）")

    async with get_session() as db:
        await db.execute(delete(Character).where(Character.novel_id == NOVEL_ID))
        await db.execute(delete(Outline).where(Outline.novel_id == NOVEL_ID))
        await db.execute(delete(Entity).where(Entity.novel_id == NOVEL_ID))
        await db.execute(delete(EntityRelationship).where(EntityRelationship.novel_id == NOVEL_ID))
        for c in CHARACTERS:
            db.add(Character(novel_id=NOVEL_ID, name=c["name"], role_type=RoleType(c["role_type"]),
                             profile=c["profile"], first_appearance=1))
        for v in OUTLINE["volumes"]:
            db.add(Outline(novel_id=NOVEL_ID, volume_number=v["volume"], volume_title=v["title"],
                           arcs=v["arcs"], outline_type="main", target_chapters=10, actual_chapters=0,
                           summary=v["title"]))
        await db.commit()
        print("[2] DB 人物(%d)/大纲(%d卷) 已写入" % (len(CHARACTERS), len(OUTLINE["volumes"])))

    from app.services.workflow_entity_sync import WorkflowEntitySyncService
    sync = WorkflowEntitySyncService(NOVEL_ID)
    c = await sync.sync_characters(CHARACTERS)
    e = await sync.sync_world_setting(WORLD_SETTING)
    print(f"[3] 实体同步: 角色{c} 个, 世界观{e} 个")
    print("\n注入完成。")


if __name__ == "__main__":
    asyncio.run(main())