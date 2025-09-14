import aiohttp
import json
from typing import Optional, Dict, Any, Tuple
import logging
import os
import asyncio

logger = logging.getLogger(__name__)

class DifyService:
    def __init__(self, api_key: str, base_url: str = "https://api.dify.ai/v1"):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }

    async def upload_file_async(self, file_path: str, filename: str) -> Optional[str]:
        """异步上传文件到Dify"""
        url = f"{self.base_url}/files/upload"

        try:
            if not os.path.exists(file_path):
                logger.error(f"文件不存在: {file_path}")
                return None

            # 配置连接器和超时设置来处理大文件
            connector = aiohttp.TCPConnector(
                limit=100,
                limit_per_host=30,
                keepalive_timeout=300,
            )

            timeout = aiohttp.ClientTimeout(
                total=300,  # 总超时时间5分钟
                connect=60,  # 连接超时1分钟
                sock_read=120  # 读取超时2分钟
            )

            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                with open(file_path, 'rb') as f:
                    data = aiohttp.FormData()
                    data.add_field('file', f, filename=filename, content_type='text/csv')

                    headers = {
                        'Authorization': f'Bearer {self.api_key}'
                    }

                    async with session.post(url, headers=headers, data=data) as response:
                        if response.status in [200, 201]:
                            result = await response.json()
                            file_id = result.get('id')
                            if file_id:
                                logger.info(f"✅ 文件上传成功: {filename}")
                                return file_id
                            else:
                                logger.error("❌ 响应中没有找到文件ID")
                                return None
                        else:
                            error_text = await response.text()
                            logger.error(f"❌ 文件上传失败: {filename}")
                            logger.error(f"状态码: {response.status}")
                            logger.error(f"错误详情: {error_text}")
                            return None

        except Exception as e:
            logger.error(f"❌ 上传文件时发生错误: {str(e)}")
            return None
    
    async def run_workflow_async(self, file_id: str) -> Optional[Dict[Any, Any]]:
        """异步运行工作流 - 使用流式输出"""
        url = f"{self.base_url}/workflows/run"

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
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

        try:
            logger.info("🔄 开始异步流式处理工作流...")

            # 配置连接器和超时设置来处理大文件
            connector = aiohttp.TCPConnector(
                limit=100,
                limit_per_host=30,
                keepalive_timeout=300,
            )

            timeout = aiohttp.ClientTimeout(
                total=600,  # 总超时时间10分钟
                connect=60,  # 连接超时1分钟
                sock_read=300  # 读取超时5分钟
            )

            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        logger.info("📡 接收流式数据...")

                        # 处理流式数据
                        final_result = None
                        total_nodes = 0
                        completed_nodes = 0

                        # 使用 content.iter_chunked 来避免 "Chunk too big" 错误
                        buffer = b""  # 使用字节缓冲区
                        text_buffer = ""  # 文本缓冲区

                        async for chunk in response.content.iter_chunked(8192):  # 8KB chunks
                            if chunk:
                                try:
                                    # 将新的字节块添加到缓冲区
                                    buffer += chunk

                                    # 尝试解码缓冲区中的所有字节
                                    try:
                                        # 解码整个缓冲区
                                        decoded_text = buffer.decode('utf-8')
                                        # 如果解码成功，清空字节缓冲区，将文本添加到文本缓冲区
                                        buffer = b""
                                        text_buffer += decoded_text
                                    except UnicodeDecodeError as e:
                                        # 如果解码失败，可能是因为在多字节字符中间截断了
                                        # 尝试找到最后一个完整的UTF-8字符边界
                                        if len(buffer) > 0:
                                            # 从末尾开始，找到一个完整的UTF-8字符序列
                                            for i in range(len(buffer) - 1, max(len(buffer) - 4, -1), -1):
                                                try:
                                                    # 尝试解码到位置i
                                                    decoded_text = buffer[:i].decode('utf-8')
                                                    # 如果成功，保留完整部分，未完整部分留在缓冲区
                                                    text_buffer += decoded_text
                                                    buffer = buffer[i:]
                                                    break
                                                except UnicodeDecodeError:
                                                    continue
                                            else:
                                                # 如果找不到完整边界，跳过这个块
                                                logger.warning(f"⚠️ 跳过无法解码的数据块，长度: {len(buffer)}")
                                                buffer = b""
                                                continue

                                    # 按行分割处理文本缓冲区
                                    while '\n' in text_buffer:
                                        line, text_buffer = text_buffer.split('\n', 1)
                                        line = line.strip()

                                        # 跳过空行和非数据行
                                        if not line or not line.startswith('data: '):
                                            continue

                                        # 提取JSON数据
                                        json_str = line[6:]  # 移除 'data: ' 前缀

                                        try:
                                            chunk_data = json.loads(json_str)

                                            # 实时处理流式事件
                                            event = chunk_data.get('event', '')

                                            if event == 'node_started':
                                                node_data = chunk_data.get('data', {})
                                                node_title = node_data.get('title', '未知节点')
                                                logger.info(f"  🔸 开始处理: {node_title}")
                                                total_nodes += 1

                                            elif event == 'node_finished':
                                                node_data = chunk_data.get('data', {})
                                                node_title = node_data.get('title', '未知节点')
                                                logger.info(f"  ✅ 完成处理: {node_title}")
                                                completed_nodes += 1

                                            elif event == 'workflow_finished':
                                                logger.info("🎉 工作流处理完成")
                                                final_result = chunk_data
                                                break

                                            elif event == 'error':
                                                error_msg = chunk_data.get('data', {}).get('message', '未知错误')
                                                logger.error(f"❌ 处理过程中出现错误: {error_msg}")
                                                return None

                                        except json.JSONDecodeError as e:
                                            logger.warning(f"⚠️ 解析流数据失败 (行长度: {len(json_str)}): {str(e)[:100]}...")
                                            continue

                                except Exception as e:
                                    logger.warning(f"⚠️ 处理chunk时发生错误: {e}")
                                    continue

                        # 返回最终结果
                        if final_result:
                            logger.info(f"✅ 工作流执行成功")
                            return final_result
                        else:
                            logger.error("❌ 未收到完整的工作流结果")
                            return None

                    else:
                        error_text = await response.text()
                        logger.error(f"❌ 工作流执行失败")
                        logger.error(f"状态码: {response.status}")
                        logger.error(f"错误详情: {error_text}")
                        return None

        except Exception as e:
            logger.error(f"❌ 执行工作流时发生错误: {str(e)}")
            return None

    async def process_file_async(self, file_path: str, filename: str) -> Optional[Dict[Any, Any]]:
        """异步处理单个文件：上传并运行工作流"""
        logger.info(f"\n🚀 开始异步处理文件: {filename}")

        # 上传文件
        file_id = await self.upload_file_async(file_path, filename)
        if not file_id:
            logger.error(f"❌ 文件上传失败")
            return None

        # 运行工作流
        workflow_result = await self.run_workflow_async(file_id)
        if not workflow_result:
            logger.error(f"❌ 文件工作流执行失败")
            return None

        logger.info(f"✅ 文件异步处理完成")
        return workflow_result

    def extract_sources_from_result(self, workflow_result: Dict[Any, Any]) -> Tuple[Optional[list], Optional[list]]:
        """从工作流结果中提取境内外数据源"""
        try:
            data = workflow_result.get('data', {})
            outputs = data.get('outputs', {})
            structured_output = outputs.get('structured_output', {})

            domestic_sources = structured_output.get('domestic_sources', [])
            foreign_sources = structured_output.get('foreign_sources', [])

            logger.info(f"✅ 数据提取成功:")
            logger.info(f"- 境内条目数: {len(domestic_sources)}")
            logger.info(f"- 境外条目数: {len(foreign_sources)}")

            return domestic_sources, foreign_sources

        except Exception as e:
            logger.error(f"❌ 提取数据源时发生错误: {str(e)}")
            return None, None