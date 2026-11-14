export type InvitationEmailStatus = 'sent' | 'failed' | 'not-attempted'

/** Mensaje contractual mostrado al administrador cuando la invitación no se entrega. */
export function invitationDeliveryMessage(
  status: InvitationEmailStatus,
): string | null {
  if (status === 'failed') {
    return "La cuenta y la invitación se crearon correctamente, pero hubo un problema al enviar el correo electrónico. Por favor, utiliza la opción de 'Reenviar invitación' desde el panel más tarde."
  }
  if (status === 'not-attempted') {
    return 'No se pudo enviar el correo porque el servicio aún no está configurado'
  }
  return null
}
