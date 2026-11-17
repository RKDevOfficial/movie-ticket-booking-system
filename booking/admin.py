from django.contrib import admin
from .models import Theater, CinemaHall, Seat, Category, Movie, ShowTime, Client, Booking

admin.site.register(Theater)
admin.site.register(CinemaHall)
admin.site.register(Seat)
admin.site.register(Category)
admin.site.register(Movie)
admin.site.register(ShowTime)
admin.site.register(Client)
admin.site.register(Booking)
