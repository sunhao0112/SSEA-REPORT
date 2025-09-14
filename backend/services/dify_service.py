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
                                                # 只记录关键节点
                                                if 'LLM' in node_title or '文档' in node_title:
                                                    logger.info(f"  🔸 开始处理: {node_title}")
                                                total_nodes += 1

                                            elif event == 'node_finished':
                                                node_data = chunk_data.get('data', {})
                                                node_title = node_data.get('title', '未知节点')
                                                # 只记录关键节点
                                                if 'LLM' in node_title or '文档' in node_title:
                                                    logger.info(f"  ✅ 完成处理: {node_title}")
                                                completed_nodes += 1

                                            elif event == 'workflow_finished':
                                                logger.info("🎉 工作流处理完成")
                                                final_result = chunk_data

                                                # 检查工作流是否实际成功
                                                data = chunk_data.get('data', {})
                                                workflow_status = data.get('status')

                                                if workflow_status == 'failed':
                                                    error_msg = data.get('error', '未知错误')
                                                    detailed_error = self._parse_workflow_error({'message': error_msg})
                                                    logger.error(f"❌ 工作流执行失败: {detailed_error}")
                                                    return {'error': detailed_error, 'error_data': data, 'raw_error': error_msg}
                                                elif workflow_status in ['running', 'pending']:
                                                    logger.warning(f"⚠️ 工作流未完成，状态: {workflow_status}")
                                                    return {'error': f'工作流未完成，当前状态: {workflow_status}', 'status': workflow_status}

                                                break

                                            elif event == 'error':
                                                error_data = chunk_data.get('data', {})
                                                detailed_error = self._parse_workflow_error(error_data)
                                                logger.error(f"❌ 工作流处理过程中出现错误: {detailed_error}")
                                                return {'error': detailed_error, 'error_data': error_data}

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
                        detailed_error = self._parse_http_error(response.status, error_text)
                        logger.error(f"❌ 工作流执行失败")
                        logger.error(f"状态码: {response.status}")
                        logger.error(f"详细错误: {detailed_error}")
                        return {'error': detailed_error, 'status_code': response.status, 'raw_error': error_text}

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
            return {'error': '文件上传到Dify失败，请检查网络连接或文件格式'}

        # 运行工作流
        workflow_result = await self.run_workflow_async(file_id)
        if not workflow_result:
            logger.error(f"❌ 文件工作流执行失败")
            return {'error': '工作流执行失败，可能是网络连接问题或API服务不可用'}

        # 如果结果本身就是错误，直接返回
        if isinstance(workflow_result, dict) and 'error' in workflow_result:
            return workflow_result

        logger.info(f"✅ 文件异步处理完成")
        return workflow_result

    def extract_sources_from_result(self, workflow_result: Dict[Any, Any]) -> Tuple[Optional[list], Optional[list]]:
        """从工作流结果中提取境内外数据源"""
        try:
            # 检查是否是错误结果
            if 'error' in workflow_result:
                logger.error(f"❌ 工作流返回错误: {workflow_result['error']}")
                return None, None

            # 安全地检查每一级是否存在
            if not workflow_result:
                logger.error("❌ workflow_result 为空")
                return None, None

            # 记录完整的工作流结果结构以便调试
            logger.info(f"📋 工作流结果结构: {list(workflow_result.keys())}")

            data = workflow_result.get('data')
            if not data:
                logger.error("❌ workflow_result 中没有 'data' 字段")
                logger.error(f"❌ 可用字段: {list(workflow_result.keys())}")
                return None, None

            # 记录data结构
            logger.info(f"📋 data 字段结构: {list(data.keys()) if isinstance(data, dict) else type(data)}")

            # 检查工作流状态
            workflow_status = data.get('status')
            if workflow_status:
                logger.info(f"🔄 工作流状态: {workflow_status}")

                if workflow_status == 'failed':
                    error_msg = data.get('error', '未知错误')
                    logger.error(f"❌ 工作流执行失败: {error_msg}")
                    return None, None
                elif workflow_status == 'running':
                    logger.warning("⚠️ 工作流仍在运行中，可能未完成")
                    return None, None
                elif workflow_status != 'succeeded':
                    logger.warning(f"⚠️ 工作流状态异常: {workflow_status}")

            outputs = data.get('outputs')
            if not outputs:
                logger.error("❌ data 中没有 'outputs' 字段")
                logger.error(f"❌ data 中可用字段: {list(data.keys()) if isinstance(data, dict) else 'data不是字典类型'}")

                # 检查是否有其他可能的输出字段
                possible_output_fields = ['output', 'result', 'response', 'content']
                for field in possible_output_fields:
                    if field in data:
                        logger.info(f"🔍 发现可能的输出字段: {field}")
                        outputs = data[field]
                        break

                if not outputs:
                    return None, None

            # 记录outputs结构
            logger.info(f"📋 outputs 字段结构: {list(outputs.keys()) if isinstance(outputs, dict) else type(outputs)}")

            structured_output = outputs.get('structured_output')
            if not structured_output:
                logger.error("❌ outputs 中没有 'structured_output' 字段")
                logger.error(f"❌ outputs 中可用字段: {list(outputs.keys()) if isinstance(outputs, dict) else 'outputs不是字典类型'}")

                # 尝试其他可能的结构化输出字段名
                possible_structured_fields = ['structured_data', 'parsed_output', 'analysis_result', 'classification']
                for field in possible_structured_fields:
                    if field in outputs:
                        logger.info(f"🔍 发现可能的结构化输出字段: {field}")
                        structured_output = outputs[field]
                        break

                if not structured_output:
                    # 如果没有结构化输出，尝试直接从outputs获取
                    if 'domestic_sources' in outputs or 'foreign_sources' in outputs:
                        logger.info("🔍 直接从outputs获取数据源")
                        domestic_sources = outputs.get('domestic_sources', [])
                        foreign_sources = outputs.get('foreign_sources', [])
                    else:
                        return None, None
                else:
                    domestic_sources = structured_output.get('domestic_sources', [])
                    foreign_sources = structured_output.get('foreign_sources', [])
            else:
                domestic_sources = structured_output.get('domestic_sources', [])
                foreign_sources = structured_output.get('foreign_sources', [])

            # 记录最终结果
            logger.info(f"✅ 数据提取成功:")
            logger.info(f"- 境内条目数: {len(domestic_sources) if domestic_sources else 0}")
            logger.info(f"- 境外条目数: {len(foreign_sources) if foreign_sources else 0}")

            return domestic_sources, foreign_sources

        except Exception as e:
            logger.error(f"❌ 提取数据源时发生错误: {str(e)}")
            logger.error(f"❌ 完整工作流结果: {workflow_result}")
            return None, None

    def _parse_workflow_error(self, error_data: dict) -> str:
        """解析工作流错误信息，提供详细的用户友好错误描述"""
        try:
            # 获取基础错误信息
            message = error_data.get('message', '未知错误')
            error_type = error_data.get('error_type', '未知类型')

            # 尝试解析嵌套的错误信息
            if 'PluginInvokeError' in message:
                # 解析插件调用错误
                return self._parse_plugin_error(message)

            # 检查常见的API错误模式
            if '429' in message or 'RESOURCE_EXHAUSTED' in message:
                return self._parse_quota_error(message)
            elif '401' in message or 'unauthorized' in message.lower():
                return "API认证失败：请检查API密钥是否正确配置"
            elif '403' in message or 'forbidden' in message.lower():
                return "API访问被拒绝：权限不足或API密钥无效"
            elif '500' in message or 'internal server error' in message.lower():
                return "API服务内部错误：建议稍后重试"
            elif 'timeout' in message.lower():
                return "请求超时：数据量可能过大或网络连接不稳定"
            elif 'connection' in message.lower():
                return "网络连接错误：无法连接到API服务"

            # 返回原始错误信息（如果无法解析）
            return f"{error_type}: {message}"

        except Exception as e:
            logger.warning(f"解析工作流错误失败: {e}")
            return str(error_data)

    def _parse_plugin_error(self, message: str) -> str:
        """解析插件调用错误"""
        try:
            # 查找JSON部分
            if 'PluginInvokeError: {' in message:
                json_start = message.find('PluginInvokeError: {') + len('PluginInvokeError: ')
                json_part = message[json_start:]

                # 尝试解析JSON（可能被截断）
                try:
                    # 找到完整的JSON结构
                    brace_count = 0
                    json_end = 0
                    for i, char in enumerate(json_part):
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                json_end = i + 1
                                break

                    if json_end > 0:
                        json_str = json_part[:json_end]
                        error_obj = json.loads(json_str)
                        return self._parse_plugin_error_object(error_obj)

                except json.JSONDecodeError:
                    pass

            # 如果无法解析JSON，查找关键信息
            if '429 RESOURCE_EXHAUSTED' in message:
                return self._parse_quota_error(message)

            return f"插件调用错误: {message[:200]}..."

        except Exception as e:
            logger.warning(f"解析插件错误失败: {e}")
            return f"插件调用错误: {message[:200]}..."

    def _parse_plugin_error_object(self, error_obj: dict) -> str:
        """解析插件错误对象"""
        error_type = error_obj.get('error_type', '未知类型')
        message = error_obj.get('message', '未知错误')

        if error_type == 'ClientError' and '429' in message:
            return self._parse_quota_error(message)
        elif error_type == 'ClientError' and '401' in message:
            return "API认证错误：请检查Google Gemini API密钥配置"
        elif error_type == 'ClientError' and '403' in message:
            return "API访问被禁止：请检查API密钥权限或项目配置"
        elif error_type == 'ClientError':
            return f"API客户端错误: {message[:200]}..."
        else:
            return f"{error_type}: {message[:200]}..."

    def _parse_quota_error(self, message: str) -> str:
        """解析配额错误，提供具体的解决建议"""
        try:
            # 检查具体的配额类型
            if 'generate_content_free_tier_input_token_count' in message:
                if 'GenerateContentInputTokensPerModelPerMinute-FreeTier' in message:
                    return ("Google Gemini API 免费配额已用完（每分钟250,000 tokens限制）\n"
                           "建议解决方案：\n"
                           "1. 等待1分钟后重试\n"
                           "2. 减少单次处理的数据量\n"
                           "3. 升级到付费版本以获得更高配额")
                else:
                    return ("Google Gemini API 配额不足\n"
                           "请检查您的API配额限制或升级计划")
            elif 'quota' in message.lower() or '配额' in message:
                return ("API配额已达上限\n"
                       "建议：等待配额重置或联系API提供商升级服务")
            elif '429' in message:
                return ("API请求频率过高（429错误）\n"
                       "建议：等待几分钟后重试，或减少并发请求数量")
            else:
                return f"配额限制错误: {message[:200]}..."

        except Exception as e:
            return "API配额错误：请稍后重试或联系系统管理员"

    def _parse_http_error(self, status_code: int, error_text: str) -> str:
        """解析HTTP错误响应"""
        try:
            # 尝试解析JSON错误响应
            try:
                error_obj = json.loads(error_text)
                if isinstance(error_obj, dict):
                    # 检查是否是工作流错误响应
                    if 'data' in error_obj and 'error' in error_obj['data']:
                        return self._parse_workflow_error(error_obj['data'])
                    elif 'message' in error_obj:
                        return f"API错误: {error_obj['message']}"
                    elif 'error' in error_obj:
                        if isinstance(error_obj['error'], str):
                            return f"API错误: {error_obj['error']}"
                        elif isinstance(error_obj['error'], dict):
                            error_msg = error_obj['error'].get('message', str(error_obj['error']))
                            return f"API错误: {error_msg}"
            except json.JSONDecodeError:
                pass

            # 根据HTTP状态码提供友好错误信息
            if status_code == 400:
                return f"请求参数错误 (400): {error_text[:200]}..."
            elif status_code == 401:
                return "API认证失败 (401)：请检查API密钥配置"
            elif status_code == 403:
                return "API访问被禁止 (403)：权限不足或API密钥无效"
            elif status_code == 429:
                return "API请求频率过高 (429)：请等待后重试"
            elif status_code == 500:
                return "API服务内部错误 (500)：建议稍后重试"
            elif status_code == 502:
                return "API网关错误 (502)：服务暂时不可用"
            elif status_code == 503:
                return "API服务不可用 (503)：服务器维护中"
            elif status_code == 504:
                return "API请求超时 (504)：数据处理时间过长"
            else:
                return f"HTTP错误 ({status_code}): {error_text[:200]}..."

        except Exception as e:
            return f"HTTP错误 ({status_code}): 无法解析错误详情"