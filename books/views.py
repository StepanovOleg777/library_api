# books/views.py
from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.views.decorators.cache import never_cache
from django.utils.decorators import method_decorator
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from datetime import date

from .models import User, Author, Book, BookBorrow
from .serializers import (
    UserSerializer,
    AuthorSerializer,
    BookSerializer,
    BookBorrowSerializer,
    BookReturnSerializer,
)


class IsAdminOrReadOnly(permissions.BasePermission):
    """Доступ на запись только для админов"""

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_staff


class UserViewSet(viewsets.ModelViewSet):
    """ViewSet для работы с читателями"""

    queryset = User.objects.all().order_by("id")
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = [
        "username",
        "email",
        "first_name",
        "last_name",
        "library_card_number",
    ]

    def get_permissions(self):
        """Регистрация доступна всем, остальное только админам"""
        if self.action == "create":
            return [permissions.AllowAny()]
        return super().get_permissions()

    @action(detail=True, methods=["get"])
    def borrowed_books(self, request, pk=None):
        """Получить книги, которые взял читатель"""
        user = self.get_object()
        borrows = BookBorrow.objects.filter(user=user).order_by("-borrow_date")
        serializer = BookBorrowSerializer(borrows, many=True)
        return Response(serializer.data)


class AuthorViewSet(viewsets.ModelViewSet):
    """ViewSet для работы с авторами"""

    queryset = Author.objects.all().order_by("last_name", "first_name")
    serializer_class = AuthorSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [filters.SearchFilter]
    search_fields = ["last_name", "first_name"]


@method_decorator(never_cache, name="dispatch")
class BookViewSet(viewsets.ModelViewSet):
    """ViewSet для работы с книгами"""

    queryset = Book.objects.all().order_by("title")
    serializer_class = BookSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["status", "publication_year", "publisher"]
    search_fields = ["title", "isbn", "authors__last_name"]
    ordering_fields = ["title", "publication_year"]

    @action(detail=True, methods=["get"])
    def borrow_history(self, request, pk=None):
        """История выдач конкретной книги"""
        book = self.get_object()
        borrows = BookBorrow.objects.filter(book=book).order_by("-borrow_date")
        serializer = BookBorrowSerializer(borrows, many=True)
        return Response(serializer.data)


@method_decorator(never_cache, name="dispatch")
class BookBorrowViewSet(viewsets.ModelViewSet):
    """ViewSet для работы с выдачами книг"""

    queryset = BookBorrow.objects.all().order_by("-borrow_date")
    serializer_class = BookBorrowSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["is_returned", "user", "book"]
    search_fields = ["user__last_name", "user__library_card_number", "book__title"]

    def get_serializer_class(self):
        """Возвращаем разные сериализаторы для разных действий"""
        if self.action == "return_book":
            return BookReturnSerializer
        return BookBorrowSerializer

    def get_queryset(self):
        """Пользователи видят только свои выдачи, админы - все"""
        user = self.request.user
        if user.is_staff:
            return BookBorrow.objects.all()
        return BookBorrow.objects.filter(user=user)

    @action(detail=True, methods=["post"])
    def return_book(self, request, pk=None):
        """Эндпоинт для возврата книги"""
        borrow = self.get_object()

        if borrow.is_returned:
            return Response(
                {"error": "Книга уже возвращена"}, status=status.HTTP_400_BAD_REQUEST
            )

        if not request.user.is_staff and borrow.user != request.user:
            return Response(
                {"error": "Нет прав на возврат чужой книги"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = BookReturnSerializer(borrow, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["get"])
    def overdue(self, request):
        """Список просроченных книг"""
        today = date.today()
        overdue_books = self.get_queryset().filter(
            is_returned=False, due_date__lt=today
        )
        serializer = self.get_serializer(overdue_books, many=True)
        return Response(serializer.data)
