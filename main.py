from fastapi import FastAPI, HTTPException, Depends, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid
from typing import Optional
import os
import firebase_admin
from firebase_admin import credentials, storage
import os
import uuid
from datetime import datetime
import json
import requests
from video_utils import parse_slides, create_slide_image, create_video_from_slides_and_audio

# Initialize Firebase Admin 
# Get credentials from environment variable
cred_json = os.environ.get("FIREBASE_CREDENTIALS")

# Get LLM API key from environment variable
llm_api_key = os.environ.get("LLM_API_KEY")
if not llm_api_key:
    raise HTTPException(status_code=500, detail="LLM API key not configured")

# Parse the JSON string to create a credential object
if cred_json:
    cred_dict = json.loads(cred_json)
    cred = credentials.Certificate(cred_dict)
else:
    # Fallback for local development
    cred = credentials.Certificate("../extreme-learning-ba3b3-firebase-adminsdk-fbsvc-8a0b3ec797.json")

firebase_admin.initialize_app(cred, {
    'storageBucket': 'extreme-learning-ba3b3.firebasestorage.app'  # bucket
})

# Access Firebase Storage bucket
bucket = storage.bucket()

async def upload_to_firebase(video_data, user_id):
    """
    Upload a video to Firebase Storage
    
    Args:
        video_data (bytes): The video binary data
        user_id (str): The user ID who created the video
        
    Returns:
        str: The public URL of the uploaded video
    """
    # Create a unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"videos/{user_id}/{timestamp}_{uuid.uuid4()}.mp4"
    
    # Upload to Firebase Storage
    blob = bucket.blob(filename)
    blob.upload_from_string(
        video_data,
        content_type='video/mp4'
    )
    
    # Make the file publicly accessible
    blob.make_public()
    
    # Return the public URL
    return blob.public_url

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, replace with your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class TextRequest(BaseModel):
    text: str
    userId: str

class VideoResponse(BaseModel):
    videoId: str
    message: str
    success: bool

# In-memory store for demo purposes
# In a real app, you'd use a database
videos = {}

@app.get("/")
def read_root():
    return {"message": "Video Generation API"}

detailed_prompt = """ 
# SLIDE PRESENTATION GENERATOR
Please create the text for slides as per detailed requirements stated below. 
## User Information
- Topic: Mongo DB
- Some suggested subtopics (this is not exhaustive): transactions, Consistency, Replication, Partitioning, Data Models, Query, Indexing
- Number of slides requested: 10
- My educational background: I am a Technical Architect with 20 years experience in enterprise java development. I have experience in building microservices based applications. I have experience working with both SQL and NoSQL databases like Oracle, postgreSQL, MongoDB, ElasticSearch. 
- My current knowledge level on this topic: Beginner
- Specific concepts I am already familiar with: I have experience working with both SQL and NoSQL databases like Oracle, postgreSQL, MongoDB, ElasticSearch.
- Concepts you're unfamiliar with but think might be relevant: BTrees
- Target learning outcome: I want to be able to discuss Mongo DB in a Big Tech Interview
- Preferred learning style: Text
- Time available to review the slides: 1 hr
- Additional context or requirements: 
## Output Format
The presentation will include:
1. A prerequisite slide listing all background knowledge needed
2. [Number of slides requested] content slides covering the topic
3. A final summary/conclusion slide
4. A references/further reading slide
## Presentation Style Guidelines
- Technical depth: Moderate
- Language level: Standard
- Visual elements: Minimal
- Example preference: Real-world
- Focus areas: Theoretical foundations with a focus on interview questions
Please provide as much detail as possible in the above sections.
"""
def get_claude_response(prompt):
    headers = {
        "x-api-key": llm_api_key,
        "content-type": "application/json",
        "anthropic-version": "2023-06-01"
    }
    
    data = {
        "model": "claude-3-7-sonnet-20250219",
        "max_tokens": 10000,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }
    
    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers=headers,
        json=data
    )
    
    if response.status_code == 200:
        return response.json()["content"][0]["text"]
    else:
        return f"Error: {response.status_code}, {response.text}"


def save_response_to_file(response_text, filename="claude_response.txt"):
    with open(filename, "w", encoding="utf-8") as file:
        file.write(response_text)
    print(f"Response saved to {filename}")

def upload_video_to_firebase(video_path, user_id):
    """
    Upload a video file to Firebase Storage
    
    Args:
        video_path (str): The local path to the video file
        user_id (str): The user ID who created the video
        
    Returns:
        str: The public URL of the uploaded video
    """
    try:
        # Generate a unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"videos/{user_id}/{timestamp}_{uuid.uuid4()}.mp4"
        
        # Create a reference to the storage bucket
        bucket = storage.bucket()
        blob = bucket.blob(filename)
        
        # Upload the file
        with open(video_path, 'rb') as video_file:
            blob.upload_from_file(
                video_file,
                content_type='video/mp4'
            )
        
        # Make the file publicly accessible
        blob.make_public()
        
        # Return the public URL
        return blob.public_url
    
    except Exception as e:
        print(f"Error uploading to Firebase: {e}")
        raise Exception(f"Failed to upload video: {str(e)}")


@app.post("/process", response_model=VideoResponse)
async def process_text(request: TextRequest):
    # Generate a unique ID for the video
    video_id = str(uuid.uuid4())
    
    # Input and output paths
    #slides_text_file = "/Users/soumyajitray/Documents/extreme_learning/documentation/slides_text.txt"
    slides_folder = "slides_images"
    audio_folder = "audio_files"  # Folder containing MP3 files named slide_1.mp3, slide_2.mp3, etc.
    output_video = "presentation.mp4"

    slides_text = get_claude_response(detailed_prompt)
    # Parse slides
    slides = parse_slides(slides_text)
    # Create slide images
    for slide in slides:
        img_path = create_slide_image(slide, slides_folder)
        print(f"Created image for slide {slide['number']}: {img_path}")
    # Create video
    output_video_path = await create_video_from_slides_and_audio(slides_folder, audio_folder, output_video)


    try:
        video_url = await upload_video_to_firebase(output_video, request.userId)
        
        # Store metadata in your database (in-memory for this example)
        videos[video_id] = {
            "text": request.text,
            "userId": request.userId,
            "status": "completed",
            "videoUrl": video_url,
            "createdAt": datetime.now().isoformat()
        }
        
        return {
            "videoId": video_id,
            "message": "Video generation completed",
            "success": True,
            "videoUrl": video_url  # Return the URL to the frontend
        }
    except Exception as e:
        print(f"Error uploading to Firebase: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload video: {str(e)}")
    

@app.get("/videos/{video_id}")
async def get_video(video_id: str):
    if video_id not in videos:
        raise HTTPException(status_code=404, detail="Video not found")
    
    return videos[video_id]

@app.get("/users/{user_id}/videos")
async def get_user_videos(user_id: str):
    user_videos = {
        video_id: video 
        for video_id, video in videos.items() 
        if video["userId"] == user_id
    }
    
    return list(user_videos.values())