from io import BytesIO

from django import forms
from django.core.files.base import ContentFile
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction
from django.db.models import Q
from PIL import Image, ImageOps

from booking.models import Theater, Client, CinemaHall, Seat, ShowTime, Category, Movie, Booking


class AccountCreationForm(UserCreationForm):
    first_name = forms.CharField(max_length=100)
    last_name = forms.CharField(max_length=100)
    gender = forms.ChoiceField(choices=Client._meta.get_field('gender').choices)
    phone_number = forms.CharField(max_length=15, label='Contact')
    email = forms.EmailField(max_length=200)

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = (
            'first_name',
            'last_name',
            'gender',
            'phone_number',
            'email',
            'username',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_fields([
            'first_name',
            'last_name',
            'gender',
            'phone_number',
            'email',
            'username',
            'password1',
            'password2',
        ])
        self.fields['username'].widget.attrs.update({
            'autocomplete': 'username',
        })
        self.fields['first_name'].widget.attrs['autocomplete'] = 'given-name'
        self.fields['last_name'].widget.attrs['autocomplete'] = 'family-name'
        self.fields['phone_number'].widget.attrs.update({
            'autocomplete': 'tel',
            'type': 'tel',
        })
        self.fields['email'].widget.attrs.update({
            'autocomplete': 'email',
            'type': 'email',
        })
        self.fields['password1'].widget.attrs['autocomplete'] = 'new-password'
        self.fields['password2'].widget.attrs['autocomplete'] = 'new-password'

    def clean_email(self):
        email = self.cleaned_data['email']
        if Client.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']

        if commit:
            with transaction.atomic():
                user.save()
                Client.objects.create(
                    first_name=user.first_name,
                    last_name=user.last_name,
                    gender=self.cleaned_data['gender'],
                    phone_number=self.cleaned_data['phone_number'],
                    email=user.email,
                )
        return user


class ProfileEditForm(forms.Form):
    first_name = forms.CharField(max_length=100)
    last_name = forms.CharField(max_length=100)
    gender = forms.ChoiceField(choices=Client._meta.get_field('gender').choices)
    phone_number = forms.CharField(max_length=15, label='Contact')
    email = forms.EmailField(max_length=200)
    username = forms.CharField(max_length=get_user_model()._meta.get_field('username').max_length)
    profile_picture = forms.ImageField(required=False, label='Profile picture')

    def __init__(self, *args, user, client=None, **kwargs):
        self.user = user
        self.client_profile = client
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.initial.update({
                'first_name': user.first_name,
                'last_name': user.last_name,
                'gender': client.gender if client else '',
                'phone_number': client.phone_number if client else '',
                'email': client.email if client else user.email,
                'username': user.get_username(),
            })

    def clean_username(self):
        username = self.cleaned_data['username']
        users = get_user_model()._default_manager.exclude(pk=self.user.pk)
        if users.filter(username__iexact=username).exists():
            raise forms.ValidationError('This username is already in use.')
        return username

    def clean_email(self):
        email = self.cleaned_data['email']
        clients = Client.objects.filter(email__iexact=email)
        if self.client_profile:
            clients = clients.exclude(pk=self.client_profile.pk)
        if clients.exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def save(self):
        with transaction.atomic():
            self.user.first_name = self.cleaned_data['first_name']
            self.user.last_name = self.cleaned_data['last_name']
            self.user.email = self.cleaned_data['email']
            self.user.username = self.cleaned_data['username']
            self.user.save()
            client = self.client_profile or Client()
            client.first_name = self.user.first_name
            client.last_name = self.user.last_name
            client.gender = self.cleaned_data['gender']
            client.phone_number = self.cleaned_data['phone_number']
            client.email = self.user.email
            client.is_active = not self.user.is_staff
            uploaded_picture = self.cleaned_data.get('profile_picture')
            if uploaded_picture:
                with Image.open(uploaded_picture) as image:
                    square_picture = ImageOps.fit(
                        ImageOps.exif_transpose(image).convert('RGB'),
                        (512, 512),
                        method=Image.Resampling.LANCZOS,
                    )
                    picture_content = BytesIO()
                    square_picture.save(
                        picture_content,
                        format='JPEG',
                        quality=90,
                        optimize=True,
                    )
                client.profile_picture.save(
                    'profile-picture.jpg',
                    ContentFile(picture_content.getvalue()),
                    save=False,
                )
            client.save()
            self.client_profile = client
        return self.user


class UserChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.get_full_name() or obj.get_username()


class RoleAssignmentForm(forms.Form):
    user = UserChoiceField(
        queryset=get_user_model().objects.none(),
        label='Account',
    )
    role = forms.ChoiceField(
        choices=(
            ('customer', 'Customer'),
            ('staff', 'Staff'),
        ),
    )

    def __init__(self, *args, assigning_user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['user'].queryset = get_user_model().objects.filter(
            is_superuser=False,
        ).exclude(pk=assigning_user.pk).order_by('username')

    def save(self):
        user = self.cleaned_data['user']
        user.is_staff = self.cleaned_data['role'] == 'staff'
        with transaction.atomic():
            user.save(update_fields=['is_staff'])
            if user.email:
                Client.objects.filter(email__iexact=user.email).update(
                    is_active=not user.is_staff,
                )
        return user


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = [
            'first_name',
            'last_name',
            'email',
            'phone_number',
            'gender'
        ]

class TheaterForm(forms.ModelForm):
    class Meta:
        model = Theater
        fields = [
            'name',
            'location'
        ]

class CinemaHallForm(forms.ModelForm):
    class Meta:
        model = CinemaHall
        fields = [
            'theater',
            'name',
            'capacity'
        ]

class SeatForm(forms.ModelForm):
    class Meta:
        model = Seat
        fields = [
            'seat_number',
            'hall'
        ]

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = [
            'category_name'
        ]

class MovieForm(forms.ModelForm):
    class Meta:
        model = Movie
        fields = [
            'title',
            'duration',
            'rating',
            'language',
            'release_year',
            'category'
        ]

class ShowTimeForm(forms.ModelForm):
    class Meta:
        model = ShowTime
        widgets = {
            'show_date': forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
        }
        fields = [
            'movie',
            'hall',
            'show_date',
            'start_time',
            'end_time'
        ]

class BookingForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        clients = Client.objects.filter(is_active=True)
        if self.instance.pk and self.instance.client_id:
            clients = Client.objects.filter(
                Q(is_active=True) | Q(pk=self.instance.client_id),
            )
        self.fields['client'].queryset = clients.order_by(
            'first_name',
            'last_name',
            'pk',
        )

    class Meta:
        model = Booking
        fields = [
            'client',
            'showtime',
            'seat',
            'amount',
            'payment_status',
            'payment_method'
        ]
