-- HU-26 B.I.2: conservar datos propios del ticket sin reconstruir el legado.
-- La ausencia de nombre, resolución u objetivo histórico se representa con NULL.
-- El runner confirma el esquema y su versión en la misma transacción.
ALTER TABLE tickets
    ADD COLUMN assignee_name text,
    ADD COLUMN resolved_at timestamptz,
    ADD COLUMN resolved_target_minutes integer;
