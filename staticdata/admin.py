from django.contrib import admin
from .models import ProjectFile,Project,ProjectLike,ProjectComment,UserNameDb,Quiz


admin.site.register(ProjectFile)
admin.site.register(Project)
admin.site.register(ProjectLike)
admin.site.register(ProjectComment)
admin.site.register(UserNameDb)
admin.site.register(Quiz)