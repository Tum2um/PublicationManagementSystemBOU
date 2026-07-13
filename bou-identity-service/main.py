from datetime import timedelta
from typing import Annotated

import jwt
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jwt.exceptions import InvalidTokenError
from sqlalchemy.orm import Session

import models
import schemas
from database import engine, get_db
from security import (
    get_password_hash, verify_password, create_access_token,
    SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES,
)

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="BOU Identity & Access Service")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


@app.get("/")
def read_root():
    return {"message": "Welcome to the Bank of Uganda Identity Service API!"}


@app.post("/users/register", response_model=schemas.UserResponse)
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    new_user = models.User(
        name=user.name, email=user.email,
        password_hash=get_password_hash(user.password),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@app.post("/token", response_model=schemas.Token)
def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: Session = Depends(get_db)):
    # OAuth2's standard form always calls the identifier field "username" —
    # we're just using the user's email in that field.
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Account is deactivated")

    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: Session = Depends(get_db)) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if email is None:
            raise credentials_exception
    except InvalidTokenError:
        raise credentials_exception

    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None:
        raise credentials_exception
    return user


@app.get("/users/me", response_model=schemas.UserResponse)
def read_current_user(current_user: Annotated[models.User, Depends(get_current_user)]):
    return current_user


# --- RBAC helper: reuse this pattern for every protected route across ALL your services ---
def require_roles(*allowed_roles: str):
    def role_checker(current_user: Annotated[models.User, Depends(get_current_user)]) -> models.User:
        user_roles = {r.role_name for r in current_user.roles}
        if not user_roles.intersection(allowed_roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
        return current_user
    return role_checker


@app.get("/admin/ping")
def admin_ping(current_user: Annotated[models.User, Depends(require_roles("System Administrator"))]):
    return {"message": f"Hello Administrator {current_user.name}"}