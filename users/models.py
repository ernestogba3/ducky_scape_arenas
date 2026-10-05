from django.contrib.auth.models import User
from django.db import models


class ProfileUser(models.Model):
    ROLE_CHOICES = [
        ('USUARIO', 'Usuario'),
        ('PREMIUM', 'Premium'),
        ('ADMIN', 'Admin'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile_user')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='USUARIO')
    bio = models.TextField(blank=True, null=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.user.username


