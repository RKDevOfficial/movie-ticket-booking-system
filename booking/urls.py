from django.urls import path
from . import views

urlpatterns = [
    path('', views.base_view, name='index_page'),
    path('profile/', views.profile_view, name='profile'),
    path('settings/', views.settings_view, name='settings'),
    path('list_theater/', views.list_theater_view, name='list_theater'),
    path('add_theater/', views.add_theater_view, name='add_theater'),
    path('edit_theater/<int:pk>/', views.edit_theater_view, name='edit_theater'),
    path('delete_theater/<int:pk>/', views.delete_theater_view, name='delete_theater'),

    path('list_hall/', views.list_hall_view, name='list_hall'),
    path('add_hall/', views.add_hall_view, name='add_hall'),
    path('edit_hall/<int:pk>/', views.edit_hall_view, name='edit_hall'),
    path('delete_hall/<int:pk>/', views.delete_hall_view, name='delete_hall'),

    path('list_seat/', views.list_seat_view, name='list_seat'),
    path('add_seat/', views.add_seat_view, name='add_seat'),
    path('edit_seat/<int:pk>/', views.edit_seat_view, name='edit_seat'),
    path('delete_seat/<int:pk>/', views.delete_seat_view, name='delete_seat'),

    path('list_category/', views.list_category_view, name='list_category'),
    path('add_category/', views.add_category_view, name='add_category'),
    path('edit_category/<int:pk>/', views.edit_category_view, name='edit_category'),
    path('delete_category/<int:pk>/', views.delete_category_view, name='delete_category'),

    path('list_movie/', views.list_movies_views, name='list_movie'),
    path('add_movie/', views.add_movie_view, name='add_movie'),
    path('edit_movie/<int:pk>/', views.edit_movie_view, name='edit_movie'),
    path('delete_movie/<int:pk>/', views.delete_movie_view, name='delete_movie'),

    path('list_showtime/', views.list_showtime_view, name='list_showtime'),
    path('add_showtime/', views.add_showtime_view, name='add_showtime'),
    path('edit_showtime/<int:pk>/', views.edit_showtime_view, name='edit_showtime'),
    path('delete_showtime/<int:pk>/', views.delete_showtime_view, name='delete_showtime'),

    path('list_client/', views.list_client_view, name='list_client'),
    path('add_client/', views.add_client_view, name='add_client'),
    path('edit_client/<int:pk>/', views.edit_client_view, name='edit_client'),
    path('delete_client/<int:pk>/', views.delete_client_view, name='delete_client'),

    path('list_booking/', views.list_booking_view, name='list_booking'),
    path('add_booking/', views.add_booking_view, name='add_booking'),
    path('edit_booking/<int:pk>/', views.edit_booking_view, name='edit_booking'),
    path('delete_booking/<int:pk>/', views.delete_booking_view, name='delete_booking'),

    path('reports/', views.reports_view, name='reports'),
]
