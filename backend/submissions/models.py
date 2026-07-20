from django.conf import settings
from django.db import models


class Call(models.Model):
    fiscal_year = models.CharField(max_length=20)
    description = models.TextField(blank=True)
    abstract_deadline = models.DateTimeField()
    paper_deadline = models.DateTimeField()
    status = models.CharField(max_length=20, default="draft")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.fiscal_year


class Theme(models.Model):
    call = models.ForeignKey(Call, on_delete=models.CASCADE, related_name="themes")
    name = models.CharField(max_length=200)
    status = models.CharField(max_length=20, default="active")

    def __str__(self):
        return self.name


class Submission(models.Model):
    call = models.ForeignKey(Call, on_delete=models.CASCADE, related_name="submissions")
    theme = models.ForeignKey(Theme, on_delete=models.PROTECT, related_name="submissions")
    title = models.CharField(max_length=300)
    corresponding_author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    status = models.CharField(max_length=40, default="submitted")
    current_stage = models.CharField(max_length=60, default="submitted")
    decision_reason = models.TextField(blank=True)
    publication_reference = models.CharField(max_length=80, blank=True)
    publication_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class SubmissionAuthor(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="authors")
    name = models.CharField(max_length=200)
    email = models.EmailField()
    is_bou_staff = models.BooleanField(default=False)
    department_id = models.IntegerField(null=True, blank=True)
    institution = models.CharField(max_length=200, blank=True)
    is_corresponding = models.BooleanField(default=False)


class DocumentVersion(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="documents")
    doc_type = models.CharField(max_length=20)
    file = models.FileField(upload_to="submission_documents/")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    version_number = models.IntegerField(default=1)
