import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction


class Command(BaseCommand):
    help = 'Create the initial admin superuser when configured.'

    def handle(self, *args, **options):
        password = os.environ.get('INITIAL_SUPERUSER_PASSWORD')
        if not password:
            self.stdout.write('Initial superuser not configured; skipping.')
            return

        username = os.environ.get('INITIAL_SUPERUSER_USERNAME', 'admin').strip()
        if not username:
            raise CommandError('INITIAL_SUPERUSER_USERNAME cannot be empty.')

        user_model = get_user_model()
        user = user_model.objects.filter(username=username).first()
        if user and user.is_superuser:
            self.stdout.write(f'Superuser {username!r} already exists; skipping.')
            return

        try:
            with transaction.atomic():
                if user:
                    user.is_staff = True
                    user.is_superuser = True
                    user.set_password(password)
                    user.save(
                        update_fields=('is_staff', 'is_superuser', 'password')
                    )
                else:
                    user_model.objects.create_superuser(
                        username=username,
                        password=password,
                    )
        except IntegrityError:
            if user_model.objects.filter(username=username).exists():
                self.stdout.write(
                    f'Superuser {username!r} already exists; skipping.'
                )
                return
            raise

        self.stdout.write(
            self.style.SUCCESS(f'Created initial superuser {username!r}.')
        )
