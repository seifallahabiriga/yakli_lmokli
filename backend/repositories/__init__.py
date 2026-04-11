from backend.repositories.base_repository import BaseRepository
from backend.repositories.cluster_repository import ClusterRepository
from backend.repositories.notification_repository import NotificationRepository
from backend.repositories.opportunity_repository import OpportunityRepository
from backend.repositories.recommendation_repository import RecommendationRepository
from backend.repositories.user_repository import UserRepository

__all__ = [
    "BaseRepository",
    "UserRepository",
    "OpportunityRepository",
    "ClusterRepository",
    "RecommendationRepository",
    "NotificationRepository",
]