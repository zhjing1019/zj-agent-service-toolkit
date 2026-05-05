from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config.settings import settings

class Database:
    def __init__(self):
        if settings.DB_TYPE == "sqlite":
            self.engine = create_engine(f"sqlite:///{settings.SQLITE_PATH}")
        elif settings.DB_TYPE == "mysql":
            self.engine = create_engine(f"mysql+pymysql://...")
        
        self.Session = sessionmaker(bind=self.engine)

    def get_session(self):
        return self.Session()

db = Database()