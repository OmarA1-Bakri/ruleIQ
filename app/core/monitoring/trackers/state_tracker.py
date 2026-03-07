"""
State transition tracking for LangGraph workflows.
"""

import time
from collections import defaultdict, deque
from typing import Any, Deque, Dict, List, Optional, Tuple


class StateTransitionTracker:
    """Tracks state transitions in LangGraph workflows."""

    def __init__(self, max_history: int = 5000) -> None:
        """Initialize state transition tracker.

        Args:
            max_history: Maximum number of transitions to keep
        """
        self.max_history = max_history
        self._transitions: Deque[Dict[str, Any]] = deque(maxlen=max_history)
        self._transition_counts: Dict[Tuple[str, str], int] = defaultdict(int)
        self._state_durations: Dict[str, List[float]] = defaultdict(list)
        self._current_states: Dict[str, Tuple[str, float]] = {}
        self._state_machines: Dict[str, Dict[str, Any]] = {}
        self._valid_states: set = set()
        self._valid_transitions: Dict[str, List[str]] = {}
        self._initial_state: Optional[str] = None

    def define_state_machine(self, state_machine: Dict[str, Any]) -> None:
        """Define valid state transitions for validation.

        Args:
            state_machine: Dictionary defining valid states and transitions
                          Can be either:
                          1. Simple format: {
                              "state1": ["state2", "state3"],
                              "state2": ["state3"],
                              ...
                          }
                          2. Complex format: {
                              "initial": "state_name",
                              "states": ["state1", "state2", ...],
                              "transitions": {
                                  "state1": ["state2", "state3"],
                                  "state2": ["state3"],
                                  ...
                              }
                          }
        """
        # Check if it's simple format
        is_simple_format = all(isinstance(v, list) for v in state_machine.values())

        if is_simple_format:
            # Convert simple format to complex format
            states = list(state_machine.keys())
            for transitions in state_machine.values():
                for state in transitions:
                    if state not in states:
                        states.append(state)

            initial_state = states[0] if states else None
            converted_machine = {
                "initial": initial_state,
                "states": states,
                "transitions": state_machine,
            }
            state_machine = converted_machine

        self._state_machines["default"] = state_machine

        if "initial" not in state_machine or state_machine["initial"] is None:
            raise ValueError("State machine must define an initial state")
        if "states" not in state_machine:
            raise ValueError("State machine must define available states")
        if "transitions" not in state_machine:
            raise ValueError("State machine must define valid transitions")

        self._valid_states = set(state_machine["states"])
        self._valid_transitions = state_machine["transitions"]
        self._initial_state = state_machine["initial"]

    def is_valid_transition(self, from_state: str, to_state: str) -> bool:
        """Check if a transition from one state to another is valid.

        Args:
            from_state: The state transitioning from
            to_state: The state transitioning to

        Returns:
            True if the transition is valid, False otherwise
        """
        if not self._valid_transitions:
            return True  # No validation defined

        if from_state not in self._valid_transitions:
            return False

        return to_state in self._valid_transitions[from_state]

    def record_transition(
        self,
        workflow_id: str,
        from_state: str,
        to_state: str,
        metadata: Dict[str, Any] = None,
        transition_trigger: Optional[str] = None,
    ) -> str:
        """Record a state transition.

        Args:
            workflow_id: Workflow ID
            from_state: Previous state
            to_state: New state
            metadata: Additional metadata
            transition_trigger: What triggered the transition

        Returns:
            Transition ID
        """
        transition_time = time.time()
        transition_id = f"{workflow_id}_{from_state}_{to_state}_{int(transition_time * 1000)}"

        # Track state duration
        if workflow_id in self._current_states:
            current_state, start_time = self._current_states[workflow_id]
            duration = transition_time - start_time
            self._state_durations[current_state].append(duration)

        self._current_states[workflow_id] = (to_state, transition_time)

        transition = {
            "id": transition_id,
            "workflow_id": workflow_id,
            "from_state": from_state,
            "to_state": to_state,
            "timestamp": transition_time,
            "metadata": metadata or {},
            "trigger": transition_trigger,
        }

        self._transitions.append(transition)
        self._transition_counts[(from_state, to_state)] += 1

        return transition_id

    def enter_state(self, workflow_id: str, state: str, metadata: Dict[str, Any] = None) -> str:
        """Enter a new state (convenience method for initial state or simple transitions).

        Args:
            workflow_id: Workflow ID
            state: State to enter
            metadata: Additional metadata

        Returns:
            State entry ID
        """
        if workflow_id in self._current_states:
            current_state, _ = self._current_states[workflow_id]
            return self.record_transition(
                workflow_id=workflow_id, from_state=current_state, to_state=state, metadata=metadata
            )

        # Initial state entry
        entry_time = time.time()
        entry_id = f"{workflow_id}_{state}_{int(entry_time * 1000)}"
        self._current_states[workflow_id] = (state, entry_time)

        transition = {
            "id": entry_id,
            "workflow_id": workflow_id,
            "from_state": None,
            "to_state": state,
            "timestamp": entry_time,
            "metadata": metadata or {},
            "trigger": "initial",
        }

        self._transitions.append(transition)
        return entry_id

    def get_transition_matrix(self) -> Dict[str, Dict[str, int]]:
        """Get transition matrix showing counts between states.

        Returns:
            Nested dictionary of transition counts
        """
        matrix = defaultdict(lambda: defaultdict(int))
        for (from_state, to_state), count in self._transition_counts.items():
            matrix[from_state][to_state] = count
        return dict(matrix)

    def get_transition_details(self, transition_id: str) -> Optional[Dict[str, Any]]:
        """Get details of a specific transition.

        Args:
            transition_id: The transition ID to look up

        Returns:
            Dictionary with transition details or None if not found
        """
        for transition in self._transitions:
            if transition["id"] == transition_id:
                return {
                    "from_state": transition["from_state"],
                    "to_state": transition["to_state"],
                    "transition_trigger": transition.get("trigger"),
                    "timestamp": transition["timestamp"],
                    "workflow_id": transition["workflow_id"],
                    "metadata": transition.get("metadata", {}),
                }
        return None

    def get_state_durations(self, workflow_id: Optional[str] = None) -> Dict[str, float]:
        """Get duration statistics for states.

        Args:
            workflow_id: Specific workflow ID or None for all workflows

        Returns:
            Dictionary mapping state names to average durations in milliseconds
        """
        if workflow_id:
            workflow_durations = {}
            workflow_transitions = [
                t for t in self._transitions if t.get("workflow_id") == workflow_id
            ]
            workflow_transitions.sort(key=lambda x: x["timestamp"])

            for i in range(len(workflow_transitions) - 1):
                current = workflow_transitions[i]
                next_trans = workflow_transitions[i + 1]
                state = current.get("to_state")
                if state:
                    duration_ms = (next_trans["timestamp"] - current["timestamp"]) * 1000
                    workflow_durations[state] = duration_ms

            return workflow_durations

        # Average durations across all workflows
        result = {}
        for state_name, durations in self._state_durations.items():
            if durations:
                result[state_name] = sum(durations) / len(durations) * 1000  # Convert to ms

        return result

    def validate_transition(
        self, from_state: str, to_state: str, allowed_transitions: Dict[str, List[str]]
    ) -> bool:
        """Validate if a transition is allowed.

        Args:
            from_state: Current state
            to_state: Target state
            allowed_transitions: Dictionary of allowed transitions

        Returns:
            True if transition is valid
        """
        if from_state not in allowed_transitions:
            return False
        return to_state in allowed_transitions[from_state]

    def get_transition_history(
        self, workflow_id: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get transition history.

        Args:
            workflow_id: Specific workflow or None for all
            limit: Maximum number of transitions to return

        Returns:
            List of transitions
        """
        if workflow_id:
            transitions = [t for t in self._transitions if t["workflow_id"] == workflow_id]
        else:
            transitions = list(self._transitions)

        return transitions[-limit:]

    def detect_patterns(self, min_count: int = 3) -> List[List[Tuple[str, str]]]:
        """Detect common transition patterns.

        Args:
            min_count: Minimum count for a pattern to be considered common

        Returns:
            List of common transition sequences
        """
        workflow_sequences = defaultdict(list)
        for transition in self._transitions:
            workflow_sequences[transition["workflow_id"]].append(
                (transition["from_state"], transition["to_state"])
            )

        pattern_counts = defaultdict(int)
        for sequence in workflow_sequences.values():
            for length in range(2, min(6, len(sequence) + 1)):
                for i in range(len(sequence) - length + 1):
                    pattern = tuple(sequence[i : i + length])
                    pattern_counts[pattern] += 1

        common_patterns = [
            list(pattern) for pattern, count in pattern_counts.items() if count >= min_count
        ]
        common_patterns.sort(key=lambda p: pattern_counts[tuple(p)], reverse=True)

        return common_patterns

    def get_workflow_history(self, workflow_id: str) -> List[Dict[str, Any]]:
        """Get the complete transition history for a workflow.

        Args:
            workflow_id: Workflow ID to get history for

        Returns:
            List of transitions for the workflow
        """
        history = []
        for transition in self._transitions:
            if transition["workflow_id"] == workflow_id:
                history.append(
                    {
                        "from_state": transition["from_state"],
                        "to_state": transition["to_state"],
                        "timestamp": transition["timestamp"],
                        "trigger": transition.get("trigger"),
                        "metadata": transition.get("metadata", {}),
                    }
                )

        return sorted(history, key=lambda x: x["timestamp"])

    def analyze_transition_patterns(
        self, workflow_id: str = None, min_frequency: int = 1
    ) -> Dict[str, Any]:
        """Analyze state transition patterns.

        Args:
            workflow_id: Optional workflow ID to filter by
            min_frequency: Minimum frequency for patterns to be included

        Returns:
            Analysis of transition patterns including most common paths
        """
        if workflow_id:
            transitions = [t for t in self._transitions if t["workflow_id"] == workflow_id]
        else:
            transitions = list(self._transitions)

        if not transitions:
            return {}

        pattern_counts = defaultdict(int)
        from_state_counts = defaultdict(int)

        for transition in transitions:
            from_state = transition.get("from_state")
            to_state = transition.get("to_state")
            if from_state and to_state:
                pattern_key = f"{from_state}->{to_state}"
                pattern_counts[pattern_key] += 1
                from_state_counts[from_state] += 1

        result = {}
        for pattern, count in pattern_counts.items():
            if count >= min_frequency:
                from_state = pattern.split("->")[0]
                total_from_state = from_state_counts[from_state]
                result[pattern] = {
                    "count": count,
                    "probability": count / total_from_state if total_from_state > 0 else 0,
                }

        return result
