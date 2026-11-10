import os

class Config:
    DATABASE_URL = os.getenv(
        "DATABASE_URL", 
        "postgresql://predi_user:predi_password@analitica-db:5432/analitica_db"
    )
    EXISTENCIAS_SERVICE_URL = os.getenv(
        "EXISTENCIAS_SERVICE_URL", 
        "http://localhost:8000/api"
    )
    MODELS_STORAGE_PATH = os.getenv(
        "MODELS_STORAGE_PATH", 
        os.path.join(os.getcwd(), "models_storage")
    )
    PORT = int(os.getenv("PORT", 5000))
    DEBUG = os.getenv("FLASK_ENV") == "development"