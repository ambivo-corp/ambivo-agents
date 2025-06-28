# ambivo_agents/agents/media_editor.py
"""
Media Editor Agent with FFmpeg Integration
Handles audio/video processing using Docker containers with ffmpeg
"""

import asyncio
import json
import uuid
import time
import tempfile
import shutil
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta

from ..core.base import BaseAgent, AgentRole, AgentMessage, MessageType, ExecutionContext, AgentTool
from ..config.loader import load_config, get_config_section
from ..executors.media_executor import MediaDockerExecutor


class MediaEditorAgent(BaseAgent):
    """Media Editor Agent for audio/video processing using FFmpeg"""

    def __init__(self, agent_id: str| None = None, memory_manager=None, llm_service=None, **kwargs):
        if agent_id is None:
            agent_id = f"media_editor_{str(uuid.uuid4())[:8]}"

        super().__init__(
            agent_id=agent_id,
            role=AgentRole.CODE_EXECUTOR,  # Using CODE_EXECUTOR role for media processing
            memory_manager=memory_manager,
            llm_service=llm_service,
            name="Media Editor Agent",
            description="Agent for audio/video processing, transcoding, and editing using FFmpeg",
            **kwargs
        )

        # Load media configuration from YAML
        try:
            config = load_config()
            self.media_config = get_config_section('media_editor', config)
        except Exception as e:
            raise ValueError(f"media_editor configuration not found in agent_config.yaml: {e}")

        # Initialize media Docker executor
        self.media_executor = MediaDockerExecutor(self.media_config)

        # Add media processing tools
        self._add_media_tools()

    def _add_media_tools(self):
        """Add all media processing tools"""

        # Extract audio from video
        self.add_tool(AgentTool(
            name="extract_audio_from_video",
            description="Extract audio track from video file",
            function=self._extract_audio_from_video,
            parameters_schema={
                "type": "object",
                "properties": {
                    "input_video": {"type": "string", "description": "Path to input video file"},
                    "output_format": {"type": "string", "enum": ["mp3", "wav", "aac", "flac"], "default": "mp3"},
                    "audio_quality": {"type": "string", "enum": ["high", "medium", "low"], "default": "medium"}
                },
                "required": ["input_video"]
            }
        ))

        # Convert video format
        self.add_tool(AgentTool(
            name="convert_video_format",
            description="Convert video to different format/codec",
            function=self._convert_video_format,
            parameters_schema={
                "type": "object",
                "properties": {
                    "input_video": {"type": "string", "description": "Path to input video file"},
                    "output_format": {"type": "string", "enum": ["mp4", "avi", "mov", "mkv", "webm"], "default": "mp4"},
                    "video_codec": {"type": "string", "enum": ["h264", "h265", "vp9", "copy"], "default": "h264"},
                    "audio_codec": {"type": "string", "enum": ["aac", "mp3", "opus", "copy"], "default": "aac"},
                    "crf": {"type": "integer", "minimum": 0, "maximum": 51, "default": 23}
                },
                "required": ["input_video"]
            }
        ))

        # Resize video
        self.add_tool(AgentTool(
            name="resize_video",
            description="Resize video to specific dimensions",
            function=self._resize_video,
            parameters_schema={
                "type": "object",
                "properties": {
                    "input_video": {"type": "string", "description": "Path to input video file"},
                    "width": {"type": "integer", "description": "Target width in pixels"},
                    "height": {"type": "integer", "description": "Target height in pixels"},
                    "maintain_aspect": {"type": "boolean", "default": True},
                    "preset": {"type": "string", "enum": ["720p", "1080p", "4k", "480p", "custom"], "default": "custom"}
                },
                "required": ["input_video"]
            }
        ))

        # Get media information
        self.add_tool(AgentTool(
            name="get_media_info",
            description="Get detailed information about media file",
            function=self._get_media_info,
            parameters_schema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to media file"}
                },
                "required": ["file_path"]
            }
        ))

        # Trim media
        self.add_tool(AgentTool(
            name="trim_media",
            description="Trim/cut media file to specific time range",
            function=self._trim_media,
            parameters_schema={
                "type": "object",
                "properties": {
                    "input_file": {"type": "string", "description": "Path to input media file"},
                    "start_time": {"type": "string", "description": "Start time (HH:MM:SS or seconds)"},
                    "duration": {"type": "string", "description": "Duration (HH:MM:SS or seconds)"},
                    "end_time": {"type": "string", "description": "End time (alternative to duration)"}
                },
                "required": ["input_file", "start_time"]
            }
        ))

        # Create video thumbnail
        self.add_tool(AgentTool(
            name="create_video_thumbnail",
            description="Extract thumbnail/frame from video",
            function=self._create_video_thumbnail,
            parameters_schema={
                "type": "object",
                "properties": {
                    "input_video": {"type": "string", "description": "Path to input video file"},
                    "timestamp": {"type": "string", "description": "Time to extract frame (HH:MM:SS)",
                                  "default": "00:00:05"},
                    "output_format": {"type": "string", "enum": ["jpg", "png", "bmp"], "default": "jpg"},
                    "width": {"type": "integer", "description": "Thumbnail width", "default": 320}
                },
                "required": ["input_video"]
            }
        ))

        # Merge audio and video
        self.add_tool(AgentTool(
            name="merge_audio_video",
            description="Combine separate audio and video files",
            function=self._merge_audio_video,
            parameters_schema={
                "type": "object",
                "properties": {
                    "video_file": {"type": "string", "description": "Path to video file"},
                    "audio_file": {"type": "string", "description": "Path to audio file"},
                    "output_format": {"type": "string", "enum": ["mp4", "mkv", "avi"], "default": "mp4"}
                },
                "required": ["video_file", "audio_file"]
            }
        ))

        # Adjust audio volume
        self.add_tool(AgentTool(
            name="adjust_audio_volume",
            description="Adjust audio volume/gain",
            function=self._adjust_audio_volume,
            parameters_schema={
                "type": "object",
                "properties": {
                    "input_file": {"type": "string", "description": "Path to audio/video file"},
                    "volume_change": {"type": "string", "description": "Volume change (+10dB, -5dB, 0.5, 2.0)"},
                    "normalize": {"type": "boolean", "description": "Normalize audio levels", "default": False}
                },
                "required": ["input_file", "volume_change"]
            }
        ))

        # Convert audio format
        self.add_tool(AgentTool(
            name="convert_audio_format",
            description="Convert audio to different format",
            function=self._convert_audio_format,
            parameters_schema={
                "type": "object",
                "properties": {
                    "input_audio": {"type": "string", "description": "Path to input audio file"},
                    "output_format": {"type": "string", "enum": ["mp3", "wav", "aac", "flac", "ogg"], "default": "mp3"},
                    "bitrate": {"type": "string", "description": "Audio bitrate (128k, 192k, 320k)", "default": "192k"},
                    "sample_rate": {"type": "integer", "description": "Sample rate (44100, 48000)", "default": 44100}
                },
                "required": ["input_audio"]
            }
        ))

    async def _extract_audio_from_video(self, input_video: str, output_format: str = "mp3",
                                        audio_quality: str = "medium") -> Dict[str, Any]:
        """Extract audio from video file"""
        try:
            if not Path(input_video).exists():
                return {"success": False, "error": f"Input video file not found: {input_video}"}

            # Quality settings
            quality_settings = {
                "low": "-b:a 128k",
                "medium": "-b:a 192k",
                "high": "-b:a 320k"
            }

            output_filename = f"extracted_audio_{int(time.time())}.{output_format}"

            ffmpeg_command = (
                f"ffmpeg -i ${{input_video}} "
                f"{quality_settings.get(audio_quality, quality_settings['medium'])} "
                f"-vn -acodec {self._get_audio_codec(output_format)} "
                f"${{OUTPUT}}"
            )

            result = self.media_executor.execute_ffmpeg_command(
                ffmpeg_command=ffmpeg_command,
                input_files={'input_video': input_video},
                output_filename=output_filename
            )

            if result['success']:
                return {
                    "success": True,
                    "message": f"Audio extracted successfully to {output_format}",
                    "output_file": result['output_file'],
                    "input_video": input_video,
                    "execution_time": result['execution_time']
                }
            else:
                return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _convert_video_format(self, input_video: str, output_format: str = "mp4",
                                    video_codec: str = "h264", audio_codec: str = "aac",
                                    crf: int = 23) -> Dict[str, Any]:
        """Convert video to different format"""
        try:
            if not Path(input_video).exists():
                return {"success": False, "error": f"Input video file not found: {input_video}"}

            output_filename = f"converted_video_{int(time.time())}.{output_format}"

            # Build codec parameters
            video_params = f"-c:v {video_codec}" if video_codec != "copy" else "-c:v copy"
            audio_params = f"-c:a {audio_codec}" if audio_codec != "copy" else "-c:a copy"

            if video_codec in ["h264", "h265"] and video_codec != "copy":
                video_params += f" -crf {crf}"

            ffmpeg_command = (
                f"ffmpeg -i ${{input_video}} "
                f"{video_params} {audio_params} "
                f"-preset medium "
                f"${{OUTPUT}}"
            )

            result = self.media_executor.execute_ffmpeg_command(
                ffmpeg_command=ffmpeg_command,
                input_files={'input_video': input_video},
                output_filename=output_filename
            )

            if result['success']:
                return {
                    "success": True,
                    "message": f"Video converted successfully to {output_format}",
                    "output_file": result['output_file'],
                    "input_video": input_video,
                    "conversion_settings": {
                        "output_format": output_format,
                        "video_codec": video_codec,
                        "audio_codec": audio_codec,
                        "crf": crf
                    },
                    "execution_time": result['execution_time']
                }
            else:
                return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _resize_video(self, input_video: str, width: int = None, height: int = None,
                            maintain_aspect: bool = True, preset: str = "custom") -> Dict[str, Any]:
        """Resize video to specific dimensions"""
        try:
            if not Path(input_video).exists():
                return {"success": False, "error": f"Input video file not found: {input_video}"}

            # Handle presets
            if preset != "custom":
                preset_dimensions = {
                    "480p": (854, 480),
                    "720p": (1280, 720),
                    "1080p": (1920, 1080),
                    "4k": (3840, 2160)
                }
                if preset in preset_dimensions:
                    width, height = preset_dimensions[preset]

            if not width or not height:
                return {"success": False, "error": "Width and height must be specified"}

            output_filename = f"resized_video_{width}x{height}_{int(time.time())}.mp4"

            # Scale filter with aspect ratio handling
            if maintain_aspect:
                scale_filter = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
            else:
                scale_filter = f"scale={width}:{height}"

            ffmpeg_command = (
                f"ffmpeg -i ${{input_video}} "
                f"-vf \"{scale_filter}\" "
                f"-c:a copy "
                f"${{OUTPUT}}"
            )

            result = self.media_executor.execute_ffmpeg_command(
                ffmpeg_command=ffmpeg_command,
                input_files={'input_video': input_video},
                output_filename=output_filename
            )

            if result['success']:
                return {
                    "success": True,
                    "message": f"Video resized successfully to {width}x{height}",
                    "output_file": result['output_file'],
                    "input_video": input_video,
                    "resize_settings": {
                        "width": width,
                        "height": height,
                        "maintain_aspect": maintain_aspect,
                        "preset": preset
                    },
                    "execution_time": result['execution_time']
                }
            else:
                return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _get_media_info(self, file_path: str) -> Dict[str, Any]:
        """Get detailed media file information"""
        try:
            result = self.media_executor.get_media_info(file_path)

            if result['success']:
                return {
                    "success": True,
                    "message": "Media information retrieved successfully",
                    "file_path": file_path,
                    "media_info": result.get('media_info', {}),
                    "raw_output": result.get('raw_output', '')
                }
            else:
                return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _trim_media(self, input_file: str, start_time: str,
                          duration: str = None, end_time: str = None) -> Dict[str, Any]:
        """Trim media file to specific time range"""
        try:
            if not Path(input_file).exists():
                return {"success": False, "error": f"Input file not found: {input_file}"}

            if not duration and not end_time:
                return {"success": False, "error": "Either duration or end_time must be specified"}

            file_ext = Path(input_file).suffix
            output_filename = f"trimmed_media_{int(time.time())}{file_ext}"

            # Build time parameters
            time_params = f"-ss {start_time}"
            if duration:
                time_params += f" -t {duration}"
            elif end_time:
                time_params += f" -to {end_time}"

            ffmpeg_command = (
                f"ffmpeg -i ${{input_file}} "
                f"{time_params} "
                f"-c copy "
                f"${{OUTPUT}}"
            )

            result = self.media_executor.execute_ffmpeg_command(
                ffmpeg_command=ffmpeg_command,
                input_files={'input_file': input_file},
                output_filename=output_filename
            )

            if result['success']:
                return {
                    "success": True,
                    "message": f"Media trimmed successfully",
                    "output_file": result['output_file'],
                    "input_file": input_file,
                    "trim_settings": {
                        "start_time": start_time,
                        "duration": duration,
                        "end_time": end_time
                    },
                    "execution_time": result['execution_time']
                }
            else:
                return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _create_video_thumbnail(self, input_video: str, timestamp: str = "00:00:05",
                                      output_format: str = "jpg", width: int = 320) -> Dict[str, Any]:
        """Create thumbnail from video"""
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
                input_files={'input_video': input_video},
                output_filename=output_filename
            )

            if result['success']:
                return {
                    "success": True,
                    "message": f"Thumbnail created successfully",
                    "output_file": result['output_file'],
                    "input_video": input_video,
                    "thumbnail_settings": {
                        "timestamp": timestamp,
                        "output_format": output_format,
                        "width": width
                    },
                    "execution_time": result['execution_time']
                }
            else:
                return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _merge_audio_video(self, video_file: str, audio_file: str,
                                 output_format: str = "mp4") -> Dict[str, Any]:
        """Merge separate audio and video files"""
        try:
            if not Path(video_file).exists():
                return {"success": False, "error": f"Video file not found: {video_file}"}
            if not Path(audio_file).exists():
                return {"success": False, "error": f"Audio file not found: {audio_file}"}

            output_filename = f"merged_av_{int(time.time())}.{output_format}"

            ffmpeg_command = (
                f"ffmpeg -i ${{video_file}} -i ${{audio_file}} "
                f"-c:v copy -c:a aac "
                f"-shortest "
                f"${{OUTPUT}}"
            )

            result = self.media_executor.execute_ffmpeg_command(
                ffmpeg_command=ffmpeg_command,
                input_files={'video_file': video_file, 'audio_file': audio_file},
                output_filename=output_filename
            )

            if result['success']:
                return {
                    "success": True,
                    "message": f"Audio and video merged successfully",
                    "output_file": result['output_file'],
                    "input_files": {
                        "video": video_file,
                        "audio": audio_file
                    },
                    "execution_time": result['execution_time']
                }
            else:
                return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _adjust_audio_volume(self, input_file: str, volume_change: str,
                                   normalize: bool = False) -> Dict[str, Any]:
        """Adjust audio volume"""
        try:
            if not Path(input_file).exists():
                return {"success": False, "error": f"Input file not found: {input_file}"}

            file_ext = Path(input_file).suffix
            output_filename = f"volume_adjusted_{int(time.time())}{file_ext}"

            # Build audio filter
            if normalize:
                audio_filter = f"loudnorm,volume={volume_change}"
            else:
                audio_filter = f"volume={volume_change}"

            ffmpeg_command = (
                f"ffmpeg -i ${{input_file}} "
                f"-af \"{audio_filter}\" "
                f"-c:v copy "
                f"${{OUTPUT}}"
            )

            result = self.media_executor.execute_ffmpeg_command(
                ffmpeg_command=ffmpeg_command,
                input_files={'input_file': input_file},
                output_filename=output_filename
            )

            if result['success']:
                return {
                    "success": True,
                    "message": f"Audio volume adjusted successfully",
                    "output_file": result['output_file'],
                    "input_file": input_file,
                    "volume_settings": {
                        "volume_change": volume_change,
                        "normalize": normalize
                    },
                    "execution_time": result['execution_time']
                }
            else:
                return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _convert_audio_format(self, input_audio: str, output_format: str = "mp3",
                                    bitrate: str = "192k", sample_rate: int = 44100) -> Dict[str, Any]:
        """Convert audio to different format"""
        try:
            if not Path(input_audio).exists():
                return {"success": False, "error": f"Input audio file not found: {input_audio}"}

            output_filename = f"converted_audio_{int(time.time())}.{output_format}"

            audio_codec = self._get_audio_codec(output_format)

            ffmpeg_command = (
                f"ffmpeg -i ${{input_audio}} "
                f"-acodec {audio_codec} "
                f"-ab {bitrate} "
                f"-ar {sample_rate} "
                f"${{OUTPUT}}"
            )

            result = self.media_executor.execute_ffmpeg_command(
                ffmpeg_command=ffmpeg_command,
                input_files={'input_audio': input_audio},
                output_filename=output_filename
            )

            if result['success']:
                return {
                    "success": True,
                    "message": f"Audio converted successfully to {output_format}",
                    "output_file": result['output_file'],
                    "input_audio": input_audio,
                    "conversion_settings": {
                        "output_format": output_format,
                        "bitrate": bitrate,
                        "sample_rate": sample_rate,
                        "codec": audio_codec
                    },
                    "execution_time": result['execution_time']
                }
            else:
                return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _get_audio_codec(self, format: str) -> str:
        """Get appropriate audio codec for format"""
        codec_map = {
            "mp3": "libmp3lame",
            "aac": "aac",
            "wav": "pcm_s16le",
            "flac": "flac",
            "ogg": "libvorbis",
            "opus": "libopus"
        }
        return codec_map.get(format, "aac")

    async def process_message(self, message: AgentMessage, context: ExecutionContext) -> AgentMessage:
        """Process incoming message and route to appropriate media operations"""
        self.memory.store_message(message)

        try:
            content = message.content.lower()
            user_message = message.content

            # Determine the appropriate action based on message content
            if any(keyword in content for keyword in ['extract audio', 'audio from video', 'extract sound']):
                response_content = await self._handle_audio_extraction_request(user_message, context)
            elif any(keyword in content for keyword in ['convert video', 'transcode', 'change format']):
                response_content = await self._handle_video_conversion_request(user_message, context)
            elif any(keyword in content for keyword in ['resize video', 'scale video', 'change size']):
                response_content = await self._handle_video_resize_request(user_message, context)
            elif any(keyword in content for keyword in ['trim', 'cut', 'clip', 'extract clip']):
                response_content = await self._handle_media_trim_request(user_message, context)
            elif any(keyword in content for keyword in ['thumbnail', 'screenshot', 'frame']):
                response_content = await self._handle_thumbnail_request(user_message, context)
            elif any(keyword in content for keyword in ['merge', 'combine', 'join']):
                response_content = await self._handle_merge_request(user_message, context)
            elif any(keyword in content for keyword in ['volume', 'loud', 'quiet', 'audio level']):
                response_content = await self._handle_volume_request(user_message, context)
            elif any(keyword in content for keyword in ['info', 'details', 'properties', 'metadata']):
                response_content = await self._handle_info_request(user_message, context)
            else:
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
                content=f"Media Editor Agent error: {str(e)}",
                recipient_id=message.sender_id,
                message_type=MessageType.ERROR,
                session_id=message.session_id,
                conversation_id=message.conversation_id
            )
            return error_response

    async def _handle_audio_extraction_request(self, user_message: str, context: ExecutionContext) -> str:
        """Handle audio extraction requests"""
        return ("I can extract audio from video files. Please provide:\n\n"
                "1. Path to the video file\n"
                "2. Desired audio format (mp3, wav, aac, flac)\n"
                "3. Audio quality (high, medium, low)\n\n"
                "Example: 'Extract audio from /path/to/video.mp4 as high quality mp3'")

    async def _handle_video_conversion_request(self, user_message: str, context: ExecutionContext) -> str:
        """Handle video conversion requests"""
        return ("I can convert videos to different formats. Please specify:\n\n"
                "1. Input video file path\n"
                "2. Target format (mp4, avi, mov, mkv, webm)\n"
                "3. Video codec (h264, h265, vp9)\n"
                "4. Audio codec (aac, mp3, opus)\n"
                "5. Quality (CRF value 0-51, lower = better)\n\n"
                "Example: 'Convert /path/to/video.avi to mp4 with h264 codec'")

    async def _handle_video_resize_request(self, user_message: str, context: ExecutionContext) -> str:
        """Handle video resize requests"""
        return ("I can resize videos to different dimensions. Please provide:\n\n"
                "1. Input video file path\n"
                "2. Target dimensions (width x height) or preset (720p, 1080p, 4k)\n"
                "3. Whether to maintain aspect ratio\n\n"
                "Example: 'Resize /path/to/video.mp4 to 1280x720' or 'Resize video to 720p'")

    async def _handle_media_trim_request(self, user_message: str, context: ExecutionContext) -> str:
        """Handle media trimming requests"""
        return ("I can trim/cut media files. Please specify:\n\n"
                "1. Input file path\n"
                "2. Start time (HH:MM:SS format)\n"
                "3. Duration or end time\n\n"
                "Example: 'Trim /path/to/video.mp4 from 00:01:30 for 30 seconds'")

    async def _handle_thumbnail_request(self, user_message: str, context: ExecutionContext) -> str:
        """Handle thumbnail creation requests"""
        return ("I can create thumbnails from videos. Please provide:\n\n"
                "1. Input video file path\n"
                "2. Timestamp for thumbnail (HH:MM:SS)\n"
                "3. Output format (jpg, png, bmp)\n"
                "4. Thumbnail width (optional)\n\n"
                "Example: 'Create thumbnail from /path/to/video.mp4 at 00:05:00'")

    async def _handle_merge_request(self, user_message: str, context: ExecutionContext) -> str:
        """Handle audio/video merge requests"""
        return ("I can merge separate audio and video files. Please provide:\n\n"
                "1. Video file path\n"
                "2. Audio file path\n"
                "3. Output format (mp4, mkv, avi)\n\n"
                "Example: 'Merge /path/to/video.mp4 with /path/to/audio.mp3'")

    async def _handle_volume_request(self, user_message: str, context: ExecutionContext) -> str:
        """Handle volume adjustment requests"""
        return ("I can adjust audio volume. Please specify:\n\n"
                "1. Input file path (audio or video)\n"
                "2. Volume change (+10dB, -5dB, 0.5, 2.0)\n"
                "3. Whether to normalize audio levels\n\n"
                "Example: 'Increase volume of /path/to/audio.mp3 by +5dB'")

    async def _handle_info_request(self, user_message: str, context: ExecutionContext) -> str:
        """Handle media info requests"""
        return ("I can provide detailed information about media files. Please provide:\n\n"
                "1. Path to the media file\n\n"
                "I'll show you format, duration, codecs, resolution, bitrate, and other metadata.\n\n"
                "Example: 'Get info for /path/to/media.mp4'")

    async def _handle_general_request(self, user_message: str, context: ExecutionContext) -> str:
        """Handle general media processing requests"""
        if self.llm_service:
            prompt = f"""
            You are a Media Editor Agent specialized in audio/video processing using FFmpeg.

            Your capabilities include:
            - Extracting audio from video files
            - Converting video/audio formats and codecs
            - Resizing and scaling videos
            - Trimming/cutting media files
            - Creating thumbnails and extracting frames
            - Merging audio and video files
            - Adjusting audio volume and levels
            - Getting detailed media file information
            - Processing various formats (MP4, AVI, MOV, MP3, WAV, etc.)

            User message: {user_message}

            Provide a helpful response about how you can assist with their media processing needs.
            """

            response = await self.llm_service.generate_response(prompt, context.metadata)
            return response
        else:
            return ("I'm your Media Editor Agent! I can help you with:\n\n"
                    "🎥 **Video Processing**\n"
                    "- Convert between formats (MP4, AVI, MOV, MKV, WebM)\n"
                    "- Resize and scale videos\n"
                    "- Extract thumbnails and frames\n"
                    "- Trim and cut video clips\n\n"
                    "🎵 **Audio Processing**\n"
                    "- Extract audio from videos\n"
                    "- Convert audio formats (MP3, WAV, AAC, FLAC)\n"
                    "- Adjust volume and normalize levels\n"
                    "- Merge audio with video\n\n"
                    "📊 **Media Analysis**\n"
                    "- Get detailed media information\n"
                    "- Check codecs, resolution, and bitrates\n"
                    "- Analyze file properties\n\n"
                    "⚙️ **Advanced Features**\n"
                    "- Custom FFmpeg processing\n"
                    "- Batch operations\n"
                    "- Quality optimization\n\n"
                    "How can I help you process your media files today?")