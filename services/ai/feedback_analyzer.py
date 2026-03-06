"""Feedback analysis and aggregation module for the feedback system."""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict
from dataclasses import dataclass, field
import statistics

from config.langsmith_feedback import FeedbackItem, FeedbackType


@dataclass
class AggregationResult:
    """Result of feedback aggregation."""

    metric: str
    value: float
    count: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UserPattern:
    """User feedback pattern analysis."""

    user_id: str
    total_feedback: int
    average_rating: Optional[float]
    dominant_sentiment: Optional[str] = None
    feedback_frequency: float = 0.0  # feedbacks per day
    correction_rate: float = 0.0  # percentage of corrections


@dataclass
class QualityScore:
    """Quality score with dimensional breakdown."""

    overall: float
    dimensions: Dict[str, float] = field(default_factory=dict)
    confidence: float = 0.0
    sample_size: int = 0


@dataclass
class ResponseFeedback:
    """Response feedback for a specific AI response."""

    response_id: str
    feedback_type: FeedbackType
    value: Any
    timestamp: datetime
    user_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class FeedbackAnalyzer:
    """Analyzer for feedback aggregation and pattern detection."""

    def __init__(self) -> None:
        """Initialize the feedback analyzer."""
        self.feedback_items: List[FeedbackItem] = []
        self.feedback_by_run: Dict[str, List[FeedbackItem]] = defaultdict(list)
        self.feedback_by_user: Dict[str, List[FeedbackItem]] = defaultdict(list)

    def add_feedback(self, feedback: FeedbackItem) -> None:
        """Add a feedback item to the analyzer.

        Args:
            feedback: The feedback item to add
        """
        self.feedback_items.append(feedback)
        self.feedback_by_run[feedback.run_id].append(feedback)
        self.feedback_by_user[feedback.user_id].append(feedback)

    def aggregate_ratings(self) -> AggregationResult:
        """Aggregate rating feedback.

        Returns:
            AggregationResult with average rating and count
        """
        ratings = [
            f.value
            for f in self.feedback_items
            if f.feedback_type == FeedbackType.RATING and isinstance(f.value, (int, float))
        ]

        if not ratings:
            return AggregationResult(
                metric="average_rating",
                value=0.0,
                count=0,
                metadata={"min": 0, "max": 0, "std_dev": 0},
            )

        return AggregationResult(
            metric="average_rating",
            value=statistics.mean(ratings),
            count=len(ratings),
            metadata={
                "min": min(ratings),
                "max": max(ratings),
                "std_dev": statistics.stdev(ratings) if len(ratings) > 1 else 0,
            },
        )

    def get_sentiment_breakdown(self) -> Dict[str, int]:
        """Get breakdown of sentiment feedback.

        Returns:
            Dictionary with counts of positive, negative, and neutral sentiment
        """
        sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0}

        for feedback in self.feedback_items:
            if feedback.feedback_type == FeedbackType.THUMBS_UP:
                sentiment_counts["positive"] += 1
            elif feedback.feedback_type == FeedbackType.THUMBS_DOWN:
                sentiment_counts["negative"] += 1
            elif feedback.feedback_type == FeedbackType.COMMENT:
                # Simple sentiment analysis based on keywords
                comment = str(feedback.value).lower()
                if any(
                    word in comment for word in ["good", "great", "excellent", "love", "perfect"]
                ):
                    sentiment_counts["positive"] += 1
                elif any(word in comment for word in ["bad", "poor", "terrible", "hate", "awful"]):
                    sentiment_counts["negative"] += 1
                else:
                    sentiment_counts["neutral"] += 1

        return sentiment_counts

    def aggregate_by_time_window(self, window_hours: int = 24) -> List[AggregationResult]:
        """Aggregate feedback by time windows.

        Args:
            window_hours: Size of time window in hours

        Returns:
            List of aggregation results for each time window
        """
        if not self.feedback_items:
            return []

        # Sort feedback by timestamp
        sorted_feedback = sorted(self.feedback_items, key=lambda x: x.timestamp)

        # Group by time windows
        windows = []
        current_window_start = sorted_feedback[0].timestamp
        current_window = []

        for feedback in sorted_feedback:
            if feedback.timestamp < current_window_start + timedelta(hours=window_hours):
                current_window.append(feedback)
            else:
                # Process current window
                if current_window:
                    ratings = [
                        f.value
                        for f in current_window
                        if f.feedback_type == FeedbackType.RATING
                        and isinstance(f.value, (int, float))
                    ]

                    windows.append(
                        AggregationResult(
                            metric=f"window_{current_window_start.isoformat()}",
                            value=statistics.mean(ratings) if ratings else 0,
                            count=len(current_window),
                            metadata={
                                "start": current_window_start.isoformat(),
                                "end": (
                                    current_window_start + timedelta(hours=window_hours)
                                ).isoformat(),
                                "feedback_types": self._count_feedback_types(
                                    current_window,
                                ),
                            },
                        ),
                    )

                # Start new window
                current_window_start = feedback.timestamp
                current_window = [feedback]

        # Process last window
        if current_window:
            ratings = [
                f.value
                for f in current_window
                if f.feedback_type == FeedbackType.RATING and isinstance(f.value, (int, float))
            ]

            windows.append(
                AggregationResult(
                    metric=f"window_{current_window_start.isoformat()}",
                    value=statistics.mean(ratings) if ratings else 0,
                    count=len(current_window),
                    metadata={
                        "start": current_window_start.isoformat(),
                        "end": (current_window_start + timedelta(hours=window_hours)).isoformat(),
                        "feedback_types": self._count_feedback_types(current_window),
                    },
                ),
            )

        return windows

    def analyze_user_patterns(self) -> List[UserPattern]:
        """Analyze feedback patterns by user.

        Returns:
            List of user patterns
        """
        patterns = []

        for user_id, user_feedback in self.feedback_by_user.items():
            if not user_feedback:
                continue

            # Calculate metrics
            ratings = [
                f.value
                for f in user_feedback
                if f.feedback_type == FeedbackType.RATING and isinstance(f.value, (int, float))
            ]

            corrections = [f for f in user_feedback if f.feedback_type == FeedbackType.CORRECTION]

            # Calculate time span
            timestamps = [f.timestamp for f in user_feedback]
            time_span = (max(timestamps) - min(timestamps)).days or 1

            # Determine dominant sentiment
            sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0}
            for f in user_feedback:
                if f.feedback_type == FeedbackType.THUMBS_UP:
                    sentiment_counts["positive"] += 1
                elif f.feedback_type == FeedbackType.THUMBS_DOWN:
                    sentiment_counts["negative"] += 1
                else:
                    sentiment_counts["neutral"] += 1

            dominant_sentiment = max(sentiment_counts, key=sentiment_counts.get)

            patterns.append(
                UserPattern(
                    user_id=user_id,
                    total_feedback=len(user_feedback),
                    average_rating=statistics.mean(ratings) if ratings else None,
                    dominant_sentiment=dominant_sentiment,
                    feedback_frequency=len(user_feedback) / time_span,
                    correction_rate=len(corrections) / len(user_feedback) * 100,
                ),
            )

        return patterns

    def get_feedback_summary(self) -> Dict[str, Any]:
        """Get a comprehensive summary of all feedback.

        Returns:
            Dictionary with summary statistics
        """
        rating_agg = self.aggregate_ratings()
        sentiment_breakdown = self.get_sentiment_breakdown()
        user_patterns = self.analyze_user_patterns()

        return {
            "total_feedback": len(self.feedback_items),
            "unique_users": len(self.feedback_by_user),
            "unique_runs": len(self.feedback_by_run),
            "average_rating": rating_agg.value,
            "rating_count": rating_agg.count,
            "sentiment": sentiment_breakdown,
            "active_users": len([p for p in user_patterns if p.feedback_frequency > 1]),
            "high_correction_users": len([p for p in user_patterns if p.correction_rate > 20]),
            "feedback_types": self._count_feedback_types(self.feedback_items),
        }

    def _count_feedback_types(self, feedback_items: List[FeedbackItem]) -> Dict[str, int]:
        """Count feedback by type.

        Args:
            feedback_items: List of feedback items to count

        Returns:
            Dictionary with counts by feedback type
        """
        counts = defaultdict(int)
        for item in feedback_items:
            counts[item.feedback_type.value] += 1
        return dict(counts)

    def check_fine_tuning_triggers(self) -> Dict[str, bool]:
        """Check if fine-tuning triggers are met.

        Returns:
            Dictionary of trigger conditions and whether they're met
        """
        triggers = {
            "high_correction_rate": False,
            "low_average_rating": False,
            "high_negative_sentiment": False,
            "composite_trigger": False,
        }

        # Check correction rate (>20% corrections)
        corrections = len(
            [f for f in self.feedback_items if f.feedback_type == FeedbackType.CORRECTION]
        )
        if self.feedback_items:
            correction_rate = corrections / len(self.feedback_items)
            triggers["high_correction_rate"] = correction_rate > 0.2

        # Check average rating (<3.0)
        rating_agg = self.aggregate_ratings()
        if rating_agg.count > 0:
            triggers["low_average_rating"] = rating_agg.value < 3.0

        # Check negative sentiment (>40% negative)
        sentiment = self.get_sentiment_breakdown()
        total_sentiment = sum(sentiment.values())
        if total_sentiment > 0:
            negative_rate = sentiment["negative"] / total_sentiment
            triggers["high_negative_sentiment"] = negative_rate > 0.4

        # Composite trigger (2 or more conditions met)
        conditions_met = sum(
            [
                triggers["high_correction_rate"],
                triggers["low_average_rating"],
                triggers["high_negative_sentiment"],
            ],
        )
        triggers["composite_trigger"] = conditions_met >= 2

        return triggers

    def calculate_statistics(self) -> Dict[str, Any]:
        """Calculate comprehensive statistics for all feedback.

        Returns:
            Dictionary with statistical metrics
        """
        rating_agg = self.aggregate_ratings()
        sentiment = self.get_sentiment_breakdown()

        # Calculate rating distribution
        ratings = [
            f.value
            for f in self.feedback_items
            if f.feedback_type == FeedbackType.RATING and isinstance(f.value, (int, float))
        ]

        # Count each type of feedback
        rating_distribution = {
            "rating": len(ratings),
            "thumbs_up": len(
                [f for f in self.feedback_items if f.feedback_type == FeedbackType.THUMBS_UP]
            ),
            "thumbs_down": len(
                [f for f in self.feedback_items if f.feedback_type == FeedbackType.THUMBS_DOWN]
            ),
        }

        # Calculate sentiment score
        total_sentiment_feedback = sentiment["positive"] + sentiment["negative"]
        if total_sentiment_feedback > 0:
            sentiment_score = sentiment["positive"] / total_sentiment_feedback
        else:
            sentiment_score = 0.0

        # Calculate feedback type distribution
        type_distribution = self._count_feedback_types(self.feedback_items)

        # Calculate temporal statistics
        if self.feedback_items:
            timestamps = [f.timestamp for f in self.feedback_items]
            time_span = max(timestamps) - min(timestamps)
            feedback_rate = len(self.feedback_items) / (time_span.days or 1)
        else:
            feedback_rate = 0

        return {
            "total_feedback": len(self.feedback_items),
            "unique_users": len(self.feedback_by_user),
            "unique_runs": len(self.feedback_by_run),
            "average_rating": rating_agg.value,
            "rating_count": rating_agg.count,
            "rating_distribution": rating_distribution,
            "sentiment_breakdown": sentiment,
            "sentiment_score": sentiment_score,
            "feedback_types": type_distribution,
            "feedback_rate_per_day": feedback_rate,
            "rating_metadata": rating_agg.metadata if rating_agg.count > 0 else {},
        }

    def get_trends(self, window_hours: int = 24) -> Dict[str, Any]:
        """Analyze trends in feedback over time.

        Args:
            window_hours: Size of time window for trend analysis

        Returns:
            Dictionary with trend information
        """
        windows = self.aggregate_by_time_window(window_hours)

        if len(windows) < 2:
            return {
                "trend": "insufficient_data",
                "windows": len(windows),
                "rating_trend": None,
                "volume_trend": None,
                "sentiment_trend": None,
                "hourly_counts": [],
                "average_rating_trend": [],
            }

        # Calculate rating trend
        rating_values = [w.value for w in windows if w.value > 0]
        if len(rating_values) >= 2:
            rating_trend = ("improving" if rating_values[-1] > rating_values[0] else "declining",)
            rating_change = rating_values[-1] - rating_values[0]
        else:
            rating_trend = None
            rating_change = 0

        # Calculate volume trend
        volumes = [w.count for w in windows]
        volume_trend = "increasing" if volumes[-1] > volumes[0] else "decreasing"
        volume_change = volumes[-1] - volumes[0]

        # Calculate sentiment trend over windows
        sentiment_progression = []
        for window in windows:
            if "feedback_types" in window.metadata:
                types = window.metadata["feedback_types"]
                positive = types.get("THUMBS_UP", 0)
                negative = types.get("THUMBS_DOWN", 0)
                total = positive + negative
                if total > 0:
                    sentiment_progression.append(positive / total)
                else:
                    sentiment_progression.append(0.5)

        if len(sentiment_progression) >= 2:
            sentiment_trend = (
                "improving"
                if sentiment_progression[-1] > sentiment_progression[0]
                else "declining",
            )
        else:
            sentiment_trend = None

        # Format for test compatibility
        hourly_counts = [w.count for w in windows]
        average_rating_trend = [w.value for w in windows]

        return {
            "trend": "analyzed",
            "windows": len(windows),
            "rating_trend": rating_trend,
            "rating_change": rating_change,
            "volume_trend": volume_trend,
            "volume_change": volume_change,
            "sentiment_trend": sentiment_trend,
            "hourly_counts": hourly_counts,
            "average_rating_trend": average_rating_trend,
            "time_range": {
                "start": windows[0].metadata.get("start") if windows else None,
                "end": windows[-1].metadata.get("end") if windows else None,
            },
        }

    def identify_patterns(self) -> Dict[str, Any]:
        """Identify patterns in user feedback behavior.

        Returns:
            Dictionary with identified patterns
        """
        patterns_list = self.analyze_user_patterns()

        if not patterns_list:
            return {
                "patterns_found": False,
                "user_patterns": {},
                "user_segments": [],
                "behavioral_patterns": [],
                "recommendations": [],
            }

        # Create user_patterns dictionary for test compatibility
        user_patterns_dict = {}
        for pattern in patterns_list:
            user_patterns_dict[pattern.user_id] = {
                "total_feedback": pattern.total_feedback,
                "average_rating": pattern.average_rating,
                "dominant_sentiment": pattern.dominant_sentiment,
                "feedback_frequency": pattern.feedback_frequency,
                "correction_rate": pattern.correction_rate,
            }

        # Segment users by behavior
        user_segments = {
            "highly_engaged": [],
            "critics": [],
            "supporters": [],
            "correctors": [],
        }

        for pattern in patterns_list:
            # Highly engaged users (frequent feedback)
            if pattern.feedback_frequency > 2:
                user_segments["highly_engaged"].append(pattern.user_id)

            # Critics (low ratings or negative sentiment)
            if pattern.dominant_sentiment == "negative" or (
                pattern.average_rating and pattern.average_rating < 3
            ):
                user_segments["critics"].append(pattern.user_id)

            # Supporters (high ratings or positive sentiment)
            if pattern.dominant_sentiment == "positive" or (
                pattern.average_rating and pattern.average_rating >= 4
            ):
                user_segments["supporters"].append(pattern.user_id)

            # Correctors (high correction rate)
            if pattern.correction_rate > 20:
                user_segments["correctors"].append(pattern.user_id)

        # Identify behavioral patterns
        behavioral_patterns = []

        # Pattern: Feedback clustering
        if self.feedback_items:
            timestamps = sorted([f.timestamp for f in self.feedback_items])
            if len(timestamps) > 1:
                gaps = [
                    (timestamps[i + 1] - timestamps[i]).total_seconds() / 3600
                    for i in range(len(timestamps) - 1)
                ]
                avg_gap = statistics.mean(gaps)
                if avg_gap < 1:  # Less than 1 hour average gap
                    behavioral_patterns.append("feedback_clustering")

        # Pattern: Rating polarization
        ratings = [
            f.value
            for f in self.feedback_items
            if f.feedback_type == FeedbackType.RATING and isinstance(f.value, (int, float))
        ]
        if ratings:
            low_ratings = sum(1 for r in ratings if r <= 2)
            high_ratings = sum(1 for r in ratings if r >= 4)
            mid_ratings = len(ratings) - low_ratings - high_ratings
            if (low_ratings + high_ratings) > mid_ratings * 2:
                behavioral_patterns.append("rating_polarization")

        # Pattern: Correction dominance
        correction_count = len(
            [f for f in self.feedback_items if f.feedback_type == FeedbackType.CORRECTION]
        )
        if self.feedback_items and correction_count / len(self.feedback_items) > 0.3:
            behavioral_patterns.append("correction_dominance")

        # Generate recommendations based on patterns
        recommendations = []
        if "feedback_clustering" in behavioral_patterns:
            recommendations.append(
                "Consider implementing rate limiting for feedback submission",
            )
        if "rating_polarization" in behavioral_patterns:
            recommendations.append(
                "Investigate causes of polarized opinions in user base",
            )
        if "correction_dominance" in behavioral_patterns:
            recommendations.append(
                "Model may need retraining based on high correction rate",
            )
        if len(user_segments["critics"]) > len(user_segments["supporters"]):
            recommendations.append("Focus on addressing concerns from critical users")

        return {
            "patterns_found": True,
            "user_patterns": user_patterns_dict,
            "user_segments": {k: len(v) for k, v in user_segments.items()},
            "behavioral_patterns": behavioral_patterns,
            "recommendations": recommendations,
            "detailed_segments": user_segments,
        }
