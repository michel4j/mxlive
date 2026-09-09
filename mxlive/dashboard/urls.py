from django.urls import path
from . import views

urlpatterns = [
    path('', views.DashboardIndexView.as_view(), name='dashboard'),
    path('user/', views.UserDashboardView.as_view(), name='user-dashboard'),
    path('staff/', views.StaffDashboardView.as_view(), name='staff-dashboard'),
]
