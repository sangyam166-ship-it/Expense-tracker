from django.contrib.auth.models import User

class AutoLoginMiddleware:
    """
    Seamless auto-login middleware for direct instant access.
    Eliminates authentication login barriers so FINORA opens immediately.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Allow REST API v1 endpoints to enforce their own authentication credentials
        if request.path.startswith('/api/v1/'):
            return self.get_response(request)

        if not request.user.is_authenticated:
            user = User.objects.filter(is_active=True).first()
            if not user:
                user = User.objects.create_user(
                    username='finora_user',
                    email='user@finora.io',
                    password='FinoraDirectAccessKey123!',
                    first_name='Finora',
                    last_name='User'
                )
            request.user = user

        return self.get_response(request)
