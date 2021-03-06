import base64
import random

import requests
from allauth.socialaccount.models import SocialAccount
from allauth.socialaccount.providers.kakao.views import KakaoOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from dj_rest_auth.registration.views import SocialLoginView
from django.conf import settings
from django.contrib import auth
from django.contrib.auth.hashers import make_password, check_password
from django.core.files.base import ContentFile
from django.core.mail import send_mail
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.generics import *
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.serializers import *
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError

from config.settings.base import SOCIAL_OAUTH_CONFIG

BASE_URL = "https://baedalius.com/"  # deploy version
# BASE_URL = "http://localhost:8000/"  # local version

KAKAO_CLIENT_ID = SOCIAL_OAUTH_CONFIG['KAKAO_REST_API_KEY']
KAKAO_REDIRECT_URI = f"{BASE_URL}{SOCIAL_OAUTH_CONFIG['KAKAO_REDIRECT_URI']}"
KAKAO_CLIENT_SECRET = SOCIAL_OAUTH_CONFIG['KAKAO_SECRET_KEY']

authenticate_num_dict = {}


class UserCreateAPIView(CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = UserCreateSerializer

    def post(self, request, *args, **kwargs):

        email = request.data['email']
        avatar = request.data['avatar']

        user_data = {
            'username': request.data['username'],
            'email': email,
            'password': make_password(request.data['password'])
        }

        serializer = self.serializer_class(data=user_data)

        if serializer.is_valid(raise_exception=False):
            user = serializer.create(user_data)
            token = RefreshToken.for_user(user)
            refresh = str(token)
            access = str(token.access_token)

        else:
            print(serializer.errors)
            return Response({"status": status.HTTP_400_BAD_REQUEST})

        # ???????????? ????????? ????????? ??????
        if avatar:
            imgdata = base64.b64decode(avatar)
            with open(f"media/images/avatar/{email}-avatar.jpg", 'wb') as f:
                f.write(imgdata)

            user = User.objects.get(email=email)
            user.avatar = f"images/avatar/{email}-avatar.jpg"
            user.save()

        return JsonResponse(
            {"status": status.HTTP_201_CREATED, "user": user.pk, "access": access, "refresh": refresh})


class EmailSendView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = EmailSendSerializer

    def post(self, request):
        random_num = int(random.random() * 1000000)
        print("random_num", random_num)
        message = f"??????????????? ?????? ????????? ????????? ?????? ?????? ???????????????.\n{random_num}"

        authenticate_num_dict[request.data['email']] = random_num

        mail_title = "??????????????? ?????? ???????????? ???????????????"
        mail_to = request.data['email']
        send_mail(mail_title, message, None, [mail_to], fail_silently=False)

        return JsonResponse({"status": status.HTTP_200_OK, "data": {"random_num": random_num}})


class EmailVerifyView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = EmailVerifySerializer

    def post(self, request):
        if request.data['email'] in authenticate_num_dict and \
                authenticate_num_dict[request.data['email']] == request.data['random_num']:
            authenticate_num_dict.pop(request.data['email'])
            return Response({"status": status.HTTP_200_OK, "data": {"email": request.data['email']}})
        else:
            return Response({"status": status.HTTP_400_BAD_REQUEST})


class UserLoginAPIView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = UserLoginSerializer

    def post(self, request):
        serializer = self.serializer_class

        request_email = request.data['email']
        request_password = request.data['password']

        try:
            user = User.objects.get(email=request_email)  # ????????? ????????? ????????? DoesNotExist ????????????
            user_password = user.password
            if check_password(request_password, user_password):
                token = RefreshToken.for_user(user)
                refresh = str(token)
                access = str(token.access_token)

                return JsonResponse({"status": status.HTTP_201_CREATED, "user": user.pk, "refresh": refresh, "access": access})  # ???????????????
            else:
                return JsonResponse(
                    {"status": status.HTTP_400_BAD_REQUEST})  # ???????????????

        except User.DoesNotExist:
            return JsonResponse(
                {"status": status.HTTP_401_UNAUTHORIZED})  # ??????????????? 2


class UserLogoutAPIView(APIView):
    def post(self, request):
        response = Response({"status": status.HTTP_200_OK})

        if 'rest_framework_simplejwt.token_blacklist' in settings.INSTALLED_APPS:
            try:
                token = RefreshToken(request.data['refresh'])
                token.blacklist()

            except KeyError:
                response.data = {"status": status.HTTP_400_BAD_REQUEST}
                response.status_code = status.HTTP_401_UNAUTHORIZED
            except (TokenError, AttributeError, TypeError) as error:
                if hasattr(error, 'args'):
                    if 'Token is blacklisted' in error.args or 'Token is invalid or expired' in error.args:
                        response.data = {"status": status.HTTP_401_UNAUTHORIZED}
                    else:
                        response.data = {"status": status.HTTP_500_INTERNAL_SERVER_ERROR}
                else:
                    response.data = {"status": status.HTTP_500_INTERNAL_SERVER_ERROR}
        return response


# Code Request
@csrf_exempt
def kakao_login(request):
    url = "https://kauth.kakao.com/oauth/authorize?client_id={0}&redirect_uri={1}&response_type={2}" \
        .format(KAKAO_CLIENT_ID, KAKAO_REDIRECT_URI, 'code')
    return redirect(url)


# kakao Login or Signup
@csrf_exempt
def kakao_callback(request):
    code = request.GET.get('code')  # ?????? ?????? ????????? ????????? ?????? ??????
    print(f"?????? ??????: {code}")

    # Access Token Request
    token_api = "https://kauth.kakao.com/oauth/token"  # ?????? ?????? api
    data = {
        "grant_type": "authorization_code",
        "client_id": KAKAO_CLIENT_ID,
        "redirect_uri": KAKAO_REDIRECT_URI,
        "client_secret": KAKAO_CLIENT_SECRET,
        "code": code
    }
    headers = {
        'Content-type': 'application/x-www-form-urlencoded;charset=utf-8'
    }

    token_response = requests.post(token_api, data=data, headers=headers)
    token_json = token_response.json()
    access_token = token_json['access_token']
    print(f"????????? ?????? ???????????? ??????: {access_token}")

    # session ??????
    request.session['access_token'] = access_token
    request.session['client_id'] = KAKAO_CLIENT_ID
    request.session['redirect_uri'] = KAKAO_REDIRECT_URI

    # Email Request
    profile_request = requests.get(
        "https://kapi.kakao.com/v2/user/me",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    profile_json = profile_request.json()
    kakao_account = profile_json['kakao_account']
    kakao_profile = kakao_account['profile']
    email = kakao_account['email']

    # Login, Sighup Request
    try:
        # ?????????
        user = User.objects.get(email=email)
        social_user = SocialAccount.objects.filter(user=user)

        if not social_user:  # ?????? ???????????? ?????? ?????? (???????????????)
            return JsonResponse({"status": status.HTTP_404_NOT_FOUND})
        if social_user[0].provider != "kakao":  # kakao ?????? ???????????? ?????? ??????
            return JsonResponse({"status": status.HTTP_400_BAD_REQUEST})

        # kakao ?????? ?????????
        data = {'access_token': access_token, 'code': code}
        accept = requests.post(
            f"{BASE_URL}accounts/kakao/login/finish/", data=data)
        accept_status = accept.status_code
        if accept_status != 200:
            return JsonResponse(
                {"status": accept_status})
        accept_json = accept.json()
        accept_json.pop("user", None)

        user = User.objects.get(email=email)
        auth.login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        print("kakao ????????? ??????!")

        return JsonResponse({"status": status.HTTP_200_OK, "data": accept_json})

    except User.DoesNotExist:
        # ????????? ????????? ????????? ????????? ?????? ??????
        data = {'access_token': access_token, 'code': code}
        accept = requests.post(
            f"{BASE_URL}accounts/kakao/login/finish/", data=data
        )
        # ????????? ?????? ??????
        user = User.objects.get(email=email)
        avatar_url = kakao_profile['profile_image_url']

        # ????????? ?????? ????????? ?????? ??? -> ????????? ??????
        if avatar_url != "http://k.kakaocdn.net/dn/dpk9l1/btqmGhA2lKL/Oz0wDuJn1YV2DIn92f6DVK/img_640x640.jpg":
            avatar_request = requests.get(avatar_url)
            user.avatar.save(
                f"{kakao_account['email']}-avatar.jpg", ContentFile(avatar_request.content)
            )
        else:  # ?????? ???????????? ??? -> ????????? ????????? ??????
            user.avatar = "images/avatar/default_img.jpg"
        user.save()

        accept_status = accept.status_code
        if accept_status != 200:
            return JsonResponse({"status": accept_status})
        accept_json = accept.json()
        accept_json.pop("user", None)

        auth.login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        print("kakao ?????? ?????? ??????!")

        return JsonResponse({"status": status.HTTP_200_OK, "data": accept_json})


class KakaoLogin(SocialLoginView):
    adapter_class = KakaoOAuth2Adapter
    client_class = OAuth2Client
    callback_url = KAKAO_REDIRECT_URI


@csrf_exempt
def kakao_logout(request):
    if request.user.is_authenticated:
        print(f"?????? ?????? ????????? ??????: {request.user.username}")

    access_token = request.session['access_token']
    accept = requests.post(
        "https://kapi.kakao.com/v1/user/logout",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    # ???????????? ?????? ?????? ?????? status_code
    accept_status = accept.status_code
    if accept_status != 200:
        return JsonResponse({"status": accept_status}, status=accept_status)
    auth.logout(request)

    return JsonResponse({"status": status.HTTP_200_OK, "data": accept.json()})
