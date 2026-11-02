from django.core.management.base import BaseCommand
from django.utils import timezone
from donations.models import Donation


class Command(BaseCommand):
    help = 'Mark donations as expired if their available_until date has passed'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show which donations would be expired without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        now = timezone.now()

        expired_donations = Donation.objects.filter(
            status__in=['published', 'reserved'],
            available_until__lt=now,
        )

        count = expired_donations.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS('No donations to expire.'))
            return

        if dry_run:
            self.stdout.write(f'Would expire {count} donations:')
            for donation in expired_donations:
                self.stdout.write(f'  - {donation.title} (ID: {donation.id}, expired at {donation.available_until})')
            return

        updated = expired_donations.update(status='expired')
        self.stdout.write(self.style.SUCCESS(f'Successfully expired {updated} donations.'))

        for donation in expired_donations:
            self.stdout.write(f'  - {donation.title} (ID: {donation.id})')