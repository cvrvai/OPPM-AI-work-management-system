-- Store task owners against unified OPPM project members so virtual members
-- can participate in the owner grid alongside workspace-backed members.

DO $$
DECLARE
    current_fk_target TEXT;
BEGIN
    SELECT confrelid::regclass::text
    INTO current_fk_target
    FROM pg_constraint
    WHERE conrelid = 'task_owners'::regclass
      AND conname = 'task_owners_member_id_fkey'
    LIMIT 1;

    IF current_fk_target LIKE '%workspace_members' THEN
        ALTER TABLE task_owners ADD COLUMN IF NOT EXISTS all_member_id UUID;

        INSERT INTO oppm_project_all_members (project_id, workspace_member_id, display_order, is_leader)
        SELECT DISTINCT t.project_id, o.member_id, 0, FALSE
        FROM task_owners o
        JOIN tasks t ON t.id = o.task_id
        LEFT JOIN oppm_project_all_members pam
            ON pam.project_id = t.project_id
           AND pam.workspace_member_id = o.member_id
        WHERE pam.id IS NULL;

                UPDATE task_owners o
                SET all_member_id = pam.id
                FROM tasks t, oppm_project_all_members pam
                WHERE o.task_id = t.id
                    AND pam.project_id = t.project_id
                    AND pam.workspace_member_id = o.member_id
                    AND o.all_member_id IS NULL;

        IF EXISTS (SELECT 1 FROM task_owners WHERE all_member_id IS NULL) THEN
            RAISE EXCEPTION 'Unable to migrate task_owners.member_id to oppm_project_all_members.id';
        END IF;

        ALTER TABLE task_owners DROP CONSTRAINT IF EXISTS task_owners_member_id_fkey;
        ALTER TABLE task_owners DROP CONSTRAINT IF EXISTS uq_task_owners_task_member;
        DROP INDEX IF EXISTS ix_task_owners_member_id;

        ALTER TABLE task_owners DROP COLUMN member_id;
        ALTER TABLE task_owners RENAME COLUMN all_member_id TO member_id;

        ALTER TABLE task_owners
            ADD CONSTRAINT task_owners_member_id_fkey
            FOREIGN KEY (member_id) REFERENCES oppm_project_all_members(id) ON DELETE CASCADE;
        CREATE INDEX IF NOT EXISTS ix_task_owners_member_id ON task_owners(member_id);
        ALTER TABLE task_owners
            ADD CONSTRAINT uq_task_owners_task_member UNIQUE (task_id, member_id);
    END IF;
END $$;