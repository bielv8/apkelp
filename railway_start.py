#!/usr/bin/env python3
"""
Railway startup script
1. Initialize database tables
2. Start the Flask application
"""
import logging
import sys

logging.basicConfig(level=logging.INFO)

def main():
    logging.info("🚀 Starting Railway deployment...")
    
    # Step 1: Initialize database
    logging.info("📊 Step 1: Initializing database...")
    try:
        from init_db import init_database
        if not init_database():
            logging.error("❌ Database initialization failed!")
            sys.exit(1)
    except Exception as e:
        logging.error(f"❌ Database initialization error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Step 2: Start Flask app
    logging.info("🌐 Step 2: Starting Flask application...")
    try:
        from app import app
        port = int(os.environ.get('PORT', 5000))
        app.run(host='0.0.0.0', port=port)
    except Exception as e:
        logging.error(f"❌ Flask startup error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    import os
    main()
