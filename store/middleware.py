# store/middleware.py

from django.db import connection
from django.utils.deprecation import MiddlewareMixin

class SchemaSwitcherMiddleware(MiddlewareMixin):
    def process_request(self, request):
        user = getattr(request, 'user', None)
        if user and user.is_authenticated:
            schema_name = f"store_{user.username.lower()}"
            with connection.cursor() as cursor:
                cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name};")
            # Set schema for this request connection
            with connection.cursor() as cursor:
                cursor.execute(f"SET search_path TO {schema_name}, public;")
        else:
            # Use default schema for anonymous users
            with connection.cursor() as cursor:
                cursor.execute("SET search_path TO public;")
