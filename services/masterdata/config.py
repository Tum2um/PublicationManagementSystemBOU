class Config:
    # The secret password to read your teammate's tokens
    JWT_SECRET = "BOU_DEV_SUPER_SECRET_2026"
    
    # FORCE the computer to use a local file called "database.db" 
    # DO NOT look for the bank's SQL Server.
    SQLALCHEMY_DATABASE_URI = "sqlite:///database.db"
    
    # Turn off a warning
    SQLALCHEMY_TRACK_MODIFICATIONS = False