import uvicorn
import socket
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.playapi import router as play_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("poker_api")

app = FastAPI(title="Poker Game API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(play_router, tags=["Poker Game"])

# Using a fixed port instead of finding an available one
if __name__ == "__main__":
    fixed_port = 8000
    logger.info(f"Starting server on port {fixed_port}")
    uvicorn.run("main:app", host="0.0.0.0", port=fixed_port, reload=True)