"""Legacy string-criterion compatibility gate: never infer PASS from list length."""
from flux.contracts.reviewer import ReviewDecision


def strict_review(parsed, criteria, checks):
    decision_type=parsed.get('decision')
    if decision_type not in {'ACCEPT_CANDIDATE','REVISE','ESCALATE','REJECT'}:
        return ReviewDecision(decision='ESCALATE',confidence='low')
    if decision_type!='ACCEPT_CANDIDATE':return ReviewDecision.model_validate(parsed)
    passed=parsed.get('passed_criteria',[])
    failed=parsed.get('failed_criteria',[])
    issues=parsed.get('blocking_issues',[])
    if not isinstance(passed,list) or not isinstance(failed,list) or not isinstance(issues,list):raise ValueError('Malformed reviewer lists.')
    blocking=[]
    for issue in issues:
        if isinstance(issue,str):blocking.append({'criterion':'review conflict','evidence':issue,'required_change':'Resolve the review conflict.'})
        elif isinstance(issue,dict):blocking.append({'criterion':str(issue.get('criterion') or 'review conflict'),'evidence':str(issue.get('evidence') or issue),'required_change':str(issue.get('required_change') or 'Resolve the review conflict.')})
        else:raise ValueError('Malformed review issue.')
    missing=[c for c in criteria if c not in passed]
    for criterion in missing+failed:
        blocking.append({'criterion':criterion,'evidence':'Exact criterion is missing or reported failed.','required_change':'Review this criterion with concrete evidence.'})
    for check in checks:
        if check.status!='passed':blocking.append({'criterion':check.name,'evidence':check.evidence or check.status,'required_change':'Run and verify this check.'})
    if len(passed)!=len(set(passed)) or any(c not in criteria for c in passed):
        blocking.append({'criterion':'criterion identity','evidence':'Duplicate or unknown passed criteria.','required_change':'Use exact immutable root criterion strings.'})
    if blocking:
        return ReviewDecision(decision='REVISE',blocking_issues=blocking,passed_criteria=[c for c in criteria if c in passed and c not in failed],failed_criteria=list(dict.fromkeys(missing+failed)),confidence='low')
    return ReviewDecision.model_validate(parsed)
