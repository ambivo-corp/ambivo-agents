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
from ..core.file_resolution import resolve_agent_file_path
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
            - Process image files (PNG, JPEG, GIF, BMP, TIFF) with various transformations
            - Image operations: resize, crop, rotate, grayscale, brightness/contrast, blur, sharpen
            - Image watermarking: apply image and text watermarks with position and opacity control
            - Transparency operations: background removal, transparent canvas creation, alpha masking
            - Batch image processing and format conversion
            - Remember file references from previous conversations naturally
            - Understand context like "that video", "this image", or "the file we just processed"
            - Provide clear progress updates and detailed processing results
            - Handle technical specifications like codecs, quality settings, dimensions, and image filters"""

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
            }

    async def _llm_analyze_media_intent(
        self, user_message: str, conversation_context: str = ""
    ) -> Dict[str, Any]:
        """Use LLM to analyze media processing intent"""
        if not self.llm_service:
            return self._keyword_based_media_analysis(user_message)

        prompt = f"""
        Analyze this user message in the context of media processing and extract:
        1. Primary intent (extract_audio, convert_video, resize_video, trim_media, create_thumbnail, get_info, help_request, resize_image, crop_image, rotate_image, convert_image, grayscale_image, adjust_image, blur_image, batch_process_images)
        2. Media file references (file paths, video/audio/image files)
        3. Output preferences (format, quality, dimensions, timing, rotation, cropping area)
        4. Context references (referring to previous media operations)
        5. Technical specifications (codecs, bitrates, resolution, image filters, etc.)

        Conversation Context:
        {conversation_context}

        Current User Message: {user_message}

        Respond in JSON format:
        {{
            "primary_intent": "extract_audio|convert_video|resize_video|trim_media|create_thumbnail|get_info|help_request|resize_image|crop_image|rotate_image|convert_image|grayscale_image|adjust_image|blur_image|batch_process_images|apply_watermark|apply_text_watermark|remove_background|create_transparent_canvas|apply_alpha_mask",
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
        elif any(
            word in content_lower for word in ["convert", "change format", "transform"]
        ) and any(word in content_lower for word in ["video", "mp4", "avi", "mov"]):
            intent = "convert_video"
        elif any(
            word in content_lower for word in ["convert", "change format", "transform"]
        ) and any(
            word in content_lower
            for word in ["image", "picture", "photo", "png", "jpg", "jpeg", "gif", "bmp"]
        ):
            intent = "convert_image"
        elif any(word in content_lower for word in ["resize", "scale", "dimensions"]) and any(
            word in content_lower for word in ["video", "mp4", "avi"]
        ):
            intent = "resize_video"
        elif any(word in content_lower for word in ["resize", "scale", "dimensions"]) and any(
            word in content_lower for word in ["image", "picture", "photo", "png", "jpg"]
        ):
            intent = "resize_image"
        elif any(word in content_lower for word in ["crop", "cropping", "cut out"]):
            intent = "crop_image"
        elif any(word in content_lower for word in ["rotate", "rotation", "turn", "flip"]):
            intent = "rotate_image"
        elif any(
            word in content_lower
            for word in ["grayscale", "grey", "gray", "black and white", "monochrome"]
        ):
            intent = "grayscale_image"
        elif any(word in content_lower for word in ["brightness", "contrast", "adjust", "enhance"]):
            intent = "adjust_image"
        elif any(word in content_lower for word in ["blur", "sharpen", "smooth", "soften"]):
            intent = "blur_image"
        elif any(word in content_lower for word in ["batch", "multiple", "all images", "folder"]):
            intent = "batch_process_images"
        elif any(word in content_lower for word in ["watermark", "logo", "overlay"]) and any(
            word in content_lower for word in ["image", "picture", "photo"]
        ):
            intent = "apply_watermark"
        elif any(word in content_lower for word in ["watermark", "logo", "overlay"]) and any(
            word in content_lower for word in ["text", "title", "caption"]
        ):
            intent = "apply_text_watermark"
        elif any(
            word in content_lower
            for word in ["transparent", "remove background", "background removal", "chromakey"]
        ):
            intent = "remove_background"
        elif any(
            word in content_lower
            for word in ["transparent canvas", "blank transparent", "empty transparent"]
        ):
            intent = "create_transparent_canvas"
        elif any(
            word in content_lower for word in ["alpha mask", "transparency mask", "apply mask"]
        ):
            intent = "apply_alpha_mask"
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
        self, message: Union[str, AgentMessage], context: ExecutionContext = None
    ) -> AgentMessage:
        """Process message with LLM-based media intent detection - FIXED: Context preserved across provider switches"""

        # Handle both string and AgentMessage inputs
        if isinstance(message, AgentMessage):
            user_message = message.content
            original_message = message
        else:
            user_message = str(message)
            original_message = AgentMessage(
                id=str(uuid.uuid4()),
                sender_id=context.user_id if context else self.context.user_id,
                recipient_id=self.agent_id,
                content=user_message,
                message_type=MessageType.USER_INPUT,
                timestamp=datetime.now(),
            )

        self.memory.store_message(original_message)

        try:

            # Update conversation state
            self.update_conversation_state(user_message)

            llm_context_from_routing = original_message.metadata.get("llm_context", {})
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
                "conversation_id": original_message.conversation_id,
                "user_id": original_message.sender_id,
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
                recipient_id=original_message.sender_id,
                session_id=original_message.session_id,
                conversation_id=original_message.conversation_id,
            )

            self.memory.store_message(response)
            return response

        except Exception as e:
            error_response = self.create_response(
                content=f"Media Editor Agent error: {str(e)}",
                recipient_id=original_message.sender_id,
                message_type=MessageType.ERROR,
                session_id=original_message.session_id,
                conversation_id=original_message.conversation_id,
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
        1. Primary intent (extract_audio, convert_video, resize_video, trim_media, create_thumbnail, get_info, help_request, resize_image, crop_image, rotate_image, convert_image, grayscale_image, adjust_image, blur_image, batch_process_images)
        2. Media file references (file paths, video/audio/image files)
        3. Output preferences (format, quality, dimensions, timing, rotation, cropping area)
        4. Context references (referring to previous media operations)
        5. Technical specifications (codecs, bitrates, resolution, image filters, etc.)

        Conversation Context:
        {conversation_context}

        Current User Message: {user_message}

        Respond in JSON format:
        {{
            "primary_intent": "extract_audio|convert_video|resize_video|trim_media|create_thumbnail|get_info|help_request|resize_image|crop_image|rotate_image|convert_image|grayscale_image|adjust_image|blur_image|batch_process_images|apply_watermark|apply_text_watermark|remove_background|create_transparent_canvas|apply_alpha_mask",
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
        # Image processing intents
        elif primary_intent == "resize_image":
            return await self._handle_image_resize(media_files, output_prefs, user_message)
        elif primary_intent == "crop_image":
            return await self._handle_image_crop(media_files, output_prefs, user_message)
        elif primary_intent == "rotate_image":
            return await self._handle_image_rotate(media_files, output_prefs, user_message)
        elif primary_intent == "convert_image":
            return await self._handle_image_convert(media_files, output_prefs, user_message)
        elif primary_intent == "grayscale_image":
            return await self._handle_image_grayscale(media_files, output_prefs, user_message)
        elif primary_intent == "adjust_image":
            return await self._handle_image_adjust(media_files, output_prefs, user_message)
        elif primary_intent == "blur_image":
            return await self._handle_image_blur(media_files, output_prefs, user_message)
        elif primary_intent == "batch_process_images":
            return await self._handle_batch_image_processing(
                media_files, output_prefs, user_message
            )
        # Watermarking and transparency intents
        elif primary_intent == "apply_watermark":
            return await self._handle_watermark_application(media_files, output_prefs, user_message)
        elif primary_intent == "apply_text_watermark":
            return await self._handle_text_watermark_application(
                media_files, output_prefs, user_message
            )
        elif primary_intent == "remove_background":
            return await self._handle_background_removal(media_files, output_prefs, user_message)
        elif primary_intent == "create_transparent_canvas":
            return await self._handle_transparent_canvas_creation(
                media_files, output_prefs, user_message
            )
        elif primary_intent == "apply_alpha_mask":
            return await self._handle_alpha_mask_application(
                media_files, output_prefs, user_message
            )
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
            "🖼️ **Image Processing**\n"
            "- Resize and scale images\n"
            "- Crop images to specific areas\n"
            "- Rotate and flip images\n"
            "- Convert formats (PNG, JPEG, GIF, BMP)\n"
            "- Apply grayscale/black & white effects\n"
            "- Adjust brightness, contrast, and saturation\n"
            "- Apply blur, sharpen, and other filters\n"
            "- Batch process multiple images\n\n"
            "🧠 **Smart Context Features**\n"
            "- Remembers files from previous messages\n"
            "- Understands 'that video', 'this image', and 'that file'\n"
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
        response += "• 'Resize image.png to 1920x1080'\n"
        response += "• 'Crop that picture to 500x500'\n"
        response += "• 'Rotate photo.jpg by 90 degrees'\n"
        response += "• 'Convert image to grayscale'\n"
        response += "• 'Batch process all PNG files'\n"
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
        # Image processing intents
        elif primary_intent == "resize_image":
            return await self._handle_image_resize(media_files, output_prefs, user_message)
        elif primary_intent == "crop_image":
            return await self._handle_image_crop(media_files, output_prefs, user_message)
        elif primary_intent == "rotate_image":
            return await self._handle_image_rotate(media_files, output_prefs, user_message)
        elif primary_intent == "convert_image":
            return await self._handle_image_convert(media_files, output_prefs, user_message)
        elif primary_intent == "grayscale_image":
            return await self._handle_image_grayscale(media_files, output_prefs, user_message)
        elif primary_intent == "adjust_image":
            return await self._handle_image_adjust(media_files, output_prefs, user_message)
        elif primary_intent == "blur_image":
            return await self._handle_image_blur(media_files, output_prefs, user_message)
        elif primary_intent == "batch_process_images":
            return await self._handle_batch_image_processing(
                media_files, output_prefs, user_message
            )
        # Watermarking and transparency intents
        elif primary_intent == "apply_watermark":
            return await self._handle_watermark_application(media_files, output_prefs, user_message)
        elif primary_intent == "apply_text_watermark":
            return await self._handle_text_watermark_application(
                media_files, output_prefs, user_message
            )
        elif primary_intent == "remove_background":
            return await self._handle_background_removal(media_files, output_prefs, user_message)
        elif primary_intent == "create_transparent_canvas":
            return await self._handle_transparent_canvas_creation(
                media_files, output_prefs, user_message
            )
        elif primary_intent == "apply_alpha_mask":
            return await self._handle_alpha_mask_application(
                media_files, output_prefs, user_message
            )
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
            "🖼️ **Image Processing**\n"
            "- Resize and scale images\n"
            "- Crop images to specific areas\n"
            "- Rotate and flip images\n"
            "- Convert formats (PNG, JPEG, GIF, BMP)\n"
            "- Apply grayscale/black & white effects\n"
            "- Adjust brightness, contrast, and saturation\n"
            "- Apply blur, sharpen, and other filters\n"
            "- Batch process multiple images\n\n"
            "🧠 **Smart Context Features**\n"
            "- Remembers files from previous messages\n"
            "- Understands 'that video', 'this image', and 'that file'\n"
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
        response += "• 'Resize image.png to 1920x1080'\n"
        response += "• 'Crop that picture to 500x500'\n"
        response += "• 'Rotate photo.jpg by 90 degrees'\n"
        response += "• 'Convert image to grayscale'\n"
        response += "• 'Batch process all PNG files'\n"
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

    def _resolve_media_file(self, file_path: str) -> str:
        """
        Resolve media file path using universal file resolution system

        Args:
            file_path: File name or path to resolve

        Returns:
            Resolved path string if found, original path otherwise
        """
        # Use universal file resolution from BaseAgent
        resolved_path = self.resolve_file_path(file_path, agent_type="media")
        if resolved_path:
            return str(resolved_path)

        # Fallback to executor's file resolution for compatibility
        if hasattr(self.media_executor, "resolve_input_file"):
            resolved = self.media_executor.resolve_input_file(file_path)
            if resolved:
                return str(resolved)
        return file_path

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

        # ========================
        # IMAGE PROCESSING TOOLS
        # ========================

        # Resize image tool
        self.add_tool(
            AgentTool(
                name="resize_image",
                description="Resize image to specific dimensions",
                function=self._resize_image,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "input_image": {
                            "type": "string",
                            "description": "Path to input image file",
                        },
                        "width": {"type": "integer", "description": "Target width in pixels"},
                        "height": {"type": "integer", "description": "Target height in pixels"},
                    },
                    "required": ["input_image", "width", "height"],
                },
            )
        )

        # Crop image tool
        self.add_tool(
            AgentTool(
                name="crop_image",
                description="Crop image to specific area",
                function=self._crop_image,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "input_image": {
                            "type": "string",
                            "description": "Path to input image file",
                        },
                        "width": {"type": "integer", "description": "Crop width in pixels"},
                        "height": {"type": "integer", "description": "Crop height in pixels"},
                        "x": {"type": "integer", "description": "X offset for crop", "default": 0},
                        "y": {"type": "integer", "description": "Y offset for crop", "default": 0},
                        "position": {
                            "type": "string",
                            "enum": [
                                "center",
                                "top-left",
                                "top-right",
                                "bottom-left",
                                "bottom-right",
                            ],
                            "default": "center",
                        },
                    },
                    "required": ["input_image", "width", "height"],
                },
            )
        )

        # Rotate image tool
        self.add_tool(
            AgentTool(
                name="rotate_image",
                description="Rotate image by specified angle",
                function=self._rotate_image,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "input_image": {
                            "type": "string",
                            "description": "Path to input image file",
                        },
                        "angle": {
                            "type": "number",
                            "description": "Rotation angle in degrees (0-360)",
                        },
                    },
                    "required": ["input_image", "angle"],
                },
            )
        )

        # Convert image format tool
        self.add_tool(
            AgentTool(
                name="convert_image_format",
                description="Convert image to different format",
                function=self._convert_image_format,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "input_image": {
                            "type": "string",
                            "description": "Path to input image file",
                        },
                        "target_format": {
                            "type": "string",
                            "enum": ["png", "jpeg", "jpg", "gif", "bmp", "tiff", "webp"],
                            "description": "Target image format",
                        },
                    },
                    "required": ["input_image", "target_format"],
                },
            )
        )

        # Apply grayscale tool
        self.add_tool(
            AgentTool(
                name="apply_grayscale",
                description="Convert image to grayscale/black and white",
                function=self._apply_grayscale,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "input_image": {
                            "type": "string",
                            "description": "Path to input image file",
                        },
                    },
                    "required": ["input_image"],
                },
            )
        )

        # Adjust image properties tool
        self.add_tool(
            AgentTool(
                name="adjust_image_properties",
                description="Adjust image brightness, contrast, and saturation",
                function=self._adjust_image_properties,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "input_image": {
                            "type": "string",
                            "description": "Path to input image file",
                        },
                        "adjustments": {
                            "type": "object",
                            "properties": {
                                "brightness": {
                                    "type": "integer",
                                    "description": "Brightness adjustment (-100 to 100)",
                                },
                                "contrast": {
                                    "type": "integer",
                                    "description": "Contrast adjustment (0 to 300)",
                                },
                                "saturation": {
                                    "type": "integer",
                                    "description": "Saturation adjustment (0 to 300)",
                                },
                            },
                            "description": "Dictionary of adjustments to apply",
                        },
                    },
                    "required": ["input_image", "adjustments"],
                },
            )
        )

        # Apply blur/sharpen effect tool
        self.add_tool(
            AgentTool(
                name="apply_blur_effect",
                description="Apply blur or sharpen effect to image",
                function=self._apply_blur_effect,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "input_image": {
                            "type": "string",
                            "description": "Path to input image file",
                        },
                        "effect_params": {
                            "type": "object",
                            "properties": {
                                "type": {
                                    "type": "string",
                                    "enum": ["blur", "sharpen"],
                                    "description": "Type of effect to apply",
                                },
                                "intensity": {
                                    "type": "string",
                                    "enum": ["slight", "medium", "strong"],
                                    "description": "Effect intensity",
                                    "default": "medium",
                                },
                            },
                            "required": ["type"],
                            "description": "Effect parameters",
                        },
                    },
                    "required": ["input_image", "effect_params"],
                },
            )
        )

        # ========================
        # WATERMARKING AND TRANSPARENCY TOOLS
        # ========================

        # Apply image watermark tool
        self.add_tool(
            AgentTool(
                name="apply_image_watermark",
                description="Apply image watermark to another image",
                function=self._apply_image_watermark,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "input_image": {
                            "type": "string",
                            "description": "Path to input image file",
                        },
                        "watermark_image": {
                            "type": "string",
                            "description": "Path to watermark image file",
                        },
                        "position": {
                            "type": "string",
                            "enum": [
                                "top-left",
                                "top-right",
                                "bottom-left",
                                "bottom-right",
                                "center",
                            ],
                            "default": "bottom-right",
                            "description": "Position of watermark on image",
                        },
                        "opacity": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                            "default": 1.0,
                            "description": "Opacity of watermark (0.0 to 1.0)",
                        },
                        "scale": {
                            "type": "number",
                            "minimum": 0.1,
                            "maximum": 3.0,
                            "default": 1.0,
                            "description": "Scale factor for watermark size",
                        },
                        "margin": {
                            "type": "integer",
                            "minimum": 0,
                            "default": 10,
                            "description": "Margin from edge in pixels",
                        },
                    },
                    "required": ["input_image", "watermark_image"],
                },
            )
        )

        # Apply text watermark tool
        self.add_tool(
            AgentTool(
                name="apply_text_watermark",
                description="Apply text watermark to image",
                function=self._apply_text_watermark,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "input_image": {
                            "type": "string",
                            "description": "Path to input image file",
                        },
                        "text": {
                            "type": "string",
                            "description": "Text to apply as watermark",
                        },
                        "position": {
                            "type": "string",
                            "enum": [
                                "top-left",
                                "top-right",
                                "bottom-left",
                                "bottom-right",
                                "center",
                            ],
                            "default": "bottom-right",
                            "description": "Position of text watermark",
                        },
                        "font_size": {
                            "type": "integer",
                            "minimum": 8,
                            "maximum": 200,
                            "default": 24,
                            "description": "Font size in pixels",
                        },
                        "font_color": {
                            "type": "string",
                            "default": "white",
                            "description": "Font color (e.g., 'white', 'black', '#FF0000')",
                        },
                        "font_family": {
                            "type": "string",
                            "default": "Arial",
                            "description": "Font family name",
                        },
                        "opacity": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                            "default": 1.0,
                            "description": "Text opacity (0.0 to 1.0)",
                        },
                        "margin": {
                            "type": "integer",
                            "minimum": 0,
                            "default": 10,
                            "description": "Margin from edge in pixels",
                        },
                    },
                    "required": ["input_image", "text"],
                },
            )
        )

        # Remove background tool
        self.add_tool(
            AgentTool(
                name="remove_background",
                description="Remove background color from image and make it transparent",
                function=self._remove_background,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "input_image": {
                            "type": "string",
                            "description": "Path to input image file",
                        },
                        "background_color": {
                            "type": "string",
                            "default": "white",
                            "description": "Background color to remove (e.g., 'white', 'green', '#00FF00')",
                        },
                        "similarity": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                            "default": 0.3,
                            "description": "Color similarity threshold (0.0 to 1.0)",
                        },
                        "blend": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                            "default": 0.1,
                            "description": "Blend factor for edge smoothing (0.0 to 1.0)",
                        },
                    },
                    "required": ["input_image"],
                },
            )
        )

        # Create transparent canvas tool
        self.add_tool(
            AgentTool(
                name="create_transparent_canvas",
                description="Create a transparent canvas/background image",
                function=self._create_transparent_canvas,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "width": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 8000,
                            "description": "Canvas width in pixels",
                        },
                        "height": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 8000,
                            "description": "Canvas height in pixels",
                        },
                        "color": {
                            "type": "string",
                            "default": "transparent",
                            "description": "Canvas color (use 'transparent' for transparent canvas)",
                        },
                    },
                    "required": ["width", "height"],
                },
            )
        )

        # Apply alpha mask tool
        self.add_tool(
            AgentTool(
                name="apply_alpha_mask",
                description="Apply alpha mask to make parts of image transparent",
                function=self._apply_alpha_mask,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "input_image": {
                            "type": "string",
                            "description": "Path to input image file",
                        },
                        "mask_image": {
                            "type": "string",
                            "description": "Path to alpha mask image file",
                        },
                    },
                    "required": ["input_image", "mask_image"],
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
            # Resolve the input file path
            resolved_input = self._resolve_media_file(input_video)
            if not Path(resolved_input).exists():
                return {
                    "success": False,
                    "error": f"Input video file not found: {input_video}. Searched in docker_shared/input/media/ and current directory.",
                }

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
                input_files={"input_video": resolved_input},
                output_filename=output_filename,
            )

            if result["success"]:
                return {
                    "success": True,
                    "message": f"Audio extracted successfully to {output_format}",
                    "output_file": result.get("output_file", {}),
                    "input_video": resolved_input,
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

    # ========================
    # IMAGE PROCESSING CORE METHODS
    # ========================

    async def _resize_image(self, input_image: str, width: int, height: int):
        """Resize image using FFmpeg"""
        try:
            # Resolve the input file path
            resolved_input = self._resolve_media_file(input_image)
            if not Path(resolved_input).exists():
                return {
                    "success": False,
                    "error": f"Input image file not found: {input_image}. Searched in docker_shared/input/media/ and current directory.",
                }

            output_filename = f"resized_image_{int(time.time())}.png"

            # Use FFmpeg for image resizing - supports many formats
            ffmpeg_command = f"ffmpeg -y -i ${{input_image}} -vf scale={width}:{height} ${{OUTPUT}}"

            result = self.media_executor.execute_ffmpeg_command(
                ffmpeg_command=ffmpeg_command,
                input_files={"input_image": resolved_input},
                output_filename=output_filename,
            )

            if result["success"]:
                return {
                    "success": True,
                    "message": f"Image resized successfully to {width}x{height}",
                    "output_file": result.get("output_file", {}),
                    "input_image": resolved_input,
                    "execution_time": result["execution_time"],
                    "final_dimensions": f"{width}x{height}",
                }
            else:
                return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _crop_image(
        self,
        input_image: str,
        width: int,
        height: int,
        x: int = 0,
        y: int = 0,
        position: str = "center",
    ):
        """Crop image using FFmpeg"""
        try:
            resolved_input = self._resolve_media_file(input_image)
            if not Path(resolved_input).exists():
                return {"success": False, "error": f"Input image file not found: {input_image}"}

            output_filename = f"cropped_image_{int(time.time())}.png"

            # Calculate crop position if specified as position name
            if position == "center":
                # We'll let FFmpeg auto-center by using crop filter with just width:height
                ffmpeg_command = (
                    f"ffmpeg -y -i ${{input_image}} -vf crop={width}:{height} ${{OUTPUT}}"
                )
            else:
                # Use specific x,y coordinates
                ffmpeg_command = (
                    f"ffmpeg -y -i ${{input_image}} -vf crop={width}:{height}:{x}:{y} ${{OUTPUT}}"
                )

            result = self.media_executor.execute_ffmpeg_command(
                ffmpeg_command=ffmpeg_command,
                input_files={"input_image": resolved_input},
                output_filename=output_filename,
            )

            if result["success"]:
                return {
                    "success": True,
                    "message": f"Image cropped successfully to {width}x{height}",
                    "output_file": result.get("output_file", {}),
                    "input_image": resolved_input,
                    "execution_time": result["execution_time"],
                }
            else:
                return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _rotate_image(self, input_image: str, angle: float):
        """Rotate image using FFmpeg"""
        try:
            resolved_input = self._resolve_media_file(input_image)
            if not Path(resolved_input).exists():
                return {"success": False, "error": f"Input image file not found: {input_image}"}

            output_filename = f"rotated_image_{int(time.time())}.png"

            # Convert angle to FFmpeg rotation filter
            # FFmpeg rotate filter uses radians, but also has shortcuts for common angles
            if angle == 90:
                ffmpeg_command = f"ffmpeg -y -i ${{input_image}} -vf transpose=1 ${{OUTPUT}}"
            elif angle == 180:
                ffmpeg_command = (
                    f"ffmpeg -y -i ${{input_image}} -vf transpose=2,transpose=2 ${{OUTPUT}}"
                )
            elif angle == 270:
                ffmpeg_command = f"ffmpeg -y -i ${{input_image}} -vf transpose=2 ${{OUTPUT}}"
            else:
                # For arbitrary angles, use rotate filter (angle in radians)
                angle_rad = angle * 3.14159 / 180
                ffmpeg_command = f"ffmpeg -y -i ${{input_image}} -vf rotate={angle_rad} ${{OUTPUT}}"

            result = self.media_executor.execute_ffmpeg_command(
                ffmpeg_command=ffmpeg_command,
                input_files={"input_image": resolved_input},
                output_filename=output_filename,
            )

            if result["success"]:
                return {
                    "success": True,
                    "message": f"Image rotated successfully by {angle} degrees",
                    "output_file": result.get("output_file", {}),
                    "input_image": resolved_input,
                    "execution_time": result["execution_time"],
                }
            else:
                return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _convert_image_format(self, input_image: str, target_format: str):
        """Convert image format using FFmpeg"""
        try:
            resolved_input = self._resolve_media_file(input_image)
            if not Path(resolved_input).exists():
                return {"success": False, "error": f"Input image file not found: {input_image}"}

            # Map format names to file extensions
            format_extensions = {
                "png": "png",
                "jpeg": "jpg",
                "jpg": "jpg",
                "gif": "gif",
                "bmp": "bmp",
                "tiff": "tiff",
                "webp": "webp",
            }

            ext = format_extensions.get(target_format.lower(), target_format.lower())
            output_filename = f"converted_image_{int(time.time())}.{ext}"

            # FFmpeg automatically handles format conversion based on extension
            ffmpeg_command = f"ffmpeg -y -i ${{input_image}} ${{OUTPUT}}"

            result = self.media_executor.execute_ffmpeg_command(
                ffmpeg_command=ffmpeg_command,
                input_files={"input_image": resolved_input},
                output_filename=output_filename,
            )

            if result["success"]:
                return {
                    "success": True,
                    "message": f"Image converted successfully to {target_format.upper()}",
                    "output_file": result.get("output_file", {}),
                    "input_image": resolved_input,
                    "execution_time": result["execution_time"],
                }
            else:
                return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _apply_grayscale(self, input_image: str):
        """Convert image to grayscale using FFmpeg"""
        try:
            resolved_input = self._resolve_media_file(input_image)
            if not Path(resolved_input).exists():
                return {"success": False, "error": f"Input image file not found: {input_image}"}

            output_filename = f"grayscale_image_{int(time.time())}.png"

            # Apply grayscale filter
            ffmpeg_command = f"ffmpeg -y -i ${{input_image}} -vf format=gray ${{OUTPUT}}"

            result = self.media_executor.execute_ffmpeg_command(
                ffmpeg_command=ffmpeg_command,
                input_files={"input_image": resolved_input},
                output_filename=output_filename,
            )

            if result["success"]:
                return {
                    "success": True,
                    "message": f"Image converted to grayscale successfully",
                    "output_file": result.get("output_file", {}),
                    "input_image": resolved_input,
                    "execution_time": result["execution_time"],
                }
            else:
                return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _adjust_image_properties(self, input_image: str, adjustments: Dict[str, Any]):
        """Adjust image brightness, contrast, saturation using FFmpeg"""
        try:
            resolved_input = self._resolve_media_file(input_image)
            if not Path(resolved_input).exists():
                return {"success": False, "error": f"Input image file not found: {input_image}"}

            output_filename = f"adjusted_image_{int(time.time())}.png"

            # Build FFmpeg filter for adjustments
            filters = []

            if "brightness" in adjustments:
                # FFmpeg eq filter: brightness range -1.0 to 1.0
                brightness = (
                    float(adjustments["brightness"]) / 100.0
                )  # Convert percentage to decimal
                filters.append(f"eq=brightness={brightness}")

            if "contrast" in adjustments:
                # FFmpeg eq filter: contrast range 0.0 to 3.0 (1.0 = normal)
                contrast = float(adjustments["contrast"]) / 100.0
                filters.append(f"eq=contrast={contrast}")

            if "saturation" in adjustments:
                # FFmpeg eq filter: saturation range 0.0 to 3.0 (1.0 = normal)
                saturation = float(adjustments["saturation"]) / 100.0
                filters.append(f"eq=saturation={saturation}")

            if not filters:
                return {"success": False, "error": "No valid adjustments specified"}

            filter_string = ",".join(filters)
            ffmpeg_command = f"ffmpeg -y -i ${{input_image}} -vf {filter_string} ${{OUTPUT}}"

            result = self.media_executor.execute_ffmpeg_command(
                ffmpeg_command=ffmpeg_command,
                input_files={"input_image": resolved_input},
                output_filename=output_filename,
            )

            if result["success"]:
                return {
                    "success": True,
                    "message": f"Image adjusted successfully",
                    "output_file": result.get("output_file", {}),
                    "input_image": resolved_input,
                    "execution_time": result["execution_time"],
                    "adjustments": adjustments,
                }
            else:
                return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _apply_blur_effect(self, input_image: str, effect_params: Dict[str, Any]):
        """Apply blur or sharpen effect using FFmpeg"""
        try:
            resolved_input = self._resolve_media_file(input_image)
            if not Path(resolved_input).exists():
                return {"success": False, "error": f"Input image file not found: {input_image}"}

            output_filename = f"effect_image_{int(time.time())}.png"

            effect_type = effect_params.get("type", "blur")
            intensity = effect_params.get("intensity", "medium")

            # Map intensity to values
            intensity_map = {"slight": 1, "medium": 3, "strong": 5}
            radius = intensity_map.get(intensity, 3)

            if effect_type == "blur":
                # Gaussian blur filter
                ffmpeg_command = (
                    f"ffmpeg -y -i ${{input_image}} -vf gblur=sigma={radius} ${{OUTPUT}}"
                )
            elif effect_type == "sharpen":
                # Unsharp mask for sharpening
                ffmpeg_command = (
                    f"ffmpeg -y -i ${{input_image}} -vf unsharp=5:5:{radius} ${{OUTPUT}}"
                )
            else:
                return {"success": False, "error": f"Unknown effect type: {effect_type}"}

            result = self.media_executor.execute_ffmpeg_command(
                ffmpeg_command=ffmpeg_command,
                input_files={"input_image": resolved_input},
                output_filename=output_filename,
            )

            if result["success"]:
                return {
                    "success": True,
                    "message": f"{effect_type.title()} effect applied successfully",
                    "output_file": result.get("output_file", {}),
                    "input_image": resolved_input,
                    "execution_time": result["execution_time"],
                    "effect": effect_params,
                }
            else:
                return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _find_batch_images(self, pattern: str):
        """Find images matching a pattern for batch processing"""
        import glob

        # Search in multiple locations
        search_paths = [
            str(self.input_dir / pattern),
            str(Path.cwd() / pattern),
        ]

        found_images = []
        for search_path in search_paths:
            found_images.extend(glob.glob(search_path))

        # Filter for supported image formats
        image_extensions = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp"}
        filtered_images = [
            img for img in found_images if Path(img).suffix.lower() in image_extensions
        ]

        return filtered_images

    # ========================
    # WATERMARKING AND TRANSPARENCY METHODS
    # ========================

    async def _apply_image_watermark(
        self,
        input_image: str,
        watermark_image: str,
        position: str = "bottom-right",
        opacity: float = 1.0,
        scale: float = 1.0,
        margin: int = 10,
    ):
        """Apply image watermark to an image"""
        try:
            resolved_input = self._resolve_media_file(input_image)
            resolved_watermark = self._resolve_media_file(watermark_image)

            if not Path(resolved_input).exists():
                return {"success": False, "error": f"Input image not found: {input_image}"}
            if not Path(resolved_watermark).exists():
                return {"success": False, "error": f"Watermark image not found: {watermark_image}"}

            output_filename = f"watermarked_{int(time.time())}.png"

            # Position calculations
            position_map = {
                "top-left": f"{margin}:{margin}",
                "top-right": f"main_w-overlay_w-{margin}:{margin}",
                "bottom-left": f"{margin}:main_h-overlay_h-{margin}",
                "bottom-right": f"main_w-overlay_w-{margin}:main_h-overlay_h-{margin}",
                "center": "(main_w-overlay_w)/2:(main_h-overlay_h)/2",
            }

            pos = position_map.get(position, position_map["bottom-right"])

            # Build filter complex for watermark with scaling and opacity
            if scale != 1.0 or opacity != 1.0:
                # Scale watermark and adjust opacity
                scale_filter = f"scale=iw*{scale}:ih*{scale}"
                opacity_filter = f"format=rgba,colorchannelmixer=aa={opacity}"
                watermark_filter = f"[1]{scale_filter},{opacity_filter}[wm]"
                overlay_filter = f"[0][wm]overlay={pos}"
                filter_complex = f"{watermark_filter};{overlay_filter}"
            else:
                # Simple overlay
                filter_complex = f"overlay={pos}"

            ffmpeg_command = f"ffmpeg -y -i ${{input_image}} -i ${{watermark_image}} -filter_complex {filter_complex} ${{OUTPUT}}"

            result = self.media_executor.execute_ffmpeg_command(
                ffmpeg_command=ffmpeg_command,
                input_files={"input_image": resolved_input, "watermark_image": resolved_watermark},
                output_filename=output_filename,
            )

            if result["success"]:
                return {
                    "success": True,
                    "message": f"Image watermark applied successfully",
                    "output_file": result.get("output_file", {}),
                    "input_image": resolved_input,
                    "watermark_image": resolved_watermark,
                    "position": position,
                    "opacity": opacity,
                    "scale": scale,
                    "execution_time": result["execution_time"],
                }
            else:
                return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _apply_text_watermark(
        self,
        input_image: str,
        text: str,
        position: str = "bottom-right",
        font_size: int = 24,
        font_color: str = "white",
        background: bool = False,
        background_color: str = "black@0.5",
        margin: int = 10,
    ):
        """Apply text watermark to an image"""
        try:
            resolved_input = self._resolve_media_file(input_image)
            if not Path(resolved_input).exists():
                return {"success": False, "error": f"Input image not found: {input_image}"}

            output_filename = f"text_watermarked_{int(time.time())}.png"

            # Position calculations for text
            position_map = {
                "top-left": f"x={margin}:y={margin}",
                "top-right": f"x=w-tw-{margin}:y={margin}",
                "bottom-left": f"x={margin}:y=h-th-{margin}",
                "bottom-right": f"x=w-tw-{margin}:y=h-th-{margin}",
                "center": "x=(w-tw)/2:y=(h-th)/2",
            }

            pos = position_map.get(position, position_map["bottom-right"])

            # Build drawtext filter
            drawtext_params = [
                f"text='{text}'",
                f"fontsize={font_size}",
                f"fontcolor={font_color}",
                pos,
            ]

            if background:
                drawtext_params.extend(["box=1", f"boxcolor={background_color}", "boxborderw=5"])

            drawtext_filter = "drawtext=" + ":".join(drawtext_params)

            ffmpeg_command = f"ffmpeg -y -i ${{input_image}} -vf {drawtext_filter} ${{OUTPUT}}"

            result = self.media_executor.execute_ffmpeg_command(
                ffmpeg_command=ffmpeg_command,
                input_files={"input_image": resolved_input},
                output_filename=output_filename,
            )

            if result["success"]:
                return {
                    "success": True,
                    "message": f"Text watermark applied successfully",
                    "output_file": result.get("output_file", {}),
                    "input_image": resolved_input,
                    "watermark_text": text,
                    "position": position,
                    "font_size": font_size,
                    "font_color": font_color,
                    "execution_time": result["execution_time"],
                }
            else:
                return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _remove_background(
        self,
        input_image: str,
        background_color: str = "white",
        similarity: float = 0.3,
        blend: float = 0.1,
    ):
        """Remove background color and make it transparent"""
        try:
            resolved_input = self._resolve_media_file(input_image)
            if not Path(resolved_input).exists():
                return {"success": False, "error": f"Input image file not found: {input_image}"}

            output_filename = f"transparent_bg_{int(time.time())}.png"

            # Use chromakey filter to remove background
            ffmpeg_command = f"ffmpeg -y -i ${{input_image}} -vf chromakey={background_color}:similarity={similarity}:blend={blend} -pix_fmt rgba ${{OUTPUT}}"

            result = self.media_executor.execute_ffmpeg_command(
                ffmpeg_command=ffmpeg_command,
                input_files={"input_image": resolved_input},
                output_filename=output_filename,
            )

            if result["success"]:
                return {
                    "success": True,
                    "message": f"Background removed successfully",
                    "output_file": result.get("output_file", {}),
                    "input_image": resolved_input,
                    "background_color": background_color,
                    "similarity": similarity,
                    "execution_time": result["execution_time"],
                }
            else:
                return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _create_transparent_canvas(self, width: int, height: int, color: str = "transparent"):
        """Create a transparent canvas"""
        try:
            output_filename = f"transparent_canvas_{int(time.time())}.png"

            # Create transparent canvas
            ffmpeg_command = f"ffmpeg -y -f lavfi -i color=c={color}:size={width}x{height}:d=1 -frames:v 1 -pix_fmt rgba ${{OUTPUT}}"

            result = self.media_executor.execute_ffmpeg_command(
                ffmpeg_command=ffmpeg_command,
                input_files={},  # No input files needed
                output_filename=output_filename,
            )

            if result["success"]:
                return {
                    "success": True,
                    "message": f"Transparent canvas created successfully",
                    "output_file": result.get("output_file", {}),
                    "execution_time": result["execution_time"],
                    "dimensions": f"{width}x{height}",
                }
            else:
                return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _apply_alpha_mask(self, input_image: str, mask_image: str):
        """Apply an alpha mask to make parts transparent"""
        try:
            resolved_input = self._resolve_media_file(input_image)
            resolved_mask = self._resolve_media_file(mask_image)

            if not Path(resolved_input).exists():
                return {"success": False, "error": f"Input image not found: {input_image}"}
            if not Path(resolved_mask).exists():
                return {"success": False, "error": f"Mask image not found: {mask_image}"}

            output_filename = f"alpha_masked_{int(time.time())}.png"

            # Apply alpha mask
            ffmpeg_command = f"ffmpeg -y -i ${{input_image}} -i ${{mask_image}} -filter_complex [0][1]alphamerge -pix_fmt rgba ${{OUTPUT}}"

            result = self.media_executor.execute_ffmpeg_command(
                ffmpeg_command=ffmpeg_command,
                input_files={"input_image": resolved_input, "mask_image": resolved_mask},
                output_filename=output_filename,
            )

            if result["success"]:
                return {
                    "success": True,
                    "message": f"Alpha mask applied successfully",
                    "output_file": result.get("output_file", {}),
                    "input_image": resolved_input,
                    "mask_image": resolved_mask,
                    "execution_time": result["execution_time"],
                }
            else:
                return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========================
    # IMAGE PARSING HELPER METHODS
    # ========================

    def _parse_image_dimensions(self, dimensions: str, user_message: str) -> tuple:
        """Parse image dimensions from preferences or message"""
        if dimensions:
            dimensions_str = str(dimensions).lower().strip()
            if "x" in dimensions_str:
                try:
                    width, height = dimensions_str.split("x")
                    return int(width), int(height)
                except:
                    pass

        # Parse from user message
        import re

        # Look for WIDTHxHEIGHT pattern
        dimension_matches = re.findall(r"(\d{1,5})\s*[x×]\s*(\d{1,5})", user_message)
        if dimension_matches:
            width, height = dimension_matches[0]
            return int(width), int(height)

        # Look for percentage
        percent_match = re.search(r"(\d+)%", user_message)
        if percent_match:
            # Return special values to indicate percentage scaling
            percent = int(percent_match.group(1))
            return percent, percent  # Will be handled specially by caller

        return None, None

    def _parse_crop_parameters(self, user_message: str) -> Dict[str, Any]:
        """Parse crop parameters from user message"""
        import re

        # Look for dimensions
        dimension_matches = re.findall(r"(\d{1,5})\s*[x×]\s*(\d{1,5})", user_message)
        if not dimension_matches:
            return None

        width, height = map(int, dimension_matches[0])

        # Look for position
        position = "center"  # default
        if "top" in user_message.lower() and "left" in user_message.lower():
            position = "top-left"
        elif "top" in user_message.lower() and "right" in user_message.lower():
            position = "top-right"
        elif "bottom" in user_message.lower() and "left" in user_message.lower():
            position = "bottom-left"
        elif "bottom" in user_message.lower() and "right" in user_message.lower():
            position = "bottom-right"
        elif "center" in user_message.lower():
            position = "center"

        return {"width": width, "height": height, "position": position}

    def _parse_rotation_angle(self, user_message: str) -> Optional[float]:
        """Parse rotation angle from user message"""
        import re

        # Look for degree values
        degree_matches = re.findall(
            r"(\d+(?:\.\d+)?)\s*(?:degrees?|°)", user_message, re.IGNORECASE
        )
        if degree_matches:
            return float(degree_matches[0])

        # Look for common rotation terms
        message_lower = user_message.lower()
        if "90" in message_lower or "quarter" in message_lower:
            if "counter" in message_lower or "anti" in message_lower:
                return 270
            return 90
        elif "180" in message_lower or "half" in message_lower or "upside" in message_lower:
            return 180
        elif "270" in message_lower:
            return 270
        elif "clockwise" in message_lower:
            return 90
        elif "counter" in message_lower:
            return 270

        return None

    def _parse_image_format(self, user_message: str) -> Optional[str]:
        """Parse target image format from user message"""
        message_lower = user_message.lower()

        formats = ["png", "jpeg", "jpg", "gif", "bmp", "tiff", "webp"]
        for fmt in formats:
            if fmt in message_lower:
                return fmt

        return None

    def _parse_image_adjustments(self, user_message: str) -> Dict[str, Any]:
        """Parse image adjustment parameters from user message"""
        import re

        adjustments = {}
        message_lower = user_message.lower()

        # Parse brightness
        brightness_match = re.search(r"brightness.*?([+-]?\d+)%?", message_lower)
        if brightness_match:
            adjustments["brightness"] = int(brightness_match.group(1))
        elif "brighter" in message_lower:
            adjustments["brightness"] = 30
        elif "darker" in message_lower:
            adjustments["brightness"] = -30

        # Parse contrast
        contrast_match = re.search(r"contrast.*?(\d+)%?", message_lower)
        if contrast_match:
            adjustments["contrast"] = int(contrast_match.group(1))
        elif "more contrast" in message_lower:
            adjustments["contrast"] = 150
        elif "less contrast" in message_lower:
            adjustments["contrast"] = 70

        # Parse saturation
        saturation_match = re.search(r"saturat.*?(\d+)%?", message_lower)
        if saturation_match:
            adjustments["saturation"] = int(saturation_match.group(1))
        elif "more saturated" in message_lower:
            adjustments["saturation"] = 150
        elif "less saturated" in message_lower:
            adjustments["saturation"] = 70

        return adjustments

    def _parse_blur_parameters(self, user_message: str) -> Dict[str, Any]:
        """Parse blur/sharpen parameters from user message"""
        message_lower = user_message.lower()

        # Determine effect type
        if "sharpen" in message_lower:
            effect_type = "sharpen"
        elif "blur" in message_lower:
            effect_type = "blur"
        else:
            return None

        # Determine intensity
        intensity = "medium"  # default
        if "slight" in message_lower or "light" in message_lower:
            intensity = "slight"
        elif "strong" in message_lower or "heavy" in message_lower:
            intensity = "strong"
        elif "medium" in message_lower:
            intensity = "medium"

        return {"type": effect_type, "intensity": intensity}

    def _parse_batch_operation(self, user_message: str) -> Dict[str, Any]:
        """Parse batch operation from user message"""
        import re

        message_lower = user_message.lower()

        # Determine operation type
        operation = None
        if "resize" in message_lower:
            operation = "resize"
        elif "convert" in message_lower:
            operation = "convert"
        elif "grayscale" in message_lower or "gray" in message_lower:
            operation = "grayscale"
        else:
            return None

        result = {"operation": operation}

        # Parse file pattern
        if "*.png" in user_message or "png files" in message_lower:
            result["pattern"] = "*.png"
        elif (
            "*.jpg" in user_message or "jpeg files" in message_lower or "jpg files" in message_lower
        ):
            result["pattern"] = "*.jpg"
        elif "*.gif" in user_message or "gif files" in message_lower:
            result["pattern"] = "*.gif"
        else:
            result["pattern"] = "*.*"  # All files

        # Parse operation-specific parameters
        if operation == "resize":
            dimension_matches = re.findall(r"(\d{1,5})\s*[x×]\s*(\d{1,5})", user_message)
            if dimension_matches:
                result["width"], result["height"] = map(int, dimension_matches[0])

        elif operation == "convert":
            target_format = self._parse_image_format(user_message)
            if target_format:
                result["format"] = target_format

        return result

    def _parse_watermark_parameters(self, user_message: str) -> Dict[str, Any]:
        """Parse watermark parameters from user message"""
        import re

        params = {}
        message_lower = user_message.lower()

        # Parse position
        if "top" in message_lower and "left" in message_lower:
            params["position"] = "top-left"
        elif "top" in message_lower and "right" in message_lower:
            params["position"] = "top-right"
        elif "bottom" in message_lower and "left" in message_lower:
            params["position"] = "bottom-left"
        elif "bottom" in message_lower and "right" in message_lower:
            params["position"] = "bottom-right"
        elif "center" in message_lower:
            params["position"] = "center"
        else:
            params["position"] = "bottom-right"  # default

        # Parse opacity
        opacity_match = re.search(r"opacity[:\s]*(\d+)%?", message_lower)
        if opacity_match:
            opacity = int(opacity_match.group(1))
            params["opacity"] = opacity / 100.0 if opacity > 1 else opacity

        # Parse scale/size
        scale_match = re.search(r"(?:scale|size)[:\s]*(\d+)%?", message_lower)
        if scale_match:
            scale = int(scale_match.group(1))
            params["scale"] = scale / 100.0 if scale > 1 else scale

        # Parse text content (look for quoted text)
        text_match = re.search(r"['\"]([^'\"]+)['\"]", user_message)
        if text_match:
            params["text"] = text_match.group(1)

        # Parse font size
        size_match = re.search(r"(?:font[:\s]*)?size[:\s]*(\d+)", message_lower)
        if size_match:
            params["font_size"] = int(size_match.group(1))

        # Parse color
        color_match = re.search(r"color[:\s]*(\w+)", message_lower)
        if color_match:
            params["font_color"] = color_match.group(1)

        # Check for background box
        if "background" in message_lower or "box" in message_lower:
            params["background"] = True

        return params

    def _parse_transparency_parameters(self, user_message: str) -> Dict[str, Any]:
        """Parse transparency/background removal parameters from user message"""
        import re

        params = {}
        message_lower = user_message.lower()

        # Parse background color
        if "white" in message_lower:
            params["background_color"] = "white"
        elif "green" in message_lower:
            params["background_color"] = "green"
        elif "blue" in message_lower:
            params["background_color"] = "blue"
        elif "red" in message_lower:
            params["background_color"] = "red"
        elif "black" in message_lower:
            params["background_color"] = "black"
        else:
            params["background_color"] = "white"  # default

        # Parse similarity tolerance
        similarity_match = re.search(
            r"(?:similarity|tolerance)[:\s]*(\d+(?:\.\d+)?)%?", message_lower
        )
        if similarity_match:
            similarity = float(similarity_match.group(1))
            params["similarity"] = similarity / 100.0 if similarity > 1 else similarity

        # Parse blend amount
        blend_match = re.search(r"blend[:\s]*(\d+(?:\.\d+)?)%?", message_lower)
        if blend_match:
            blend = float(blend_match.group(1))
            params["blend"] = blend / 100.0 if blend > 1 else blend

        return params

    def _extract_watermark_text(self, user_message: str) -> str:
        """Extract watermark text from user message"""
        import re

        # Look for quoted text
        quoted_match = re.search(r'["\']([^"\']+)["\']', user_message)
        if quoted_match:
            return quoted_match.group(1)

        # Look for common watermark phrases
        copyright_match = re.search(r"©\s*\d{4}.*?(?:\s|$)", user_message)
        if copyright_match:
            return copyright_match.group(0).strip()

        # Look for "text:" pattern
        text_match = re.search(r"text:\s*([^,\n]+)", user_message, re.IGNORECASE)
        if text_match:
            return text_match.group(1).strip()

        # Look for common watermark words
        watermark_words = ["copyright", "confidential", "draft", "sample", "watermark"]
        for word in watermark_words:
            if word in user_message.lower():
                return word.upper()

        return None

    def _identify_watermark_files(
        self, user_message: str, media_files: List[str]
    ) -> Dict[str, str]:
        """Identify which file is the main image and which is the watermark"""
        result = {"main_image": None, "watermark_image": None}

        if len(media_files) >= 2:
            # Assume first file is main image, second is watermark
            result["main_image"] = media_files[0]
            result["watermark_image"] = media_files[1]
        elif len(media_files) == 1:
            result["main_image"] = media_files[0]

            # Look for watermark file mentions
            message_lower = user_message.lower()
            watermark_indicators = ["watermark", "logo", "stamp", "mark"]

            for indicator in watermark_indicators:
                if indicator in message_lower:
                    # Try to extract watermark filename
                    import re

                    # Look for filename patterns near watermark indicators
                    pattern = rf"{indicator}\s*[:\s]*([a-zA-Z0-9_.-]+\.(png|jpg|jpeg|gif|bmp))"
                    match = re.search(pattern, message_lower)
                    if match:
                        result["watermark_image"] = match.group(1)
                        break

        return result

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
        self, message: Union[str, AgentMessage], context: ExecutionContext = None
    ) -> AsyncIterator[StreamChunk]:
        """Stream processing for MediaEditorAgent - COMPLETE IMPLEMENTATION"""

        # Handle both string and AgentMessage inputs
        if isinstance(message, AgentMessage):
            user_message = message.content
            original_message = message
        else:
            user_message = str(message)
            original_message = AgentMessage(
                id=str(uuid.uuid4()),
                sender_id=context.user_id if context else self.context.user_id,
                recipient_id=self.agent_id,
                content=user_message,
                message_type=MessageType.USER_INPUT,
                timestamp=datetime.now(),
            )

        self.memory.store_message(original_message)

        try:
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
                "conversation_id": original_message.conversation_id,
                "streaming": True,
                "user_id": original_message.sender_id,
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

    # ========================
    # IMAGE PROCESSING HANDLERS
    # ========================

    async def _handle_image_resize(
        self, image_files: List[str], output_prefs: Dict[str, Any], user_message: str
    ) -> str:
        """Handle image resizing with FFmpeg"""

        if not image_files:
            recent_file = self.get_recent_media_file()
            if recent_file:
                return f"I can resize images. Did you mean to resize **{recent_file}**? Please specify dimensions."
            else:
                return (
                    "I can resize images! Please provide:\n\n"
                    "**1. Image file path**\n"
                    "**2. Target dimensions**\n\n"
                    "**Examples:**\n"
                    "• 'Resize image.png to 800x600'\n"
                    "• 'Scale photo.jpg to 1920x1080'\n"
                    "• 'Resize picture to 50% size'"
                )

        input_file = image_files[0]
        dimensions = output_prefs.get("dimensions")

        # Parse dimensions from user message or preferences
        width, height = self._parse_image_dimensions(dimensions, user_message)

        if not width or not height:
            return (
                f"I need specific dimensions to resize **{input_file}**.\n\n"
                f"**Please specify:**\n"
                f"• Exact dimensions: '800x600', '1920x1080'\n"
                f"• Percentage: '50%', '200%'\n\n"
                f"**Example:** 'Resize {input_file} to 800x600'"
            )

        try:
            result = await self._resize_image(input_file, width, height)

            if result["success"]:
                return (
                    f"✅ **Image Resize Completed**\n\n"
                    f"📁 **Input:** {input_file}\n"
                    f"🖼️ **Output:** {result.get('output_file', {}).get('filename', 'Unknown')}\n"
                    f"📏 **Dimensions:** {width}x{height}\n"
                    f"⏱️ **Time:** {result.get('execution_time', 0):.2f}s\n"
                    f"📊 **Size:** {result.get('output_file', {}).get('size_bytes', 0) // 1024}KB\n\n"
                    f"Your resized image is ready! 🎉"
                )
            else:
                return f"❌ **Image resize failed:** {result.get('error', 'Unknown error')}"

        except Exception as e:
            return f"❌ **Error during image resize:** {str(e)}"

    async def _handle_image_crop(
        self, image_files: List[str], output_prefs: Dict[str, Any], user_message: str
    ) -> str:
        """Handle image cropping"""

        if not image_files:
            recent_file = self.get_recent_media_file()
            if recent_file:
                return f"I can crop images. Did you mean to crop **{recent_file}**? Please specify crop area."
            else:
                return (
                    "I can crop images! Please provide:\n\n"
                    "**1. Image file path**\n"
                    "**2. Crop dimensions and position**\n\n"
                    "**Examples:**\n"
                    "• 'Crop image.png to 500x500 from center'\n"
                    "• 'Crop photo.jpg 800x600 from top-left'\n"
                    "• 'Crop to square 400x400'"
                )

        input_file = image_files[0]

        # Parse crop parameters from user message
        crop_params = self._parse_crop_parameters(user_message)

        if not crop_params:
            return (
                f"I need crop specifications for **{input_file}**.\n\n"
                f"**Please specify:**\n"
                f"• Size: '500x500', '800x600'\n"
                f"• Position: 'center', 'top-left', 'bottom-right'\n\n"
                f"**Example:** 'Crop {input_file} to 500x500 from center'"
            )

        try:
            result = await self._crop_image(input_file, **crop_params)

            if result["success"]:
                return (
                    f"✅ **Image Crop Completed**\n\n"
                    f"📁 **Input:** {input_file}\n"
                    f"✂️ **Output:** {result.get('output_file', {}).get('filename', 'Unknown')}\n"
                    f"📏 **Crop Area:** {crop_params.get('width')}x{crop_params.get('height')}\n"
                    f"📍 **Position:** {crop_params.get('position', 'center')}\n"
                    f"⏱️ **Time:** {result.get('execution_time', 0):.2f}s\n\n"
                    f"Your cropped image is ready! 🎉"
                )
            else:
                return f"❌ **Image crop failed:** {result.get('error', 'Unknown error')}"

        except Exception as e:
            return f"❌ **Error during image crop:** {str(e)}"

    async def _handle_image_rotate(
        self, image_files: List[str], output_prefs: Dict[str, Any], user_message: str
    ) -> str:
        """Handle image rotation"""

        if not image_files:
            recent_file = self.get_recent_media_file()
            if recent_file:
                return f"I can rotate images. Did you mean to rotate **{recent_file}**? Please specify rotation angle."
            else:
                return (
                    "I can rotate images! Please provide:\n\n"
                    "**1. Image file path**\n"
                    "**2. Rotation angle**\n\n"
                    "**Examples:**\n"
                    "• 'Rotate image.png by 90 degrees'\n"
                    "• 'Turn photo.jpg 180 degrees'\n"
                    "• 'Flip picture clockwise'"
                )

        input_file = image_files[0]

        # Parse rotation angle from user message
        angle = self._parse_rotation_angle(user_message)

        if angle is None:
            return (
                f"I need a rotation angle for **{input_file}**.\n\n"
                f"**Please specify:**\n"
                f"• Degrees: '90', '180', '270', '45'\n"
                f"• Direction: 'clockwise', 'counterclockwise'\n\n"
                f"**Example:** 'Rotate {input_file} by 90 degrees'"
            )

        try:
            result = await self._rotate_image(input_file, angle)

            if result["success"]:
                return (
                    f"✅ **Image Rotation Completed**\n\n"
                    f"📁 **Input:** {input_file}\n"
                    f"🔄 **Output:** {result.get('output_file', {}).get('filename', 'Unknown')}\n"
                    f"📐 **Rotation:** {angle}°\n"
                    f"⏱️ **Time:** {result.get('execution_time', 0):.2f}s\n\n"
                    f"Your rotated image is ready! 🎉"
                )
            else:
                return f"❌ **Image rotation failed:** {result.get('error', 'Unknown error')}"

        except Exception as e:
            return f"❌ **Error during image rotation:** {str(e)}"

    async def _handle_image_convert(
        self, image_files: List[str], output_prefs: Dict[str, Any], user_message: str
    ) -> str:
        """Handle image format conversion"""

        if not image_files:
            recent_file = self.get_recent_media_file()
            if recent_file:
                return f"I can convert image formats. Did you mean to convert **{recent_file}**? Please specify target format."
            else:
                return (
                    "I can convert image formats! Please provide:\n\n"
                    "**1. Image file path**\n"
                    "**2. Target format**\n\n"
                    "**Supported formats:** PNG, JPEG, GIF, BMP, TIFF, WEBP\n\n"
                    "**Examples:**\n"
                    "• 'Convert image.png to JPEG'\n"
                    "• 'Change photo.jpg to PNG'"
                )

        input_file = image_files[0]

        # Parse target format from user message or preferences
        target_format = output_prefs.get("format") or self._parse_image_format(user_message)

        if not target_format:
            return (
                f"I need a target format to convert **{input_file}**.\n\n"
                f"**Supported formats:**\n"
                f"• PNG (best quality, larger size)\n"
                f"• JPEG (good quality, smaller size)\n"
                f"• GIF (animations, limited colors)\n"
                f"• BMP (uncompressed)\n"
                f"• WEBP (modern, efficient)\n\n"
                f"**Example:** 'Convert {input_file} to PNG'"
            )

        try:
            result = await self._convert_image_format(input_file, target_format)

            if result["success"]:
                return (
                    f"✅ **Image Format Conversion Completed**\n\n"
                    f"📁 **Input:** {input_file}\n"
                    f"🔄 **Output:** {result.get('output_file', {}).get('filename', 'Unknown')}\n"
                    f"📊 **Format:** {target_format.upper()}\n"
                    f"⏱️ **Time:** {result.get('execution_time', 0):.2f}s\n"
                    f"📁 **Size:** {result.get('output_file', {}).get('size_bytes', 0) // 1024}KB\n\n"
                    f"Your converted image is ready! 🎉"
                )
            else:
                return (
                    f"❌ **Image format conversion failed:** {result.get('error', 'Unknown error')}"
                )

        except Exception as e:
            return f"❌ **Error during image format conversion:** {str(e)}"

    async def _handle_image_grayscale(
        self, image_files: List[str], output_prefs: Dict[str, Any], user_message: str
    ) -> str:
        """Handle grayscale conversion"""

        if not image_files:
            recent_file = self.get_recent_media_file()
            if recent_file:
                return f"I can convert images to grayscale. Did you mean to convert **{recent_file}** to black and white?"
            else:
                return (
                    "I can convert images to grayscale! Please provide an image file path.\n\n"
                    "**Example:** 'Convert image.png to grayscale'"
                )

        input_file = image_files[0]

        try:
            result = await self._apply_grayscale(input_file)

            if result["success"]:
                return (
                    f"✅ **Grayscale Conversion Completed**\n\n"
                    f"📁 **Input:** {input_file}\n"
                    f"⚫ **Output:** {result.get('output_file', {}).get('filename', 'Unknown')}\n"
                    f"🎨 **Effect:** Black & White\n"
                    f"⏱️ **Time:** {result.get('execution_time', 0):.2f}s\n\n"
                    f"Your grayscale image is ready! 🎉"
                )
            else:
                return f"❌ **Grayscale conversion failed:** {result.get('error', 'Unknown error')}"

        except Exception as e:
            return f"❌ **Error during grayscale conversion:** {str(e)}"

    async def _handle_image_adjust(
        self, image_files: List[str], output_prefs: Dict[str, Any], user_message: str
    ) -> str:
        """Handle image adjustments (brightness, contrast, saturation)"""

        if not image_files:
            recent_file = self.get_recent_media_file()
            if recent_file:
                return f"I can adjust image properties. Did you mean to adjust **{recent_file}**? Please specify what to adjust."
            else:
                return (
                    "I can adjust image properties! Please provide:\n\n"
                    "**1. Image file path**\n"
                    "**2. Adjustment type and value**\n\n"
                    "**Examples:**\n"
                    "• 'Increase brightness of image.png by 20%'\n"
                    "• 'Adjust contrast to 150%'\n"
                    "• 'Make photo.jpg more saturated'"
                )

        input_file = image_files[0]

        # Parse adjustment parameters from user message
        adjustments = self._parse_image_adjustments(user_message)

        if not adjustments:
            return (
                f"I need adjustment specifications for **{input_file}**.\n\n"
                f"**Available adjustments:**\n"
                f"• Brightness: 'brightness +20%', 'brighter'\n"
                f"• Contrast: 'contrast 150%', 'more contrast'\n"
                f"• Saturation: 'saturation 80%', 'less saturated'\n\n"
                f"**Example:** 'Increase brightness of {input_file} by 30%'"
            )

        try:
            result = await self._adjust_image_properties(input_file, adjustments)

            if result["success"]:
                adj_desc = ", ".join([f"{k}: {v}" for k, v in adjustments.items()])
                return (
                    f"✅ **Image Adjustment Completed**\n\n"
                    f"📁 **Input:** {input_file}\n"
                    f"🎨 **Output:** {result.get('output_file', {}).get('filename', 'Unknown')}\n"
                    f"⚙️ **Adjustments:** {adj_desc}\n"
                    f"⏱️ **Time:** {result.get('execution_time', 0):.2f}s\n\n"
                    f"Your adjusted image is ready! 🎉"
                )
            else:
                return f"❌ **Image adjustment failed:** {result.get('error', 'Unknown error')}"

        except Exception as e:
            return f"❌ **Error during image adjustment:** {str(e)}"

    async def _handle_image_blur(
        self, image_files: List[str], output_prefs: Dict[str, Any], user_message: str
    ) -> str:
        """Handle image blur/sharpen effects"""

        if not image_files:
            recent_file = self.get_recent_media_file()
            if recent_file:
                return f"I can apply blur/sharpen effects. Did you mean to modify **{recent_file}**? Please specify the effect."
            else:
                return (
                    "I can apply blur and sharpen effects! Please provide:\n\n"
                    "**1. Image file path**\n"
                    "**2. Effect type and intensity**\n\n"
                    "**Examples:**\n"
                    "• 'Blur image.png slightly'\n"
                    "• 'Sharpen photo.jpg'\n"
                    "• 'Apply gaussian blur with radius 5'"
                )

        input_file = image_files[0]

        # Parse blur/sharpen parameters from user message
        effect_params = self._parse_blur_parameters(user_message)

        if not effect_params:
            return (
                f"I need effect specifications for **{input_file}**.\n\n"
                f"**Available effects:**\n"
                f"• Blur: 'blur', 'gaussian blur', 'soft blur'\n"
                f"• Sharpen: 'sharpen', 'enhance sharpness'\n"
                f"• Intensity: 'slight', 'medium', 'strong', or radius value\n\n"
                f"**Example:** 'Apply medium blur to {input_file}'"
            )

        try:
            result = await self._apply_blur_effect(input_file, effect_params)

            if result["success"]:
                effect_desc = f"{effect_params.get('type', 'blur')} (intensity: {effect_params.get('intensity', 'medium')})"
                return (
                    f"✅ **Image Effect Applied**\n\n"
                    f"📁 **Input:** {input_file}\n"
                    f"✨ **Output:** {result.get('output_file', {}).get('filename', 'Unknown')}\n"
                    f"🎭 **Effect:** {effect_desc}\n"
                    f"⏱️ **Time:** {result.get('execution_time', 0):.2f}s\n\n"
                    f"Your processed image is ready! 🎉"
                )
            else:
                return f"❌ **Image effect failed:** {result.get('error', 'Unknown error')}"

        except Exception as e:
            return f"❌ **Error during image effect processing:** {str(e)}"

    async def _handle_batch_image_processing(
        self, image_files: List[str], output_prefs: Dict[str, Any], user_message: str
    ) -> str:
        """Handle batch processing of multiple images"""

        # Parse batch operation from user message
        batch_operation = self._parse_batch_operation(user_message)

        if not batch_operation:
            return (
                "I can batch process multiple images! Please specify:\n\n"
                "**1. Operation type**\n"
                "**2. File pattern or folder**\n\n"
                "**Examples:**\n"
                "• 'Resize all PNG files to 800x600'\n"
                "• 'Convert all JPEG files to PNG'\n"
                "• 'Apply grayscale to all images in folder'\n"
                "• 'Batch resize *.jpg to 50% size'"
            )

        try:
            # Find images to process
            images_to_process = await self._find_batch_images(
                batch_operation.get("pattern", "*.png")
            )

            if not images_to_process:
                return (
                    f"❌ **No images found** matching pattern: {batch_operation.get('pattern', 'N/A')}\n\n"
                    f"**Searched in:**\n"
                    f"• docker_shared/input/media/\n"
                    f"• Current directory\n\n"
                    f"**Supported formats:** PNG, JPEG, GIF, BMP, TIFF"
                )

            # Process each image
            results = []
            failed_count = 0

            for i, image_file in enumerate(images_to_process):
                try:
                    if batch_operation["operation"] == "resize":
                        result = await self._resize_image(
                            image_file, batch_operation["width"], batch_operation["height"]
                        )
                    elif batch_operation["operation"] == "convert":
                        result = await self._convert_image_format(
                            image_file, batch_operation["format"]
                        )
                    elif batch_operation["operation"] == "grayscale":
                        result = await self._apply_grayscale(image_file)
                    else:
                        continue

                    if result["success"]:
                        results.append(f"✅ {Path(image_file).name}")
                    else:
                        results.append(f"❌ {Path(image_file).name}")
                        failed_count += 1

                except Exception:
                    results.append(f"❌ {Path(image_file).name}")
                    failed_count += 1

            success_count = len(images_to_process) - failed_count

            return (
                f"✅ **Batch Processing Completed**\n\n"
                f"📊 **Results:** {success_count}/{len(images_to_process)} successful\n"
                f"⚙️ **Operation:** {batch_operation['operation']}\n"
                f"📁 **Processed files:**\n"
                + "\n".join(results[:10])
                + (f"\n... and {len(results) - 10} more" if len(results) > 10 else "")
                + f"\n\n🎉 Batch processing complete!"
            )

        except Exception as e:
            return f"❌ **Error during batch processing:** {str(e)}"

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
                "image_resizing",
                "image_cropping",
                "image_rotation",
                "image_format_conversion",
                "grayscale_conversion",
                "image_adjustments",
                "blur_sharpen_effects",
                "batch_image_processing",
                "image_watermarking",
                "text_watermarking",
                "background_removal",
                "transparent_canvas_creation",
                "alpha_mask_application",
                "context_awareness",
                "ffmpeg_processing",
                "docker_execution",
                "streaming_responses",
            ],
        }


# ========================
# WATERMARKING AND TRANSPARENCY HANDLERS
# ========================


async def _handle_watermark_application(
    self, image_files: List[str], output_prefs: Dict[str, Any], user_message: str
) -> str:
    """Handle image watermarking requests"""

    # Parse watermark parameters from user message
    watermark_params = self._parse_watermark_parameters(user_message)

    if not watermark_params:
        return (
            "I can apply image watermarks! Please specify:\n\n"
            "**1. Source image to watermark**\n"
            "**2. Watermark image file**\n"
            "**3. Position (optional)**\n\n"
            "**Examples:**\n"
            "• 'Add logo.png watermark to photo.jpg at bottom-right'\n"
            "• 'Apply watermark.png to image.jpg with 70% opacity'\n"
            "• 'Watermark photo.jpg with logo.png at top-left corner'"
        )

    try:
        # Get input image
        if not image_files:
            recent_file = self.get_recent_media_file()
            if recent_file:
                input_image = recent_file
            else:
                return "❌ **No image specified.** Please provide an image file to watermark."
        else:
            input_image = image_files[0]

        # Get watermark image from parameters
        watermark_image = watermark_params.get("watermark_file")
        if not watermark_image:
            return "❌ **No watermark image specified.** Please provide a watermark image file."

        # Apply image watermark
        result = await self._apply_image_watermark(
            input_image=input_image,
            watermark_image=watermark_image,
            position=watermark_params.get("position", "bottom-right"),
            opacity=watermark_params.get("opacity", 1.0),
            scale=watermark_params.get("scale", 1.0),
            margin=watermark_params.get("margin", 10),
        )

        if result["success"]:
            return (
                f"✅ **Watermark Applied Successfully!**\n\n"
                f"📁 **Source:** {input_image}\n"
                f"🖼️ **Watermark:** {watermark_image}\n"
                f"📍 **Position:** {watermark_params.get('position', 'bottom-right')}\n"
                f"🎨 **Opacity:** {watermark_params.get('opacity', 1.0)*100:.0f}%\n"
                f"📏 **Scale:** {watermark_params.get('scale', 1.0)*100:.0f}%\n"
                f"💾 **Output:** {result['output_file']}\n"
                f"⏱️ **Time:** {result.get('execution_time', 'N/A')}\n\n"
                f"Your watermarked image is ready! 🎉"
            )
        else:
            return f"❌ **Watermark application failed:** {result.get('error', 'Unknown error')}"

    except Exception as e:
        return f"❌ **Error during watermark application:** {str(e)}"


async def _handle_text_watermark_application(
    self, image_files: List[str], output_prefs: Dict[str, Any], user_message: str
) -> str:
    """Handle text watermarking requests"""

    # Parse text watermark parameters from user message
    watermark_text = self._extract_watermark_text(user_message)
    watermark_params = self._parse_watermark_parameters(user_message)

    if not watermark_text:
        return (
            "I can add text watermarks! Please specify:\n\n"
            "**1. Source image**\n"
            "**2. Text to add**\n"
            "**3. Position (optional)**\n\n"
            "**Examples:**\n"
            "• 'Add text watermark \"Copyright 2024\" to photo.jpg'\n"
            "• 'Apply \"DRAFT\" text watermark at top-left of image.png'\n"
            "• 'Watermark photo.jpg with text \"My Company\" at bottom center'"
        )

    try:
        # Get input image
        if not image_files:
            recent_file = self.get_recent_media_file()
            if recent_file:
                input_image = recent_file
            else:
                return "❌ **No image specified.** Please provide an image file to watermark."
        else:
            input_image = image_files[0]

        # Apply text watermark
        result = await self._apply_text_watermark(
            input_image=input_image,
            text=watermark_text,
            position=watermark_params.get("position", "bottom-right"),
            font_size=watermark_params.get("font_size", 24),
            font_color=watermark_params.get("font_color", "white"),
            font_family=watermark_params.get("font_family", "Arial"),
            opacity=watermark_params.get("opacity", 1.0),
            margin=watermark_params.get("margin", 10),
        )

        if result["success"]:
            return (
                f"✅ **Text Watermark Applied Successfully!**\n\n"
                f"📁 **Source:** {input_image}\n"
                f"📝 **Text:** {watermark_text}\n"
                f"📍 **Position:** {watermark_params.get('position', 'bottom-right')}\n"
                f"🎨 **Color:** {watermark_params.get('font_color', 'white')}\n"
                f"📏 **Size:** {watermark_params.get('font_size', 24)}px\n"
                f"💾 **Output:** {result['output_file']}\n"
                f"⏱️ **Time:** {result.get('execution_time', 'N/A')}\n\n"
                f"Your text watermarked image is ready! 🎉"
            )
        else:
            return (
                f"❌ **Text watermark application failed:** {result.get('error', 'Unknown error')}"
            )

    except Exception as e:
        return f"❌ **Error during text watermark application:** {str(e)}"


async def _handle_background_removal(
    self, image_files: List[str], output_prefs: Dict[str, Any], user_message: str
) -> str:
    """Handle background removal requests"""

    # Parse transparency parameters from user message
    transparency_params = self._parse_transparency_parameters(user_message)

    try:
        # Get input image
        if not image_files:
            recent_file = self.get_recent_media_file()
            if recent_file:
                input_image = recent_file
            else:
                return "❌ **No image specified.** Please provide an image file for background removal."
        else:
            input_image = image_files[0]

        # Remove background
        result = await self._remove_background(
            input_image=input_image,
            background_color=transparency_params.get("background_color", "white"),
            similarity=transparency_params.get("similarity", 0.3),
            blend=transparency_params.get("blend", 0.1),
        )

        if result["success"]:
            return (
                f"✅ **Background Removed Successfully!**\n\n"
                f"📁 **Source:** {input_image}\n"
                f"🎨 **Background Color:** {transparency_params.get('background_color', 'white')}\n"
                f"🎯 **Similarity:** {transparency_params.get('similarity', 0.3)*100:.0f}%\n"
                f"🌀 **Blend:** {transparency_params.get('blend', 0.1)*100:.0f}%\n"
                f"💾 **Output:** {result['output_file']}\n"
                f"⏱️ **Time:** {result.get('execution_time', 'N/A')}\n\n"
                f"Your transparent image is ready! 🎉"
            )
        else:
            return f"❌ **Background removal failed:** {result.get('error', 'Unknown error')}"

    except Exception as e:
        return f"❌ **Error during background removal:** {str(e)}"


async def _handle_transparent_canvas_creation(
    self, image_files: List[str], output_prefs: Dict[str, Any], user_message: str
) -> str:
    """Handle transparent canvas creation requests"""

    # Parse dimensions from user message
    dimensions = self._parse_image_dimensions(output_prefs, user_message)

    if not dimensions or not all(dimensions):
        return (
            "I can create transparent canvases! Please specify dimensions:\n\n"
            "**Examples:**\n"
            "• 'Create a transparent canvas 800x600'\n"
            "• 'Make a blank transparent image 1920x1080'\n"
            "• 'Generate empty transparent canvas 500x500'"
        )

    try:
        width, height = dimensions

        # Create transparent canvas
        result = await self._create_transparent_canvas(
            width=width, height=height, color="transparent"
        )

        if result["success"]:
            return (
                f"✅ **Transparent Canvas Created Successfully!**\n\n"
                f"📏 **Dimensions:** {width}x{height}\n"
                f"🎨 **Type:** Transparent RGBA\n"
                f"💾 **Output:** {result['output_file']}\n"
                f"⏱️ **Time:** {result.get('execution_time', 'N/A')}\n\n"
                f"Your transparent canvas is ready! 🎉"
            )
        else:
            return (
                f"❌ **Transparent canvas creation failed:** {result.get('error', 'Unknown error')}"
            )

    except Exception as e:
        return f"❌ **Error during transparent canvas creation:** {str(e)}"


async def _handle_alpha_mask_application(
    self, image_files: List[str], output_prefs: Dict[str, Any], user_message: str
) -> str:
    """Handle alpha mask application requests"""

    # Parse mask parameters from user message
    mask_files = self._identify_watermark_files(user_message, file_type="mask")

    if not mask_files:
        return (
            "I can apply alpha masks! Please specify:\n\n"
            "**1. Source image**\n"
            "**2. Mask image file**\n\n"
            "**Examples:**\n"
            "• 'Apply mask.png to photo.jpg'\n"
            "• 'Use alpha_mask.png on image.jpg'\n"
            "• 'Apply transparency mask shape.png to picture.jpg'"
        )

    try:
        # Get input image
        if not image_files:
            recent_file = self.get_recent_media_file()
            if recent_file:
                input_image = recent_file
            else:
                return "❌ **No image specified.** Please provide an image file for alpha mask application."
        else:
            input_image = image_files[0]

        # Get mask image
        mask_image = mask_files[0]

        # Apply alpha mask
        result = await self._apply_alpha_mask(input_image=input_image, mask_image=mask_image)

        if result["success"]:
            return (
                f"✅ **Alpha Mask Applied Successfully!**\n\n"
                f"📁 **Source:** {input_image}\n"
                f"🎭 **Mask:** {mask_image}\n"
                f"💾 **Output:** {result['output_file']}\n"
                f"⏱️ **Time:** {result.get('execution_time', 'N/A')}\n\n"
                f"Your masked image is ready! 🎉"
            )
        else:
            return f"❌ **Alpha mask application failed:** {result.get('error', 'Unknown error')}"

    except Exception as e:
        return f"❌ **Error during alpha mask application:** {str(e)}"
