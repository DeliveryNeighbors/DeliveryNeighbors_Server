from django.conf import settings
from django.conf.urls.static import static
from django.urls import path
from chat import views

app_name = 'chat'
urlpatterns = [
    # 채팅방 생성 & 목록 조회
    path('room/', views.RoomGetCreateAPIView.as_view(), name='room-main'),
    # 단일 채팅방 조회 & 삭제
    path('room/<int:pk>', views.RoomRetrieveDestroyAPIView.as_view(), name='room-sub'),
    # 카테고리 조회
    # path('category/', views.CategoryListView.as_view(), name='category-list'),
    # 채팅방 참여 인원 조회/생성/삭제
    path('room/<int:room_id>/neighbor/', views.ChatUserView.as_view(), name='chat-user'),
    # 실시간 위치 정보 입력 & 특정 채팅방에 속한 모든 유저 위치 조회
    path('room/cur_location/', views.CurrentLocationView.as_view(), name='user-location'),
]
