from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.routes import router

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(router)

templates = Jinja2Templates(directory="app/templates")