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

# Initialize Firebase Admin 
# Get credentials from environment variable
cred_json = os.environ.get("FIREBASE_CREDENTIALS")

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

@app.post("/process", response_model=VideoResponse)
async def process_text(request: TextRequest):
    # Generate a unique ID for the video
    video_id = str(uuid.uuid4())
    
    # In a real app, you would:
    # 1. Process the text with your AI model
    # 2. Generate a video
    # 3. Store it somewhere
    sample_video_data = open("sample_video.mp4", "rb").read()
 
    try:
        video_url = await upload_to_firebase(sample_video_data, request.userId)
        
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