import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dicom_project.settings')
django.setup()

from dicom_app.models import Member

valid_roles = [choice[0] for choice in Member.ROLE_CHOICES]
print(f"Valid roles: {valid_roles}")

members = Member.objects.all()
all_valid = True
for member in members:
    if member.role not in valid_roles:
        print(f"INVALID ROLE: {member.role} for member {member}")
        all_valid = False
    else:
        print(f"Valid role: {member.role} for member {member}")

if all_valid:
    print("SUCCESS: All members have valid roles.")
else:
    print("FAILURE: Some members have invalid roles.")
