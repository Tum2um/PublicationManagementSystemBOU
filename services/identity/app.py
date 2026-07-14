# 1. Import the libraries we installed
import os
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
from functools import wraps
from dotenv import load_dotenv

# 2. Load environment variables from .env file
load_dotenv()

# 3. Create the Flask app
app = Flask(__name__)

# 4. Configure the database connection from .env
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///identity.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # disables a warning

# 5. Get the JWT secret from .env
app.config['SECRET_KEY'] = os.getenv('JWT_SECRET', 'BOU_DEV_SUPER_SECRET_2026')

# 6. Initialize the database object
db = SQLAlchemy(app)

# ---------- Database Models (Tables) ----------
# We define a User table and a Role table, plus a many-to-many relationship.

class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    # The backref lets us access user.roles easily.

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    # Many-to-many relationship with roles via a junction table
    roles = db.relationship('Role', secondary='user_roles', backref='users')

class UserRole(db.Model):
    __tablename__ = 'user_roles'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)

# ---------- Helper function: token_required (decorator for protected routes) ----------
def token_required(required_roles=None):
    """
    This decorator checks if the request has a valid JWT token.
    If required_roles is given (e.g., ['Admin']), it also checks the user has one of those roles.
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            token = None
            # The token should be in the Authorization header: "Bearer <token>"
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]

            if not token:
                return jsonify({'message': 'Token is missing!'}), 401

            try:
                # Decode the token using the secret key
                data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
                # data contains the payload we encoded (user_id, roles, exp)
                current_user_id = data['user_id']
                user_roles = data.get('roles', [])
            except jwt.ExpiredSignatureError:
                return jsonify({'message': 'Token has expired!'}), 401
            except jwt.InvalidTokenError:
                return jsonify({'message': 'Invalid token!'}), 401

            # If specific roles are required, check them
            if required_roles:
                if not any(role in user_roles for role in required_roles):
                    return jsonify({'message': 'You do not have permission to perform this action'}), 403

            # Attach user info to the request so the route can use it
            request.user_id = current_user_id
            request.user_roles = user_roles
            return f(*args, **kwargs)
        return decorated
    return decorator

# ---------- Routes (Endpoints) ----------

# 1. Health check - to test if the service is running
@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'Identity Service is running'}), 200

# 2. Register a new user (for now, we allow anyone to register, but later we'll restrict to Admin)
@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data:
        return jsonify({'message': 'No input data provided'}), 400

    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    role_names = data.get('roles', ['Author'])  # default role is Author

    # Basic validation
    if not name or not email or not password:
        return jsonify({'message': 'Name, email and password are required'}), 400

    # Check if user already exists
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({'message': 'User with this email already exists'}), 409

    # Hash the password
    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

    # Create new user
    new_user = User(name=name, email=email, password_hash=hashed_password)

    # Assign roles
    for role_name in role_names:
        role = Role.query.filter_by(name=role_name).first()
        if role:
            new_user.roles.append(role)
        else:
            # If role doesn't exist, we could create it, but for now we ignore or log
            pass

    db.session.add(new_user)
    db.session.commit()

    return jsonify({'message': 'User created successfully', 'user_id': new_user.id}), 201

# 3. Login - returns a JWT token
@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data:
        return jsonify({'message': 'No input data provided'}), 400

    email = data.get('email')
    password = data.get('password')

    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({'message': 'Invalid email or password'}), 401

    if not user.is_active:
        return jsonify({'message': 'Account is disabled'}), 403

    # Prepare roles list for the token
    user_roles = [role.name for role in user.roles]

    # Create JWT token with expiry (8 hours)
    payload = {
        'user_id': user.id,
        'email': user.email,
        'roles': user_roles,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=8)
    }
    token = jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')

    return jsonify({'token': token, 'user_id': user.id, 'roles': user_roles}), 200

# 4. Get current user profile (protected route)
@app.route('/api/auth/me', methods=['GET'])
@token_required()  # just requires a valid token, no specific role
def get_me():
    user = User.query.get(request.user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404
    return jsonify({
        'id': user.id,
        'name': user.name,
        'email': user.email,
        'roles': [role.name for role in user.roles],
        'is_active': user.is_active
    }), 200

# 5. Admin only: list all users (to test role-based access)
@app.route('/api/users', methods=['GET'])
@token_required(required_roles=['Admin'])
def list_users():
    users = User.query.all()
    result = []
    for user in users:
        result.append({
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'roles': [role.name for role in user.roles],
            'is_active': user.is_active
        })
    return jsonify(result), 200

# ---------- Create tables if they don't exist ----------
# We need to run this once when the app starts. We'll do it in the main block.
with app.app_context():
    db.create_all()
    # Also seed default roles if they don't exist
    for role_name in ['Admin', 'ResearchOfficer', 'EditorialBoard', 'InternalReviewer', 'ExternalReviewer', 'Author']:
        if not Role.query.filter_by(name=role_name).first():
            db.session.add(Role(name=role_name))
    db.session.commit()

# ---------- Run the app ----------
if __name__ == '__main__':
    # Run on all interfaces (0.0.0.0) so we can access from other machines if needed, port 5001
    app.run(host='0.0.0.0', port=5001, debug=True)
