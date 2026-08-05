from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import ManagerProfile


@receiver(post_save, sender=User)
def ensure_manager_profile(sender, instance, created, **kwargs):
    if created:
        ManagerProfile.objects.get_or_create(user=instance)
