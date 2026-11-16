"""Add a candidate cohort while preserving existing listening campaigns."""


def _install_candidate_report(connection):
    from workforce_intelligence.dataset import (
        AuditActor,
        advance_revision,
        current_dataset,
        record_audit,
    )
    from workforce_intelligence.voice_campaigns import TEMPLATE_ID, populate_candidate_feedback

    if connection.execute("SELECT 1 FROM dataset_state").fetchone() and populate_candidate_feedback(
        connection
    ):
        state = advance_revision(connection, current_dataset(connection))
        record_audit(
            connection,
            state,
            AuditActor("workforce-seed", "req_candidate_fixture", "seed"),
            entity_type="survey",
            entity_key=TEMPLATE_ID,
            action="seed_candidate_feedback",
            old_values=None,
            new_values={"synthetic": True, "seed": 1516},
        )


CANDIDATE_MIGRATION = (
    """
    ALTER TABLE voice_campaign_settings ADD COLUMN candidate_audience TEXT
    CHECK (candidate_audience IS NULL OR (candidate_audience = 'candidates' AND audience = 'employees'))
    """,
    _install_candidate_report,
)
