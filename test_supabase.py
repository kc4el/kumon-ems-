import os
import django
from pathlib import Path
from urllib.parse import quote_plus
from dotenv import load_dotenv

# Load environment variables explicitly
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kumon_ems.settings')
django.setup()

from django.db import connection

def test_database_connection():
    try:
        raw_password = os.getenv('DB_PASSWORD', '')
        encoded_password = quote_plus(raw_password)
        
        print(f"\nAttempting connection to Supabase host: {os.getenv('DB_HOST')}")
        with connection.cursor() as cursor:
            cursor.execute("SELECT version();")
            db_version = cursor.fetchone()
            print("\nSUCCESS: Successfully connected to Supabase PostgreSQL!")
            print(f"Database Version: {db_version[0]}\n")
    except Exception as e:
        print("\nERROR: Failed to connect to Supabase PostgreSQL.")
        print(f"Details: {e}\n")

if __name__ == '__main__':
    test_database_connection()