from fastapi import FastAPI

# Initialize the FastAPI application
app = FastAPI(title="BOU Identity & Access Service")

@app.get("/")
def read_root():
    return {"message": "Welcome to the Bank of Uganda Identity Service API!"}