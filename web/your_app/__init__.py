from flask import Flask
from web.your_app.views import webapp

def create_app():
    app = Flask(__name__)
    app.register_blueprint(webapp)
    return app
