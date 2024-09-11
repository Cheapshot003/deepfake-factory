from fastapi import FastAPI, APIRouter, Request, File, UploadFile, Form, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import os
import asyncio
import sqlite3
from concurrent.futures import ThreadPoolExecutor

app = FastAPI()
router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# Create a ThreadPoolExecutor
executor = ThreadPoolExecutor(max_workers=3)  # Adjust the number of workers as needed

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tasks
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  filename TEXT,
                  status TEXT)''')
    conn.commit()
    conn.close()

init_db()

def compress_video(file_path, task_id):
    # Implement your video compression logic here
    # This is a placeholder implementation
    print(f"Compressing video: {file_path}")
    # Simulate compression time
    import time
    time.sleep(10)
    print(f"Compression complete: {file_path}")
    
    # Update task status in the database
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute("UPDATE tasks SET status = 'completed' WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()

@router.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@router.get("/upload", response_class=HTMLResponse)
async def upload_form(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})

@router.post("/upload")
async def upload_video(request: Request, background_tasks: BackgroundTasks, video: UploadFile = File(...), text: str = Form(...), name: str = Form(...)):
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
    c.execute("INSERT INTO tasks (filename, status) VALUES (?, ?)", (filename, 'pending'))
    task_id = c.lastrowid
    conn.commit()
    conn.close()
    
    # Start the compression task
    loop = asyncio.get_event_loop()
    loop.run_in_executor(executor, compress_video, file_path, task_id)
    
    return templates.TemplateResponse("upload.html", {
        "request": request,
        "message": f"Video '{filename}' uploaded successfully for {name} with text: {text}. Compression started in the background.",
        "task_id": task_id
    })

@router.get("/compression-status/{task_id}")
async def compression_status(task_id: int):
    conn = sqlite3.connect('tasks.db')
    c = conn.cursor()
    c.execute("SELECT status FROM tasks WHERE id = ?", (task_id,))
    result = c.fetchone()
    conn.close()
    
    if result:
        return {"task_id": task_id, "status": result[0]}
    else:
        return {"task_id": task_id, "status": "not found"}

@router.get("/list-videos", response_class=HTMLResponse)
async def list_videos(request: Request):
    # Get list of videos from the uploads directory
    videos = [f for f in os.listdir("uploads") if os.path.isfile(os.path.join("uploads", f))]
    return templates.TemplateResponse("list_videos.html", {"request": request, "videos": videos})

app.include_router(router)

# If you're using uvicorn to run your app, you'd start it with:
# uvicorn main:app --reload