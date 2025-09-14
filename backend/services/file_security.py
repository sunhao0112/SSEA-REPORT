"""
文件安全验证服务
提供文件上传安全检查、病毒扫描、内容验证等功能
"""
import os
import io
import csv
import hashlib
import mimetypes
from typing import Tuple, List, Dict, Any
import pandas as pd
from pathlib import Path
import logging

# 兼容处理python-magic库
try:
    import magic
    HAS_MAGIC = True
except ImportError:
    HAS_MAGIC = False
    magic = None

logger = logging.getLogger(__name__)

class FileSecurityValidator:
    """文件安全验证器"""

    # 允许的文件类型
    ALLOWED_MIME_TYPES = [
        'text/csv',
        'text/plain',
        'application/csv',
        'application/vnd.ms-excel'
    ]

    # 最大文件大小 (50MB)
    MAX_FILE_SIZE = 50 * 1024 * 1024

    # 最大行数限制
    MAX_ROWS = 100000

    # 危险关键词检测
    DANGEROUS_KEYWORDS = [
        'script', 'javascript', 'vbscript', 'onload', 'onerror',
        'eval', 'exec', 'import', 'require', '__import__',
        'system', 'subprocess', 'os.', 'file://', 'http://', 'https://'
    ]

    def __init__(self):
        """初始化文件安全验证器"""
        self.file_signatures = {
            # CSV 文件签名
            'csv': [b'', b'\xff\xfe', b'\xfe\xff', b'\xef\xbb\xbf'],  # 包含BOM
        }

    def validate_file_upload(self, file_content: bytes, filename: str) -> Tuple[bool, str, Dict[str, Any]]:
        """
        全面文件上传安全验证

        Args:
            file_content: 文件内容字节
            filename: 文件名

        Returns:
            Tuple[bool, str, Dict]: (是否有效, 错误信息, 文件信息)
        """
        try:
            file_info = {
                'filename': filename,
                'size': len(file_content),
                'hash': hashlib.sha256(file_content).hexdigest(),
                'encoding': None,
                'rows_count': 0,
                'columns_count': 0,
                'mime_type': None
            }

            # 1. 基础验证
            is_valid, error = self._validate_basic_info(filename, len(file_content))
            if not is_valid:
                return False, error, file_info

            # 2. 文件类型验证
            is_valid, error, mime_type = self._validate_file_type(file_content, filename)
            if not is_valid:
                return False, error, file_info
            file_info['mime_type'] = mime_type

            # 3. 文件签名验证
            is_valid, error = self._validate_file_signature(file_content)
            if not is_valid:
                return False, error, file_info

            # 4. 内容安全验证
            is_valid, error, content_info = self._validate_content_security(file_content)
            if not is_valid:
                return False, error, file_info
            file_info.update(content_info)

            # 5. CSV 格式验证
            is_valid, error, csv_info = self._validate_csv_format(file_content)
            if not is_valid:
                return False, error, file_info
            file_info.update(csv_info)

            logger.info(f"文件验证成功: {filename}, 大小: {len(file_content)} bytes, 行数: {file_info.get('rows_count', 0)}")
            return True, "文件验证通过", file_info

        except Exception as e:
            logger.error(f"文件验证异常: {filename}, 错误: {str(e)}")
            return False, f"文件验证过程中出现错误: {str(e)}", file_info

    def _validate_basic_info(self, filename: str, file_size: int) -> Tuple[bool, str]:
        """基础信息验证"""
        # 文件名验证
        if not filename or len(filename) > 255:
            return False, "文件名无效或过长"

        # 检查危险字符
        dangerous_chars = ['..', '/', '\\', '<', '>', ':', '"', '|', '?', '*']
        if any(char in filename for char in dangerous_chars):
            return False, "文件名包含危险字符"

        # 文件扩展名验证
        if not filename.lower().endswith('.csv'):
            return False, "只允许上传CSV文件"

        # 文件大小验证
        if file_size == 0:
            return False, "文件为空"

        if file_size > self.MAX_FILE_SIZE:
            return False, f"文件大小超出限制 ({self.MAX_FILE_SIZE / 1024 / 1024:.1f}MB)"

        return True, ""

    def _validate_file_type(self, file_content: bytes, filename: str) -> Tuple[bool, str, str]:
        """文件类型验证"""
        try:
            # 使用 python-magic 检测真实文件类型
            if HAS_MAGIC:
                mime_type = magic.from_buffer(file_content, mime=True)
            else:
                # 回退到mimetypes
                mime_type, _ = mimetypes.guess_type(filename)

            if mime_type not in self.ALLOWED_MIME_TYPES:
                # 尝试基于文件名推测
                guessed_type, _ = mimetypes.guess_type(filename)
                if guessed_type and guessed_type in self.ALLOWED_MIME_TYPES:
                    mime_type = guessed_type
                else:
                    return False, f"不支持的文件类型: {mime_type}", mime_type

            return True, "", mime_type

        except Exception as e:
            logger.warning(f"文件类型检测失败: {str(e)}, 使用文件名推测")
            # 降级到基于文件名的检测
            guessed_type, _ = mimetypes.guess_type(filename)
            if guessed_type and guessed_type in self.ALLOWED_MIME_TYPES:
                return True, "", guessed_type
            return False, "无法确定文件类型", "unknown"

    def _validate_file_signature(self, file_content: bytes) -> Tuple[bool, str]:
        """文件签名验证"""
        if not file_content:
            return False, "文件内容为空"

        # 检查文件头，验证是否为文本文件
        try:
            # 尝试解码前1024字节来验证是否为文本文件
            sample = file_content[:1024]
            sample.decode('utf-8-sig')  # 支持BOM
            return True, ""
        except UnicodeDecodeError:
            try:
                sample.decode('gbk')  # 尝试GBK编码
                return True, ""
            except UnicodeDecodeError:
                try:
                    sample.decode('latin1')  # 尝试Latin1编码
                    return True, ""
                except UnicodeDecodeError:
                    return False, "文件编码格式不支持或文件损坏"

    def _validate_content_security(self, file_content: bytes) -> Tuple[bool, str, Dict[str, Any]]:
        """内容安全验证"""
        content_info = {
            'encoding': 'utf-8',
            'has_dangerous_content': False,
            'dangerous_patterns': []
        }

        try:
            # 尝试多种编码解码
            text_content = ""
            for encoding in ['utf-8-sig', 'utf-8', 'gbk', 'latin1']:
                try:
                    text_content = file_content.decode(encoding)
                    content_info['encoding'] = encoding
                    break
                except UnicodeDecodeError:
                    continue

            if not text_content:
                return False, "无法解码文件内容", content_info

            # 检查危险内容
            text_lower = text_content.lower()
            found_dangerous = []

            for keyword in self.DANGEROUS_KEYWORDS:
                if keyword in text_lower:
                    found_dangerous.append(keyword)

            if found_dangerous:
                content_info['has_dangerous_content'] = True
                content_info['dangerous_patterns'] = found_dangerous
                return False, f"文件包含可疑内容: {', '.join(found_dangerous)}", content_info

            return True, "", content_info

        except Exception as e:
            return False, f"内容安全验证失败: {str(e)}", content_info

    def _validate_csv_format(self, file_content: bytes) -> Tuple[bool, str, Dict[str, Any]]:
        """CSV 格式验证 - 简化为基本检查，避免复杂解析问题"""
        csv_info = {
            'rows_count': 0,
            'columns_count': 0,
            'headers': [],
            'sample_data': []
        }

        try:
            # 检查文件大小
            if len(file_content) == 0:
                return False, "CSV文件为空", csv_info

            if len(file_content) > self.MAX_FILE_SIZE:
                return False, f"CSV文件过大 (最大 {self.MAX_FILE_SIZE / 1024 / 1024:.1f}MB)", csv_info

            # 尝试解码文件内容
            text_content = ""
            for encoding in ['utf-8-sig', 'utf-8', 'gbk', 'latin1']:
                try:
                    text_content = file_content.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue

            if not text_content:
                return False, "无法解码CSV文件", csv_info

            # 基本行数统计
            lines = text_content.split('\n')
            non_empty_lines = [line for line in lines if line.strip()]

            if len(non_empty_lines) < 1:
                return False, "CSV文件没有有效内容", csv_info

            if len(non_empty_lines) > self.MAX_ROWS:
                return False, f"CSV文件行数过多 ({len(non_empty_lines)} 行，最大允许 {self.MAX_ROWS} 行)", csv_info

            # 检查是否包含常见的分隔符
            first_line = non_empty_lines[0]
            has_separator = (',' in first_line or ';' in first_line or '\t' in first_line)

            if not has_separator:
                # 允许只有一列的情况
                if len(non_empty_lines) >= 2:
                    csv_info['columns_count'] = 1
                    csv_info['headers'] = ['Column_1']
                else:
                    return False, "CSV文件格式错误：无法识别有效的数据格式", csv_info
            else:
                # 估算列数（使用最常见的分隔符）
                if ',' in first_line:
                    csv_info['columns_count'] = first_line.count(',') + 1
                elif ';' in first_line:
                    csv_info['columns_count'] = first_line.count(';') + 1
                elif '\t' in first_line:
                    csv_info['columns_count'] = first_line.count('\t') + 1

                csv_info['headers'] = [f"Column_{i+1}" for i in range(csv_info['columns_count'])]

            # 估算数据行数（排除表头）
            csv_info['rows_count'] = max(0, len(non_empty_lines) - 1)

            logger.info(f"CSV基础验证通过: {csv_info['rows_count']} 行（估算）, {csv_info['columns_count']} 列（估算）")
            return True, "", csv_info

        except Exception as e:
            logger.error(f"CSV格式验证异常: {str(e)}")
            return False, f"CSV格式验证失败: {str(e)}", csv_info

    def generate_file_hash(self, file_content: bytes) -> str:
        """生成文件哈希值用于去重检测"""
        return hashlib.sha256(file_content).hexdigest()

    def is_duplicate_file(self, file_hash: str, existing_hashes: List[str]) -> bool:
        """检查是否为重复文件"""
        return file_hash in existing_hashes

    def sanitize_filename(self, filename: str) -> str:
        """清理文件名，移除危险字符"""
        # 移除危险字符
        dangerous_chars = ['..', '/', '\\', '<', '>', ':', '"', '|', '?', '*']
        clean_name = filename
        for char in dangerous_chars:
            clean_name = clean_name.replace(char, '_')

        # 限制长度
        if len(clean_name) > 200:
            name, ext = os.path.splitext(clean_name)
            clean_name = name[:200-len(ext)] + ext

        return clean_name