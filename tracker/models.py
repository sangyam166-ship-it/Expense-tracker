from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
import datetime

class UserProfile(models.Model):
    CURRENCY_CHOICES = [
        ('USD', 'US Dollar ($)'),
        ('INR', 'Indian Rupee (₹)'),
        ('EUR', 'Euro (€)'),
        ('GBP', 'British Pound (£)'),
        ('CAD', 'Canadian Dollar (CA$)'),
        ('AUD', 'Australian Dollar (A$)'),
        ('JPY', 'Japanese Yen (¥)'),
        ('SGD', 'Singapore Dollar (S$)'),
        ('AED', 'UAE Dirham (AED)'),
    ]

    CURRENCY_SYMBOLS = {
        'USD': '$',
        'INR': '₹',
        'EUR': '€',
        'GBP': '£',
        'CAD': 'CA$',
        'AUD': 'A$',
        'JPY': '¥',
        'SGD': 'S$',
        'AED': 'AED ',
    }

    THEME_CHOICES = [
        ('dark', 'Deep Navy (Dark)'),
        ('light', 'Clean Light'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    currency = models.CharField(max_length=5, choices=CURRENCY_CHOICES, default='INR')
    theme = models.CharField(max_length=10, choices=THEME_CHOICES, default='dark')
    phone = models.CharField(max_length=20, blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    monthly_income_target = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    monthly_savings_target = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    bio = models.TextField(blank=True, max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"

    def get_currency_symbol(self):
        return self.CURRENCY_SYMBOLS.get(self.currency, '$')


class Category(models.Model):
    TYPE_CHOICES = [
        ('EXPENSE', 'Expense'),
        ('INCOME', 'Income'),
    ]

    DEFAULT_EXPENSE_CATEGORIES = [
        ('Food & Dining', 'utensils', '#F59E0B'),
        ('Shopping', 'shopping-bag', '#EC4899'),
        ('Education', 'book-open', '#8B5CF6'),
        ('Transport', 'car', '#3B82F6'),
        ('Entertainment', 'tv', '#06B6D4'),
        ('Healthcare', 'heart-pulse', '#EF4444'),
        ('Bills & Utilities', 'receipt', '#6366F1'),
        ('Travel', 'plane', '#10B981'),
        ('Other Expense', 'tag', '#64748B'),
    ]

    DEFAULT_INCOME_CATEGORIES = [
        ('Salary', 'briefcase', '#10B981'),
        ('Freelance', 'laptop', '#06B6D4'),
        ('Investments', 'trending-up', '#8B5CF6'),
        ('Business', 'building', '#3B82F6'),
        ('Gift & Bonus', 'gift', '#F59E0B'),
        ('Other Income', 'dollar-sign', '#14B8A6'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='categories')
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='EXPENSE')
    icon = models.CharField(max_length=50, default='tag', help_text='Lucide icon name')
    color = models.CharField(max_length=20, default='#3B82F6', help_text='Hex color code')
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['type', 'name']
        constraints = [
            models.UniqueConstraint(fields=['user', 'name', 'type'], name='unique_user_category_name_type')
        ]

    def __str__(self):
        return f"{self.name} ({self.get_type_display()})"


class Transaction(models.Model):
    TYPE_CHOICES = [
        ('EXPENSE', 'Expense'),
        ('INCOME', 'Income'),
    ]

    PAYMENT_METHOD_CHOICES = [
        ('CASH', 'Cash'),
        ('CREDIT_CARD', 'Credit Card'),
        ('DEBIT_CARD', 'Debit Card'),
        ('BANK_TRANSFER', 'Bank Transfer'),
        ('UPI', 'UPI / Instant Pay'),
        ('NET_BANKING', 'Net Banking'),
        ('OTHER', 'Other'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    title = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField(default=timezone.now)
    time = models.TimeField(null=True, blank=True, help_text="Time of transaction")
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='OTHER')
    notes = models.TextField(blank=True)
    receipt = models.FileField(upload_to='receipts/', blank=True, null=True)
    is_recurring_instance = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.get_type_display()} - {self.title}: {self.amount}"


class Budget(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='budgets')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, null=True, blank=True, related_name='budgets')
    month = models.PositiveSmallIntegerField(default=timezone.now().month)
    year = models.PositiveSmallIntegerField(default=timezone.now().year)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-year', '-month']
        constraints = [
            models.UniqueConstraint(fields=['user', 'category', 'month', 'year'], name='unique_user_budget_month_year')
        ]

    def __str__(self):
        cat_name = self.category.name if self.category else "Overall Monthly Budget"
        return f"{cat_name} ({self.month}/{self.year}): {self.amount}"

    def get_spent_amount(self):
        tx_qs = Transaction.objects.filter(
            user=self.user,
            type='EXPENSE',
            date__year=self.year,
            date__month=self.month
        )
        if self.category:
            tx_qs = tx_qs.filter(category=self.category)
        aggregate = tx_qs.aggregate(total=models.Sum('amount'))['total']
        return aggregate or Decimal('0.00')

    def get_percentage(self):
        if not self.amount or self.amount <= Decimal('0.00'):
            return 0.0
        spent = self.get_spent_amount()
        pct = (spent / self.amount) * Decimal('100.0')
        return round(float(pct), 1)

    def get_remaining(self):
        spent = self.get_spent_amount()
        return self.amount - spent

    def is_warning(self):
        return self.get_percentage() >= 80.0 and not self.is_exceeded()

    def is_exceeded(self):
        return self.get_percentage() >= 100.0


class SavingsGoal(models.Model):
    STATUS_CHOICES = [
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('ON_HOLD', 'On Hold'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='savings_goals')
    title = models.CharField(max_length=150)
    target_amount = models.DecimalField(max_digits=12, decimal_places=2)
    current_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    target_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='IN_PROGRESS')
    color = models.CharField(max_length=20, default='#3B82F6')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['target_date', '-created_at']

    def __str__(self):
        return f"{self.title}: {self.current_amount} / {self.target_amount}"

    def get_percentage(self):
        if not self.target_amount or self.target_amount <= Decimal('0.00'):
            return 0.0
        pct = (self.current_amount / self.target_amount) * Decimal('100.0')
        return min(round(float(pct), 1), 100.0)

    def get_remaining(self):
        rem = self.target_amount - self.current_amount
        return max(rem, Decimal('0.00'))

    def days_remaining(self):
        if not self.target_date:
            return None
        today = timezone.now().date()
        delta = (self.target_date - today).days
        return delta


class RecurringTransaction(models.Model):
    FREQUENCY_CHOICES = [
        ('DAILY', 'Daily'),
        ('WEEKLY', 'Weekly'),
        ('MONTHLY', 'Monthly'),
        ('YEARLY', 'Yearly'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recurring_transactions')
    title = models.CharField(max_length=200)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    type = models.CharField(max_length=10, choices=Transaction.TYPE_CHOICES, default='EXPENSE')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES, default='MONTHLY')
    payment_method = models.CharField(max_length=20, choices=Transaction.PAYMENT_METHOD_CHOICES, default='OTHER')
    start_date = models.DateField(default=timezone.now)
    next_due_date = models.DateField()
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['next_due_date']

    def __str__(self):
        return f"{self.title} ({self.frequency}): {self.amount}"


class Notification(models.Model):
    TYPE_CHOICES = [
        ('INFO', 'Information'),
        ('WARNING', 'Warning'),
        ('SUCCESS', 'Success'),
        ('DANGER', 'Danger / Alert'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='INFO')
    is_read = models.BooleanField(default=False)
    link = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.type}] {self.title} - {self.user.username}"
