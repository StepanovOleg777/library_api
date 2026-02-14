# books/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import datetime, date


# Модель пользователя (читателя)
# Мы расширяем стандартную модель User, добавив номер читательского билета
class User(AbstractUser):
    """
    Модель пользователя (читателя).
    Наследуется от AbstractUser, чтобы добавить номер читательского билета.
    """

    library_card_number = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="Номер читательского билета",
        help_text="Уникальный номер читательского билета",
    )
    phone = models.CharField(max_length=15, blank=True, verbose_name="Телефон")
    address = models.TextField(blank=True, verbose_name="Адрес")

    class Meta:
        verbose_name = "Читатель"
        verbose_name_plural = "Читатели"

    def __str__(self):
        return f"{self.last_name} {self.first_name} ({self.library_card_number})"


class Author(models.Model):
    """
    Модель автора книги.
    """

    first_name = models.CharField(max_length=100, verbose_name="Имя")
    last_name = models.CharField(max_length=100, verbose_name="Фамилия")
    middle_name = models.CharField(max_length=100, blank=True, verbose_name="Отчество")
    birth_date = models.DateField(null=True, blank=True, verbose_name="Дата рождения")
    biography = models.TextField(blank=True, verbose_name="Биография")

    class Meta:
        verbose_name = "Автор"
        verbose_name_plural = "Авторы"
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.last_name} {self.first_name}"


class Book(models.Model):
    """
    Модель книги.
    """

    class StatusChoices(models.TextChoices):
        AVAILABLE = "available", "В наличии"
        BORROWED = "borrowed", "Выдана"
        UNDER_REPAIR = "under_repair", "На ремонте"

    title = models.CharField(max_length=200, verbose_name="Название")
    authors = models.ManyToManyField(
        Author, related_name="books", verbose_name="Авторы"
    )
    isbn = models.CharField(max_length=13, unique=True, verbose_name="ISBN")
    publication_year = models.IntegerField(
        validators=[MinValueValidator(1000), MaxValueValidator(datetime.now().year)],
        verbose_name="Год издания",
    )
    publisher = models.CharField(max_length=100, verbose_name="Издательство")
    pages = models.IntegerField(
        validators=[MinValueValidator(1)], verbose_name="Количество страниц"
    )
    description = models.TextField(blank=True, verbose_name="Описание")
    quantity = models.IntegerField(
        validators=[MinValueValidator(0)], verbose_name="Общее количество экземпляров"
    )
    available_quantity = models.IntegerField(
        validators=[MinValueValidator(0)], verbose_name="Доступно экземпляров"
    )
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.AVAILABLE,
        verbose_name="Статус",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата добавления")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        verbose_name = "Книга"
        verbose_name_plural = "Книги"
        ordering = ["title"]

    def __str__(self):
        return f"{self.title} (ISBN: {self.isbn})"

    def save(self, *args, **kwargs):
        """
        Переопределяем save, чтобы автоматически обновлять статус
        на основе доступного количества
        """
        # Если available_quantity не задано, устанавливаем равным quantity
        if self.available_quantity is None:
            self.available_quantity = self.quantity

        if self.available_quantity <= 0:
            self.status = self.StatusChoices.BORROWED
        elif (
            self.available_quantity > 0
            and self.status != self.StatusChoices.UNDER_REPAIR
        ):
            self.status = self.StatusChoices.AVAILABLE
        super().save(*args, **kwargs)


class BookBorrow(models.Model):
    """
    Модель выдачи книги.
    Фиксирует факт выдачи книги читателю.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="borrowed_books",
        verbose_name="Читатель",
    )
    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name="borrowed_records",
        verbose_name="Книга",
    )
    borrow_date = models.DateTimeField(auto_now_add=True, verbose_name="Дата выдачи")
    due_date = models.DateField(verbose_name="Дата возврата")
    return_date = models.DateField(
        null=True, blank=True, verbose_name="Фактическая дата возврата"
    )
    is_returned = models.BooleanField(default=False, verbose_name="Возвращена")

    class Meta:
        verbose_name = "Выдача книги"
        verbose_name_plural = "Выдачи книг"
        ordering = ["-borrow_date"]

    def __str__(self):
        return f"{self.user} взял '{self.book.title}' до {self.due_date}"

    def save(self, *args, **kwargs):
        """
        При создании записи о выдаче уменьшаем доступное количество книг
        """
        if not self.pk:  # Только при создании новой записи
            if self.book.available_quantity > 0:
                self.book.available_quantity -= 1
                self.book.save()
            else:
                raise ValueError("Нет доступных экземпляров книги")
        super().save(*args, **kwargs)
