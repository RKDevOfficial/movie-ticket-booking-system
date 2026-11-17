from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

class Client(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(max_length=200, unique=True)
    phone_number = models.CharField(max_length=15)
    is_active = models.BooleanField(default=True)
    profile_picture = models.ImageField(
        upload_to='profile_pictures/',
        blank=True,
    )
    gender = models.CharField(
        max_length=10,
        choices=[
            ('Male', 'Male'),
            ('Female', 'Female'),
            ]
    )

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

class Theater(models.Model):
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class CinemaHall(models.Model):
    theater = models.ForeignKey(Theater, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    capacity = models.IntegerField()

    def __str__(self):
        return self.name

class Seat(models.Model):
    seat_number = models.CharField(max_length=30, unique=True)
    hall = models.ForeignKey(CinemaHall, on_delete=models.CASCADE)

    def __str__(self):
        return str(self.seat_number)

class Category(models.Model):
    category_name = models.CharField(max_length=100)

    def __str__(self):
        return self.category_name

class Movie(models.Model):
    title = models.CharField(max_length=100)
    duration = models.IntegerField()
    rating = models.CharField(
        max_length=5,
        choices=[
            ('G', 'G'),
            ('PG', 'PG'),
            ('PG-13', 'PG-13'),
            ('R', 'R'),
            ('NC-17', 'NC-17'),
            ('NR', 'Not Rated'),
        ],
        default='PG-13',
    )
    language = models.CharField(
        max_length=20,
        choices=[
            ('English','English'),
            ('Luganda','Luganda'),
            ('Swahili','Swahili'),
        ])
    release_year = models.PositiveBigIntegerField(
        validators=[
            MinValueValidator(1888),
            MaxValueValidator(timezone.now().year)
        ]
    )
    category = models.ForeignKey(Category, on_delete=models.CASCADE)

    def __str__(self):
        return self.title

class ShowTime(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE)
    hall = models.ForeignKey(CinemaHall, on_delete=models.CASCADE)
    show_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    def __str__(self):
        return f"{self.movie.title} - {self.show_date} - {self.start_time}"

class Booking(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    showtime = models.ForeignKey(ShowTime, on_delete=models.CASCADE)
    seat = models.ForeignKey(Seat, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_status = models.CharField(
        max_length=20,
        choices=[
            ('Pending','Pending'),
            ('Paid', 'Paid'),
            ('Failed', 'Failed'),
            ('Refunded','Refunded'),
        ],
        default='Pending'

        
    )
    payment_date = models.DateField(auto_now_add=True)
    payment_method = models.CharField(
        max_length=20,
        choices=[
            ('Cash','Cash'),
            ('Mobile Money','Mobile Money'),
            ('Credit Card', 'Credit Card'),
        ]
    )

    def __str__(self):
        client_name = str(self.client) if self.client else 'Former client'
        return f"{client_name} - {self.showtime} - {self.seat}"
