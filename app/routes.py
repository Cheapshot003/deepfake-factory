from fastapi import APIRouter, Request, File, UploadFile, Form, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import os
import asyncio
import requests
import sqlite3
from concurrent.futures import ThreadPoolExecutor
import moviepy.config as config
from moviepy.editor import VideoFileClip
import json

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# Set moviepy to use a non-default audio backend
config.change_settings({"IMAGEMAGICK_BINARY": "null"})

# Create a ThreadPoolExecutor
executor = ThreadPoolExecutor(max_workers=3)  # Adjust the number of workers as needed

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tasks
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  filename TEXT,
                  status TEXT,
                  result TEXT)''')
    conn.commit()
    conn.close()

init_db()

import requests
import os
import json
import time
from moviepy.editor import VideoFileClip

def process_video(file_path, task_id, text):
    try:
        print(f"Processing video: {file_path}")
        
        # Extract audio from video without using ALSA
        video = VideoFileClip(file_path)
        audio_path = os.path.splitext(file_path)[0] + ".mp3"
        video.audio.write_audiofile(audio_path, codec='libmp3lame', verbose=False, logger=None)
        video.close()
        
        print(f"Audio extracted: {audio_path}")
        
        # Send audio to ElevenLabs for voice cloning
        elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")
        if not elevenlabs_api_key:
            raise ValueError("ELEVENLABS_API_KEY environment variable is not set")
        
        url = "https://api.elevenlabs.io/v1/voices/add"
        
        headers = {
            "Accept": "application/json",
            "xi-api-key": elevenlabs_api_key
        }
        
        data = {
            'name': f'Voice_{os.path.basename(file_path)}',
            'labels': json.dumps({"language": "German"})
        }
        
        files = [
            ('files', ('sample1.mp3', open(audio_path, 'rb'), 'audio/mpeg'))
        ]
        
        response = requests.post(url, headers=headers, data=data, files=files)
        
        if response.status_code == 200:
            voice_id = response.json().get('voice_id')
            print(f"Voice cloned successfully. Voice ID: {voice_id}")
            
            # Generate text-to-speech with the cloned voice
            tts_url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
            tts_headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": elevenlabs_api_key
            }
            tts_data = {
                "text": text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": 0.31,
                    "similarity_boost": 0.8,
                },
                "language_id": "de"
            }
            
            tts_response = requests.post(tts_url, json=tts_data, headers=tts_headers)
            
            if tts_response.status_code == 200:
                # Ensure the audio directory exists
                os.makedirs("audio", exist_ok=True)
                
                # Save the generated audio
                output_audio_path = os.path.join("audio", f"generated_{os.path.basename(file_path)}.mp3")
                with open(output_audio_path, 'wb') as audio_file:
                    audio_file.write(tts_response.content)
                
                print(f"Text-to-speech audio generated and saved: {output_audio_path}")
                
                # Perform lipsync
                sync_api_key = os.getenv("SYNC_API_KEY")
                server_domain = os.getenv("SERVER_DOMAIN")
                if not sync_api_key:
                    raise ValueError("SYNC_API_KEY environment variable is not set")
                
                lipsync_url = "https://api.synclabs.so/lipsync"
                lipsync_headers = {
                    "x-api-key": sync_api_key,
                    "Content-Type": "application/json"
                }
                lipsync_data = {
                    "audioUrl": f"https://{server_domain}/audio/{os.path.basename(output_audio_path)}",
                    "videoUrl": f"https://{server_domain}/uploads/{os.path.basename(file_path)}",
                    "model": "sync-1.6.0",
                    "synergize": True
                }
                
                lipsync_response = requests.post(lipsync_url, headers=lipsync_headers, json=lipsync_data)
                
                if lipsync_response.status_code == 201:
                    lipsync_result = lipsync_response.json()
                    job_id = lipsync_result.get('id')
                    
                    # Poll the API until the video is created
                    poll_url = f"https://api.synclabs.so/lipsync/{job_id}"
                    while True:
                        poll_response = requests.get(poll_url, headers=lipsync_headers)
                        if poll_response.status_code == 200:
                            job_status = poll_response.json().get('status')
                            if job_status == 'completed':
                                synced_video_url = poll_response.json().get('videoUrl')
                                break
                            elif job_status == 'failed':
                                raise Exception(f"Lipsync job failed: {poll_response.json().get('errorMessage')}")
                        else:
                            raise Exception(f"Error polling lipsync job: {poll_response.text}")
                        time.sleep(10)  # Wait for 10 seconds before polling again
                    
                    # Download the synced video
                    synced_video_path = os.path.join("uploads", f"synced_{os.path.basename(file_path)}")
                    synced_video_response = requests.get(synced_video_url)
                    with open(synced_video_path, 'wb') as synced_video_file:
                        synced_video_file.write(synced_video_response.content)
                    
                    print(f"Lipsync completed. Synced video saved: {synced_video_path}")
                    status = 'completed'
                    result = f"Voice cloned, TTS generated, and lipsync completed. Synced video: {synced_video_path}"
                else:
                    print(f"Error in lipsync: {lipsync_response.text}")
                    status = 'failed'
                    result = f"Lipsync failed: {lipsync_response.text}"
            else:
                print(f"Error in text-to-speech generation: {tts_response.text}")
                status = 'failed'
                result = f"Text-to-speech generation failed: {tts_response.text}"
        else:
            print(f"Error in voice cloning: {response.text}")
            status = 'failed'
            result = f"Voice cloning failed: {response.text}"
        
        # Clean up the extracted audio file
        os.remove(audio_path)
        
    except Exception as e:
        print(f"Error: {str(e)}")
        status = 'failed'
        result = str(e)
    
    finally:
        # Delete the cloned voice from ElevenLabs
        if voice_id:
            delete_url = f"https://api.elevenlabs.io/v1/voices/{voice_id}"
            delete_headers = {
                "Accept": "application/json",
                "xi-api-key": elevenlabs_api_key
            }
            delete_response = requests.delete(delete_url, headers=delete_headers)
            
            if delete_response.status_code == 200:
                print(f"Successfully deleted cloned voice with ID: {voice_id}")
            else:
                print(f"Failed to delete cloned voice. Status code: {delete_response.status_code}")
                print(f"Response: {delete_response.text}")
        
        # Update task status in the database
        conn = sqlite3.connect('tasks.db')
        c = conn.cursor()
        c.execute("UPDATE tasks SET status = ?, result = ? WHERE id = ?", (status, result, task_id))
        conn.commit()
        conn.close()

@router.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@router.get("/upload", response_class=HTMLResponse)
async def upload_form(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})

@router.post("/upload")
async def upload_video(request: Request, background_tasks: BackgroundTasks, video: UploadFile = File(...), name: str = Form(...), text: str = Form(...)):
    contents = await video.read()
    filename = video.filename
    
    # Ensure the uploads directory exists
    os.makedirs("uploads", exist_ok=True)
    
    # Save the video
    file_path = f"uploads/{filename}"
    with open(file_path, "wb") as f:
        f.write(contents)
    
    # Create a new task in the database
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute("INSERT INTO tasks (filename, status, result) VALUES (?, ?, ?)", (filename, 'pending', ''))
    task_id = c.lastrowid
    conn.commit()
    conn.close()
    
    # Start the video processing task
    loop = asyncio.get_event_loop()
    loop.run_in_executor(executor, process_video, file_path, task_id, text)
    
    return templates.TemplateResponse("upload.html", {
        "request": request,
        "message": f"Video '{filename}' uploaded successfully for {name}. Processing started in the background.",
        "task_id": task_id
    })

@router.get("/list-videos", response_class=HTMLResponse)
async def list_videos(request: Request):
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute("SELECT filename, status, result FROM tasks ORDER BY id DESC")
    videos = c.fetchall()
    conn.close()
    
    # Add the base URL for videos
    base_url = "/uploads/"
    
    return templates.TemplateResponse("list_videos.html", {
        "request": request, 
        "videos": videos,
        "base_url": base_url
    })