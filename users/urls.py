from django.urls import path, include
from .views import *

app_name = 'users'

urlpatterns = [
    # path('', include('django.contrib.auth.urls')),
    path('login/', login_view, name='login_view'),
    path('signup/', signup_view, name='signup_view'),
    path('logout/', logout_view, name='logout_view'),
]
