"""
Context processors for FINORA.
Provides global user preferences (currency symbol, theme, notifications) across all templates.
"""

def finora_global_context(request):
    if not request.user.is_authenticated:
        return {
            'FINORA_APP_NAME': 'FINORA',
            'user_currency_symbol': '₹',
            'user_theme': 'dark',
            'unread_notifications_count': 0,
            'recent_notifications': [],
        }

    # Safe retrieval of profile and notifications
    try:
        from tracker.models import UserProfile, Notification, Category
        from django.db.models import Q
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        # Default to INR if not set
        if not profile.currency or profile.currency == 'USD':
            profile.currency = 'INR'
            profile.save()
        currency_symbol = profile.get_currency_symbol()
        theme = profile.theme or 'dark'
        unread_notifications_count = Notification.objects.filter(user=request.user, is_read=False).count()
        recent_notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:5]
        global_categories = Category.objects.filter(Q(user=request.user) | Q(user__isnull=True)).order_by('type', 'name')
    except Exception:
        profile = None
        currency_symbol = '₹'
        theme = 'dark'
        unread_notifications_count = 0
        recent_notifications = []
        global_categories = []

    return {
        'FINORA_APP_NAME': 'FINORA',
        'user_profile': profile,
        'user_currency_symbol': currency_symbol,
        'user_theme': theme,
        'unread_notifications_count': unread_notifications_count,
        'recent_notifications': recent_notifications,
        'global_categories': global_categories,
    }
