import csv
import base64

from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login
from django.contrib.auth.decorators import login_not_required
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_http_methods

from .forms import (
    BookingForm,
    AccountCreationForm,
    CategoryForm,
    CinemaHallForm,
    ClientForm,
    MovieForm,
    ProfileEditForm,
    RoleAssignmentForm,
    SeatForm,
    ShowTimeForm,
    TheaterForm,
)
from .models import (
    Booking,
    Category,
    CinemaHall,
    Client,
    Movie,
    Seat,
    ShowTime,
    Theater,
)


@login_not_required
@require_http_methods(['GET', 'POST'])
def login_view(request):
    next_url = request.POST.get('next') or request.GET.get('next', '')
    context = {'next': next_url, 'username': request.POST.get('username', '')}

    if request.user.is_authenticated:
        return redirect('index_page')

    if request.method == 'POST':
        user = authenticate(
            request,
            username=request.POST.get('username', '').strip(),
            password=request.POST.get('password', ''),
        )
        if user is not None:
            auth_login(request, user)
            messages.success(
                request,
                f"Welcome, {user.first_name or user.get_username()}!",
            )
            if url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_url)
            return redirect('index_page')
        context['error'] = 'The username or password you entered is incorrect.'

    return render(request, 'registration/login.html', context)


@login_not_required
@require_http_methods(['GET', 'POST'])
def signup_view(request):
    if request.user.is_authenticated:
        return redirect('index_page')

    next_url = request.POST.get('next') or request.GET.get('next', '')
    form = AccountCreationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        auth_login(request, user)
        messages.success(
            request,
            f"Welcome, {user.first_name or user.get_username()}!",
        )
        if url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return redirect(next_url)
        return redirect('index_page')

    return render(
        request,
        'registration/signup.html',
        {'form': form, 'next': next_url},
    )


def profile_view(request):
    client = Client.objects.filter(email__iexact=request.user.email).first()
    form = ProfileEditForm(
        request.POST or None,
        request.FILES or None,
        user=request.user,
        client=client,
    )
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Your profile has been updated.')
        return redirect('profile')

    return render(request, 'registration/profile.html', {'form': form})


def settings_view(request):
    role_form = None
    if request.user.is_superuser:
        role_form = RoleAssignmentForm(
            request.POST or None,
            assigning_user=request.user,
        )
        if request.method == 'POST':
            if role_form.is_valid():
                updated_user = role_form.save()
                messages.success(
                    request,
                    f"{updated_user.get_username()} is now a "
                    f"{role_form.cleaned_data['role']}.",
                )
                return redirect('settings')
    elif request.method == 'POST':
        return HttpResponseForbidden('Only superusers can assign user roles.')

    users = (
        get_user_model().objects.filter(is_superuser=False)
        .exclude(pk=request.user.pk)
        .order_by('username')
        if request.user.is_superuser
        else ()
    )
    return render(
        request,
        'registration/settings.html',
        {'role_form': role_form, 'role_users': users},
    )


def base_view(request):
    today = timezone.localdate()
    paid_bookings = Booking.objects.filter(payment_status='Paid')
    upcoming_screenings = ShowTime.objects.filter(show_date__gte=today)
    upcoming_show_list = upcoming_screenings.select_related('movie', 'hall', 'hall__theater').order_by('show_date', 'start_time')[:5]
    total_seats = ShowTime.objects.aggregate(
        total=Sum('hall__capacity'),
    )['total'] or 0
    booked_seat_count = Booking.objects.values(
        'showtime_id',
        'seat_id',
    ).distinct().count()
    if not total_seats:
        total_seats = CinemaHall.objects.aggregate(
            total=Sum('capacity'),
        )['total'] or 0
    booked_seats = booked_seat_count
    seat_fill_percent = min(round(booked_seats * 100 / total_seats), 100) if total_seats else 0
    return render(
        request,
        'dashboard.html',
        {
            'booking_count': Booking.objects.count(),
            'today': today,
            'client_count': Client.objects.filter(is_active=True).count(),
            'movie_count': Movie.objects.count(),
            'showtime_count': ShowTime.objects.filter(show_date__gte=today).count(),
            'paid_revenue': paid_bookings.aggregate(total=Sum('amount'))['total'] or 0,
            'paid_booking_count': paid_bookings.count(),
            'total_seats': total_seats,
            'booked_seats': booked_seats,
            'booked_seat_count': booked_seat_count,
            'seat_fill_percent': seat_fill_percent,
            'featured_movie': Movie.objects.order_by('-pk').first(),
            'upcoming_shows': upcoming_show_list,
            'recent_bookings': Booking.objects.select_related('client', 'showtime', 'showtime__movie')
                .order_by('-pk')[:5],
        }
    )
    
# theater
def list_theater_view(request):
    all_theaters = Theater.objects.annotate(hall_total=Count('cinemahall', distinct=True)).order_by(
        'name', 'location', 'pk'
    )
    search_query = request.GET.get('q', '').strip()
    theaters = all_theaters
    if search_query:
        theater_search = Q(name__icontains=search_query) | Q(location__icontains=search_query)
        if search_query.isdigit():
            theater_search |= Q(pk=int(search_query))
        theaters = theaters.filter(theater_search)

    page_limit = request.GET.get('limit', '10')
    if page_limit not in {'10', '25', '50'}:
        page_limit = '10'
    theater_page = Paginator(theaters, int(page_limit)).get_page(request.GET.get('page'))

    form_mode = request.GET.get('theater_form')
    theater_instance = None
    if form_mode == 'edit':
        theater_instance = get_object_or_404(Theater, pk=request.GET.get('theater_id'))

    theater_form = None
    if form_mode in {'add', 'edit'}:
        if request.method == 'POST':
            theater_form = TheaterForm(request.POST, instance=theater_instance)
            if theater_form.is_valid():
                saved_theater = theater_form.save()
                messages.success(
                    request,
                    f'Theater "{saved_theater.name}" '
                    f'{"added" if form_mode == "add" else "updated"} successfully.',
                )
                return redirect('list_theater')
        else:
            theater_form = TheaterForm(instance=theater_instance)

    return render(
        request,
        'theater/list_theater.html',
        {
            'theater': theater_page.object_list,
            'page_obj': theater_page,
            'page_limit': page_limit,
            'search_query': search_query,
            'theater_form': theater_form,
            'theater_form_title': 'Add theater' if form_mode == 'add' else 'Edit theater',
            'theater_count': all_theaters.count(),
            'hall_count': CinemaHall.objects.count(),
            'location_count': all_theaters.values('location').distinct().count(),
        }
    )

def add_theater_view(request):
    return redirect(f"{reverse('list_theater')}?theater_form=add")

def edit_theater_view(request, pk):
    get_object_or_404(Theater, pk=pk)
    return redirect(f"{reverse('list_theater')}?theater_form=edit&theater_id={pk}")

def delete_theater_view(request, pk):
    theater = get_object_or_404(Theater, pk=pk)

    if request.method == 'POST':
        theater_name = theater.name
        theater.delete()
        messages.success(request, f'Theater "{theater_name}" deleted successfully.')
        return redirect('list_theater')

    return render(
        request,
        'theater/delete_theater.html',
        {'theater': theater}
    )

# CinemaHall
def list_hall_view(request):
    all_halls = CinemaHall.objects.select_related('theater').annotate(
        seat_total=Count('seat', distinct=True)
    ).order_by('theater__name', 'name', 'pk')
    search_query = request.GET.get('q', '').strip()
    halls = all_halls
    if search_query:
        hall_search = (
            Q(name__icontains=search_query)
            | Q(theater__name__icontains=search_query)
            | Q(theater__location__icontains=search_query)
        )
        if search_query.isdigit():
            hall_search |= Q(pk=int(search_query)) | Q(capacity=int(search_query))
        halls = halls.filter(hall_search)

    page_limit = request.GET.get('limit', '10')
    if page_limit not in {'10', '25', '50'}:
        page_limit = '10'
    hall_page = Paginator(halls, int(page_limit)).get_page(request.GET.get('page'))

    form_mode = request.GET.get('hall_form')
    hall_instance = None
    if form_mode == 'edit':
        hall_instance = get_object_or_404(CinemaHall, pk=request.GET.get('hall_id'))

    hall_form = None
    if form_mode in {'add', 'edit'}:
        if request.method == 'POST':
            hall_form = CinemaHallForm(request.POST, instance=hall_instance)
            if hall_form.is_valid():
                saved_hall = hall_form.save()
                messages.success(
                    request,
                    f'Hall "{saved_hall.name}" '
                    f'{"added" if form_mode == "add" else "updated"} successfully.',
                )
                return redirect('list_hall')
        else:
            hall_form = CinemaHallForm(instance=hall_instance)

    return render(
        request,
        'hall/list_hall.html',
        {
            'hall': hall_page.object_list,
            'page_obj': hall_page,
            'page_limit': page_limit,
            'search_query': search_query,
            'hall_form': hall_form,
            'hall_form_title': 'Add cinema hall' if form_mode == 'add' else 'Edit cinema hall',
            'hall_count': all_halls.count(),
            'theater_count': Theater.objects.count(),
            'seat_capacity': all_halls.aggregate(total=Sum('capacity'))['total'] or 0,
        }
    )

def add_hall_view(request):
    return redirect(f"{reverse('list_hall')}?hall_form=add")

def edit_hall_view(request, pk):
    get_object_or_404(CinemaHall, pk=pk)
    return redirect(f"{reverse('list_hall')}?hall_form=edit&hall_id={pk}")

def delete_hall_view(request, pk):
    halls = get_object_or_404(CinemaHall, pk=pk)

    if request.method == 'POST':
        hall_name = halls.name
        halls.delete()
        messages.success(request, f'Hall "{hall_name}" deleted successfully.')
        return redirect('list_hall')

    return render(
        request,
        'hall/delete_hall.html',
        {'hall': halls}
    )

# SEATS
def list_seat_view(request):
    all_seats = Seat.objects.select_related('hall', 'hall__theater').order_by(
        'hall__theater__name', 'hall__name', 'seat_number', 'pk'
    )
    search_query = request.GET.get('q', '').strip()
    seats = all_seats
    if search_query:
        seat_search = (
            Q(seat_number__icontains=search_query)
            | Q(hall__name__icontains=search_query)
            | Q(hall__theater__name__icontains=search_query)
        )
        if search_query.isdigit():
            seat_search |= Q(pk=int(search_query))
        seats = seats.filter(seat_search)

    page_limit = request.GET.get('limit', '10')
    if page_limit not in {'10', '25', '50'}:
        page_limit = '10'
    seat_page = Paginator(seats, int(page_limit)).get_page(request.GET.get('page'))

    form_mode = request.GET.get('seat_form')
    seat_instance = None
    if form_mode == 'edit':
        seat_instance = get_object_or_404(Seat, pk=request.GET.get('seat_id'))

    seat_form = None
    if form_mode in {'add', 'edit'}:
        if request.method == 'POST':
            seat_form = SeatForm(request.POST, instance=seat_instance)
            if seat_form.is_valid():
                saved_seat = seat_form.save()
                messages.success(
                    request,
                    f'Seat "{saved_seat.seat_number}" '
                    f'{"added" if form_mode == "add" else "updated"} successfully.',
                )
                return redirect('list_seat')
        else:
            seat_form = SeatForm(instance=seat_instance)

    return render(
        request,
        'seat/list_seat.html',
        {
            'seat': seat_page.object_list,
            'page_obj': seat_page,
            'page_limit': page_limit,
            'search_query': search_query,
            'seat_form': seat_form,
            'seat_form_title': 'Add seat' if form_mode == 'add' else 'Edit seat',
            'seat_count': all_seats.count(),
            'hall_count': CinemaHall.objects.count(),
        }
    )

def add_seat_view(request):
    return redirect(f"{reverse('list_seat')}?seat_form=add")

def edit_seat_view(request, pk):
    get_object_or_404(Seat, pk=pk)
    return redirect(f"{reverse('list_seat')}?seat_form=edit&seat_id={pk}")

def delete_seat_view(request, pk):
    seats = get_object_or_404(Seat, pk=pk)

    if request.method == 'POST':
        seat_number = seats.seat_number
        seats.delete()
        messages.success(request, f'Seat "{seat_number}" deleted successfully.')
        return redirect('list_seat')

    return render(
        request,
        'seat/delete_seat.html',
        {'seat': seats}
    )

# CATEGORY
def list_category_view(request):
    all_categories = Category.objects.annotate(movie_total=Count('movie')).order_by('category_name', 'pk')
    search_query = request.GET.get('q', '').strip()
    categories = all_categories
    if search_query:
        category_search = Q(category_name__icontains=search_query)
        if search_query.isdigit():
            category_search |= Q(pk=int(search_query))
        categories = categories.filter(category_search)

    page_limit = request.GET.get('limit', '10')
    if page_limit not in {'10', '25', '50'}:
        page_limit = '10'
    category_page = Paginator(categories, int(page_limit)).get_page(request.GET.get('page'))

    form_mode = request.GET.get('category_form')
    category_instance = None
    if form_mode == 'edit':
        category_instance = get_object_or_404(Category, pk=request.GET.get('category_id'))

    category_form = None
    if form_mode in {'add', 'edit'}:
        if request.method == 'POST':
            category_form = CategoryForm(request.POST, instance=category_instance)
            if category_form.is_valid():
                saved_category = category_form.save()
                messages.success(
                    request,
                    f'Category "{saved_category.category_name}" '
                    f'{"added" if form_mode == "add" else "updated"} successfully.',
                )
                return redirect('list_category')
        else:
            category_form = CategoryForm(instance=category_instance)

    return render(
        request,
        'category/list_category.html',
        {
            'category': category_page.object_list,
            'page_obj': category_page,
            'page_limit': page_limit,
            'search_query': search_query,
            'category_form': category_form,
            'category_form_title': 'Add category' if form_mode == 'add' else 'Edit category',
            'category_count': all_categories.count(),
            'categories_with_movies': all_categories.filter(movie_total__gt=0).count(),
        }
    )

def add_category_view(request):
    return redirect(f"{reverse('list_category')}?category_form=add")

def edit_category_view(request, pk):
    get_object_or_404(Category, pk=pk)
    return redirect(f"{reverse('list_category')}?category_form=edit&category_id={pk}")

def delete_category_view(request, pk):
    category = get_object_or_404(Category, pk=pk)

    if request.method == 'POST':
        category_name = category.category_name
        category.delete()
        messages.success(request, f'Category "{category_name}" deleted successfully.')
        return redirect('list_category')

    return render(
        request,
        'category/delete_category.html',
        {'category': category}
    )

# MOVIES
def list_movies_views(request):
    all_movies = Movie.objects.select_related('category').order_by('title', 'pk')
    search_query = request.GET.get('q', '').strip()
    movies = all_movies
    if search_query:
        movie_search = (
            Q(title__icontains=search_query)
            | Q(category__category_name__icontains=search_query)
            | Q(language__icontains=search_query)
            | Q(rating__icontains=search_query)
        )
        if search_query.isdigit():
            movie_search |= Q(release_year=int(search_query)) | Q(duration=int(search_query))
        movies = movies.filter(movie_search)

    page_limit = request.GET.get('limit', '10')
    if page_limit not in {'10', '25', '50'}:
        page_limit = '10'
    movie_page = Paginator(movies, int(page_limit)).get_page(request.GET.get('page'))

    form_mode = request.GET.get('movie_form')
    movie_instance = None
    if form_mode == 'edit':
        movie_instance = get_object_or_404(Movie, pk=request.GET.get('movie_id'))

    movie_form = None
    if form_mode in {'add', 'edit'}:
        if request.method == 'POST':
            movie_form = MovieForm(request.POST, instance=movie_instance)
            if movie_form.is_valid():
                saved_movie = movie_form.save()
                messages.success(
                    request,
                    f'Movie "{saved_movie.title}" '
                    f'{"added" if form_mode == "add" else "updated"} successfully.',
                )
                return redirect('list_movie')
        else:
            movie_form = MovieForm(instance=movie_instance)

    return render(
        request,
        'movie/list_movie.html',
        {
            'movie': movie_page.object_list,
            'page_obj': movie_page,
            'page_limit': page_limit,
            'search_query': search_query,
            'movie_form': movie_form,
            'movie_form_title': 'New movie' if form_mode == 'add' else 'Edit movie',
            'movie_count': all_movies.count(),
            'category_count': Category.objects.count(),
        }
    )

def add_movie_view(request):
    return redirect(f"{reverse('list_movie')}?movie_form=add")

def edit_movie_view(request, pk):
    get_object_or_404(Movie, pk=pk)
    return redirect(f"{reverse('list_movie')}?movie_form=edit&movie_id={pk}")

def delete_movie_view(request, pk):
    movie = get_object_or_404(Movie, pk=pk)

    if request.method == 'POST':
        movie_title = movie.title
        movie.delete()
        messages.success(request, f'Movie "{movie_title}" deleted successfully.')
        return redirect('list_movie')

    return render(
        request,
        'movie/delete_movie.html',
        {'movie': movie}
    )

#Showtime
def list_showtime_view(request):
    all_showtimes = ShowTime.objects.select_related('movie', 'hall', 'hall__theater').order_by(
        '-show_date', 'start_time', 'pk'
    )
    search_query = request.GET.get('q', '').strip()
    showtimes = all_showtimes
    if search_query:
        showtime_search = (
            Q(movie__title__icontains=search_query)
            | Q(hall__name__icontains=search_query)
            | Q(hall__theater__name__icontains=search_query)
        )
        parsed_date = parse_date(search_query)
        if parsed_date:
            showtime_search |= Q(show_date=parsed_date)
        if search_query.isdigit():
            showtime_search |= Q(pk=int(search_query))
        showtimes = showtimes.filter(showtime_search)

    page_limit = request.GET.get('limit', '10')
    if page_limit not in {'10', '25', '50'}:
        page_limit = '10'
    showtime_page = Paginator(showtimes, int(page_limit)).get_page(request.GET.get('page'))

    form_mode = request.GET.get('showtime_form')
    showtime_instance = None
    if form_mode == 'edit':
        showtime_instance = get_object_or_404(ShowTime, pk=request.GET.get('showtime_id'))

    showtime_form = None
    if form_mode in {'add', 'edit'}:
        if request.method == 'POST':
            showtime_form = ShowTimeForm(request.POST, instance=showtime_instance)
            if showtime_form.is_valid():
                saved_showtime = showtime_form.save()
                messages.success(
                    request,
                    f'Showtime for "{saved_showtime.movie}" '
                    f'{"added" if form_mode == "add" else "updated"} successfully.',
                )
                return redirect('list_showtime')
        else:
            showtime_form = ShowTimeForm(instance=showtime_instance)

    return render(
        request,
        'showtime/list_showtime.html',
        {
            'showtime': showtime_page.object_list,
            'page_obj': showtime_page,
            'page_limit': page_limit,
            'search_query': search_query,
            'showtime_form': showtime_form,
            'showtime_form_title': 'New showtime' if form_mode == 'add' else 'Edit showtime',
            'showtime_count': all_showtimes.count(),
            'upcoming_showtime_count': all_showtimes.filter(show_date__gte=timezone.localdate()).count(),
        }
    )

def add_showtime_view(request):
    return redirect(f"{reverse('list_showtime')}?showtime_form=add")

def edit_showtime_view(request, pk):
    get_object_or_404(ShowTime, pk=pk)
    return redirect(f"{reverse('list_showtime')}?showtime_form=edit&showtime_id={pk}")

def delete_showtime_view(request, pk):
    showtime = get_object_or_404(ShowTime, pk=pk)

    if request.method == 'POST':
        movie_title = showtime.movie.title
        showtime.delete()
        messages.success(request, f'Showtime for "{movie_title}" deleted successfully.')
        return redirect('list_showtime')

    return render(
        request,
        'showtime/delete_showtime.html',
        {'showtime': showtime}
    )

# Client
def list_client_view(request):
    all_clients = Client.objects.filter(is_active=True).annotate(
        booking_total=Count('booking'),
    ).order_by('first_name', 'last_name', 'pk')
    search_query = request.GET.get('q', '').strip()
    clients = all_clients
    if search_query:
        client_search = (
            Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(phone_number__icontains=search_query)
            | Q(gender__icontains=search_query)
        )
        if search_query.isdigit():
            client_search |= Q(pk=int(search_query))
        clients = clients.filter(client_search)

    page_limit = request.GET.get('limit', '10')
    if page_limit not in {'10', '25', '50'}:
        page_limit = '10'
    client_page = Paginator(clients, int(page_limit)).get_page(request.GET.get('page'))

    form_mode = request.GET.get('client_form')
    client_instance = None
    if form_mode == 'edit':
        client_instance = get_object_or_404(
            all_clients,
            pk=request.GET.get('client_id'),
        )

    client_form = None
    if form_mode in {'add', 'edit'}:
        if request.method == 'POST':
            client_form = ClientForm(request.POST, instance=client_instance)
            if client_form.is_valid():
                saved_client = client_form.save()
                messages.success(
                    request,
                    f'Client "{saved_client.first_name} {saved_client.last_name}" '
                    f'{"added" if form_mode == "add" else "updated"} successfully.',
                )
                return redirect('list_client')
        else:
            client_form = ClientForm(instance=client_instance)

    return render(
        request,
        'client/list_client.html',
        {
            'client': client_page.object_list,
            'page_obj': client_page,
            'page_limit': page_limit,
            'search_query': search_query,
            'client_form': client_form,
            'client_form_title': 'Add client' if form_mode == 'add' else 'Edit client',
            'client_count': all_clients.count(),
            'male_count': all_clients.filter(gender='Male').count(),
            'female_count': all_clients.filter(gender='Female').count(),
        }
    )

def add_client_view(request):
    return redirect(f"{reverse('list_client')}?client_form=add")

def edit_client_view(request, pk):
    get_object_or_404(Client, pk=pk, is_active=True)
    return redirect(f"{reverse('list_client')}?client_form=edit&client_id={pk}")

def delete_client_view(request, pk):
    client = get_object_or_404(Client, pk=pk, is_active=True)

    if request.method == 'POST':
        client_name = f'{client.first_name} {client.last_name}'
        client.delete()
        messages.success(request, f'Client {client_name} deleted successfully.')
        return redirect('list_client')

    return render(
        request,
        'client/delete_client.html',
        {'client': client}
    )

#BOOKING
def list_booking_view(request):
    all_bookings = Booking.objects.select_related(
        'client', 'showtime', 'showtime__movie', 'seat'
    ).order_by('-payment_date', '-pk')
    search_query = request.GET.get('q', '').strip()
    bookings = all_bookings
    if search_query:
        booking_search = (
            Q(client__first_name__icontains=search_query)
            | Q(client__last_name__icontains=search_query)
            | Q(client__email__icontains=search_query)
            | Q(showtime__movie__title__icontains=search_query)
            | Q(seat__seat_number__icontains=search_query)
            | Q(payment_status__icontains=search_query)
            | Q(payment_method__icontains=search_query)
        )
        if search_query.replace('.', '', 1).isdigit():
            booking_search |= Q(amount=search_query)
            if search_query.isdigit():
                booking_search |= Q(pk=int(search_query))
        bookings = bookings.filter(booking_search)
    page_limit = request.GET.get('limit', '10')
    if page_limit not in {'10', '25', '50'}:
        page_limit = '10'
    booking_page = Paginator(bookings, int(page_limit)).get_page(request.GET.get('page'))
    paid_bookings = all_bookings.filter(payment_status='Paid')

    form_mode = request.GET.get('booking_form')
    booking_instance = None
    if form_mode == 'edit':
        booking_instance = get_object_or_404(Booking, pk=request.GET.get('booking_id'))

    booking_form = None
    if form_mode in {'add', 'edit'}:
        if request.method == 'POST':
            booking_form = BookingForm(request.POST, instance=booking_instance)
            if booking_form.is_valid():
                booking_form.save()
                messages.success(
                    request,
                    'Booking saved successfully.' if form_mode == 'add' else 'Booking updated successfully.',
                )
                return redirect('list_booking')
        else:
            booking_form = BookingForm(instance=booking_instance)

    return render(
        request,
        'booking/list_booking.html',
        {
            'booking': booking_page.object_list,
            'page_obj': booking_page,
            'page_limit': page_limit,
            'booking_count': all_bookings.count(),
            'paid_booking_count': paid_bookings.count(),
            'pending_booking_count': all_bookings.filter(payment_status='Pending').count(),
            'booking_revenue': paid_bookings.aggregate(total=Sum('amount'))['total'] or 0,
            'search_query': search_query,
            'booking_form': booking_form,
            'booking_form_title': 'New booking' if form_mode == 'add' else 'Edit booking',
        }
    )

def add_booking_view(request):
    return redirect(f"{reverse('list_booking')}?booking_form=add")

def edit_booking_view(request, pk):
    get_object_or_404(Booking, pk=pk)
    return redirect(f"{reverse('list_booking')}?booking_form=edit&booking_id={pk}")
def delete_booking_view(request, pk):
    bookings = get_object_or_404(Booking, pk=pk)

    if request.method == 'POST':
        bookings.delete()
        messages.success(request, 'Booking has been deleted successfully.')
        return redirect('list_booking')

    return render(
        request,
        'booking/delete_booking.html',
        {'booking': bookings}
    )


def reports_view(request):
    today = timezone.localdate()
    default_start = today.replace(day=1)
    start_value = request.GET.get('start_date', '')
    end_value = request.GET.get('end_date', '')
    start_date = parse_date(start_value) if start_value else default_start
    end_date = parse_date(end_value) if end_value else today
    date_error = False

    if not start_date or not end_date or start_date > end_date:
        date_error = True
        start_date = default_start
        end_date = today

    report_bookings = Booking.objects.select_related(
        'client', 'showtime', 'showtime__movie', 'showtime__hall', 'seat'
    ).filter(payment_date__range=(start_date, end_date)).order_by('-payment_date', '-pk')
    paid_bookings = report_bookings.filter(payment_status='Paid')

    if request.GET.get('format') == 'html' and not date_error:
        with staticfiles_storage.open('assets/img/logo.png', 'rb') as logo_file:
            logo_data = base64.b64encode(logo_file.read()).decode('ascii')
        download_context = {
            'logo_data_uri': f'data:image/png;base64,{logo_data}',
            'start_date': start_date,
            'end_date': end_date,
            'report_bookings': report_bookings,
            'report_booking_count': report_bookings.count(),
            'report_paid_count': paid_bookings.count(),
            'report_pending_count': report_bookings.filter(payment_status='Pending').count(),
            'report_revenue': paid_bookings.aggregate(total=Sum('amount'))['total'] or 0,
            'system_client_count': Client.objects.filter(is_active=True).count(),
            'system_movie_count': Movie.objects.count(),
            'system_category_count': Category.objects.count(),
            'system_theater_count': Theater.objects.count(),
            'system_hall_count': CinemaHall.objects.count(),
            'system_seat_count': Seat.objects.count(),
            'system_showtime_count': ShowTime.objects.count(),
            'system_booking_count': Booking.objects.count(),
            'system_paid_revenue': Booking.objects.filter(payment_status='Paid').aggregate(total=Sum('amount'))['total'] or 0,
        }
        report_html = render(request, 'reports/download_report.html', download_context).content.decode('utf-8')
        response = HttpResponse(report_html, content_type='text/html; charset=utf-8')
        response['Content-Disposition'] = (
            f'attachment; filename="rk-tickets-system-report-{start_date:%Y%m%d}-{end_date:%Y%m%d}.html"'
        )
        return response

    if request.GET.get('format') == 'csv' and not date_error:
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = (
            f'attachment; filename="rk-tickets-report-{start_date:%Y%m%d}-{end_date:%Y%m%d}.csv"'
        )
        response.write('\ufeff')
        writer = csv.writer(response)
        writer.writerow([
            'OVERALL SYSTEM SUMMARY',
        ])
        writer.writerow(['Metric', 'Value'])
        writer.writerow(['Clients', Client.objects.filter(is_active=True).count()])
        writer.writerow(['Movies', Movie.objects.count()])
        writer.writerow(['Categories', Category.objects.count()])
        writer.writerow(['Theaters', Theater.objects.count()])
        writer.writerow(['Cinema halls', CinemaHall.objects.count()])
        writer.writerow(['Seats', Seat.objects.count()])
        writer.writerow(['Showtimes', ShowTime.objects.count()])
        writer.writerow(['All bookings', Booking.objects.count()])
        writer.writerow(['All-time paid revenue', Booking.objects.filter(payment_status='Paid').aggregate(total=Sum('amount'))['total'] or 0])
        writer.writerow([])
        writer.writerow([f'BOOKINGS RECORDED FROM {start_date} THROUGH {end_date}'])
        writer.writerow([
            'Booking ID', 'Payment date', 'Client', 'Email', 'Movie', 'Show date',
            'Start time', 'Cinema hall', 'Seat', 'Payment status', 'Payment method', 'Amount',
        ])

        def safe_csv_text(value):
            text_value = str(value)
            if text_value.startswith(('=', '+', '-', '@', '\t', '\r')):
                return f"'{text_value}"
            return text_value

        for booking in report_bookings.iterator():
            writer.writerow([
                booking.pk,
                booking.payment_date,
                safe_csv_text(f'{booking.client.first_name} {booking.client.last_name}'),
                safe_csv_text(booking.client.email),
                safe_csv_text(booking.showtime.movie.title),
                booking.showtime.show_date,
                booking.showtime.start_time,
                safe_csv_text(booking.showtime.hall.name),
                safe_csv_text(booking.seat.seat_number),
                safe_csv_text(booking.payment_status),
                safe_csv_text(booking.payment_method),
                booking.amount,
            ])
        return response

    page_limit = request.GET.get('limit', '10')
    if page_limit not in {'10', '25', '50'}:
        page_limit = '10'
    report_page = Paginator(report_bookings, int(page_limit)).get_page(request.GET.get('page'))

    context = {
            'report_bookings': report_page.object_list,
            'page_obj': report_page,
            'page_limit': page_limit,
            'start_date': start_date,
            'end_date': end_date,
            'date_error': date_error,
            'report_booking_count': report_bookings.count(),
            'report_paid_count': paid_bookings.count(),
            'report_pending_count': report_bookings.filter(payment_status='Pending').count(),
            'report_revenue': paid_bookings.aggregate(total=Sum('amount'))['total'] or 0,
            'system_client_count': Client.objects.filter(is_active=True).count(),
            'system_movie_count': Movie.objects.count(),
            'system_category_count': Category.objects.count(),
            'system_theater_count': Theater.objects.count(),
            'system_hall_count': CinemaHall.objects.count(),
            'system_seat_count': Seat.objects.count(),
            'system_showtime_count': ShowTime.objects.count(),
            'system_booking_count': Booking.objects.count(),
            'system_paid_revenue': Booking.objects.filter(payment_status='Paid').aggregate(total=Sum('amount'))['total'] or 0,
        }
    template_name = 'reports/_report_content.html' if request.GET.get('modal') == '1' else 'reports/list_reports.html'
    return render(request, template_name, context)
