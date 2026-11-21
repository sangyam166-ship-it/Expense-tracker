import datetime
from decimal import Decimal
from django import forms
from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordChangeForm
from django.utils import timezone
from .models import UserProfile, Transaction, Category, Budget, SavingsGoal, RecurringTransaction

class FinoraUserRegistrationForm(UserCreationForm):
    first_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={
        'class': 'form-control-finora',
        'placeholder': 'e.g. Alex'
    }))
    last_name = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={
        'class': 'form-control-finora',
        'placeholder': 'e.g. Morgan'
    }))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={
        'class': 'form-control-finora',
        'placeholder': 'alex.morgan@finora.io'
    }))
    currency = forms.ChoiceField(choices=UserProfile.CURRENCY_CHOICES, initial='USD', widget=forms.Select(attrs={
        'class': 'form-control-finora form-select-finora'
    }))

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control-finora', 'placeholder': 'Choose unique username'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({'class': 'form-control-finora', 'placeholder': '••••••••'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control-finora', 'placeholder': '••••••••'})


class FinoraLoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'form-control-finora',
        'placeholder': 'Username or Email',
        'autofocus': True
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control-finora',
        'placeholder': '••••••••'
    }))


class UserProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'class': 'form-control-finora'}))
    last_name = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'class': 'form-control-finora'}))
    email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={'class': 'form-control-finora'}))

    class Meta:
        model = UserProfile
        fields = ['currency', 'theme', 'phone', 'avatar', 'monthly_income_target', 'monthly_savings_target', 'bio']
        widgets = {
            'currency': forms.Select(attrs={'class': 'form-control-finora form-select-finora'}),
            'theme': forms.Select(attrs={'class': 'form-control-finora form-select-finora'}),
            'phone': forms.TextInput(attrs={'class': 'form-control-finora', 'placeholder': '+1 (555) 000-0000'}),
            'monthly_income_target': forms.NumberInput(attrs={'class': 'form-control-finora', 'step': '0.01'}),
            'monthly_savings_target': forms.NumberInput(attrs={'class': 'form-control-finora', 'step': '0.01'}),
            'bio': forms.Textarea(attrs={'class': 'form-control-finora', 'rows': 3, 'placeholder': 'Tell us about your financial journey'}),
            'avatar': forms.FileInput(attrs={'class': 'form-control-finora file-input-finora'}),
        }


class FinoraPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control-finora', 'placeholder': '••••••••'})


class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['type', 'title', 'amount', 'date', 'time', 'category', 'payment_method', 'notes', 'receipt']
        widgets = {
            'type': forms.Select(attrs={'class': 'form-control-finora form-select-finora', 'id': 'id_transaction_type'}),
            'title': forms.TextInput(attrs={'class': 'form-control-finora', 'placeholder': 'e.g. Grocery Store, Monthly Salary'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control-finora', 'step': '0.01', 'placeholder': '0.00'}),
            'date': forms.DateInput(attrs={'class': 'form-control-finora', 'type': 'date'}),
            'time': forms.TimeInput(attrs={'class': 'form-control-finora', 'type': 'time'}),
            'category': forms.Select(attrs={'class': 'form-control-finora form-select-finora'}),
            'payment_method': forms.Select(attrs={'class': 'form-control-finora form-select-finora'}),
            'notes': forms.Textarea(attrs={'class': 'form-control-finora', 'rows': 2, 'placeholder': 'Optional notes or tags'}),
            'receipt': forms.FileInput(attrs={'class': 'form-control-finora file-input-finora'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        if not self.initial.get('date'):
            self.initial['date'] = timezone.now().date()
        if not self.initial.get('time'):
            self.initial['time'] = timezone.now().strftime('%H:%M')
        if user:
            self.fields['category'].queryset = Category.objects.filter(
                models.Q(user=user) | models.Q(user__isnull=True)
            ).order_by('type', 'name')

    def clean_title(self):
        title = self.cleaned_data.get('title', '').strip()
        if not title:
            raise forms.ValidationError("Transaction title cannot be empty.")
        return title

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is None or amount <= Decimal('0.00'):
            raise forms.ValidationError("Transaction amount must be strictly greater than 0.00.")
        return amount

    def clean(self):
        cleaned_data = super().clean()
        title = cleaned_data.get('title')
        amount = cleaned_data.get('amount')
        date = cleaned_data.get('date')
        tx_type = cleaned_data.get('type')
        category = cleaned_data.get('category')

        # Prevent duplicate submissions created within the last 2 minutes
        if self.user and title and amount and date and not self.instance.pk:
            two_mins_ago = timezone.now() - datetime.timedelta(minutes=2)
            duplicate = Transaction.objects.filter(
                user=self.user,
                title__iexact=title,
                amount=amount,
                date=date,
                type=tx_type,
                category=category,
                created_at__gte=two_mins_ago
            ).exists()
            if duplicate:
                raise forms.ValidationError(
                    "Duplicate transaction detected: an identical record was created within the last 2 minutes."
                )

        return cleaned_data


class BudgetForm(forms.ModelForm):
    class Meta:
        model = Budget
        fields = ['category', 'month', 'year', 'amount']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-control-finora form-select-finora'}),
            'month': forms.Select(choices=[(i, datetime.date(2000, i, 1).strftime('%B')) for i in range(1, 13)], attrs={'class': 'form-control-finora form-select-finora'}),
            'year': forms.NumberInput(attrs={'class': 'form-control-finora'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control-finora', 'step': '0.01', 'placeholder': 'Budget Amount'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        now = timezone.now()
        if not self.initial.get('month'):
            self.initial['month'] = now.month
        if not self.initial.get('year'):
            self.initial['year'] = now.year
        if user:
            self.fields['category'].queryset = Category.objects.filter(
                (models.Q(user=user) | models.Q(user__isnull=True)) & models.Q(type='EXPENSE')
            ).order_by('name')
            self.fields['category'].empty_label = "🌟 Overall Monthly Budget"

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is None or amount <= Decimal('0.00'):
            raise forms.ValidationError("Budget amount must be strictly greater than 0.00.")
        return amount


class SavingsGoalForm(forms.ModelForm):
    class Meta:
        model = SavingsGoal
        fields = ['title', 'target_amount', 'current_amount', 'target_date', 'status', 'color', 'notes']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control-finora', 'placeholder': 'e.g. Emergency Fund, New Laptop'}),
            'target_amount': forms.NumberInput(attrs={'class': 'form-control-finora', 'step': '0.01', 'placeholder': '5000.00'}),
            'current_amount': forms.NumberInput(attrs={'class': 'form-control-finora', 'step': '0.01', 'placeholder': '0.00'}),
            'target_date': forms.DateInput(attrs={'class': 'form-control-finora', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-control-finora form-select-finora'}),
            'color': forms.TextInput(attrs={'class': 'form-control-finora', 'type': 'color', 'value': '#3B82F6'}),
            'notes': forms.Textarea(attrs={'class': 'form-control-finora', 'rows': 2, 'placeholder': 'Goal details and motivation'}),
        }

    def clean_title(self):
        title = self.cleaned_data.get('title', '').strip()
        if not title:
            raise forms.ValidationError("Goal title cannot be empty.")
        return title

    def clean_target_amount(self):
        amount = self.cleaned_data.get('target_amount')
        if amount is None or amount <= Decimal('0.00'):
            raise forms.ValidationError("Target amount must be strictly greater than 0.00.")
        return amount

    def clean_current_amount(self):
        amount = self.cleaned_data.get('current_amount')
        if amount is None or amount < Decimal('0.00'):
            raise forms.ValidationError("Current amount cannot be negative.")
        return amount


class SavingsContributionForm(forms.Form):
    amount = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control-finora',
            'step': '0.01',
            'placeholder': 'Amount to add'
        })
    )

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is None or amount <= Decimal('0.00'):
            raise forms.ValidationError("Contribution amount must be strictly greater than 0.00.")
        return amount


class RecurringTransactionForm(forms.ModelForm):
    class Meta:
        model = RecurringTransaction
        fields = ['title', 'category', 'type', 'amount', 'frequency', 'payment_method', 'start_date', 'next_due_date', 'is_active', 'notes']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control-finora', 'placeholder': 'e.g. Netflix Subscription, House Rent'}),
            'category': forms.Select(attrs={'class': 'form-control-finora form-select-finora'}),
            'type': forms.Select(attrs={'class': 'form-control-finora form-select-finora'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control-finora', 'step': '0.01'}),
            'frequency': forms.Select(attrs={'class': 'form-control-finora form-select-finora'}),
            'payment_method': forms.Select(attrs={'class': 'form-control-finora form-select-finora'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control-finora', 'type': 'date'}),
            'next_due_date': forms.DateInput(attrs={'class': 'form-control-finora', 'type': 'date'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input-finora'}),
            'notes': forms.Textarea(attrs={'class': 'form-control-finora', 'rows': 2}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.initial.get('start_date'):
            self.initial['start_date'] = timezone.now().date()
        if not self.initial.get('next_due_date'):
            self.initial['next_due_date'] = timezone.now().date() + datetime.timedelta(days=30)
        if user:
            self.fields['category'].queryset = Category.objects.filter(
                models.Q(user=user) | models.Q(user__isnull=True)
            ).order_by('type', 'name')

    def clean_title(self):
        title = self.cleaned_data.get('title', '').strip()
        if not title:
            raise forms.ValidationError("Subscription / recurring title cannot be empty.")
        return title

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is None or amount <= Decimal('0.00'):
            raise forms.ValidationError("Recurring amount must be strictly greater than 0.00.")
        return amount


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'type', 'icon', 'color']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control-finora', 'placeholder': 'e.g. Gym & Fitness, Tech Gear'}),
            'type': forms.Select(attrs={'class': 'form-control-finora form-select-finora'}),
            'icon': forms.Select(choices=[
                ('tag', 'Tag (Default)'),
                ('utensils', 'Dining / Food'),
                ('shopping-bag', 'Shopping'),
                ('book-open', 'Education'),
                ('car', 'Transport / Fuel'),
                ('tv', 'Entertainment'),
                ('heart-pulse', 'Healthcare'),
                ('receipt', 'Bills & Utilities'),
                ('plane', 'Travel'),
                ('briefcase', 'Salary / Employment'),
                ('laptop', 'Tech / Freelance'),
                ('trending-up', 'Investments / Returns'),
                ('gift', 'Gift / Bonus'),
                ('dumbbell', 'Fitness & Wellness'),
                ('coffee', 'Cafe & Social'),
                ('home', 'Housing & Rent'),
            ], attrs={'class': 'form-control-finora form-select-finora'}),
            'color': forms.TextInput(attrs={'class': 'form-control-finora', 'type': 'color', 'value': '#3B82F6'}),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise forms.ValidationError("Category name cannot be empty.")
        return name


class CSVImportForm(forms.Form):
    csv_file = forms.FileField(
        label='Select CSV File',
        widget=forms.FileInput(attrs={'class': 'form-control-finora file-input-finora', 'accept': '.csv'})
    )


class DataRestoreForm(forms.Form):
    backup_file = forms.FileField(
        label='Select JSON Backup File',
        widget=forms.FileInput(attrs={'class': 'form-control-finora file-input-finora', 'accept': '.json'})
    )
