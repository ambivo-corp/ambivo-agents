# ambivo_agents/agents/youtube_download.py
"""
YouTube Download Agent with pytubefix integration
Handles YouTube video and audio downloads using Docker containers
Updated with LLM-aware intent detection and conversation history integration.
"""

import asyncio
import json
import uuid
import time
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

from ..core.base import BaseAgent, AgentRole, AgentMessage, MessageType, ExecutionContext, AgentTool
from ..config.loader import load_config, get_config_section
from ..core.history import WebAgentHistoryMixin, ContextType
from ..executors.youtube_executor import YouTubeDockerExecutor


class YouTubeDownloadAgent(BaseAgent, WebAgentHistoryMixin):
    """YouTube Download Agent for downloading videos and audio from YouTube"""

    def __init__(self, agent_id: str = None, memory_manager=None, llm_service=None, **kwargs):
        if agent_id is None:
            agent_id = f"youtube_{str(uuid.uuid4())[:8]}"

        super().__init__(
            agent_id=agent_id,
            role=AgentRole.CODE_EXECUTOR,
            memory_manager=memory_manager,
            llm_service=llm_service,
            name="YouTube Download Agent",
            description="Agent for downloading videos and audio from YouTube using pytubefix",
            **kwargs
        )

        # Initialize history mixin
        self.setup_history_mixin()

        # Load YouTube configuration
        try:
            if hasattr(self, 'config') and self.config:
                self.youtube_config = self.config.get('youtube_download', {})
            else:
                config = load_config()
                self.youtube_config = config.get('youtube_download', {})
        except Exception as e:
            # Provide sensible defaults if config fails
            self.youtube_config = {
                'docker_image': 'sgosain/amb-ubuntu-python-public-pod',
                'download_dir': './youtube_downloads',
                'timeout': 600,
                'memory_limit': '1g',
                'default_audio_only': True
            }

        # YouTube-specific initialization
        self._load_youtube_config()
        self._initialize_youtube_executor()
        self._add_youtube_tools()

    async def _llm_analyze_youtube_intent(self, user_message: str, conversation_context: str = "") -> Dict[str, Any]:
        """Use LLM to analyze YouTube download intent"""
        if not self.llm_service:
            return self._keyword_based_youtube_analysis(user_message)

        prompt = f"""
        Analyze this user message in the context of YouTube operations and extract:
        1. Primary intent (download_audio, download_video, get_info, batch_download, help_request)
        2. YouTube URLs mentioned
        3. Output preferences (audio/video, format, quality)
        4. Context references (referring to previous YouTube operations)
        5. Custom filename preferences

        Conversation Context:
        {conversation_context}

        Current User Message: {user_message}

        Respond in JSON format:
        {{
            "primary_intent": "download_audio|download_video|get_info|batch_download|help_request",
            "youtube_urls": ["https://youtube.com/watch?v=example"],
            "output_preferences": {{
                "format_type": "audio|video",
                "format": "mp3|mp4|wav",
                "quality": "high|medium|low",
                "custom_filename": "filename or null"
            }},
            "uses_context_reference": true/false,
            "context_type": "previous_url|previous_download",
            "confidence": 0.0-1.0
        }}
        """

        try:
            response = await self.llm_service.generate_response(prompt)
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return self._extract_youtube_intent_from_llm_response(response, user_message)
        except Exception as e:
            return self._keyword_based_youtube_analysis(user_message)

    def _keyword_based_youtube_analysis(self, user_message: str) -> Dict[str, Any]:
        """Fallback keyword-based YouTube intent analysis"""
        content_lower = user_message.lower()

        # Determine intent
        if any(word in content_lower for word in ['info', 'information', 'details', 'about']):
            intent = 'get_info'
        elif any(word in content_lower for word in ['audio', 'mp3', 'music', 'sound']):
            intent = 'download_audio'
        elif any(word in content_lower for word in ['video', 'mp4', 'watch']):
            intent = 'download_video'
        elif any(word in content_lower for word in ['batch', 'multiple', 'several']):
            intent = 'batch_download'
        elif any(word in content_lower for word in ['download', 'get', 'fetch']):
            # Default to audio if no specific format mentioned
            intent = 'download_audio'
        else:
            intent = 'help_request'

        # Extract YouTube URLs
        youtube_urls = self._extract_youtube_urls(user_message)

        # Determine output preferences
        format_type = "video" if intent == 'download_video' else "audio"
        output_format = None
        if 'mp3' in content_lower:
            output_format = 'mp3'
        elif 'mp4' in content_lower:
            output_format = 'mp4'
        elif 'wav' in content_lower:
            output_format = 'wav'

        quality = 'medium'
        if 'high' in content_lower:
            quality = 'high'
        elif 'low' in content_lower:
            quality = 'low'

        return {
            "primary_intent": intent,
            "youtube_urls": youtube_urls,
            "output_preferences": {
                "format_type": format_type,
                "format": output_format,
                "quality": quality,
                "custom_filename": None
            },
            "uses_context_reference": any(word in content_lower for word in ['this', 'that', 'it']),
            "context_type": "previous_url",
            "confidence": 0.7
        }

    async def process_message(self, message: AgentMessage, context: ExecutionContext = None) -> AgentMessage:
        """Process message with LLM-based YouTube intent detection and history context"""
        self.memory.store_message(message)

        try:
            user_message = message.content

            # Update conversation state
            self.update_conversation_state(user_message)

            # Get conversation context for LLM analysis
            conversation_context = self._get_youtube_conversation_context_summary()

            # Use LLM to analyze intent
            intent_analysis = await self._llm_analyze_youtube_intent(user_message, conversation_context)

            # Route request based on LLM analysis
            response_content = await self._route_youtube_with_llm_analysis(intent_analysis, user_message, context)

            response = self.create_response(
                content=response_content,
                recipient_id=message.sender_id,
                session_id=message.session_id,
                conversation_id=message.conversation_id
            )

            self.memory.store_message(response)
            return response

        except Exception as e:
            error_response = self.create_response(
                content=f"YouTube Download Agent error: {str(e)}",
                recipient_id=message.sender_id,
                message_type=MessageType.ERROR,
                session_id=message.session_id,
                conversation_id=message.conversation_id
            )
            return error_response

    def _get_youtube_conversation_context_summary(self) -> str:
        """Get YouTube conversation context summary"""
        try:
            recent_history = self.get_conversation_history_with_context(
                limit=3,
                context_types=[ContextType.URL]
            )

            context_summary = []
            for msg in recent_history:
                if msg.get('message_type') == 'user_input':
                    extracted_context = msg.get('extracted_context', {})
                    urls = extracted_context.get('url', [])

                    youtube_urls = [url for url in urls if self._is_valid_youtube_url(url)]
                    if youtube_urls:
                        context_summary.append(f"Previous YouTube URL: {youtube_urls[0]}")

            return "\n".join(context_summary) if context_summary else "No previous YouTube context"
        except:
            return "No previous YouTube context"

    async def _route_youtube_with_llm_analysis(self, intent_analysis: Dict[str, Any], user_message: str,
                                              context: ExecutionContext) -> str:
        """Route YouTube request based on LLM intent analysis"""

        primary_intent = intent_analysis.get("primary_intent", "help_request")
        youtube_urls = intent_analysis.get("youtube_urls", [])
        output_prefs = intent_analysis.get("output_preferences", {})
        uses_context = intent_analysis.get("uses_context_reference", False)

        # Resolve context references if needed
        if uses_context and not youtube_urls:
            recent_url = self._get_recent_youtube_url_from_history(context)
            if recent_url:
                youtube_urls = [recent_url]

        # Route based on intent
        if primary_intent == "help_request":
            return await self._handle_youtube_help_request(user_message)
        elif primary_intent == "download_audio":
            return await self._handle_audio_download(youtube_urls, output_prefs, user_message)
        elif primary_intent == "download_video":
            return await self._handle_video_download(youtube_urls, output_prefs, user_message)
        elif primary_intent == "get_info":
            return await self._handle_video_info(youtube_urls, user_message)
        elif primary_intent == "batch_download":
            return await self._handle_batch_download(youtube_urls, output_prefs, user_message)
        else:
            return await self._handle_youtube_help_request(user_message)

    async def _handle_audio_download(self, youtube_urls: List[str], output_prefs: Dict[str, Any], user_message: str) -> str:
        """Handle audio download requests"""
        if not youtube_urls:
            recent_url = self._get_recent_youtube_url_from_history(None)
            if recent_url:
                return f"I can download audio from YouTube videos. Did you mean to download audio from **{recent_url}**? Please confirm."
            else:
                return "I can download audio from YouTube videos. Please provide a YouTube URL.\n\n" \
                       "Example: 'Download audio from https://youtube.com/watch?v=example'"

        url = youtube_urls[0]
        output_format = output_prefs.get("format", "mp3")
        quality = output_prefs.get("quality", "medium")
        custom_filename = output_prefs.get("custom_filename")

        try:
            result = await self._download_youtube_audio(url, custom_filename)

            if result['success']:
                file_size_mb = result.get('file_size_bytes', 0) / (1024 * 1024)
                return f"""✅ **YouTube Audio Download Completed**

🎵 **Type:** Audio (MP3)
🔗 **URL:** {url}
📁 **File:** {result.get('filename', 'Unknown')}
📍 **Location:** {result.get('file_path', 'Unknown')}
📊 **Size:** {file_size_mb:.2f} MB
⏱️ **Download Time:** {result.get('execution_time', 0):.2f}s

Your audio file has been successfully downloaded and is ready to use! 🎉"""
            else:
                return f"❌ **Audio download failed:** {result['error']}"

        except Exception as e:
            return f"❌ **Error during audio download:** {str(e)}"

    async def _handle_video_download(self, youtube_urls: List[str], output_prefs: Dict[str, Any], user_message: str) -> str:
        """Handle video download requests"""
        if not youtube_urls:
            recent_url = self._get_recent_youtube_url_from_history(None)
            if recent_url:
                return f"I can download videos from YouTube. Did you mean to download the video from **{recent_url}**? Please confirm."
            else:
                return "I can download videos from YouTube. Please provide a YouTube URL.\n\n" \
                       "Example: 'Download video from https://youtube.com/watch?v=example'"

        url = youtube_urls[0]
        custom_filename = output_prefs.get("custom_filename")

        try:
            result = await self._download_youtube_video(url, custom_filename)

            if result['success']:
                file_size_mb = result.get('file_size_bytes', 0) / (1024 * 1024)
                return f"""✅ **YouTube Video Download Completed**

🎬 **Type:** Video (MP4)
🔗 **URL:** {url}
📁 **File:** {result.get('filename', 'Unknown')}
📍 **Location:** {result.get('file_path', 'Unknown')}
📊 **Size:** {file_size_mb:.2f} MB
⏱️ **Download Time:** {result.get('execution_time', 0):.2f}s

Your video file has been successfully downloaded and is ready to use! 🎉"""
            else:
                return f"❌ **Video download failed:** {result['error']}"

        except Exception as e:
            return f"❌ **Error during video download:** {str(e)}"

    async def _handle_video_info(self, youtube_urls: List[str], user_message: str) -> str:
        """Handle video info requests"""
        if not youtube_urls:
            recent_url = self._get_recent_youtube_url_from_history(None)
            if recent_url:
                return f"I can get information about YouTube videos. Did you mean to get info for **{recent_url}**? Please confirm."
            else:
                return "I can get information about YouTube videos. Please provide a YouTube URL.\n\n" \
                       "Example: 'Get info about https://youtube.com/watch?v=example'"

        url = youtube_urls[0]

        try:
            result = await self._get_youtube_info(url)

            if result['success']:
                video_info = result['video_info']
                return f"""📹 **YouTube Video Information**

**🎬 Title:** {video_info.get('title', 'Unknown')}
**👤 Author:** {video_info.get('author', 'Unknown')}
**⏱️ Duration:** {self._format_duration(video_info.get('duration', 0))}
**👀 Views:** {video_info.get('views', 0):,}
**🔗 URL:** {url}

**📊 Available Streams:**
- Audio streams: {video_info.get('available_streams', {}).get('audio_streams', 0)}
- Video streams: {video_info.get('available_streams', {}).get('video_streams', 0)}
- Highest resolution: {video_info.get('available_streams', {}).get('highest_resolution', 'Unknown')}

Would you like me to download this video?"""
            else:
                return f"❌ **Error getting video info:** {result['error']}"

        except Exception as e:
            return f"❌ **Error getting video info:** {str(e)}"

    async def _handle_batch_download(self, youtube_urls: List[str], output_prefs: Dict[str, Any], user_message: str) -> str:
        """Handle batch download requests"""
        if not youtube_urls:
            return "I can download multiple YouTube videos at once. Please provide YouTube URLs.\n\n" \
                   "Example: 'Download https://youtube.com/watch?v=1 and https://youtube.com/watch?v=2'"

        format_type = output_prefs.get("format_type", "audio")
        audio_only = format_type == "audio"

        try:
            result = await self._batch_download_youtube(youtube_urls, audio_only)

            if result['success']:
                successful = result['successful']
                failed = result['failed']
                total = result['total_urls']

                response = f"""📦 **Batch YouTube Download Completed**

📊 **Summary:**
- **Total URLs:** {total}
- **Successful:** {successful}
- **Failed:** {failed}
- **Type:** {'Audio' if audio_only else 'Video'}

"""

                if successful > 0:
                    response += "✅ **Successfully Downloaded:**\n"
                    for i, download_result in enumerate(result['results'], 1):
                        if download_result.get('success', False):
                            response += f"{i}. {download_result.get('filename', 'Unknown')}\n"

                if failed > 0:
                    response += f"\n❌ **Failed Downloads:** {failed}\n"
                    for i, download_result in enumerate(result['results'], 1):
                        if not download_result.get('success', False):
                            response += f"{i}. {download_result.get('url', 'Unknown')}: {download_result.get('error', 'Unknown error')}\n"

                response += f"\n🎉 Batch download completed with {successful}/{total} successful downloads!"
                return response
            else:
                return f"❌ **Batch download failed:** {result['error']}"

        except Exception as e:
            return f"❌ **Error during batch download:** {str(e)}"

    async def _handle_youtube_help_request(self, user_message: str) -> str:
        """Handle YouTube help requests with conversation context"""
        state = self.get_conversation_state()

        response = ("I'm your YouTube Download Agent! I can help you with:\n\n"
                    "🎵 **Audio Downloads**\n"
                    "- Download MP3 audio from YouTube videos\n"
                    "- High-quality audio extraction\n"
                    "- Custom filename support\n\n"
                    "🎥 **Video Downloads**\n"
                    "- Download MP4 videos in highest available quality\n"
                    "- Progressive download format\n"
                    "- Full video with audio\n\n"
                    "📊 **Video Information**\n"
                    "- Get video details without downloading\n"
                    "- Check duration, views, and available streams\n"
                    "- Thumbnail and metadata extraction\n\n"
                    "📦 **Batch Operations**\n"
                    "- Download multiple videos at once\n"
                    "- Bulk audio/video processing\n\n"
                    "🧠 **Smart Context Features**\n"
                    "- Remembers YouTube URLs from conversation\n"
                    "- Understands 'that video' and 'this URL'\n"
                    "- Maintains working context\n\n")

        # Add current context information
        if state.current_resource and self._is_valid_youtube_url(state.current_resource):
            response += f"🎯 **Current Video:** {state.current_resource}\n"

        response += "\n💡 **Examples:**\n"
        response += "• 'Download audio from https://youtube.com/watch?v=example'\n"
        response += "• 'Download video from https://youtube.com/watch?v=example'\n"
        response += "• 'Get info about https://youtube.com/watch?v=example'\n"
        response += "• 'Download that video as audio'\n"
        response += "\nI understand context from our conversation! 🚀"

        return response

    def _extract_youtube_intent_from_llm_response(self, llm_response: str, user_message: str) -> Dict[str, Any]:
        """Extract YouTube intent from non-JSON LLM response"""
        content_lower = llm_response.lower()

        if 'audio' in content_lower or 'mp3' in content_lower:
            intent = 'download_audio'
        elif 'video' in content_lower or 'mp4' in content_lower:
            intent = 'download_video'
        elif 'info' in content_lower or 'information' in content_lower:
            intent = 'get_info'
        elif 'batch' in content_lower or 'multiple' in content_lower:
            intent = 'batch_download'
        else:
            intent = 'help_request'

        return {
            "primary_intent": intent,
            "youtube_urls": [],
            "output_preferences": {"format_type": "audio", "format": None, "quality": "medium"},
            "uses_context_reference": False,
            "context_type": "none",
            "confidence": 0.6
        }

    def _add_youtube_tools(self):
        """Add all YouTube download tools"""

        # Download video/audio tool
        self.add_tool(AgentTool(
            name="download_youtube",
            description="Download video or audio from YouTube URL",
            function=self._download_youtube,
            parameters_schema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "YouTube URL to download"},
                    "audio_only": {"type": "boolean", "default": True, "description": "Download only audio if True"},
                    "custom_filename": {"type": "string", "description": "Custom filename (optional)"}
                },
                "required": ["url"]
            }
        ))

        # Get video information tool
        self.add_tool(AgentTool(
            name="get_youtube_info",
            description="Get information about a YouTube video without downloading",
            function=self._get_youtube_info,
            parameters_schema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "YouTube URL to get information about"}
                },
                "required": ["url"]
            }
        ))

        # Download audio specifically
        self.add_tool(AgentTool(
            name="download_youtube_audio",
            description="Download audio only from YouTube URL",
            function=self._download_youtube_audio,
            parameters_schema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "YouTube URL to download audio from"},
                    "custom_filename": {"type": "string", "description": "Custom filename (optional)"}
                },
                "required": ["url"]
            }
        ))

        # Download video specifically
        self.add_tool(AgentTool(
            name="download_youtube_video",
            description="Download video from YouTube URL",
            function=self._download_youtube_video,
            parameters_schema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "YouTube URL to download video from"},
                    "custom_filename": {"type": "string", "description": "Custom filename (optional)"}
                },
                "required": ["url"]
            }
        ))

        # Batch download tool
        self.add_tool(AgentTool(
            name="batch_download_youtube",
            description="Download multiple YouTube videos/audio",
            function=self._batch_download_youtube,
            parameters_schema={
                "type": "object",
                "properties": {
                    "urls": {"type": "array", "items": {"type": "string"}, "description": "List of YouTube URLs"},
                    "audio_only": {"type": "boolean", "default": True, "description": "Download only audio if True"}
                },
                "required": ["urls"]
            }
        ))

    def _load_youtube_config(self):
        """Load YouTube configuration with fallbacks"""
        try:
            if hasattr(self, 'config') and self.config:
                self.youtube_config = self.config.get('youtube_download', {})
                logging.info("Loaded YouTube config from agent config")
            else:
                config = load_config()
                self.youtube_config = config.get('youtube_download', {})
                logging.info("Loaded YouTube config from file")
        except Exception as e:
            # Provide sensible defaults if config fails
            self.youtube_config = {
                'docker_image': 'sgosain/amb-ubuntu-python-public-pod',
                'download_dir': './youtube_downloads',
                'timeout': 600,
                'memory_limit': '1g',
                'default_audio_only': True
            }

    def _initialize_youtube_executor(self):
        """Initialize the YouTube executor"""
        try:
            from ..executors.youtube_executor import YouTubeDockerExecutor
            self.youtube_executor = YouTubeDockerExecutor(self.youtube_config)
            logging.info("YouTube executor initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize YouTube executor: {e}")
            raise RuntimeError(f"Failed to initialize YouTube executor: {e}")

    async def _download_youtube(self, url: str, audio_only: bool = True, custom_filename: str = None) -> Dict[str, Any]:
        """Download video or audio from YouTube"""
        try:
            if not self._is_valid_youtube_url(url):
                return {"success": False, "error": f"Invalid YouTube URL: {url}"}

            result = self.youtube_executor.download_youtube_video(
                url=url,
                audio_only=audio_only,
                output_filename=custom_filename
            )

            if result['success']:
                download_info = result.get('download_info', {})
                return {
                    "success": True,
                    "message": f"Successfully downloaded {'audio' if audio_only else 'video'} from YouTube",
                    "url": url,
                    "audio_only": audio_only,
                    "file_path": download_info.get('final_path'),
                    "filename": download_info.get('filename'),
                    "file_size_bytes": download_info.get('size_bytes', 0),
                    "execution_time": result['execution_time'],
                    "custom_filename": custom_filename
                }
            else:
                return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _download_youtube_audio(self, url: str, custom_filename: str = None) -> Dict[str, Any]:
        """Download audio only from YouTube"""
        return await self._download_youtube(url, audio_only=True, custom_filename=custom_filename)

    async def _download_youtube_video(self, url: str, custom_filename: str = None) -> Dict[str, Any]:
        """Download video from YouTube"""
        return await self._download_youtube(url, audio_only=False, custom_filename=custom_filename)

    async def _get_youtube_info(self, url: str) -> Dict[str, Any]:
        """Get YouTube video information"""
        try:
            if not self._is_valid_youtube_url(url):
                return {"success": False, "error": f"Invalid YouTube URL: {url}"}

            result = self.youtube_executor.get_video_info(url)

            if result['success']:
                return {
                    "success": True,
                    "message": "Successfully retrieved video information",
                    "url": url,
                    "video_info": result['video_info']
                }
            else:
                return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _batch_download_youtube(self, urls: List[str], audio_only: bool = True) -> Dict[str, Any]:
        """Download multiple YouTube videos/audio"""
        try:
            results = []
            successful = 0
            failed = 0

            for i, url in enumerate(urls):
                try:
                    result = await self._download_youtube(url, audio_only=audio_only)
                    results.append(result)

                    if result.get('success', False):
                        successful += 1
                    else:
                        failed += 1

                    # Add delay between downloads to be respectful
                    if i < len(urls) - 1:
                        await asyncio.sleep(2)

                except Exception as e:
                    results.append({
                        "success": False,
                        "url": url,
                        "error": str(e)
                    })
                    failed += 1

            return {
                "success": True,
                "message": f"Batch download completed: {successful} successful, {failed} failed",
                "total_urls": len(urls),
                "successful": successful,
                "failed": failed,
                "audio_only": audio_only,
                "results": results
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _is_valid_youtube_url(self, url: str) -> bool:
        """Check if URL is a valid YouTube URL"""
        youtube_patterns = [
            r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/',
            r'(https?://)?(www\.)?youtu\.be/',
            r'(https?://)?(www\.)?youtube\.com/watch\?v=',
            r'(https?://)?(www\.)?youtube\.com/embed/',
            r'(https?://)?(www\.)?youtube\.com/v/',
        ]

        return any(re.match(pattern, url, re.IGNORECASE) for pattern in youtube_patterns)

    def _extract_youtube_urls(self, text: str) -> List[str]:
        """Extract YouTube URLs from text"""
        youtube_patterns = [
            r'https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+',
            r'https?://(?:www\.)?youtu\.be/[\w-]+',
            r'https?://(?:www\.)?youtube\.com/embed/[\w-]+',
            r'https?://(?:www\.)?youtube\.com/v/[\w-]+',
        ]

        urls = []
        for pattern in youtube_patterns:
            urls.extend(re.findall(pattern, text, re.IGNORECASE))

        return list(set(urls))  # Remove duplicates

    def _get_recent_youtube_url_from_history(self, context):
        """Get most recent YouTube URL from conversation history"""
        try:
            history = self.memory.get_recent_messages(limit=5, conversation_id=context.conversation_id if context else None)
            for msg in reversed(history):
                if isinstance(msg, dict):
                    content = msg.get('content', '')
                    urls = self._extract_youtube_urls(content)
                    if urls:
                        return urls[0]
        except:
            pass
        return None

    def _format_duration(self, seconds: int) -> str:
        """Format duration in seconds to readable format"""
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            remaining_seconds = seconds % 60
            return f"{minutes}m {remaining_seconds}s"
        else:
            hours = seconds // 3600
            remaining_minutes = (seconds % 3600) // 60
            remaining_seconds = seconds % 60
            return f"{hours}h {remaining_minutes}m {remaining_seconds}s"

    @classmethod
    def create_simple(cls, agent_id: str = None, **kwargs):
        """
        Create agent with auto-configuration (recommended for most users)

        Args:
            agent_id: Optional agent ID. If None, auto-generates one.
            **kwargs: Additional arguments passed to constructor

        Returns:
            YouTubeDownloadAgent: Configured agent ready to use
        """
        # Auto-generate ID if not provided
        if agent_id is None:
            agent_id = f"youtube_{str(uuid.uuid4())[:8]}"

        # Create with auto-configuration enabled
        return cls(
            agent_id=agent_id,
            auto_configure=True,  # Enable auto-configuration
            **kwargs
        )

    @classmethod
    def create_advanced(cls,
                        agent_id: str,
                        memory_manager,
                        llm_service=None,
                        config: Dict[str, Any] = None,
                        **kwargs):
        """
        Create agent with explicit dependencies (for advanced use cases)

        Args:
            agent_id: Agent identifier
            memory_manager: Pre-configured memory manager
            llm_service: Optional pre-configured LLM service
            config: Optional configuration dictionary
            **kwargs: Additional arguments passed to constructor

        Returns:
            YouTubeDownloadAgent: Agent with explicit dependencies
        """
        return cls(
            agent_id=agent_id,
            memory_manager=memory_manager,
            llm_service=llm_service,
            config=config,
            auto_configure=False,  # Disable auto-config when using advanced mode
            **kwargs
        )