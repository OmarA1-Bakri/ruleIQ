"""

# Constants
DEFAULT_RETRIES = 5
MAX_RETRIES = 3


LangSmith Feedback Collection System
Enables human-in-the-loop feedback for continuous improvement
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class FeedbackType(Enum):
    """Types of feedback that can be collected."""

    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"
    RATING = "rating"
    CORRECTION = "correction"
    COMMENT = "comment"
    FLAG = "flag"


@dataclass
class FeedbackItem:
    """Individual feedback item."""

    run_id: str
    feedback_type: FeedbackType
    value: Any
    user_id: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "run_id": self.run_id,
            "feedback_type": self.feedback_type.value,
            "value": self.value,
            "user_id": self.user_id,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


class LangSmithFeedbackCollector:
    """Collect and manage feedback for LangSmith runs."""

    def __init__(self) -> None:
        self.feedback_queue: List[FeedbackItem] = []
        self.feedback_stats = {
            "total_collected": 0,
            "by_type": {ft.value: (0) for ft in FeedbackType},
            "by_user": {},
        }

    def collect_feedback(
        self,
        run_id: str,
        feedback_type: FeedbackType,
        value: Any,
        user_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FeedbackItem:
        """
        Collect feedback for a specific run.

        Args:
            run_id: LangSmith run ID
            feedback_type: Type of feedback
            value: Feedback value (depends on type)
            user_id: ID of user providing feedback
            metadata: Additional context

        Returns:
            FeedbackItem that was collected
        """
        if feedback_type == FeedbackType.RATING:
            if not isinstance(value, (int, float)) or value < 1 or value > DEFAULT_RETRIES:
                raise ValueError("Rating must be between 1 and 5")
        elif feedback_type in [FeedbackType.THUMBS_UP, FeedbackType.THUMBS_DOWN]:
            value = bool(value)
        elif feedback_type == FeedbackType.CORRECTION:
            if not isinstance(value, (str, dict)):
                raise ValueError("Correction must be string or dict")
        feedback = FeedbackItem(
            run_id=run_id,
            feedback_type=feedback_type,
            value=value,
            user_id=user_id,
            metadata=metadata or {},
        )
        self.feedback_queue.append(feedback)
        self.feedback_stats["total_collected"] += 1
        self.feedback_stats["by_type"][feedback_type.value] += 1
        self.feedback_stats["by_user"][user_id] = self.feedback_stats["by_user"].get(user_id, 0) + 1
        logger.info("Collected %s feedback for run %s" % (feedback_type.value, run_id))
        return feedback

    def batch_submit_to_langsmith(self, api_key: str, project_name: str) -> Dict[str, Any]:
        """
        Submit collected feedback to LangSmith.

        Args:
            api_key: LangSmith API key
            project_name: Project name in LangSmith

        Returns:
            Submission results
        """
        if not self.feedback_queue:
            return {"status": "no_feedback", "count": 0}
        try:
            from langsmith import Client

            client = Client(api_key=api_key)
            submitted_count = 0
            errors = []
            for feedback in self.feedback_queue:
                try:
                    if feedback.feedback_type == FeedbackType.THUMBS_UP:
                        client.create_feedback(
                            run_id=feedback.run_id,
                            key="thumbs",
                            score=1.0,
                            comment=feedback.metadata.get("comment", ""),
                        )
                    elif feedback.feedback_type == FeedbackType.THUMBS_DOWN:
                        client.create_feedback(
                            run_id=feedback.run_id,
                            key="thumbs",
                            score=0.0,
                            comment=feedback.metadata.get("comment", ""),
                        )
                    elif feedback.feedback_type == FeedbackType.RATING:
                        client.create_feedback(
                            run_id=feedback.run_id,
                            key="rating",
                            score=feedback.value / 5.0,
                            comment=feedback.metadata.get("comment", ""),
                        )
                    elif feedback.feedback_type == FeedbackType.CORRECTION:
                        client.create_feedback(
                            run_id=feedback.run_id,
                            key="correction",
                            correction=feedback.value,
                            comment="User-provided correction",
                        )
                    elif feedback.feedback_type == FeedbackType.COMMENT:
                        client.create_feedback(
                            run_id=feedback.run_id, key="comment", comment=feedback.value
                        )
                    elif feedback.feedback_type == FeedbackType.FLAG:
                        client.create_feedback(
                            run_id=feedback.run_id,
                            key="flag",
                            score=0.0,
                            comment=f"Flagged for review: {feedback.value}",
                        )
                    submitted_count += 1
                except Exception as e:
                    errors.append({"run_id": feedback.run_id, "error": str(e)})
                    logger.error("Failed to submit feedback for run %s: %s" % (feedback.run_id, e))
            if submitted_count > 0:
                self.feedback_queue = self.feedback_queue[submitted_count:]
            return {
                "status": "success",
                "submitted": submitted_count,
                "errors": errors,
                "remaining": len(self.feedback_queue),
            }
        except ImportError:
            logger.error("LangSmith client not installed")
            return {"status": "error", "message": "LangSmith client not available"}
        except Exception as e:
            logger.error("Failed to submit feedback batch: %s" % e)
            return {"status": "error", "message": str(e)}

    def get_feedback_summary(self) -> Dict[str, Any]:
        """Get summary of collected feedback."""
        return {
            "total_collected": self.feedback_stats["total_collected"],
            "pending_submission": len(self.feedback_queue),
            "by_type": self.feedback_stats["by_type"],
            "top_contributors": sorted(
                self.feedback_stats["by_user"].items(), key=lambda x: x[1], reverse=True
            )[:5],
        }

    def export_feedback(self, filepath: str) -> None:
        """Export feedback to JSON file for analysis."""
        export_data = {
            "export_date": datetime.now(timezone.utc).isoformat(),
            "statistics": self.get_feedback_summary(),
            "feedback_items": [f.to_dict() for f in self.feedback_queue],
        }
        with open(filepath, "w") as f:
            json.dump(export_data, f, indent=2)
        logger.info("Exported %s feedback items to %s" % (len(self.feedback_queue), filepath))


class FeedbackAnalyzer:
    """Analyze collected feedback to identify patterns and improvements."""

    @staticmethod
    def analyze_feedback_trends(feedback_items: List[FeedbackItem]) -> Dict[str, Any]:
        """
        Analyze feedback to identify trends.

        Args:
            feedback_items: List of feedback items

        Returns:
            Analysis results with trends and patterns
        """
        if not feedback_items:
            return {"status": "no_data"}
        analysis = {
            "total_feedback": len(feedback_items),
            "time_range": {
                "start": min(f.timestamp for f in feedback_items).isoformat(),
                "end": max(f.timestamp for f in feedback_items).isoformat(),
            },
            "sentiment": {"positive": 0, "negative": 0, "neutral": 0},
            "average_rating": None,
            "correction_rate": 0,
            "flag_rate": 0,
            "top_issues": [],
        }
        ratings = []
        for feedback in feedback_items:
            if feedback.feedback_type == FeedbackType.THUMBS_UP:
                analysis["sentiment"]["positive"] += 1
            elif feedback.feedback_type == FeedbackType.THUMBS_DOWN:
                analysis["sentiment"]["negative"] += 1
            elif feedback.feedback_type == FeedbackType.RATING:
                ratings.append(feedback.value)
                if feedback.value >= 4:
                    analysis["sentiment"]["positive"] += 1
                elif feedback.value <= 2:
                    analysis["sentiment"]["negative"] += 1
                else:
                    analysis["sentiment"]["neutral"] += 1
            if feedback.feedback_type == FeedbackType.CORRECTION:
                analysis["correction_rate"] += 1
            elif feedback.feedback_type == FeedbackType.FLAG:
                analysis["flag_rate"] += 1
        total = len(feedback_items)
        analysis["correction_rate"] = analysis["correction_rate"] / total * 100
        analysis["flag_rate"] = analysis["flag_rate"] / total * 100
        if ratings:
            analysis["average_rating"] = sum(ratings) / len(ratings)
        comments = [f.value for f in feedback_items if f.feedback_type == FeedbackType.COMMENT]
        if comments:
            from collections import Counter

            words = " ".join(comments).lower().split()
            common_words = Counter(words).most_common(10)
            analysis["top_issues"] = [word for word, count in common_words if count > 1]
        return analysis

    @staticmethod
    def generate_improvement_recommendations(analysis: Dict[str, Any]) -> List[str]:
        """
        Generate recommendations based on feedback analysis.

        Args:
            analysis: Analysis results from analyze_feedback_trends

        Returns:
            List of recommendations
        """
        recommendations = []
        if analysis.get("sentiment", {}).get("negative", 0) > analysis.get("sentiment", {}).get(
            "positive", 0
        ):
            recommendations.append(
                "High negative feedback detected. Review recent changes and error logs."
            )
        avg_rating = analysis.get("average_rating")
        if avg_rating and avg_rating < MAX_RETRIES:
            recommendations.append(
                f"Low average rating ({avg_rating:.1f}/5). Consider reviewing output quality."
            )
        correction_rate = analysis.get("correction_rate", 0)
        if correction_rate > 10:
            recommendations.append(
                f"High correction rate ({correction_rate:.1f}%). Consider retraining or adjusting prompts."
            )
        flag_rate = analysis.get("flag_rate", 0)
        if flag_rate > DEFAULT_RETRIES:
            recommendations.append(
                f"Multiple items flagged ({flag_rate:.1f}%). Manual review recommended."
            )
        if analysis.get("top_issues"):
            recommendations.append(
                f"Common issues mentioned: {', '.join(analysis['top_issues'][:3])}"
            )
        if not recommendations:
            recommendations.append("System performing well. Continue monitoring for trends.")
        return recommendations


feedback_collector = LangSmithFeedbackCollector()
