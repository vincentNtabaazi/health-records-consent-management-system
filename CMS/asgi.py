"""
ASGI config for CMS project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""
# import pymysql
# pymysql.version_info = (2, 2, 1, "final", 0)
# pymysql.install_as_MySQLdb()

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CMS.settings')

application = get_asgi_application()
