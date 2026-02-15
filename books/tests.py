from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from datetime import date, timedelta
from .models import Author, Book, BookBorrow

User = get_user_model()


class AuthorModelTest(TestCase):
    """Тесты для модели Author"""

    def setUp(self):
        self.author = Author.objects.create(
            first_name="Лев",
            last_name="Толстой",
            middle_name="Николаевич",
            birth_date="1828-09-09",
            biography="Великий русский писатель",
        )

    def test_author_creation(self):
        """Тест создания автора"""
        self.assertEqual(self.author.first_name, "Лев")
        self.assertEqual(self.author.last_name, "Толстой")
        self.assertEqual(self.author.middle_name, "Николаевич")
        self.assertEqual(str(self.author), "Толстой Лев")

    def test_author_ordering(self):
        """Тест сортировки авторов"""
        Author.objects.create(first_name="Фёдор", last_name="Достоевский")
        authors = Author.objects.all()
        self.assertEqual(authors[0].last_name, "Достоевский")
        self.assertEqual(authors[1].last_name, "Толстой")

    def test_author_update(self):
        """Тест обновления автора"""
        self.author.biography = "Обновленная биография"
        self.author.save()
        self.assertEqual(self.author.biography, "Обновленная биография")

    def test_author_delete(self):
        """Тест удаления автора"""
        author_id = self.author.id
        self.author.delete()
        with self.assertRaises(Author.DoesNotExist):
            Author.objects.get(id=author_id)


class BookModelTest(TestCase):
    """Тесты для модели Book"""

    def setUp(self):
        self.author = Author.objects.create(first_name="Лев", last_name="Толстой")
        self.book = Book.objects.create(
            title="Война и мир",
            isbn="9783161484100",
            publication_year=1869,
            publisher="Русский вестник",
            pages=1300,
            description="Роман-эпопея",
            quantity=5,
            available_quantity=5,
        )
        self.book.authors.add(self.author)

    def test_book_creation(self):
        """Тест создания книги"""
        self.assertEqual(self.book.title, "Война и мир")
        self.assertEqual(self.book.quantity, 5)
        self.assertEqual(self.book.available_quantity, 5)
        self.assertEqual(self.book.status, Book.StatusChoices.AVAILABLE)

    def test_book_status_changes_when_unavailable(self):
        """Тест изменения статуса при недоступности"""
        self.book.available_quantity = 0
        self.book.save()
        self.assertEqual(self.book.status, Book.StatusChoices.BORROWED)

    def test_book_status_repair(self):
        """Тест статуса 'на ремонте'"""
        self.book.status = Book.StatusChoices.UNDER_REPAIR
        self.book.save()
        self.assertEqual(self.book.status, Book.StatusChoices.UNDER_REPAIR)

    def test_book_str_method(self):
        """Тест строкового представления"""
        self.assertEqual(str(self.book), "Война и мир (ISBN: 9783161484100)")

    def test_book_update(self):
        """Тест обновления книги"""
        self.book.pages = 1400
        self.book.save()
        self.assertEqual(self.book.pages, 1400)

    def test_book_delete(self):
        """Тест удаления книги"""
        book_id = self.book.id
        self.book.delete()
        with self.assertRaises(Book.DoesNotExist):
            Book.objects.get(id=book_id)

    def test_book_quantity_validation(self):
        """Тест валидации количества"""
        book = Book(
            title="Тест",
            isbn="1234567890123",
            publication_year=2024,
            publisher="Тест",
            pages=-5,
            quantity=5,
            available_quantity=5,
        )
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            book.full_clean()


class BookBorrowModelTest(TestCase):
    """Тесты для модели выдачи книг"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123",
            library_card_number="LIB0001",
            first_name="Иван",
            last_name="Иванов",
        )
        self.author = Author.objects.create(first_name="Лев", last_name="Толстой")
        self.book = Book.objects.create(
            title="Война и мир",
            isbn="9783161484100",
            publication_year=1869,
            publisher="Русский вестник",
            pages=1300,
            quantity=5,
            available_quantity=5,
        )
        self.book.authors.add(self.author)

    def test_borrow_creation(self):
        """Тест создания выдачи"""
        borrow = BookBorrow.objects.create(
            user=self.user, book=self.book, due_date=date.today() + timedelta(days=14)
        )
        self.assertEqual(borrow.user, self.user)
        self.assertEqual(borrow.book, self.book)
        self.assertFalse(borrow.is_returned)
        self.assertIsNotNone(borrow.borrow_date)

        self.book.refresh_from_db()
        self.assertEqual(self.book.available_quantity, 4)

    def test_borrow_with_no_available_books(self):
        """Тест выдачи при отсутствии доступных книг"""
        self.book.available_quantity = 0
        self.book.save()

        with self.assertRaises(ValueError):
            BookBorrow.objects.create(
                user=self.user,
                book=self.book,
                due_date=date.today() + timedelta(days=14),
            )

    def test_return_book(self):
        """Тест возврата книги"""
        borrow = BookBorrow.objects.create(
            user=self.user, book=self.book, due_date=date.today() + timedelta(days=14)
        )

        borrow.is_returned = True
        borrow.return_date = date.today()
        borrow.save()

        self.book.available_quantity += 1
        self.book.save()

        self.book.refresh_from_db()
        self.assertEqual(self.book.available_quantity, 5)
        self.assertTrue(borrow.is_returned)
        self.assertEqual(borrow.return_date, date.today())

    def test_overdue_books(self):
        """Тест просроченных книг"""
        borrow = BookBorrow.objects.create(
            user=self.user, book=self.book, due_date=date.today() - timedelta(days=5)
        )

        self.assertFalse(borrow.is_returned)
        self.assertTrue(borrow.due_date < date.today())

    def test_borrow_str_method(self):
        """Тест строкового представления выдачи"""
        borrow = BookBorrow.objects.create(
            user=self.user, book=self.book, due_date=date.today() + timedelta(days=14)
        )
        self.assertIn("Иванов", str(borrow))
        self.assertIn("Война и мир", str(borrow))

    def test_multiple_borrows(self):
        """Тест нескольких выдач одной книги"""
        user2 = User.objects.create_user(
            username="testuser2", password="testpass123", library_card_number="LIB0002"
        )

        BookBorrow.objects.create(
            user=self.user, book=self.book, due_date=date.today() + timedelta(days=14)
        )

        self.book.refresh_from_db()
        self.assertEqual(self.book.available_quantity, 4)

        BookBorrow.objects.create(
            user=user2, book=self.book, due_date=date.today() + timedelta(days=14)
        )

        self.book.refresh_from_db()
        self.assertEqual(self.book.available_quantity, 3)


class BookAPITest(APITestCase):
    """Тесты для API"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123",
            library_card_number="LIB0001",
            first_name="Иван",
            last_name="Иванов",
        )
        self.admin = User.objects.create_superuser(
            username="admin", password="admin123", library_card_number="LIB0000"
        )
        self.author = Author.objects.create(first_name="Лев", last_name="Толстой")
        self.book = Book.objects.create(
            title="Война и мир",
            isbn="9783161484100",
            publication_year=1869,
            publisher="Русский вестник",
            pages=1300,
            quantity=5,
            available_quantity=5,
        )
        self.book.authors.add(self.author)

        response = self.client.post(
            "/api/token/", {"username": "testuser", "password": "testpass123"}
        )
        self.token = response.data.get("access")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")

    def test_get_books_list(self):
        """Тест получения списка книг"""
        response = self.client.get("/api/books/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_get_book_detail(self):
        """Тест получения деталей книги"""
        response = self.client.get(f"/api/books/{self.book.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Война и мир")

    def test_get_author_detail(self):
        """Тест получения деталей автора"""
        response = self.client.get(f"/api/authors/{self.author.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["last_name"], "Толстой")

    def test_create_book_unauthorized(self):
        """Тест создания книги без прав админа"""
        response = self.client.post(
            "/api/books/",
            {
                "title": "Новая книга",
                "isbn": "1234567890123",
                "publication_year": 2024,
                "publisher": "Тест",
                "pages": 100,
                "quantity": 3,
                "authors": [self.author.id],
            },
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_book_as_admin(self):
        """Тест создания книги админом"""
        response = self.client.post(
            "/api/token/", {"username": "admin", "password": "admin123"}
        )
        admin_token = response.data.get("access")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {admin_token}")

        response = self.client.post(
            "/api/books/",
            {
                "title": "Новая книга",
                "isbn": "1234567890123",
                "publication_year": 2024,
                "publisher": "Тест",
                "pages": 100,
                "quantity": 3,
                "authors": [self.author.id],
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Book.objects.count(), 2)

    def test_create_author_as_admin(self):
        """Тест создания автора админом"""
        response = self.client.post(
            "/api/token/", {"username": "admin", "password": "admin123"}
        )
        admin_token = response.data.get("access")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {admin_token}")

        response = self.client.post(
            "/api/authors/",
            {"first_name": "Антон", "last_name": "Чехов", "birth_date": "1860-01-29"},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Author.objects.count(), 2)

    def test_borrow_unavailable_book(self):
        """Тест выдачи недоступной книги"""
        self.book.available_quantity = 0
        self.book.save()

        response = self.client.post(
            "/api/borrows/", {"user": self.user.id, "book": self.book.id}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_users_list(self):
        """Тест получения списка пользователей"""
        response = self.client.get("/api/users/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)  # user + admin

    def test_get_user_detail(self):
        """Тест получения деталей пользователя"""
        response = self.client.get(f"/api/users/{self.user.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "testuser")


class ViewCoverageTests(TestCase):
    """Тесты для views.py"""

    def setUp(self):
        from rest_framework.test import APIRequestFactory
        from .views import AuthorViewSet, BookViewSet, UserViewSet, BookBorrowViewSet

        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(
            username="viewuser", password="test123", library_card_number="LIB8888"
        )

        request = self.factory.get("/")
        request.user = self.user

        self.author_view = AuthorViewSet()
        self.author_view.request = request

        self.book_view = BookViewSet()
        self.book_view.request = request

        self.user_view = UserViewSet()
        self.user_view.request = request

        self.borrow_view = BookBorrowViewSet()
        self.borrow_view.request = request

    def test_author_viewset_queryset(self):
        """Тест queryset у AuthorViewSet"""
        queryset = self.author_view.get_queryset()
        self.assertIsNotNone(queryset)

    def test_book_viewset_queryset(self):
        """Тест queryset у BookViewSet"""
        queryset = self.book_view.get_queryset()
        self.assertIsNotNone(queryset)

    def test_user_viewset_queryset(self):
        """Тест queryset у UserViewSet"""
        queryset = self.user_view.get_queryset()
        self.assertIsNotNone(queryset)

    def test_borrow_viewset_queryset(self):
        """Тест queryset у BookBorrowViewSet"""
        queryset = self.borrow_view.get_queryset()
        self.assertIsNotNone(queryset)


class SerializerDetailedTests(TestCase):
    """Детальные тесты сериализаторов"""

    def setUp(self):
        self.author = Author.objects.create(first_name="Сергей", last_name="Есенин")
        self.book = Book.objects.create(
            title="Стихи",
            isbn="5555555555555",
            publication_year=1920,
            publisher="Поэзия",
            pages=200,
            quantity=2,
            available_quantity=2,
        )
        self.book.authors.add(self.author)
        self.user = User.objects.create_user(
            username="serializeruser", password="test123", library_card_number="LIB7777"
        )

    def test_book_serializer_fields(self):
        """Тест всех полей BookSerializer"""
        from .serializers import BookSerializer

        serializer = BookSerializer(self.book)
        data = serializer.data
        self.assertIn("id", data)
        self.assertIn("title", data)
        self.assertIn("authors", data)
        self.assertIn("authors_display", data)
        self.assertIn("isbn", data)
        self.assertIn("publication_year", data)
        self.assertIn("publisher", data)
        self.assertIn("pages", data)
        self.assertIn("quantity", data)
        self.assertIn("available_quantity", data)
        self.assertIn("status", data)

    def test_author_serializer_fields(self):
        """Тест всех полей AuthorSerializer"""
        from .serializers import AuthorSerializer

        serializer = AuthorSerializer(self.author)
        data = serializer.data
        self.assertIn("id", data)
        self.assertIn("first_name", data)
        self.assertIn("last_name", data)
        self.assertIn("middle_name", data)
        self.assertIn("birth_date", data)
        self.assertIn("biography", data)

    def test_user_serializer_create(self):
        """Тест создания пользователя через сериализатор"""
        from .serializers import UserSerializer

        data = {
            "username": "testcreate",
            "password": "complexpass123",
            "email": "test@create.com",
            "first_name": "Тест",
            "last_name": "Создатель",
            "phone": "+71234567890",
        }
        serializer = UserSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        user = serializer.save()
        self.assertIsNotNone(user.library_card_number)
        self.assertTrue(user.library_card_number.startswith("LIB"))

    def test_user_serializer_validation(self):
        """Тест валидации UserSerializer"""
        from .serializers import UserSerializer

        # Неполные данные
        data = {"username": "test", "password": "123"}
        serializer = UserSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_book_borrow_serializer_validation(self):
        """Тест валидации BookBorrowSerializer"""
        from .serializers import BookBorrowSerializer
        from datetime import date, timedelta

        self.book.available_quantity = 2
        self.book.save()

        data = {
            "user": self.user.id,
            "book": self.book.id,
            "due_date": date.today() + timedelta(days=14),
        }
        serializer = BookBorrowSerializer(data=data)
        is_valid = serializer.is_valid()
        if not is_valid:
            print("Ошибки валидации:", serializer.errors)
        self.assertTrue(is_valid)

    def test_book_borrow_serializer_invalid(self):
        """Тест невалидных данных BookBorrowSerializer"""
        from .serializers import BookBorrowSerializer

        data = {"user": 99999, "book": 99999}
        serializer = BookBorrowSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_book_return_serializer(self):
        """Тест сериализатора возврата"""
        from .serializers import BookReturnSerializer

        borrow = BookBorrow.objects.create(
            user=self.user, book=self.book, due_date=date.today() + timedelta(days=14)
        )
        serializer = BookReturnSerializer(borrow, data={}, partial=True)
        self.assertTrue(serializer.is_valid())


class PermissionTests(TestCase):
    """Тесты для permissions"""

    def test_is_admin_or_readonly_permission(self):
        """Тест пермишена IsAdminOrReadOnly"""
        from .views import IsAdminOrReadOnly
        from rest_framework.test import APIRequestFactory
        from rest_framework.request import Request

        factory = APIRequestFactory()

        request = Request(factory.get("/"))
        permission = IsAdminOrReadOnly()
        self.assertTrue(permission.has_permission(request, None))

        request = Request(factory.post("/"))
        self.assertFalse(permission.has_permission(request, None))


class FilterTests(TestCase):
    """Тесты фильтрации"""

    def setUp(self):
        self.author1 = Author.objects.create(first_name="Лев", last_name="Толстой")
        self.author2 = Author.objects.create(
            first_name="Фёдор", last_name="Достоевский"
        )

        self.book1 = Book.objects.create(
            title="Война и мир",
            isbn="1111111111111",
            publication_year=1869,
            publisher="А",
            pages=1300,
            quantity=5,
            available_quantity=5,
        )
        self.book1.authors.add(self.author1)

        self.book2 = Book.objects.create(
            title="Преступление и наказание",
            isbn="2222222222222",
            publication_year=1866,
            publisher="Б",
            pages=500,
            quantity=3,
            available_quantity=3,
        )
        self.book2.authors.add(self.author2)

    def test_book_filter_by_year(self):
        """Тест фильтрации книг по году"""
        books = Book.objects.filter(publication_year=1869)
        self.assertEqual(books.count(), 1)
        self.assertEqual(books.first().title, "Война и мир")

    def test_book_filter_by_publisher(self):
        """Тест фильтрации книг по издательству"""
        books = Book.objects.filter(publisher="Б")
        self.assertEqual(books.count(), 1)
        self.assertEqual(books.first().title, "Преступление и наказание")

    def test_author_search_by_lastname(self):
        """Тест поиска авторов по фамилии"""
        authors = Author.objects.filter(last_name__icontains="той")
        self.assertEqual(authors.count(), 1)
        self.assertEqual(authors.first().last_name, "Толстой")
