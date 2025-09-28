"""
千问API接口模块

这个模块负责与阿里云千问qwen3-livetranslate-flash-realtime模型进行通信，
实现实时音视频翻译功能。支持WebSocket连接、流式数据传输和多模态翻译。
"""

import json
import logging
import asyncio
import websockets
import base64
import time
from typing import Optional, Dict, Any, Callable, AsyncGenerator, Tuple
from dataclasses import dataclass
from enum import Enum
import threading
from concurrent.futures import Future
import uuid

from ..utils.config import get_config


class MessageType(Enum):
    """消息类型枚举"""
    SESSION_CONFIG = "session.configure"
    INPUT_AUDIO = "input_audio.data"
    INPUT_IMAGE = "input_image.data"
    SESSION_END = "session.end"
    RESPONSE_TEXT = "response.text"
    RESPONSE_AUDIO = "response.audio"
    ERROR = "error"


@dataclass
class TranslationResponse:
    """翻译响应数据类"""
    text: Optional[str] = None
    audio_data: Optional[bytes] = None
    timestamp: float = 0.0
    is_final: bool = False
    error: Optional[str] = None


class QwenAPIClient:
    """千问API客户端"""
    
    def __init__(self, config=None):
        self.config = config or get_config()
        self.logger = logging.getLogger(__name__)
        
        # WebSocket连接
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.session_id: str = ""
        self.is_connected: bool = False
        self.is_session_configured: bool = False
        
        # 回调函数
        self.text_callback: Optional[Callable[[str, bool], None]] = None
        self.audio_callback: Optional[Callable[[bytes], None]] = None
        self.error_callback: Optional[Callable[[str], None]] = None
        
        # 状态管理
        self._lock = threading.Lock()
        self._response_buffer = []
        self._audio_buffer = []
        
        # 性能统计
        self.stats = {
            'messages_sent': 0,
            'messages_received': 0,
            'audio_chunks_sent': 0,
            'image_frames_sent': 0,
            'connection_time': 0,
            'total_latency': 0,
            'error_count': 0
        }
    
    async def connect(self) -> bool:
        """
        建立WebSocket连接
        
        Returns:
            bool: 连接是否成功
        """
        try:
            start_time = time.time()
            
            # 构建连接URL
            url = self.config.api.api_url
            headers = {
                'Authorization': f'Bearer {self.config.api.api_key}',
                'X-DashScope-DataInspection': 'enable'
            }
            
            self.logger.info(f"正在连接到千问API: {url}")
            
            # 建立WebSocket连接
            self.websocket = await websockets.connect(
                url,
                extra_headers=headers,
                ping_interval=30,
                ping_timeout=10,
                close_timeout=10
            )
            
            self.is_connected = True
            self.session_id = str(uuid.uuid4())
            connection_time = time.time() - start_time
            self.stats['connection_time'] = connection_time
            
            self.logger.info(f"连接成功，会话ID: {self.session_id}, 耗时: {connection_time:.2f}秒")
            
            # 启动消息接收任务
            asyncio.create_task(self._message_receiver())
            
            return True
            
        except Exception as e:
            self.logger.error(f"连接失败: {e}")
            self.is_connected = False
            self.stats['error_count'] += 1
            return False
    
    async def configure_session(self) -> bool:
        """
        配置翻译会话
        
        Returns:
            bool: 配置是否成功
        """
        try:
            if not self.is_connected:
                raise RuntimeError("WebSocket未连接")
            
            # 构建会话配置消息
            config_message = {
                "type": MessageType.SESSION_CONFIG.value,
                "session": {
                    "session_id": self.session_id,
                    "model_name": self.config.api.model_name,
                    "model_parameters": {
                        "output_modalities": ["text", "audio"],
                        "target_language": self.config.api.target_language,
                        "voice": {
                            "name": self.config.api.voice_type
                        },
                        "input_audio_format": self.config.audio.audio_format,
                        "output_audio_format": self.config.audio.audio_format,
                        "input_audio_sample_rate": self.config.audio.input_sample_rate,
                        "output_audio_sample_rate": self.config.audio.output_sample_rate
                    }
                }
            }
            
            self.logger.info("发送会话配置...")
            await self._send_message(config_message)
            
            # 等待配置确认（简化处理，实际应该等待响应）
            await asyncio.sleep(1)
            self.is_session_configured = True
            
            self.logger.info("会话配置完成")
            return True
            
        except Exception as e:
            self.logger.error(f"会话配置失败: {e}")
            self.stats['error_count'] += 1
            return False
    
    async def send_audio_chunk(self, audio_data: bytes) -> bool:
        """
        发送音频数据块
        
        Args:
            audio_data: 音频数据（PCM16格式）
            
        Returns:
            bool: 发送是否成功
        """
        try:
            if not self.is_session_configured:
                raise RuntimeError("会话未配置")
            
            # 将音频数据编码为Base64
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            
            # 构建音频消息
            audio_message = {
                "type": MessageType.INPUT_AUDIO.value,
                "audio": {
                    "data": audio_base64,
                    "format": self.config.audio.audio_format,
                    "sample_rate": self.config.audio.input_sample_rate,
                    "channels": self.config.audio.channels
                }
            }
            
            await self._send_message(audio_message)
            self.stats['audio_chunks_sent'] += 1
            
            return True
            
        except Exception as e:
            self.logger.error(f"发送音频数据失败: {e}")
            self.stats['error_count'] += 1
            return False
    
    async def send_image_frame(self, image_data: bytes, timestamp: float) -> bool:
        """
        发送视频帧图像数据
        
        Args:
            image_data: Base64编码的JPEG图像数据
            timestamp: 时间戳
            
        Returns:
            bool: 发送是否成功
        """
        try:
            if not self.is_session_configured:
                raise RuntimeError("会话未配置")
            
            # 如果传入的是原始bytes，需要编码为base64
            if isinstance(image_data, bytes):
                image_base64 = base64.b64encode(image_data).decode('utf-8')
            else:
                image_base64 = image_data.decode('utf-8') if isinstance(image_data, bytes) else image_data
            
            # 构建图像消息
            image_message = {
                "type": MessageType.INPUT_IMAGE.value,
                "image": {
                    "data": image_base64,
                    "format": "jpeg",
                    "timestamp": timestamp
                }
            }
            
            await self._send_message(image_message)
            self.stats['image_frames_sent'] += 1
            
            return True
            
        except Exception as e:
            self.logger.error(f"发送图像数据失败: {e}")
            self.stats['error_count'] += 1
            return False
    
    async def end_session(self) -> bool:
        """
        结束翻译会话
        
        Returns:
            bool: 结束是否成功
        """
        try:
            if not self.is_connected:
                return True
            
            # 发送会话结束消息
            end_message = {
                "type": MessageType.SESSION_END.value,
                "session": {
                    "session_id": self.session_id
                }
            }
            
            await self._send_message(end_message)
            self.logger.info("会话结束消息已发送")
            
            # 等待一段时间让服务器处理
            await asyncio.sleep(2)
            
            return True
            
        except Exception as e:
            self.logger.error(f"结束会话失败: {e}")
            return False
    
    async def disconnect(self):
        """断开WebSocket连接"""
        try:
            if self.websocket and not self.websocket.closed:
                await self.websocket.close()
            
            self.is_connected = False
            self.is_session_configured = False
            self.logger.info("WebSocket连接已断开")
            
        except Exception as e:
            self.logger.error(f"断开连接时发生错误: {e}")
    
    def set_callbacks(self, 
                     text_callback: Optional[Callable[[str, bool], None]] = None,
                     audio_callback: Optional[Callable[[bytes], None]] = None,
                     error_callback: Optional[Callable[[str], None]] = None):
        """
        设置回调函数
        
        Args:
            text_callback: 文本响应回调函数，参数为(text, is_final)
            audio_callback: 音频响应回调函数，参数为(audio_data)
            error_callback: 错误回调函数，参数为(error_message)
        """
        self.text_callback = text_callback
        self.audio_callback = audio_callback
        self.error_callback = error_callback
    
    async def _send_message(self, message: Dict[str, Any]):
        """
        发送消息到WebSocket
        
        Args:
            message: 要发送的消息
        """
        try:
            if not self.websocket or self.websocket.closed:
                raise RuntimeError("WebSocket连接不可用")
            
            message_json = json.dumps(message, ensure_ascii=False)
            await self.websocket.send(message_json)
            
            self.stats['messages_sent'] += 1
            self.logger.debug(f"消息已发送: {message['type']}")
            
        except Exception as e:
            self.logger.error(f"发送消息失败: {e}")
            raise
    
    async def _message_receiver(self):
        """消息接收器（后台任务）"""
        try:
            self.logger.info("消息接收器已启动")
            
            async for message in self.websocket:
                try:
                    await self._handle_message(message)
                except Exception as e:
                    self.logger.error(f"处理接收消息时发生错误: {e}")
                    if self.error_callback:
                        self.error_callback(str(e))
        
        except websockets.exceptions.ConnectionClosed:
            self.logger.info("WebSocket连接已关闭")
            self.is_connected = False
        except Exception as e:
            self.logger.error(f"消息接收器发生错误: {e}")
            self.is_connected = False
            if self.error_callback:
                self.error_callback(str(e))
    
    async def _handle_message(self, message: str):
        """
        处理接收到的消息
        
        Args:
            message: 接收到的JSON消息
        """
        try:
            data = json.loads(message)
            message_type = data.get('type', '')
            
            self.stats['messages_received'] += 1
            self.logger.debug(f"收到消息: {message_type}")
            
            if message_type == 'response.audio_transcript.done':
                # 文本翻译完成
                text = data.get('text', '')
                if text and self.text_callback:
                    self.text_callback(text, True)
            
            elif message_type == 'response.audio.delta':
                # 音频数据片段
                audio_data = data.get('delta', '')
                if audio_data:
                    # 解码Base64音频数据
                    audio_bytes = base64.b64decode(audio_data)
                    if self.audio_callback:
                        self.audio_callback(audio_bytes)
            
            elif message_type == 'response.audio_transcript.delta':
                # 文本翻译片段（流式）
                text = data.get('delta', '')
                if text and self.text_callback:
                    self.text_callback(text, False)
            
            elif message_type == 'error':
                # 错误消息
                error_msg = data.get('error', {}).get('message', '未知错误')
                self.logger.error(f"API返回错误: {error_msg}")
                self.stats['error_count'] += 1
                if self.error_callback:
                    self.error_callback(error_msg)
            
            else:
                self.logger.debug(f"未处理的消息类型: {message_type}")
        
        except json.JSONDecodeError as e:
            self.logger.error(f"消息JSON解析失败: {e}")
        except Exception as e:
            self.logger.error(f"消息处理失败: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取性能统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        return self.stats.copy()


class TranslationEngine:
    """翻译引擎，提供高级接口"""
    
    def __init__(self, config=None):
        self.config = config or get_config()
        self.logger = logging.getLogger(__name__)
        self.client = QwenAPIClient(config)
        
        # 翻译结果缓存
        self.translated_texts = []
        self.audio_segments = []
        
        # 状态标识
        self.is_running = False
        self._translation_complete = False
    
    async def initialize(self) -> bool:
        """
        初始化翻译引擎
        
        Returns:
            bool: 初始化是否成功
        """
        try:
            self.logger.info("初始化翻译引擎...")
            
            # 设置回调函数
            self.client.set_callbacks(
                text_callback=self._on_text_received,
                audio_callback=self._on_audio_received,
                error_callback=self._on_error_received
            )
            
            # 建立连接
            if not await self.client.connect():
                return False
            
            # 配置会话
            if not await self.client.configure_session():
                return False
            
            self.is_running = True
            self.logger.info("翻译引擎初始化成功")
            return True
            
        except Exception as e:
            self.logger.error(f"翻译引擎初始化失败: {e}")
            return False
    
    async def translate_stream(self, 
                             audio_stream: AsyncGenerator[bytes, None],
                             image_stream: Optional[AsyncGenerator[Tuple[float, bytes], None]] = None) -> AsyncGenerator[TranslationResponse, None]:
        """
        流式翻译音视频数据
        
        Args:
            audio_stream: 音频数据流
            image_stream: 图像数据流（可选）
            
        Yields:
            TranslationResponse: 翻译响应
        """
        try:
            if not self.is_running:
                raise RuntimeError("翻译引擎未初始化")
            
            self.logger.info("开始流式翻译...")
            
            # 创建处理任务
            audio_task = asyncio.create_task(self._process_audio_stream(audio_stream))
            
            image_task = None
            if image_stream:
                image_task = asyncio.create_task(self._process_image_stream(image_stream))
            
            # 等待处理完成
            tasks = [audio_task]
            if image_task:
                tasks.append(image_task)
            
            await asyncio.gather(*tasks)
            
            # 发送结束信号
            await self.client.end_session()
            
            self.logger.info("流式翻译完成")
            
        except Exception as e:
            self.logger.error(f"流式翻译失败: {e}")
            raise
    
    async def _process_audio_stream(self, audio_stream: AsyncGenerator[bytes, None]):
        """处理音频流"""
        async for audio_chunk in audio_stream:
            if not self.is_running:
                break
            await self.client.send_audio_chunk(audio_chunk)
            # 控制发送频率，避免过载
            await asyncio.sleep(0.1)
    
    async def _process_image_stream(self, image_stream: AsyncGenerator[Tuple[float, bytes], None]):
        """处理图像流"""
        async for timestamp, image_data in image_stream:
            if not self.is_running:
                break
            await self.client.send_image_frame(image_data, timestamp)
            # 控制发送频率
            await asyncio.sleep(0.5)
    
    def _on_text_received(self, text: str, is_final: bool):
        """文本接收回调"""
        if is_final:
            self.translated_texts.append(text)
            self.logger.info(f"收到完整翻译文本: {text}")
        else:
            self.logger.debug(f"收到文本片段: {text}")
    
    def _on_audio_received(self, audio_data: bytes):
        """音频接收回调"""
        self.audio_segments.append(audio_data)
        self.logger.debug(f"收到音频片段，大小: {len(audio_data)} 字节")
    
    def _on_error_received(self, error_message: str):
        """错误接收回调"""
        self.logger.error(f"翻译过程中发生错误: {error_message}")
    
    async def shutdown(self):
        """关闭翻译引擎"""
        try:
            self.is_running = False
            await self.client.disconnect()
            self.logger.info("翻译引擎已关闭")
        except Exception as e:
            self.logger.error(f"关闭翻译引擎时发生错误: {e}")
    
    def get_translation_results(self) -> Tuple[list, list]:
        """
        获取翻译结果
        
        Returns:
            Tuple[list, list]: (翻译文本列表, 音频片段列表)
        """
        return self.translated_texts.copy(), self.audio_segments.copy()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self.client.get_stats()
        stats.update({
            'translated_texts_count': len(self.translated_texts),
            'audio_segments_count': len(self.audio_segments),
            'is_running': self.is_running
        })
        return stats


if __name__ == "__main__":
    # 测试千问API模块
    async def test_qwen_api():
        """测试API连接和基本功能"""
        try:
            engine = TranslationEngine()
            
            # 初始化
            if not await engine.initialize():
                print("初始化失败")
                return
            
            print("API连接测试成功")
            
            # 获取统计信息
            stats = engine.get_stats()
            print("统计信息:", stats)
            
            # 关闭
            await engine.shutdown()
            print("测试完成")
            
        except Exception as e:
            print(f"测试失败: {e}")
    
    # 运行测试
    if __name__ == "__main__":
        asyncio.run(test_qwen_api())