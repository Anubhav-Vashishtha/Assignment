import sqlite3
import json
from typing import Dict, List, Any
import logging
from datetime import datetime
import os
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class DataManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        
    def initialize_database(self):
        """Create database tables if they don't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create businesses table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS businesses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data JSON NOT NULL,
            created_at TEXT NOT NULL
        )
        ''')
        
        # Create directory_submissions table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS directory_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER NOT NULL,
            directory_url TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            response_data JSON,
            listing_status TEXT DEFAULT 'not_found',
            last_checked TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT,
            FOREIGN KEY (business_id) REFERENCES businesses (id)
        )
        ''')
        
        conn.commit()
        conn.close()
        
    def save_business_data(self, business_data: Dict) -> int:
        """Save business data and return the ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        cursor.execute(
            "INSERT INTO businesses (data, created_at) VALUES (?, ?)",
            (json.dumps(business_data), now)
        )
        
        business_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        
        return business_id
    
    def get_business_data(self, business_id: int) -> Dict:
        """Get business data by ID"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT data FROM businesses WHERE id = ?", (business_id,))
        row = cursor.fetchone()
        
        conn.close()
        
        if row:
            return json.loads(row['data'])
        return None
    
    def add_directory_url(self, business_id: int, directory_url: str):
        """Add a directory URL for a business"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        cursor.execute(
            """
            INSERT INTO directory_submissions 
            (business_id, directory_url, status, created_at) 
            VALUES (?, ?, ?, ?)
            """,
            (business_id, directory_url, "pending", now)
        )
        
        conn.commit()
        conn.close()
    
    def update_submission_status(self, business_id: int, directory_url: str, 
                                status: str, response_data: Dict = None):
        """Update the status of a directory submission"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        cursor.execute(
            """
            UPDATE directory_submissions
            SET status = ?, response_data = ?, updated_at = ?
            WHERE business_id = ? AND directory_url = ?
            """,
            (status, json.dumps(response_data) if response_data else None, 
             now, business_id, directory_url)
        )
        
        conn.commit()
        conn.close()
    
    def update_listing_status(self, business_id: int, directory_url: str, 
                             listing_status: str):
        """Update the listing status of a directory submission"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        cursor.execute(
            """
            UPDATE directory_submissions
            SET listing_status = ?, last_checked = ?, updated_at = ?
            WHERE business_id = ? AND directory_url = ?
            """,
            (listing_status, now, now, business_id, directory_url)
        )
        
        conn.commit()
        conn.close()
    
    def get_all_submission_statuses(self, business_id: int) -> List[Dict]:
        """Get statuses of all directory submissions for a business"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(
            """
            SELECT directory_url, status, response_data, listing_status, 
                   last_checked, created_at, updated_at
            FROM directory_submissions
            WHERE business_id = ?
            """,
            (business_id,)
        )
        
        rows = cursor.fetchall()
        
        statuses = []
        for row in rows:
            status_dict = dict(row)
            if status_dict['response_data']:
                status_dict['response_data'] = json.loads(status_dict['response_data'])
            statuses.append(status_dict)
        
        conn.close()
        
        return statuses
    
    def get_submissions_for_checking(self, business_id: int = None) -> List[Dict]:
        """Get submissions that need to be checked for listing status"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = """
            SELECT ds.id, ds.business_id, ds.directory_url, b.data,
                   ds.listing_status, ds.last_checked
            FROM directory_submissions ds
            JOIN businesses b ON ds.business_id = b.id
            WHERE ds.status = 'success' AND ds.listing_status != 'live'
        """
        
        params = []
        if business_id:
            query += " AND ds.business_id = ?"
            params.append(business_id)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        submissions = []
        for row in rows:
            submission = dict(row)
            if 'data' in submission:
                submission['data'] = json.loads(submission['data'])
            submissions.append(submission)
            
        conn.close()
        
        return submissions