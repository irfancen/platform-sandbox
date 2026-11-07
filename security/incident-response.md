# Troubleshooting and Incident Response

## Scenario A: Critical vulnerability in the base image blocks a release

Trivy fails the pipeline on a Critical CVE in the base image, and the team asks to deploy to production anyway because "the app works".

### Investigation and risk assessment

1. **Identify the finding.** Get the CVE, the package, the installed version and whether a fixed version exists, from the `trivy-results` artifact.
2. **Judge real exploitability.**
   - Is the vulnerable package loaded by the app at all? For example, a sqlite flaw doesn't matter if the app never opens a database.
   - Is the service internet-facing?
   - Is there a public exploit (CISA KEV, a high EPSS score)?
3. **Check production.** Is the same CVE already in the image running in production? If it is, blocking this release doesn't reduce exposure, and the fix becomes the priority instead.

### Likely root causes

- A new CVE was published against a base image that hasn't changed. This is the usual case, and the Monday re-scan is designed to catch it.
- The base-image digest is stale because a Dependabot PR hasn't been merged.
- A new package pulled in a vulnerable library.

### Corrective actions

1. **Fix first.**
   - Rebuild with the patched base image (merge or create the digest bump), or drop the package.
   - Then let the pipeline go green and release normally.
   - When a patch exists, this usually takes minutes.
2. **No fix exists, and it isn't exploitable here.** If every condition in the [policy](vulnerability-policy.md#releasing-with-a-critical-or-high-that-has-no-fix) holds, add an exception to `.trivyignore.yaml` (evidence in `statement`, `expired_at` at most 7 days), approved by the service owner and security in a PR. The pipeline re-runs and passes on that basis.
3. **Exploitable, and the release is urgent** (for example, a fix for an outage):
   - An accountable owner, such as the head of engineering with security, signs off on the risk in writing for a limited time.
   - Compensating controls go in first: a WAF rule, tighter network access, or disabling the affected feature.

**Release authorization:** the gate is never bypassed by disabling the job or force-merging. The only way through is a reviewed exception, followed by the normal `prod` approval. "The app works" is a functional test, not a security decision.

**Follow-up:** track the fix against the 2-day deadline for Criticals in the [vulnerability policy](vulnerability-policy.md), and remove the exception once a patch ships.

## Scenario B: ECS Fargate task cannot retrieve its secret

### Investigation

Start with the error, because it tells you which layer failed:

```bash
aws ecs describe-tasks --cluster <cluster> --tasks <task-id> \
  --query 'tasks[0].{reason: stoppedReason, containers: containers[].reason}'
```

`ResourceInitializationError ... AccessDeniedException` points to IAM or KMS. `... context deadline exceeded` or `i/o timeout` points to the network.

| Area | What to check |
|---|---|
| **Execution role vs task role** | Secrets in the task definition's `secrets` / `valueFrom` are fetched by the ECS agent using the **task execution role**, before the container starts. The **task role** is only for calls the app makes at runtime. Granting the permission to the task role instead of the execution role is the most common mistake. |
| **Secrets Manager permission** | The execution role needs `secretsmanager:GetSecretValue` on the exact secret ARN. That ARN ends in a random 6-character suffix (`name-AbC123`), so a policy written with just the name doesn't match. Also check `valueFrom` for a JSON key or version, and the secret's resource policy for an explicit `Deny`. |
| **KMS** | If the secret uses a customer-managed key, the execution role needs `kms:Decrypt` on that key, *and* the key policy must allow it. The default `aws/secretsmanager` key needs nothing extra. |
| **Network** | A task in a private subnet needs a route to Secrets Manager: either a NAT gateway, or VPC interface endpoints for `secretsmanager`, `ecr.api`, `ecr.dkr` and `logs`, plus the S3 gateway endpoint. Check that the endpoint security group allows 443 from the task security group, that private DNS is on, and that the task's egress rules and NACLs allow 443. |
| **Logs and events** | If the container never started, there are no app logs. Use ECS service events, the stopped reason, and CloudTrail: a `GetSecretValue` or `Decrypt` event with `errorCode: AccessDenied` shows exactly which principal was denied which action. |

### Isolating the problem without admin rights

Every step uses read-only access (ViewOnly or SecurityAudit):

- **Test the IAM policy without changing anything:**

  ```bash
  aws iam simulate-principal-policy --policy-source-arn <execution-role-arn> \
    --action-names secretsmanager:GetSecretValue --resource-arns <secret-arn>
  ```

- **Find the denial in CloudTrail:** look up `GetSecretValue` and `Decrypt` events with an error code.
- **Test the network path:** run VPC Reachability Analyzer from the task's network interface to the VPC endpoint or NAT gateway.
- **Fix only the missing piece,** in Terraform, through a PR: one action on one ARN. Never grant `*` or attach an admin policy "to see if it helps".

### Likely root causes

- The permission was added to the task role instead of the execution role.
- A hand-typed secret ARN is missing its random suffix.
- The CMK key policy doesn't allow the role.
- There's no NAT or VPC endpoint in a private subnet, or a security group blocks 443.

### Corrective actions

- Reference the secret and key ARNs from Terraform resources instead of typing them, so the policy always matches.
- Alarm on ECS task start failures.

In this repo's EKS design, the same job is done by the Pod Identity app role ([terraform/iam.tf](../terraform/iam.tf)). A failure there shows up in the pod's logs, because the app refuses to start without its secret.

## Scenario C: Unexpected AWS API calls from the pipeline's IAM principal

### Immediate containment (first minutes)

1. **Stop new credentials.**
   - Disable the workflow or the `prod` environment in GitHub.
   - Change the deploy role's trust policy to deny all, or block the role with an SCP.
2. **Kill existing sessions.** Use IAM "Revoke active sessions" on the role. This denies every token issued before now, using `aws:TokenIssueTime`. OIDC sessions expire within 1 hour anyway, but don't wait. If any long-lived access key is involved, **deactivate** it rather than deleting it, so it can still be investigated.
3. **Preserve evidence.**
   - Don't delete what the attacker created yet; tag it and snapshot it.
   - Make sure the CloudTrail logs are in the log-archive account with S3 Object Lock, and export the relevant events.

### Investigation

- **Scope the activity.** List everything the role's sessions did during the window, and compare it with normal behaviour: the expected user agent, regions and event names.

  ```bash
  aws cloudtrail lookup-events --start-time <t0> \
    --lookup-attributes AttributeKey=EventName,AttributeValue=AssumeRoleWithWebIdentity
  aws cloudtrail lookup-events --start-time <t0> \
    --lookup-attributes AttributeKey=AccessKeyId,AttributeValue=<ASIA...>
  ```

  Each `AssumeRoleWithWebIdentity` event records the token's `sub` (repo and environment). Match it to a specific workflow run.
- **Find how it happened.** Correlate with the GitHub audit log and the run logs: which commit, who pushed and approved, and whether workflows, Actions or dependencies changed. Decide whether this is:
  - **stolen credentials:** used from an unknown IP or outside any workflow run;
  - **a compromised pipeline:** a malicious workflow change, a poisoned Action or dependency, or a compromised runner;
  - **over-broad permissions:** a legitimate step doing more than intended.
- **List the affected resources:**
  - ECR images pushed, with digests compared against what the pipeline built;
  - changes to the app namespace, from the EKS audit logs;
  - any new IAM entities or resources in unused regions;
  - GuardDuty findings.

  Calls the deploy role shouldn't be able to make at all mean its permissions are broader than designed.

### Recovery

1. **Remove what the attacker left.**
   - Delete unknown image digests.
   - Roll the deployment back to the last known-good digest.
   - Delete any IAM users, keys, roles or resources they created.
2. **Rotate anything the role could read.** By design, the deploy role can't read secrets. If the investigation shows it could, rotate those secrets.
3. **Fix the cause.**
   - Revert the malicious change.
   - Pin the Actions to commit SHAs.
   - Rebuild runners from scratch.
   - Narrow the trust policy and permissions.
4. **Re-enable gradually,** with alerts on this role's activity: EventBridge or CloudTrail metric filters on unexpected event names, regions or source IPs, plus GuardDuty.
5. **Run a post-incident review** with a timeline and actions. If personal data was exposed, legal and compliance handle notification; Indonesia's personal data protection law (UU PDP) requires notice within 3×24 hours.
