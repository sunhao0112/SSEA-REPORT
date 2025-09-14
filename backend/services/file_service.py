import pandas as pd
import numpy as np
import os
from typing import List, Dict, Any
from schemas import RawDataItem

def clean_value(value):
    """清理数据值，处理NaN和None"""
    if pd.isna(value) or value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    elif isinstance(value, str) and value.lower() in ['nan', 'null', '']:
        return None
    else:
        return str(value).strip()

class FileService:
    """文件处理服务"""
    
    def __init__(self):
        self.required_columns = ['URL', '来源名称', '作者用户名称', '标题', '命中句子', '语言']
    
    def read_csv_file(self, file_path: str) -> List[Dict[str, Any]]:
        """读取CSV文件并返回原始数据，支持多种编码格式和容错处理"""
        # 首先检测文件编码
        detected_encoding = self._detect_file_encoding(file_path)
        if detected_encoding:
            print(f"🔍 检测到文件编码: {detected_encoding}")
        
        # 尝试多种编码格式，优先使用检测到的编码
        encodings = ['utf-8', 'utf-8-sig', 'utf-16', 'utf-16le', 'utf-16be', 'gbk', 'gb2312', 'gb18030']
        if detected_encoding and detected_encoding not in encodings:
            encodings.insert(0, detected_encoding)
        
        for encoding in encodings:
            try:
                # 尝试不同的CSV读取参数组合
                read_params = [
                    # 标准参数
                    {'encoding': encoding},
                    # 容错参数 - 处理格式不规范的CSV
                    {'encoding': encoding, 'error_bad_lines': False, 'warn_bad_lines': True},
                    # 更宽松的参数
                    {'encoding': encoding, 'sep': None, 'engine': 'python'},
                    # 指定分隔符
                    {'encoding': encoding, 'sep': ',', 'quotechar': '"', 'skipinitialspace': True},
                    # 最宽松的参数
                    {'encoding': encoding, 'sep': None, 'engine': 'python', 'on_bad_lines': 'skip'}
                ]
                
                for params in read_params:
                    try:
                        df = pd.read_csv(file_path, **params)
                        if not df.empty:
                            print(f"成功使用 {encoding} 编码读取文件，参数: {params}")
                            return df.to_dict('records')
                    except Exception:
                        continue
                        
            except UnicodeDecodeError:
                continue
            except Exception as e:
                if encoding == encodings[-1]:  # 最后一个编码也失败了
                    # 尝试最后的兜底方案：逐行读取
                    try:
                        return self._read_csv_line_by_line(file_path, encoding)
                    except Exception:
                        raise Exception(f"读取CSV文件失败: {str(e)}")
                continue
        
        raise Exception("无法识别文件编码格式，请确保文件是有效的CSV格式")
    
    def _read_csv_line_by_line(self, file_path: str, encoding: str) -> List[Dict[str, Any]]:
        """逐行读取CSV文件的兜底方案"""
        import csv
        
        data = []
        headers = None
        
        with open(file_path, 'r', encoding=encoding, newline='') as file:
            # 尝试不同的分隔符
            for delimiter in [',', ';', '\t', '|']:
                file.seek(0)
                try:
                    reader = csv.reader(file, delimiter=delimiter)
                    rows = list(reader)
                    
                    if len(rows) > 1 and len(rows[0]) > 1:  # 至少有标题行和一行数据，且有多列
                        headers = rows[0]
                        for row in rows[1:]:
                            if len(row) >= len(headers):
                                row_dict = {}
                                for i, header in enumerate(headers):
                                    row_dict[header] = row[i] if i < len(row) else ''
                                data.append(row_dict)
                        
                        if data:
                            print(f"使用逐行读取成功，分隔符: '{delimiter}'")
                            return data
                except Exception:
                    continue
        
        raise Exception("无法解析CSV文件格式")
    
    def _detect_file_encoding(self, file_path: str) -> str:
        """检测文件编码"""
        try:
            import chardet
            
            with open(file_path, 'rb') as file:
                # 读取文件的前几KB来检测编码
                raw_data = file.read(8192)
                result = chardet.detect(raw_data)
                
                if result and result['confidence'] > 0.7:
                    encoding = result['encoding']
                    print(f"chardet检测结果: {encoding} (置信度: {result['confidence']:.2f})")
                    return encoding

        except ImportError:
            print("chardet未安装，使用内置编码检测")
        except Exception as e:
            print(f"编码检测失败: {e}")
        
        # 内置编码检测
        try:
            with open(file_path, 'rb') as file:
                raw_data = file.read(4)
                
                # 检测BOM
                if raw_data.startswith(b'\xff\xfe'):
                    return 'utf-16le'
                elif raw_data.startswith(b'\xfe\xff'):
                    return 'utf-16be'
                elif raw_data.startswith(b'\xef\xbb\xbf'):
                    return 'utf-8-sig'
                elif raw_data.startswith(b'\xff\xfe\x00\x00'):
                    return 'utf-32le'
                elif raw_data.startswith(b'\x00\x00\xfe\xff'):
                    return 'utf-32be'
                    
        except Exception as e:
            print(f"⚠️ BOM检测失败: {e}")
        
        return None
    
    def clean_data(self, raw_data: List[Dict[str, Any]]) -> List[RawDataItem]:
        """清洗数据，只保留需要的字段"""
        try:
            if not raw_data:
                return []
            
            # 获取第一行数据来检查列名
            first_row = raw_data[0]
            column_mapping = {}
            missing_columns = []
            
            print(f"📋 CSV文件中的列名: {list(first_row.keys())}")
            print(f"🎯 需要匹配的列名: {self.required_columns}")
            
            # 尝试匹配列名（支持不同的命名方式）
            for required_col in self.required_columns:
                found = False
                for col in first_row.keys():
                    if self._is_column_match(col, required_col):
                        column_mapping[required_col] = col
                        print(f"✅ 匹配成功: '{required_col}' -> '{col}'")
                        found = True
                        break
                
                if not found:
                    missing_columns.append(required_col)
                    print(f"❌ 未找到匹配: '{required_col}'")
            
            if missing_columns:
                print(f"❌ 缺少必需的列: {missing_columns}")
                print(f"💡 请检查CSV文件是否包含以下列名（支持中英文）:")
                for col in missing_columns:
                    print(f"   - {col}")
                raise ValueError(f"缺少必需的列: {missing_columns}")
            
            # 提取需要的数据
            cleaned_data = []
            for row in raw_data:
                item = RawDataItem(
                    url=clean_value(row.get(column_mapping['URL'])),
                    source_name=clean_value(row.get(column_mapping['来源名称'])),
                    author_username=clean_value(row.get(column_mapping['作者用户名称'])),
                    title=clean_value(row.get(column_mapping['标题'])),
                    hit_sentence=clean_value(row.get(column_mapping['命中句子'])),
                    language=clean_value(row.get(column_mapping['语言']))
                )
                cleaned_data.append(item)
            
            return cleaned_data
            
        except Exception as e:
            raise Exception(f"数据清洗失败: {str(e)}")
    
    
    async def clean_csv_data(self, file_path: str) -> List[RawDataItem]:
        """清洗CSV数据，只保留需要的字段"""
        
        try:
            # 读取CSV文件
            df = pd.read_csv(file_path, encoding='utf-8')
            
            # 检查必需的列是否存在
            missing_columns = []
            column_mapping = {}
            
            # 尝试匹配列名（支持不同的命名方式）
            for required_col in self.required_columns:
                found = False
                for col in df.columns:
                    if self._is_column_match(col, required_col):
                        column_mapping[required_col] = col
                        found = True
                        break
                
                if not found:
                    missing_columns.append(required_col)
            
            if missing_columns:
                raise ValueError(f"缺少必需的列: {missing_columns}")
            
            # 提取需要的数据
            cleaned_data = []
            for _, row in df.iterrows():
                item = RawDataItem(
                    url=clean_value(row[column_mapping['URL']]),
                    source_name=clean_value(row[column_mapping['来源名称']]),
                    author_username=clean_value(row[column_mapping['作者用户名称']]),
                    title=clean_value(row[column_mapping['标题']]),
                    hit_sentence=clean_value(row[column_mapping['命中句子']]),
                    language=clean_value(row[column_mapping['语言']])
                )
                cleaned_data.append(item)
            
            return cleaned_data
            
        except Exception as e:
            raise Exception(f"CSV数据清洗失败: {str(e)}")
    
    async def deduplicate_data(self, data: List[RawDataItem]) -> List[RawDataItem]:
        """基于命中句子进行去重"""
        import logging
        logger = logging.getLogger(__name__)

        # 记录去重前的统计信息
        original_count = len(data)
        logger.info(f"📊 去重处理开始 - 原始数据行数: {original_count}")

        # 统计有无命中句子的数据分布
        has_sentence_count = sum(1 for item in data if item.hit_sentence)
        no_sentence_count = original_count - has_sentence_count
        logger.info(f"📈 数据分布 - 有命中句子: {has_sentence_count} 条，无命中句子: {no_sentence_count} 条")

        # 调试：打印前5个命中句子样例
        logger.info("🔍 前5个命中句子样例:")
        for i, item in enumerate(data[:5]):
            if item.hit_sentence:
                sentence_preview = item.hit_sentence.strip()[:100] + '...' if len(item.hit_sentence.strip()) > 100 else item.hit_sentence.strip()
                logger.info(f"   {i+1}. 长度:{len(item.hit_sentence.strip())} - {sentence_preview}")
            else:
                logger.info(f"   {i+1}. [空命中句子] - 标题: {item.title}")

        seen_sentences = set()
        deduped_data = []
        duplicate_count = 0
        duplicate_examples = []  # 保存前几个重复样例
        empty_sentence_count = 0

        for i, item in enumerate(data):
            if item.hit_sentence:
                # 清理和标准化命中句子（去除首尾空格，统一换行符）
                cleaned_sentence = item.hit_sentence.strip().replace('\r\n', '\n').replace('\r', '\n')

                if not cleaned_sentence:
                    # 清理后命中句子为空，保留该条目
                    empty_sentence_count += 1
                    deduped_data.append(item)
                elif cleaned_sentence not in seen_sentences:
                    seen_sentences.add(cleaned_sentence)
                    deduped_data.append(item)
                else:
                    # 记录重复数据
                    duplicate_count += 1
                    # 保存前5个重复样例用于日志展示
                    if len(duplicate_examples) < 5:
                        duplicate_examples.append({
                            'index': i + 1,
                            'sentence': cleaned_sentence[:100] + '...' if len(cleaned_sentence) > 100 else cleaned_sentence,
                            'sentence_length': len(cleaned_sentence),
                            'url': item.url,
                            'title': item.title[:50] + '...' if item.title and len(item.title) > 50 else item.title
                        })
            else:
                # 如果没有命中句子，保留该条目
                deduped_data.append(item)

        # 记录去重后的统计信息
        final_count = len(deduped_data)
        removed_count = original_count - final_count
        unique_sentences = len(seen_sentences)

        logger.info(f"✅ 去重处理完成 - 最终数据行数: {final_count}")
        logger.info(f"🗑️  去重统计 - 移除重复数据: {removed_count} 条 ({removed_count/original_count*100:.1f}%)")
        logger.info(f"🔢 唯一命中句子数量: {unique_sentences}")
        logger.info(f"📋 清理后为空的命中句子: {empty_sentence_count} 条")
        logger.info(f"📋 保留数据构成 - 有效命中句子: {unique_sentences} 条，空命中句子: {empty_sentence_count} 条，无命中句子: {no_sentence_count} 条")

        # 输出重复样例
        if duplicate_examples:
            logger.info(f"🔍 重复数据样例 ({len(duplicate_examples)} 个示例):")
            for example in duplicate_examples:
                logger.info(f"   第{example['index']}行 - 长度:{example['sentence_length']} - {example['sentence']}")
                logger.info(f"      标题: {example['title'] or '无标题'}")
                logger.info(f"      URL: {example['url'] or '无URL'}")

        return deduped_data

    def analyze_hit_sentences(self, data: List[RawDataItem]) -> dict:
        """分析命中句子的分布情况，用于调试去重问题"""
        import logging
        from collections import Counter
        logger = logging.getLogger(__name__)

        sentence_counts = Counter()
        sentence_examples = {}

        for i, item in enumerate(data):
            if item.hit_sentence:
                cleaned_sentence = item.hit_sentence.strip().replace('\r\n', '\n').replace('\r', '\n')
                if cleaned_sentence:
                    sentence_counts[cleaned_sentence] += 1
                    # 保存每个句子的第一个样例
                    if cleaned_sentence not in sentence_examples:
                        sentence_examples[cleaned_sentence] = {
                            'first_occurrence': i + 1,
                            'title': item.title,
                            'url': item.url,
                            'source': item.source_name
                        }

        # 分析统计信息
        total_sentences = len([item for item in data if item.hit_sentence])
        unique_sentences = len(sentence_counts)

        # 找出重复次数最多的句子
        most_duplicated = sentence_counts.most_common(10)

        analysis = {
            'total_items': len(data),
            'items_with_sentences': total_sentences,
            'unique_sentences': unique_sentences,
            'duplication_rate': (total_sentences - unique_sentences) / total_sentences if total_sentences > 0 else 0,
            'most_duplicated': []
        }

        for sentence, count in most_duplicated:
            if count > 1:
                example = sentence_examples[sentence]
                analysis['most_duplicated'].append({
                    'sentence': sentence[:100] + '...' if len(sentence) > 100 else sentence,
                    'count': count,
                    'first_occurrence': example['first_occurrence'],
                    'title': example['title'],
                    'source': example['source']
                })

        # 记录分析结果
        logger.info(f"📊 命中句子分析结果:")
        logger.info(f"   总数据条数: {analysis['total_items']}")
        logger.info(f"   有命中句子的条数: {analysis['items_with_sentences']}")
        logger.info(f"   唯一命中句子数: {analysis['unique_sentences']}")
        logger.info(f"   预期去重率: {analysis['duplication_rate']*100:.1f}%")

        if analysis['most_duplicated']:
            logger.info(f"🔍 重复次数最多的命中句子:")
            for dup in analysis['most_duplicated'][:5]:
                logger.info(f"   重复 {dup['count']} 次: {dup['sentence']}")
                logger.info(f"      来源: {dup['source']} | 标题: {dup['title']}")

        return analysis
    
    def _is_column_match(self, col_name: str, target: str) -> bool:
        """检查列名是否匹配目标列名 - 使用精准匹配"""
        col_name = col_name.strip()
        target = target.strip()

        # 只进行精确匹配
        return col_name == target
    
    async def save_to_csv(self, data: List[RawDataItem], output_path: str):
        """将清洗后的数据保存为CSV"""
        
        df_data = []
        for item in data:
            df_data.append({
                'URL': item.url,
                '来源名称': item.source_name,
                '作者用户名称': item.author_username,
                '标题': item.title,
                '命中句子': item.hit_sentence,
                '语言': item.language
            })
        
        df = pd.DataFrame(df_data)
        df.to_csv(output_path, index=False, encoding='utf-8')
        
        return output_path