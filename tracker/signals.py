from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import UserProfile, Category, Notification

@receiver(post_save, sender=User)
def create_user_profile_and_categories(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)

        # Seed standard expense categories
        for name, icon, color in Category.DEFAULT_EXPENSE_CATEGORIES:
            Category.objects.get_or_create(
                user=instance,
                name=name,
                type='EXPENSE',
                defaults={'icon': icon, 'color': color, 'is_default': True}
            )

        # Seed standard income categories
        for name, icon, color in Category.DEFAULT_INCOME_CATEGORIES:
            Category.objects.get_or_create(
                user=instance,
                name=name,
                type='INCOME',
                defaults={'icon': icon, 'color': color, 'is_default': True}
            )

        # Welcome notification
        Notification.objects.create(
            user=instance,
            title="Welcome to FINORA! 🚀",
            message="Your smart financial operating system is ready. Start by logging your first transaction or setting up a monthly budget.",
            type="SUCCESS",
            link="/dashboard/"
        )
