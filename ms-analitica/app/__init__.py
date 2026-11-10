from flask import Flask
from app.database import engine, Base
from app.routes.pipeline_routes import pipeline_bp
from app.routes.reports_routes import reports_bp

def create_app():
    app = Flask(__name__)
    Base.metadata.create_all(bind=engine)

    app.register_blueprint(pipeline_bp)
    app.register_blueprint(reports_bp)

    @app.route('/health', methods=['GET'])
    def health():
        return {"status": "UP", "service": "analytics"}, 200

    return app