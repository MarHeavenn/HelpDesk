-- HU-19: fecha de alta de las cuentas (RF-141).
--
-- RF-141 ordena las cuentas administradoras de una empresa por fecha de alta
-- ascendente y, en empate, por identificador. El almacen de cuentas no
-- guardaba esa fecha, asi que se anade como columna de solo lectura para el
-- resto del sistema. Las filas preexistentes toman la fecha de aplicacion de
-- esta migracion: la fecha exacta de alta original no es recuperable.
ALTER TABLE identity_invitation_accounts
    ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();
