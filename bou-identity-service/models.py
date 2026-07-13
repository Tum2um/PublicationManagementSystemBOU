from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    """
    Represents a user account in the BOU Publication Management System.
    Maps directly to the attributes requested in Section 6 of the SRS.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False) # NFR-2: Passwords must be hashed securely
    is_active = Column(Boolean, default=True)      # Corresponds to user account status (Active/Deactivated)

    # Relationship to allow a user to hold multiple role designations (FR-1.4)
    roles = relationship("UserRole", back_populates="user", cascade="all, delete-orphan")


class UserRole(Base):
    """
    Tracks group memberships/roles assigned to a user (FR-1.3).
    A single user can have multiple entries here (e.g., Author AND Internal Reviewer).
    """
    __tablename__ = "user_roles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role_name = Column(String, nullable=False) # e.g., "Author", "Research Officer", "Internal Reviewer"

    # Link back to the parent User model
    user = relationship("User", back_populates="roles")