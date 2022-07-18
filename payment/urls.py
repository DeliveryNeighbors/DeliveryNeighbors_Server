from django.urls import path

from payment import views

urlpatterns = [
    # 결제 승인
    path('toss/confirm/<int:chatuser>/', views.payConfirmed, name='pay_confirmed'),
]
