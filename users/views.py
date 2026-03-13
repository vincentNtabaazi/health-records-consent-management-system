from django.contrib import messages
from django.contrib.auth import login, logout
from django.shortcuts import render, redirect
from .utils import authenticate
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password

User = get_user_model()

def signup_view(request):
    if request.method == "POST":
        first_name   = request.POST.get("first_name")
        last_name    = request.POST.get("last_name")
        email        = request.POST.get("email")
        organisation = request.POST.get("organisation")
        role         = request.POST.get("role")
        password1    = request.POST.get("password1")
        password2    = request.POST.get("password2")

        # Basic validation
        if password1 != password2:
            messages.error(request, "Passwords do not match.")
            return render(request, "users/login.html")

        if User.objects.filter(email=email).exists():
            messages.error(request, "A user with that email already exists.")
            return render(request, "users/login.html")

        # Create user (adjust username logic to your setup)
        user = User(
            first_name=first_name,
            last_name=last_name,
            email=email,
            organization_name=organisation,
            role=role,
        )

        # If your custom user still has username, set it:
        if hasattr(User, "username"):
            user.username = email

        user.password = make_password(password1)
        user.save()

        messages.success(request, "Account created successfully. You can now log in.")
        return redirect("users:login_view")

    return render(request, "users/signup.html")

def login_view(request):

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(password=password, username=username)

        if user is not None:
            login(request, user)
            messages.success(request, "Logged in successfully.")
            return redirect('pages:home')

        else:
            messages.error(request, 'Invalid credentials', extra_tags='danger')
            return redirect('users:login_view')

    return render(request, 'users/login.html')

def logout_view(request):
    logout(request)
    messages.success(request, "Logged out successfully.")
    return redirect('users:login_view')
