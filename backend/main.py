from fastapi import FastAPI
from backend.core.config import settings

app = FastAPI(title=settings.PROJECT_NAME)

@app.get('/')
def read_root():
    return {'message': 'Welcome to Observatory API'}
