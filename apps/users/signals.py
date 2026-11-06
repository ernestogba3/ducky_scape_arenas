from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import ProfileUser


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile_user(sender, instance, created, **kwargs):
    if created:
        ProfileUser.objects.create(user=instance, role='USUARIO')


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def save_profile_user(sender, instance, **kwargs):
    if hasattr(instance, 'profile_user'):
        instance.profile_user.save()
