from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("reviews", "0001_initial")]
    operations = [
        migrations.AddField(
            model_name="reviewcomment",
            name="attachment",
            field=models.FileField(blank=True, null=True, upload_to="review_documents/"),
        ),
    ]
