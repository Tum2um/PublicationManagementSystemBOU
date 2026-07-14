# WHY: This is the "Engine" of your microservice. 
# When you run this, it starts a web server on your computer.

from flask import Flask, request, jsonify
from config import Config
from models import db, Department, Theme
import jwt
from functools import wraps

# 1. Create the Flask App
app = Flask(__name__)
app.config.from_object(Config)

# 2. Connect the database blueprint to the app
db.init_app(app)


@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    return response


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'Master Data Service is running'}), 200

# 3. Create the actual database file (database.db) if it doesn't exist.
# We put this inside a special check so it only runs when we manually tell it to.
@app.cli.command("initdb")
def initdb():
    db.create_all()
    print("SUCCESS: Database file 'database.db' and tables created!")

# ------------------- JWT HELPER (To read your teammate's tokens) -------------------
# WHY: When a user logs in via your teammate's service, they get a 'token'.
# This function checks if that token is valid so we trust the request.

def decode_token(token):
    try:
        # We use the SAME secret key to decode the token
        return jwt.decode(token, Config.JWT_SECRET, algorithms=['HS256'])
    except:
        return None

def require_auth(required_roles=None):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            # Look for the token in the request header
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                return jsonify({'error': 'Missing token'}), 401
            
            token = auth_header[7:]  # Remove the word "Bearer "
            payload = decode_token(token)
            if not payload:
                return jsonify({'error': 'Invalid or expired token'}), 401
            
            # If the endpoint requires an Admin role, check it here
            if required_roles:
                user_roles = payload.get('roles', [])
                if not any(role in user_roles for role in required_roles):
                    return jsonify({'error': 'Not an Admin'}), 403
            
            # Store user info for later use
            request.user = payload
            return f(*args, **kwargs)
        return decorated
    return decorator

# ------------------- DEPARTMENT ENDPOINTS -------------------
# WHY: These are the "URLs" the frontend will call to get or add departments.

@app.route('/api/departments', methods=['GET'])
@require_auth()  # Any logged-in user can view
def get_departments():
    # Ask the database for all active departments
    departments = Department.query.filter_by(is_active=True).all()
    # Convert them to a list of JSON objects and send back
    return jsonify([{'id': d.id, 'name': d.name} for d in departments])

@app.route('/api/departments', methods=['POST'])
@require_auth(required_roles=['Admin'])  # ONLY Admin can add
def create_department():
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'error': 'Name is required'}), 400
    
    # Create a new Department record
    dept = Department(name=data['name'])
    db.session.add(dept)
    db.session.commit()  # Save to database
    
    return jsonify({'id': dept.id, 'name': dept.name}), 201

@app.route('/api/departments/<int:dept_id>', methods=['PUT'])
@require_auth(required_roles=['Admin'])
def update_department(dept_id):
    dept = Department.query.get(dept_id)
    if not dept:
        return jsonify({'error': 'Not found'}), 404
    
    data = request.get_json()
    if 'name' in data:
        dept.name = data['name']
    if 'is_active' in data:
        dept.is_active = data['is_active']
    
    db.session.commit()
    return jsonify({'id': dept.id, 'name': dept.name, 'is_active': dept.is_active})

# ------------------- THEME ENDPOINTS (same as above) -------------------

@app.route('/api/themes', methods=['GET'])
@require_auth()
def get_themes():
    themes = Theme.query.filter_by(is_active=True).all()
    return jsonify([{'id': t.id, 'name': t.name} for t in themes])

@app.route('/api/themes', methods=['POST'])
@require_auth(required_roles=['Admin'])
def create_theme():
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'error': 'Name is required'}), 400
    theme = Theme(name=data['name'])
    db.session.add(theme)
    db.session.commit()
    return jsonify({'id': theme.id, 'name': theme.name}), 201

@app.route('/api/themes/<int:theme_id>', methods=['PUT'])
@require_auth(required_roles=['Admin'])
def update_theme(theme_id):
    theme = Theme.query.get(theme_id)
    if not theme:
        return jsonify({'error': 'Not found'}), 404
    data = request.get_json()
    if 'name' in data:
        theme.name = data['name']
    if 'is_active' in data:
        theme.is_active = data['is_active']
    db.session.commit()
    return jsonify({'id': theme.id, 'name': theme.name, 'is_active': theme.is_active})

# ------------------- START THE WEBSITE -------------------
with app.app_context():
    db.create_all()
    for name in [
        'Research Department',
        'Financial Markets Department',
        'Statistics Department',
        'Supervision Department',
        'National Payment Systems Department'
    ]:
        if not Department.query.filter_by(name=name).first():
            db.session.add(Department(name=name))
    for name in [
        'Macroeconomic Policy',
        'Financial Stability',
        'Monetary Policy',
        'Digital Financial Services',
        'External Sector Research'
    ]:
        if not Theme.query.filter_by(name=name).first():
            db.session.add(Theme(name=name))
    db.session.commit()


if __name__ == '__main__':
    # Port 5004 is YOUR assigned port. 
    # debug=True means it restarts automatically when you change code.
    app.run(host='0.0.0.0', port=5004, debug=True)
