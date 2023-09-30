from django.urls import path

from app import views

app_name = 'app'

urlpatterns = [
    path('', views.home, name='home'),
    path('accounts/profile/', views.profile, name='profile'),
    path('projects/', views.projects, name='projects'),
    path('projects/<int:projectid>/', views.view_project, name='view_project'),
    path('projects/<int:projectid>/list/<str:unittype>', views.list_types,
         name='list_types'),
    path('projects/<int:projectid>/add/<str:unittype>', views.create_unit,
         name='create_unit'),
    path('projects/<int:projectid>/view/<int:unitid>/', views.view_unit,
         name='view_unit'),
    path('api/<int:projectid>/get/', views.get_unit, name='get_unit'),
    path('api/<int:projectid>/set/', views.set_features,
         name='set_features'),
    path('api/<int:projectid>/add/', views.add_unit, name='add_unit'),
    path('api/<int:projectid>/edit_times/', views.modification_times,
         name='edit_times'),
]
