import os
import datetime
import json
import urllib.error
import urllib.request
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
import jwt
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///submission.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('JWT_SECRET', 'BOU_DEV_SUPER_SECRET_2026')
app.config['NOTIFICATION_SERVICE_URL'] = os.getenv(
    'NOTIFICATION_SERVICE_URL',
    'http://127.0.0.1:5005'
)

db = SQLAlchemy(app)


@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    return response


def send_notification(user_id, title, message, notification_type='info', related_submission_id=None):
    """
    Send an in-app notification through the Notification Service.
    If the notification service is down, the main submission workflow still continues.
    """
    payload = {
        'user_id': user_id,
        'title': title,
        'message': message,
        'notification_type': notification_type,
        'related_submission_id': related_submission_id,
        'channel': 'in_app'
    }
    url = app.config['NOTIFICATION_SERVICE_URL'].rstrip('/') + '/notifications'
    request_data = json.dumps(payload).encode('utf-8')
    notification_request = urllib.request.Request(
        url,
        data=request_data,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    try:
        urllib.request.urlopen(notification_request, timeout=3)
        return True
    except (urllib.error.URLError, TimeoutError):
        app.logger.warning('Notification service unavailable; continuing workflow.')
        return False

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
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

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
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
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
    uploaded_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
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


def build_tracking_steps(submission):
    stages = [
        ('submitted', 'Submitted'),
        ('assigned_internal_reviewer', 'Internal reviewer assigned'),
        ('internal_review', 'Internal review'),
        ('author_revision', 'Author revision'),
        ('revised_submission', 'Revision submitted'),
        ('external_review', 'External review if needed'),
        ('editorial_board', 'Editorial Board'),
        ('published', 'Publication decision')
    ]
    current_index = 0
    for index, (key, _label) in enumerate(stages):
        if submission.current_stage == key or submission.status == key:
            current_index = index
            break
    if submission.status in ['approved_for_publishing', 'published', 'declined']:
        current_index = len(stages) - 1

    return [
        {
            'key': key,
            'label': label,
            'state': 'completed' if index < current_index else 'current' if index == current_index else 'pending'
        }
        for index, (key, label) in enumerate(stages)
    ]


def serialize_submission(submission, include_details=False):
    result = {
        'id': submission.id,
        'title': submission.title,
        'status': submission.status,
        'current_stage': submission.current_stage,
        'call_id': submission.call_id,
        'theme_id': submission.theme_id,
        'theme_name': submission.theme.name if submission.theme else None,
        'corresponding_author_id': submission.corresponding_author_id,
        'created_at': submission.created_at.isoformat(),
        'tracking_steps': build_tracking_steps(submission)
    }
    if submission.call:
        result['call'] = {
            'id': submission.call.id,
            'fiscal_year': submission.call.fiscal_year,
            'abstract_deadline': submission.call.abstract_deadline.isoformat(),
            'paper_deadline': submission.call.paper_deadline.isoformat(),
            'status': submission.call.status
        }
    if include_details:
        result['authors'] = [
            {
                'id': a.id,
                'name': a.name,
                'email': a.email,
                'is_bou_staff': a.is_bou_staff,
                'department_id': a.department_id,
                'institution': a.institution,
                'is_corresponding': a.is_corresponding
            }
            for a in submission.authors
        ]
        result['documents'] = [
            {
                'id': d.id,
                'type': d.doc_type,
                'file_path': d.file_path,
                'uploaded_at': d.uploaded_at.isoformat(),
                'version_number': d.version_number
            }
            for d in submission.documents
        ]
    return result

# ---------- Routes ----------
# 1. Health check
@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'Submission Service is running'}), 200

# 2. Create a Call for Papers (Research Officer only)
@app.route('/api/calls', methods=['POST'])
@token_required(required_roles=['ResearchOfficer'])
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
    db.session.flush()

    for theme_name in data.get('themes', []):
        db.session.add(Theme(call_id=new_call.id, name=theme_name))

    db.session.commit()
    return jsonify({'message': 'Call created', 'call_id': new_call.id}), 201

# 3. Publish a Call (Research Officer only)
@app.route('/api/calls/<int:call_id>/publish', methods=['PUT'])
@token_required(required_roles=['ResearchOfficer'])
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
        status='submitted',
        current_stage='submitted'
    )
    db.session.add(new_submission)
    db.session.flush()  # to get the id

    for index, author_data in enumerate(data['authors']):
        author = Author(
            submission_id=new_submission.id,
            name=author_data['name'],
            email=author_data['email'],
            is_bou_staff=author_data.get('is_bou_staff', False),
            department_id=author_data.get('department_id'),
            institution=author_data.get('institution'),
            is_corresponding=author_data.get('is_corresponding', index == 0)
        )
        db.session.add(author)

    db.session.commit()
    send_notification(
        request.user_id,
        'Submission received',
        f'Your submission "{new_submission.title}" has been received and is awaiting review.',
        notification_type='submission',
        related_submission_id=new_submission.id
    )
    return jsonify({'message': 'Submission created', 'submission_id': new_submission.id}), 201


# 6. List submissions. Authors see their own submissions; staff roles see all.
@app.route('/api/submissions', methods=['GET'])
@token_required()
def list_submissions():
    staff_roles = {'ResearchOfficer', 'EditorialBoard', 'InternalReviewer', 'ExternalReviewer', 'Admin'}
    if staff_roles.intersection(set(request.user_roles)):
        submissions = Submission.query.order_by(Submission.id.desc()).all()
    else:
        submissions = Submission.query.filter_by(
            corresponding_author_id=request.user_id
        ).order_by(Submission.id.desc()).all()

    return jsonify([serialize_submission(item) for item in submissions]), 200


# 7. Update an author submission before or during requested revision.
@app.route('/api/submissions/<int:submission_id>', methods=['PUT'])
@token_required(required_roles=['Author'])
def update_submission(submission_id):
    submission = db.session.get(Submission, submission_id)
    if not submission:
        return jsonify({'message': 'Submission not found'}), 404
    if submission.corresponding_author_id != request.user_id:
        return jsonify({'message': 'You can only edit your own submissions'}), 403
    if submission.status in ['approved_for_publishing', 'published', 'declined']:
        return jsonify({'message': 'This submission can no longer be edited'}), 400

    data = request.get_json() or {}
    if data.get('title'):
        submission.title = data['title']
    if data.get('theme_id'):
        theme = db.session.get(Theme, data['theme_id'])
        if not theme or theme.call_id != submission.call_id:
            return jsonify({'message': 'Invalid theme for this call'}), 400
        submission.theme_id = theme.id

    if isinstance(data.get('authors'), list) and data['authors']:
        Author.query.filter_by(submission_id=submission.id).delete()
        for index, author_data in enumerate(data['authors']):
            db.session.add(Author(
                submission_id=submission.id,
                name=author_data['name'],
                email=author_data['email'],
                is_bou_staff=author_data.get('is_bou_staff', False),
                department_id=author_data.get('department_id'),
                institution=author_data.get('institution'),
                is_corresponding=author_data.get('is_corresponding', index == 0)
            ))

    submission.status = 'submitted'
    submission.current_stage = 'revised_submission' if data.get('is_revision') else submission.current_stage
    db.session.commit()

    send_notification(
        request.user_id,
        'Submission updated',
        f'Your submission "{submission.title}" has been updated.',
        notification_type='submission',
        related_submission_id=submission.id
    )
    return jsonify({'message': 'Submission updated', 'submission': serialize_submission(submission, True)}), 200


# 8. Delete an author submission before a final decision is made.
@app.route('/api/submissions/<int:submission_id>', methods=['DELETE'])
@token_required(required_roles=['Author'])
def delete_submission(submission_id):
    submission = db.session.get(Submission, submission_id)
    if not submission:
        return jsonify({'message': 'Submission not found'}), 404
    if submission.corresponding_author_id != request.user_id:
        return jsonify({'message': 'You can only delete your own submissions'}), 403
    if submission.status in ['approved_for_publishing', 'published', 'declined']:
        return jsonify({'message': 'This submission can no longer be deleted'}), 400

    Author.query.filter_by(submission_id=submission.id).delete()
    DocumentVersion.query.filter_by(submission_id=submission.id).delete()
    db.session.delete(submission)
    db.session.commit()
    return jsonify({'message': 'Submission deleted'}), 200


# 9. Staff update workflow status/stage after verification or publication decisions.
@app.route('/api/submissions/<int:submission_id>/status', methods=['PUT'])
@token_required(required_roles=['ResearchOfficer', 'EditorialBoard', 'Admin'])
def update_submission_status(submission_id):
    submission = db.session.get(Submission, submission_id)
    if not submission:
        return jsonify({'message': 'Submission not found'}), 404

    data = request.get_json() or {}
    if data.get('status'):
        submission.status = data['status']
    if data.get('current_stage'):
        submission.current_stage = data['current_stage']

    db.session.commit()

    if data.get('notify_author', True):
        decision_message = data.get('message') or f'Your submission "{submission.title}" is now at {submission.current_stage}.'
        send_notification(
            submission.corresponding_author_id,
            data.get('title', 'Submission status updated'),
            decision_message,
            notification_type='decision',
            related_submission_id=submission.id
        )

    return jsonify({'message': 'Submission status updated', 'submission': serialize_submission(submission, True)}), 200


# 10. Upload a document (abstract, paper, revision)
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
    timestamp = datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')
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
    send_notification(
        submission.corresponding_author_id,
        'Document uploaded',
        f'Your {doc_type} document for "{submission.title}" has been uploaded successfully.',
        notification_type='document',
        related_submission_id=submission.id
    )
    return jsonify({'message': 'File uploaded', 'document_id': doc.id}), 201

# 11. Get submission details (with authors and documents)
@app.route('/api/submissions/<int:submission_id>', methods=['GET'])
@token_required()
def get_submission(submission_id):
    submission = db.session.get(Submission, submission_id)
    if not submission:
        return jsonify({'message': 'Not found'}), 404
    staff_roles = {'ResearchOfficer', 'EditorialBoard', 'InternalReviewer', 'ExternalReviewer', 'Admin'}
    if submission.corresponding_author_id != request.user_id and not staff_roles.intersection(set(request.user_roles)):
        return jsonify({'message': 'Permission denied'}), 403

    return jsonify(serialize_submission(submission, True)), 200

# ---------- Create tables and initial data ----------
with app.app_context():
    db.create_all()
    # Optionally seed a sample call for testing (remove later)
    # if not Call.query.first():
    #     sample_call = Call(fiscal_year='2026/2027', description='Test Call', abstract_deadline=datetime.datetime.utcnow()+datetime.timedelta(days=30), paper_deadline=datetime.datetime.utcnow()+datetime.timedelta(days=60), status='published')
    #     db.session.add(sample_call)
    #     db.session.commit()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=True)
