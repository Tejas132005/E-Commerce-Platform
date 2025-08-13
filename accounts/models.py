# accounts/models.py

from django.db import models
from django.utils import timezone
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin

class CustomUserManager(BaseUserManager):
    def create_user(self, phone, email, username, password=None, **extra_fields):
        if not phone:
            raise ValueError("Phone Number Required")
        if not email:
            raise ValueError("Email is required")
        if not username:
            raise ValueError("Username is required")
            
        email = self.normalize_email(email)
        user = self.model(phone=phone, email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        
        return user

    def create_superuser(self, phone, email, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(phone, email, username, password, **extra_fields)

class CustomUser(AbstractBaseUser, PermissionsMixin):
    phone = models.CharField(max_length=15, unique=True, primary_key=True)
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=100, unique=True)
    dob = models.DateField()
    location = models.CharField(max_length=255)
    company_name = models.CharField(max_length=100, blank=True)
    is_paid = models.BooleanField(default=False)
    subscription_expiry = models.DateTimeField(null=True, blank=True)
    
    # Required fields for Django admin
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = CustomUserManager()

    USERNAME_FIELD = 'phone'
    REQUIRED_FIELDS = ['email', 'username']

    def __str__(self):
        return f"{self.username} ({self.phone})"

    def return_username(self):
        return self.username

    @property
    def is_subscription_active(self):
        """Check if user's subscription is still active"""
        if not self.is_paid or not self.subscription_expiry:
            return False
        return self.subscription_expiry > timezone.now()

class Subscription(models.Model):
    TIER_CHOICES = [
        ('free', 'Free'),
        ('pro', 'Pro'),
    ]
    
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='subscription')
    tier = models.CharField(max_length=20, choices=TIER_CHOICES, default='free')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.tier}"