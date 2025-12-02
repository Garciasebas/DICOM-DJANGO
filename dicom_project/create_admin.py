
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dicom_project.settings')
django.setup()

from django.contrib.auth.models import User

username = 'admin'
password = 'admin123'
email = 'admin@example.com'

if not User.objects.filter(username=username).exists():
    print(f"Creating user {username}...")
    User.objects.create_superuser(username, email, password)
    print(f"User {username} created successfully.")
else:
    print(f"User {username} already exists. Updating password...")
    user = User.objects.get(username=username)
    user.set_password(password)
    user.save()
    print(f"User {username} password updated.")
