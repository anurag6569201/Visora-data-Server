from datetime import timedelta
from django.utils.timezone import now
from staticdata.models import Project, Leaderboard, UserNameDb

def likeScoreCalculation(user_name):
    """
    Function to calculate and update the leaderboard score.
    - 5 points for liking a project
    - 7 points for commenting on a project
    - 10 point per project
    """
    # Fetch or create leaderboard entry
    user_instance = UserNameDb.objects.get(username=user_name)
    leaderboard_entry, _ = Leaderboard.objects.get_or_create(user=user_instance)

    # Check if it's time to recalculate the score
    if leaderboard_entry.check_time_gap():
        projects = Project.objects.filter(username=user_name)

        # Initialize score variables
        like_score = 0
        comment_score = 0
        project_score = 0

        for prj in projects:
            like_score += prj.total_likes() * 5
            comment_score += prj.total_comments() * 7
            project_score += 10  # Each project contributes 1 point

        # Calculate total score
        total_score = like_score + comment_score + project_score

        # Update the leaderboard score
        leaderboard_entry.score = total_score
        leaderboard_entry.save()

        print(f"The total score of user {user_name} is: {total_score}")
