from django.contrib import admin
from .models import UserProfile, Category, Transaction, Budget, SavingsGoal, RecurringTransaction, Notification

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'currency', 'theme', 'monthly_income_target', 'monthly_savings_target', 'created_at')
    search_fields = ('user__username', 'user__email')
    list_filter = ('currency', 'theme')

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'user', 'icon', 'color', 'is_default')
    list_filter = ('type', 'is_default')
    search_fields = ('name', 'user__username')

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'type', 'amount', 'category', 'payment_method', 'date')
    list_filter = ('type', 'payment_method', 'date', 'category')
    search_fields = ('title', 'notes', 'user__username')
    date_hierarchy = 'date'

@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ('user', 'category', 'month', 'year', 'amount')
    list_filter = ('year', 'month')
    search_fields = ('user__username', 'category__name')

@admin.register(SavingsGoal)
class SavingsGoalAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'current_amount', 'target_amount', 'target_date', 'status')
    list_filter = ('status', 'target_date')
    search_fields = ('title', 'user__username')

@admin.register(RecurringTransaction)
class RecurringTransactionAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'type', 'amount', 'frequency', 'next_due_date', 'is_active')
    list_filter = ('frequency', 'type', 'is_active')
    search_fields = ('title', 'user__username')

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'type', 'is_read', 'created_at')
    list_filter = ('type', 'is_read', 'created_at')
    search_fields = ('title', 'message', 'user__username')
