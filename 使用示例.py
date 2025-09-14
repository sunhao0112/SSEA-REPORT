import json
import re
from typing import Tuple, Optional
import os

import requests
from docxtpl import DocxTemplate
import datetime


def upload(file_path: str) -> Optional[str]:
    """
    上传CSV文件到Dify API
    """
    url = "https://api.dify.ai/v1/files/upload"
    
    try:
        if not os.path.exists(file_path):
            print(f"❌ 文件不存在: {file_path}")
            return None
        
        filename = os.path.basename(file_path)
        
        with open(file_path, 'rb') as f:
            files = {
                'file': (filename, f, 'text/csv')
            }
            headers = {
                'Authorization': 'Bearer app-cg5qmpzNXybVJwuNR2qgQsMR'
            }
            
            response = requests.post(url, headers=headers, files=files, timeout=60)
            
            # HTTP 201 Created 也表示成功
            if response.status_code in [200, 201]:
                result = response.json()
                file_id = result.get('id')
                if file_id:
                    print(f"✅ 文件上传成功: {filename}")
                    return file_id
                else:
                    print("❌ 响应中没有找到文件ID")
                    return None
            else:
                print(f"❌ 文件上传失败: {filename}")
                print(f"状态码: {response.status_code}")
                print(f"错误详情: {response.text}")
                return None
                
    except Exception as e:
        print(f"❌ 上传文件时发生错误: {str(e)}")
        return None


def run_workflow(file_id: str) -> Optional[dict]:
    """
    运行工作流 - 使用流式输出
    """
    url = "https://api.dify.ai/v1/workflows/run"
    
    payload = {
        "inputs": {
            "raw_data": {
                "type": "document",
                "transfer_method": "local_file",
                "upload_file_id": file_id
            }
        },
        "response_mode": "streaming",
        "user": "abc-123"
    }
    
    headers = {
        'Authorization': 'Bearer app-cg5qmpzNXybVJwuNR2qgQsMR',
        'Content-Type': 'application/json'
    }
    
    try:
        print("🔄 开始流式处理工作流...")
        response = requests.post(url, headers=headers, json=payload, timeout=300, stream=True)
        
        if response.status_code == 200:
            print("📡 接收流式数据...")
            
            # 收集所有流式数据
            collected_data = []
            final_result = None
            
            for line in response.iter_lines():
                if line:
                    line_text = line.decode('utf-8')
                    
                    # 跳过空行和非数据行
                    if not line_text.strip() or not line_text.startswith('data: '):
                        continue
                    
                    # 提取JSON数据
                    json_str = line_text[6:]  # 移除 'data: ' 前缀
                    
                    try:
                        chunk_data = json.loads(json_str)
                        collected_data.append(chunk_data)
                        
                        # 显示处理进度
                        event = chunk_data.get('event', '')
                        if event == 'node_started':
                            node_data = chunk_data.get('data', {})
                            node_title = node_data.get('title', '未知节点')
                            print(f"  🔸 开始处理: {node_title}")
                        elif event == 'node_finished':
                            node_data = chunk_data.get('data', {})
                            node_title = node_data.get('title', '未知节点')
                            print(f"  ✅ 完成处理: {node_title}")
                        elif event == 'workflow_finished':
                            print("🎉 工作流处理完成")
                            final_result = chunk_data
                            break
                        elif event == 'error':
                            print(f"❌ 处理过程中出现错误: {chunk_data.get('data', {}).get('message', '未知错误')}")
                            return None
                            
                    except json.JSONDecodeError as e:
                        print(f"⚠️ 解析流数据失败: {e}")
                        continue
            
            # 返回最终结果
            if final_result:
                print(f"✅ 工作流执行成功")
                return final_result
            else:
                print("❌ 未收到完整的工作流结果")
                return None
                
        else:
            print(f"❌ 工作流执行失败")
            print(f"状态码: {response.status_code}")
            print(f"错误详情: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ 执行工作流时发生错误: {str(e)}")
        return None


def process_single_file(file_path: str, file_type: str) -> Optional[dict]:
    """
    处理单个文件：上传并运行工作流
    """
    print(f"\n🚀 开始处理{file_type}文件: {os.path.basename(file_path)}")

    # 上传文件
    file_id = upload(file_path)
    if not file_id:
        print(f"❌ {file_type}文件上传失败")
        return None

    # 运行工作流
    workflow_result = run_workflow(file_id)
    if not workflow_result:
        print(f"❌ {file_type}文件工作流执行失败")
        return None

    print(f"✅ {file_type}文件处理完成")
    return workflow_result



def generate_report(result):
    # 检查数据提取结果，如果任一失败则终止
    if not domestic_sources:
        print("❌ 境内数据提取失败，程序终止")
        return False

    if not foreign_sources:
        print("❌ 境外数据提取失败，程序终止")
        return False

    # 准备模板数据
    today = datetime.date.today()
    date_text = today.strftime('%Y年%#m月%#d日')

    one_day = datetime.timedelta(days=1)
    previous_day = today - one_day
    previous_date_text = previous_day.strftime('%Y年%#m月%#d日')

    # 确保所有字段都是正确的类型
    context = {
        'title': '南海舆情日报',
        'date': date_text,
        'previous_date': previous_date_text,
        'outside_total': len(foreign_sources),
        'inside_total': len(domestic_sources),
        'domestic_sources': domestic_sources,
        'foreign_sources': foreign_sources
    }

    # 打印调试信息
    print(f"\n📋 模板数据准备完成:")
    print(f"- 境内条目数: {context['inside_total']}")
    print(f"- 境外条目数: {context['outside_total']}")
    print(f"- 报告日期: {context['date']}")

    # 生成Word文档
    try:
        if not os.path.exists("template.docx"):
            print("❌ 模板文件 template.docx 不存在")
            return False

        doc = DocxTemplate("template.docx")
        doc.render(context)
        doc.save(output_filename)
        print(f"\n✅ 报告生成成功: {output_filename}")
        print("=" * 60)
        return True
    except Exception as e:
        print(f"\n❌ 生成Word文档时发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


csv_path = input("\n请输入境内采集信息.csv的完整路径: ").strip()
workflow_result = process_single_file(csv_path, '')
print(workflow_result)
''''{
    "event": "workflow_finished",
    "workflow_run_id": "19b09554-8912-4c72-af59-e82140724c49",
    "task_id": "da076196-c2ac-4bf5-95d7-7f8725be0749",
    "data": {
        "id": "19b09554-8912-4c72-af59-e82140724c49",
        "workflow_id": "838127fc-b672-4312-a40c-b78d30acbcd1",
        "status": "succeeded",
        "outputs": {
            "structured_output": {
                "domestic_sources": [
                    {
                        "title": "1. 中国在黄岩岛设立国家级自然保护区，强化主权宣示与生态保护并重。",
                        "content": "多篇文章指出，中国在黄岩岛设立国家级自然保护区，此举被视为一项“无解的阳谋”，旨在通过法律和行政手段，在维护生态环境的同时，有效巩固中国对黄岩岛的主权管辖。此举导致菲律宾的抗议显得无力，而美国则因自身在环保议题上的立场而难以对此明确反对。文章强调黄岩岛自古以来属于中国，此举是对菲律宾近期挑衅行为的有力回应，并有助于在国际社会中清晰传递中国维护南海权益的坚定立场。",
                        "links": [
                            "http://mp.weixin.qq.com/s?__biz=MzYyMzI4MTQ3MQ==&idx=2&mid=2247483832&scene=0&sn=3bc18d589699cc9fa3bdbdd9e2a6be57（WeChat, 作者：衡阳融媒识光）",
                            "http://mp.weixin.qq.com/s?__biz=MzE5MTY0MzE5Mw==&idx=1&mid=2247484432&scene=0&sn=7c3a204acf9905db5e3390594d3e82a0（WeChat, 作者：熊熊2004）",
                            "http://mp.weixin.qq.com/s?__biz=MzYyNTE0ODkwOQ==&idx=1&mid=2247484019&scene=0&sn=f08e6b267574844054d735626bdd4b6a（WeChat, 作者：田舍资读）",
                            "http://mp.weixin.qq.com/s?__biz=Mzk0Nzc2MDc0Nw==&idx=1&mid=2247483975&scene=0&sn=18b1ae67c44f701b4b0840ee7cefb65c（WeChat, 作者：成都欧深特信息科技有限公司）",
                            "https://weibo.com/2310663307/Q4cBs4xNT（Sina Weibo, 作者：肥唐说）",
                            "http://mp.weixin.qq.com/s?__biz=Mzk1NzU5NTU2Nw==&idx=2&mid=2247488586&sn=5e1d20abea9fb8270a4b6c1281b834f8（WeChat, 作者：镇边关）",
                            "http://mp.weixin.qq.com/s?__biz=MzkwMzY5NTQ5NQ==&idx=1&mid=2247501451&sn=d9201fd2a1cf84fc259b01988217202e（WeChat, 作者：柳君兰）"
                        ]
                    },
                    {
                        "title": "2. 菲律宾在仁爱礁补给行动受挫，中方实施常态化管控，美方口头支持难助菲方实现既定目标。",
                        "content": "菲律宾在仁爱礁非法“坐滩”的“马德雷山号”轮补行动屡次受阻，菲军方被迫承认补给未能成功。中国海警和军舰在仁爱礁水域实行常态化巡逻和有效管控，对菲方船只进行跟踪查证、管制航路，阻止其运送建筑材料，迫使其仅能运送生活物资。此举被解读为中方为菲律宾设定的“台阶”。文章普遍认为，美国在此事件中仅提供口头支持，并未派遣军舰直接为菲律宾撑腰，使得菲律宾在南海问题上面临进退两难的困境。",
                        "links": [
                            "http://mp.weixin.qq.com/s?__biz=MzIzMjQ2MTUxMA==&idx=4&mid=2247557195&scene=0&sn=b74c8325c67fb863827c7574117fcecf（WeChat, 作者：宏观微言）",
                            "http://mp.weixin.qq.com/s?__biz=MzE5MTY0MzE5Mw==&idx=1&mid=2247484432&scene=0&sn=7c3a204acf9905db5e3390594d3e82a0（WeChat, 作者：熊熊2004）",
                            "https://www.xiaohongshu.com/discovery/item/68c3983d000000001d007770（Red, 作者：Anland）",
                            "http://mp.weixin.qq.com/s?__biz=MzYyNTE0ODkwOQ==&idx=1&mid=2247484019&scene=0&sn=f08e6b267574844054d735626bdd4b6a（WeChat, 作者：田舍资读）",
                            "http://mp.weixin.qq.com/s?__biz=MzU1ODg3MjE2Mg==&idx=1&mid=2247487435&sn=768f428b843316ec85ee99901a1945f7（WeChat, 作者：秦林涛战研社）"
                        ]
                    },
                    {
                        "title": "3. 中国海军力量在南海地区活动增加，引发美方关注。",
                        "content": "九三阅兵后，中国海军在南海地区动作频频。卫星图片显示，中国最先进的福建舰离开江南造船厂并一路南下，其甲板被罕见清空，这一举动引发了美军的关注和担忧。同时，中美两国高层互动中，中方强调致力于与地区国家一道维护南海和平稳定，并坚决反对个别国家侵权挑衅以及域外国家的蓄意煽动。",
                        "links": [
                            "https://www.360kuai.com/92a797a64d47bf1a4（360kuai）",
                            "http://mp.weixin.qq.com/s?__biz=MzA3Mjk4MDI4Ng==&idx=1&mid=2652719646&sn=b79b9d5546b1586307298f83081fb1ff（WeChat, 作者：小小学习号）"
                        ]
                    }
                ],
                "foreign_sources": [
                    {
                        "title": "1. 中国福建号航空母舰穿越台湾海峡进入南海进行例行试验，加剧地区紧张局势。",
                        "content": "多份国际报道指出，中国最先进的航空母舰福建号最近通过敏感的台湾海峡进入南海进行例行试验。这一举动被视为中国军事活动增加的信号，并引发了地区紧张局势的上升。",
                        "links": [
                            "https://www.econotimes.com/Chinas-Fujian-Aircraft-Carrier-Sails-Through-Taiwan-Strait-Amid-Rising-Tensions-1720420（EconoTimes）",
                            "https://stratnewsglobal.com/team-sng/chinas-fujian-carrier-nears-taiwan-in-routine-trials/（Strat News Global）",
                            "https://m.dailyhunt.in/news/india/english/stratnewsglobal-epaper-stratnew/china+s+fujian+carrier+nears+taiwan+in+routine+trials-newsid-n680706848（Dailyhunt）"
                        ]
                    },
                    {
                        "title": "2. 菲律宾国家安全委员会反对中国在马辛洛克滩（黄岩岛）设立自然保护区的计划，并重申其主权主张。",
                        "content": "菲律宾国家安全委员会（NSC）明确反对中华人民共和国新宣布的在马辛洛克滩（即黄岩岛或帕纳塔格礁）设立国家级自然保护区的计划。国家安全顾问爱德华多·阿诺强调，该区域不属于中国，并以此拒绝中方的主张。",
                        "links": [
                            "https://mb.com.ph/2025/09/12/hindi-naman-inyo-iyan-nsc-rejects-chinas-plan-for-nature-reserve-at-bajo-de-masinloc（Manila Bulletin, 作者：Martin Sadongdong）"
                        ]
                    },
                    {
                        "title": "3. 菲律宾与日本加强防务合作，探讨可能转让海军资产以提升菲律宾海军能力。",
                        "content": "菲律宾国防部长与日本国防大臣在2025年首尔防务对话期间举行会晤，讨论了将日本阿武隈级驱逐舰护卫舰转让给菲律宾海军的可能性。菲律宾海军已完成对这些舰船的检查，并向国防部提交了建议，预示着两国为应对地区安全关切而加强防务合作。",
                        "links": [
                            "https://www.youtube.com/watch?v=niLMzD_51gU(Youtube, 作者：PHMalaya)"
                        ]
                    }
                ]
            }
        },
        "error": "",
        "elapsed_time": 55.693838,
        "total_tokens": 22604,
        "total_steps": 4,
        "created_by": {
            "id": "b17e6665-221d-4cfc-aa13-8ebf5b077f50",
            "user": "abc-123"
        },
        "created_at": 1757774984,
        "finished_at": 1757775040,
        "exceptions_count": 0,
        "files": []
    }
}
'''