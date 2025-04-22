from django.contrib import admin
from .models import (
    Category, Course,    Module, Lesson, Resource, CertificateTemplate,
    SCORMxAPISettings, LearningPath
)



class ModuleInline(admin.StackedInline):
    model = Module
    extra = 1
    show_change_link = True

class ResourceInline(admin.TabularInline):
    model = Resource
    extra = 1

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'level', 'status', 'created_at')
    list_filter = ('status', 'level', 'category')
    search_fields = ('title', 'description', 'code')
    prepopulated_fields = {'slug': ('title',)}
    inlines = [ ModuleInline, ResourceInline]

class LessonInline(admin.StackedInline):
    model = Lesson
    extra = 1

@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'order', 'is_published')
    list_filter = ('is_published', 'course')
    search_fields = ('title', 'description')
    inlines = [LessonInline]
    ordering = ('course', 'order')

@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ('title', 'module', 'lesson_type', 'duration_display', 'is_published')
    list_filter = ('lesson_type', 'is_published')
    search_fields = ('title', 'description')
    ordering = ('module', 'order')

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'resource_type')
    list_filter = ('resource_type',)
    search_fields = ('title',)

@admin.register(CertificateTemplate)
class CertificateTemplateAdmin(admin.ModelAdmin):
    list_display = ('course', 'is_active', 'template')
    list_filter = ('is_active', 'template')

@admin.register(SCORMxAPISettings)
class SCORMxAPISettingsAdmin(admin.ModelAdmin):
    list_display = ('course', 'is_active', 'standard')
    list_filter = ('is_active', 'standard')

@admin.register(LearningPath)
class LearningPathAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_active', 'created_at')
    list_filter = ('is_active',)
    filter_horizontal = ('courses',)