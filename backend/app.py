import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routes import (
    chat_router,
    map_router,
    measurements_router,
    mission_router,
    recommendations_router,
    weather_router,
)

app = FastAPI(title='Agribotics API V1')

cors_origins = [o.strip() for o in os.getenv('CORS_ORIGINS', '*').split(',') if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(chat_router)
app.include_router(measurements_router)
app.include_router(mission_router)
app.include_router(map_router)
app.include_router(recommendations_router)
app.include_router(weather_router)


@app.get('/')
def root():
    return {'message': 'Agribotics backend running'}
