from django.urls import path
from . import views

app_name = 'crm'

urlpatterns = [
    # =====================================
    # CORE CRM ROUTES
    # =====================================
    
    # Dashboard - The central hub for all CRM activities
    path('', views.crm_dashboard, name='dashboard'),
    
    # =====================================
    # CLIENT MANAGEMENT ROUTES
    # =====================================
    
    # Client CRUD operations with RESTful URL patterns
    path('clients/', views.client_list, name='client_list'),
    path('clients/create/', views.client_create, name='client_create'),
    path('clients/<int:client_id>/', views.client_detail, name='client_detail'),
    path('clients/<int:client_id>/edit/', views.client_update, name='client_update'),
    path('clients/<int:client_id>/delete/', views.client_delete, name='client_delete'),
    
    # =====================================
    # CUSTOMER INTERACTION ROUTES
    # =====================================
    
    # Interaction management with context-aware routing
    path('clients/<int:client_id>/interaction/add/', views.add_interaction, name='add_interaction'),
    path('interactions/', views.interaction_list, name='interaction_list'),
    path('clients/<int:client_id>/interactions/', views.interaction_list, name='client_interactions'),
    
    # =====================================
    # DEAL MANAGEMENT ROUTES (NEW)
    # =====================================
    
    # Deal CRUD operations following the same patterns as clients
    path('deals/', views.deal_list, name='deal_list'),
    path('deals/create/', views.deal_create, name='deal_create'),
    path('deals/<int:deal_id>/', views.deal_detail, name='deal_detail'),
    path('deals/<int:deal_id>/edit/', views.deal_update, name='deal_update'),
    path('deals/<int:deal_id>/delete/', views.deal_delete, name='deal_delete'),
    
    # Context-aware deal creation (from client page)
    path('clients/<int:client_id>/deals/create/', views.deal_create, name='deal_create_for_client'),
    
    # =====================================
    # TASK MANAGEMENT ROUTES (NEW)
    # =====================================
    
    # Task CRUD operations with comprehensive context support
    path('tasks/', views.task_list, name='task_list'),
    path('tasks/create/', views.task_create, name='task_create'),
    path('tasks/<int:task_id>/', views.task_detail, name='task_detail'),
    path('tasks/<int:task_id>/edit/', views.task_update, name='task_update'),
    path('tasks/<int:task_id>/delete/', views.task_delete, name='task_delete'),
    
    # Context-aware task creation (from client or deal pages)
    path('clients/<int:client_id>/tasks/create/', views.task_create, name='task_create_for_client'),
    path('deals/<int:deal_id>/tasks/create/', views.task_create, name='task_create_for_deal'),
    
    # Quick task completion for productivity workflows
    path('tasks/<int:task_id>/complete/', views.task_complete, name='task_complete'),
    
    # =====================================
    # FOLLOW-UP MANAGEMENT ROUTES
    # =====================================
    
    # Follow-up tracking and management
    path('followups/', views.followup_list, name='followup_list'),
    path('interactions/<int:interaction_id>/complete-followup/', views.mark_followup_complete, name='mark_followup_complete'),
    
    # =====================================
    # ANALYTICS AND REPORTING ROUTES
    # =====================================
    
    # Business intelligence and performance tracking
    path('analytics/', views.client_analytics, name='analytics'),
    path('performance-report/', views.performance_report, name='performance_report'),
    path('performance-report/pdf/', views.export_performance_pdf, name='export_performance_pdf'),
    path('performance-report/excel/', views.export_performance_excel, name='export_performance_excel'),

    # =====================================
    # AJAX/API UTILITY ROUTES
    # =====================================
    
    # Client-related AJAX endpoints for enhanced user experience
    path('ajax/search-clients/', views.search_clients, name='search_clients'),
    path('ajax/client/<int:client_id>/stats/', views.client_quick_stats, name='client_quick_stats'),
    
    # Deal-related AJAX endpoints (NEW)
    path('ajax/deal/<int:deal_id>/stats/', views.deal_quick_stats, name='deal_quick_stats'),
    
    # Task-related AJAX endpoints (NEW)
    path('ajax/task/<int:task_id>/stats/', views.task_quick_stats, name='task_quick_stats'),
    
    # =====================================
    # INTEGRATION ROUTES (FOR FUTURE EXPANSION)
    # =====================================
    
    # These routes are planned for future integration with other systems
    # Uncomment and implement when needed:
    
    # Quote integration routes
    # path('clients/<int:client_id>/quotes/', views.client_quotes, name='client_quotes'),
    # path('deals/<int:deal_id>/quotes/', views.deal_quotes, name='deal_quotes'),
    
    # Calendar integration routes
    # path('calendar/', views.crm_calendar, name='calendar'),
    # path('calendar/events/', views.calendar_events, name='calendar_events'),
    
    # Import/Export routes
    # path('import/clients/', views.import_clients, name='import_clients'),
    # path('export/clients/', views.export_clients, name='export_clients'),
    # path('export/deals/', views.export_deals, name='export_deals'),
    
    # Advanced analytics routes
    # path('analytics/pipeline/', views.pipeline_analytics, name='pipeline_analytics'),
    # path('analytics/performance/', views.performance_analytics, name='performance_analytics'),
    # path('analytics/forecasting/', views.sales_forecasting, name='sales_forecasting'),

]
