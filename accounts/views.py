import random

import requests
from allauth.socialaccount.models import SocialAccount
from allauth.socialaccount.providers.kakao.views import KakaoOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from dj_rest_auth.registration.views import SocialLoginView
from django.conf import settings
from django.contrib import auth
from django.contrib.auth.hashers import make_password, check_password
from django.core.mail import send_mail
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.generics import *
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils.translation import gettext_lazy

from accounts.models import Address
from accounts.serializers import *
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError

from config.settings.base import SOCIAL_OAUTH_CONFIG
from config.authentication import CustomJWTAuthentication

# BASE_URL = "http://3.38.38.248/"  # deploy version
BASE_URL = "http://localhost:8000/"  # local version

KAKAO_CLIENT_ID = SOCIAL_OAUTH_CONFIG['KAKAO_REST_API_KEY']
KAKAO_REDIRECT_URI = f"{BASE_URL}{SOCIAL_OAUTH_CONFIG['KAKAO_REDIRECT_URI']}"
KAKAO_CLIENT_SECRET = SOCIAL_OAUTH_CONFIG['KAKAO_SECRET_KEY']

authenticate_num_dict = {}


class UserCreateAPIView(CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = UserCreateSerializer

    def post(self, request, *args, **kwargs):
        if request.data['avatar']:
            user_data = {
                'username': request.data['username'],
                'email': request.data['email'],
                'password': make_password(request.data['password']),
                'avatar': request.data['avatar']
            }
        else:
            user_data = {
                'username': request.data['username'],
                'email': request.data['email'],
                'password': make_password(request.data['password'])
            }

        serializer = self.serializer_class(data=request.data)

        if serializer.is_valid(raise_exception=False):
            user = serializer.create(user_data)
            print("user", user)
            token = RefreshToken.for_user(user)
            refresh = str(token)
            access = str(token.access_token)

            return JsonResponse(
                {"status": status.HTTP_201_CREATED, "success": "true", "data": {
                    'user': user.pk, 'access': access, 'refresh': refresh}})

        else:
            print(serializer.errors)
            return Response({"status": status.HTTP_400_BAD_REQUEST, "success": "fail", "message": "유효성 검증 오류"})


class EmailSendView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = EmailSendSerializer

    def post(self, request):
        random_num = int(random.random() * 1000000)
        print("random_num", random_num)
        message = f"회원가입을 위해 아래의 난수를 확인 창에 입력하세요.\n{random_num}"

        authenticate_num_dict[request.data['email']] = random_num

        mail_title = "회원가입을 위해 이메일을 인증하세요"
        mail_to = request.data['email']
        send_mail(mail_title, message, None, [mail_to], fail_silently=False)

        return JsonResponse({"status": status.HTTP_200_OK, "success": "true", "message": "email send success",
                             "data": {"random_num": random_num}})


class EmailVerifyView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = EmailVerifySerializer

    def post(self, request):
        if request.data['email'] in authenticate_num_dict and \
                authenticate_num_dict[request.data['email']] == request.data['random_num']:
            authenticate_num_dict.pop(request.data['email'])
            return Response({"status": status.HTTP_200_OK, "success": "true", "message": "email verify success",
                             "data": {"email": request.data['email']}})
        else:
            return Response({"status": status.HTTP_400_BAD_REQUEST, "success": "fail", "message": "email verify fail"})


class UserLoginAPIView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = UserLoginSerializer

    def post(self, request):
        serializer = self.serializer_class

        request_email = request.data['email']
        request_password = request.data['password']

        try:
            user = User.objects.get(email=request_email)  # 여기서 객체가 없으면 DoesNotExist 예외처리
            user_password = user.password
            if check_password(request_password, user_password):
                token = RefreshToken.for_user(user)
                refresh = str(token)
                access = str(token.access_token)

                return JsonResponse({"status": status.HTTP_201_CREATED, "success": "true",
                                     "data": {'user': user.pk, 'refresh': refresh, 'access': access}})  # 성공메세지
            else:
                return JsonResponse(
                    {"status": status.HTTP_400_BAD_REQUEST, "success": "false", "message": "비밀번호가 올바르지 않습니다"})  # 에러메세지

        except User.DoesNotExist:
            return JsonResponse(
                {"status": status.HTTP_401_UNAUTHORIZED, "success": "false", "message": "이메일로 등록된 유저가 없습니다"})  # 에러메세지 2


class UserLogoutAPIView(APIView):
    def post(self, request):
        response = Response({"status": status.HTTP_200_OK, "message": "Successfully logged out"})

        if 'rest_framework_simplejwt.token_blacklist' in settings.INSTALLED_APPS:
            try:
                token = RefreshToken(request.data['refresh'])
                token.blacklist()

            except KeyError:
                response.data = {"status": status.HTTP_400_BAD_REQUEST, "success": "false",
                                 'message': "Refresh token was not included in request data"}
                response.status_code = status.HTTP_401_UNAUTHORIZED
            except (TokenError, AttributeError, TypeError) as error:
                if hasattr(error, 'args'):
                    if 'Token is blacklisted' in error.args or 'Token is invalid or expired' in error.args:
                        response.data = {"status": status.HTTP_401_UNAUTHORIZED, "success": "false",
                                         'message': gettext_lazy(error.args[0])}
                    else:
                        response.data = {"status": status.HTTP_500_INTERNAL_SERVER_ERROR, "success": "false",
                                         'message': "An error has occurred"}
                else:
                    response.data = {"status": status.HTTP_500_INTERNAL_SERVER_ERROR, "success": "false",
                                     'message': "An error has occurred"}
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
    code = request.GET.get('code')  # 토큰 받기 요청에 필요한 인가 코드
    print(f"인가 코드: {code}")

    # Access Token Request
    token_api = "https://kauth.kakao.com/oauth/token"  # 토큰 받기 api
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
    print(f"엑세스 토큰 가져오기 성공: {access_token}")

    # session 저장
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
        # 로그인
        user = User.objects.get(email=email)
        social_user = SocialAccount.objects.filter(user=user)

        if not social_user:  # 소셜 로그인이 아닐 경우 (자체로그인)
            return JsonResponse({"status": status.HTTP_400_BAD_REQUEST, "success": "fail",
                                 "message": "email exists but not social user"})
        if social_user[0].provider != "kakao":  # kakao 소셜 로그인이 아닌 경우
            return JsonResponse({"status": status.HTTP_400_BAD_REQUEST, "success": "fail",
                                 "message": "no matching social type"})

        # kakao 유저 로그인
        data = {'access_token': access_token, 'code': code}
        accept = requests.post(
            f"{BASE_URL}accounts/kakao/login/finish/", data=data)
        accept_status = accept.status_code
        if accept_status != 200:
            return JsonResponse(
                {"status": accept_status, "success": "false", "message": "failed to signin"})
        accept_json = accept.json()
        accept_json.pop("user", None)

        user = User.objects.get(email=email)
        auth.login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        print("kakao 로그인 성공!")

        return JsonResponse({"status": status.HTTP_200_OK, "success": "true", "data": accept_json})

    except User.DoesNotExist:
        # 기존에 가입한 유저가 아니면 회원 가입
        data = {'access_token': access_token, 'code': code}
        accept = requests.post(
            f"{BASE_URL}accounts/kakao/login/finish/", data=data
        )
        # 프로필 사진 설정
        user = User.objects.get(email=email)
        user.avatar = kakao_profile['profile_image_url']
        user.save()

        accept_status = accept.status_code
        if accept_status != 200:
            return JsonResponse({"status": accept_status, "success": "false", "message": "failed to signup"})
        accept_json = accept.json()
        accept_json.pop("user", None)

        auth.login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        print("kakao 회원 가입 성공!")

        return JsonResponse({"status": status.HTTP_200_OK, "success": "true", "data": accept_json})


class KakaoLogin(SocialLoginView):
    adapter_class = KakaoOAuth2Adapter
    client_class = OAuth2Client
    callback_url = KAKAO_REDIRECT_URI


@csrf_exempt
def kakao_logout(request):
    if request.user.is_authenticated:
        print(f"현재 로그 아웃할 유저: {request.user.username}")

    access_token = request.session['access_token']
    accept = requests.post(
        "https://kapi.kakao.com/v1/user/logout",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    # 로그아웃 에러 예외 처리 status_code
    accept_status = accept.status_code
    if accept_status != 200:
        return JsonResponse({"status": accept_status, "success": "false", "message": "failed to logout"}, status=accept_status)
    auth.logout(request)

    return JsonResponse({"status": status.HTTP_200_OK, "success": "true", "data": accept.json()})


class UserAddressView(ListCreateAPIView, DestroyAPIView):
    def post(self, request):
        user_id = CustomJWTAuthentication.authenticate(self, request)

        addr_latitude = request.data['addr_latitude']
        addr_longitude = request.data['addr_longitude']

        try:
            address = Address.objects.get(user_id=user_id, addr_latitude=addr_latitude, addr_longitude=addr_longitude)

            return Response({"status": status.HTTP_200_OK, "success": "true", "message": "already registered address"})

        except Address.DoesNotExist:
            addr = Address.objects.create(
                user=User.objects.get(id=user_id),
                addr_latitude=addr_latitude,
                addr_longitude=addr_longitude
            )

            return Response({"status": status.HTTP_201_CREATED})

    def get(self, request):
        user_id = CustomJWTAuthentication.authenticate(self, request)

        addr_list = Address.objects.filter(user_id=user_id).order_by('-updated_at')
        print("addr_list", addr_list.values())

        if len(addr_list) >= 3:
            addr_list = addr_list[:3]

        serializer = UserAddressSerializer(instance=addr_list, many=True)

        return Response({"status": status.HTTP_200_OK, "success": "true", "addr_list": serializer.data})

    def delete(self, request):
        user_id = CustomJWTAuthentication.authenticate(self, request)

        addr_latitude = request.data['addr_latitude']
        addr_longitude = request.data['addr_longitude']

        try:
            address = Address.objects.get(user_id=user_id, addr_latitude=addr_latitude, addr_longitude=addr_longitude)
            address.delete()
            return Response({"status": status.HTTP_200_OK, "success": "true"})

        except Address.DoesNotExist:
            return Response({"status": status.HTTP_400_BAD_REQUEST, "success": "false", "message": "not registered address"})


class UserInfoUpdateView(UpdateAPIView):
    def put(self, request):
        user_id = CustomJWTAuthentication.authenticate(self, request)

        try:
            user = User.objects.get(id=user_id)

            # TODO 빈 값 들어왔을 때 기본 이미지로 설정하기

            if user.is_active:
                user.username = request.data['username']
                user.avatar = request.data['avatar']

                serializer = UserUpdateSerializer(user, data=request.data, partial=False)
                serializer.is_valid(raise_exception=True)
                self.perform_update(serializer)

                return Response({"status": status.HTTP_200_OK, "success": "true", "data": {"user": serializer.data}})

            else:
                return Response({"status": status.HTTP_400_BAD_REQUEST, "success": "false", "message": "withdrawn user"})

        except User.DoesNotExist:
            return Response({"status": status.HTTP_400_BAD_REQUEST, "success": "false", "message": "user not exist"})
