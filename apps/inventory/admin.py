from django.contrib import admin

from .models import Category, Product, StockMovement, Warehouse

admin.site.register([Warehouse, Category, Product, StockMovement])
