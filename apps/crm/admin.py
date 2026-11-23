from django.contrib import admin

from .models import Interaction, Partner

admin.site.register([Partner, Interaction])
