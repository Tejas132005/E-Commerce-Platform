from django.db import models
from django.utils import timezone
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin

class CustomUserManager(BaseUserManager):
    def create_user(self, phone, email, username, password=None, **extra_fields):
        if not phone:
            raise ValueError("Phone Number Required")
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(phone=phone, email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

class CustomUser(AbstractBaseUser, PermissionsMixin):
    phone = models.CharField(max_length=15, unique=True, primary_key=True)
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=100)
    dob = models.DateField()
    location = models.CharField(max_length=255)
    company_name = models.CharField(max_length=100, blank=True)
    is_paid = models.BooleanField(default=False)
    subscription_expiry = models.DateTimeField(null=True, blank=True)
    

    objects = CustomUserManager()
    USERNAME_FIELD = 'phone'
    REQUIRED_FIELDS = ['email', 'username']

    

    def return_username(self):
        return self.username

class Subscription(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='subscription')
    tier = models.CharField(max_length=20, default='free')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.tier}"
