"""

# Constants
DEFAULT_RETRIES = 5

Test suite for sprint management system
"""

import pytest
import datetime
import tempfile
import os
from unittest.mock import patch, MagicMock
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.sprint_management import (
    SprintManager,
    Sprint,
    UserStory,
    Task,
    Priority,
    StoryStatus,
    TaskType,
    AcceptanceCriteria,
)


class TestSprintManager:
    """Test cases for SprintManager"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.sprint_manager = SprintManager(data_dir=self.temp_dir)

    def teardown_method(self):
        """Cleanup test environment"""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_init_sprint(self):
        """Test sprint initialization"""
        sprint_data = {
            "id": "test_sprint_001",
            "name": "Test Sprint",
            "goal": "Test sprint functionality",
            "start_date": "2025-08-01",
            "end_date": "2025-08-15",
            "capacity_hours": 80.0,
            "team_members": ["Developer 1", "Developer 2"],
            "velocity_target": 25,
        }
        sprint = self.sprint_manager.init_sprint(sprint_data)
        assert sprint.id == "test_sprint_001"
        assert sprint.name == "Test Sprint"
        assert sprint.goal == "Test sprint functionality"
        assert sprint.capacity_hours == 80.0
        assert sprint.velocity_target == 25
        assert len(sprint.team_members) == 2

    def test_generate_sprint_stories(self):
        """Test story generation"""
        stories = self.sprint_manager.generate_sprint_stories("test_sprint", {})
        assert len(stories) == DEFAULT_RETRIES
        rbac_story = next((s for s in stories if s.id == "STORY-001"), None)
        assert rbac_story is not None
        assert rbac_story.title == "Complete RBAC System Implementation"
        assert rbac_story.priority == Priority.CRITICAL
        assert rbac_story.feature_area == "Authentication & Authorization"
        design_story = next((s for s in stories if s.id == "STORY-002"), None)
        assert design_story is not None
        assert design_story.title == "Complete Teal Design System Migration"
        assert design_story.priority == Priority.HIGH
        for story in stories:
            assert len(story.acceptance_criteria) > 0
            assert story.estimated_hours > 0
            assert story.story_points > 0

    def test_analyze_stories(self):
        """Test story analysis"""
        stories = self.sprint_manager.generate_sprint_stories("test_sprint", {})
        analysis = self.sprint_manager.analyze_stories(stories)
        assert "total_stories" in analysis
        assert "total_story_points" in analysis
        assert "total_estimated_hours" in analysis
        assert "priority_breakdown" in analysis
        assert "complexity_breakdown" in analysis
        assert "feature_area_breakdown" in analysis
        assert "recommendations" in analysis
        assert Priority.CRITICAL.value in analysis["priority_breakdown"]
        assert Priority.HIGH.value in analysis["priority_breakdown"]
        assert isinstance(analysis["recommendations"], list)

    def test_decompose_stories(self):
        """Test story decomposition into tasks"""
        stories = self.sprint_manager.generate_sprint_stories("test_sprint", {})
        decomposed_stories = self.sprint_manager.decompose_stories(stories)
        rbac_story = next((s for s in decomposed_stories if s.id == "STORY-001"), None)
        assert rbac_story is not None
        assert len(rbac_story.tasks) > 0
        for task in rbac_story.tasks:
            assert task.id.startswith("TASK-001")
            assert task.story_id == "STORY-001"
            assert task.estimated_hours > 0
            assert isinstance(task.type, TaskType)
        design_story = next((s for s in decomposed_stories if s.id == "STORY-002"), None)
        assert design_story is not None
        assert len(design_story.tasks) > 0

    def test_track_sprint_implementation(self):
        """Test sprint progress tracking"""
        sprint_data = {
            "id": "track_test_sprint",
            "name": "Track Test Sprint",
            "goal": "Test tracking functionality",
            "start_date": "2025-07-20",
            "end_date": "2025-08-03",
            "capacity_hours": 80.0,
            "team_members": ["Developer"],
            "velocity_target": 30,
        }
        sprint = self.sprint_manager.init_sprint(sprint_data)
        stories = self.sprint_manager.generate_sprint_stories(sprint.id, {})
        stories[0].status = StoryStatus.DONE
        stories[0].actual_hours = 20.0
        stories[1].status = StoryStatus.IN_PROGRESS
        stories[1].actual_hours = 10.0
        stories[2].status = StoryStatus.BLOCKED
        sprint.stories = stories
        self.sprint_manager._save_sprint(sprint)
        with patch.object(self.sprint_manager, "_load_sprint", return_value=sprint):
            progress = self.sprint_manager.track_sprint_implementation(sprint.id)
            assert progress["sprint_id"] == sprint.id
            assert progress["total_stories"] == len(stories)
            assert progress["completed_stories"] == 1
            assert progress["in_progress_stories"] == 1
            assert progress["blocked_stories"] == 1
            assert "stories_by_status" in progress
            assert "recommendations" in progress


class TestDataClasses:
    """Test sprint data classes"""

    def test_user_story_creation(self):
        """Test UserStory dataclass"""
        criteria = [
            AcceptanceCriteria("Test criteria 1"),
            AcceptanceCriteria("Test criteria 2", automated_test="test_function"),
        ]
        story = UserStory(
            id="TEST-001",
            title="Test Story",
            description="A test story",
            priority=Priority.HIGH,
            story_points=5,
            feature_area="Testing",
            acceptance_criteria=criteria,
            estimated_hours=20.0,
        )
        assert story.id == "TEST-001"
        assert story.priority == Priority.HIGH
        assert len(story.acceptance_criteria) == 2
        assert story.acceptance_criteria[1].automated_test == "test_function"
        assert story.estimated_hours == 20.0
        assert story.status == StoryStatus.PENDING

    def test_task_creation(self):
        """Test Task dataclass"""
        task = Task(
            id="TASK-001",
            title="Test Task",
            description="A test task",
            type=TaskType.FEATURE,
            story_id="STORY-001",
            estimated_hours=8.0,
            dependencies=["TASK-002"],
        )
        assert task.id == "TASK-001"
        assert task.type == TaskType.FEATURE
        assert task.estimated_hours == 8.0
        assert task.dependencies == ["TASK-002"]
        assert task.status == StoryStatus.PENDING

    def test_sprint_creation(self):
        """Test Sprint dataclass"""
        start_date = datetime.date(2025, 8, 1)
        end_date = datetime.date(2025, 8, 15)
        sprint = Sprint(
            id="SPRINT-001",
            name="Test Sprint",
            goal="Test sprint functionality",
            start_date=start_date,
            end_date=end_date,
            capacity_hours=80.0,
            team_members=["Dev1", "Dev2"],
        )
        assert sprint.id == "SPRINT-001"
        assert sprint.start_date == start_date
        assert sprint.end_date == end_date
        assert sprint.capacity_hours == 80.0
        assert len(sprint.team_members) == 2
        assert sprint.status == "PLANNING"


class TestSprintBusinessLogic:
    """Test business logic and edge cases"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.sprint_manager = SprintManager(data_dir=self.temp_dir)

    def teardown_method(self):
        """Cleanup test environment"""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_story_priority_analysis(self):
        """Test analysis handles different story priorities correctly"""
        stories = [
            UserStory("S1", "Critical Story", "Desc", Priority.CRITICAL, 8, "Feature", []),
            UserStory("S2", "High Story", "Desc", Priority.HIGH, 5, "Feature", []),
            UserStory("S3", "Medium Story", "Desc", Priority.MEDIUM, 3, "Feature", []),
            UserStory("S4", "Low Story", "Desc", Priority.LOW, 2, "Feature", []),
        ]
        analysis = self.sprint_manager.analyze_stories(stories)
        assert analysis["priority_breakdown"][Priority.CRITICAL.value] == 1
        assert analysis["priority_breakdown"][Priority.HIGH.value] == 1
        assert analysis["priority_breakdown"][Priority.MEDIUM.value] == 1
        assert analysis["priority_breakdown"][Priority.LOW.value] == 1
        assert analysis["total_story_points"] == 18

    def test_feature_area_breakdown(self):
        """Test feature area analysis"""
        stories = [
            UserStory(
                "S1",
                "Auth Story",
                "Desc",
                Priority.HIGH,
                8,
                "Authentication",
                [],
                estimated_hours=20.0,
            ),
            UserStory(
                "S2",
                "Auth Story 2",
                "Desc",
                Priority.MEDIUM,
                5,
                "Authentication",
                [],
                estimated_hours=15.0,
            ),
            UserStory(
                "S3", "UI Story", "Desc", Priority.HIGH, 3, "Frontend", [], estimated_hours=10.0
            ),
        ]
        analysis = self.sprint_manager.analyze_stories(stories)
        breakdown = analysis["feature_area_breakdown"]
        assert "Authentication" in breakdown
        assert "Frontend" in breakdown
        assert breakdown["Authentication"]["count"] == 2
        assert breakdown["Authentication"]["story_points"] == 13
        assert breakdown["Authentication"]["hours"] == 35.0
        assert breakdown["Frontend"]["count"] == 1

    def test_recommendations_generation(self):
        """Test that appropriate recommendations are generated"""
        stories = []
        for i in range(10):
            story = UserStory(
                f"S{i}", f"Story {i}", "Desc", Priority.HIGH, 8, "Feature", [], estimated_hours=20.0
            )
            stories.append(story)
        analysis = self.sprint_manager.analyze_stories(stories)
        recommendations = analysis["recommendations"]
        assert any("splitting sprint" in rec.lower() for rec in recommendations)

    def test_critical_complexity_risk_detection(self):
        """Test detection of high-risk stories"""
        stories = [
            UserStory(
                "S1",
                "Complex Story 1",
                "Desc",
                Priority.HIGH,
                8,
                "Feature",
                [],
                technical_complexity="CRITICAL",
            ),
            UserStory(
                "S2",
                "Complex Story 2",
                "Desc",
                Priority.HIGH,
                8,
                "Feature",
                [],
                technical_complexity="CRITICAL",
            ),
        ]
        analysis = self.sprint_manager.analyze_stories(stories)
        risks = analysis["risks"]
        assert any("critical complexity" in risk.lower() for risk in risks)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
