from rest_framework import serializers
from .models import Transaction, Category, Budget, SavingsGoal, Notification

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'type', 'icon', 'color', 'is_default']


class TransactionSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_color = serializers.CharField(source='category.color', read_only=True)
    category_icon = serializers.CharField(source='category.icon', read_only=True)

    class Meta:
        model = Transaction
        fields = [
            'id', 'type', 'title', 'amount', 'date', 'category',
            'category_name', 'category_color', 'category_icon',
            'payment_method', 'notes', 'created_at'
        ]


class BudgetSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    spent = serializers.DecimalField(source='get_spent_amount', max_digits=12, decimal_places=2, read_only=True)
    percentage = serializers.FloatField(source='get_percentage', read_only=True)

    class Meta:
        model = Budget
        fields = ['id', 'category', 'category_name', 'month', 'year', 'amount', 'spent', 'percentage']


class SavingsGoalSerializer(serializers.ModelSerializer):
    percentage = serializers.FloatField(source='get_percentage', read_only=True)
    remaining = serializers.DecimalField(source='get_remaining', max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = SavingsGoal
        fields = [
            'id', 'title', 'target_amount', 'current_amount',
            'target_date', 'status', 'color', 'notes',
            'percentage', 'remaining', 'created_at'
        ]


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'title', 'message', 'type', 'is_read', 'link', 'created_at']
