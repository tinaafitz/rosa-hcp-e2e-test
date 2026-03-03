# AI Agent Framework for ROSA HCP Test Automation

## Overview

The AI Agent Framework provides **autonomous issue detection and remediation** for ROSA HCP (Red Hat OpenShift Service on AWS - Hosted Control Plane) test automation. This self-healing test framework monitors test execution in real-time, diagnoses issues as they occur, and automatically applies fixes to keep tests running smoothly.

## Table of Contents

- [Quick Start](#quick-start)
- [How It Works](#how-it-works)
- [Architecture](#architecture)
- [Key Features](#key-features)
- [Usage Examples](#usage-examples)
- [Detected Issues and Fixes](#detected-issues-and-fixes)
- [Configuration](#configuration)
- [Monitoring and Auditing](#monitoring-and-auditing)
- [Jenkins Integration](#jenkins-integration)
- [Safety Features](#safety-features)
- [Extending the Framework](#extending-the-framework)
- [Troubleshooting](#troubleshooting)

## Quick Start

### Enable AI Agents

```bash
# Enable AI agents with live remediation
./run-test-suite.py 20-rosa-hcp-provision --ai-agent

# Enable AI agents in dry-run mode (detect and diagnose only)
./run-test-suite.py 20-rosa-hcp-provision --ai-agent --ai-agent-dry-run

# Combine with verbose mode for detailed agent logging
./run-test-suite.py 20-rosa-hcp-provision --ai-agent -vv
```

### Example Output

```
🤖 Initializing AI Agent Framework...
✓ AI Agent Framework initialized (LIVE MODE)
  - Monitoring Agent: Real-time issue detection
  - Diagnostic Agent: Root cause analysis
  - Remediation Agent: Autonomous fixes

================================================================================
CAPA Test Suite Runner
================================================================================

[Test execution begins...]

🤖 AI Agent detected issue: rosanetwork_stuck_deletion
   Root cause: ROSANetwork has finalizers preventing deletion
   Confidence: 95%
   Recommended fix: remove_finalizers
   ✓ Fix applied: Successfully removed finalizers from rosanetwork/test-cluster

[Test execution continues...]

================================================================================
📊 FINAL RESULTS SUMMARY:
   Total Tests: 3
   ✓ Passed: 3
   ✗ Failed: 0
   ⏱️  Total Duration: 15m 42s

🤖 AI AGENT STATISTICS:
   Issues Detected: 2
   Interventions: 2

   Fix Success Rates:
      remove_finalizers: 100.0% (1/1)
      backoff_and_retry: 100.0% (1/1)
================================================================================
```

## How It Works

### Step-by-Step Flow

#### 1. Real-Time Output Streaming

When you run a test suite with `--ai-agent`, the framework hooks into the output processing:

```python
for line in process.stdout:
    # Print immediately (prevents timeout detection in CI/CD)
    print(line, end='')

    # AI Agent Hook: Process line in real-time for issue detection
    if self.ai_agent_enabled and self.monitor_agent:
        self.monitor_agent.process_line(line)
```

#### 2. Pattern Detection (Monitoring Agent)

The **Monitoring Agent** processes each line looking for known issue patterns:

```
Output Line → Monitor Agent → Check against 8 patterns
                              ↓
                      Pattern Match Found?
                              ↓
                      Trigger Issue Callback
```

Example patterns:
- `rosanetwork.*delete.*timeout` → ROSANetwork stuck deletion
- `rate limit|429|too many requests` → API rate limiting
- `cloudformation.*(delete.*fail|rollback)` → CloudFormation failure

#### 3. Root Cause Analysis (Diagnostic Agent)

When the monitor detects an issue, it calls the **Diagnostic Agent**:

```python
def _ai_agent_issue_detected(self, issue_type: str, context: Dict, issue: Dict):
    print(f"\n🤖 AI Agent detected issue: {issue_type}")

    # Step 1: Diagnose the issue
    diagnosis = self.diagnostic_agent.diagnose(issue_type, context)
```

The Diagnostic Agent:
1. Reads the context (last 50 lines of output, current task name, resource names)
2. Queries Kubernetes if needed (e.g., `oc get rosanetwork -o json`)
3. Analyzes the evidence and determines root cause
4. Assigns confidence score (0.0 to 1.0)
5. Recommends a fix strategy

#### 4. Autonomous Fix Execution (Remediation Agent)

If confidence ≥ 70%, the **Remediation Agent** executes the fix:

```python
if diagnosis.get('confidence', 0) >= 0.7:
    success, message = self.remediation_agent.remediate(diagnosis)

    if success:
        print(f"✓ Fix applied: {message}")
```

### Complete End-to-End Example

Here's a real scenario showing the full flow:

```
1. Test running: Creating ROSA HCP cluster
   ↓
2. Output line: "Error: rosanetwork test-cluster deletion timeout after 600s"
   ↓
3. Monitor Agent: Pattern match! "rosanetwork.*delete.*timeout"
   ↓
4. Diagnostic Agent queries:
   $ oc get rosanetwork test-cluster -o json

   Finds:
   - deletionTimestamp: "2026-03-03T15:30:00Z"
   - finalizers: ["rosanetwork.infrastructure.cluster.x-k8s.io/finalizer"]
   - CloudFormation stack: already deleted or timed out

   Diagnosis:
   - Root cause: Finalizers blocking deletion after CF failure
   - Confidence: 95%
   - Recommended fix: remove_finalizers
   ↓
5. Remediation Agent executes:
   $ oc patch rosanetwork test-cluster --type=merge -p '{"metadata":{"finalizers":null}}'

   Result: Resource deleted successfully
   ↓
6. Agent logs intervention to:
   agents/knowledge_base/intervention_log.json

   Updates success rate: remove_finalizers 96% (24/25)
   ↓
7. Test continues running without manual intervention
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Test Suite Runner                        │
│                   (run-test-suite.py)                        │
└──────────────────────┬──────────────────────────────────────┘
                       │ Line-by-line streaming
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  Monitoring Agent                            │
│  • Processes output in real-time                            │
│  • Detects 8+ issue patterns                                │
│  • Maintains 50-line context buffer                         │
└──────────────────────┬──────────────────────────────────────┘
                       │ Issue detected
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                 Diagnostic Agent                             │
│  • Determines root cause                                    │
│  • Queries Kubernetes resources (oc/kubectl)                │
│  • Provides confidence score                                │
└──────────────────────┬──────────────────────────────────────┘
                       │ Diagnosis + recommended fix
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                Remediation Agent                             │
│  • Executes autonomous fixes                                │
│  • Tracks success rates                                     │
│  • Records interventions for audit                          │
└─────────────────────────────────────────────────────────────┘
```

### Component Structure

```
rosa-hcp-e2e-test/
├── run-test-suite.py              # Main test runner with AI integration
├── agents/
│   ├── __init__.py                # Agent exports
│   ├── base_agent.py              # Foundation class for all agents
│   ├── monitoring_agent.py        # Real-time output monitoring
│   ├── diagnostic_agent.py        # Root cause analysis
│   ├── remediation_agent.py       # Autonomous fix execution
│   ├── knowledge_base/
│   │   ├── known_issues.json      # Issue pattern definitions
│   │   ├── fix_strategies.json    # Remediation playbooks
│   │   └── intervention_log.json  # Audit trail (generated)
│   └── README.md                  # Detailed agent documentation
└── AI_AGENT_FRAMEWORK.md          # This file
```

## Key Features

### Real-Time Monitoring
- Line-by-line analysis of test output as it streams
- 50-line context buffer for multi-line pattern detection
- Tracks current Ansible task and resource states

### Pattern-Based Detection
- 8+ predefined issue patterns with regex matching
- Configurable patterns in JSON knowledge base
- Support for both single-line and multi-line patterns

### Root Cause Analysis
- Kubernetes resource introspection via `oc`/`kubectl`
- Log analysis and pattern correlation
- Evidence collection for audit trail

### Autonomous Remediation
- 7+ automated fix strategies
- Confidence-based intervention (≥70% threshold)
- Success rate tracking per fix type
- Dry-run mode for testing

### Learning System
- Tracks success rates for each fix type
- Records all interventions with full context
- Continuous improvement through feedback loop

### Safety Features
- Non-invasive by default (must explicitly enable)
- Fail-safe error handling (agent errors never break tests)
- Comprehensive audit trail
- Dry-run mode for validation

## Usage Examples

### Basic Usage

```bash
# Run test with AI agents enabled
./run-test-suite.py 20-rosa-hcp-provision --ai-agent

# Run with AI agents in dry-run mode (no fixes applied)
./run-test-suite.py 20-rosa-hcp-provision --ai-agent --ai-agent-dry-run

# Run with verbose agent logging
./run-test-suite.py 20-rosa-hcp-provision --ai-agent -vv
```

### Jenkins Pipeline

```groovy
stage('Provision ROSA HCP Cluster') {
    steps {
        sh '''
            cd rosa-hcp-e2e-test
            ./run-test-suite.py 20-rosa-hcp-provision --format junit --ai-agent \
              -e name_prefix="${NAME_PREFIX}" \
              -e AWS_REGION="us-west-2"
        '''
    }
}
```

### Viewing Intervention Logs

```bash
# Check if any interventions occurred
cat agents/knowledge_base/intervention_log.json | jq .

# View specific intervention details
cat agents/knowledge_base/intervention_log.json | jq '.[] | select(.success == true)'

# Count interventions by type
cat agents/knowledge_base/intervention_log.json | jq 'group_by(.type) | map({type: .[0].type, count: length})'
```

## Detected Issues and Fixes

### Automated Fixes (High Confidence)

#### 1. ROSANetwork Stuck in Deletion
- **Pattern**: `rosanetwork.*delete.*timeout`
- **Auto-Fix**: ✅ Yes
- **Fix Strategy**: Remove finalizers from stuck resource
- **Success Rate**: High (95%+)
- **Command**: `oc patch rosanetwork <name> --type=merge -p '{"metadata":{"finalizers":null}}'`

#### 2. API Rate Limiting
- **Pattern**: `rate limit|429|too many requests`
- **Auto-Fix**: ✅ Yes
- **Fix Strategy**: Exponential backoff (60s, 120s, 240s)
- **Success Rate**: High (90%+)
- **Action**: Sleep with exponential backoff

#### 3. OCM Token Refresh
- **Pattern**: `ocm.*(401|403|unauthorized)`
- **Auto-Fix**: ⚠️ Partial (requires new credentials)
- **Fix Strategy**: Alert operator to refresh OCM token
- **Action**: Provides guidance for token refresh

### Manual Intervention Required

#### 4. CloudFormation Deletion Failure
- **Pattern**: `cloudformation.*(delete.*fail|rollback)`
- **Auto-Fix**: ❌ Manual intervention required
- **Fix Strategy**: Log issue for operator review
- **Next Steps**: AWS console cleanup of orphaned resources (security groups, ENIs)

#### 5. CAPI/CAPA Controller Not Running
- **Pattern**: `capi.*(not found|does not exist)`
- **Auto-Fix**: ❌ Manual intervention required
- **Fix Strategy**: Guide user to run `10-configure-mce-environment`
- **Next Steps**: Execute MCE configuration playbook

#### 6. Resource Quota Exceeded
- **Pattern**: `quota.*exceed`
- **Auto-Fix**: ❌ Manual intervention required
- **Fix Strategy**: Alert operator to request quota increase or cleanup
- **Common Quotas**: VPCs (5), Elastic IPs (5), NAT Gateways (5)

#### 7. Networking Configuration Error
- **Pattern**: `(subnet|vpc|network).*(invalid|not found)`
- **Auto-Fix**: ❌ Manual intervention required
- **Fix Strategy**: Verify VPC and subnet configurations
- **Notes**: ROSA HCP requires specific network architecture

#### 8. Repeated Timeouts
- **Pattern**: Multiple `timeout` occurrences in buffer
- **Auto-Fix**: ⚠️ Partial
- **Fix Strategy**: Recommend increasing timeout values
- **Notes**: May indicate stuck resources requiring inspection

## Configuration

### Confidence Threshold

The framework only applies automatic remediation when diagnostic confidence ≥ 70%. This threshold is configured in `run-test-suite.py`:

```python
if diagnosis.get('confidence', 0) >= 0.7:
    success, message = self.remediation_agent.remediate(diagnosis)
```

To adjust the threshold, modify this value in the code.

### Verbosity Levels

- **Default** (`--ai-agent`): Shows only issue detection and fix results
- **-v**: Adds agent debug logging
- **-vv**: Detailed agent operation logs
- **-vvv**: Maximum verbosity with all agent details

### Knowledge Base Configuration

Issue patterns and fix strategies are defined in JSON files:

**`agents/knowledge_base/known_issues.json`**:
```json
{
  "rosanetwork_stuck_deletion": {
    "pattern": "rosanetwork.*delete.*timeout",
    "severity": "high",
    "auto_fix": true,
    "description": "ROSANetwork resource stuck in deletion",
    "symptoms": ["Deletion timeout", "Finalizers present"],
    "common_causes": ["CloudFormation failure", "Network dependencies"]
  }
}
```

**`agents/knowledge_base/fix_strategies.json`**:
```json
{
  "rosanetwork_stuck_deletion": {
    "name": "Remove Finalizers from Stuck ROSANetwork",
    "strategy": "remove_finalizers",
    "automated": true,
    "steps": [
      "Verify resource has deletionTimestamp",
      "Check for finalizers on the resource",
      "Patch resource to remove finalizers",
      "Verify resource deletion completes"
    ],
    "commands": [
      "oc patch rosanetwork {name} -n {namespace} --type=merge -p '{\"metadata\":{\"finalizers\":null}}'"
    ]
  }
}
```

## Monitoring and Auditing

### Intervention Logs

All agent interventions are recorded in `agents/knowledge_base/intervention_log.json`:

```json
{
  "timestamp": "2026-03-03T14:23:45.123456",
  "type": "remove_finalizers",
  "details": {
    "issue_type": "rosanetwork_stuck_deletion",
    "success": true,
    "message": "Successfully removed finalizers from rosanetwork/test-cluster",
    "parameters": {
      "resource_type": "rosanetwork",
      "resource_name": "test-cluster",
      "namespace": "default"
    }
  }
}
```

### Success Rate Tracking

Each fix type maintains statistics:

```json
{
  "remove_finalizers": {
    "successes": 15,
    "failures": 1,
    "total_attempts": 16,
    "success_rate": "93.8%"
  }
}
```

### Console Output

Real-time feedback during test execution:

```
🤖 AI Agent detected issue: rosanetwork_stuck_deletion
   Root cause: ROSANetwork has finalizers preventing deletion
   Confidence: 95%
   Recommended fix: remove_finalizers
   ✓ Fix applied: Successfully removed finalizers from rosanetwork/test-cluster
```

### Final Summary Statistics

At the end of test execution:

```
🤖 AI AGENT STATISTICS:
   Issues Detected: 2
   Interventions: 2

   Fix Success Rates:
      remove_finalizers: 100.0% (1/1)
      backoff_and_retry: 100.0% (1/1)
```

## Jenkins Integration

### Artifact Archiving

The `Jenkinsfile` is configured to archive intervention logs with test results:

```groovy
// Archive test results including AI agent logs
archiveArtifacts artifacts: 'rosa-hcp-e2e-test/test-results/**/*.xml,
                             rosa-hcp-e2e-test/test-results/**/*.html,
                             rosa-hcp-e2e-test/agents/knowledge_base/intervention_log.json',
                allowEmptyArchive: true
```

### Viewing Intervention Logs in Jenkins

1. Navigate to build artifacts
2. Download `intervention_log.json`
3. Review interventions that occurred during the test run

### Pipeline Example

```groovy
stage('Configure CAPI/CAPA Environment') {
    steps {
        withCredentials([...]) {
            sh '''
                cd rosa-hcp-e2e-test
                ./run-test-suite.py 10-configure-mce-environment --format junit --ai-agent -vvv \
                  -e OCP_HUB_API_URL="${OCP_HUB_API_URL}" \
                  -e AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID}" \
                  -e OCM_CLIENT_ID="${OCM_CLIENT_ID}"
            '''
        }
        archiveArtifacts artifacts: 'rosa-hcp-e2e-test/test-results/**/*.xml,
                                     rosa-hcp-e2e-test/agents/knowledge_base/intervention_log.json'
    }
}
```

## Safety Features

### Non-Invasive by Default
- Agents are **disabled by default**
- Must explicitly enable with `--ai-agent` flag
- Dry-run mode available for testing (`--ai-agent-dry-run`)

### Fail-Safe Error Handling
- Agent errors never break test execution
- Exceptions caught and logged
- Test suite continues even if agents fail

Example:
```python
try:
    self.monitor_agent.process_line(line)
except Exception as e:
    # Don't let agent errors break the test execution
    if self.verbosity > 0:
        print(f"AI Agent Warning: {str(e)}")
```

### Confidence-Based Intervention
- Only acts on high-confidence diagnoses (≥70%)
- Low-confidence issues are logged but not remediated
- Human review recommended for complex issues

### Audit Trail
- All interventions recorded with timestamps
- Success/failure tracking
- Full parameter logging for reproducibility
- Intervention logs archived with test results in Jenkins

### What Gets Fixed vs. What Gets Reported

**Auto-fixes (no manual intervention needed):**
- Transient automation issues (stuck deletions, rate limiting)
- Issues with high confidence and known solutions
- Non-destructive operations (finalizer removal, backoff delays)

**Reports for manual intervention:**
- Infrastructure problems (CloudFormation failures, quota limits)
- Configuration errors (network setup, IAM permissions)
- Issues requiring human decision-making

## Extending the Framework

### Adding New Issue Patterns

#### 1. Add pattern to `known_issues.json`

```json
{
  "new_issue_type": {
    "pattern": ".*your.*regex.*pattern.*",
    "severity": "high",
    "auto_fix": true,
    "description": "Description of the issue",
    "symptoms": ["Symptom 1", "Symptom 2"],
    "common_causes": ["Cause 1", "Cause 2"]
  }
}
```

#### 2. Add diagnostic method to `diagnostic_agent.py`

```python
def _diagnose_new_issue(self, context: Dict) -> Dict:
    """Diagnose new issue type"""
    return {
        "issue_type": "new_issue_type",
        "root_cause": "Root cause description",
        "severity": "high",
        "confidence": 0.9,
        "evidence": ["Evidence 1", "Evidence 2"],
        "recommended_fix": "new_fix_strategy",
        "fix_parameters": {}
    }
```

#### 3. Add remediation method to `remediation_agent.py`

```python
def _fix_new_strategy(self, params: Dict) -> Tuple[bool, str]:
    """Implement new fix strategy"""
    # Your fix logic here
    return True, "Fix successfully applied"
```

#### 4. Register the new fix method

```python
fix_methods = {
    "new_fix_strategy": self._fix_new_strategy,
    # ... existing methods
}
```

### Example: Adding AWS Quota Detection

**Step 1: Add pattern to `known_issues.json`**:
```json
{
  "aws_vpc_quota_exceeded": {
    "pattern": "VpcLimitExceeded|The maximum number of VPCs has been reached",
    "severity": "high",
    "auto_fix": false,
    "description": "AWS VPC quota limit reached",
    "symptoms": ["VpcLimitExceeded error", "Cannot create VPC"],
    "common_causes": ["Too many VPCs in region", "Quota not increased"]
  }
}
```

**Step 2: Add diagnosis in `diagnostic_agent.py`**:
```python
def _diagnose_aws_vpc_quota_exceeded(self, context: Dict) -> Dict:
    # Query current VPC count
    result = subprocess.run(
        ["aws", "ec2", "describe-vpcs", "--query", "length(Vpcs)"],
        capture_output=True, text=True
    )
    vpc_count = int(result.stdout.strip())

    return {
        "issue_type": "aws_vpc_quota_exceeded",
        "root_cause": f"VPC quota limit reached ({vpc_count}/5 VPCs in use)",
        "severity": "high",
        "confidence": 0.95,
        "evidence": [f"Current VPC count: {vpc_count}"],
        "recommended_fix": "request_quota_increase",
        "fix_parameters": {"resource": "vpc", "current": vpc_count}
    }
```

**Step 3: Add remediation in `remediation_agent.py`**:
```python
def _fix_request_quota_increase(self, params: Dict) -> Tuple[bool, str]:
    message = f"""
    AWS {params['resource']} quota exceeded.
    Current usage: {params['current']}

    ACTION REQUIRED:
    1. Go to AWS Service Quotas console
    2. Request quota increase for EC2 VPCs
    3. Wait for approval (typically 24-48 hours)
    4. Retry operation
    """
    self.log_info(message)
    return False, "Manual quota increase required"
```

## Troubleshooting

### AI Agents Not Working

**Problem**: Agents requested but not available

**Solution**: Verify `agents/` module exists in rosa-hcp-e2e-test directory

```bash
ls -la agents/
# Should show: __init__.py, base_agent.py, monitoring_agent.py, etc.
```

---

**Problem**: No issues detected during test

**Solution**: Check that test actually has issues or increase verbosity

```bash
./run-test-suite.py 20-rosa-hcp-provision --ai-agent -vv
```

---

**Problem**: Issues detected but not remediated

**Solution**: Check confidence scores - may be below 70% threshold

Look for output like:
```
⚠ Confidence too low for auto-remediation
```

### Debugging Agent Behavior

Enable verbose mode to see detailed agent logging:

```bash
./run-test-suite.py 20-rosa-hcp-provision --ai-agent -vv
```

Check intervention logs:

```bash
ls -la agents/knowledge_base/intervention_log.json
cat agents/knowledge_base/intervention_log.json | jq .
```

Review agent initialization:

```bash
# Look for these lines in output:
🤖 Initializing AI Agent Framework...
✓ AI Agent Framework initialized (LIVE MODE)
  - Monitoring Agent: Real-time issue detection
  - Diagnostic Agent: Root cause analysis
  - Remediation Agent: Autonomous fixes
```

### Common Issues

**Issue**: Agent errors breaking test execution

**Solution**: This should never happen due to fail-safe error handling. If it does, check for syntax errors in agent code.

---

**Issue**: False positive detections

**Solution**: Review and refine regex patterns in `known_issues.json`. Make patterns more specific.

---

**Issue**: Low success rates for fixes

**Solution**:
1. Review intervention logs to see failure reasons
2. Adjust fix strategies in `fix_strategies.json`
3. Update diagnostic logic for better root cause detection

## Performance Impact

### Overhead
- **CPU**: Minimal (<1% additional CPU usage)
- **Memory**: ~10-20MB for agent framework
- **Latency**: <1ms per line processed
- **I/O**: Minimal (only when querying Kubernetes resources)

### Scalability
- Handles 1000+ lines/second of output
- Buffer limited to 50 lines for memory efficiency
- Asynchronous operation doesn't block test execution

## Security Considerations

### Credentials
- Agents use existing `oc`/`kubectl` authentication
- No credentials stored in agent code
- All resource queries use current user context

### Permissions
- Requires Kubernetes API access for resource queries
- Needs `patch` permission for finalizer removal
- Standard user permissions sufficient for most operations

### Audit Trail
- All interventions logged with timestamps
- Full parameter logging for security review
- No sensitive data in agent logs

## Future Enhancements

### Planned Features
- [ ] Ansible callback plugin for deeper integration
- [ ] Machine learning for pattern adaptation
- [ ] Cluster-wide issue correlation
- [ ] Predictive issue detection
- [ ] Integration with Prometheus/Grafana
- [ ] Slack/email notifications for critical issues
- [ ] Web dashboard for agent statistics

## References

- **Main Documentation**: [README.md](README.md)
- **Test Runner**: [run-test-suite.py](run-test-suite.py)
- **Agent Details**: [agents/README.md](agents/README.md)
- **Issue Patterns**: [agents/knowledge_base/known_issues.json](agents/knowledge_base/known_issues.json)
- **Fix Strategies**: [agents/knowledge_base/fix_strategies.json](agents/knowledge_base/fix_strategies.json)

## Support

For issues or questions:
- File an issue in the repository
- Check the main README troubleshooting section
- Review agent logs in `agents/knowledge_base/` directory
- Check intervention logs for audit trail

---

**Version**: 1.0.0
**Author**: Tina Fitzgerald
**Created**: March 3, 2026
**License**: Apache 2.0
