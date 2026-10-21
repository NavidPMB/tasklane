"""Minuten bleiben API-Einheit; importierte Millisekunden sind maßgeblich."""
from django.db.models import BigIntegerField, F, FloatField, Sum, Value
from django.db.models.functions import Coalesce, Cast


def minute_sum(prefix=''):
    duration = Coalesce(F(prefix + 'duration_ms'), F(prefix + 'minutes') * Value(60000), output_field=BigIntegerField())
    return Cast(Coalesce(Sum(duration), Value(0), output_field=BigIntegerField()), FloatField()) / Value(60000.0)


def external_person_data(person):
    return {'id': -person.pk, 'name': person.name, 'email': person.email, 'is_external': True, 'is_active': False}
