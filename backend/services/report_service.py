from docxtpl import DocxTemplate
import datetime
import os
from typing import List, Dict, Any
from services.logger_config import get_logger

logger = get_logger("report")

class ReportService:
    def __init__(self, template_path: str = None):
        if template_path is None:
            # 使用环境变量配置的模板目录
            templates_dir = os.getenv('TEMPLATES_DIR', './templates')
            template_path = os.path.join(templates_dir, "report_template.docx")

        self.template_path = template_path
        #logger.info("使用模板文件", template_path=self.template_path)
    
    def generate_report(self, domestic_sources: List[Dict[Any, Any]],
                       foreign_sources: List[Dict[Any, Any]],
                       inside_total: int = None,
                       outside_total: int = None,
                       output_filename: str = None) -> bool:
        """生成Word报告"""
        try:
            # 检查数据提取结果，如果任一失败则终止
            if not domestic_sources:
                logger.error("❌ 境内数据提取失败，程序终止")
                return False

            if not foreign_sources:
                logger.error("❌ 境外数据提取失败，程序终止")
                return False

            # 准备模板数据
            today = datetime.date.today()
            date_text = today.strftime('%Y年%#m月%#d日')

            one_day = datetime.timedelta(days=1)
            previous_day = today - one_day
            previous_date_text = previous_day.strftime('%Y年%#m月%#d日')

            if not output_filename:
                output_filename = f"舆情日报_{date_text}.docx"

            # 确保所有字段都是正确的类型
            context = {
                'title': '南海舆情日报',
                'date': date_text,
                'previous_date': previous_date_text,
                'outside_total': outside_total if outside_total is not None else len(foreign_sources),
                'inside_total': inside_total if inside_total is not None else len(domestic_sources),
                'domestic_sources': domestic_sources,
                'foreign_sources': foreign_sources
            }

            # 打印调试信息
            logger.info(f"\n📋 模板数据准备完成:")
            #logger.info(f"- 境内条目数: {context['inside_total']}")
            #logger.info(f"- 境外条目数: {context['outside_total']}")
            #logger.info(f"- 报告日期: {context['date']}")

            # 生成Word文档
            if not os.path.exists(self.template_path):
                logger.error(f"❌ 模板文件 {self.template_path} 不存在")
                return False

            doc = DocxTemplate(self.template_path)
            doc.render(context)
            doc.save(output_filename)
            logger.info(f"\n✅ 报告生成成功: {output_filename}")
            logger.info("=" * 60)
            return True
            
        except Exception as e:
            logger.error(f"\n❌ 生成Word文档时发生错误: {str(e)}")
            import traceback
            traceback.print_exc()
            return False