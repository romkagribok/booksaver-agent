from booksaver.domain.check_result import FailureCode


def test_recovery_failure_codes_are_stable_and_distinct() -> None:
    assert FailureCode.AGENT_NO_PROGRESS.value == "agent_no_progress"
    assert FailureCode.LLM_ERROR.value == "llm_error"
    assert len(
        {
            FailureCode.AGENT_NO_PROGRESS,
            FailureCode.LLM_ERROR,
            FailureCode.AGENT_GAVE_UP,
            FailureCode.BUDGET_EXCEEDED,
        }
    ) == 4
