# WHY: This script forces Flask to wake up and create the database tables.
# It does exactly what "flask initdb" was supposed to do, but without the command-line confusion.

from app import app, db

# Tell Flask we are ready to work
with app.app_context():
    # Create all the tables (Departments and Themes) in the database.db file
    db.create_all()
    print("SUCCESS! The database.db file and tables have been created!")
    