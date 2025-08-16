# LangGraph Conversational Assessment Integration Guide

## Overview

The ruleIQ assessment system has been enhanced with a LangGraph-based conversational agent that provides:
- Stateful, multi-turn conversations
- Dynamic question generation based on context
- Adaptive difficulty based on user expertise
- Progressive compliance profile building
- Full observability through LangSmith tracing

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────┐
│                   Frontend (Next.js)                     │
│  EmailCaptureForm → Assessment Page → Results Display   │
└────────────────────┬────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│                  Freemium API Router                     │
│         /freemium/sessions → /freemium/answers          │
└────────────────────┬────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│            FreemiumAssessmentService                     │
│  Feature Flag: USE_LANGGRAPH_AGENT (true/false)        │
└────────────┬───────────────────┬────────────────────────┘
             │                   │
             ▼                   ▼
┌──────────────────────┐ ┌──────────────────────┐
│  AssessmentAgent     │ │  Traditional Flow    │
│   (LangGraph)        │ │  (Static Questions)  │
└──────────────────────┘ └──────────────────────┘
```

### LangGraph State Machine

The assessment agent uses a state graph with the following nodes:

1. **Introduction** → Initial greeting and context setting
2. **Analyze Context** → Process business information
3. **Generate Question** → AI-powered dynamic question generation
4. **Process Answer** → Handle user responses
5. **Determine Next** → Routing logic for next step
6. **Generate Results** → Create compliance assessment
7. **Completion** → Finalize session

### State Management

```python
class AssessmentState(TypedDict):
    messages: List[Any]              # Conversation history
    session_id: str                  # Unique session ID
    lead_id: str                     # Lead identifier
    thread_id: str                   # LangGraph thread ID
    current_phase: AssessmentPhase   # Current conversation phase
    questions_asked: List[str]      # Track asked questions
    questions_answered: int          # Count of answers
    business_profile: Dict           # Business context
    compliance_needs: List[str]     # Identified needs
    identified_risks: List[str]     # Discovered risks
    compliance_score: float          # Calculated score
    risk_level: str                 # Risk assessment
    recommendations: List[Dict]      # AI recommendations
```

## Implementation Details

### 1. Assessment Agent (`services/assessment_agent.py`)

The core LangGraph agent that manages the conversational flow:

```python
from services.assessment_agent import AssessmentAgent

# Initialize with database session
agent = AssessmentAgent(db_session)

# Start assessment
state = await agent.start_assessment(
    session_id="unique_session_id",
    lead_id="lead_id",
    initial_context={
        "business_type": "Software Company",
        "company_size": "11-50",
        "industry": "Technology"
    }
)

# Process user response
state = await agent.process_user_response(
    session_id="unique_session_id",
    user_response="We handle customer data and payments",
    confidence="high"
)
```

### 2. Circuit Breaker Pattern

The agent includes fallback mechanisms when AI services are unavailable:

```python
if self.circuit_breaker.is_model_available("gemini-2.5-flash"):
    # Use AI for dynamic questions
    question = await self._generate_ai_question(context)
else:
    # Fallback to predefined questions
    question = self._get_fallback_question(phase)
```

### 3. Memory Persistence

Uses LangGraph's checkpointer for conversation continuity:

```python
self.checkpointer = MemorySaver()
self.app = self.graph.compile(checkpointer=self.checkpointer)
```

## LangSmith Observability

### Setup

1. **Get LangSmith API Key**
   - Sign up at https://smith.langchain.com
   - Get your API key from the dashboard

2. **Configure Environment Variables**
   ```bash
   # .env file
   LANGCHAIN_TRACING_V2=true
   LANGCHAIN_API_KEY=ls__your_api_key_here
   LANGCHAIN_PROJECT=ruleiq-assessment
   LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
   ```

3. **Verify Configuration**
   ```bash
   python scripts/test_langsmith_tracing.py
   ```

### What You'll See in LangSmith

- **Complete Conversation Flow**: Visual graph of state transitions
- **Node Executions**: Input/output for each processing step
- **AI Model Calls**: Prompts and responses from Gemini
- **Error Traces**: Fallback behavior and error handling
- **Performance Metrics**: Timing for each step
- **Session Timelines**: Complete assessment journey

### Trace Metadata

The system automatically adds:
- Session IDs for tracking conversations
- Lead IDs for user correlation
- Phase information for context
- Error counts and fallback status
- Custom tags for filtering

## Usage Examples

### 1. Starting an Assessment

```python
# In freemium_assessment_service.py
async def create_session(self, lead_id: str, ...):
    if self.USE_LANGGRAPH_AGENT:
        # Use conversational agent
        state = await self.assessment_agent.start_assessment(
            session_id=str(session.id),
            lead_id=str(lead_id),
            initial_context={
                "business_type": business_type,
                "company_size": company_size,
                "assessment_type": assessment_type,
                "personalization_data": personalization_data
            }
        )
        # Extract first question from state
        question = self._extract_question_from_state(state)
    else:
        # Traditional flow
        questions = await self._generate_initial_questions(...)
```

### 2. Processing Answers

```python
async def process_answer(self, session_id: UUID, ...):
    if self.USE_LANGGRAPH_AGENT:
        # Conversational processing
        state = await self.assessment_agent.process_user_response(
            session_id=str(session_id),
            user_response=answer,
            confidence=answer_confidence
        )
        # Extract next question or results
        return self._format_response_from_state(state)
    else:
        # Traditional processing
        return await self._process_traditional_answer(...)
```

## Testing

### 1. Unit Tests

```bash
# Test assessment agent
pytest tests/unit/services/test_assessment_agent.py -v

# Test with tracing enabled
LANGCHAIN_TRACING_V2=true pytest tests/integration/test_langgraph_flow.py -v
```

### 2. Integration Tests

```bash
# Test full freemium flow with LangGraph
pytest tests/integration/api/test_freemium_langgraph.py -v
```

### 3. Manual Testing

1. **Enable Feature Flag**
   ```python
   # services/freemium_assessment_service.py
   self.USE_LANGGRAPH_AGENT = True
   ```

2. **Start Services**
   ```bash
   # Terminal 1: Backend
   source .venv/bin/activate
   python main.py
   
   # Terminal 2: Frontend
   cd frontend
   pnpm dev --turbo
   ```

3. **Test Flow**
   - Navigate to http://localhost:3000
   - Enter email to start assessment
   - Answer conversational questions
   - View AI-generated results

## Monitoring & Debugging

### 1. Enable Tracing for Debugging

```bash
# Temporarily enable for debugging
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_API_KEY=ls__your_key
```

### 2. View Logs

```python
# Check application logs
tail -f logs/ruleiq.log | grep "AssessmentAgent"

# Filter for specific session
tail -f logs/ruleiq.log | grep "session:abc123"
```

### 3. LangSmith Dashboard

- Go to https://smith.langchain.com
- Filter by project: "ruleiq-assessment"
- Use tags to find specific sessions
- Analyze conversation flow and errors

## Performance Considerations

### 1. Response Times

- **AI Generation**: 500-1500ms per question
- **Fallback Mode**: <50ms using cached questions
- **State Persistence**: ~20ms per checkpoint

### 2. Optimization Tips

- Enable caching for repeated questions
- Use fallback mode during high load
- Batch process results generation
- Implement request queuing for AI calls

### 3. Scaling

- Checkpointer uses in-memory storage (development)
- For production, use Redis or PostgreSQL checkpointer
- Implement connection pooling for database
- Use rate limiting for AI API calls

## Troubleshooting

### Common Issues

1. **Gemini API Quota Exceeded**
   - System automatically falls back to predefined questions
   - Check logs for: "Gemini API quota exceeded"
   - Solution: Upgrade API key or wait for quota reset

2. **LangSmith Traces Not Appearing**
   - Verify LANGCHAIN_TRACING_V2=true
   - Check API key format (should start with "ls__")
   - Ensure project name matches dashboard

3. **State Not Persisting**
   - Check thread_id consistency
   - Verify checkpointer initialization
   - Look for session timeout issues

4. **Slow Response Times**
   - Monitor AI API latency
   - Check circuit breaker status
   - Consider enabling fallback mode

## Future Enhancements

1. **Planned Improvements**
   - Multi-language support
   - Voice input/output integration
   - Real-time collaborative assessments
   - Advanced analytics dashboard

2. **LangGraph Optimizations**
   - Implement parallel node execution
   - Add conditional branching for expertise levels
   - Create specialized sub-graphs for industries
   - Implement streaming responses

3. **Observability Enhancements**
   - Custom LangSmith evaluators
   - Automated performance benchmarks
   - A/B testing framework
   - User satisfaction tracking

## References

- [LangGraph Documentation](https://python.langchain.com/docs/langgraph)
- [LangSmith Tracing Guide](https://docs.smith.langchain.com/observability/how_to_guides/trace_with_langgraph)
- [ruleIQ API Documentation](./API_ENDPOINTS_DOCUMENTATION.md)
- [Assessment Agent Source](../services/assessment_agent.py)

## Support

For questions or issues:
1. Check logs in `logs/ruleiq.log`
2. Review LangSmith traces
3. Consult this documentation
4. Contact the development team

---

*Last Updated: August 2025*
*Version: 1.0.0*