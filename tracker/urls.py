from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('', views.dashboard_view, name='dashboard'),
    path('dashboard/', views.dashboard_view, name='dashboard_alt'),

    # Auth & Profile
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/toggle-theme/', views.toggle_theme_view, name='toggle_theme'),
    path('profile/update-currency/', views.update_currency_view, name='update_currency'),

    # Transactions & Management
    path('transactions/', views.transactions_list_view, name='transactions'),
    path('expenses/', views.expenses_list_view, name='expenses'),
    path('income/', views.income_list_view, name='income'),
    path('transactions/create/', views.transaction_create_view, name='transaction_create'),
    path('transactions/<int:pk>/edit/', views.transaction_update_view, name='transaction_update'),
    path('transactions/<int:pk>/delete/', views.transaction_delete_view, name='transaction_delete'),
    path('transactions/import-csv/', views.import_csv_view, name='import_csv'),

    # Custom Category Management
    path('categories/', views.categories_view, name='categories'),
    path('categories/create/', views.category_create_view, name='category_create'),
    path('categories/<int:pk>/delete/', views.category_delete_view, name='category_delete'),

    # Budget Management
    path('budgets/', views.budgets_view, name='budgets'),
    path('budgets/create/', views.budget_create_view, name='budget_create'),
    path('budgets/<int:pk>/delete/', views.budget_delete_view, name='budget_delete'),
    path('budgets/reset/', views.budget_reset_view, name='budget_reset'),

    # Savings Goals
    path('goals/', views.savings_goals_view, name='goals'),
    path('goals/create/', views.savings_goal_create_view, name='goal_create'),
    path('goals/<int:pk>/edit/', views.savings_goal_update_view, name='goal_update'),
    path('goals/<int:pk>/delete/', views.savings_goal_delete_view, name='goal_delete'),
    path('goals/<int:pk>/contribute/', views.savings_goal_contribute_view, name='goal_contribute'),

    # Recurring Transactions
    path('recurring/', views.recurring_transactions_view, name='recurring'),
    path('recurring/create/', views.recurring_create_view, name='recurring_create'),
    path('recurring/<int:pk>/toggle/', views.recurring_toggle_view, name='recurring_toggle'),
    path('recurring/<int:pk>/delete/', views.recurring_delete_view, name='recurring_delete'),
    path('recurring/process/', views.process_recurring_view, name='recurring_process'),

    # Analytics, Calculators & Reports
    path('analytics/', views.analytics_view, name='analytics'),
    path('calculators/', views.calculators_view, name='calculators'),
    path('reports/', views.reports_view, name='reports'),
    path('api/charts-data/', views.chart_data_api, name='api_charts_data'),

    # Data Export, Import & Backup
    path('export/csv/', views.export_csv_view, name='export_csv'),
    path('reports/pdf/<int:year>/<int:month>/', views.download_pdf_report_view, name='download_pdf_report'),
    path('backup/export/', views.backup_data_view, name='backup_data'),
    path('backup/restore/', views.restore_data_view, name='restore_data'),

    # REST API Endpoints & Health Check
    path('api/health/', views.api_health_check, name='api_health_check'),
    path('api/v1/transactions/', views.api_transactions_list_create, name='api_transactions_list_create'),
    path('api/v1/transactions/<int:pk>/', views.api_transaction_detail, name='api_transaction_detail'),
    path('api/v1/categories/', views.api_categories_list, name='api_categories_list'),
    path('api/v1/budgets/', views.api_budgets_list, name='api_budgets_list'),
    path('api/v1/goals/', views.api_goals_list, name='api_goals_list'),

    # Notifications
    path('notifications/', views.notifications_view, name='notifications'),
    path('notifications/<int:pk>/read/', views.mark_notification_read_view, name='mark_notification_read'),
    path('notifications/read-all/', views.mark_all_notifications_read_view, name='mark_all_notifications_read'),
]
