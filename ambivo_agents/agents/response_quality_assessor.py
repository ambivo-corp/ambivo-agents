"""
Response Quality Assessor Agent

This agent assesses the quality of responses from various sources (knowledge base, web search, web scraping)
and determines if the response is sufficient or if additional sources need to be consulted.
"""

import asyncio
import json
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

from ambivo_agents.core import BaseAgent, AgentContext, AgentSession
from ambivo_agents.core.memory import RedisMemoryManager
from ambivo_agents.core.llm import MultiProviderLLMService


class ResponseSource(Enum):
    """Sources of information for responses"""
    KNOWLEDGE_BASE = "knowledge_base"
    WEB_SEARCH = "web_search"
    WEB_SCRAPE = "web_scrape"
    COMBINED = "combined"
    NONE = "none"


class QualityLevel(Enum):
    """Response quality levels"""
    EXCELLENT = "excellent"      # Comprehensive, accurate, well-sourced
    GOOD = "good"                # Adequate, mostly complete
    FAIR = "fair"                # Partial answer, may need enhancement
    POOR = "poor"                # Insufficient or unclear
    UNACCEPTABLE = "unacceptable"  # No useful information


@dataclass
class ResponseAssessment:
    """Assessment result for a response"""
    quality_level: QualityLevel
    confidence_score: float  # 0.0 to 1.0
    sources_used: List[ResponseSource]
    strengths: List[str]
    weaknesses: List[str]
    recommendations: List[str]
    needs_additional_sources: bool
    suggested_sources: List[ResponseSource]
    final_response: str
    metadata: Dict[str, Any]


@dataclass
class SourceResponse:
    """Response from a specific source"""
    source: ResponseSource
    content: str
    confidence: float
    metadata: Dict[str, Any]


class ResponseQualityAssessor(BaseAgent):
    """
    Agent that assesses response quality from various sources and determines 
    if additional information gathering is needed.
    """
    
    DEFAULT_SYSTEM_MESSAGE = """You are a Response Quality Assessment specialist. Your role is to:
1. Evaluate responses from various sources (knowledge base, web search, web scraping)
2. Assess completeness, accuracy, and relevance of responses
3. Identify strengths and weaknesses in the responses
4. Recommend whether additional sources should be consulted
5. Synthesize multiple responses into a comprehensive final answer

Quality Assessment Criteria:
- Relevance: How well does the response address the user's question?
- Completeness: Are all aspects of the question answered?
- Accuracy: Is the information factually correct and up-to-date?
- Clarity: Is the response clear and easy to understand?
- Sources: Are responses properly sourced and credible?
- Depth: Does the response provide sufficient detail?

Quality Levels:
- EXCELLENT: Comprehensive, accurate, well-sourced, fully addresses the question
- GOOD: Adequate response with minor gaps, mostly complete
- FAIR: Partial answer, some important aspects missing
- POOR: Insufficient information, major gaps or inaccuracies
- UNACCEPTABLE: No useful information or completely off-topic

When assessing, be thorough but fair. Consider the context and complexity of the question."""
    
    def __init__(
        self,
        agent_id: str,
        memory_manager: RedisMemoryManager,
        llm_service: MultiProviderLLMService,
        context: Optional[AgentContext] = None,
        system_message: Optional[str] = None,
        **config
    ):
        super().__init__(
            agent_id=agent_id,
            memory_manager=memory_manager,
            llm_service=llm_service,
            context=context,
            system_message=system_message or self.DEFAULT_SYSTEM_MESSAGE,
            **config
        )
        
        self.quality_thresholds = config.get('quality_thresholds', {
            'excellent': 0.9,
            'good': 0.75,
            'fair': 0.6,
            'poor': 0.4
        })
        
        self.source_weights = config.get('source_weights', {
            ResponseSource.KNOWLEDGE_BASE: 0.9,  # High trust for curated knowledge
            ResponseSource.WEB_SEARCH: 0.7,      # Good for current info
            ResponseSource.WEB_SCRAPE: 0.8,      # Direct source content
            ResponseSource.COMBINED: 1.0         # Highest when combined
        })
    
    async def assess_response(
        self,
        question: str,
        responses: List[SourceResponse],
        user_preferences: Optional[Dict[str, Any]] = None
    ) -> ResponseAssessment:
        """
        Assess the quality of responses from various sources.
        
        Args:
            question: The original user question
            responses: List of responses from different sources
            user_preferences: Optional user preferences (e.g., prioritize web search)
            
        Returns:
            ResponseAssessment with quality analysis and recommendations
        """
        # Build assessment prompt
        assessment_prompt = self._build_assessment_prompt(question, responses, user_preferences)
        
        # Get LLM assessment
        llm_response = await self.llm_service.generate_response(
            prompt=assessment_prompt,
            system_message=self.system_message
        )
        
        # Parse assessment
        assessment_data = self._parse_assessment(llm_response)
        
        # Calculate final confidence score
        confidence_score = self._calculate_confidence(responses, assessment_data)
        
        # Determine quality level
        quality_level = self._determine_quality_level(confidence_score)
        
        # Generate final synthesized response - always generate for meaningful responses
        final_response = ""
        if quality_level in [QualityLevel.EXCELLENT, QualityLevel.GOOD, QualityLevel.FAIR]:
            final_response = await self._synthesize_response(question, responses, assessment_data)
        elif responses:
            # Fallback: use the best available response even for poor quality
            best_response = max(responses, key=lambda r: r.confidence)
            final_response = best_response.content
        else:
            final_response = "I couldn't find sufficient information to answer your question."
        
        # Determine if additional sources needed
        needs_additional = quality_level in [QualityLevel.POOR, QualityLevel.UNACCEPTABLE, QualityLevel.FAIR]
        
        # Suggest additional sources
        suggested_sources = self._suggest_additional_sources(responses, assessment_data)
        
        return ResponseAssessment(
            quality_level=quality_level,
            confidence_score=confidence_score,
            sources_used=[r.source for r in responses],
            strengths=assessment_data.get('strengths', []),
            weaknesses=assessment_data.get('weaknesses', []),
            recommendations=assessment_data.get('recommendations', []),
            needs_additional_sources=needs_additional,
            suggested_sources=suggested_sources,
            final_response=final_response,
            metadata={
                'assessment_data': assessment_data,
                'user_preferences': user_preferences or {},
                'response_count': len(responses)
            }
        )
    
    def _build_assessment_prompt(
        self,
        question: str,
        responses: List[SourceResponse],
        user_preferences: Optional[Dict[str, Any]]
    ) -> str:
        """Build the assessment prompt for the LLM"""
        prompt = f"Please assess the quality of the following responses to the user's question.\n\n"
        prompt += f"USER QUESTION: {question}\n\n"
        
        if user_preferences:
            prompt += f"USER PREFERENCES: {json.dumps(user_preferences)}\n\n"
        
        prompt += "RESPONSES FROM SOURCES:\n"
        for i, response in enumerate(responses, 1):
            prompt += f"\n{i}. Source: {response.source.value}\n"
            prompt += f"   Confidence: {response.confidence:.2f}\n"
            prompt += f"   Content: {response.content[:1000]}...\n" if len(response.content) > 1000 else f"   Content: {response.content}\n"
        
        prompt += """
Please provide your assessment in the following JSON format:
{
    "overall_assessment": "Brief overall assessment of response quality",
    "relevance_score": 0.0-1.0,
    "completeness_score": 0.0-1.0,
    "accuracy_score": 0.0-1.0,
    "clarity_score": 0.0-1.0,
    "strengths": ["strength1", "strength2"],
    "weaknesses": ["weakness1", "weakness2"],
    "recommendations": ["recommendation1", "recommendation2"],
    "missing_information": ["missing1", "missing2"],
    "best_response_index": index of best response (1-based),
    "should_combine_responses": true/false,
    "suggested_improvements": "How to improve the response"
}"""
        return prompt
    
    def _parse_assessment(self, assessment_content: str) -> Dict[str, Any]:
        """Parse the assessment from LLM response"""
        try:
            # Try to parse as JSON
            if assessment_content.strip().startswith('{'):
                return json.loads(assessment_content)
            
            # Extract JSON from markdown code block if present
            import re
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', assessment_content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
            
            # Fallback: create basic assessment
            return {
                'overall_assessment': assessment_content,
                'relevance_score': 0.5,
                'completeness_score': 0.5,
                'accuracy_score': 0.5,
                'clarity_score': 0.5,
                'strengths': [],
                'weaknesses': ['Could not parse detailed assessment'],
                'recommendations': ['Retry assessment'],
                'missing_information': [],
                'best_response_index': 1,
                'should_combine_responses': False,
                'suggested_improvements': 'Needs reassessment'
            }
        except Exception as e:
            self.logger.error(f"Error parsing assessment: {e}")
            return {
                'error': str(e),
                'relevance_score': 0.5,
                'completeness_score': 0.5,
                'accuracy_score': 0.5,
                'clarity_score': 0.5
            }
    
    def _calculate_confidence(
        self,
        responses: List[SourceResponse],
        assessment_data: Dict[str, Any]
    ) -> float:
        """Calculate overall confidence score"""
        # Get assessment scores
        relevance = assessment_data.get('relevance_score', 0.5)
        completeness = assessment_data.get('completeness_score', 0.5)
        accuracy = assessment_data.get('accuracy_score', 0.5)
        clarity = assessment_data.get('clarity_score', 0.5)
        
        # Calculate base score from assessment
        base_score = (relevance * 0.3 + completeness * 0.3 + accuracy * 0.3 + clarity * 0.1)
        
        # Apply source weights
        if responses:
            source_bonus = 0
            for response in responses:
                source_weight = self.source_weights.get(response.source, 0.5)
                source_bonus += source_weight * response.confidence * 0.1
            
            # Combine base score with source bonus
            final_score = base_score * 0.9 + source_bonus * 0.1
        else:
            final_score = base_score
        
        # Multiple sources bonus
        if len(responses) > 1:
            final_score = min(1.0, final_score * 1.1)
        
        return min(1.0, max(0.0, final_score))
    
    def _determine_quality_level(self, confidence_score: float) -> QualityLevel:
        """Determine quality level based on confidence score"""
        if confidence_score >= self.quality_thresholds['excellent']:
            return QualityLevel.EXCELLENT
        elif confidence_score >= self.quality_thresholds['good']:
            return QualityLevel.GOOD
        elif confidence_score >= self.quality_thresholds['fair']:
            return QualityLevel.FAIR
        elif confidence_score >= self.quality_thresholds['poor']:
            return QualityLevel.POOR
        else:
            return QualityLevel.UNACCEPTABLE
    
    async def _synthesize_response(
        self,
        question: str,
        responses: List[SourceResponse],
        assessment_data: Dict[str, Any]
    ) -> str:
        """Synthesize multiple responses into a final comprehensive answer"""
        if not responses:
            return ""
        
        # If only one response or one is clearly best, use it
        if len(responses) == 1 or not assessment_data.get('should_combine_responses', False):
            best_index = assessment_data.get('best_response_index', 1) - 1
            if 0 <= best_index < len(responses):
                return responses[best_index].content
            return responses[0].content
        
        # Synthesize multiple responses
        synthesis_prompt = f"""Given the following question and multiple responses from different sources, 
create a comprehensive, well-structured final answer that combines the best information from all sources.

Question: {question}

Responses:
"""
        for i, response in enumerate(responses, 1):
            synthesis_prompt += f"\nSource {i} ({response.source.value}):\n{response.content}\n"
        
        synthesis_prompt += """
Create a synthesized response that:
1. Combines the most accurate and relevant information from all sources
2. Eliminates redundancy
3. Maintains clarity and coherence
4. Properly attributes information to sources when appropriate
5. Provides a complete answer to the user's question"""
        
        synthesis_response = await self.llm_service.generate_response(
            prompt=synthesis_prompt,
            system_message="You are a response synthesizer. Create comprehensive answers from multiple sources."
        )
        
        return synthesis_response
    
    def _suggest_additional_sources(
        self,
        responses: List[SourceResponse],
        assessment_data: Dict[str, Any]
    ) -> List[ResponseSource]:
        """Suggest additional sources to consult based on assessment"""
        suggestions = []
        used_sources = {r.source for r in responses}
        
        # Check what's missing
        missing_info = assessment_data.get('missing_information', [])
        
        # If knowledge base wasn't used and we need authoritative info
        if ResponseSource.KNOWLEDGE_BASE not in used_sources and missing_info:
            suggestions.append(ResponseSource.KNOWLEDGE_BASE)
        
        # If web search wasn't used and we need current information
        if ResponseSource.WEB_SEARCH not in used_sources:
            if any(keyword in str(missing_info).lower() for keyword in ['recent', 'latest', 'current', 'news', 'update']):
                suggestions.append(ResponseSource.WEB_SEARCH)
        
        # If we have search results but no deep scraping
        if ResponseSource.WEB_SEARCH in used_sources and ResponseSource.WEB_SCRAPE not in used_sources:
            if assessment_data.get('completeness_score', 0) < 0.7:
                suggestions.append(ResponseSource.WEB_SCRAPE)
        
        return suggestions
    
    async def process_message(self, message: str, **kwargs) -> Dict[str, Any]:
        """
        Process a message (mainly for testing the assessor directly).
        In production, this agent is called by the EnhancedModeratorAgent.
        """
        # This is mainly for testing - in production, use assess_response directly
        return {
            'success': True,
            'response': 'ResponseQualityAssessor is ready. Use assess_response() method for quality assessment.',
            'agent': self.agent_id
        }
    
    async def process_message_stream(self, message: str, **kwargs):
        """Stream processing not implemented for assessor"""
        yield {
            'success': True,
            'response': 'Streaming not supported for ResponseQualityAssessor',
            'agent': self.agent_id
        }