# PR Auto-Review System

The PR Auto-Review System provides intelligent, automated review and management of all pull requests in the repository. It can safely auto-merge high-confidence PRs and provide actionable feedback for others.

## 🤖 Features

### Automatic Actions
- **Auto-merge safe PRs** - Merges PRs with high confidence scores (≥85% by default)
- **Intelligent commenting** - Adds helpful comments with specific next steps for uncertain PRs
- **Safety checks** - Comprehensive validation before any action
- **Audit trail** - Complete logging of all decisions and actions

### Safety Measures
- **Dry-run mode by default** - Test changes without affecting PRs
- **Confidence thresholds** - Only acts on PRs above configured confidence levels
- **Rate limiting** - Maximum 5 auto-merges per run to prevent runaway automation
- **Multi-layered validation** - CI status, conflicts, security scans, and more
- **Protected file detection** - Extra caution for critical files

### Smart Decision Making
- **Decision matrix evaluation** - Uses existing sophisticated scoring system
- **PR type classification** - Different handling for dependabot, security, feature, and bugfix PRs
- **Context-aware comments** - Tailored feedback based on PR type and issues

## 🚀 Quick Start

### Simple Usage
```bash
# Safe dry-run (no changes made)
./review_all_prs.sh

# Auto-review only (faster)
./review_all_prs.sh --auto-review-only

# Live mode (actually merges PRs)
./review_all_prs.sh --live
```

### Python Usage
```bash
# Direct Python execution
python pr_auto_reviewer.py --dry-run
python enhanced_pr_orchestrator.py --auto-review-only
```

## 📊 How It Works

### 1. PR Discovery
- Fetches all open PRs from the repository
- Classifies each PR by type (dependabot, security, feature, etc.)

### 2. Safety Checks
For each PR, the system validates:
- ✅ CI/CD pipeline status
- ✅ No merge conflicts
- ✅ Security scan results
- ✅ File change patterns
- ✅ PR size and complexity

### 3. Decision Matrix Evaluation
- Calculates confidence score based on multiple factors
- Determines appropriate action (auto-merge, comment, or manual review)
- Uses different thresholds for different PR types

### 4. Automated Actions
Based on confidence score:
- **≥85%**: Auto-merge with approval
- **≥60%**: Add helpful comment with next steps
- **<60%**: Flag for manual review

### 5. Reporting
- Generates comprehensive reports
- Tracks all actions and decisions
- Provides recommendations for improvement

## 🛡️ Safety Features

### Multiple Safety Layers
1. **Pre-flight checks** - Validates system state before any action
2. **PR-level validation** - Individual safety checks per PR
3. **Action confirmation** - Final validation before merge/comment
4. **Audit logging** - Complete record of all decisions

### Configurable Limits
```yaml
auto_reviewer:
  auto_merge_confidence_threshold: 85.0  # High bar for auto-merge
  comment_confidence_threshold: 60.0     # Helpful comments
  max_auto_merges_per_run: 5            # Safety limit
```

### Protected Files
Extra caution for critical files:
- `.github/` - GitHub configuration
- `config/` - Application configuration
- `security/` - Security-related files
- `Dockerfile*` - Container definitions
- `requirements.txt` - Dependencies

## 📈 Example Workflow

### High-Confidence PR (Auto-merged)
```
PR #123: Bump eslint from 8.1.0 to 8.2.0
├── Type: dependabot
├── Confidence: 92%
├── Checks: All passing ✅
├── Conflicts: None ✅
├── Action: Auto-merged 🎉
└── Comment: "🤖 Automated Review - APPROVED ✅"
```

### Medium-Confidence PR (Commented)
```
PR #456: Add user authentication feature
├── Type: feature
├── Confidence: 73%
├── Checks: Some failing ⚠️
├── Action: Helpful comment added 💬
└── Comment: "## 🤖 Automated Review - Action Required
              ❌ Blocking Issues:
              - CI checks are failing
              - Missing test coverage
              🔧 Required Actions:
              - Fix failing unit tests
              - Add integration tests for auth flow"
```

### Low-Confidence PR (Manual Review)
```
PR #789: Massive refactoring across 200 files
├── Type: feature
├── Confidence: 45%
├── Size: Very large ⚠️
├── Action: Manual review required 👨‍💻
└── Reason: Complex changes need human oversight
```

## 🔧 Configuration

### Main Configuration (`config.yaml`)
```yaml
auto_reviewer:
  enabled: true
  auto_merge_confidence_threshold: 85.0
  comment_confidence_threshold: 60.0
  max_auto_merges_per_run: 5
  
  # Safety settings
  require_ci_success: true
  block_on_conflicts: true
  block_on_security_issues: true
  
  # Protected file patterns
  protected_patterns:
    - ".github/"
    - "config/"
    - "security/"
```

### Decision Matrix Weights
The system uses sophisticated scoring based on:
- **CI Status** (30 points) - All checks must pass
- **Security Priority** (25 points) - Security fixes get priority
- **No Conflicts** (20 points) - Clean merge required
- **Has Tests** (15 points) - Test coverage important
- **Appropriate Size** (10 points) - Reasonable change size

## 📋 Reports and Monitoring

### Generated Reports
- **JSON Results** - Machine-readable detailed results
- **Markdown Report** - Human-readable summary
- **Audit Log** - Complete action history

### Key Metrics
- Total PRs processed
- Auto-merge success rate
- Comment effectiveness
- Error rates
- Processing time

### Example Report Output
```markdown
# PR Auto-Reviewer Report

## Summary
- Total PRs Processed: 15
- Auto-Merged: 8
- Commented: 5
- Skipped: 2
- Success Rate: 86.7%

## Auto-Merged PRs
- PR #121: Bump @types/node (Confidence: 95.2%)
- PR #120: Bump eslint (Confidence: 93.8%)
- PR #119: Fix typo in README (Confidence: 88.1%)
```

## 🔍 Troubleshooting

### Common Issues

**No PRs Found**
- Check repository access
- Verify GitHub token is configured
- Ensure PRs are actually open

**Auto-merge Failed**
- Check CI status
- Verify no merge conflicts
- Review branch protection rules

**Low Confidence Scores**
- Improve PR descriptions
- Add comprehensive tests
- Break down large changes
- Ensure CI passes

### Debug Mode
```bash
# Enable verbose logging
export LOG_LEVEL=DEBUG
./review_all_prs.sh --dry-run
```

## 🤝 Integration

### GitHub Actions
```yaml
name: Auto-Review PRs
on:
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours
  workflow_dispatch:

jobs:
  auto-review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: pip install -r scripts/pr_management/requirements.txt
      - name: Run auto-review
        run: |
          cd scripts/pr_management
          ./review_all_prs.sh --live
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### Webhook Integration
The system can be triggered by webhook events:
- PR opened
- PR updated
- CI status changed

## 📚 Advanced Usage

### Custom Decision Logic
Extend the decision matrix for specific needs:
```python
# Custom factor evaluation
def _evaluate_custom_factor(self, factor, pr_data):
    if factor['name'] == 'custom_business_logic':
        # Your custom logic here
        return True
```

### Integration with External Systems
- Slack notifications
- Jira ticket updates
- Email alerts
- Custom webhooks

## 🛠️ Development

### Running Tests
```bash
# Run existing test suite
make test-groups

# Test PR management specifically
python -m pytest tests/ -k pr_management
```

### Adding New Features
1. Extend decision matrix factors
2. Add new PR type classifications
3. Implement custom comment templates
4. Add integration points

## 📄 License and Support

This auto-review system is part of the ruleIQ project and follows the same licensing terms.

For support:
- Check the troubleshooting section
- Review generated logs and reports
- Open an issue with detailed information

---

**⚠️ Important:** Always test changes in dry-run mode first. The auto-merge functionality should be used carefully with appropriate safety measures and monitoring.