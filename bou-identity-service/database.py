from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

# 1. Define where the database file will live on your computer.
# This will create a file named 'bou_identity.db' in your project folder.
SQLALCHEMY_DATABASE_URL = "sqlite:///./bou_identity.db"

# 2. Create the database engine. 
# The 'check_same_thread' argument is specific to SQLite and allows multiple API requests to access it safely.
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# 3. Create a SessionLocal class. Each instance of this class will be a distinct database session.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 4. Create a Base class. We will inherit from this class to create our database tables (models).
Base = declarative_base()

# 5. Helper function to get a database connection session. 
# This automatically closes the connection once an API request is finished.
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()