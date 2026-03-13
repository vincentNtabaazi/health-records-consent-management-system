import re
from django.contrib.auth import get_user_model

def check_if_email(username):
    email_regex = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
    if re.match(email_regex, username):
        return username
    else:
        return None

def authenticate(password, username):
    email = check_if_email(username)
    User = get_user_model()

    try:
        if email:
            user = User.objects.get(email=email)
            if user.check_password(password):
                return user
            return None
        elif username:
            user = User.objects.get(username=username)
            if user.check_password(password):
                return user
            return None
    except User.DoesNotExist:
        return None
