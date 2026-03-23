from django.contrib import admin
from users.models import User, RolePermission, Role, CustomPermission

# Register your models here.
admin.site.register(User)

class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ('role', 'permission', 'id')
    list_filter = ('role', 'permission')
    search_fields = ('role__name', 'permission__name')
    ordering = ('role__name', 'permission__name')

admin.site.register(RolePermission, RolePermissionAdmin)
admin.site.register(Role)
admin.site.register(CustomPermission)