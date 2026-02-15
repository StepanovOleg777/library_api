from django.contrib import admin
from .models import User, Author, Book, BookBorrow


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        "username",
        "last_name",
        "first_name",
        "library_card_number",
        "email",
    )
    search_fields = ("username", "last_name", "first_name", "library_card_number")
    list_filter = ("is_active",)


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ("last_name", "first_name", "middle_name", "birth_date")
    search_fields = ("last_name", "first_name")


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "get_authors",
        "isbn",
        "publication_year",
        "quantity",
        "available_quantity",
        "status",
    )
    search_fields = ("title", "isbn")
    list_filter = ("status", "publication_year", "publisher")
    filter_horizontal = ("authors",)

    def get_authors(self, obj):
        return ", ".join([str(author) for author in obj.authors.all()])

    get_authors.short_description = "Авторы"


@admin.register(BookBorrow)
class BookBorrowAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "book",
        "borrow_date",
        "due_date",
        "return_date",
        "is_returned",
    )
    list_filter = ("is_returned", "borrow_date", "due_date")
    search_fields = ("user__username", "user__last_name", "book__title")
    readonly_fields = ("borrow_date",)
