# ambivo_agents/agents/media_editor.py
"""
Media Editor Agent with FFmpeg Integration
Handles audio/video processing using Docker containers with ffmpeg
Updated with LLM-aware intent detection and conversation history integration.
"""

import asyncio
import json
import os
import shutil
import tempfile
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional, Union

from ..config.loader import get_config_section, load_config
from ..core.base import (
    AgentMessage,
    AgentRole,
    AgentTool,
    BaseAgent,
    ExecutionContext,
    MessageType,
    StreamChunk,
    StreamSubType,
)
from ..core.history import ContextType, MediaAgentHistoryMixin
from ..executors.media_executor import MediaDockerExecutor


class MediaEditorAgent(BaseAgent, MediaAgentHistoryMixin):
    """LLM-Aware Media Editor Agent with conversation context and intelligent routing"""

    def __init__(
        self,
        agent_id: str = None,
        memory_manager=None,
        llm_service=None,
        system_message: str = None,
        **kwargs,
    ):
        if agent_id is None:
            agent_id = f"media_editor_{str(uuid.uuid4())[:8]}"

        default_system = """You are a specialized media processing agent with the following capabilities:
            - Process video and audio files using FFmpeg in secure Docker containers
            - Extract audio from videos, convert formats, resize videos, create thumbnails
            - Remember file references from previous conversations naturally
            - Understand context like "that video" or "the file we just processed"
            - Provide clear progress updates and detailed processing results
            - Handle technical specifications like codecs, quality settings, and dimensions"""

        super().__init__(
            agent_id=agent_id,
            role=AgentRole.CODE_EXECUTOR,
            memory_manager=memory_manager,
            llm_service=llm_service,
            name="Media Editor Agent",
            description="LLM-aware media processing agent with conversation history",
            system_message=system_message or default_system,
            **kwargs,
        )

        # Initialize history mixin
        self.setup_history_mixin()

        # Load media configuration and initialize executor
        self._load_media_config()
        self._initialize_media_executor()
        self._add_media_tools()

        # Load configuration and initialize

    def _load_media_config(self):
        """Load media configuration"""
        try:
            config = load_config()
            self.media_config = get_config_section("media_editor", config)
        except Exception as e:
            self.media_config = {
                "docker_image": "sgosain/amb-ubuntu-python-public-pod",
                "timeout": 300,
                "input_dir": "./examples/media_input",
                "output_dir": "./examples/media_output",
            }

    async def _llm_analyze_media_intent(
        self, user_message: str, conversation_context: str = ""
    ) -> Dict[str, Any]:
        """Use LLM to analyze media processing intent"""
        if not self.llm_service:
            return self._keyword_based_media_analysis(user_message)

        prompt = f"""
        Analyze this user message in the context of media processing and extract:
        1. Primary intent (extract_audio, convert_video, resize_video, trim_media, create_thumbnail, get_info, help_request)
        2. Media file references (file paths, video/audio files)
        3. Output preferences (format, quality, dimensions, timing)
        4. Context references (referring to previous media operations)
        5. Technical specifications (codecs, bitrates, resolution, etc.)

        Conversation Context:
        {conversation_context}

        Current User Message: {user_message}

        Respond in JSON format:
        {{
            "primary_intent": "extract_audio|convert_video|resize_video|trim_media|create_thumbnail|get_info|help_request",
            "media_files": ["file1.mp4", "video2.avi"],
            "output_preferences": {{
                "format": "mp4|avi|mp3|wav|etc",
                "quality": "high|medium|low",
                "dimensions": "1920x1080|720p|1080p|4k",
                "timing": {{"start": "00:01:30", "duration": "30s"}},
                "codec": "h264|h265|aac|mp3"
            }},
            "uses_context_reference": true/false,
            "context_type": "previous_file|previous_operation",
            "technical_specs": {{
                "video_codec": "codec_name",
                "audio_codec": "codec_name", 
                "bitrate": "value",
                "fps": "value"
            }},
            "confidence": 0.0-1.0
        }}
        """

        try:
            response = await self.llm_service.generate_response(prompt)
            import re

            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return self._extract_media_intent_from_llm_response(response, user_message)
        except Exception as e:
            return self._keyword_based_media_analysis(user_message)

    def _keyword_based_media_analysis(self, user_message: str) -> Dict[str, Any]:
        """Fallback keyword-based media intent analysis"""
        content_lower = user_message.lower()

        # Determine intent
        if any(word in content_lower for word in ["extract audio", "get audio", "audio from"]):
            intent = "extract_audio"
        elif any(word in content_lower for word in ["convert", "change format", "transform"]):
            intent = "convert_video"
        elif any(word in content_lower for word in ["resize", "scale", "dimensions"]):
            intent = "resize_video"
        elif any(word in content_lower for word in ["trim", "cut", "clip"]):
            intent = "trim_media"
        elif any(word in content_lower for word in ["thumbnail", "screenshot", "frame"]):
            intent = "create_thumbnail"
        elif any(
            word in content_lower for word in ["info", "information", "details", "properties"]
        ):
            intent = "get_info"
        else:
            intent = "help_request"

        # Extract media files
        media_files = self.extract_context_from_text(user_message, ContextType.MEDIA_FILE)
        file_paths = self.extract_context_from_text(user_message, ContextType.FILE_PATH)
        all_files = media_files + file_paths

        # Extract output preferences
        output_format = None
        if "mp4" in content_lower:
            output_format = "mp4"
        elif "mp3" in content_lower:
            output_format = "mp3"
        elif "wav" in content_lower:
            output_format = "wav"

        quality = "medium"
        if "high" in content_lower:
            quality = "high"
        elif "low" in content_lower:
            quality = "low"

        return {
            "primary_intent": intent,
            "media_files": all_files,
            "output_preferences": {
                "format": output_format,
                "quality": quality,
                "dimensions": None,
                "timing": {},
                "codec": None,
            },
            "uses_context_reference": any(word in content_lower for word in ["this", "that", "it"]),
            "context_type": "previous_file",
            "technical_specs": {},
            "confidence": 0.7,
        }

    async def process_message(
        self, message: AgentMessage, context: ExecutionContext = None
    ) -> AgentMessage:
        """Process message with LLM-based media intent detection - FIXED: Context preserved across provider switches"""
        self.memory.store_message(message)

        try:
            user_message = message.content

            # Update conversation state
            self.update_conversation_state(user_message)

            llm_context_from_routing = message.metadata.get("llm_context", {})
            conversation_history_from_routing = llm_context_from_routing.get(
                "conversation_history", []
            )

            if conversation_history_from_routing:
                conversation_history = conversation_history_from_routing
            else:
                conversation_history = await self.get_conversation_history(
                    limit=5, include_metadata=True
                )

            conversation_context = self._get_media_conversation_context_summary()

            # Build LLM context with conversation history
            llm_context = {
                "conversation_history": conversation_history,
                "conversation_id": message.conversation_id,
                "user_id": message.sender_id,
                "agent_type": "media_editor",
            }

            # Use LLM to analyze intent WITH CONTEXT
            intent_analysis = await self._llm_analyze_media_intent_with_context(
                user_message, conversation_context, llm_context
            )

            # Route request based on LLM analysis with context
            response_content = await self._route_media_with_llm_analysis_with_context(
                intent_analysis, user_message, context, llm_context
            )

            response = self.create_response(
                content=response_content,
                recipient_id=message.sender_id,
                session_id=message.session_id,
                conversation_id=message.conversation_id,
            )

            self.memory.store_message(response)
            return response

        except Exception as e:
            error_response = self.create_response(
                content=f"Media Editor Agent error: {str(e)}",
                recipient_id=message.sender_id,
                message_type=MessageType.ERROR,
                session_id=message.session_id,
                conversation_id=message.conversation_id,
            )
            return error_response

    async def _llm_analyze_media_intent_with_context(
        self, user_message: str, conversation_context: str = "", llm_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Use LLM to analyze media processing intent - FIXED: With conversation context"""
        if not self.llm_service:
            return self._keyword_based_media_analysis(user_message)

        prompt = f"""
        Analyze this user message in the context of media processing and extract:
        1. Primary intent (extract_audio, convert_video, resize_video, trim_media, create_thumbnail, get_info, help_request)
        2. Media file references (file paths, video/audio files)
        3. Output preferences (format, quality, dimensions, timing)
        4. Context references (referring to previous media operations)
        5. Technical specifications (codecs, bitrates, resolution, etc.)

        Conversation Context:
        {conversation_context}

        Current User Message: {user_message}

        Respond in JSON format:
        {{
            "primary_intent": "extract_audio|convert_video|resize_video|trim_media|create_thumbnail|get_info|help_request",
            "media_files": ["file1.mp4", "video2.avi"],
            "output_preferences": {{
                "format": "mp4|avi|mp3|wav|etc",
                "quality": "high|medium|low",
                "dimensions": "1920x1080|720p|1080p|4k",
                "timing": {{"start": "00:01:30", "duration": "30s"}},
                "codec": "h264|h265|aac|mp3"
            }},
            "uses_context_reference": true/false,
            "context_type": "previous_file|previous_operation",
            "technical_specs": {{
                "video_codec": "codec_name",
                "audio_codec": "codec_name", 
                "bitrate": "value",
                "fps": "value"
            }},
            "confidence": 0.0-1.0
        }}
        """

        enhanced_system_message = self.get_system_message_for_llm(llm_context)
        try:
            # Pass conversation history through context
            response = await self.llm_service.generate_response(
                prompt=prompt, context=llm_context, system_message=enhanced_system_message
            )

            import re

            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return self._extract_media_intent_from_llm_response(response, user_message)
        except Exception as e:
            print(f"LLM media intent analysis failed: {e}")
            return self._keyword_based_media_analysis(user_message)

    async def _route_media_with_llm_analysis_with_context(
        self,
        intent_analysis: Dict[str, Any],
        user_message: str,
        context: ExecutionContext,
        llm_context: Dict[str, Any],
    ) -> str:
        """Route media request based on LLM intent analysis - FIXED: With context preservation"""

        primary_intent = intent_analysis.get("primary_intent", "help_request")
        media_files = intent_analysis.get("media_files", [])
        output_prefs = intent_analysis.get("output_preferences", {})
        uses_context = intent_analysis.get("uses_context_reference", False)

        # Resolve context references if needed
        if uses_context and not media_files:
            recent_file = self.get_recent_media_file()
            if recent_file:
                media_files = [recent_file]

        # Route based on intent (existing routing logic but with context)
        if primary_intent == "help_request":
            return await self._handle_media_help_request_with_context(user_message, llm_context)
        elif primary_intent == "extract_audio":
            return await self._handle_audio_extraction(media_files, output_prefs, user_message)
        elif primary_intent == "convert_video":
            return await self._handle_video_conversion(media_files, output_prefs, user_message)
        elif primary_intent == "resize_video":
            return await self._handle_video_resize(media_files, output_prefs, user_message)
        elif primary_intent == "trim_media":
            return await self._handle_media_trim(media_files, output_prefs, user_message)
        elif primary_intent == "create_thumbnail":
            return await self._handle_thumbnail_creation(media_files, output_prefs, user_message)
        elif primary_intent == "get_info":
            return await self._handle_media_info(media_files, user_message)
        else:
            return await self._handle_media_help_request_with_context(user_message, llm_context)

    async def _handle_media_help_request_with_context(
        self, user_message: str, llm_context: Dict[str, Any]
    ) -> str:
        """Handle media help requests with conversation context - FIXED: Context preserved"""

        # Use LLM for more intelligent help if available
        if self.llm_service and llm_context.get("conversation_history"):
            enhanced_system_message = self.get_system_message_for_llm(llm_context)
            help_prompt = f"""As a media processing assistant, provide helpful guidance for: {user_message}

    Consider the user's previous media operations and provide contextual assistance."""

            try:
                # Use LLM with conversation context
                intelligent_help = await self.llm_service.generate_response(
                    prompt=help_prompt, context=llm_context, system_message=enhanced_system_message
                )
                return intelligent_help
            except Exception as e:
                print(f"LLM help generation failed: {e}")

        # Fallback to standard help message
        state = self.get_conversation_state()

        response = (
            "I'm your Media Editor Agent! I can help you with:\n\n"
            "🎥 **Video Processing**\n"
            "- Extract audio from videos\n"
            "- Convert between formats (MP4, AVI, MOV, MKV)\n"
            "- Resize and scale videos\n"
            "- Create thumbnails and frames\n"
            "- Trim and cut clips\n\n"
            "🎵 **Audio Processing**\n"
            "- Convert audio formats (MP3, WAV, AAC, FLAC)\n"
            "- Extract from videos\n"
            "- Adjust quality settings\n\n"
            "🧠 **Smart Context Features**\n"
            "- Remembers files from previous messages\n"
            "- Understands 'that video' and 'this file'\n"
            "- Maintains working context\n\n"
        )

        # Add current context information
        if state.current_resource:
            response += f"🎯 **Current File:** {state.current_resource}\n"

        if state.working_files:
            response += f"📁 **Working Files:** {len(state.working_files)} files\n"
            for file in state.working_files[-3:]:  # Show last 3
                response += f"   • {file}\n"

        response += "\n💡 **Examples:**\n"
        response += "• 'Extract audio from video.mp4 as MP3'\n"
        response += "• 'Convert that video to MP4'\n"
        response += "• 'Resize it to 720p'\n"
        response += "• 'Create a thumbnail at 2 minutes'\n"
        response += "\nI understand context from our conversation! 🚀"

        return response

    def _get_media_conversation_context_summary(self) -> str:
        """Get media conversation context summary"""
        try:
            recent_history = self.get_conversation_history_with_context(
                limit=3, context_types=[ContextType.MEDIA_FILE, ContextType.FILE_PATH]
            )

            context_summary = []
            for msg in recent_history:
                if msg.get("message_type") == "user_input":
                    extracted_context = msg.get("extracted_context", {})
                    media_files = extracted_context.get("media_file", [])
                    file_paths = extracted_context.get("file_path", [])

                    if media_files:
                        context_summary.append(f"Previous media file: {media_files[0]}")
                    elif file_paths:
                        context_summary.append(f"Previous file: {file_paths[0]}")

            return "\n".join(context_summary) if context_summary else "No previous media context"
        except:
            return "No previous media context"

    async def _route_media_with_llm_analysis(
        self, intent_analysis: Dict[str, Any], user_message: str, context: ExecutionContext
    ) -> str:
        """Route media request based on LLM intent analysis"""

        primary_intent = intent_analysis.get("primary_intent", "help_request")
        media_files = intent_analysis.get("media_files", [])
        output_prefs = intent_analysis.get("output_preferences", {})
        uses_context = intent_analysis.get("uses_context_reference", False)

        # Resolve context references if needed
        if uses_context and not media_files:
            recent_file = self.get_recent_media_file()
            if recent_file:
                media_files = [recent_file]

        # Route based on intent
        if primary_intent == "help_request":
            return await self._handle_media_help_request(user_message)
        elif primary_intent == "extract_audio":
            return await self._handle_audio_extraction(media_files, output_prefs, user_message)
        elif primary_intent == "convert_video":
            return await self._handle_video_conversion(media_files, output_prefs, user_message)
        elif primary_intent == "resize_video":
            return await self._handle_video_resize(media_files, output_prefs, user_message)
        elif primary_intent == "trim_media":
            return await self._handle_media_trim(media_files, output_prefs, user_message)
        elif primary_intent == "create_thumbnail":
            return await self._handle_thumbnail_creation(media_files, output_prefs, user_message)
        elif primary_intent == "get_info":
            return await self._handle_media_info(media_files, user_message)
        else:
            return await self._handle_media_help_request(user_message)

    async def _handle_audio_extraction(
        self, media_files: List[str], output_prefs: Dict[str, Any], user_message: str
    ) -> str:
        """Handle audio extraction with LLM analysis"""

        if not media_files:
            recent_file = self.get_recent_media_file()
            if recent_file:
                return f"I can extract audio from media files. Did you mean to extract audio from **{recent_file}**? Please confirm."
            else:
                return (
                    "I can extract audio from video files. Please provide the video file path.\n\n"
                    "Example: 'Extract audio from video.mp4 as high quality mp3'"
                )

        input_file = media_files[0]
        output_format = output_prefs.get("format", "mp3")
        quality = output_prefs.get("quality", "medium")

        try:
            result = await self._extract_audio_from_video(input_file, output_format, quality)

            if result["success"]:
                return (
                    f"✅ **Audio Extraction Completed**\n\n"
                    f"📁 **Input:** {input_file}\n"
                    f"🎵 **Output:** {result.get('output_file', 'Unknown')}\n"
                    f"📊 **Format:** {output_format.upper()}\n"
                    f"🎚️ **Quality:** {quality}\n"
                    f"⏱️ **Time:** {result.get('execution_time', 0):.2f}s\n\n"
                    f"Your audio file is ready! 🎉"
                )
            else:
                return f"❌ **Audio extraction failed:** {result.get('error', 'Unknown error')}"

        except Exception as e:
            return f"❌ **Error during audio extraction:** {str(e)}"

    async def _handle_video_conversion(
        self, media_files: List[str], output_prefs: Dict[str, Any], user_message: str
    ) -> str:
        """Handle video conversion with LLM analysis"""

        if not media_files:
            recent_file = self.get_recent_media_file()
            if recent_file:
                return f"I can convert video files. Did you mean to convert **{recent_file}**? Please specify the target format."
            else:
                return (
                    "I can convert video files. Please provide:\n\n"
                    "1. Video file path\n"
                    "2. Target format (mp4, avi, mov, mkv, webm)\n\n"
                    "Example: 'Convert video.avi to mp4'"
                )

        input_file = media_files[0]
        output_format = output_prefs.get("format", "mp4")
        video_codec = output_prefs.get("codec", "h264")

        try:
            result = await self._convert_video_format(input_file, output_format, video_codec)

            if result["success"]:
                return (
                    f"✅ **Video Conversion Completed**\n\n"
                    f"📁 **Input:** {input_file}\n"
                    f"🎬 **Output:** {result.get('output_file', 'Unknown')}\n"
                    f"📊 **Format:** {output_format.upper()}\n"
                    f"🔧 **Codec:** {video_codec}\n"
                    f"⏱️ **Time:** {result.get('execution_time', 0):.2f}s\n\n"
                    f"Your converted video is ready! 🎉"
                )
            else:
                return f"❌ **Video conversion failed:** {result.get('error', 'Unknown error')}"

        except Exception as e:
            return f"❌ **Error during video conversion:** {str(e)}"

    async def _create_video_thumbnail(
        self,
        input_video: str,
        timestamp: str = "00:00:05",
        output_format: str = "jpg",
        width: int = 320,
    ):
        """Create thumbnail - FIXED: Better FFmpeg command and error handling"""
        try:
            if not Path(input_video).exists():
                return {"success": False, "error": f"Input video file not found: {input_video}"}

            output_filename = f"thumbnail_{int(time.time())}.{output_format}"

            # Try multiple FFmpeg command approaches for better compatibility
            commands_to_try = [
                # Approach 1: Simple with scaling (most common)
                f"ffmpeg -y -v quiet -i ${{input_video}} -ss {timestamp} -vframes 1 -vf scale={width}:-1 ${{OUTPUT}}",
                # Approach 2: Basic thumbnail without scaling
                f"ffmpeg -y -v quiet -i ${{input_video}} -ss {timestamp} -vframes 1 ${{OUTPUT}}",
                # Approach 3: Alternative syntax
                f"ffmpeg -y -i ${{input_video}} -ss {timestamp} -frames:v 1 -q:v 2 ${{OUTPUT}}",
                # Approach 4: Most basic
                f"ffmpeg -i ${{input_video}} -ss {timestamp} -vframes 1 ${{OUTPUT}}",
            ]

            last_error = None
            for i, ffmpeg_command in enumerate(commands_to_try):
                result = self.media_executor.execute_ffmpeg_command(
                    ffmpeg_command=ffmpeg_command,
                    input_files={"input_video": input_video},
                    output_filename=output_filename,
                )

                if result["success"]:
                    return {
                        "success": True,
                        "message": f"Thumbnail created successfully (method {i + 1})",
                        "output_file": result.get("output_file", {}),
                        "input_video": input_video,
                        "execution_time": result["execution_time"],
                    }
                else:
                    last_error = result.get("error", "Unknown error")

            return {
                "success": False,
                "error": f"All thumbnail methods failed. Last error: {last_error}",
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    # PATCH: Replace the _resize_video method in MediaEditorAgent
    # Add this to your media_editor.py file

    async def _resize_video(
        self,
        input_video: str,
        width: int = None,
        height: int = None,
        maintain_aspect: bool = True,
        preset: str = "custom",
    ):
        """FIXED: Video resize with simpler, more compatible FFmpeg commands"""
        try:
            if not Path(input_video).exists():
                return {"success": False, "error": f"Input video file not found: {input_video}"}

            # Handle presets
            if preset == "720p":
                width, height = 1280, 720
            elif preset == "1080p":
                width, height = 1920, 1080
            elif preset == "4k":
                width, height = 3840, 2160
            elif preset == "480p":
                width, height = 854, 480

            if not width or not height:
                return {"success": False, "error": "Width and height must be specified"}

            # Ensure even dimensions (required for H.264)
            width = width + (width % 2)
            height = height + (height % 2)

            output_filename = f"resized_video_{int(time.time())}.mp4"

            # SIMPLIFIED: Use the same command pattern that works for thumbnails
            # Since thumbnail creation works, let's use a similar simple approach
            scale_commands = [
                # Approach 1: Ultra-simple, same style as working thumbnail command
                f"ffmpeg -y -i ${{input_video}} -vf scale={width}:{height} ${{OUTPUT}}",
                # Approach 2: With audio copy (like thumbnail but with audio)
                f"ffmpeg -y -i ${{input_video}} -vf scale={width}:{height} -c:a copy ${{OUTPUT}}",
                # Approach 3: Force even dimensions (H.264 compatible)
                f"ffmpeg -y -i ${{input_video}} -vf scale={width}:{height}:force_divisible_by=2 ${{OUTPUT}}",
                # Approach 4: Basic resize without filters
                f"ffmpeg -y -i ${{input_video}} -s {width}x{height} ${{OUTPUT}}",
            ]

            last_error = None
            for i, ffmpeg_command in enumerate(scale_commands):
                try:
                    print(f"🔄 Trying resize method {i + 1}: {width}x{height}")

                    result = self.media_executor.execute_ffmpeg_command(
                        ffmpeg_command=ffmpeg_command,
                        input_files={"input_video": input_video},
                        output_filename=output_filename,
                    )

                    if result["success"]:
                        return {
                            "success": True,
                            "message": f"Video resized successfully to {width}x{height} (method {i + 1})",
                            "output_file": result.get("output_file", {}),
                            "input_video": input_video,
                            "execution_time": result["execution_time"],
                            "method_used": i + 1,
                            "final_dimensions": f"{width}x{height}",
                        }
                    else:
                        last_error = result.get("error", "Unknown error")
                        print(f"❌ Method {i + 1} failed: {last_error[:100]}...")

                except Exception as approach_error:
                    last_error = str(approach_error)
                    print(f"❌ Method {i + 1} exception: {last_error}")

            return {
                "success": False,
                "error": f"All {len(scale_commands)} resize methods failed. Last error: {last_error}",
                "attempted_methods": len(scale_commands),
                "target_dimensions": f"{width}x{height}",
            }

        except Exception as e:
            return {"success": False, "error": f"Resize method error: {str(e)}"}

    # ALTERNATIVE: If the above doesn't work, try this minimal version
    async def _resize_video_minimal(
        self,
        input_video: str,
        width: int = None,
        height: int = None,
        maintain_aspect: bool = True,
        preset: str = "custom",
    ):
        """MINIMAL: Copy the exact working pattern from thumbnail creation"""
        try:
            if not Path(input_video).exists():
                return {"success": False, "error": f"Input video file not found: {input_video}"}

            # Handle presets
            if preset == "720p":
                width, height = 1280, 720
            elif preset == "1080p":
                width, height = 1920, 1080
            elif preset == "4k":
                width, height = 3840, 2160
            elif preset == "480p":
                width, height = 854, 480

            if not width or not height:
                return {"success": False, "error": "Width and height must be specified"}

            output_filename = f"resized_video_{int(time.time())}.mp4"

            # USE EXACT SAME PATTERN AS WORKING THUMBNAIL - just change the filter
            ffmpeg_command = (
                f"ffmpeg -y -v quiet -i ${{input_video}} -vf scale={width}:{height} ${{OUTPUT}}"
            )

            result = self.media_executor.execute_ffmpeg_command(
                ffmpeg_command=ffmpeg_command,
                input_files={"input_video": input_video},
                output_filename=output_filename,
            )

            if result["success"]:
                return {
                    "success": True,
                    "message": f"Video resized successfully to {width}x{height}",
                    "output_file": result.get("output_file", {}),
                    "input_video": input_video,
                    "execution_time": result["execution_time"],
                    "final_dimensions": f"{width}x{height}",
                }
            else:
                return {
                    "success": False,
                    "error": f"Video resize failed: {result.get('error', 'Unknown error')}",
                    "target_dimensions": f"{width}x{height}",
                }

        except Exception as e:
            return {"success": False, "error": f"Resize error: {str(e)}"}

    def _parse_dimensions(self, dimensions: str, user_message: str) -> tuple:
        """Parse dimensions from preferences or message - ENHANCED with better regex"""
        if dimensions:
            dimensions_str = str(dimensions).lower().strip()
            if dimensions_str == "720p":
                return 1280, 720
            elif dimensions_str == "1080p":
                return 1920, 1080
            elif dimensions_str == "4k":
                return 3840, 2160
            elif dimensions_str == "480p":
                return 854, 480
            elif "x" in dimensions_str:
                try:
                    width, height = dimensions_str.split("x")
                    return int(width), int(height)
                except:
                    pass

        # Parse from user message with improved patterns
        import re

        message_lower = user_message.lower()

        # Check for common presets first (more comprehensive)
        preset_patterns = [
            (r"\b720p?\b", (1280, 720)),
            (r"\b1080p?\b", (1920, 1080)),
            (r"\b4k\b", (3840, 2160)),
            (r"\b480p?\b", (854, 480)),
            (r"\bresize\s+to\s+720\b", (1280, 720)),
            (r"\bresize\s+to\s+1080\b", (1920, 1080)),
            (r"\bscale\s+to\s+720p?\b", (1280, 720)),
            (r"\bscale\s+to\s+1080p?\b", (1920, 1080)),
            (r"\bscale\s+to\s+480p?\b", (854, 480)),
        ]

        for pattern, dimensions in preset_patterns:
            if re.search(pattern, message_lower):
                return dimensions

        # Look for WIDTHxHEIGHT pattern (more flexible)
        dimension_matches = re.findall(r"(\d{3,4})\s*[x×]\s*(\d{3,4})", user_message)
        if dimension_matches:
            width, height = dimension_matches[0]
            return int(width), int(height)

        # Look for individual width/height mentions
        width_match = re.search(r"width[:\s]*(\d+)", message_lower)
        height_match = re.search(r"height[:\s]*(\d+)", message_lower)

        if width_match and height_match:
            return int(width_match.group(1)), int(height_match.group(1))

        # Look for single dimension with common ratios
        single_width = re.search(r"\bwidth\s+(\d+)", message_lower)
        single_height = re.search(r"\bheight\s+(\d+)", message_lower)

        if single_width:
            width = int(single_width.group(1))
            # Assume 16:9 ratio
            height = int(width * 9 / 16)
            return width, height

        if single_height:
            height = int(single_height.group(1))
            # Assume 16:9 ratio
            width = int(height * 16 / 9)
            return width, height

        # Default fallback
        return None, None

    async def _handle_video_resize(
        self, media_files: List[str], output_prefs: Dict[str, Any], user_message: str
    ) -> str:
        """Handle video resize with ENHANCED error reporting and user guidance"""

        if not media_files:
            recent_file = self.get_recent_media_file()
            if recent_file:
                return (
                    f"I can resize videos. Did you mean to resize **{recent_file}**? Please specify dimensions.\n\n"
                    f"**Examples:**\n"
                    f"• 'Resize {recent_file} to 720p'\n"
                    f"• 'Scale it to 1920x1080'\n"
                    f"• 'Make it 4k resolution'"
                )
            else:
                return (
                    "I can resize videos! Please provide:\n\n"
                    "**1. Video file path**\n"
                    "**2. Target dimensions**\n\n"
                    "**Supported formats:**\n"
                    "• Presets: 720p, 1080p, 4k, 480p\n"
                    "• Custom: 1920x1080, 1280x720, etc.\n\n"
                    "**Example:** 'Resize video.mp4 to 720p'"
                )

        input_file = media_files[0]
        dimensions = output_prefs.get("dimensions")

        # Parse dimensions with enhanced error handling
        width, height = self._parse_dimensions(dimensions, user_message)

        if not width or not height:
            return (
                f"I need specific dimensions to resize **{input_file}**.\n\n"
                f"**Please specify one of:**\n"
                f"• Standard: '720p', '1080p', '4k'\n"
                f"• Custom: '1920x1080', '1280x720'\n"
                f"• Explicit: 'width 1280 height 720'\n\n"
                f"**Examples:**\n"
                f"• 'Resize {input_file} to 720p'\n"
                f"• 'Scale to 1920x1080'\n"
                f"• 'Make it 4k resolution'"
            )

        # Validate dimensions
        if width < 100 or height < 100:
            return (
                f"❌ **Invalid dimensions:** {width}x{height} is too small.\n"
                f"Minimum supported size is 100x100 pixels."
            )

        if width > 7680 or height > 4320:
            return (
                f"❌ **Invalid dimensions:** {width}x{height} is too large.\n"
                f"Maximum supported size is 7680x4320 (8K)."
            )

        try:
            # Show what we're attempting
            processing_msg = (
                f"🎬 **Processing Video Resize**\n\n"
                f"📁 **Input:** {input_file}\n"
                f"📏 **Target:** {width}x{height}\n"
                f"⚙️ **Method:** Multiple fallback approaches\n\n"
                f"🔄 Processing..."
            )

            # Actually perform the resize
            result = await self._resize_video(input_file, width, height)

            if result["success"]:
                return (
                    f"✅ **Video Resize Completed**\n\n"
                    f"📁 **Input:** {input_file}\n"
                    f"🎬 **Output:** {result.get('output_file', {}).get('filename', 'Unknown')}\n"
                    f"📏 **Dimensions:** {result.get('final_dimensions', f'{width}x{height}')}\n"
                    f"⚙️ **Method:** {result.get('method_used', 'Unknown')}/{result.get('attempted_methods', 'N/A')}\n"
                    f"⏱️ **Time:** {result.get('execution_time', 0):.2f}s\n"
                    f"📊 **Size:** {result.get('output_file', {}).get('size_bytes', 0) // 1024}KB\n\n"
                    f"Your resized video is ready! 🎉"
                )
            else:
                error_msg = result.get("error", "Unknown error")
                attempted = result.get("attempted_methods", "several")

                # Provide helpful troubleshooting
                return (
                    f"❌ **Video Resize Failed**\n\n"
                    f"📁 **Input:** {input_file}\n"
                    f"📏 **Target:** {result.get('target_dimensions', f'{width}x{height}')}\n"
                    f"🔧 **Attempted:** {attempted} different methods\n\n"
                    f"**Error Details:**\n"
                    f"{error_msg[:300]}...\n\n"
                    f"**Possible Solutions:**\n"
                    f"• Try a different resolution (720p, 1080p)\n"
                    f"• Check if the input video is valid\n"
                    f"• Try with a smaller video file first\n"
                    f"• Contact support if the issue persists"
                )

        except Exception as e:
            return (
                f"❌ **Error during video resize:** {str(e)}\n\n"
                f"📁 **File:** {input_file}\n"
                f"📏 **Target:** {width}x{height}\n\n"
                f"Please try again or contact support if the problem continues."
            )

    async def _handle_media_trim(
        self, media_files: List[str], output_prefs: Dict[str, Any], user_message: str
    ) -> str:
        """Handle media trimming with LLM analysis"""

        if not media_files:
            recent_file = self.get_recent_media_file()
            if recent_file:
                return f"I can trim media files. Did you mean to trim **{recent_file}**? Please specify start time and duration."
            else:
                return (
                    "I can trim media files. Please provide:\n\n"
                    "1. Media file path\n"
                    "2. Start time (HH:MM:SS)\n"
                    "3. Duration or end time\n\n"
                    "Example: 'Trim video.mp4 from 00:01:30 for 30 seconds'"
                )

        input_file = media_files[0]
        timing = output_prefs.get("timing", {})

        start_time = timing.get("start")
        duration = timing.get("duration")

        # Parse timing from message if not in preferences
        if not start_time or not duration:
            start_time, duration = self._parse_timing_from_message(user_message)

        if not start_time:
            return (
                f"Please specify the start time for trimming **{input_file}**.\n\n"
                f"Example: 'Trim from 00:01:30 for 30 seconds'"
            )

        if not duration:
            return (
                f"Please specify the duration for trimming **{input_file}** from {start_time}.\n\n"
                f"Example: 'for 30 seconds' or 'for 2 minutes'"
            )

        try:
            result = await self._trim_media(input_file, start_time, duration)

            if result["success"]:
                return (
                    f"✅ **Media Trim Completed**\n\n"
                    f"📁 **Input:** {input_file}\n"
                    f"🎬 **Output:** {result.get('output_file', 'Unknown')}\n"
                    f"⏱️ **Start:** {start_time}\n"
                    f"⏰ **Duration:** {duration}\n"
                    f"🕐 **Time:** {result.get('execution_time', 0):.2f}s\n\n"
                    f"Your trimmed media is ready! 🎉"
                )
            else:
                return f"❌ **Media trim failed:** {result.get('error', 'Unknown error')}"

        except Exception as e:
            return f"❌ **Error during media trim:** {str(e)}"

    async def _handle_thumbnail_creation(
        self, media_files: List[str], output_prefs: Dict[str, Any], user_message: str
    ) -> str:
        """Handle thumbnail creation with LLM analysis"""

        if not media_files:
            recent_file = self.get_recent_media_file()
            if recent_file:
                return f"I can create thumbnails from videos. Did you mean to create a thumbnail from **{recent_file}**?"
            else:
                return (
                    "I can create thumbnails from videos. Please provide:\n\n"
                    "1. Video file path\n"
                    "2. Timestamp (HH:MM:SS) - optional\n\n"
                    "Example: 'Create thumbnail from video.mp4 at 00:05:00'"
                )

        input_file = media_files[0]
        timing = output_prefs.get("timing", {})
        timestamp = timing.get("start", "00:00:05")
        output_format = output_prefs.get("format", "jpg")

        try:
            result = await self._create_video_thumbnail(input_file, timestamp, output_format)

            if result["success"]:
                return (
                    f"✅ **Thumbnail Created**\n\n"
                    f"📁 **Video:** {input_file}\n"
                    f"🖼️ **Thumbnail:** {result.get('output_file', 'Unknown')}\n"
                    f"⏱️ **Timestamp:** {timestamp}\n"
                    f"📊 **Format:** {output_format.upper()}\n"
                    f"🕐 **Time:** {result.get('execution_time', 0):.2f}s\n\n"
                    f"Your thumbnail is ready! 🎉"
                )
            else:
                return f"❌ **Thumbnail creation failed:** {result.get('error', 'Unknown error')}"

        except Exception as e:
            return f"❌ **Error during thumbnail creation:** {str(e)}"

    async def _handle_media_info(self, media_files: List[str], user_message: str) -> str:
        """Handle media info requests with LLM analysis"""

        if not media_files:
            recent_file = self.get_recent_media_file()
            if recent_file:
                return f"I can provide information about media files. Did you mean to get info for **{recent_file}**?"
            else:
                return (
                    "I can provide detailed information about media files.\n\n"
                    "Please provide the path to a media file."
                )

        input_file = media_files[0]

        try:
            result = await self._get_media_info(input_file)

            if result["success"]:
                info = result.get("media_info", {})
                return (
                    f"📊 **Media Information for {input_file}**\n\n"
                    f"**📄 File:** {info.get('filename', 'Unknown')}\n"
                    f"**📦 Format:** {info.get('format', 'Unknown')}\n"
                    f"**⏱️ Duration:** {info.get('duration', 'Unknown')}\n"
                    f"**📏 Resolution:** {info.get('resolution', 'Unknown')}\n"
                    f"**🎬 Video Codec:** {info.get('video_codec', 'Unknown')}\n"
                    f"**🎵 Audio Codec:** {info.get('audio_codec', 'Unknown')}\n"
                    f"**📊 File Size:** {info.get('file_size', 'Unknown')}\n\n"
                    f"🎉 Information retrieval completed!"
                )
            else:
                return f"❌ **Failed to get media info:** {result.get('error', 'Unknown error')}"

        except Exception as e:
            return f"❌ **Error getting media info:** {str(e)}"

    async def _handle_media_help_request(self, user_message: str) -> str:
        """Handle media help requests with conversation context"""

        state = self.get_conversation_state()

        response = (
            "I'm your Media Editor Agent! I can help you with:\n\n"
            "🎥 **Video Processing**\n"
            "- Extract audio from videos\n"
            "- Convert between formats (MP4, AVI, MOV, MKV)\n"
            "- Resize and scale videos\n"
            "- Create thumbnails and frames\n"
            "- Trim and cut clips\n\n"
            "🎵 **Audio Processing**\n"
            "- Convert audio formats (MP3, WAV, AAC, FLAC)\n"
            "- Extract from videos\n"
            "- Adjust quality settings\n\n"
            "🧠 **Smart Context Features**\n"
            "- Remembers files from previous messages\n"
            "- Understands 'that video' and 'this file'\n"
            "- Maintains working context\n\n"
        )

        # Add current context information
        if state.current_resource:
            response += f"🎯 **Current File:** {state.current_resource}\n"

        if state.working_files:
            response += f"📁 **Working Files:** {len(state.working_files)} files\n"
            for file in state.working_files[-3:]:  # Show last 3
                response += f"   • {file}\n"

        response += "\n💡 **Examples:**\n"
        response += "• 'Extract audio from video.mp4 as MP3'\n"
        response += "• 'Convert that video to MP4'\n"
        response += "• 'Resize it to 720p'\n"
        response += "• 'Create a thumbnail at 2 minutes'\n"
        response += "\nI understand context from our conversation! 🚀"

        return response

    def _parse_timing_from_message(self, user_message: str) -> tuple:
        """Parse timing information from user message"""
        import re

        # Look for time patterns
        time_patterns = re.findall(r"\b\d{1,2}:\d{2}:\d{2}\b", user_message)
        duration_patterns = re.findall(
            r"(\d+)\s*(?:seconds?|secs?|minutes?|mins?)", user_message, re.IGNORECASE
        )

        start_time = time_patterns[0] if time_patterns else None

        duration = None
        if duration_patterns:
            duration_num = duration_patterns[0]
            if "minute" in user_message.lower() or "min" in user_message.lower():
                duration = f"00:{duration_num:0>2}:00"
            else:
                duration = f"{int(duration_num)}"

        return start_time, duration

    def _extract_media_intent_from_llm_response(
        self, llm_response: str, user_message: str
    ) -> Dict[str, Any]:
        """Extract media intent from non-JSON LLM response"""
        content_lower = llm_response.lower()

        if "extract" in content_lower and "audio" in content_lower:
            intent = "extract_audio"
        elif "convert" in content_lower:
            intent = "convert_video"
        elif "resize" in content_lower:
            intent = "resize_video"
        elif "trim" in content_lower or "cut" in content_lower:
            intent = "trim_media"
        elif "thumbnail" in content_lower:
            intent = "create_thumbnail"
        elif "info" in content_lower:
            intent = "get_info"
        else:
            intent = "help_request"

        return {
            "primary_intent": intent,
            "media_files": [],
            "output_preferences": {"format": None, "quality": "medium"},
            "uses_context_reference": False,
            "context_type": "none",
            "technical_specs": {},
            "confidence": 0.6,
        }

    def _initialize_media_executor(self):
        """Initialize media executor"""
        from ..executors.media_executor import MediaDockerExecutor

        self.media_executor = MediaDockerExecutor(self.media_config)

    def _add_media_tools(self):
        """Add media processing tools"""

        # Extract audio from video tool
        self.add_tool(
            AgentTool(
                name="extract_audio_from_video",
                description="Extract audio track from video file",
                function=self._extract_audio_from_video,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "input_video": {
                            "type": "string",
                            "description": "Path to input video file",
                        },
                        "output_format": {
                            "type": "string",
                            "enum": ["mp3", "wav", "aac", "flac"],
                            "default": "mp3",
                        },
                        "audio_quality": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                            "default": "medium",
                        },
                    },
                    "required": ["input_video"],
                },
            )
        )

        # Convert video format tool
        self.add_tool(
            AgentTool(
                name="convert_video_format",
                description="Convert video to different format/codec",
                function=self._convert_video_format,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "input_video": {
                            "type": "string",
                            "description": "Path to input video file",
                        },
                        "output_format": {
                            "type": "string",
                            "enum": ["mp4", "avi", "mov", "mkv", "webm"],
                            "default": "mp4",
                        },
                        "video_codec": {
                            "type": "string",
                            "enum": ["h264", "h265", "vp9", "copy"],
                            "default": "h264",
                        },
                        "audio_codec": {
                            "type": "string",
                            "enum": ["aac", "mp3", "opus", "copy"],
                            "default": "aac",
                        },
                        "crf": {"type": "integer", "minimum": 0, "maximum": 51, "default": 23},
                    },
                    "required": ["input_video"],
                },
            )
        )

        # Get media information tool
        self.add_tool(
            AgentTool(
                name="get_media_info",
                description="Get detailed information about media file",
                function=self._get_media_info,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Path to media file"}
                    },
                    "required": ["file_path"],
                },
            )
        )

        # Resize video tool
        self.add_tool(
            AgentTool(
                name="resize_video",
                description="Resize video to specific dimensions",
                function=self._resize_video,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "input_video": {
                            "type": "string",
                            "description": "Path to input video file",
                        },
                        "width": {"type": "integer", "description": "Target width in pixels"},
                        "height": {"type": "integer", "description": "Target height in pixels"},
                        "maintain_aspect": {"type": "boolean", "default": True},
                        "preset": {
                            "type": "string",
                            "enum": ["720p", "1080p", "4k", "480p", "custom"],
                            "default": "custom",
                        },
                    },
                    "required": ["input_video"],
                },
            )
        )

        # Trim media tool
        self.add_tool(
            AgentTool(
                name="trim_media",
                description="Trim/cut media file to specific time range",
                function=self._trim_media,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "input_file": {"type": "string", "description": "Path to input media file"},
                        "start_time": {
                            "type": "string",
                            "description": "Start time (HH:MM:SS or seconds)",
                        },
                        "duration": {
                            "type": "string",
                            "description": "Duration (HH:MM:SS or seconds)",
                        },
                        "end_time": {
                            "type": "string",
                            "description": "End time (alternative to duration)",
                        },
                    },
                    "required": ["input_file", "start_time"],
                },
            )
        )

        # Create video thumbnail tool
        self.add_tool(
            AgentTool(
                name="create_video_thumbnail",
                description="Extract thumbnail/frame from video",
                function=self._create_video_thumbnail,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "input_video": {
                            "type": "string",
                            "description": "Path to input video file",
                        },
                        "timestamp": {
                            "type": "string",
                            "description": "Time to extract frame (HH:MM:SS)",
                            "default": "00:00:05",
                        },
                        "output_format": {
                            "type": "string",
                            "enum": ["jpg", "png", "bmp"],
                            "default": "jpg",
                        },
                        "width": {
                            "type": "integer",
                            "description": "Thumbnail width",
                            "default": 320,
                        },
                    },
                    "required": ["input_video"],
                },
            )
        )

    # Media processing method implementations
    async def _extract_audio_from_video_orig(
        self, input_video: str, output_format: str = "mp3", audio_quality: str = "medium"
    ):
        """Extract audio from video file"""
        try:
            if not Path(input_video).exists():
                return {"success": False, "error": f"Input video file not found: {input_video}"}

            # Quality settings
            quality_settings = {"low": "-b:a 128k", "medium": "-b:a 192k", "high": "-b:a 320k"}

            output_filename = f"extracted_audio_{int(time.time())}.{output_format}"

            ffmpeg_command = (
                f"ffmpeg -i ${{input_video}} "
                f"{quality_settings.get(audio_quality, quality_settings['medium'])} "
                f"-vn -acodec {self._get_audio_codec(output_format)} "
                f"${{OUTPUT}}"
            )

            result = self.media_executor.execute_ffmpeg_command(
                ffmpeg_command=ffmpeg_command,
                input_files={"input_video": input_video},
                output_filename=output_filename,
            )

            if result["success"]:
                return {
                    "success": True,
                    "message": f"Audio extracted successfully to {output_format}",
                    "output_file": result["output_file"],
                    "input_video": input_video,
                    "execution_time": result["execution_time"],
                }
            else:
                return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ====start
    # FIXED: Audio extraction with proper command syntax
    async def _extract_audio_from_video(
        self, input_video: str, output_format: str = "mp3", audio_quality: str = "medium"
    ):
        """FIXED: Extract audio from video file with proper FFmpeg syntax"""
        try:
            if not Path(input_video).exists():
                return {"success": False, "error": f"Input video file not found: {input_video}"}

            # Quality settings - FIXED: Proper bitrate syntax
            quality_settings = {"low": "128k", "medium": "192k", "high": "320k"}

            output_filename = f"extracted_audio_{int(time.time())}.{output_format}"

            # FIXED: Proper FFmpeg command without shell syntax errors
            audio_codec = self._get_audio_codec(output_format)
            bitrate = quality_settings.get(audio_quality, "192k")

            ffmpeg_command = (
                f"ffmpeg -i ${{input_video}} -vn -acodec {audio_codec} -b:a {bitrate} ${{OUTPUT}}"
            )

            result = self.media_executor.execute_ffmpeg_command(
                ffmpeg_command=ffmpeg_command,
                input_files={"input_video": input_video},
                output_filename=output_filename,
            )

            if result["success"]:
                return {
                    "success": True,
                    "message": f"Audio extracted successfully to {output_format}",
                    "output_file": result.get("output_file", {}),
                    "input_video": input_video,
                    "execution_time": result["execution_time"],
                }
            else:
                return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    # FIXED: Video conversion with proper syntax
    async def _convert_video_format(
        self,
        input_video: str,
        output_format: str = "mp4",
        video_codec: str = "h264",
        audio_codec: str = "aac",
        crf: int = 23,
    ):
        """FIXED: Convert video format with proper FFmpeg syntax"""
        try:
            if not Path(input_video).exists():
                return {"success": False, "error": f"Input video file not found: {input_video}"}

            output_filename = f"converted_video_{int(time.time())}.{output_format}"

            # FIXED: Proper codec mapping
            codec_map = {"h264": "libx264", "h265": "libx265", "vp9": "libvpx-vp9"}

            video_codec_proper = codec_map.get(video_codec, "libx264")

            # FIXED: Simplified, working FFmpeg command
            ffmpeg_command = f"ffmpeg -i ${{input_video}} -c:v {video_codec_proper} -c:a {audio_codec} -crf {crf} ${{OUTPUT}}"

            result = self.media_executor.execute_ffmpeg_command(
                ffmpeg_command=ffmpeg_command,
                input_files={"input_video": input_video},
                output_filename=output_filename,
            )

            if result["success"]:
                return {
                    "success": True,
                    "message": f"Video converted successfully to {output_format}",
                    "output_file": result.get("output_file", {}),
                    "input_video": input_video,
                    "execution_time": result["execution_time"],
                }
            else:
                return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    # FIXED: Media info with proper JSON parsing
    async def _get_media_info(self, file_path: str):
        """FIXED: Get media info with proper JSON parsing"""
        try:
            if not Path(file_path).exists():
                return {"success": False, "error": f"Media file not found: {file_path}"}

            output_filename = f"media_info_{int(time.time())}.json"

            # FIXED: Proper ffprobe command that outputs to file
            ffprobe_command = f"ffprobe -v quiet -print_format json -show_format -show_streams ${{input_file}} > ${{OUTPUT}}"

            result = self.media_executor.execute_ffmpeg_command(
                ffmpeg_command=ffprobe_command,
                input_files={"input_file": file_path},
                output_filename=output_filename,
            )

            if result["success"]:
                try:
                    # FIXED: Read the JSON output file
                    output_file_info = result.get("output_file", {})
                    output_file_path = output_file_info.get("final_path")

                    if output_file_path and os.path.exists(output_file_path):
                        with open(output_file_path, "r") as f:
                            info_data = json.load(f)

                        # Clean up temp file
                        os.remove(output_file_path)
                    else:
                        # Fallback: try parsing from stdout
                        info_data = json.loads(result.get("output", "{}"))

                    format_info = info_data.get("format", {})
                    streams = info_data.get("streams", [])

                    video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
                    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), {})

                    # FIXED: Safe value extraction with defaults
                    media_info = {
                        "filename": Path(file_path).name,
                        "format": format_info.get("format_name", "Unknown"),
                        "duration": self._format_duration(format_info.get("duration")),
                        "file_size": self._format_file_size(format_info.get("size")),
                        "resolution": self._get_resolution(video_stream),
                        "video_codec": video_stream.get("codec_name", "N/A"),
                        "audio_codec": audio_stream.get("codec_name", "N/A"),
                        "bit_rate": format_info.get("bit_rate", "Unknown"),
                    }

                    return {
                        "success": True,
                        "media_info": media_info,
                        "execution_time": result["execution_time"],
                    }

                except json.JSONDecodeError as e:
                    return {
                        "success": False,
                        "error": f"Failed to parse media information: {str(e)}",
                    }
            else:
                return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    # FIXED: Video resize with proper scaling

    # HELPER METHODS - FIXED
    def _get_audio_codec(self, format: str) -> str:
        """Get appropriate audio codec for format"""
        codec_map = {
            "mp3": "libmp3lame",
            "aac": "aac",
            "wav": "pcm_s16le",
            "flac": "flac",
            "ogg": "libvorbis",
            "opus": "libopus",
        }
        return codec_map.get(format, "aac")

    def _format_duration(self, duration_str):
        """Format duration string safely"""
        if not duration_str:
            return "Unknown"
        try:
            duration = float(duration_str)
            hours = int(duration // 3600)
            minutes = int((duration % 3600) // 60)
            seconds = int(duration % 60)
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        except:
            return str(duration_str)

    def _format_file_size(self, size_str):
        """Format file size safely"""
        if not size_str:
            return "Unknown"
        try:
            size = int(size_str)
            if size < 1024:
                return f"{size} B"
            elif size < 1024 * 1024:
                return f"{size / 1024:.1f} KB"
            elif size < 1024 * 1024 * 1024:
                return f"{size / (1024 * 1024):.1f} MB"
            else:
                return f"{size / (1024 * 1024 * 1024):.1f} GB"
        except:
            return str(size_str)

    def _get_resolution(self, video_stream):
        """Get video resolution safely"""
        if not video_stream:
            return "N/A"
        width = video_stream.get("width")
        height = video_stream.get("height")
        if width and height:
            return f"{width}x{height}"
        return "Unknown"

    # == end==
    async def _convert_video_format_orig(
        self,
        input_video: str,
        output_format: str = "mp4",
        video_codec: str = "h264",
        audio_codec: str = "aac",
        crf: int = 23,
    ):
        """Convert video format"""
        try:
            if not Path(input_video).exists():
                return {"success": False, "error": f"Input video file not found: {input_video}"}

            output_filename = f"converted_video_{int(time.time())}.{output_format}"

            ffmpeg_command = (
                f"ffmpeg -i ${{input_video}} "
                f"-c:v {video_codec} -c:a {audio_codec} "
                f"-crf {crf} "
                f"${{OUTPUT}}"
            )

            result = self.media_executor.execute_ffmpeg_command(
                ffmpeg_command=ffmpeg_command,
                input_files={"input_video": input_video},
                output_filename=output_filename,
            )

            if result["success"]:
                return {
                    "success": True,
                    "message": f"Video converted successfully to {output_format}",
                    "output_file": result["output_file"],
                    "input_video": input_video,
                    "execution_time": result["execution_time"],
                }
            else:
                return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _get_media_info_orig(self, file_path: str):
        """Get media info"""
        try:
            if not Path(file_path).exists():
                return {"success": False, "error": f"Media file not found: {file_path}"}

            ffprobe_command = (
                f"ffprobe -v quiet -print_format json -show_format -show_streams "
                f"${{input_file}}"
            )

            result = self.media_executor.execute_ffmpeg_command(
                ffmpeg_command=ffprobe_command,
                input_files={"input_file": file_path},
                output_filename=None,  # No output file for info
            )

            if result["success"]:
                # Parse ffprobe output
                try:
                    info_data = json.loads(result.get("output", "{}"))
                    format_info = info_data.get("format", {})
                    streams = info_data.get("streams", [])

                    video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
                    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), {})

                    media_info = {
                        "filename": Path(file_path).name,
                        "format": format_info.get("format_name", "Unknown"),
                        "duration": format_info.get("duration", "Unknown"),
                        "file_size": format_info.get("size", "Unknown"),
                        "resolution": (
                            f"{video_stream.get('width', 'Unknown')}x{video_stream.get('height', 'Unknown')}"
                            if video_stream
                            else "N/A"
                        ),
                        "video_codec": video_stream.get("codec_name", "N/A"),
                        "audio_codec": audio_stream.get("codec_name", "N/A"),
                    }

                    return {
                        "success": True,
                        "media_info": media_info,
                        "execution_time": result["execution_time"],
                    }
                except json.JSONDecodeError:
                    return {"success": False, "error": "Failed to parse media information"}
            else:
                return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _create_video_thumbnail_orig(
        self,
        input_video: str,
        timestamp: str = "00:00:05",
        output_format: str = "jpg",
        width: int = 320,
    ):
        """Create thumbnail"""
        try:
            if not Path(input_video).exists():
                return {"success": False, "error": f"Input video file not found: {input_video}"}

            output_filename = f"thumbnail_{int(time.time())}.{output_format}"

            ffmpeg_command = (
                f"ffmpeg -i ${{input_video}} "
                f"-ss {timestamp} "
                f"-vframes 1 "
                f"-vf scale={width}:-1 "
                f"${{OUTPUT}}"
            )

            result = self.media_executor.execute_ffmpeg_command(
                ffmpeg_command=ffmpeg_command,
                input_files={"input_video": input_video},
                output_filename=output_filename,
            )

            if result["success"]:
                return {
                    "success": True,
                    "message": f"Thumbnail created successfully",
                    "output_file": result["output_file"],
                    "input_video": input_video,
                    "execution_time": result["execution_time"],
                }
            else:
                return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _get_audio_codec_orig(self, format: str) -> str:
        """Get appropriate audio codec for format"""
        codec_map = {
            "mp3": "libmp3lame",
            "aac": "aac",
            "wav": "pcm_s16le",
            "flac": "flac",
            "ogg": "libvorbis",
            "opus": "libopus",
        }
        return codec_map.get(format, "aac")

    async def _trim_media(
        self, input_file: str, start_time: str, duration: str = None, end_time: str = None
    ):
        """Trim media"""
        try:
            if not Path(input_file).exists():
                return {"success": False, "error": f"Input file not found: {input_file}"}

            output_filename = f"trimmed_media_{int(time.time())}.{Path(input_file).suffix[1:]}"

            # Build ffmpeg command
            ffmpeg_command = f"ffmpeg -i ${{input_file}} -ss {start_time} "

            if duration:
                ffmpeg_command += f"-t {duration} "
            elif end_time:
                ffmpeg_command += f"-to {end_time} "
            else:
                return {"success": False, "error": "Either duration or end_time must be specified"}

            ffmpeg_command += "-c copy ${{OUTPUT}}"

            result = self.media_executor.execute_ffmpeg_command(
                ffmpeg_command=ffmpeg_command,
                input_files={"input_file": input_file},
                output_filename=output_filename,
            )

            if result["success"]:
                return {
                    "success": True,
                    "message": f"Media trimmed successfully",
                    "output_file": result["output_file"],
                    "input_file": input_file,
                    "execution_time": result["execution_time"],
                }
            else:
                return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def process_message_stream(
        self, message: AgentMessage, context: ExecutionContext = None
    ) -> AsyncIterator[StreamChunk]:
        """Stream processing for MediaEditorAgent - COMPLETE IMPLEMENTATION"""
        self.memory.store_message(message)

        try:
            user_message = message.content
            self.update_conversation_state(user_message)

            yield StreamChunk(
                text="**Media Editor Agent**\n\n",
                sub_type=StreamSubType.STATUS,
                metadata={"agent": "media_editor", "phase": "initialization"},
            )

            # Get conversation context for streaming
            conversation_context = self._get_media_conversation_context_summary()
            conversation_history = await self.get_conversation_history(
                limit=5, include_metadata=True
            )

            yield StreamChunk(
                text="Analyzing media processing request...\n",
                sub_type=StreamSubType.STATUS,
                metadata={"phase": "analysis"},
            )

            # Build LLM context for streaming
            llm_context = {
                "conversation_history": conversation_history,
                "conversation_id": message.conversation_id,
                "streaming": True,
                "user_id": message.sender_id,
                "agent_type": "media_editor",
            }

            intent_analysis = await self._llm_analyze_media_intent(
                user_message, conversation_context
            )
            primary_intent = intent_analysis.get("primary_intent", "help_request")

            yield StreamChunk(
                text=f"**Detected Intent:** {primary_intent.replace('_', ' ').title()}\n\n",
                sub_type=StreamSubType.STATUS,
                metadata={"intent": primary_intent},
            )

            if primary_intent == "extract_audio":
                yield StreamChunk(
                    text="🎵 **Audio Extraction**\n\n",
                    sub_type=StreamSubType.STATUS,
                    metadata={"operation": "extract_audio"},
                )
                response_content = await self._handle_audio_extraction_with_context(
                    intent_analysis.get("media_files", []),
                    intent_analysis.get("output_preferences", {}),
                    user_message,
                    llm_context,
                )
                yield StreamChunk(
                    text=response_content,
                    sub_type=StreamSubType.RESULT,
                    metadata={"operation": "extract_audio", "content_type": "processing_result"},
                )

            elif primary_intent == "convert_video":
                yield StreamChunk(
                    text="🎬 **Video Conversion**\n\n",
                    sub_type=StreamSubType.STATUS,
                    metadata={"operation": "convert_video"},
                )
                response_content = await self._handle_video_conversion_with_context(
                    intent_analysis.get("media_files", []),
                    intent_analysis.get("output_preferences", {}),
                    user_message,
                    llm_context,
                )
                yield StreamChunk(
                    text=response_content,
                    sub_type=StreamSubType.RESULT,
                    metadata={"operation": "convert_video", "content_type": "processing_result"},
                )

            elif primary_intent == "resize_video":
                yield StreamChunk(
                    text="📏 **Video Resize**\n\n",
                    sub_type=StreamSubType.STATUS,
                    metadata={"operation": "resize_video"},
                )
                response_content = await self._handle_video_resize(
                    intent_analysis.get("media_files", []),
                    intent_analysis.get("output_preferences", {}),
                    user_message,
                )
                yield response_content

            elif primary_intent == "trim_media":
                yield "✂️ **Media Trim**\n\n"
                response_content = await self._handle_media_trim(
                    intent_analysis.get("media_files", []),
                    intent_analysis.get("output_preferences", {}),
                    user_message,
                )
                yield response_content

            elif primary_intent == "create_thumbnail":
                yield "🖼️ **Thumbnail Creation**\n\n"
                response_content = await self._handle_thumbnail_creation(
                    intent_analysis.get("media_files", []),
                    intent_analysis.get("output_preferences", {}),
                    user_message,
                )
                yield response_content

            elif primary_intent == "get_info":
                yield "📊 **Media Information**\n\n"
                response_content = await self._handle_media_info(
                    intent_analysis.get("media_files", []), user_message
                )
                yield response_content

            else:
                # Help request or other - use LLM with context
                if self.llm_service:
                    enhanced_system_message = self.get_system_message_for_llm(llm_context)
                    help_prompt = f"As a media processing assistant, help with: {user_message}"

                    # Stream with conversation context
                    async for chunk in self.llm_service.generate_response_stream(
                        help_prompt, context=llm_context, system_message=enhanced_system_message
                    ):
                        yield chunk
                else:
                    response_content = await self._route_media_with_llm_analysis(
                        intent_analysis, user_message, context
                    )
                    yield response_content

        except Exception as e:
            yield f"❌ **Media Editor Error:** {str(e)}"

    async def _handle_audio_extraction_with_context(
        self,
        media_files: List[str],
        output_prefs: Dict[str, Any],
        user_message: str,
        llm_context: Dict[str, Any],
    ) -> str:
        """Handle audio extraction with conversation context"""
        # Use the context to provide more intelligent responses
        if self.llm_service and llm_context.get("conversation_history"):
            try:
                enhanced_system_message = self.get_system_message_for_llm(llm_context)
                context_prompt = f"""Based on our conversation history, help with audio extraction for: {user_message}

    Consider any previous media operations and provide contextual guidance."""

                # Get LLM guidance, then proceed with extraction
                guidance = await self.llm_service.generate_response(
                    prompt=context_prompt,
                    context=llm_context,
                    system_message=enhanced_system_message,
                )

                # Proceed with actual extraction
                result = await self._handle_audio_extraction(
                    media_files, output_prefs, user_message
                )

                # Enhance the result with context-aware messaging
                if "✅" in result:
                    result += f"\n\n💡 **Context Note:** {guidance[:100]}..."

                return result

            except Exception as e:
                # Fallback to regular extraction if context processing fails
                return await self._handle_audio_extraction(media_files, output_prefs, user_message)
        else:
            # No LLM or context available, use regular method
            return await self._handle_audio_extraction(media_files, output_prefs, user_message)

    async def _handle_video_conversion_with_context(
        self,
        media_files: List[str],
        output_prefs: Dict[str, Any],
        user_message: str,
        llm_context: Dict[str, Any],
    ) -> str:
        """Handle video conversion with conversation context"""
        # Use the context to provide more intelligent responses
        if self.llm_service and llm_context.get("conversation_history"):
            try:
                enhanced_system_message = self.get_system_message_for_llm(llm_context)
                context_prompt = f"""Based on our conversation history, help with video conversion for: {user_message}

    Consider any previous media operations and provide contextual guidance."""

                # Get LLM guidance, then proceed with conversion
                guidance = await self.llm_service.generate_response(
                    prompt=context_prompt,
                    context=llm_context,
                    system_message=enhanced_system_message,
                )

                # Proceed with actual conversion
                result = await self._handle_video_conversion(
                    media_files, output_prefs, user_message
                )

                # Enhance the result with context-aware messaging
                if "✅" in result:
                    result += f"\n\n💡 **Context Note:** {guidance[:100]}..."

                return result

            except Exception as e:
                # Fallback to regular conversion if context processing fails
                return await self._handle_video_conversion(media_files, output_prefs, user_message)
        else:
            # No LLM or context available, use regular method
            return await self._handle_video_conversion(media_files, output_prefs, user_message)

    def get_agent_status(self) -> Dict[str, Any]:
        """Get current agent status and configuration"""
        return {
            "agent_id": self.agent_id,
            "agent_type": "media_editor",
            "role": self.role.value,
            "name": self.name,
            "description": self.description,
            "session_id": self.context.session_id,
            "conversation_id": self.context.conversation_id,
            "user_id": self.context.user_id,
            "has_memory": bool(self.memory),
            "has_llm_service": bool(self.llm_service),
            "system_message_enabled": bool(self.system_message),
            "docker_available": bool(
                hasattr(self, "media_executor") and self.media_executor.available
            ),
            "media_config": {
                "docker_image": (
                    getattr(self.media_config, "docker_image", "Unknown")
                    if hasattr(self, "media_config")
                    else "Unknown"
                ),
                "timeout": (
                    getattr(self.media_config, "timeout", "Unknown")
                    if hasattr(self, "media_config")
                    else "Unknown"
                ),
                "input_dir": (
                    getattr(self.media_config, "input_dir", "Unknown")
                    if hasattr(self, "media_config")
                    else "Unknown"
                ),
                "output_dir": (
                    getattr(self.media_config, "output_dir", "Unknown")
                    if hasattr(self, "media_config")
                    else "Unknown"
                ),
            },
            "conversation_state": (
                {
                    "current_resource": self.conversation_state.current_resource,
                    "current_operation": self.conversation_state.current_operation,
                    "last_intent": self.conversation_state.last_intent,
                }
                if hasattr(self, "conversation_state")
                else None
            ),
            "capabilities": [
                "audio_extraction",
                "video_conversion",
                "video_resizing",
                "media_trimming",
                "thumbnail_creation",
                "media_info_retrieval",
                "context_awareness",
                "ffmpeg_processing",
                "docker_execution",
                "streaming_responses",
            ],
        }
