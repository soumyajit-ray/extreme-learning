import re
import os
from PIL import Image, ImageDraw, ImageFont
import moviepy as mp
from mutagen.mp3 import MP3

def parse_slides(content):
    """
    Parse the text and extract individual slides.
    Returns a list of dictionaries with slide number and content.
    """

    # Split content by slide markers
    slide_pattern = r'## Slide \d+: (.*?)((?=## Slide \d+:)|$)'
    slides_raw = re.findall(slide_pattern, content, re.DOTALL)
    
    slides = []
    for i, (title, content) in enumerate(slides_raw, 1):
        slides.append({
            'number': i,
            'title': title.strip(),
            'content': content.strip()
        })
    
    return slides

def create_slide_image(slide, output_folder, width=1920, height=1080):
    """
    Create an image for a slide with formatted text.
    """
    # Create a blank white image
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)
    
    # Load fonts
    try:
        title_font = ImageFont.truetype('Arial Bold.ttf', 60)
        content_font = ImageFont.truetype('Arial.ttf', 40)
    except IOError:
        # Fallback to default font if Arial is not available
        title_font = ImageFont.load_default()
        content_font = ImageFont.load_default()
    
    # Draw title
    title = f"Slide {slide['number']}: {slide['title']}"
    draw.text((100, 50), title, fill='black', font=title_font)
    
    # Process and draw content
    y_position = 150
    content_lines = slide['content'].split('\n')
    
    for line in content_lines:
        # Handle bullet points with proper indentation
        indent = 0
        if line.strip().startswith('-'):
            indent = 50
            line = '•' + line[1:]
        elif line.strip().startswith('  -'):
            indent = 100
            line = '  •' + line[3:]
        
        # Handle code blocks
        if line.strip() == '```json' or line.strip() == '```':
            continue
        
        # Draw the line
        draw.text((100 + indent, y_position), line.strip(), fill='black', font=content_font)
        y_position += 50
    
    # Save the image
    os.makedirs(output_folder, exist_ok=True)
    img_path = os.path.join(output_folder, f"slide_{slide['number']}.png")
    img.save(img_path)
    return img_path

def create_video_from_slides_and_audio(slides_folder, audio_folder, output_video_path):
    """
    Create a video presentation with slides and audio.
    """
    slide_clips = []
    
    for i in range(1, len(os.listdir(slides_folder)) + 1):
        slide_path = os.path.join(slides_folder, f"slide_{i}.png")
        audio_path = os.path.join(audio_folder, f"slide_{i}.mp3")
        
        if not os.path.exists(audio_path):
            print(f"Warning: Audio file for slide {i} not found. Using a placeholder duration.")
            duration = 5  # Default duration if audio file is missing
        else:
            # Get audio duration
            audio = MP3(audio_path)
            duration = audio.info.length
        
        # Create image clip with audio duration
        slide_clip = mp.ImageClip(slide_path).with_duration(duration)
        
        # Add audio if available
        if os.path.exists(audio_path):
            audio_clip = mp.AudioFileClip(audio_path)
            slide_clip = slide_clip.set_audio(audio_clip)
        
        slide_clips.append(slide_clip)
    
    # Concatenate all clips
    final_clip = mp.concatenate_videoclips(slide_clips, method="compose")
    
    # Write the final video
    final_clip.write_videofile(
        output_video_path,
        fps=24,
        codec='libx264',
        audio_codec='aac'
    )
    return output_video_path