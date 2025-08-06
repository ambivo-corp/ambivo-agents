"""
Presentation Generator Service
Modern HTML/CSS-based presentation generator

Creates beautiful card-style presentations with modern web styling that can be 
exported to PDF or PPTX. Designed to work with the Executive Communication Designer agent.
"""

import asyncio
import json
import tempfile
import os
import shutil
from typing import Dict, Any, List, Optional, Union, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import uuid
from datetime import datetime
import base64
import docker


@dataclass
class PresentationTheme:
    """Modern presentation theme configuration"""
    # Color scheme
    primary_color: str = "#2563eb"      # Modern Blue
    secondary_color: str = "#10b981"    # Emerald Green
    accent_color: str = "#f59e0b"       # Amber
    text_primary: str = "#1f2937"       # Dark Gray
    text_secondary: str = "#6b7280"     # Medium Gray
    background: str = "#ffffff"         # White
    surface: str = "#f9fafb"            # Light Gray
    
    # Typography
    font_family: str = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    title_size: str = "2.5rem"
    subtitle_size: str = "1.25rem"
    body_size: str = "1rem"
    small_size: str = "0.875rem"
    
    # Layout
    card_radius: str = "1rem"
    card_shadow: str = "0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)"
    spacing_unit: str = "1.5rem"
    max_width: str = "1200px"
    
    # Branding
    logo_url: Optional[str] = None
    company_name: str = ""
    brand_accent: str = "#8b5cf6"  # Purple
    
    # Animation
    transition_duration: str = "0.3s"
    hover_lift: str = "translateY(-2px)"


@dataclass
class SlideCard:
    """Configuration for a single slide card"""
    slide_type: str  # hero, insight, chart, bullets, conclusion, full_image
    title: str
    subtitle: Optional[str] = None
    content: List[str] = None
    chart_config: Optional[Dict[str, Any]] = None
    image_url: Optional[str] = None
    background_gradient: Optional[str] = None
    layout: str = "standard"  # standard, centered, split, full
    animation: str = "fade"   # fade, slide, zoom
    
    def __post_init__(self):
        if self.content is None:
            self.content = []


class ModernPresentationGenerator:
    """
    Gamma.app-style presentation generator using modern HTML/CSS.
    
    Creates beautiful card-style presentations with animations, charts,
    and responsive design that can be exported to various formats.
    """
    
    def __init__(self, docker_image: str = "sgosain/amb-ubuntu-python-public-pod"):
        self.docker_image = docker_image
        self.docker_client = None
        self.work_dir = "/tmp/presentation_generator"
        
    async def initialize(self):
        """Initialize Docker client for export functionality"""
        try:
            self.docker_client = docker.from_env()
            try:
                self.docker_client.images.get(self.docker_image)
            except docker.errors.ImageNotFound:
                print(f"Pulling Docker image: {self.docker_image}")
                self.docker_client.images.pull(self.docker_image)
        except Exception as e:
            print(f"Warning: Docker not available for exports: {e}")
    
    async def generate_presentation(
        self,
        slides: List[SlideCard],
        theme: PresentationTheme,
        title: str = "Strategic Presentation",
        output_dir: str = None
    ) -> Dict[str, Any]:
        """
        Generate a modern HTML/CSS presentation
        
        Args:
            slides: List of slide card configurations
            theme: Presentation theme settings
            title: Presentation title
            output_dir: Output directory
            
        Returns:
            Generation results with file paths
        """
        session_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if not output_dir:
            output_dir = self.work_dir
        os.makedirs(output_dir, exist_ok=True)
        
        try:
            # Generate HTML presentation
            html_content = await self._generate_html_presentation(slides, theme, title)
            
            # Save HTML file
            html_filename = f"presentation_{timestamp}_{session_id}.html"
            html_path = os.path.join(output_dir, html_filename)
            
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            # Generate standalone assets
            assets_dir = os.path.join(output_dir, f"assets_{session_id}")
            os.makedirs(assets_dir, exist_ok=True)
            
            # Save CSS and JS separately for modularity
            css_content = self._generate_css(theme)
            js_content = self._generate_javascript()
            
            with open(os.path.join(assets_dir, "styles.css"), 'w') as f:
                f.write(css_content)
            
            with open(os.path.join(assets_dir, "presentation.js"), 'w') as f:
                f.write(js_content)
            
            return {
                'success': True,
                'html_path': html_path,
                'assets_dir': assets_dir,
                'session_id': session_id,
                'slides_generated': len(slides),
                'theme_applied': asdict(theme),
                'view_url': f"file://{html_path}",
                'export_options': {
                    'pdf_available': self.docker_client is not None,
                    'pptx_available': self.docker_client is not None
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'session_id': session_id
            }
    
    async def _generate_html_presentation(
        self, 
        slides: List[SlideCard], 
        theme: PresentationTheme, 
        title: str
    ) -> str:
        """Generate complete HTML presentation"""
        
        # Generate slide HTML
        slides_html = []
        for i, slide in enumerate(slides):
            slide_html = self._generate_slide_html(slide, theme, i)
            slides_html.append(slide_html)
        
        # Create complete HTML document
        html_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/aos@2.3.4/dist/aos.js"></script>
    <link href="https://cdn.jsdelivr.net/npm/aos@2.3.4/dist/aos.css" rel="stylesheet">
    <style>
        {self._generate_css(theme)}
    </style>
</head>
<body>
    <div class="presentation-container">
        <!-- Navigation -->
        <nav class="presentation-nav">
            <div class="nav-content">
                <h1 class="presentation-title">{title}</h1>
                <div class="nav-controls">
                    <button class="nav-btn" onclick="previousSlide()">←</button>
                    <span class="slide-counter">
                        <span id="current-slide">1</span> / <span id="total-slides">{len(slides)}</span>
                    </span>
                    <button class="nav-btn" onclick="nextSlide()">→</button>
                </div>
            </div>
        </nav>
        
        <!-- Slides Container -->
        <main class="slides-container" id="slides-container">
            {chr(10).join(slides_html)}
        </main>
        
        <!-- Progress Bar -->
        <div class="progress-bar">
            <div class="progress-fill" id="progress-fill"></div>
        </div>
    </div>
    
    <script>
        {self._generate_javascript()}
    </script>
</body>
</html>
        """
        
        return html_template.strip()
    
    def _generate_slide_html(self, slide: SlideCard, theme: PresentationTheme, index: int) -> str:
        """Generate HTML for a single slide card"""
        
        slide_class = f"slide slide-{slide.slide_type}"
        if index == 0:
            slide_class += " active"
        
        if slide.slide_type == "hero":
            return self._generate_hero_slide(slide, theme, slide_class)
        elif slide.slide_type == "insight":
            return self._generate_insight_slide(slide, theme, slide_class)
        elif slide.slide_type == "chart":
            return self._generate_chart_slide(slide, theme, slide_class, index)
        elif slide.slide_type == "bullets":
            return self._generate_bullets_slide(slide, theme, slide_class)
        elif slide.slide_type == "conclusion":
            return self._generate_conclusion_slide(slide, theme, slide_class)
        else:
            return self._generate_standard_slide(slide, theme, slide_class)
    
    def _generate_hero_slide(self, slide: SlideCard, theme: PresentationTheme, slide_class: str) -> str:
        """Generate hero slide HTML"""
        background_style = ""
        if slide.background_gradient:
            background_style = f"background: {slide.background_gradient};"
        
        logo_html = ""
        if theme.logo_url:
            logo_html = f'<img src="{theme.logo_url}" alt="Logo" class="hero-logo">'
        
        return f"""
        <section class="{slide_class}" style="{background_style}">
            <div class="slide-content hero-content" data-aos="fade-up">
                {logo_html}
                <h1 class="hero-title">{slide.title}</h1>
                {f'<p class="hero-subtitle">{slide.subtitle}</p>' if slide.subtitle else ''}
                {f'<p class="hero-company">{theme.company_name}</p>' if theme.company_name else ''}
            </div>
        </section>
        """
    
    def _generate_source_references_html(self, sources: List[str]) -> str:
        """Generate HTML for source references"""
        if not sources:
            return ""
        
        source_items = [f'<div class="source-item">{source}</div>' for source in sources]
        return f"""
        <div class="source-references">
            <div class="source-references-title">Sources:</div>
            {"".join(source_items)}
        </div>
        """
    
    def _generate_insight_slide(self, slide: SlideCard, theme: PresentationTheme, slide_class: str) -> str:
        """Generate insight slide with emphasis styling"""
        content_html = ""
        if slide.content:
            content_items = [f'<li class="insight-item" data-aos="fade-up" data-aos-delay="{i*100}">{item}</li>' 
                           for i, item in enumerate(slide.content)]
            content_html = f'<ul class="insight-list">{"".join(content_items)}</ul>'
        
        # Get source references if available
        sources_html = ""
        if hasattr(slide, 'source_references') and slide.source_references:
            sources_html = self._generate_source_references_html(slide.source_references)
        
        return f"""
        <section class="{slide_class}">
            <div class="slide-content insight-content">
                <div class="insight-card" data-aos="zoom-in">
                    <h2 class="insight-title">{slide.title}</h2>
                    {f'<p class="insight-subtitle">{slide.subtitle}</p>' if slide.subtitle else ''}
                    {content_html}
                    {sources_html}
                </div>
            </div>
        </section>
        """
    
    def _generate_chart_slide(self, slide: SlideCard, theme: PresentationTheme, slide_class: str, index: int) -> str:
        """Generate chart slide with Chart.js integration"""
        chart_id = f"chart-{index}"
        
        # Get source references if available
        sources_html = ""
        if hasattr(slide, 'source_references') and slide.source_references:
            sources_html = self._generate_source_references_html(slide.source_references)
        
        return f"""
        <section class="{slide_class}">
            <div class="slide-content chart-content">
                <div class="chart-card" data-aos="fade-up">
                    <h2 class="chart-title">{slide.title}</h2>
                    {f'<p class="chart-subtitle">{slide.subtitle}</p>' if slide.subtitle else ''}
                    <div class="chart-container">
                        <canvas id="{chart_id}"></canvas>
                    </div>
                    {sources_html}
                </div>
            </div>
            <script>
                // Initialize chart when slide becomes active
                document.addEventListener('slideChanged', function(e) {{
                    if (e.detail.slideIndex === {index}) {{
                        initializeChart_{index}();
                    }}
                }});
                
                function initializeChart_{index}() {{
                    const ctx = document.getElementById('{chart_id}');
                    if (ctx && !ctx.chart) {{
                        const chartConfig = {json.dumps(slide.chart_config or self._get_default_chart_config())};
                        ctx.chart = new Chart(ctx, chartConfig);
                    }}
                }}
            </script>
        </section>
        """
    
    def _generate_bullets_slide(self, slide: SlideCard, theme: PresentationTheme, slide_class: str) -> str:
        """Generate bullet points slide"""
        content_html = ""
        if slide.content:
            content_items = [f'<li class="bullet-item" data-aos="fade-right" data-aos-delay="{i*150}">{item}</li>' 
                           for i, item in enumerate(slide.content)]
            content_html = f'<ul class="bullet-list">{"".join(content_items)}</ul>'
        
        # Get source references if available
        sources_html = ""
        if hasattr(slide, 'source_references') and slide.source_references:
            sources_html = self._generate_source_references_html(slide.source_references)
        
        return f"""
        <section class="{slide_class}">
            <div class="slide-content bullets-content">
                <div class="bullets-card" data-aos="fade-up">
                    <h2 class="bullets-title">{slide.title}</h2>
                    {f'<p class="bullets-subtitle">{slide.subtitle}</p>' if slide.subtitle else ''}
                    {content_html}
                    {sources_html}
                </div>
            </div>
        </section>
        """
    
    def _generate_conclusion_slide(self, slide: SlideCard, theme: PresentationTheme, slide_class: str) -> str:
        """Generate conclusion slide with call-to-action styling"""
        content_html = ""
        if slide.content:
            content_items = [f'<div class="conclusion-item" data-aos="zoom-in" data-aos-delay="{i*100}">{item}</div>' 
                           for i, item in enumerate(slide.content)]
            content_html = f'<div class="conclusion-items">{"".join(content_items)}</div>'
        
        # Get source references if available
        sources_html = ""
        if hasattr(slide, 'source_references') and slide.source_references:
            sources_html = self._generate_source_references_html(slide.source_references)
        
        return f"""
        <section class="{slide_class}">
            <div class="slide-content conclusion-content">
                <div class="conclusion-card" data-aos="fade-up">
                    <h2 class="conclusion-title">{slide.title}</h2>
                    {f'<p class="conclusion-subtitle">{slide.subtitle}</p>' if slide.subtitle else ''}
                    {content_html}
                    {sources_html}
                </div>
            </div>
        </section>
        """
    
    def _generate_standard_slide(self, slide: SlideCard, theme: PresentationTheme, slide_class: str) -> str:
        """Generate standard content slide"""
        content_html = ""
        if slide.content:
            content_items = [f'<p class="content-item" data-aos="fade-up" data-aos-delay="{i*100}">{item}</p>' 
                           for i, item in enumerate(slide.content)]
            content_html = f'<div class="content-items">{"".join(content_items)}</div>'
        
        # Get source references if available
        sources_html = ""
        if hasattr(slide, 'source_references') and slide.source_references:
            sources_html = self._generate_source_references_html(slide.source_references)
        
        return f"""
        <section class="{slide_class}">
            <div class="slide-content standard-content">
                <div class="content-card" data-aos="fade-up">
                    <h2 class="content-title">{slide.title}</h2>
                    {f'<p class="content-subtitle">{slide.subtitle}</p>' if slide.subtitle else ''}
                    {content_html}
                    {sources_html}
                </div>
            </div>
        </section>
        """
    
    def _generate_css(self, theme: PresentationTheme) -> str:
        """Generate modern CSS styles"""
        return f"""
        /* Reset and Base Styles */
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: {theme.font_family};
            background: {theme.background};
            color: {theme.text_primary};
            overflow-x: hidden;
        }}
        
        /* Presentation Container */
        .presentation-container {{
            height: 100vh;
            display: flex;
            flex-direction: column;
        }}
        
        /* Navigation */
        .presentation-nav {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-bottom: 1px solid rgba(0, 0, 0, 0.1);
            z-index: 1000;
            padding: 1rem 0;
        }}
        
        .nav-content {{
            max-width: {theme.max_width};
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0 2rem;
        }}
        
        .presentation-title {{
            font-size: 1.25rem;
            font-weight: 600;
            color: {theme.primary_color};
        }}
        
        .nav-controls {{
            display: flex;
            align-items: center;
            gap: 1rem;
        }}
        
        .nav-btn {{
            background: {theme.primary_color};
            color: white;
            border: none;
            border-radius: 0.5rem;
            padding: 0.5rem 1rem;
            cursor: pointer;
            font-size: 1rem;
            transition: all {theme.transition_duration};
        }}
        
        .nav-btn:hover {{
            background: {theme.secondary_color};
            transform: {theme.hover_lift};
        }}
        
        .slide-counter {{
            font-size: 0.875rem;
            color: {theme.text_secondary};
            font-weight: 500;
        }}
        
        /* Slides Container */
        .slides-container {{
            flex: 1;
            position: relative;
            margin-top: 80px;
            overflow: hidden;
        }}
        
        /* Individual Slides */
        .slide {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            opacity: 0;
            transform: translateX(100px);
            transition: all 0.6s cubic-bezier(0.4, 0, 0.2, 1);
            padding: 2rem;
        }}
        
        .slide.active {{
            opacity: 1;
            transform: translateX(0);
        }}
        
        .slide-content {{
            max-width: {theme.max_width};
            width: 100%;
            text-align: center;
        }}
        
        /* Hero Slide */
        .slide-hero {{
            background: linear-gradient(135deg, {theme.primary_color}, {theme.secondary_color});
            color: white;
        }}
        
        .hero-content {{
            text-align: center;
        }}
        
        .hero-logo {{
            width: 80px;
            height: 80px;
            object-fit: contain;
            margin-bottom: 2rem;
        }}
        
        .hero-title {{
            font-size: 3.5rem;
            font-weight: 700;
            margin-bottom: 1rem;
            line-height: 1.1;
        }}
        
        .hero-subtitle {{
            font-size: 1.5rem;
            font-weight: 400;
            opacity: 0.9;
            margin-bottom: 2rem;
        }}
        
        .hero-company {{
            font-size: 1.125rem;
            font-weight: 500;
            opacity: 0.8;
        }}
        
        /* Card Styles */
        .insight-card, .chart-card, .bullets-card, .conclusion-card, .content-card {{
            background: {theme.surface};
            border-radius: {theme.card_radius};
            box-shadow: {theme.card_shadow};
            padding: 3rem;
            max-width: 900px;
            margin: 0 auto;
            transition: all {theme.transition_duration};
        }}
        
        .insight-card:hover, .chart-card:hover, .bullets-card:hover, .conclusion-card:hover, .content-card:hover {{
            transform: {theme.hover_lift};
            box-shadow: 0 20px 40px -10px rgba(0, 0, 0, 0.15);
        }}
        
        /* Typography */
        .insight-title, .chart-title, .bullets-title, .conclusion-title, .content-title {{
            font-size: {theme.title_size};
            font-weight: 700;
            color: {theme.primary_color};
            margin-bottom: 1rem;
            line-height: 1.2;
        }}
        
        .insight-subtitle, .chart-subtitle, .bullets-subtitle, .conclusion-subtitle, .content-subtitle {{
            font-size: {theme.subtitle_size};
            color: {theme.text_secondary};
            margin-bottom: 2rem;
            line-height: 1.4;
        }}
        
        /* Lists */
        .insight-list, .bullet-list {{
            list-style: none;
            text-align: left;
        }}
        
        .insight-item, .bullet-item {{
            font-size: {theme.body_size};
            line-height: 1.6;
            margin-bottom: 1rem;
            padding-left: 2rem;
            position: relative;
        }}
        
        .insight-item::before, .bullet-item::before {{
            content: '';
            position: absolute;
            left: 0;
            top: 0.6rem;
            width: 8px;
            height: 8px;
            background: {theme.accent_color};
            border-radius: 50%;
        }}
        
        /* Chart Container */
        .chart-container {{
            height: 400px;
            margin-top: 2rem;
        }}
        
        /* Conclusion Styles */
        .conclusion-card {{
            background: linear-gradient(135deg, {theme.accent_color}, {theme.brand_accent});
            color: white;
        }}
        
        .conclusion-title {{
            color: white;
        }}
        
        .conclusion-subtitle {{
            color: rgba(255, 255, 255, 0.9);
        }}
        
        .conclusion-items {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1.5rem;
            margin-top: 2rem;
        }}
        
        .conclusion-item {{
            background: rgba(255, 255, 255, 0.1);
            border-radius: 0.75rem;
            padding: 1.5rem;
            font-weight: 500;
            backdrop-filter: blur(10px);
        }}
        
        /* Source References */
        .source-references {{
            margin-top: 2rem;
            padding-top: 1rem;
            border-top: 1px solid rgba(0, 0, 0, 0.1);
            font-size: 0.75rem;
            color: #6b7280;
            text-align: left;
        }}
        
        .source-references-title {{
            font-weight: 600;
            margin-bottom: 0.5rem;
            color: #4b5563;
        }}
        
        .source-item {{
            margin-bottom: 0.25rem;
            line-height: 1.4;
        }}
        
        .source-item::before {{
            content: '→ ';
            color: {theme.accent_color};
        }}
        
        /* Progress Bar */
        .progress-bar {{
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: rgba(0, 0, 0, 0.1);
        }}
        
        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, {theme.primary_color}, {theme.secondary_color});
            transition: width 0.3s ease;
            width: 0%;
        }}
        
        /* Responsive Design */
        @media (max-width: 768px) {{
            .hero-title {{
                font-size: 2.5rem;
            }}
            
            .hero-subtitle {{
                font-size: 1.25rem;
            }}
            
            .insight-card, .chart-card, .bullets-card, .conclusion-card, .content-card {{
                padding: 2rem;
                margin: 0 1rem;
            }}
            
            .nav-content {{
                padding: 0 1rem;
            }}
            
            .presentation-title {{
                font-size: 1rem;
            }}
        }}
        
        /* Animation Classes */
        .fade-in {{
            animation: fadeIn 0.6s ease-out;
        }}
        
        @keyframes fadeIn {{
            from {{
                opacity: 0;
                transform: translateY(30px);
            }}
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}
        """
    
    def _generate_javascript(self) -> str:
        """Generate JavaScript for presentation functionality"""
        return """
        // Presentation Controller
        class PresentationController {
            constructor() {
                this.currentSlide = 0;
                this.slides = document.querySelectorAll('.slide');
                this.totalSlides = this.slides.length;
                this.init();
            }
            
            init() {
                this.updateSlideCounter();
                this.updateProgressBar();
                this.bindKeyboardEvents();
                this.initializeAOS();
                
                // Initialize first slide chart if it exists
                setTimeout(() => {
                    this.initializeCurrentSlideChart();
                }, 100);
            }
            
            initializeAOS() {
                if (typeof AOS !== 'undefined') {
                    AOS.init({
                        duration: 600,
                        easing: 'ease-out',
                        once: false
                    });
                }
            }
            
            nextSlide() {
                if (this.currentSlide < this.totalSlides - 1) {
                    this.goToSlide(this.currentSlide + 1);
                }
            }
            
            previousSlide() {
                if (this.currentSlide > 0) {
                    this.goToSlide(this.currentSlide - 1);
                }
            }
            
            goToSlide(slideIndex) {
                // Remove active class from current slide
                this.slides[this.currentSlide].classList.remove('active');
                
                // Update current slide
                this.currentSlide = slideIndex;
                
                // Add active class to new slide
                this.slides[this.currentSlide].classList.add('active');
                
                // Update UI
                this.updateSlideCounter();
                this.updateProgressBar();
                
                // Reinitialize AOS for new slide
                if (typeof AOS !== 'undefined') {
                    AOS.refresh();
                }
                
                // Initialize chart for new slide
                setTimeout(() => {
                    this.initializeCurrentSlideChart();
                }, 300);
                
                // Dispatch slide change event
                document.dispatchEvent(new CustomEvent('slideChanged', {
                    detail: { slideIndex: this.currentSlide }
                }));
            }
            
            initializeCurrentSlideChart() {
                const currentSlideElement = this.slides[this.currentSlide];
                const canvas = currentSlideElement.querySelector('canvas');
                
                if (canvas && !canvas.chart) {
                    const initFunction = window[`initializeChart_${this.currentSlide}`];
                    if (typeof initFunction === 'function') {
                        initFunction();
                    }
                }
            }
            
            updateSlideCounter() {
                const currentElement = document.getElementById('current-slide');
                const totalElement = document.getElementById('total-slides');
                
                if (currentElement) currentElement.textContent = this.currentSlide + 1;
                if (totalElement) totalElement.textContent = this.totalSlides;
            }
            
            updateProgressBar() {
                const progressFill = document.getElementById('progress-fill');
                if (progressFill) {
                    const progress = ((this.currentSlide + 1) / this.totalSlides) * 100;
                    progressFill.style.width = `${progress}%`;
                }
            }
            
            bindKeyboardEvents() {
                document.addEventListener('keydown', (e) => {
                    switch(e.key) {
                        case 'ArrowRight':
                        case ' ':
                            e.preventDefault();
                            this.nextSlide();
                            break;
                        case 'ArrowLeft':
                            e.preventDefault();
                            this.previousSlide();
                            break;
                        case 'Home':
                            e.preventDefault();
                            this.goToSlide(0);
                            break;
                        case 'End':
                            e.preventDefault();
                            this.goToSlide(this.totalSlides - 1);
                            break;
                    }
                });
            }
        }
        
        // Navigation Functions
        function nextSlide() {
            if (window.presentationController) {
                window.presentationController.nextSlide();
            }
        }
        
        function previousSlide() {
            if (window.presentationController) {
                window.presentationController.previousSlide();
            }
        }
        
        // Initialize presentation when DOM is loaded
        document.addEventListener('DOMContentLoaded', function() {
            window.presentationController = new PresentationController();
        });
        """
    
    def _get_default_chart_config(self) -> Dict[str, Any]:
        """Get default Chart.js configuration"""
        return {
            'type': 'bar',
            'data': {
                'labels': ['Q1', 'Q2', 'Q3', 'Q4'],
                'datasets': [{
                    'label': 'Revenue',
                    'data': [12, 19, 3, 5],
                    'backgroundColor': [
                        'rgba(37, 99, 235, 0.8)',
                        'rgba(16, 185, 129, 0.8)',
                        'rgba(245, 158, 11, 0.8)',
                        'rgba(139, 92, 246, 0.8)'
                    ],
                    'borderColor': [
                        'rgba(37, 99, 235, 1)',
                        'rgba(16, 185, 129, 1)',
                        'rgba(245, 158, 11, 1)',
                        'rgba(139, 92, 246, 1)'
                    ],
                    'borderWidth': 2,
                    'borderRadius': 8
                }]
            },
            'options': {
                'responsive': True,
                'maintainAspectRatio': False,
                'plugins': {
                    'legend': {
                        'display': False
                    }
                },
                'scales': {
                    'y': {
                        'beginAtZero': True,
                        'grid': {
                            'color': 'rgba(0, 0, 0, 0.05)'
                        }
                    },
                    'x': {
                        'grid': {
                            'display': False
                        }
                    }
                }
            }
        }
    
    async def export_to_pdf(self, html_path: str, output_path: str = None) -> Dict[str, Any]:
        """Export HTML presentation to PDF using Docker"""
        if not self.docker_client:
            await self.initialize()
        
        if not self.docker_client:
            return {'success': False, 'error': 'Docker not available for PDF export'}
        
        # Implementation for PDF export using puppeteer in Docker
        # This would use headless Chrome to render the HTML and export to PDF
        pass
    
    async def create_research_presentation_cards(
        self,
        title: str,
        slides_content: List[Dict[str, Any]],
        theme_overrides: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Create research-style presentation cards from ExecutiveCommunicationDesigner output
        
        Args:
            title: Presentation title
            slides_content: Slide specifications from ExecutiveCommunicationDesigner
            theme_overrides: Optional theme customizations
            
        Returns:
            Generation results with HTML path
        """
        
        # Create research theme
        theme = PresentationTheme(
            primary_color="#1F4E79",    # Research Blue
            secondary_color="#70AD47",  # Growth Green
            accent_color="#E74C3C",     # Alert Red
            company_name="Research Consulting",
            font_family="Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
        )
        
        # Apply theme overrides
        if theme_overrides:
            for key, value in theme_overrides.items():
                if hasattr(theme, key):
                    setattr(theme, key, value)
        
        # Convert slide specifications to SlideCard objects
        slides = []
        
        # Hero slide
        slides.append(SlideCard(
            slide_type="hero",
            title=title,
            subtitle="Strategic Analysis & Executive Recommendations",
            background_gradient=f"linear-gradient(135deg, {theme.primary_color}, {theme.secondary_color})"
        ))
        
        # Content slides
        for i, slide_spec in enumerate(slides_content):
            slide_type = self._determine_slide_type_from_spec(slide_spec)
            
            slide_title = slide_spec.get('title', f'Strategic Point {i+1}')
            bullet_points = slide_spec.get('bullet_points', [])
            
            # Handle visualization data
            chart_config = None
            if slide_type == "chart" and slide_spec.get('visualization'):
                chart_config = self._convert_visualization_to_chart_config(slide_spec['visualization'])
            
            slide_card = SlideCard(
                slide_type=slide_type,
                title=slide_title,
                subtitle=slide_spec.get('executive_focus', ''),
                content=bullet_points,
                chart_config=chart_config
            )
            
            slides.append(slide_card)
        
        # Generate presentation
        return await self.generate_presentation(slides, theme, title)
    
    def _determine_slide_type_from_spec(self, slide_spec: Dict[str, Any]) -> str:
        """Determine slide type from ExecutiveCommunicationDesigner specification"""
        title = slide_spec.get('title', '').lower()
        visualization = slide_spec.get('visualization', {})
        bullet_points = slide_spec.get('bullet_points', [])
        
        # Check if visualization is explicitly disabled
        chart_type = visualization.get('chart_type', '') if visualization else ''
        has_chart = chart_type and chart_type.lower() not in ['none', 'null', '']
        
        # Determine slide type based on content and intent
        if any(word in title for word in ['hypothesis', 'future outlook', 'conclusion', 'strategic hypothesis']):
            return 'conclusion'
        elif any(word in title for word in ['executive summary', 'key strategic insights']):
            return 'insight'  # Executive summary should be narrative, not chart
        elif any(word in title for word in ['risks', 'unknowns', 'recommendations', 'next steps']):
            return 'insight'  # Risk and recommendations should be narrative
        elif has_chart and any(word in title for word in ['market', 'growth', 'opportunities', 'implications']):
            return 'chart'  # Only market/data slides get charts
        elif len(bullet_points) > 4:
            return 'insight'  # Long bullet lists are narrative-focused
        elif any(word in title for word in ['strategic narrative', 'competitive landscape', 'innovation trends']):
            return 'insight'  # Strategic content is narrative
        else:
            return 'insight'  # Default to insight/narrative instead of chart
    
    def _convert_visualization_to_chart_config(self, viz_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Convert ExecutiveCommunicationDesigner visualization to Chart.js config"""
        chart_type = viz_spec.get('chart_type', 'bar').lower()
        
        # Map chart types
        chart_type_mapping = {
            'column': 'bar',
            'column chart': 'bar',
            'bar chart': 'bar',
            'waterfall': 'bar',
            'scatter plot': 'scatter',
            'heat map': 'bar',  # Fallback
            'line chart': 'line'
        }
        
        mapped_type = chart_type_mapping.get(chart_type, 'bar')
        
        # Create data based on actual data points and values from research
        data_points = viz_spec.get('data_points', ['Metric 1', 'Metric 2', 'Metric 3'])
        # Use actual values if provided, otherwise fall back to sample values
        data_values = viz_spec.get('data_values', [75, 60, 85])
        sample_values = data_values if data_values else [75, 60, 85]
        
        return {
            'type': mapped_type,
            'data': {
                'labels': data_points[:len(sample_values)],
                'datasets': [{
                    'label': 'Strategic Metrics',
                    'data': sample_values[:len(data_points)],
                    'backgroundColor': [
                        'rgba(31, 78, 121, 0.8)',   # Research Blue
                        'rgba(112, 173, 71, 0.8)',  # Growth Green
                        'rgba(231, 76, 60, 0.8)',   # Alert Red
                        'rgba(149, 165, 166, 0.8)', # Gray
                        'rgba(243, 156, 18, 0.8)'   # Orange
                    ],
                    'borderColor': [
                        'rgba(31, 78, 121, 1)',
                        'rgba(112, 173, 71, 1)',
                        'rgba(231, 76, 60, 1)',
                        'rgba(149, 165, 166, 1)',
                        'rgba(243, 156, 18, 1)'
                    ],
                    'borderWidth': 2,
                    'borderRadius': 8
                }]
            },
            'options': {
                'responsive': True,
                'maintainAspectRatio': False,
                'plugins': {
                    'legend': {
                        'display': False
                    }
                },
                'scales': {
                    'y': {
                        'beginAtZero': True,
                        'grid': {
                            'color': 'rgba(0, 0, 0, 0.05)'
                        }
                    },
                    'x': {
                        'grid': {
                            'display': False
                        }
                    }
                }
            }
        }


# Utility functions for creating presentations
def create_slide_cards_from_insights(insights: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert strategic insights to slide card specifications"""
    slides = []
    
    for insight in insights:
        slide = {
            'title': insight.get('headline', 'Strategic Insight'),
            'bullet_points': [
                f"📊 Evidence: {insight.get('evidence', 'Supporting data analysis')}",
                f"💡 Implication: {insight.get('implication', 'Strategic consideration required')}",
                f"🎯 Action: Implement strategic response within 90 days"
            ],
            'executive_focus': 'Strategic decision support with actionable recommendations',
            'visualization': {
                'chart_type': 'column',
                'data_points': ['Current State', 'Target State', 'Competitive Benchmark'],
                'design_notes': ['Use brand colors', 'Highlight key improvements']
            }
        }
        slides.append(slide)
    
    return slides


# Example usage
async def example_gamma_style_presentation():
    """Example of creating a Gamma.app-style presentation"""
    
    service = ModernPresentationGenerator()
    
    # Sample insights
    sample_insights = [
        {
            'headline': 'Digital transformation accelerating market disruption',
            'evidence': 'Customer adoption 60% above forecast, mobile preference at 85%',
            'implication': 'Traditional channels becoming obsolete faster than anticipated'
        },
        {
            'headline': 'AI automation creating competitive moats',
            'evidence': '40% cost reduction with 25% improvement in customer satisfaction',
            'implication': 'Early adopters establishing insurmountable advantages'
        }
    ]
    
    # Create slide specifications
    slides_content = create_slide_cards_from_insights(sample_insights)
    
    # Add conclusion slide
    slides_content.append({
        'title': 'Strategic Recommendations',
        'bullet_points': [
            '🚀 Launch digital acceleration program within 30 days',
            '🤝 Establish AI technology partnerships by Q2',
            '📈 Implement success metrics and tracking framework'
        ],
        'executive_focus': 'Immediate action required for competitive positioning'
    })
    
    # Generate presentation
    result = await service.create_mckinsey_presentation_cards(
        title="Digital Transformation Strategic Imperative",
        slides_content=slides_content,
        theme_overrides={
            'company_name': 'Research Consulting',
            'primary_color': '#1F4E79'
        }
    )
    
    return result


if __name__ == "__main__":
    result = asyncio.run(example_gamma_style_presentation())
    print(json.dumps(result, indent=2))