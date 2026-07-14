import datetime
import json
import os
import urllib.error
import urllib.request
from functools import wraps

import jwt
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy


load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///review.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('JWT_SECRET', 'BOU_DEV_SUPER_SECRET_2026')
app.config['NOTIFICATION_SERVICE_URL'] = os.getenv(
    'NOTIFICATION_SERVICE_URL',
    'http://127.0.0.1:5005'
)

db = SQLAlchemy(app)


class ReviewAssignment(db.Model):
    __tablename__ = 'review_assignments'
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, nullable=False)
    reviewer_id = db.Column(db.Integer, nullable=False)
    reviewer_type = db.Column(db.String(20), nullable=False)  # internal/external
    status = db.Column(db.String(50), default='pending_editorial_verification')
    assigned_by = db.Column(db.Integer, nullable=False)
    verified_by = db.Column(db.Integer, nullable=True)
    verify_reason = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)


class ReviewComment(db.Model):
    __tablename__ = 'review_comments'
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('review_assignments.id'), nullable=False)
    recommendation = db.Column(db.String(50), nullable=False)
    comments = db.Column(db.Text, nullable=False)
    verification_status = db.Column(db.String(30), default='pending')
    verification_reason = db.Column(db.Text, nullable=True)
    verified_by = db.Column(db.Integer, nullable=True)
    submitted_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    assignment = db.relationship('ReviewAssignment', backref='comments')


def send_notification(user_id, title, message, notification_type='review', related_submission_id=None):
    payload = {
        'user_id': user_id,
        'title': title,
        'message': message,
        'notification_type': notification_type,
        'related_submission_id': related_submission_id,
        'channel': 'in_app'
    }
    url = app.config['NOTIFICATION_SERVICE_URL'].rstrip('/') + '/notifications'
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    try:
        urllib.request.urlopen(req, timeout=3)
        return True
    except (urllib.error.URLError, TimeoutError):
        app.logger.warning('Notification service unavailable; continuing workflow.')
        return False


def token_required(required_roles=None):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                return jsonify({'message': 'Token is missing!'}), 401

            token = auth_header.split(' ')[1]
            try:
                data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            except jwt.ExpiredSignatureError:
                return jsonify({'message': 'Token has expired!'}), 401
            except jwt.InvalidTokenError:
                return jsonify({'message': 'Invalid token!'}), 401

            user_roles = data.get('roles', [])
            if required_roles and not any(role in user_roles for role in required_roles):
                return jsonify({'message': 'Permission denied'}), 403

            request.user_id = data['user_id']
            request.user_roles = user_roles
            return f(*args, **kwargs)
        return decorated
    return decorator


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'Review Service is running'}), 200


@app.route('/api/review-assignments', methods=['POST'])
@token_required(required_roles=['ResearchOfficer', 'Admin'])
def create_assignment():
    data = request.get_json() or {}
    required = ['submission_id', 'reviewer_id', 'reviewer_type']
    if not all(field in data for field in required):
        return jsonify({'message': 'submission_id, reviewer_id and reviewer_type are required'}), 400
    if data['reviewer_type'] not in ['internal', 'external']:
        return jsonify({'message': 'reviewer_type must be internal or external'}), 400

    assignment = ReviewAssignment(
        submission_id=data['submission_id'],
        reviewer_id=data['reviewer_id'],
        reviewer_type=data['reviewer_type'],
        assigned_by=request.user_id
    )
    db.session.add(assignment)
    db.session.commit()

    send_notification(
        request.user_id,
        'Reviewer assignment created',
        f'{data["reviewer_type"].title()} reviewer assignment is awaiting Editorial Board verification.',
        related_submission_id=data['submission_id']
    )

    return jsonify({
        'message': 'Review assignment created',
        'assignment_id': assignment.id,
        'status': assignment.status
    }), 201


@app.route('/api/review-assignments', methods=['GET'])
@token_required()
def list_assignments():
    assignments = ReviewAssignment.query.order_by(ReviewAssignment.id.desc()).all()
    return jsonify([
        {
            'id': item.id,
            'submission_id': item.submission_id,
            'reviewer_id': item.reviewer_id,
            'reviewer_type': item.reviewer_type,
            'status': item.status,
            'assigned_by': item.assigned_by,
            'verified_by': item.verified_by,
            'verify_reason': item.verify_reason
        }
        for item in assignments
    ]), 200


@app.route('/api/review-assignments/<int:assignment_id>/verify', methods=['PUT'])
@token_required(required_roles=['EditorialBoard', 'Admin'])
def verify_assignment(assignment_id):
    assignment = db.session.get(ReviewAssignment, assignment_id)
    if not assignment:
        return jsonify({'message': 'Review assignment not found'}), 404

    data = request.get_json() or {}
    approved = bool(data.get('approved'))
    assignment.status = 'verified' if approved else 'returned_to_research_officer'
    assignment.verified_by = request.user_id
    assignment.verify_reason = data.get('reason')
    assignment.updated_at = datetime.datetime.utcnow()
    db.session.commit()

    if approved:
        send_notification(
            assignment.reviewer_id,
            'Paper assigned for review',
            'A paper has been assigned to you for review.',
            related_submission_id=assignment.submission_id
        )
    else:
        send_notification(
            assignment.assigned_by,
            'Reviewer assignment returned',
            assignment.verify_reason or 'The Editorial Board returned the reviewer assignment.',
            related_submission_id=assignment.submission_id
        )

    return jsonify({'message': 'Assignment verification recorded', 'status': assignment.status}), 200


@app.route('/api/review-assignments/<int:assignment_id>/comments', methods=['POST'])
@token_required(required_roles=['InternalReviewer', 'ExternalReviewer', 'Admin'])
def submit_comments(assignment_id):
    assignment = db.session.get(ReviewAssignment, assignment_id)
    if not assignment:
        return jsonify({'message': 'Review assignment not found'}), 404
    if assignment.reviewer_id != request.user_id and 'Admin' not in request.user_roles:
        return jsonify({'message': 'You can only comment on assignments given to you'}), 403

    data = request.get_json() or {}
    if not data.get('recommendation') or not data.get('comments'):
        return jsonify({'message': 'recommendation and comments are required'}), 400

    comment = ReviewComment(
        assignment_id=assignment.id,
        recommendation=data['recommendation'],
        comments=data['comments']
    )
    assignment.status = 'comments_submitted'
    assignment.updated_at = datetime.datetime.utcnow()
    db.session.add(comment)
    db.session.commit()

    send_notification(
        assignment.assigned_by,
        'Reviewer comments submitted',
        'Reviewer comments are ready for Research Officer verification.',
        related_submission_id=assignment.submission_id
    )

    return jsonify({'message': 'Review comments submitted', 'comment_id': comment.id}), 201


@app.route('/api/review-comments/<int:comment_id>/verify', methods=['PUT'])
@token_required(required_roles=['ResearchOfficer', 'Admin'])
def verify_comments(comment_id):
    comment = db.session.get(ReviewComment, comment_id)
    if not comment:
        return jsonify({'message': 'Review comment not found'}), 404

    data = request.get_json() or {}
    approved = bool(data.get('approved'))
    comment.verification_status = 'approved' if approved else 'returned_to_reviewer'
    comment.verification_reason = data.get('reason')
    comment.verified_by = request.user_id
    db.session.commit()

    if not approved:
        send_notification(
            comment.assignment.reviewer_id,
            'Review comments returned',
            comment.verification_reason or 'Please revise your review comments.',
            related_submission_id=comment.assignment.submission_id
        )

    return jsonify({'message': 'Review comment verification recorded', 'status': comment.verification_status}), 200


with app.app_context():
    db.create_all()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003, debug=True)
