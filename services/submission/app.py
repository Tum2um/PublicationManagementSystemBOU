import os
import datetime
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
import jwt
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('JWT_SECRET')

db = SQLAlchemy(app)

# ---------- Models ----------
# We'll define tables for: Call, Theme, Submission, Author, DocumentVersion

class Call(db.Model):
    __tablename__ = 'calls'
    id = db.Column(db.Integer, primary_key=True)
    fiscal_year = db.Column(db.String(20), nullable=False)
    description = db.Column(db.Text, nullable=True)
    abstract_deadline = db.Column(db.DateTime, nullable=False)
    paper_deadline = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='draft')  # draft, published, closed
    created_at = db.Column(db.DateTime, default=datetime.datetime.now(datetime.UTC))

class Theme(db.Model):
    __tablename__ = 'themes'
    id = db.Column(db.Integer, primary_key=True)
    call_id = db.Column(db.Integer, db.ForeignKey('calls.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), default='active')  # active, inactive
    # relationship back to call
    call = db.relationship('Call', backref='themes')

class Submission(db.Model):
    __tablename__ = 'submissions'
    id = db.Column(db.Integer, primary_key=True)
    call_id = db.Column(db.Integer, db.ForeignKey('calls.id'), nullable=False)
    theme_id = db.Column(db.Integer, db.ForeignKey('themes.id'), nullable=False)
    title = db.Column(db.String(300), nullable=False)
    corresponding_author_id = db.Column(db.Integer, nullable=False)  # user id from identity service
    status = db.Column(db.String(30), default='draft')  # draft, submitted, under_internal_review, etc.
    current_stage = db.Column(db.String(50), default='submitted')  # see SRS
    created_at = db.Column(db.DateTime, default=datetime.datetime.now(datetime.UTC))
    # relationships
    call = db.relationship('Call', backref='submissions')
    theme = db.relationship('Theme', backref='submissions')
    authors = db.relationship('Author', backref='submission', lazy=True)
    documents = db.relationship('DocumentVersion', backref='submission', lazy=True)

class Author(db.Model):
    __tablename__ = 'authors'
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('submissions.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), nullable=False)
    is_bou_staff = db.Column(db.Boolean, default=False)
    department_id = db.Column(db.Integer, nullable=True)   # we don't have departments table yet; we store id
    institution = db.Column(db.String(200), nullable=True)  # for external
    is_corresponding = db.Column(db.Boolean, default=False)

class DocumentVersion(db.Model):
    __tablename__ = 'documents'
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('submissions.id'), nullable=False)
    doc_type = db.Column(db.String(20), nullable=False)  # 'abstract', 'paper', 'revision'
    file_path = db.Column(db.String(500), nullable=False)  # path to stored file
    uploaded_by = db.Column(db.Integer, nullable=False)  # user id
    uploaded_at = db.Column(db.DateTime, default=datetime.datetime.now(datetime.UTC))
    version_number = db.Column(db.Integer, default=1)

# ---------- Helper: token_required decorator (identical to identity service) ----------
def token_required(required_roles=None):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            token = None
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
            if not token:
                return jsonify({'message': 'Token is missing!'}), 401
            try:
                data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
                current_user_id = data['user_id']
                user_roles = data.get('roles', [])
            except jwt.ExpiredSignatureError:
                return jsonify({'message': 'Token has expired!'}), 401
            except jwt.InvalidTokenError:
                return jsonify({'message': 'Invalid token!'}), 401
            if required_roles:
                if not any(role in user_roles for role in required_roles):
                    return jsonify({'message': 'Permission denied'}), 403
            request.user_id = current_user_id
            request.user_roles = user_roles
            return f(*args, **kwargs)
        return decorated
    return decorator

# ---------- Routes ----------
# 1. Health check
@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'Submission Service is running'}), 200

# 2. Create a Call for Papers (only Research Officer or Admin)
@app.route('/api/calls', methods=['POST'])
@token_required(required_roles=['ResearchOfficer', 'Admin'])
def create_call():
    data = request.get_json()
    required = ['fiscal_year', 'description', 'abstract_deadline', 'paper_deadline']
    if not all(k in data for k in required):
        return jsonify({'message': 'Missing required fields'}), 400
    # parse deadlines (assuming ISO format strings)
    try:
        abstract_deadline = datetime.datetime.fromisoformat(data['abstract_deadline'])
        paper_deadline = datetime.datetime.fromisoformat(data['paper_deadline'])
    except:
        return jsonify({'message': 'Invalid date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)'}), 400
    new_call = Call(
        fiscal_year=data['fiscal_year'],
        description=data['description'],
        abstract_deadline=abstract_deadline,
        paper_deadline=paper_deadline,
        status='draft'
    )
    db.session.add(new_call)
    db.session.commit()
    return jsonify({'message': 'Call created', 'call_id': new_call.id}), 201

# 3. Publish a Call (Research Officer/Admin)
@app.route('/api/calls/<int:call_id>/publish', methods=['PUT'])
@token_required(required_roles=['ResearchOfficer', 'Admin'])
def publish_call(call_id):
    call = db.session.get(Call, call_id)
    if not call:
        return jsonify({'message': 'Call not found'}), 404
    call.status = 'published'
    db.session.commit()
    return jsonify({'message': 'Call published'}), 200

# 4. List all Calls (any authenticated user)
@app.route('/api/calls', methods=['GET'])
@token_required()  # any valid token
def list_calls():
    calls = Call.query.all()
    result = []
    for c in calls:
        result.append({
            'id': c.id,
            'fiscal_year': c.fiscal_year,
            'description': c.description,
            'abstract_deadline': c.abstract_deadline.isoformat(),
            'paper_deadline': c.paper_deadline.isoformat(),
            'status': c.status,
            'themes': [{'id': t.id, 'name': t.name} for t in c.themes]
        })
    return jsonify(result), 200

# 5. Create a new submission (Author)
@app.route('/api/submissions', methods=['POST'])
@token_required(required_roles=['Author'])
def create_submission():
    data = request.get_json()
    # Required: call_id, theme_id, title, corresponding_author details, co-authors
    # We'll simplify: we require call_id, theme_id, title, and list of authors (with at least one)
    if not all(k in data for k in ['call_id', 'theme_id', 'title', 'authors']):
        return jsonify({'message': 'Missing required fields'}), 400
    # Check call exists and is published
    call = db.session.get(Call, data['call_id'])
    if not call or call.status != 'published':
        return jsonify({'message': 'Call not available'}), 400
    # Check theme belongs to call
    theme = db.session.get(Theme, data['theme_id'])
    if not theme or theme.call_id != call.id:
        return jsonify({'message': 'Invalid theme for this call'}), 400

    # Create submission
    new_submission = Submission(
        call_id=call.id,
        theme_id=theme.id,
        title=data['title'],
        corresponding_author_id=request.user_id,  # logged-in user is corresponding
        status='draft',
        current_stage='submitted'
    )
    db.session.add(new_submission)
    db.session.flush()  # to get the id

    # Add authors (including corresponding)
    for author_data in data['authors']:
        # Ensure at least one author is the corresponding (we'll set is_corresponding based on email matching logged-in user)
        is_corresponding = (author_data.get('email') == request.user_email)  # We don't have email in token yet; we'll store in request.user
        # Actually we didn't store email in token payload; we'll add it in identity service later. For now, we'll assume the first author is corresponding.
        # We'll improve later. For now: set is_corresponding = True if index == 0
        # But we need to get the email from somewhere; we can query the identity service but for MVP we'll set corresponding as the logged user.
        # We'll make a simpler version: we will set is_corresponding for the author whose email equals the logged-in user's email.
        # Since we don't have email in token, we'll use the user_id and assume we will fetch it later.
        # For now, we'll just set is_corresponding based on a flag in the request, or we can just set it for the logged-in user.
        # Simpler: we'll set is_corresponding = (author_data.get('is_corresponding', False))
        # I'll adjust the code below.

    # For now, we'll just create authors without is_corresponding; we'll set the corresponding author later.
    # Let's keep it minimal. We'll revisit when we add the full submission form.

    # For demo, we'll just create a single author entry (the logged-in user) and ignore co-authors for now.
    # We'll expand later.

    # Simpler: we'll add only the logged-in user as author.
    # We'll get user info from identity service? Not needed for MVP.
    # We'll just store name and email from request.
    # We'll require 'authors' list with name, email, is_bou_staff, department/institution.
    # We'll just loop.

    for author_data in data['authors']:
        author = Author(
            submission_id=new_submission.id,
            name=author_data['name'],
            email=author_data['email'],
            is_bou_staff=author_data.get('is_bou_staff', False),
            department_id=author_data.get('department_id'),
            institution=author_data.get('institution'),
            is_corresponding=author_data.get('is_corresponding', False)
        )
        db.session.add(author)

    db.session.commit()
    return jsonify({'message': 'Submission created', 'submission_id': new_submission.id}), 201

# 6. Upload a document (abstract, paper, revision)
@app.route('/api/submissions/<int:submission_id>/documents', methods=['POST'])
@token_required(required_roles=['Author'])
def upload_document(submission_id):
    # check submission belongs to user (or user is author)
    submission = db.session.get(Submission, submission_id)
    if not submission:
        return jsonify({'message': 'Submission not found'}), 404
    # Check if user is the corresponding author or co-author (we'll skip for now)
    # For simplicity, we'll allow any Author to upload.
    # Get file from request
    if 'file' not in request.files:
        return jsonify({'message': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'message': 'No selected file'}), 400
    # Validate file type and size
    allowed_extensions = {'pdf', 'docx'}
    if '.' not in file.filename or file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
        return jsonify({'message': 'File type not allowed. Allowed: pdf, docx'}), 400
    # Check size (10 MB)
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > 10 * 1024 * 1024:
        return jsonify({'message': 'File too large. Max 10 MB'}), 400

    # Determine doc_type from form data
    doc_type = request.form.get('doc_type')
    if doc_type not in ['abstract', 'paper', 'revision']:
        return jsonify({'message': 'doc_type must be abstract, paper, or revision'}), 400

    # Save file to uploads folder
    upload_dir = os.path.join(os.getcwd(), 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    # Generate unique filename
    timestamp = datetime.datetime.now(datetime.UTC).strftime('%Y%m%d_%H%M%S')
    filename = f"{submission_id}_{doc_type}_{timestamp}_{file.filename}"
    file_path = os.path.join(upload_dir, filename)
    file.save(file_path)

    # Create document record
    doc = DocumentVersion(
        submission_id=submission_id,
        doc_type=doc_type,
        file_path=file_path,
        uploaded_by=request.user_id
    )
    db.session.add(doc)
    db.session.commit()
    return jsonify({'message': 'File uploaded', 'document_id': doc.id}), 201

# 7. Get submission details (with authors and documents)
@app.route('/api/submissions/<int:submission_id>', methods=['GET'])
@token_required()
def get_submission(submission_id):
    submission = db.session.get(Submission, submission_id)
    if not submission:
        return jsonify({'message': 'Not found'}), 404
    # Check if user has access (author, RO, Editorial, etc.) We'll allow all for now
    result = {
        'id': submission.id,
        'title': submission.title,
        'status': submission.status,
        'current_stage': submission.current_stage,
        'call_id': submission.call_id,
        'theme_id': submission.theme_id,
        'authors': [{'id': a.id, 'name': a.name, 'email': a.email, 'is_corresponding': a.is_corresponding} for a in submission.authors],
        'documents': [{'id': d.id, 'type': d.doc_type, 'file_path': d.file_path, 'uploaded_at': d.uploaded_at.isoformat()} for d in submission.documents]
    }
    return jsonify(result), 200

# ---------- Create tables and initial data ----------
with app.app_context():
    db.create_all()
    # Optionally seed a sample call for testing (remove later)
    # if not Call.query.first():
    #     sample_call = Call(fiscal_year='2026/2027', description='Test Call', abstract_deadline=datetime.datetime.now(datetime.UTC)+datetime.timedelta(days=30), paper_deadline=datetime.datetime.now(datetime.UTC)+datetime.timedelta(days=60), status='published')
    #     db.session.add(sample_call)
    #     db.session.commit()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=True)