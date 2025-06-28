# ambivo_agents/agents/youtube_download.py
"""
YouTube Download Agent with pytubefix integration
Handles YouTube video and audio downloads using Docker containers
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
from ..executors.youtube_executor import YouTubeDockerExecutor


class YouTubeDownloadAgent(BaseAgent):
    """YouTube Download Agent for downloading videos and audio from YouTube"""

    def __init__(self, agent_id: str = None, memory_manager=None, llm_service=None, **kwargs):
        # Generate ID if not provided
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
            #logging.warning(f"Using default YouTube config due to: {e}")

        # ===
        # YouTube-specific initialization
        self._load_youtube_config()
        self._initialize_youtube_executor()
        self._add_youtube_tools()

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
            #logging.warning(f"Using default YouTube config due to: {e}")

    def _initialize_youtube_executor(self):
        """Initialize the YouTube executor"""
        try:
            from ..executors.youtube_executor import YouTubeDockerExecutor
            self.youtube_executor = YouTubeDockerExecutor(self.youtube_config)
            logging.info("YouTube executor initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize YouTube executor: {e}")
            raise RuntimeError(f"Failed to initialize YouTube executor: {e}")

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

    async def process_message(self, message: AgentMessage, context: ExecutionContext) -> AgentMessage:
        """Process incoming message and route to appropriate YouTube operations"""
        self.memory.store_message(message)

        try:
            content = message.content.lower()
            user_message = message.content

            # Extract YouTube URLs from message
            youtube_urls = self._extract_youtube_urls(user_message)

            if youtube_urls:
                # Determine if user wants audio or video
                audio_keywords = ['audio', 'mp3', 'music', 'sound', 'song']
                video_keywords = ['video', 'mp4', 'watch', 'visual']

                wants_audio = any(keyword in content for keyword in audio_keywords)
                wants_video = any(keyword in content for keyword in video_keywords)

                # Default to audio unless video is explicitly requested
                audio_only = not wants_video if wants_video else True

                if len(youtube_urls) == 1:
                    # Single URL download
                    response_content = await self._handle_single_download(youtube_urls[0], audio_only, user_message,
                                                                          context)
                else:
                    # Multiple URL download
                    response_content = await self._handle_batch_download(youtube_urls, audio_only, user_message,
                                                                         context)
            else:
                # No URLs found, provide help
                response_content = await self._handle_general_request(user_message, context)

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

    async def _handle_single_download(self, url: str, audio_only: bool, user_message: str,
                                      context: ExecutionContext) -> str:
        """Handle single YouTube URL download"""
        try:
            # Check if user wants info only
            if any(keyword in user_message.lower() for keyword in ['info', 'information', 'details', 'about']):
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

            # Proceed with download
            result = await self._download_youtube(url, audio_only=audio_only)

            if result['success']:
                file_size_mb = result.get('file_size_bytes', 0) / (1024 * 1024)
                return f"""✅ **YouTube Download Completed**

**🎯 Type:** {'Audio' if audio_only else 'Video'}
**🔗 URL:** {url}
**📁 File:** {result.get('filename', 'Unknown')}
**📍 Location:** {result.get('file_path', 'Unknown')}
**📊 Size:** {file_size_mb:.2f} MB
**⏱️ Download Time:** {result.get('execution_time', 0):.2f}s

Your {'audio' if audio_only else 'video'} has been successfully downloaded and is ready to use! 🎉"""
            else:
                return f"❌ **Download Failed:** {result['error']}"

        except Exception as e:
            return f"❌ **Error processing download:** {str(e)}"

    async def _handle_batch_download(self, urls: List[str], audio_only: bool, user_message: str,
                                     context: ExecutionContext) -> str:
        """Handle batch YouTube URL downloads"""
        try:
            result = await self._batch_download_youtube(urls, audio_only=audio_only)

            if result['success']:
                successful = result['successful']
                failed = result['failed']
                total = result['total_urls']

                response = f"""📦 **Batch YouTube Download Completed**

**📊 Summary:**
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
            return f"❌ **Error processing batch download:** {str(e)}"

    async def _handle_general_request(self, user_message: str, context: ExecutionContext) -> str:
        """Handle general YouTube download requests"""
        if self.llm_service:
            prompt = f"""
            You are a YouTube Download Agent specialized in downloading videos and audio from YouTube.

            Your capabilities include:
            - Downloading audio (MP3) from YouTube videos
            - Downloading videos (MP4) from YouTube
            - Getting video information without downloading
            - Batch downloading multiple URLs
            - Custom filename support

            User message: {user_message}

            Provide a helpful response about how you can assist with their YouTube download needs.
            """

            response = await self.llm_service.generate_response(prompt, context.metadata)
            return response
        else:
            return ("I'm your YouTube Download Agent! I can help you with:\n\n"
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
                    "**📝 Usage Examples:**\n"
                    "- 'Download audio from https://youtube.com/watch?v=example'\n"
                    "- 'Download video from https://youtube.com/watch?v=example'\n"
                    "- 'Get info about https://youtube.com/watch?v=example'\n"
                    "- 'Download https://youtube.com/watch?v=1 and https://youtube.com/watch?v=2'\n\n"
                    "Just paste any YouTube URL and I'll handle the download for you! 🚀")

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