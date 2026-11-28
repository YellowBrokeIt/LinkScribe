"""Pure, model-free guards for the two-case summary experiment."""
import math

PHASES = ('prepare', 'english', 'greek')
CASE_IDS = ('summary-en-consent-and-roles', 'summary-el-workshop-counts')
TOTAL_SECONDS = 900
RSS_BYTES = 6144 * 1024 ** 2
SUMMARY_CHECKS = {
    'one_exact_declared_request', 'request_timeout_240s', 'normal_completion',
    'empty_reasoning', 'nonempty_final_content', 'output_below_cap',
    'actual_prompt_count_matches_preflight', 'strict_raw_summary_schema',
    'application_result_accepted', 'application_projection_exact',
    'original_source_unchanged', 'authentic_single_chapter_start',
    'one_exact_unload_acknowledged', 'resident_models_empty', 'case_below_600s',
}


def require(value, message):
    if not value:
        raise ValueError(message)


def verify_authorization(value, phase, plan_sha, independent_review_sha):
    require(phase in PHASES and value.get('phase') == phase, 'Authorization names another phase.')
    require(value.get('plan_sha256') == plan_sha, 'Authorization does not bind this exact plan.')
    require(value.get('root_authorized') is True and value.get('local_model_slot_reserved') is True,
            'Root execution authorization and exclusive model slot are required.')
    require(value.get('independent_review_sha256') == independent_review_sha,
            'Independent review identity does not match authorization.')
    require(value.get('runner_author_self_approval') is False,
            'The runner author cannot approve this experiment.')


def remaining_seconds(previous_resources):
    """Count measured preparation and both model phases; human review time is excluded."""
    elapsed = 0.0
    for report in previous_resources:
        require(report.get('passed') is True and report.get('complete') is True,
                'A preceding measured phase did not complete successfully.')
        require(report.get('worker_exit_code') == 0 and report.get('owned_processes_stopped') is True,
                'A preceding worker or owned process did not stop cleanly.')
        value = report.get('elapsed_seconds')
        require(type(value) in (int, float) and math.isfinite(value) and value > 0,
                'A preceding phase has no valid measured elapsed time.')
        require(report.get('measurement_complete') is True and not report.get('measurement_errors'),
                'A preceding phase has incomplete resource measurements.')
        peak = report.get('peak_rss_sample', {}).get('rss_bytes')
        require(type(peak) is int and 0 < peak <= RSS_BYTES,
                'A preceding recorded RSS peak exceeded the fixed budget.')
        elapsed += value
    require(elapsed < TOTAL_SECONDS, 'The shared 900-second model-stage budget is exhausted.')
    return TOTAL_SECONDS - elapsed


def verify_english_acceptance(decision, report, resources, bindings):
    require(report.get('id') == CASE_IDS[0] and report.get('complete') is True,
            'The English case is not complete.')
    checks = report.get('checks', {})
    require(report.get('structural_pass') is True and set(checks) == SUMMARY_CHECKS
            and all(value is True for value in checks.values()),
            'The English case did not pass its execution contract.')
    remaining_seconds([resources])
    for key in ('plan_sha256', 'english_report_sha256', 'english_resources_sha256',
                'original_review_criteria_sha256', 'source_cases_sha256'):
        require(decision.get(key) == bindings[key], 'English semantic decision identity mismatch: ' + key)
    require(decision.get('case_id') == CASE_IDS[0] and decision.get('review_complete') is True,
            'A completed independent English meaning review is required.')
    require(decision.get('independent_of_runner_author') is True,
            'English meaning must be reviewed independently of this runner author.')
    require(type(decision.get('major_error_count')) is int and decision['major_error_count'] == 0,
            'A material English meaning error blocks the Greek case.')
    require(decision.get('original_criteria_satisfied') is True
            and decision.get('paragraph_points_and_chapter_reviewed') is True
            and decision.get('approved_to_run_greek') is True,
            'English has not met the unchanged complete development criterion.')


def native_response_checks(response, prompt_tokens):
    message = response.get('message', {}) if isinstance(response, dict) else {}
    count = response.get('eval_count') if isinstance(response, dict) else None
    return {
        'normal_completion': isinstance(response, dict) and response.get('done') is True
                             and response.get('done_reason') == 'stop',
        'empty_reasoning': isinstance(message.get('thinking', ''), str)
                           and not message.get('thinking', '').strip(),
        'nonempty_final_content': isinstance(message.get('content'), str)
                                 and bool(message.get('content', '').strip()),
        'output_below_cap': type(count) is int and 0 < count < 2048,
        'actual_prompt_count_matches_preflight': isinstance(response, dict)
                                                and response.get('prompt_eval_count') == prompt_tokens,
    }


def raw_summary_matches_schema(value):
    return (isinstance(value, dict) and set(value) == {'summary', 'key_points', 'chapter_title'}
            and isinstance(value['summary'], str) and bool(value['summary'].strip())
            and isinstance(value['chapter_title'], str) and bool(value['chapter_title'].strip())
            and isinstance(value['key_points'], list) and 1 <= len(value['key_points']) <= 8
            and all(isinstance(point, str) and bool(point.strip()) for point in value['key_points']))


def final_phase_checks(phase, resources, report, allowed_seconds):
    """Never infer worker success merely from its exit code or polling samples."""
    errors = []
    def check(condition, reason):
        if not condition:
            errors.append(reason)
    elapsed = resources.get('elapsed_seconds')
    check(type(elapsed) in (int, float) and math.isfinite(elapsed)
          and 0 < elapsed <= allowed_seconds, 'final_measured_phase_time')
    check(resources.get('passed') is True and resources.get('owned_processes_stopped') is True,
          'external_resource_or_cleanup_failure')
    initialized = [event for event in resources.get('events', []) if event.get('event') == 'initialized']
    observed = initialized[0].get('observed_elapsed_seconds') if len(initialized) == 1 else None
    check(type(observed) in (int, float) and math.isfinite(observed) and 0 <= observed <= 180,
          'final_initialization_time')
    if not isinstance(report, dict):
        return errors + ['missing_phase_report']
    check(report.get('complete') is True and report.get('owned_daemon_stopped') is True,
          'incomplete_worker_or_daemon_cleanup')
    check(report.get('plan_sha256') == resources.get('plan_sha256'), 'phase_report_plan')
    check(report.get('frozen_inputs_unchanged') is True, 'frozen_source_drift')
    check(report.get('generation_calls') == (0 if phase == 'prepare' else 1), 'generation_count')
    check(report.get('native_create_calls') == 0 and report.get('model_downloads') == 0,
          'unrequested_native_mutation')
    check(report.get('resident_after_unload', {}).get('models') == [], 'resident_models_remain')
    if phase == 'prepare':
        check([p.get('id') for p in report.get('prompts', [])] == list(CASE_IDS), 'complete_preflight_order')
        check(report.get('unload_response', {}).get('done') is True
              and report.get('unload_response', {}).get('done_reason') == 'unload', 'prepare_unload')
    else:
        checks = report.get('checks', {})
        check(set(checks) == SUMMARY_CHECKS and all(value is True for value in checks.values())
              and report.get('structural_pass') is True, 'complete_summary_execution_checks')
        check(report.get('id') == CASE_IDS[0 if phase == 'english' else 1], 'phase_case_identity')
    return errors
