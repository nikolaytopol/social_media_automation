# run.py

from flask import Flask
from web.your_app.views import webapp
import logging
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def create_app():
    # Point Flask to the correct template directory
    template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web', 'your_app', 'templates')
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web', 'your_app', 'static')
    
    app = Flask(__name__, 
                template_folder=template_dir,
                static_folder=static_dir)
    
    # Use a persistent secret key
    import secrets
    app.config['SECRET_KEY'] = 'ecbd0bba89d7d068804249d4e8d145b1'
    app.register_blueprint(webapp)
    return app

if __name__ == "__main__":
    app = create_app()
    # Changed port from 5000 to 5001 to avoid conflict with AirPlay
    app.run(debug=True, host="0.0.0.0", port=5004)
