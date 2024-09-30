from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.routes import router
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/audio", StaticFiles(directory="audio"), name="audio")
app.include_router(router)

templates = Jinja2Templates(directory="app/templates")