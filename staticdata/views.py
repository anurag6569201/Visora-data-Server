from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
import os
from django.core.files.base import ContentFile
from django.conf import settings
from django.views import View
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from .serializers import ProjectCommentSerializer, ProjectLikeSerializer,ProjectSerializer,ScoreSerializer,TheorySerializer
from .models import Project, ProjectFile,ProjectComment,ProjectLike,UserNameDb,Leaderboard,Theory
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json
from django.conf import settings
from rest_framework.permissions import BasePermission
from rest_framework.decorators import api_view
from rest_framework import generics, permissions
from rest_framework import serializers, viewsets, pagination, filters



from staticdata.score_calculations import likeScoreCalculation

class UploadProjectAPIView(APIView):
    def post(self, request):

        name = request.data.get("project_name")
        tabname = request.data.get("project_tab_name")
        gradename = request.data.get("project_grade_name")
        subjectname = request.data.get("project_subject_name")
        description = request.data.get("project_description")
        token = request.data.get("token")
        username = request.data.get("username")
        email = request.data.get("email")
        files = request.FILES.getlist("files")

        if not all([name, description, token]) or not files:
            return Response({"error": "Missing required fields"}, status=status.HTTP_400_BAD_REQUEST)
        # Create or get the project
        project, created = Project.objects.get_or_create(name=name, description=description, token=token,email=email,username=username,tabname=tabname,gradename=gradename,subjectname=subjectname)
        html_content, css_content, js_content = "", "", ""

        for file in files:
            ext = os.path.splitext(file.name)[1].lower()

            if ext == ".html":
                html_content = file.read().decode("utf-8")
            elif ext == ".css":
                css_content = file.read().decode("utf-8")
            elif ext == ".js":
                js_content = file.read().decode("utf-8")

        # Generate the combined HTML file
        combined_html = f"""
        <html>
          <head>
            <style>{css_content}</style>
          </head>
          <body>
            {html_content}
            <script>{js_content}</script>
          </body>
        </html>
        """

        # Save the combined file to the server
        combined_file_path = os.path.join("projects", project.get_folder_name(), "combined.html")
        ProjectFile.objects.create(project=project, file=ContentFile(combined_html.encode("utf-8"), name="combined.html"))
        likeScoreCalculation(project.username)

        return Response({"message": "Project uploaded successfully"}, status=status.HTTP_201_CREATED)



class OpenSourceUploadProjectAPIView(APIView):
    def post(self, request):

        name = request.data.get("project_name")
        tabname = request.data.get("project_tab_name")
        gradename = request.data.get("project_grade_name")
        subjectname = request.data.get("project_subject_name")
        description = request.data.get("project_description")
        token = request.data.get("token")
        username = request.data.get("username")
        email = request.data.get("email")
        files = request.FILES.getlist("files")

        if not all([name, description, token]) or not files:
            return Response({"error": "Missing required fields"}, status=status.HTTP_400_BAD_REQUEST)
        # Create or get the project
        project, created = Project.objects.get_or_create(name=name, description=description, token=token,email=email,username=username,tabname=tabname,gradename=gradename,subjectname=subjectname)
        html_content, css_content, js_content = "", "", ""

        for file in files:
            ext = os.path.splitext(file.name)[1].lower()

            if ext == ".html":
                html_content = file.read().decode("utf-8")
            elif ext == ".css":
                css_content = file.read().decode("utf-8")
            elif ext == ".js":
                js_content = file.read().decode("utf-8")

        # Generate the combined HTML file
        combined_html = f"""
        <html>
          <head>
            <style>{css_content}</style>
          </head>
          <body>
            {html_content}
            <script>{js_content}</script>
          </body>
        </html>
        """

        # Save the combined file to the server
        combined_file_path = os.path.join("projects", project.get_folder_name(), "combined.html")
        ProjectFile.objects.create(project=project, file=ContentFile(combined_html.encode("utf-8"), name="combined.html"))
        likeScoreCalculation(project.username)

        return Response({"message": "Project uploaded successfully"}, status=status.HTTP_201_CREATED)


def list_projects(request):

    auth_header = request.headers.get("Authorization")
    if auth_header:
        projects = Project.objects.filter(username=auth_header)
        projects_data = []
        for project in projects:
            user = UserNameDb.objects.filter(username=project.username).first()
            folder_path = os.path.join(settings.MEDIA_ROOT, "projects", project.get_folder_name())
            combined_file_path = os.path.join(folder_path, "combined.html")

            if os.path.exists(combined_file_path):
                try:
                    with open(combined_file_path, "r", encoding="utf-8") as f:
                        combined_html = f.read()
                except Exception as e:
                    print(f"Error reading combined.html: {e}")
                    combined_html = ""
            else:
                combined_html = ""

            projects_data.append({
                "id": project.id,
                "name": project.name,
                "username": user.username,
                "profile_picture": user.profile_picture,
                "userid": user.userid,
                "combined_html": combined_html,  
            })
    else:
        selected_tab = request.GET.get('selectedTab', None)
        grade = request.GET.get('grade', None)
        subject = request.GET.get('subject', None)
        projects = Project.objects.filter(tabname=selected_tab,gradename=grade,subjectname=subject)
        projects_data = []
        for project in projects:
            user = UserNameDb.objects.filter(username=project.username).first()
            folder_path = os.path.join(settings.MEDIA_ROOT, "projects", project.get_folder_name())
            combined_file_path = os.path.join(folder_path, "combined.html")

            if os.path.exists(combined_file_path):
                try:
                    with open(combined_file_path, "r", encoding="utf-8") as f:
                        combined_html = f.read()
                except Exception as e:
                    print(f"Error reading combined.html: {e}")
                    combined_html = ""
            else:
                combined_html = ""

            projects_data.append({
                "id": project.id,
                "name": project.name,
                "username": user.username,
                "profile_picture": user.profile_picture,
                "userid": user.userid,
                "combined_html": combined_html,  
            })

    return JsonResponse({"projects": projects_data})


@api_view(['GET'])
def get_project(request, id):
    try:
        project = Project.objects.get(id=id)  # Django will now match the UUID correctly
        serializer = ProjectSerializer(project)
        return Response(serializer.data)  # DRF handles JSON serialization
    except Project.DoesNotExist:
        return Response({"error": "Project not found"}, status=404)
    except ValueError:
        return Response({"error": "Invalid UUID format"}, status=400)
    
    
class CommentCreateView(APIView):
    serializer_class = ProjectCommentSerializer
    permission_classes = [permissions.AllowAny]

    def get(self, request, project_id):
        """Fetch all comments for a specific project"""
        project = get_object_or_404(Project, id=project_id)
        comments = ProjectComment.objects.filter(project=project).order_by("-created_at")
        serializer = self.serializer_class(comments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, project_id):
        """Create a new comment for a project"""
        token = request.headers.get("Authorization")
        print("comment Token received:", token)
        if not token:
            return JsonResponse({"error": "Unauthorized"}, status=401)

        user = UserNameDb.objects.filter(username=token).first()
        if not user:
            return JsonResponse({"error": "User not found"}, status=404)

        project = get_object_or_404(Project, id=project_id)
        serializer = self.serializer_class(data=request.data)

        if serializer.is_valid():
            serializer.save(username=user, project=project)  # Save user instance
            likeScoreCalculation(project.username)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)




@method_decorator(csrf_exempt, name='dispatch')
class LikeToggleView(View):
    def get(self, request, project_id):
        """Return the like count and whether the user has liked the project"""
        token = request.headers.get("Authorization")
        print("Token received:", token)

        if not token:
            return JsonResponse({"error": "Unauthorized"}, status=401)

        user = UserNameDb.objects.filter(username=token).first()
        if not user:
            return JsonResponse({"error": "User not found"}, status=404)

        if not user:
            return JsonResponse({"error": "User not found"}, status=404)
        project = get_object_or_404(Project, id=project_id)
        total_likes = ProjectLike.objects.filter(project=project).count()
        is_liked = ProjectLike.objects.filter(username=user, project=project).exists()

        return JsonResponse({"total_likes": total_likes, "is_liked": is_liked})

    def post(self, request, project_id):
        """Toggle like status using get_or_create"""
        token = request.headers.get("Authorization")

        if not token:
            return JsonResponse({"error": "Unauthorized"}, status=401)

        user = UserNameDb.objects.filter(username=token).first()
        if not user:
            return JsonResponse({"error": "User not found"}, status=404)

        project = get_object_or_404(Project, id=project_id)
        like, created = ProjectLike.objects.get_or_create(username=user, project=project)

        if not created:
            like.delete()
            liked = False
        else:
            liked = True

        total_likes = ProjectLike.objects.filter(project=project).count()
        likeScoreCalculation(project.username)
        return JsonResponse({"liked": liked, "likes_count": total_likes})
    

@method_decorator(csrf_exempt, name='dispatch')
class RegisterUserNameDbView(View):
    def post(self, request):
        try:
            data = json.loads(request.body.decode("utf-8"))  # Corrected
            username = data.get("username")
            profile_picture = data.get("profile_picture")
            userid = data.get("userid")
            role = data.get("role")
            email = data.get("email")

            if UserNameDb.objects.filter(username=username).exists():
                return JsonResponse({"error": "User already exists in Visiora-Data."}, status=400)

            user = UserNameDb.objects.create(username=username, email=email,profile_picture=profile_picture,userid=userid,role=role)
            user_instance = UserNameDb.objects.get(username=username)
            leaderboard_entry, _ = Leaderboard.objects.get_or_create(user=user_instance)

            user.save()

            return JsonResponse({"message": "User created in Visiora-Data."}, status=201)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format"}, status=400)
        
import uuid
from rest_framework import viewsets
from .models import Quiz
from .serializers import QuizSerializer
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

# ViewSet
class ScoreViewSet(viewsets.ModelViewSet):
    queryset = Leaderboard.objects.all().order_by('-score')
    serializer_class = ScoreSerializer
    pagination_class = ScorePagination
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['score', 'updated_at']


@api_view(['POST'])
def generate_ai_content(request, project_id, content_type):
    # Implement your AI generation logic here
    # This could connect to OpenAI API or your custom model
    return Response({'status': 'AI generation endpoint', 'project_id': project_id, 'type': content_type})



@api_view(['POST'])
def generate_ai_content(request, project_id, content_type):
    try:
        project = Project.objects.get(id=project_id)
        # Implement actual AI generation here using OpenAI or other services
        # Example pseudo-code:
        """
        prompt = f"Generate {content_type} for project: {project.name}\n{project.description}"
        response = openai.Completion.create(
            engine="text-davinci-003",
            prompt=prompt,
            max_tokens=1000
        )
        
        # Save to appropriate model
        if content_type == 'quiz':
            Quiz.objects.create(
                project=project,
                data=format_quiz_data(response.choices[0].text)
            )
        """
        return Response({'status': 'success', 'generated': content_type})
    except Exception as e:
        return Response({'error': str(e)}, status=500)
    



from .models import Category
from .serializers import CategorySerializer
from collections import defaultdict

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
            return []
        return {child.name: self.build_category_structure(child) for child in children}
    







from django.db.models import Q
from rest_framework import generics, permissions, status # Added permissions, status
from rest_framework.response import Response
# from .models import Project, Quiz, Theory, Examples # Import your models
# from .serializers import ProjectSerializer, QuizSerializer, TheorySerializer, ExamplesSerializer # Import your serializers

from django.db.models import Q
from .models import Project, Quiz, Theory, Examples
from .serializers import ProjectSerializer, QuizSerializer, TheorySerializer, ExamplesSerializer

from rest_framework.pagination import PageNumberPagination

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10 # Number of items per page
    page_size_query_param = 'page_size' # Allow client to override page size
    max_page_size = 50 # Maximum page size allowed

class ProjectSearchView(generics.ListAPIView):
    """
    Searches projects by name or description. Supports pagination.
    """
    serializer_class = ProjectSerializer
    permission_classes = [permissions.AllowAny] # Or IsAuthenticated if login required
    pagination_class = StandardResultsSetPagination # Enable pagination

    def get_queryset(self):
        query = self.request.query_params.get('query', '').strip()
        if query:
            # Ensure related data isn't fetched unnecessarily for list view
            # Use select_related/prefetch_related here ONLY if serializer needs related fields
            return Project.objects.filter(
                Q(name__icontains=query) |
                Q(description__icontains=query)
            ).order_by('name') # Add ordering
        return Project.objects.none() # Return empty if no query

# --- Project Detail View ---
class ProjectDetailView(generics.RetrieveAPIView):
    """
    Retrieves details for a single project.
    """
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [permissions.AllowAny] # Or IsAuthenticated
    lookup_field = 'id' # Use 'id' or 'pk' based on your URL config

    # Optional: Prefetch related materials if they were part of the ProjectSerializer
    # def get_queryset(self):
    #     return super().get_queryset().prefetch_related('quizzes', 'theories', 'examples')


# --- View for Fetching Specific Material Types for a Project ---
class ProjectMaterialsView(generics.ListAPIView):
    """
    Retrieves materials (quizzes, theories, examples) for a specific project.
    Specify material type via query parameter `type`.
    Example: /api/projects/{project_id}/materials/?type=quizzes
    """
    permission_classes = [permissions.AllowAny] # Or IsAuthenticated

    # Map query param values to models and serializers
    material_map = {
        'quizzes': {'model': Quiz, 'serializer': QuizSerializer},
        'theories': {'model': Theory, 'serializer': TheorySerializer},
        'examples': {'model': Examples, 'serializer': ExamplesSerializer},
    }

    def get_serializer_class(self):
        material_type = self.request.query_params.get('type', None)
        map_entry = self.material_map.get(material_type)
        if map_entry:
            return map_entry['serializer']
        # Return a default or raise an error if type is missing/invalid
        return None # Or raise appropriate DRF exception

    def get_queryset(self):
        project_id = self.kwargs.get('project_id')
        material_type = self.request.query_params.get('type', None)
        map_entry = self.material_map.get(material_type)

        if not project_id or not map_entry:
            return self.material_map['quizzes']['model'].objects.none() # Return empty queryset

        model = map_entry['model']
        # Efficiently filter by the foreign key
        return model.objects.filter(project__id=project_id)

    def list(self, request, *args, **kwargs):
        material_type = request.query_params.get('type', None)
        project_id = kwargs.get('project_id')

        if not project_id:
             return Response({'error': 'Project ID not provided in URL.'}, status=status.HTTP_400_BAD_REQUEST)

        if not self.material_map.get(material_type):
            return Response(
                {'error': f'Invalid material type specified. Valid types are: {", ".join(self.material_map.keys())}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Proceed with standard list behavior (get_queryset, get_serializer_class, pagination)
        return super().list(request, *args, **kwargs)






# sessions_api/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated # Ensure user is logged in
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import date, timedelta
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied

from .models import UserSessionData
from .serializers import UserSessionDataSerializer
import logging # Import logging

logger = logging.getLogger(__name__) # Setup logger

from .models import UserSessionData
from .serializers import UserSessionDataSerializer

def get_anonymous_id_from_request(request):
    """Extracts and validates the Anonymous User ID from request headers."""
    anon_id_str = request.headers.get('X-Anonymous-User-ID')
    if not anon_id_str:
        logger.warning("Missing X-Anonymous-User-ID header")
        # Returning None will likely cause a 403/400 later, which is intended.
        # Or raise PermissionDenied("Anonymous user ID header is required.")
        return None
    try:
        return uuid.UUID(anon_id_str)
    except ValueError:
        logger.warning(f"Invalid UUID format for X-Anonymous-User-ID: {anon_id_str}")
        # raise serializers.ValidationError("Invalid Anonymous User ID format.")
        return None

# Default data structure for new/missing sessions
def get_default_session_data():
     return {
         'id': None, # No ID for a default structure
         'anonymous_user_id': None, # Will be set if created
         'name': '',
         'version': '5.5-html', 'topic': '', 'prerequisites': '', 'duration': '1',
         'difficulty': 'Intermediate', 'theme_mode': 'dark', 'font_size_factor': 1.0,
         'high_contrast': False, 'reduce_animations': False, 'subtopics': [], 'plan_data': {},
         'review_schedule': {}, 'plan_analysis': None, 'user_points': 0, 'study_streak': 0,
         'earned_badges': [], 'last_study_date': None,
         'chat_history': [{'sender': 'bot', 'text': 'Hi! How can I help?'}],
         'journal_prompts': {}, 'selected_subtopic_id': None,
         'created_at': None, 'updated_at': None
     }


class UserSessionViewSet(viewsets.ViewSet):
    """
    API ViewSet to manage user sessions (identified by an anonymous ID).

    Requires 'X-Anonymous-User-ID' header containing a valid UUID.
    """
    serializer_class = UserSessionDataSerializer # Used by Browsable API etc.

    def get_queryset(self, request):
        """Filters queryset based on anonymous ID."""
        anonymous_user_id = get_anonymous_id_from_request(request)
        if not anonymous_user_id:
            # Return empty queryset if ID is missing/invalid
            # Or raise PermissionDenied here
             raise PermissionDenied("Valid X-Anonymous-User-ID header required.")
        return UserSessionData.objects.filter(anonymous_user_id=anonymous_user_id)

    @action(detail=False, methods=['get'], url_path='latest')
    def latest(self, request):
        """
        Load the most recently updated session data for the anonymous user.
        Includes server-side streak check.
        """
        print("latest function get called")
        anonymous_user_id = get_anonymous_id_from_request(request)
        if not anonymous_user_id:
             return Response({"detail": "Valid X-Anonymous-User-ID header required."}, status=status.HTTP_403_FORBIDDEN)

        try:
            queryset = self.get_queryset(request)
            session_data = queryset.order_by('updated_at').first() # Get the latest

            if not session_data:
                logger.info(f"No session data found for anon_id {str(anonymous_user_id)[:8]}. Returning defaults.")
                return Response(get_default_session_data(), status=status.HTTP_200_OK) # Return defaults, not 404

            # --- Server-side Streak Logic on Load ---
            today = date.today()
            reset_streak = False
            if session_data.last_study_date:
                yesterday = today - timedelta(days=1)
                if session_data.last_study_date < yesterday:
                    session_data.study_streak = 0
                    reset_streak = True
                    # Save the reset streak immediately? Usually not necessary on GET.
                    # session_data.save(update_fields=['study_streak'])
            elif session_data.study_streak != 0: # No date but streak > 0? Reset.
                session_data.study_streak = 0
                reset_streak = True

            serializer = UserSessionDataSerializer(session_data)
            logger.info(f"Loaded latest session (ID: {session_data.pk}) for anon_id {str(anonymous_user_id)[:8]}. Streak reset on load: {reset_streak}")
            return Response(serializer.data, status=status.HTTP_200_OK)

        except PermissionDenied as e:
             return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
             logger.error(f"Error loading latest session for anon_id {str(anonymous_user_id)[:8]}: {e}", exc_info=True)
             return Response({"detail": "An error occurred while loading session data."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def create(self, request):
        """
        Create a new session data record for the anonymous user.
        POST /api/user-sessions/
        """
        anonymous_user_id = get_anonymous_id_from_request(request)
        if not anonymous_user_id:
             return Response({"detail": "Valid X-Anonymous-User-ID header required."}, status=status.HTTP_403_FORBIDDEN)

        request_data = request.data.copy()

        # --- Server-side Streak Logic on Create/Save ---
        request_data['last_study_date'] = date.today().isoformat()
        # Frontend should send its calculated streak value. We trust it for now, but store the date.
        logger.info(f"Creating session for anon_id {str(anonymous_user_id)[:8]}. Frontend streak: {request_data.get('study_streak')}, setting last_study_date to {request_data['last_study_date']}")
        # --- End Streak Logic ---

        # Add anonymous ID and potentially default name if missing
        request_data['anonymous_user_id'] = anonymous_user_id
        if 'name' not in request_data or not request_data['name']:
             request_data['name'] = f"Session - {request_data.get('topic', 'Untitled')[:50]}"

        serializer = UserSessionDataSerializer(data=request_data)
        try:
            serializer.is_valid(raise_exception=True)
            # We need to explicitly pass the anonymous_user_id when saving
            # Note: serializer.save() doesn't automatically pick up fields not in initial `data` if they are not relationships
            # So we add it to the validated data before saving
            serializer.validated_data['anonymous_user_id'] = anonymous_user_id
            session_instance = serializer.save() # This now creates the record

            logger.info(f"Session (ID: {session_instance.pk}) created for anon_id {str(anonymous_user_id)[:8]}.")
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except serializers.ValidationError as e:
            logger.warning(f"Validation error creating session for anon_id {str(anonymous_user_id)[:8]}: {e.detail}")
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied as e:
             return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            logger.error(f"Error creating session for anon_id {str(anonymous_user_id)[:8]}: {e}", exc_info=True)
            return Response({"detail": "An error occurred while saving session data."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    def update(self, request, pk=None):
        """
        Update an existing session data record by its Primary Key (pk).
        PUT /api/user-sessions/{pk}/
        """
        anonymous_user_id = get_anonymous_id_from_request(request)
        if not anonymous_user_id:
             return Response({"detail": "Valid X-Anonymous-User-ID header required."}, status=status.HTTP_403_FORBIDDEN)

        try:
            # Ensure the session exists and belongs to the anonymous user
            queryset = self.get_queryset(request)
            session_instance = queryset.get(pk=pk) # Raises DoesNotExist if not found for this user

        except UserSessionData.DoesNotExist:
            logger.warning(f"Session update failed: Session ID {pk} not found for anon_id {str(anonymous_user_id)[:8]}.")
            raise NotFound(detail=f"Session with ID {pk} not found for this user.")
        except PermissionDenied as e:
             return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)


        request_data = request.data.copy()
        # --- Server-side Streak Logic on Create/Save ---
        request_data['last_study_date'] = date.today().isoformat()
        logger.info(f"Updating session (ID: {pk}) for anon_id {str(anonymous_user_id)[:8]}. Frontend streak: {request_data.get('study_streak')}, setting last_study_date to {request_data['last_study_date']}")
        # --- End Streak Logic ---

        # Ensure name is present if topic changes? Optional refinement.
        if 'name' not in request_data or not request_data['name']:
             request_data['name'] = f"Session - {request_data.get('topic', session_instance.topic)[:50]}"


        # Use partial=True for PUT to allow partial updates if desired,
        # though PUT typically implies replacing the whole resource (or the updatable fields).
        # If you want strict "replace", set partial=False. Let's use partial=True for flexibility.
        serializer = UserSessionDataSerializer(session_instance, data=request_data, partial=True)
        try:
            serializer.is_valid(raise_exception=True)
            # anonymous_user_id is validated by the queryset lookup, no need to set it again
            serializer.save()

            logger.info(f"Session (ID: {pk}) updated for anon_id {str(anonymous_user_id)[:8]}.")
            return Response(serializer.data, status=status.HTTP_200_OK)

        except serializers.ValidationError as e:
            logger.warning(f"Validation error updating session {pk} for anon_id {str(anonymous_user_id)[:8]}: {e.detail}")
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error updating session {pk} for anon_id {str(anonymous_user_id)[:8]}: {e}", exc_info=True)
            return Response({"detail": "An error occurred while saving session data."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Optional: Add retrieve and list methods if needed for session selection UI

    def retrieve(self, request, pk=None):
        """
        Retrieve a specific session by its Primary Key (pk).
        GET /api/user-sessions/{pk}/
        """
        anonymous_user_id = get_anonymous_id_from_request(request)
        if not anonymous_user_id:
             return Response({"detail": "Valid X-Anonymous-User-ID header required."}, status=status.HTTP_403_FORBIDDEN)

        try:
            queryset = self.get_queryset(request)
            session_instance = queryset.get(pk=pk) # Raises DoesNotExist if not found for user
            # Perform streak check on load here too, if desired (consistency)
            # ... (streak check logic similar to 'latest') ...
            serializer = UserSessionDataSerializer(session_instance)
            logger.info(f"Retrieved session (ID: {pk}) for anon_id {str(anonymous_user_id)[:8]}.")
            return Response(serializer.data)

        except UserSessionData.DoesNotExist:
             logger.warning(f"Session retrieve failed: Session ID {pk} not found for anon_id {str(anonymous_user_id)[:8]}.")
             raise NotFound(detail=f"Session with ID {pk} not found for this user.")
        except PermissionDenied as e:
             return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
             logger.error(f"Error retrieving session {pk} for anon_id {str(anonymous_user_id)[:8]}: {e}", exc_info=True)
             return Response({"detail": "An error occurred retrieving session data."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    def list(self, request):
        """
        List all sessions for the anonymous user.
        GET /api/user-sessions/
        """
        anonymous_user_id = get_anonymous_id_from_request(request)
        if not anonymous_user_id:
             return Response({"detail": "Valid X-Anonymous-User-ID header required."}, status=status.HTTP_403_FORBIDDEN)

        try:
            queryset = self.get_queryset(request).order_by('-updated_at') # Latest first
            # Optional: Paginate if the list can grow large
            # from rest_framework.pagination import PageNumberPagination
            # paginator = PageNumberPagination()
            # page = paginator.paginate_queryset(queryset, request, view=self)
            # if page is not None:
            #     serializer = self.get_serializer(page, many=True)
            #     return paginator.get_paginated_response(serializer.data)

            serializer = UserSessionDataSerializer(queryset, many=True)
            logger.info(f"Listed {queryset.count()} sessions for anon_id {str(anonymous_user_id)[:8]}.")
            return Response(serializer.data)

        except PermissionDenied as e:
             return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
             logger.error(f"Error listing sessions for anon_id {str(anonymous_user_id)[:8]}: {e}", exc_info=True)
             return Response({"detail": "An error occurred listing sessions."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

