from fastapi import FastAPI, File, UploadFile, Form, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from typing import Dict, List, Optional
import json
import csv
import io
import os
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from pydantic import BaseModel

from directory_agent import DirectoryAgent
from data_manager import DataManager
from listing_checker import ListingChecker

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("seo_agent.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(title="SEO Directory Submission Agent")

# Mount static files
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize components
data_manager = DataManager("seo_data.db")
listing_checker = ListingChecker(data_manager)

# Initialize scheduler
scheduler = BackgroundScheduler()
scheduler.start()

# Models
class BusinessData(BaseModel):
    company_name: str
    tagline: str
    website_url: str
    email: str
    phone: str
    password: str
    business_description: str
    social_media_links: Dict[str, str]
    founder_name: str
    business_category: str
    keywords: List[str]
    address: str
    location: Dict[str, str]  # city, state, country, zip

@app.on_event("startup")
async def startup_event():
    # Create tables if they don't exist
    data_manager.initialize_database()
    
    # Schedule weekly listing checker
    scheduler.add_job(
        listing_checker.check_all_listings,
        trigger=IntervalTrigger(weeks=1),
        id='listing_checker',
        name='Weekly Listing Check',
        replace_existing=True
    )
    logger.info("Weekly listing checker scheduled")

@app.on_event("shutdown")
async def shutdown_event():
    scheduler.shutdown()

@app.get("/", response_class=HTMLResponse)
async def get_home():
    with open("static/index.html", "r") as f:
        return f.read()

@app.post("/submit-business-data")
async def submit_business_data(business_data: BusinessData):
    business_id = data_manager.save_business_data(business_data.dict())
    return {"status": "success", "business_id": business_id}

@app.post("/upload-csv")
async def upload_csv_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    business_id: int = Form(...)
):
    content = await file.read()
    csv_content = content.decode('utf-8')
    csv_reader = csv.reader(io.StringIO(csv_content))
    
    urls = []
    for row in csv_reader:
        if row and row[0].strip():
            url = row[0].strip()
            urls.append(url)
            data_manager.add_directory_url(business_id, url)
    
    # Start processing in background
    background_tasks.add_task(process_directories, business_id, urls)
    
    return {"status": "success", "message": f"Processing {len(urls)} directories in the background"}

async def process_directories(business_id: int, urls: List[str]):
    business_data = data_manager.get_business_data(business_id)
    
    for url in urls:
        try:
            logger.info(f"Processing directory: {url}")
            agent = DirectoryAgent(business_data)
            result = agent.submit_to_directory(url)
            
            # Save result
            data_manager.update_submission_status(
                business_id=business_id,
                directory_url=url,
                status=result["status"],
                response_data=result
            )
        except Exception as e:
            logger.error(f"Error processing {url}: {str(e)}")
            data_manager.update_submission_status(
                business_id=business_id,
                directory_url=url,
                status="error",
                response_data={"error": str(e)}
            )

@app.get("/status/{business_id}")
async def get_status(business_id: int):
    statuses = data_manager.get_all_submission_statuses(business_id)
    return {"statuses": statuses}

@app.post("/check-listings/{business_id}")
async def trigger_listing_check(business_id: int, background_tasks: BackgroundTasks):
    background_tasks.add_task(listing_checker.check_listings_for_business, business_id)
    return {"status": "success", "message": "Listing check triggered"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
