# books/serializers.py
from rest_framework import serializers
from .models import User, Author, Book, BookBorrow
from django.contrib.auth.hashers import make_password
from datetime import date, timedelta


class UserSerializer(serializers.ModelSerializer):
    """Сериализатор для читателей"""

    class Meta:
        model = User
        fields = ['id', 'username', 'password', 'email', 'first_name', 'last_name',
                  'library_card_number', 'phone', 'address']
        extra_kwargs = {
            'password': {'write_only': True},
            'library_card_number': {'read_only': True}  # Будем генерировать автоматически
        }

    def create(self, validated_data):
        """Хешируем пароль при создании"""
        validated_data['password'] = make_password(validated_data['password'])
        # Простая генерация номера (в реальности сложнее)
        if not validated_data.get('library_card_number'):
            last_user = User.objects.order_by('id').last()
            if last_user and last_user.library_card_number:
                # Извлекаем число из номера вида "LIB0001"
                try:
                    last_num = int(last_user.library_card_number.replace('LIB', '')) + 1
                    validated_data['library_card_number'] = f'LIB{last_num:04d}'
                except ValueError:
                    validated_data['library_card_number'] = 'LIB0001'
            else:
                validated_data['library_card_number'] = 'LIB0001'
        return super().create(validated_data)


class AuthorSerializer(serializers.ModelSerializer):
    """Сериализатор для авторов"""

    class Meta:
        model = Author
        fields = '__all__'


class BookSerializer(serializers.ModelSerializer):
    """Сериализатор для книг"""
    authors_display = serializers.StringRelatedField(source='authors', many=True, read_only=True)

    class Meta:
        model = Book
        fields = ['id', 'title', 'authors', 'authors_display', 'isbn', 'publication_year',
                  'publisher', 'pages', 'description', 'quantity', 'available_quantity', 'status']
        read_only_fields = ['available_quantity', 'status']


class BookBorrowSerializer(serializers.ModelSerializer):
    """Сериализатор для выдачи книг"""
    user_details = UserSerializer(source='user', read_only=True)
    book_details = BookSerializer(source='book', read_only=True)
    days_overdue = serializers.SerializerMethodField()

    class Meta:
        model = BookBorrow
        fields = ['id', 'user', 'user_details', 'book', 'book_details', 'borrow_date',
                  'due_date', 'return_date', 'is_returned', 'days_overdue']
        read_only_fields = ['borrow_date', 'is_returned', 'return_date']

    def get_days_overdue(self, obj):
        """Считаем дни просрочки"""
        if not obj.is_returned and obj.due_date < date.today():
            return (date.today() - obj.due_date).days
        return 0

    def validate(self, data):
        """Проверяем, что книга доступна"""
        if not self.instance:  # Только при создании
            book = data.get('book')
            if book and book.available_quantity <= 0:
                raise serializers.ValidationError("Эта книга недоступна для выдачи")

            # Устанавливаем дату возврата через 14 дней по умолчанию
            if not data.get('due_date'):
                data['due_date'] = date.today() + timedelta(days=14)
        return data


class BookReturnSerializer(serializers.ModelSerializer):
    """Сериализатор для возврата книг"""

    class Meta:
        model = BookBorrow
        fields = ['id', 'return_date', 'is_returned']
        read_only_fields = ['id']

    def validate(self, data):
        """Проверяем, что книга еще не возвращена"""
        if self.instance and self.instance.is_returned:
            raise serializers.ValidationError("Эта книга уже возвращена")
        return data

    def save(self, **kwargs):
        """При возврате обновляем количество книг"""
        self.instance.is_returned = True
        self.instance.return_date = date.today()
        self.instance.save()

        # Увеличиваем доступное количество
        book = self.instance.book
        book.available_quantity += 1
        book.save()

        return self.instance