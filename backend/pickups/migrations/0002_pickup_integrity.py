from decimal import Decimal

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def verify_existing_pickups(apps, schema_editor):
    Pickup = apps.get_model('pickups', 'Pickup')
    alias = schema_editor.connection.alias
    pickups = Pickup.objects.using(alias)

    missing_allocation = pickups.filter(allocation__isnull=True).count()
    missing_request = pickups.filter(request__isnull=True).count()
    duplicate_allocations = (
        pickups.exclude(allocation__isnull=True)
        .values('allocation_id')
        .annotate(total=models.Count('id'))
        .filter(total__gt=1)
        .count()
    )
    inconsistent_links = pickups.exclude(allocation__isnull=True).exclude(
        request_id=models.F('allocation__request_id')
    ).count()
    invalid_requests = pickups.exclude(
        request__status__in=('approved', 'partially_approved')
    ).count()
    inconsistent_donations = pickups.exclude(allocation__isnull=True).exclude(
        donation_id=models.F('allocation__request__donation_id')
    ).count()
    invalid_statuses = pickups.exclude(
        status__in=('scheduled', 'in_progress', 'completed', 'cancelled', 'no_show')
    ).count()
    completed_without_actual = pickups.filter(status='completed').filter(
        models.Q(actual_quantity_kg__isnull=True) | models.Q(actual_quantity_kg__lte=0)
    ).count()
    invalid_legacy_actual = 0
    for pickup in pickups.filter(actual_quantity_kg__isnull=False).values(
        'status', 'actual_quantity_kg', 'allocation__approved_quantity',
        'allocation__approved_unit',
    ).iterator():
        unit = pickup['allocation__approved_unit']
        actual = Decimal(pickup['actual_quantity_kg'])
        approved = Decimal(pickup['allocation__approved_quantity'])
        if (
            pickup['status'] != 'completed'
            or unit not in ('kg', 'g')
            or actual <= 0
            or actual > approved * (Decimal('0.001') if unit == 'g' else Decimal('1'))
        ):
            invalid_legacy_actual += 1
    invalid_timestamps = 0
    for pickup in pickups.values(
        'status', 'started_at', 'completed_at', 'cancelled_at', 'no_show_at',
    ).iterator():
        status = pickup['status']
        timestamps = (
            pickup['started_at'],
            pickup['completed_at'],
            pickup['cancelled_at'],
            pickup['no_show_at'],
        )
        valid = {
            'scheduled': timestamps == (None, None, None, None),
            'in_progress': timestamps[0] is not None and timestamps[1:] == (None, None, None),
            'completed': timestamps[0] is not None and timestamps[1] is not None and timestamps[2:] == (None, None),
            'cancelled': timestamps[:2] == (None, None) and timestamps[2] is not None and timestamps[3] is None,
            'no_show': timestamps[:3] == (None, None, None) and timestamps[3] is not None,
        }.get(status, False)
        if not valid:
            invalid_timestamps += 1

    failures = {
        'missing allocation': missing_allocation,
        'missing request': missing_request,
        'duplicate allocations': duplicate_allocations,
        'inconsistent allocation/request links': inconsistent_links,
        'inconsistent donation links': inconsistent_donations,
        'ineligible request states': invalid_requests,
        'unknown statuses': invalid_statuses,
        'completed pickups without a recorded actual quantity': completed_without_actual,
        'legacy quantities that cannot be safely represented in kg': invalid_legacy_actual,
        'inconsistent lifecycle timestamps': invalid_timestamps,
    }
    failures = {label: count for label, count in failures.items() if count}
    if failures:
        details = ', '.join(f'{label}: {count}' for label, count in failures.items())
        raise RuntimeError(
            'Pickup integrity migration stopped before applying constraints. '
            f'Review and correct existing pickup records explicitly ({details}).'
        )

    # Preserve legacy kg values and tag them with their original unit.
    pickups.filter(actual_quantity_kg__isnull=False).update(
        actual_quantity=models.F('actual_quantity_kg'),
        actual_unit='kg',
    )


class Migration(migrations.Migration):

    dependencies = [
        ('pickups', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='pickup',
            name='actual_quantity',
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='pickup',
            name='actual_unit',
            field=models.CharField(
                blank=True,
                choices=[
                    ('kg', 'Kilograms'), ('g', 'Grams'), ('l', 'Liters'),
                    ('ml', 'Milliliters'), ('units', 'Units/Items'),
                    ('boxes', 'Boxes'), ('trays', 'Trays'),
                ],
                max_length=10,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='pickup',
            name='cancelled_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='pickup',
            name='no_show_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(verify_existing_pickups, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='pickup',
            name='status',
            field=models.CharField(
                choices=[
                    ('scheduled', 'Scheduled'), ('in_progress', 'In Progress'),
                    ('completed', 'Completed'), ('cancelled', 'Cancelled'),
                    ('no_show', 'No Show'),
                ],
                default='scheduled',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='pickup',
            name='request',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='pickups',
                to='donation_requests.donationrequest',
            ),
        ),
        migrations.AlterField(
            model_name='pickup',
            name='allocation',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='pickups',
                to='donation_requests.donationallocation',
            ),
        ),
        migrations.AddConstraint(
            model_name='pickup',
            constraint=models.UniqueConstraint(
                fields=('allocation',),
                name='uniq_pickup_per_allocation',
            ),
        ),
        migrations.AddConstraint(
            model_name='pickup',
            constraint=models.CheckConstraint(
                check=(
                    models.Q(actual_quantity__isnull=True, actual_unit__isnull=True)
                    | models.Q(actual_quantity__isnull=False, actual_unit__isnull=False)
                ),
                name='pickup_actual_quantity_unit_pair',
            ),
        ),
        migrations.AddConstraint(
            model_name='pickup',
            constraint=models.CheckConstraint(
                check=models.Q(actual_quantity__isnull=True) | models.Q(actual_quantity__gte=0),
                name='pickup_actual_quantity_nonnegative',
            ),
        ),
        migrations.AddConstraint(
            model_name='pickup',
            constraint=models.CheckConstraint(
                check=(
                    models.Q(
                        status='scheduled',
                        started_at__isnull=True,
                        completed_at__isnull=True,
                        cancelled_at__isnull=True,
                        no_show_at__isnull=True,
                        actual_quantity__isnull=True,
                        actual_unit__isnull=True,
                    )
                    | models.Q(
                        status='in_progress',
                        started_at__isnull=False,
                        completed_at__isnull=True,
                        cancelled_at__isnull=True,
                        no_show_at__isnull=True,
                        actual_quantity__isnull=True,
                        actual_unit__isnull=True,
                    )
                    | models.Q(
                        status='completed',
                        started_at__isnull=False,
                        completed_at__isnull=False,
                        actual_quantity__gt=0,
                        actual_unit__isnull=False,
                        cancelled_at__isnull=True,
                        no_show_at__isnull=True,
                    )
                    | models.Q(
                        status='cancelled',
                        started_at__isnull=True,
                        completed_at__isnull=True,
                        cancelled_at__isnull=False,
                        no_show_at__isnull=True,
                        actual_quantity__isnull=True,
                        actual_unit__isnull=True,
                    )
                    | models.Q(
                        status='no_show',
                        started_at__isnull=True,
                        completed_at__isnull=True,
                        cancelled_at__isnull=True,
                        no_show_at__isnull=False,
                        actual_quantity__isnull=True,
                        actual_unit__isnull=True,
                    )
                ),
                name='pickup_status_timestamp_consistency',
            ),
        ),
    ]
