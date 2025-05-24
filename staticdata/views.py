import os
import uuid
from django.db import models
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json
import logging
import shutil

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics, permissions, viewsets, pagination, filters
from rest_framework.decorators import api_view, action
from rest_framework.exceptions import NotFound, PermissionDenied
from django.core.files.base import ContentFile
from django.db.models import Q

from .models import (
    Project, ProjectFile, ProjectComment, ProjectLike, UserNameDb, Quiz, Theory,
    Examples, Leaderboard, Category, UserSessionData
)
from .serializers import (
    ProjectCommentSerializer, ProjectLikeSerializer, ProjectSerializer,
    QuizSerializer, TheorySerializer, ExamplesSerializer, ScoreSerializer,
    CategorySerializer, UserSessionDataSerializer
)
from staticdata.score_calculations import likeScoreCalculation

logger = logging.getLogger(__name__)

def get_username_from_auth_header(request):
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        logger.warning("Authorization header missing")
        return None
    if not UserNameDb.objects.filter(username=auth_header).exists():
        logger.warning(f"Username '{auth_header}' from Authorization header not found in UserNameDb.")
        return None
    return auth_header

class UploadProjectAPIView(APIView):
    def post(self, request):
        username = get_username_from_auth_header(request)
        if not username:
            return Response({"error": "Unauthorized or User not found"}, status=status.HTTP_401_UNAUTHORIZED)

        name = request.data.get("project_name")
        description = request.data.get("project_description", "")
        token = request.data.get("token", str(uuid.uuid4())[:8])
        email = request.data.get("email")
        
        tabname = request.data.get("project_tab_name", "DefaultTab")
        gradename = request.data.get("project_grade_name", "DefaultGrade")
        subjectname = request.data.get("project_subject_name", "DefaultSubject")

        html_content = request.data.get("html_content", "")
        css_content = request.data.get("css_content", "")
        js_content = request.data.get("js_content", "")
        files = request.FILES.getlist("files")

        if not name:
            return Response({"error": "Project name is required"}, status=status.HTTP_400_BAD_REQUEST)

        user_obj = UserNameDb.objects.get(username=username)
        if not email and user_obj:
            email = user_obj.email

        project_id = request.data.get("id")
        project = None
        created = False

        if project_id:
            try:
                project = Project.objects.get(id=project_id, username=username)
                project.name = name
                project.description = description
                project.token = token
                project.email = email
                project.tabname = tabname
                project.gradename = gradename
                project.subjectname = subjectname
                project.save()
            except Project.DoesNotExist:
                return Response({"error": "Project with specified ID not found or access denied."}, status=status.HTTP_404_NOT_FOUND)
        else:
            project, created = Project.objects.get_or_create(
                name=name, username=username,
                defaults={
                    'description': description, 'token': token, 'email': email,
                    'tabname': tabname, 'gradename': gradename, 'subjectname': subjectname
                }
            )
            if not created:
                project.description = description
                project.token = token
                project.email = email
                project.tabname = tabname
                project.gradename = gradename
                project.subjectname = subjectname
                project.save()

        if files:
            for file_obj in files:
                ext = os.path.splitext(file_obj.name)[1].lower()
                if ext == ".html": html_content = file_obj.read().decode("utf-8", errors='ignore')
                elif ext == ".css": css_content = file_obj.read().decode("utf-8", errors='ignore')
                elif ext == ".js": js_content = file_obj.read().decode("utf-8", errors='ignore')
        
        combined_html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>{project.name}</title><style>{css_content}</style></head><body>{html_content}<script type="module">{js_content}</script></body></html>"""
        
        project_folder_path = os.path.join(settings.MEDIA_ROOT, "projects", project.get_folder_name())
        os.makedirs(project_folder_path, exist_ok=True)
        
        combined_file_name = "combined.html"
        combined_file_server_path = os.path.join(project_folder_path, combined_file_name)

        with open(combined_file_server_path, "w", encoding="utf-8") as f:
            f.write(combined_html)

        relative_path_for_db = os.path.join("projects", project.get_folder_name(), combined_file_name)
        
        ProjectFile.objects.update_or_create(
            project=project, file__endswith=combined_file_name,
            defaults={'file': relative_path_for_db}
        )
        
        try: likeScoreCalculation(project.username)
        except Exception as e: logger.error(f"Error in likeScoreCalculation for {project.username}: {e}")

        serializer = ProjectSerializer(project)
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

@api_view(['GET'])
def list_projects(request):
    projects_data = []
    auth_username = get_username_from_auth_header(request)

    if auth_username:
        projects_queryset = Project.objects.filter(username=auth_username).order_by('-pk')
    else:
        selected_tab = request.GET.get('selectedTab')
        grade = request.GET.get('grade')
        subject = request.GET.get('subject')
        filter_q = Q()
        if selected_tab: filter_q &= Q(tabname=selected_tab)
        if grade: filter_q &= Q(gradename=grade)
        if subject: filter_q &= Q(subjectname=subject)
        projects_queryset = Project.objects.filter(filter_q).order_by('-pk')

    for project in projects_queryset:
        user = UserNameDb.objects.filter(username=project.username).first()
        if not user:
            logger.warning(f"Project {project.id} has username '{project.username}' not in UserNameDb.")
            continue

        relative_combined_path = os.path.join("projects", project.get_folder_name(), "combined.html")
        full_combined_path = os.path.join(settings.MEDIA_ROOT, relative_combined_path)
        combined_html_content = ""

        if os.path.exists(full_combined_path):
            try:
                with open(full_combined_path, "r", encoding="utf-8", errors='ignore') as f:
                    combined_html_content = f.read()
            except Exception as e:
                logger.error(f"Error reading combined.html for project {project.id}: {e}")
        else:
            logger.warning(f"Combined.html not found for project {project.id} at {full_combined_path}")

        projects_data.append({
            "id": project.id, "name": project.name, "description": project.description,
            "username": user.username, "profile_picture": user.profile_picture,
            "user_userid": user.userid, "token": project.token,
            "updated_at": project.pk, # Consider adding a real updated_at field to Project model
            "combined_html": combined_html_content,
        })
    return JsonResponse({"projects": projects_data})

@api_view(['GET'])
def get_project(request, id):
    try:
        project = Project.objects.get(id=id)
        relative_combined_path = os.path.join("projects", project.get_folder_name(), "combined.html")
        full_combined_path = os.path.join(settings.MEDIA_ROOT, relative_combined_path)
        combined_html_content = ""
        if os.path.exists(full_combined_path):
            try:
                with open(full_combined_path, "r", encoding="utf-8", errors='ignore') as f:
                    combined_html_content = f.read()
            except Exception as e:
                logger.error(f"Error reading combined.html for project detail {project.id}: {e}")
        serializer = ProjectSerializer(project)
        data = serializer.data
        data['combined_html'] = combined_html_content
        return Response(data)
    except Project.DoesNotExist:
        return Response({"error": "Project not found"}, status=status.HTTP_404_NOT_FOUND)
    except ValueError:
        return Response({"error": "Invalid project ID format"}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['PUT'])
def update_project_code(request, id):
    username = get_username_from_auth_header(request)
    if not username:
        return Response({"error": "Unauthorized or User not found"}, status=status.HTTP_401_UNAUTHORIZED)
    try:
        project = Project.objects.get(id=id)
    except Project.DoesNotExist:
        return Response({"error": "Project not found"}, status=status.HTTP_404_NOT_FOUND)
    except ValueError:
        return Response({"error": "Invalid project ID format"}, status=status.HTTP_400_BAD_REQUEST)

    if project.username != username:
        return Response({"error": "Permission denied. You do not own this project."}, status=status.HTTP_403_FORBIDDEN)

    data = request.data
    project.name = data.get("name", project.name)
    project.description = data.get("description", project.description)
    html_content = data.get("html_content", "")
    css_content = data.get("css_content", "")
    js_content = data.get("js_content", "")
    
    combined_html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>{project.name}</title><style>{css_content}</style></head><body>{html_content}<script type="module">{js_content}</script></body></html>"""
    project_folder_path = os.path.join(settings.MEDIA_ROOT, "projects", project.get_folder_name())
    os.makedirs(project_folder_path, exist_ok=True)
    combined_file_name = "combined.html"
    combined_file_server_path = os.path.join(project_folder_path, combined_file_name)

    try:
        with open(combined_file_server_path, "w", encoding="utf-8") as f:
            f.write(combined_html)
        project.save()
        relative_path_for_db = os.path.join("projects", project.get_folder_name(), combined_file_name)
        ProjectFile.objects.update_or_create(
            project=project, file__endswith=combined_file_name,
            defaults={'file': relative_path_for_db}
        )
    except IOError as e:
        logger.error(f"IOError writing combined.html for project {project.id}: {e}")
        return Response({"error": "Failed to write project file to server."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        logger.error(f"Unexpected error updating project {project.id}: {e}")
        return Response({"error": "An unexpected error occurred."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    serializer = ProjectSerializer(project)
    response_data = serializer.data
    response_data['combined_html'] = combined_html
    return Response(response_data, status=status.HTTP_200_OK)

@api_view(['DELETE'])
def delete_project_server(request, id):
    username = get_username_from_auth_header(request)
    if not username:
        return Response({"error": "Unauthorized or User not found"}, status=status.HTTP_401_UNAUTHORIZED)
    try:
        project = Project.objects.get(id=id)
    except Project.DoesNotExist:
        return Response({"error": "Project not found"}, status=status.HTTP_404_NOT_FOUND)
    except ValueError:
        return Response({"error": "Invalid project ID format"}, status=status.HTTP_400_BAD_REQUEST)

    if project.username != username:
        return Response({"error": "Permission denied. You do not own this project."}, status=status.HTTP_403_FORBIDDEN)

    try:
        project_folder_path = os.path.join(settings.MEDIA_ROOT, "projects", project.get_folder_name())
        if os.path.exists(project_folder_path):
            shutil.rmtree(project_folder_path)
            logger.info(f"Deleted project folder: {project_folder_path}")
        project.delete()
        logger.info(f"Deleted project {id} for user {username} from database.")
        return Response(status=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        logger.error(f"Error deleting project {id}: {e}")
        return Response({"error": "Failed to delete project."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def list_project_names_ids(request):
    projects_data = []
    auth_username = get_username_from_auth_header(request)
    if not auth_username:
         return JsonResponse({"error": "Authorization header required or user not found"}, status=401)
    projects = Project.objects.filter(username=auth_username)
    for project in projects:
        projects_data.append({"id": project.id, "name": project.name})
    return JsonResponse({"projects": projects_data})

class CommentCreateView(APIView):
    serializer_class = ProjectCommentSerializer
    permission_classes = [permissions.AllowAny]

    def get(self, request, project_id):
        project = get_object_or_404(Project, id=project_id)
        comments = ProjectComment.objects.filter(project=project).order_by("-created_at")
        serializer = self.serializer_class(comments, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, project_id):
        username_str = get_username_from_auth_header(request)
        if not username_str:
            return JsonResponse({"error": "Unauthorized or User not found"}, status=401)
        user = UserNameDb.objects.filter(username=username_str).first()
        if not user:
            return JsonResponse({"error": "User not found in UserNameDb"}, status=404)
        project = get_object_or_404(Project, id=project_id)
        serializer = self.serializer_class(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save(username=user, project=project)
            try: likeScoreCalculation(project.username)
            except Exception as e: logger.error(f"Error in likeScoreCalculation for {project.username} during comment: {e}")
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@method_decorator(csrf_exempt, name='dispatch')
class LikeToggleView(View):
    def get(self, request, project_id):
        username_str = get_username_from_auth_header(request)
        if not username_str:
            return JsonResponse({"error": "Unauthorized or User not found"}, status=401)
        user = get_object_or_404(UserNameDb, username=username_str)
        project = get_object_or_404(Project, id=project_id)
        total_likes = project.total_likes()
        is_liked = ProjectLike.objects.filter(username=user, project=project).exists()
        return JsonResponse({"total_likes": total_likes, "is_liked": is_liked})

    def post(self, request, project_id):
        username_str = get_username_from_auth_header(request)
        if not username_str:
            return JsonResponse({"error": "Unauthorized or User not found"}, status=401)
        user = get_object_or_404(UserNameDb, username=username_str)
        project = get_object_or_404(Project, id=project_id)
        like, created = ProjectLike.objects.get_or_create(username=user, project=project)
        if not created:
            like.delete()
            liked = False
        else:
            liked = True
        total_likes = project.total_likes()
        try: likeScoreCalculation(project.username)
        except Exception as e: logger.error(f"Error in likeScoreCalculation for {project.username} during like toggle: {e}")
        return JsonResponse({"liked": liked, "likes_count": total_likes})

@method_decorator(csrf_exempt, name='dispatch')
class RegisterUserNameDbView(View):
    def post(self, request):
        try:
            data = json.loads(request.body.decode("utf-8"))
            username = data.get("username")
            profile_picture = data.get("profile_picture")
            userid = data.get("userid")
            role = data.get("role")
            email = data.get("email")
            if UserNameDb.objects.filter(username=username).exists():
                return JsonResponse({"error": "User already exists in Visiora-Data."}, status=400)
            user = UserNameDb.objects.create(username=username, email=email,profile_picture=profile_picture,userid=userid,role=role)
            Leaderboard.objects.get_or_create(user=user) # Use the created user instance
            return JsonResponse({"message": "User created in Visiora-Data."}, status=201)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format"}, status=400)
        except Exception as e:
            logger.error(f"Error registering UserNameDb: {e}")
            return JsonResponse({"error": str(e)}, status=500)

class QuizViewSet(viewsets.ModelViewSet):
    serializer_class = QuizSerializer
    def get_queryset(self):
        project_id = self.kwargs.get('project_id')
        if project_id:
            return Quiz.objects.filter(project_id=project_id)
        return Quiz.objects.all()
    def perform_create(self, serializer):
        project_id = self.kwargs.get('project_id')
        project = get_object_or_404(Project, id=project_id)
        serializer.save(project=project)

class TheoryViewSet(viewsets.ModelViewSet):
    serializer_class = TheorySerializer
    def get_queryset(self):
        project_id = self.kwargs.get('project_id')
        if project_id:
            return Theory.objects.filter(project_id=project_id)
        return Theory.objects.all()
    def perform_create(self, serializer):
        project_id = self.kwargs.get('project_id')
        project = get_object_or_404(Project, id=project_id)
        serializer.save(project=project)
    
class ScorePagination(pagination.PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class ScoreViewSet(viewsets.ModelViewSet):
    queryset = Leaderboard.objects.all().order_by('-score')
    serializer_class = ScoreSerializer
    pagination_class = ScorePagination
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['score', 'updated_at']

@api_view(['POST'])
def generate_ai_content(request, project_id, content_type):
    try:
        project = Project.objects.get(id=project_id)
        logger.info(f"AI content generation requested for project {project_id}, type {content_type}")
        return Response({'status': 'success', 'generated': content_type, 'message': 'AI generation placeholder succeeded.'})
    except Project.DoesNotExist:
        return Response({"error": "Project not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error in AI content generation for project {project_id}: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CategoryListView(APIView):
    def get(self, request):
        root_categories = Category.objects.filter(parent__isnull=True)
        structured_data = {}
        for category in root_categories:
            structured_data[category.name] = self.build_category_structure(category)
        return Response(structured_data)
    
    def build_category_structure(self, category):
        children = category.children.all()
        if not children:
            return category.category_name if category.category_name else [] 
        data = {}
        for child in children:
            data[child.name] = self.build_category_structure(child)
        return data

class StandardResultsSetPagination(pagination.PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50

class ProjectSearchView(generics.ListAPIView):
    serializer_class = ProjectSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = StandardResultsSetPagination
    def get_queryset(self):
        query = self.request.query_params.get('query', '').strip()
        if query:
            return Project.objects.filter(
                Q(name__icontains=query) | Q(description__icontains=query)
            ).order_by('-pk')
        return Project.objects.none()

class ProjectDetailView(generics.RetrieveAPIView):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'id'
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data
        relative_combined_path = os.path.join("projects", instance.get_folder_name(), "combined.html")
        full_combined_path = os.path.join(settings.MEDIA_ROOT, relative_combined_path)
        combined_html_content = ""
        if os.path.exists(full_combined_path):
            try:
                with open(full_combined_path, "r", encoding="utf-8", errors='ignore') as f:
                    combined_html_content = f.read()
            except Exception as e:
                logger.error(f"Error reading combined.html for project detail {instance.id} (generic view): {e}")
        data['combined_html'] = combined_html_content
        return Response(data)

class ProjectMaterialsView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    material_map = {
        'quizzes': {'model': Quiz, 'serializer': QuizSerializer},
        'theories': {'model': Theory, 'serializer': TheorySerializer},
        'examples': {'model': Examples, 'serializer': ExamplesSerializer},
    }
    def get_serializer_class(self):
        material_type = self.request.query_params.get('type', None)
        map_entry = self.material_map.get(material_type)
        if map_entry: return map_entry['serializer']
        return None 
    def get_queryset(self):
        project_id = self.kwargs.get('project_id')
        material_type = self.request.query_params.get('type', None)
        map_entry = self.material_map.get(material_type)
        if not project_id or not map_entry: return Quiz.objects.none() 
        model = map_entry['model']
        return model.objects.filter(project__id=project_id)
    def list(self, request, *args, **kwargs):
        material_type = request.query_params.get('type', None)
        project_id = kwargs.get('project_id')
        if not project_id: return Response({'error': 'Project ID not provided in URL.'}, status=status.HTTP_400_BAD_REQUEST)
        if not self.material_map.get(material_type):
            return Response(
                {'error': f'Invalid material type specified. Valid types are: {", ".join(self.material_map.keys())}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().list(request, *args, **kwargs)

def get_anonymous_id_from_request_usersession(request): # Renamed to avoid conflict if imported directly
    anon_id_str = request.headers.get('X-Anonymous-User-ID')
    if not anon_id_str:
        logger.warning("Missing X-Anonymous-User-ID header for UserSession")
        return None
    try:
        return uuid.UUID(anon_id_str)
    except ValueError:
        logger.warning(f"Invalid UUID format for X-Anonymous-User-ID (UserSession): {anon_id_str}")
        return None

def get_default_session_data():
     return {
         'id': None, 'anonymous_user_id': None, 'name': '', 'version': '5.5-html', 
         'topic': '', 'prerequisites': '', 'duration': '1', 'difficulty': 'Intermediate', 
         'theme_mode': 'dark', 'font_size_factor': 1.0, 'high_contrast': False, 
         'reduce_animations': False, 'subtopics': [], 'plan_data': {}, 'review_schedule': {}, 
         'plan_analysis': None, 'user_points': 0, 'study_streak': 0, 'earned_badges': [], 
         'last_study_date': None, 'chat_history': [{'sender': 'bot', 'text': 'Hi! How can I help?'}],
         'journal_prompts': {}, 'selected_subtopic_id': None, 'created_at': None, 'updated_at': None
     }

class UserSessionViewSet(viewsets.ViewSet):
    serializer_class = UserSessionDataSerializer
    def get_queryset(self, request):
        anonymous_user_id = get_anonymous_id_from_request_usersession(request)
        if not anonymous_user_id:
             raise PermissionDenied("Valid X-Anonymous-User-ID header required.")
        return UserSessionData.objects.filter(anonymous_user_id=anonymous_user_id)

    @action(detail=False, methods=['get'], url_path='latest')
    def latest(self, request):
        anonymous_user_id = get_anonymous_id_from_request_usersession(request)
        if not anonymous_user_id:
             return Response({"detail": "Valid X-Anonymous-User-ID header required."}, status=status.HTTP_403_FORBIDDEN)
        try:
            queryset = self.get_queryset(request)
            session_data = queryset.order_by('-updated_at').first() # Corrected to latest
            if not session_data:
                logger.info(f"No session data found for anon_id {str(anonymous_user_id)[:8]}. Returning defaults.")
                return Response(get_default_session_data(), status=status.HTTP_200_OK)
            
            from datetime import date, timedelta # Ensure imports are here if not global
            today = date.today()
            reset_streak = False
            if session_data.last_study_date:
                yesterday = today - timedelta(days=1)
                if session_data.last_study_date < yesterday:
                    session_data.study_streak = 0
                    reset_streak = True
            elif session_data.study_streak != 0:
                session_data.study_streak = 0
                reset_streak = True
            serializer = UserSessionDataSerializer(session_data)
            logger.info(f"Loaded latest session (ID: {session_data.pk}) for anon_id {str(anonymous_user_id)[:8]}. Streak reset on load: {reset_streak}")
            return Response(serializer.data, status=status.HTTP_200_OK)
        except PermissionDenied as e: return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
             logger.error(f"Error loading latest session for anon_id {str(anonymous_user_id)[:8]}: {e}", exc_info=True)
             return Response({"detail": "An error occurred while loading session data."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def create(self, request):
        from datetime import date # Ensure import
        anonymous_user_id = get_anonymous_id_from_request_usersession(request)
        if not anonymous_user_id:
             return Response({"detail": "Valid X-Anonymous-User-ID header required."}, status=status.HTTP_403_FORBIDDEN)
        request_data = request.data.copy()
        request_data['last_study_date'] = date.today().isoformat()
        logger.info(f"Creating session for anon_id {str(anonymous_user_id)[:8]}. Frontend streak: {request_data.get('study_streak')}, setting last_study_date to {request_data['last_study_date']}")
        request_data['anonymous_user_id'] = anonymous_user_id
        if 'name' not in request_data or not request_data['name']:
             request_data['name'] = f"Session - {request_data.get('topic', 'Untitled')[:50]}"
        serializer = UserSessionDataSerializer(data=request_data)
        try:
            serializer.is_valid(raise_exception=True)
            serializer.validated_data['anonymous_user_id'] = anonymous_user_id
            session_instance = serializer.save()
            logger.info(f"Session (ID: {session_instance.pk}) created for anon_id {str(anonymous_user_id)[:8]}.")
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except serializers.ValidationError as e: # Ensure serializers is imported
            logger.warning(f"Validation error creating session for anon_id {str(anonymous_user_id)[:8]}: {e.detail}")
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied as e: return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            logger.error(f"Error creating session for anon_id {str(anonymous_user_id)[:8]}: {e}", exc_info=True)
            return Response({"detail": "An error occurred while saving session data."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def update(self, request, pk=None):
        from datetime import date # Ensure import
        anonymous_user_id = get_anonymous_id_from_request_usersession(request)
        if not anonymous_user_id:
             return Response({"detail": "Valid X-Anonymous-User-ID header required."}, status=status.HTTP_403_FORBIDDEN)
        try:
            queryset = self.get_queryset(request)
            session_instance = queryset.get(pk=pk)
        except UserSessionData.DoesNotExist:
            logger.warning(f"Session update failed: Session ID {pk} not found for anon_id {str(anonymous_user_id)[:8]}.")
            raise NotFound(detail=f"Session with ID {pk} not found for this user.")
        except PermissionDenied as e: return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)
        request_data = request.data.copy()
        request_data['last_study_date'] = date.today().isoformat()
        logger.info(f"Updating session (ID: {pk}) for anon_id {str(anonymous_user_id)[:8]}. Frontend streak: {request_data.get('study_streak')}, setting last_study_date to {request_data['last_study_date']}")
        if 'name' not in request_data or not request_data['name']:
             request_data['name'] = f"Session - {request_data.get('topic', session_instance.topic)[:50]}"
        serializer = UserSessionDataSerializer(session_instance, data=request_data, partial=True)
        try:
            serializer.is_valid(raise_exception=True)
            serializer.save()
            logger.info(f"Session (ID: {pk}) updated for anon_id {str(anonymous_user_id)[:8]}.")
            return Response(serializer.data, status=status.HTTP_200_OK)
        except serializers.ValidationError as e: # Ensure serializers is imported
            logger.warning(f"Validation error updating session {pk} for anon_id {str(anonymous_user_id)[:8]}: {e.detail}")
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error updating session {pk} for anon_id {str(anonymous_user_id)[:8]}: {e}", exc_info=True)
            return Response({"detail": "An error occurred while saving session data."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def retrieve(self, request, pk=None):
        anonymous_user_id = get_anonymous_id_from_request_usersession(request)
        if not anonymous_user_id:
             return Response({"detail": "Valid X-Anonymous-User-ID header required."}, status=status.HTTP_403_FORBIDDEN)
        try:
            queryset = self.get_queryset(request)
            session_instance = queryset.get(pk=pk)
            serializer = UserSessionDataSerializer(session_instance)
            logger.info(f"Retrieved session (ID: {pk}) for anon_id {str(anonymous_user_id)[:8]}.")
            return Response(serializer.data)
        except UserSessionData.DoesNotExist:
             logger.warning(f"Session retrieve failed: Session ID {pk} not found for anon_id {str(anonymous_user_id)[:8]}.")
             raise NotFound(detail=f"Session with ID {pk} not found for this user.")
        except PermissionDenied as e: return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
             logger.error(f"Error retrieving session {pk} for anon_id {str(anonymous_user_id)[:8]}: {e}", exc_info=True)
             return Response({"detail": "An error occurred retrieving session data."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def list(self, request):
        anonymous_user_id = get_anonymous_id_from_request_usersession(request)
        if not anonymous_user_id:
             return Response({"detail": "Valid X-Anonymous-User-ID header required."}, status=status.HTTP_403_FORBIDDEN)
        try:
            queryset = self.get_queryset(request).order_by('-updated_at')
            serializer = UserSessionDataSerializer(queryset, many=True)
            logger.info(f"Listed {queryset.count()} sessions for anon_id {str(anonymous_user_id)[:8]}.")
            return Response(serializer.data)
        except PermissionDenied as e: return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
             logger.error(f"Error listing sessions for anon_id {str(anonymous_user_id)[:8]}: {e}", exc_info=True)
             return Response({"detail": "An error occurred listing sessions."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class OpenSourceUploadProjectAPIView(APIView):
    def post(self, request):
        name = request.data.get("project_name")
        description = request.data.get("project_description", "")
        token = request.data.get("token", str(uuid.uuid4())[:8])
        username_from_payload = request.data.get("username") # This username must exist
        email = request.data.get("email") # Optional, can be derived
        tabname = request.data.get("project_tab_name", "DefaultTab")
        gradename = request.data.get("project_grade_name", "DefaultGrade")
        subjectname = request.data.get("project_subject_name", "DefaultSubject")

        html_content = request.data.get("html_content", "")
        css_content = request.data.get("css_content", "")
        js_content = request.data.get("js_content", "")
        files = request.FILES.getlist("files")

        if not name or not username_from_payload:
            return Response({"error": "Project name and username are required"}, status=status.HTTP_400_BAD_REQUEST)

        if not UserNameDb.objects.filter(username=username_from_payload).exists():
            return Response({"error": f"Username '{username_from_payload}' provided does not exist."}, status=status.HTTP_400_BAD_REQUEST)
        
        user_obj = UserNameDb.objects.get(username=username_from_payload)
        if not email: email = user_obj.email

        project, created = Project.objects.get_or_create(
            name=name, username=username_from_payload,
            defaults={
                'description': description, 'token': token, 'email': email,
                'tabname': tabname, 'gradename': gradename, 'subjectname': subjectname
            }
        )
        if not created:
            project.description = description; project.token = token; project.email = email
            project.tabname = tabname; project.gradename = gradename; project.subjectname = subjectname
            project.save()

        if files:
            for file_obj in files:
                ext = os.path.splitext(file_obj.name)[1].lower()
                if ext == ".html": html_content = file_obj.read().decode("utf-8", errors='ignore')
                elif ext == ".css": css_content = file_obj.read().decode("utf-8", errors='ignore')
                elif ext == ".js": js_content = file_obj.read().decode("utf-8", errors='ignore')
        
        combined_html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>{project.name}</title><style>{css_content}</style></head><body>{html_content}<script type="module">{js_content}</script></body></html>"""
        
        project_folder_path = os.path.join(settings.MEDIA_ROOT, "projects", project.get_folder_name())
        os.makedirs(project_folder_path, exist_ok=True)
        combined_file_name = "combined.html"
        combined_file_server_path = os.path.join(project_folder_path, combined_file_name)
        with open(combined_file_server_path, "w", encoding="utf-8") as f:
            f.write(combined_html)
        relative_path_for_db = os.path.join("projects", project.get_folder_name(), combined_file_name)
        ProjectFile.objects.update_or_create(
            project=project, file__endswith=combined_file_name,
            defaults={'file': relative_path_for_db}
        )
        
        try: likeScoreCalculation(project.username)
        except Exception as e: logger.error(f"Error in likeScoreCalculation for {project.username} (opensource): {e}")
        
        serializer = ProjectSerializer(project)
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)