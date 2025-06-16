from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth.hashers import make_password
import logging

logger = logging.getLogger(__name__)

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        logger.info(f"pre_social_login called for {sociallogin.user.email}")
        super().pre_social_login(request, sociallogin)

    def save_user(self, request, sociallogin, form=None):
        logger.info(f"save_user called for {sociallogin.account.provider}")
        user = super().save_user(request, sociallogin, form)
        new_password = make_password(None)
        logger.info(f"Changing password from {user.password} to {new_password}")
        user.password = new_password
        user.save()
        return user