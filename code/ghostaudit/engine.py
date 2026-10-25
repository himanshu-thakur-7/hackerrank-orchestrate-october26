"""Case engine. T02 placeholder: every case is NOT_APPLICABLE with no steps, so the pipeline is
contract-valid end to end. Stages 3-8 (docs/03_DESIGN.md §3) replace this from T03 onward."""


def audit(request, resolver, intent_result):
    return request["case_id"], "NOT_APPLICABLE", []
