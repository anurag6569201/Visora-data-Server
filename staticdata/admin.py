import os
import uuid
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
import json

# Import your models (as provided in your models.py)
from .models import (
    ProjectFile, Project, ProjectLike, ProjectComment, UserNameDb,
    Quiz, Leaderboard, Examples, Theory, Category, UserSessionData
)

# IMPORTANT: Determine your app's label.
# This is usually the name of the app's directory or how it's registered in INSTALLED_APPS.
# For example, if your app is 'content_manager', replace "YOUR_ACTUAL_APP_LABEL" with "content_manager".
# You can verify this by temporarily adding to your admin.py:
# print(f"App label for Project model: {Project._meta.app_label}") # This will print the app_label
APP_LABEL = "staticdata" # <--- !!! REPLACE THIS WITH YOUR APP'S ACTUAL LABEL !!!


class ProjectFileInline(admin.TabularInline):
    model = ProjectFile
    extra = 1
    readonly_fields = ('get_file_link',)

    def get_file_link(self, obj):
        if obj.file:
            return format_html('<a href="{}" target="_blank">{}</a>', obj.file.url, os.path.basename(obj.file.name))
        return "No file uploaded"
    get_file_link.short_description = "File Link"

class ProjectCommentInline(admin.TabularInline):
    model = ProjectComment
    extra = 0
    fields = ('username', 'text', 'created_at')
    readonly_fields = ('created_at',)
    autocomplete_fields = ('username',)

class ProjectLikeInline(admin.TabularInline):
    model = ProjectLike
    extra = 0
    fields = ('username', 'created_at')
    readonly_fields = ('created_at',)
    autocomplete_fields = ('username',)

class BaseProjectDataInline(admin.StackedInline):
    extra = 0
    fields = ('data_pretty',) # If you also want to edit the raw JSON, add 'data' here
    readonly_fields = ('data_pretty',)

    def data_pretty(self, obj):
        if obj.data:
            return mark_safe(f"<pre>{json.dumps(obj.data, indent=2)}</pre>")
        return "No data"
    data_pretty.short_description = "Data (Formatted)"

class QuizInline(BaseProjectDataInline):
    model = Quiz

class TheoryInline(BaseProjectDataInline):
    model = Theory

class ExamplesInline(BaseProjectDataInline):
    model = Examples

@admin.register(UserNameDb)
class UserNameDbAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'role', 'userid', 'profile_picture')
    search_fields = ('username', 'email', 'userid')
    list_filter = ('role',)
    ordering = ('username',)

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'username', 'email', 'tabname', 'gradename', 'subjectname', 'display_total_likes', 'display_total_comments', 'created_implicitly')
    search_fields = ('name', 'description', 'username__username', 'username__email', 'token', 'tabname', 'gradename', 'subjectname', 'id') # Corrected username search
    list_filter = ('tabname', 'gradename', 'subjectname', 'username') # Added username to filter
    readonly_fields = ('id', 'display_total_likes', 'display_total_comments', 'get_folder_name_display')
    ordering = ('name',)
    fieldsets = (
        ('Project Information', {
            'fields': ('name', 'description', 'id', 'get_folder_name_display')
        }),
        ('User & Ownership', {
            'fields': ('username', 'email', 'token') # Assuming these are CharFields on Project now
        }),
        ('Categorization', {
            'fields': ('tabname', 'gradename', 'subjectname')
        }),
        ('Stats (Read-Only)', {
            'fields': ('display_total_likes', 'display_total_comments'),
            'classes': ('collapse',)
        }),
    )
    inlines = [
        ProjectFileInline,
        ProjectCommentInline,
        ProjectLikeInline,
        QuizInline,
        TheoryInline,
        ExamplesInline,
    ]

    def display_total_likes(self, obj):
        return obj.total_likes()
    display_total_likes.short_description = "Likes"

    def display_total_comments(self, obj):
        return obj.total_comments()
    display_total_comments.short_description = "Comments"

    def get_folder_name_display(self, obj):
        return obj.get_folder_name()
    get_folder_name_display.short_description = "Storage Folder"

    def created_implicitly(self, obj):
        is_default_token = obj.token == 'abcd'
        # Assuming username and email on Project model are CharFields as per your models.py
        is_default_user = obj.username == 'visora'
        is_default_email = obj.email == 'visora@gmail.com'
        return not (is_default_token and is_default_user and is_default_email)
    created_implicitly.boolean = True
    created_implicitly.short_description = "Explicitly Created?"

@admin.register(ProjectFile)
class ProjectFileAdmin(admin.ModelAdmin):
    list_display = ('project_link', 'get_file_link', 'get_folder')
    search_fields = ('project__name', 'file')
    list_select_related = ('project',)
    readonly_fields = ('get_file_link', 'get_folder')
    autocomplete_fields = ('project',)

    def project_link(self, obj):
        if obj.project:
            link = reverse(f"admin:{APP_LABEL}_project_change", args=[obj.project.id])
            return format_html('<a href="{}">{}</a>', link, obj.project.name)
        return "No Project"
    project_link.short_description = "Project"

    def get_file_link(self, obj):
        if obj.file:
            return format_html('<a href="{}" target="_blank">{}</a>', obj.file.url, os.path.basename(obj.file.name))
        return "No file uploaded"
    get_file_link.short_description = "File Link"

    def get_folder(self, obj):
         if obj.project:
            return obj.project.get_folder_name()
         return "N/A"
    get_folder.short_description = "Storage Folder"

@admin.register(ProjectComment)
class ProjectCommentAdmin(admin.ModelAdmin):
    list_display = ('project_link', 'username_link', 'text_preview', 'created_at')
    search_fields = ('text', 'project__name', 'username__username')
    list_filter = ('created_at',)
    readonly_fields = ('created_at',)
    list_select_related = ('project', 'username')
    autocomplete_fields = ('project', 'username')
    date_hierarchy = 'created_at'

    def project_link(self, obj):
        if obj.project:
            link = reverse(f"admin:{APP_LABEL}_project_change", args=[obj.project.id])
            return format_html('<a href="{}">{}</a>', link, obj.project.name)
        return "No Project"
    project_link.short_description = "Project"

    def username_link(self, obj):
        if obj.username:
             link = reverse(f"admin:{APP_LABEL}_usernamedb_change", args=[obj.username.id])
             return format_html('<a href="{}">{}</a>', link, obj.username.username)
        return "No User"
    username_link.short_description = "User"

    def text_preview(self, obj):
        return (obj.text[:75] + '...') if len(obj.text) > 75 else obj.text
    text_preview.short_description = "Comment Preview"

@admin.register(ProjectLike)
class ProjectLikeAdmin(admin.ModelAdmin):
    list_display = ('project_link', 'username_link', 'created_at')
    search_fields = ('project__name', 'username__username')
    list_filter = ('created_at',)
    readonly_fields = ('created_at',)
    list_select_related = ('project', 'username')
    autocomplete_fields = ('project', 'username')
    date_hierarchy = 'created_at'

    def project_link(self, obj):
        if obj.project:
            link = reverse(f"admin:{APP_LABEL}_project_change", args=[obj.project.id])
            return format_html('<a href="{}">{}</a>', link, obj.project.name)
        return "No Project"
    project_link.short_description = "Project"

    def username_link(self, obj):
        if obj.username:
             link = reverse(f"admin:{APP_LABEL}_usernamedb_change", args=[obj.username.id])
             return format_html('<a href="{}">{}</a>', link, obj.username.username)
        return "No User"
    username_link.short_description = "User"

class BaseProjectDataAdmin(admin.ModelAdmin):
    list_display = ('project_link', 'data_preview')
    search_fields = ('project__name',)
    list_select_related = ('project',)
    autocomplete_fields = ('project',)
    readonly_fields = ('data_pretty',)
    fields = ('project', 'data_pretty') # If you want to edit the raw JSON, add 'data'

    def project_link(self, obj):
        if obj.project:
            link = reverse(f"admin:{APP_LABEL}_project_change", args=[obj.project.id])
            return format_html('<a href="{}">{}</a>', link, obj.project.name)
        return "No Project"
    project_link.short_description = "Project"

    def data_preview(self, obj):
        if isinstance(obj.data, dict):
            preview_keys = list(obj.data.keys())[:3]
            ellipsis = '...' if len(obj.data.keys()) > 3 else ''
            return f"Dict with keys: {', '.join(preview_keys)}{ellipsis}"
        elif isinstance(obj.data, list):
            return f"List with {len(obj.data)} items"
        return str(obj.data)[:50] + ('...' if len(str(obj.data)) > 50 else '')
    data_preview.short_description = "Data Preview"

    def data_pretty(self, obj):
        if obj.data:
            return mark_safe(f"<pre>{json.dumps(obj.data, indent=2)}</pre>")
        return "No data"
    data_pretty.short_description = "Data (Formatted)"

@admin.register(Quiz)
class QuizAdmin(BaseProjectDataAdmin):
    pass

@admin.register(Theory)
class TheoryAdmin(BaseProjectDataAdmin):
    pass

@admin.register(Examples)
class ExamplesAdmin(BaseProjectDataAdmin):
    pass

@admin.register(Leaderboard)
class LeaderboardAdmin(admin.ModelAdmin):
    list_display = ('user_link', 'score', 'updated_at', 'needs_update_check_display')
    search_fields = ('user__username', 'user__email')
    list_filter = ('updated_at',)
    readonly_fields = ('updated_at',)
    list_select_related = ('user',)
    autocomplete_fields = ('user',)
    ordering = ('-score', 'updated_at')
    date_hierarchy = 'updated_at'

    def user_link(self, obj):
        if obj.user:
             link = reverse(f"admin:{APP_LABEL}_usernamedb_change", args=[obj.user.id])
             return format_html('<a href="{}">{}</a>', link, obj.user.username)
        return "No User"
    user_link.short_description = "User"

    def needs_update_check_display(self, obj):
        return obj.check_time_gap()
    needs_update_check_display.boolean = True
    needs_update_check_display.short_description = "Update > 5s ago?"

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'category_name', 'parent_link')
    search_fields = ('name', 'category_name', 'parent__name')
    list_filter = ('parent',) # Parent is a FK, so this should work directly
    autocomplete_fields = ('parent',)
    ordering = ('parent__name', 'name')

    def parent_link(self, obj):
        if obj.parent:
            link = reverse(f"admin:{APP_LABEL}_category_change", args=[obj.parent.id])
            return format_html('<a href="{}">{}</a>', link, str(obj.parent))
        return "–"
    parent_link.short_description = "Parent Category"

@admin.register(UserSessionData)
class UserSessionDataAdmin(admin.ModelAdmin):
    list_display = ('anonymous_user_id_short', 'name', 'topic', 'difficulty', 'user_points', 'study_streak', 'updated_at', 'created_at')
    search_fields = ('anonymous_user_id', 'name', 'topic')
    list_filter = ('difficulty', 'theme_mode', 'high_contrast', 'reduce_animations', 'last_study_date', 'created_at', 'updated_at')
    readonly_fields = ('anonymous_user_id', 'created_at', 'updated_at', 'plan_analysis_pretty', 'subtopics_pretty', 'plan_data_pretty', 'review_schedule_pretty', 'earned_badges_pretty', 'chat_history_pretty', 'journal_prompts_pretty')
    ordering = ('anonymous_user_id', '-updated_at')
    date_hierarchy = 'updated_at' # Good for navigating by time
    fieldsets = (
        ('Session Identity', {
            'fields': ('anonymous_user_id', 'name', 'topic')
        }),
        ('Configuration', {
            'fields': ('version', 'prerequisites', 'duration', 'difficulty')
        }),
        ('Accessibility', {
            'fields': ('theme_mode', 'font_size_factor', 'high_contrast', 'reduce_animations'),
            'classes': ('collapse',)
        }),
        ('Progress & Stats', {
            'fields': ('user_points', 'study_streak', 'earned_badges_pretty', 'last_study_date'),
            'classes': ('collapse',)
        }),
         ('Learning Plan & Content', {
            'fields': ('selected_subtopic_id', 'subtopics_pretty', 'plan_data_pretty', 'review_schedule_pretty', 'plan_analysis_pretty'),
            'classes': ('collapse',)
        }),
        ('Interaction Data', {
             'fields': ('chat_history_pretty', 'journal_prompts_pretty'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def anonymous_user_id_short(self, obj):
        return str(obj.anonymous_user_id).split('-')[0] + '...'
    anonymous_user_id_short.short_description = "Anon User ID"

    def _pretty_print_json(self, data, field_name):
        if data:
            try:
                return mark_safe(f"<pre>{json.dumps(data, indent=2)}</pre>")
            except TypeError:
                return f"Could not serialize {field_name}"
        return "Empty"

    def subtopics_pretty(self, obj):
        return self._pretty_print_json(obj.subtopics, "Subtopics")
    subtopics_pretty.short_description = "Subtopics (Formatted)"

    def plan_data_pretty(self, obj):
        return self._pretty_print_json(obj.plan_data, "Plan Data")
    plan_data_pretty.short_description = "Plan Data (Formatted)"

    def review_schedule_pretty(self, obj):
        return self._pretty_print_json(obj.review_schedule, "Review Schedule")
    review_schedule_pretty.short_description = "Review Schedule (Formatted)"

    def plan_analysis_pretty(self, obj):
        return self._pretty_print_json(obj.plan_analysis, "Plan Analysis")
    plan_analysis_pretty.short_description = "Plan Analysis (Formatted)"

    def earned_badges_pretty(self, obj):
        return self._pretty_print_json(obj.earned_badges, "Earned Badges")
    earned_badges_pretty.short_description = "Earned Badges (Formatted)"

    def chat_history_pretty(self, obj):
        return self._pretty_print_json(obj.chat_history, "Chat History")
    chat_history_pretty.short_description = "Chat History (Formatted)"

    def journal_prompts_pretty(self, obj):
        return self._pretty_print_json(obj.journal_prompts, "Journal Prompts")
    journal_prompts_pretty.short_description = "Journal Prompts (Formatted)"