from django.contrib import admin
from .models import ProjectFile,Project,ProjectLike,ProjectComment,UserNameDb,Quiz,Leaderboard,Examples,Theory,Category


admin.site.register(ProjectFile)
admin.site.register(Project)
admin.site.register(ProjectLike)
admin.site.register(ProjectComment)
admin.site.register(UserNameDb)
admin.site.register(Leaderboard)
admin.site.register(Quiz)
admin.site.register(Theory)
admin.site.register(Examples)
admin.site.register(Category)