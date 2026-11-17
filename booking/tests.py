import os
from io import BytesIO
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from booking.models import (
    Booking,
    Category,
    CinemaHall,
    Client,
    Movie,
    Seat,
    ShowTime,
    Theater,
)


class BootstrapAdminCommandTests(TestCase):
    def test_creates_admin_superuser_only_when_password_is_configured(self):
        with patch.dict(os.environ, {'INITIAL_SUPERUSER_PASSWORD': 'test-only-password'}):
            call_command('bootstrap_admin')
            call_command('bootstrap_admin')

        admin = get_user_model().objects.get(username='admin')
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.check_password('test-only-password'))

    def test_skips_when_password_is_not_configured(self):
        with patch.dict(os.environ):
            os.environ.pop('INITIAL_SUPERUSER_PASSWORD', None)
            call_command('bootstrap_admin')

        self.assertFalse(get_user_model().objects.filter(username='admin').exists())


class AuthenticationFlowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='cinema-manager',
            password='SecureTestPassword123!',
        )

    def test_dashboard_redirects_to_login_for_anonymous_users(self):
        response = self.client.get(reverse('index_page'))

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('index_page')}",
        )

    def test_login_authenticates_user_and_shows_logout_control(self):
        response = self.client.post(
            reverse('login'),
            {'username': self.user.username, 'password': 'SecureTestPassword123!'},
        )

        self.assertRedirects(response, reverse('index_page'))
        dashboard = self.client.get(reverse('index_page'))
        self.assertContains(dashboard, 'aria-label="Logout"')
        self.assertContains(dashboard, 'Welcome, cinema-manager!')
        self.assertNotContains(dashboard, 'aria-label="Login"')
        self.assertContains(dashboard, 'aria-label="Edit profile"')

    def test_login_uses_custom_fields_and_rejects_invalid_credentials(self):
        response = self.client.post(
            reverse('login'),
            {'username': self.user.username, 'password': 'wrong-password'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'The username or password you entered is incorrect.')
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="password"')
        self.assertNotContains(response, 'name="csrfmiddlewaretoken" value=""')

    def test_login_ignores_external_next_url(self):
        response = self.client.post(
            f"{reverse('login')}?next=https://example.com/",
            {
                'username': self.user.username,
                'password': 'SecureTestPassword123!',
                'next': 'https://example.com/',
            },
        )

        self.assertRedirects(response, reverse('index_page'))

    def test_signup_creates_and_authenticates_standard_user(self):
        response = self.client.post(
            reverse('signup'),
            {
                'first_name': 'New',
                'last_name': 'Customer',
                'gender': 'Female',
                'phone_number': '+1234567890',
                'email': 'new-customer@example.com',
                'username': 'new-customer',
                'password1': 'AnotherSecurePassword123!',
                'password2': 'AnotherSecurePassword123!',
            },
        )

        self.assertRedirects(response, reverse('index_page'))
        new_user = get_user_model().objects.get(username='new-customer')
        client_profile = Client.objects.get(email='new-customer@example.com')
        self.assertEqual(new_user.first_name, 'New')
        self.assertEqual(new_user.last_name, 'Customer')
        self.assertEqual(new_user.email, 'new-customer@example.com')
        self.assertEqual(client_profile.first_name, 'New')
        self.assertEqual(client_profile.last_name, 'Customer')
        self.assertEqual(client_profile.gender, 'Female')
        self.assertEqual(client_profile.phone_number, '+1234567890')
        self.assertFalse(new_user.is_staff)
        self.assertFalse(new_user.is_superuser)
        self.assertEqual(
            int(self.client.session['_auth_user_id']),
            new_user.pk,
        )

    def test_signup_shows_validation_errors_for_mismatched_passwords(self):
        response = self.client.post(
            reverse('signup'),
            {
                'first_name': 'New',
                'last_name': 'Customer',
                'gender': 'Female',
                'phone_number': '+1234567890',
                'email': 'new-customer@example.com',
                'username': 'new-customer',
                'password1': 'AnotherSecurePassword123!',
                'password2': 'DifferentSecurePassword123!',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'The two password fields didn’t match.')
        self.assertFalse(get_user_model().objects.filter(username='new-customer').exists())
        self.assertFalse(Client.objects.filter(email='new-customer@example.com').exists())

    def test_signup_allows_password_similar_to_account_names(self):
        response = self.client.post(
            reverse('signup'),
            {
                'first_name': 'New',
                'last_name': 'Customer',
                'gender': 'Female',
                'phone_number': '+1234567890',
                'email': 'new-customer@example.com',
                'username': 'new-customer',
                'password1': 'NewCustomer123!Secure',
                'password2': 'NewCustomer123!Secure',
            },
        )

        self.assertRedirects(response, reverse('index_page'))
        self.assertTrue(
            get_user_model().objects.filter(username='new-customer').exists()
        )

    def test_signup_ignores_external_next_url(self):
        response = self.client.post(
            f"{reverse('signup')}?next=https://example.com/",
            {
                'first_name': 'New',
                'last_name': 'Customer',
                'gender': 'Female',
                'phone_number': '+1234567890',
                'email': 'new-customer@example.com',
                'username': 'new-customer',
                'password1': 'AnotherSecurePassword123!',
                'password2': 'AnotherSecurePassword123!',
                'next': 'https://example.com/',
            },
        )

        self.assertRedirects(response, reverse('index_page'))

    def test_signup_form_collects_account_and_contact_fields_without_guides(self):
        response = self.client.get(reverse('signup'))

        for field in (
            'first_name',
            'last_name',
            'gender',
            'phone_number',
            'email',
            'username',
            'password1',
            'password2',
        ):
            self.assertContains(response, f'name="{field}"')
        self.assertNotContains(response, 'Your password can’t be too similar')
        self.assertNotContains(response, 'Your password must contain')

    def test_signup_rejects_an_email_already_used_by_a_client(self):
        Client.objects.create(
            first_name='Existing',
            last_name='Customer',
            email='existing@example.com',
            phone_number='5551234',
            gender='Male',
        )

        response = self.client.post(
            reverse('signup'),
            {
                'first_name': 'New',
                'last_name': 'Customer',
                'gender': 'Female',
                'phone_number': '+1234567890',
                'email': 'existing@example.com',
                'username': 'new-customer',
                'password1': 'AnotherSecurePassword123!',
                'password2': 'AnotherSecurePassword123!',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'An account with this email already exists.')
        self.assertFalse(get_user_model().objects.filter(username='new-customer').exists())

    def test_profile_updates_user_and_client_details(self):
        client_profile = Client.objects.create(
            first_name='Cinema',
            last_name='Manager',
            email='cinema-manager@example.com',
            phone_number='5551234',
            gender='Male',
        )
        self.user.first_name = 'Cinema'
        self.user.last_name = 'Manager'
        self.user.email = client_profile.email
        self.user.save()
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('profile'),
            {
                'first_name': 'Updated',
                'last_name': 'Manager',
                'gender': 'Female',
                'phone_number': '+1234567890',
                'email': 'updated@example.com',
                'username': 'updated-manager',
            },
        )

        self.assertRedirects(response, reverse('profile'))
        self.user.refresh_from_db()
        client_profile.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Updated')
        self.assertEqual(self.user.last_name, 'Manager')
        self.assertEqual(self.user.email, 'updated@example.com')
        self.assertEqual(self.user.username, 'updated-manager')
        self.assertEqual(client_profile.first_name, 'Updated')
        self.assertEqual(client_profile.gender, 'Female')
        self.assertEqual(client_profile.phone_number, '+1234567890')
        self.assertEqual(client_profile.email, 'updated@example.com')

    def test_profile_requires_authentication(self):
        response = self.client.get(reverse('profile'))

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('profile')}",
        )

    def test_profile_picture_upload_updates_top_nav_avatar(self):
        client_profile = Client.objects.create(
            first_name='Cinema',
            last_name='Manager',
            email='cinema-manager@example.com',
            phone_number='5551234',
            gender='Male',
        )
        self.user.first_name = 'Cinema'
        self.user.last_name = 'Manager'
        self.user.email = client_profile.email
        self.user.save()
        self.client.force_login(self.user)
        image_buffer = BytesIO()
        Image.new('RGB', (1, 1), color='orange').save(image_buffer, format='PNG')

        with TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                response = self.client.post(
                    reverse('profile'),
                    {
                        'first_name': 'Cinema',
                        'last_name': 'Manager',
                        'gender': 'Male',
                        'phone_number': '5551234',
                        'email': client_profile.email,
                        'username': self.user.username,
                        'profile_picture': SimpleUploadedFile(
                            'avatar.png',
                            image_buffer.getvalue(),
                            content_type='image/png',
                        ),
                    },
                )

                self.assertRedirects(response, reverse('profile'))
                client_profile.refresh_from_db()
                self.assertTrue(client_profile.profile_picture)
                self.assertTrue(client_profile.profile_picture.storage.exists(
                    client_profile.profile_picture.name
                ))
                with client_profile.profile_picture.open('rb') as image_file:
                    with Image.open(image_file) as saved_picture:
                        self.assertEqual(saved_picture.size, (512, 512))
                profile_page = self.client.get(reverse('profile'))
                self.assertContains(
                    profile_page,
                    f'src="{client_profile.profile_picture.url}"',
                )
                self.assertContains(profile_page, 'aria-label="Edit profile"')
                self.assertContains(profile_page, 'data-crop-stage')
                self.assertContains(profile_page, 'id="profilePictureZoom"')
                self.assertContains(profile_page, 'Adjust your picture')
                self.assertContains(profile_page, 'The square shown is what will be saved.')

    def test_logout_ends_session_and_requires_post(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('logout')).status_code, 405)
        response = self.client.post(reverse('logout'))

        self.assertRedirects(response, reverse('login'))
        self.assertRedirects(
            self.client.get(reverse('index_page')),
            f"{reverse('login')}?next={reverse('index_page')}",
        )


class SettingsPageTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='customer',
            password='SecureTestPassword123!',
        )
        self.admin_user = get_user_model().objects.create_superuser(
            username='site-admin',
            email='site-admin@example.com',
            password='SecureAdminPassword123!',
        )

    def test_settings_page_includes_profile_and_theme_options(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('settings'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('profile'))
        self.assertContains(response, 'id="themeToggle"')
        self.assertContains(response, 'Day mode')
        self.assertContains(response, 'Night mode')
        self.assertContains(response, 'Role assignments are managed by a superuser.')
        self.assertNotContains(response, 'Assign user roles')

    def test_superuser_can_assign_staff_and_customer_roles(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('settings'),
            {'user': self.user.pk, 'role': 'staff'},
        )

        self.assertRedirects(response, reverse('settings'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_staff)

        response = self.client.post(
            reverse('settings'),
            {'user': self.user.pk, 'role': 'customer'},
        )

        self.assertRedirects(response, reverse('settings'))
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff)

    def test_staff_assignment_removes_client_from_active_list_and_preserves_bookings(self):
        self.user.email = 'staff-candidate@example.com'
        self.user.save(update_fields=['email'])
        client_profile = Client.objects.create(
            first_name='Staff',
            last_name='Candidate',
            email=self.user.email,
            phone_number='5551234',
            gender='Male',
        )
        theater = Theater.objects.create(name='Main Theater', location='Town')
        hall = CinemaHall.objects.create(
            theater=theater,
            name='Screen 1',
            capacity=1,
        )
        seat = Seat.objects.create(seat_number='A1', hall=hall)
        category = Category.objects.create(category_name='Drama')
        movie = Movie.objects.create(
            title='Sample Film',
            duration=90,
            rating='PG-13',
            language='English',
            release_year=timezone.localdate().year,
            category=category,
        )
        showtime = ShowTime.objects.create(
            movie=movie,
            hall=hall,
            show_date=timezone.localdate(),
            start_time='10:00',
            end_time='11:30',
        )
        booking = Booking.objects.create(
            client=client_profile,
            showtime=showtime,
            seat=seat,
            amount='10.00',
            payment_status='Paid',
            payment_method='Cash',
        )
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('settings'),
            {'user': self.user.pk, 'role': 'staff'},
        )

        self.assertRedirects(response, reverse('settings'))
        client_profile.refresh_from_db()
        self.assertFalse(client_profile.is_active)
        self.assertTrue(Booking.objects.filter(pk=booking.pk).exists())
        self.assertFalse(
            Client.objects.filter(
                pk=client_profile.pk,
                is_active=True,
            ).exists(),
        )

        response = self.client.get(reverse('list_client'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Staff Candidate')

    def test_role_dropdown_shows_full_names_for_all_other_non_superusers(self):
        self.user.first_name = 'Taylor'
        self.user.last_name = 'Customer'
        self.user.save(update_fields=['first_name', 'last_name'])
        inactive_user = get_user_model().objects.create_user(
            username='inactive-account',
            first_name='Morgan',
            last_name='Inactive',
            is_active=False,
        )
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('settings'))

        self.assertContains(
            response,
            f'<option value="{self.user.pk}">Taylor Customer</option>',
            html=True,
        )
        self.assertContains(
            response,
            f'<option value="{inactive_user.pk}">Morgan Inactive</option>',
            html=True,
        )
        self.assertNotContains(response, f'<option value="{self.admin_user.pk}">')

    def test_standard_user_cannot_submit_role_assignment(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('settings'),
            {'user': self.admin_user.pk, 'role': 'staff'},
        )

        self.assertEqual(response.status_code, 403)
        self.admin_user.refresh_from_db()
        self.assertTrue(self.admin_user.is_superuser)


class DashboardSeatCountTests(TestCase):
    def test_dashboard_counts_booked_seat_per_showtime(self):
        user = get_user_model().objects.create_user(
            username='dashboard-user',
            password='SecureTestPassword123!',
        )
        self.client.force_login(user)
        client_profile = Client.objects.create(
            first_name='Seat',
            last_name='Booker',
            email='seat-booker@example.com',
            phone_number='5551234',
            gender='Male',
        )
        theater = Theater.objects.create(name='Main Theater', location='Town')
        hall = CinemaHall.objects.create(
            theater=theater,
            name='Screen 1',
            capacity=2,
        )
        seat = Seat.objects.create(seat_number='A1', hall=hall)
        category = Category.objects.create(category_name='Drama')
        movie = Movie.objects.create(
            title='Sample Film',
            duration=90,
            rating='PG-13',
            language='English',
            release_year=timezone.localdate().year,
            category=category,
        )
        first_show = ShowTime.objects.create(
            movie=movie,
            hall=hall,
            show_date=timezone.localdate(),
            start_time='10:00',
            end_time='11:30',
        )
        second_show = ShowTime.objects.create(
            movie=movie,
            hall=hall,
            show_date=timezone.localdate(),
            start_time='13:00',
            end_time='14:30',
        )
        for show in (first_show, second_show):
            Booking.objects.create(
                client=client_profile,
                showtime=show,
                seat=seat,
                amount='10.00',
                payment_status='Paid',
                payment_method='Cash',
            )

        response = self.client.get(reverse('index_page'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['booked_seat_count'], 2)
        self.assertEqual(response.context['booked_seats'], 2)
        self.assertEqual(response.context['total_seats'], 4)
        self.assertEqual(response.context['seat_fill_percent'], 50)
        self.assertContains(response, '<p>Seats booked</p><strong>2</strong>', html=True)
        self.assertContains(response, '<i class="legend-dot booked"></i>Booked <strong>2</strong>', html=True)
        self.assertContains(response, '<i class="legend-dot available"></i>Total seats <strong>4</strong>', html=True)
        self.assertNotContains(response, 'videos/trailer-1.mp4')
        self.assertNotContains(response, 'videos/trailer-2.mp4')
        self.assertNotContains(response, 'videos/trailer-3.mp4')
        self.assertNotContains(response, '<video')

    def test_dashboard_shows_configured_capacity_when_no_showtimes_exist(self):
        user = get_user_model().objects.create_user(
            username='capacity-user',
            password='SecureTestPassword123!',
        )
        self.client.force_login(user)
        theater = Theater.objects.create(name='Main Theater', location='Town')
        CinemaHall.objects.create(
            theater=theater,
            name='Screen 1',
            capacity=120,
        )
        CinemaHall.objects.create(
            theater=theater,
            name='Screen 2',
            capacity=80,
        )

        response = self.client.get(reverse('index_page'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_seats'], 200)
        self.assertEqual(response.context['booked_seats'], 0)
        self.assertEqual(response.context['seat_fill_percent'], 0)
        self.assertContains(response, '<i class="legend-dot available"></i>Total seats <strong>200</strong>', html=True)
