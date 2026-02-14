# books/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r"users", views.UserViewSet)
router.register(r"authors", views.AuthorViewSet)
router.register(r"books", views.BookViewSet)
router.register(r"borrows", views.BookBorrowViewSet)

urlpatterns = [
    path("", include(router.urls)),
]
